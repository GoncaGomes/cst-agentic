"""Production manual-session factory, shared by terminal and future coordinator."""

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
from .recovery import RecoveryError, RecoveryStore


def admit_manual_catalogue(tools: list[Tool]) -> None:
    """Check bootstrap definitions, not model-visible inventory admission.

    No tools are exposed/dispatched by this lifecycle slice. #19/#24 must review
    schemas and enforcement before admitting any model-visible inventory.
    """
    names = [tool.name for tool in tools]
    required = {"cst_connect", "cst_disconnect", "cst_connection_status"}
    if len(set(names)) != len(names) or not required <= set(names):
        raise RecoveryError("Controller bootstrap catalogue is incompatible.")
    if any(tool.input_schema.get("type") != "object" for tool in tools):
        raise RecoveryError("Controller bootstrap schemas are incompatible.")


@dataclass(frozen=True)
class ManualController:
    """Lifecycle-only runtime; no dispatch or attachment interface is authorized."""

    model: OpenAIChatCompletionsModel
    run_config: RunConfig


EXIT_WARNING = (
    "Controller-launched CST instances are session-bound: no survival guarantee "
    "after exit or a crash. Unsaved work may be lost and active simulations may "
    "be interrupted. Live save/run state is unknown, not verified idle. "
    "Task completion never authorizes closing CST. This lifecycle-only session "
    "has not launched or attached to CST; exit does not dispatch save, stop, "
    "disconnect or close tools. Check CST directly if intervention is needed."
)


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
    """Lifecycle front end only; conversational dispatch belongs to #19/#24."""
    async with create_controller_session(config, state_directory=state_directory):
        write_line(
            "Controller ready in manual mode; CST was not launched or attached. "
            "Commands: help, quit. Modeling requires #19/#24; no tools are exposed."
        )
        while True:
            try:
                command = (await read_line("Controller> ")).strip().lower()
                if command in {"quit", "exit"}:
                    write_line(EXIT_WARNING)
                    confirmation = await read_line(
                        "Type exit to confirm, or anything else to stay: "
                    )
                    if confirmation.strip().lower() == "exit":
                        return 0
                    write_line("Exit cancelled.")
                elif command == "help":
                    write_line(
                        "Commands: help, quit. Work and attachment remain blocked pending #19/#24."
                    )
                elif command:
                    write_line(
                        "No work dispatched: conversational/target prerequisites "
                        "(#19/#24) are unavailable."
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
        store, client_factory, inventory=frozenset(), dispatch_check=lambda *args: None
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
