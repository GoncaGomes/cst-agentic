"""Production manual-session factory and thin coordinator terminal adapter."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from agents import RunConfig, set_trace_processors, set_tracing_disabled
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from mcp.types import Tool
from openai import AsyncOpenAI

from .controller import ControllerMcpClient, ControllerSession
from .controller_config import ControllerConfig
from .conversation import EXIT_WARNING, ConversationCoordinator
from .discovery import APPROVED_MCP_TOOLS, ToolDiscovery
from .recovery import RecoveryError, RecoveryStore


def admit_manual_catalogue(tools: list[Tool]) -> None:
    """Require faithful startup; unavailable optional groups do not block startup."""
    discovery = ToolDiscovery(tools)
    if discovery.blocker is not None:
        raise RecoveryError(discovery.blocker)


@dataclass(frozen=True)
class ManualController:
    """Shared runtime; unavailable production prerequisites remain blocked."""

    model: OpenAIChatCompletionsModel
    run_config: RunConfig
    coordinator: ConversationCoordinator | None = None


async def terminal_input(prompt: str) -> str:
    """Poll the Windows console without an uncancellable executor input thread.

    Redirected stdin is deliberately unsupported: a synchronous pipe read could
    keep the application alive after Ctrl+C. EOF follows the abnormal-exit path.
    """
    if sys.platform != "win32" or not sys.stdin.isatty():
        raise EOFError
    import msvcrt

    sys.stdout.write(prompt)
    sys.stdout.flush()
    characters: list[str] = []
    special_key = False
    while True:
        if not msvcrt.kbhit():
            await asyncio.sleep(0.02)
            continue
        character = msvcrt.getwch()
        if special_key:
            special_key = False
            continue
        if character in {"\x00", "\xe0"}:
            special_key = True
            continue
        if character in {"\r", "\n"}:
            sys.stdout.write("\n")
            sys.stdout.flush()
            return "".join(characters)
        if character == "\x1a":
            raise EOFError
        if character == "\x03":
            raise KeyboardInterrupt
        if character in {"\b", "\x7f"}:
            if characters:
                characters.pop()
                sys.stdout.write("\b \b")
        elif character.isprintable():
            characters.append(character)
            sys.stdout.write(character)
        sys.stdout.flush()


async def run_controller_terminal(
    config: ControllerConfig,
    *,
    read_line: Callable[[str], Awaitable[str]] = terminal_input,
    write_line: Callable[[str], None] = print,
    state_directory: Path | None = None,
) -> int:
    """Thin input/output adapter; the shared coordinator owns conversation policy."""
    async with create_controller_session(config, state_directory=state_directory) as runtime:
        coordinator = runtime.coordinator
        if coordinator is None:
            raise RecoveryError("Controller conversation coordinator is unavailable.")
        write_line(
            "Controller ready in manual mode; CST was not launched or attached. "
            "Enter a request or help. Live work requires reviewed prerequisites (#24)."
        )
        prompt = "Controller> "
        while True:
            try:
                reply = await coordinator.submit(
                    await read_line(prompt),
                    on_event=lambda event: write_line(event.text),
                )
                write_line(reply.text)
                if reply.state == "exit":
                    return 0
                prompt = (
                    "Type exit to confirm, or anything else to stay: "
                    if reply.state == "confirm_exit"
                    else "Controller> "
                )
            except EOFError:
                write_line(EXIT_WARNING)
                write_line(
                    "Input closed without confirmation; attempting bounded local cleanup only."
                )
                return 1
            except asyncio.CancelledError:
                write_line(EXIT_WARNING)
                write_line("Controller interrupted; attempting bounded local cleanup only.")
                raise


@asynccontextmanager
async def create_controller_session(
    config: ControllerConfig, *, state_directory: Path | None = None
) -> AsyncIterator[ManualController]:
    if config.context_budget is not None and not config.context_budget.matches(
        config.base_url, config.model
    ):
        raise RecoveryError("Controller context validation does not match the configured provider.")
    set_tracing_disabled(True)
    set_trace_processors([])
    store = RecoveryStore(state_directory)

    def client_factory() -> ControllerMcpClient:
        return ControllerMcpClient(
            executable=config.mcp_executable,
            cwd=config.mcp_cwd,
            env=config.child_env(os.environ),
            startup_timeout_s=config.startup_timeout_s,
            shutdown_timeout_s=config.shutdown_timeout_s,
            request_timeout_s=120,
            catalogue_admission=admit_manual_catalogue,
        )

    async with ControllerSession(
        store, client_factory, inventory=APPROVED_MCP_TOOLS, dispatch_check=lambda *args: None
    ) as session:
        await session.open_manual_transport()
        provider: AsyncOpenAI | None = None
        try:
            try:
                provider = AsyncOpenAI(
                    base_url=config.base_url, api_key=config.api_key, timeout=120, max_retries=0
                )
                model = OpenAIChatCompletionsModel(model=config.model, openai_client=provider)
            except Exception:
                raise RecoveryError("Controller provider initialization failed.") from None
            yield ManualController(
                model,
                RunConfig(model=model, tracing_disabled=True, trace_include_sensitive_data=False),
                ConversationCoordinator(
                    model=model,
                    connection=session,
                    store=store,
                    discovery=ToolDiscovery(session.catalogue),
                    catalogue_loader=session.refresh_catalogue,
                    allowlist=APPROVED_MCP_TOOLS,
                    context_budget=config.context_budget,
                ),
            )
        finally:
            primary = sys.exception()
            deadline = asyncio.get_running_loop().time() + config.shutdown_timeout_s
            session.begin_cleanup(deadline)
            if provider is not None:
                try:
                    async with asyncio.timeout_at(deadline):
                        await provider.close()
                except BaseException:
                    cleanup = RecoveryError("Controller provider cleanup failed.")
                    if primary is not None:
                        raise BaseExceptionGroup(
                            "Controller provider exit failed", [primary, cleanup]
                        ) from None
                    raise cleanup from None
