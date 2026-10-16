"""Orchestration for the model/MCP connectivity check.

``run_connectivity_check`` drives the full sequence: start the MCP server in
disabled mode, initialize it, discover tools, expose only
``cst_connection_status`` to the institutional model, run a bounded agent
loop, and verify that the model actually called the tool through MCP and that
the returned status is disconnected. It always releases its model client and
MCP subprocess, and it returns a structured report rather than raising.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from agents import Agent, RunConfig, Runner
from agents.items import ToolCallItem
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from .config import ConnectivityConfig
from .mcp_client import CstMcpClient, McpError, McpToolCall
from .tool_gateway import ALLOWED_TOOLS, ToolGateway, build_status_tool

SYSTEM_INSTRUCTIONS = (
    "You are verifying connectivity to a CST Studio Suite MCP server that is "
    "running in disabled (offline) mode. Use the `cst_connection_status` tool "
    "to obtain the current connection status, then give a concise summary of "
    "the observed status. State the connection mode and whether a project is "
    "open. Report only what the tool returns; do not invent or assume any "
    "status."
)

USER_TASK = (
    "Call the cst_connection_status tool and summarize the CST connection status it reports."
)


@dataclass
class Check:
    """One named verification with a human-readable detail line."""

    name: str
    passed: bool
    detail: str


@dataclass
class ConnectivityReport:
    """The outcome and evidence of one connectivity check run."""

    success: bool
    stage: str
    error: str | None
    server_name: str | None = None
    server_version: str | None = None
    discovered_tools: list[str] = field(default_factory=list)
    exposed_tools: list[str] = field(default_factory=list)
    model_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    mcp_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    status_payload: dict[str, Any] | None = None
    final_answer: str | None = None
    checks: list[Check] = field(default_factory=list)
    duration_s: float = 0.0

    def summary(self) -> str:
        """Render a concise, credential-safe diagnostic summary."""
        lines = [
            f"Connectivity check: {'PASSED' if self.success else 'FAILED'} "
            f"(stage={self.stage}, {self.duration_s:.2f}s)"
        ]
        if self.server_name is not None:
            lines.append(
                f"  server: {self.server_name} (version {self.server_version or 'unknown'})"
            )
        if self.discovered_tools:
            preview = ", ".join(self.discovered_tools[:8])
            extra = len(self.discovered_tools) - 8
            more = f" (+{extra} more)" if extra > 0 else ""
            lines.append(f"  discovered {len(self.discovered_tools)} tool(s): {preview}{more}")
        if self.exposed_tools:
            lines.append(f"  exposed to model: {', '.join(self.exposed_tools)}")
        for call in self.model_tool_calls:
            lines.append(f"  model tool call: {call['name']} args={json.dumps(call['arguments'])}")
        for call in self.mcp_tool_calls:
            lines.append(
                f"  mcp tool call: {call['name']} args={json.dumps(call['arguments'])} "
                f"is_error={call['is_error']}"
            )
        if self.status_payload is not None:
            lines.append(
                "  status: mode="
                f"{self.status_payload.get('mode')!r} "
                f"project_open={self.status_payload.get('project_open')!r} "
                f"version={self.status_payload.get('cst_version')!r}"
            )
        if self.final_answer is not None:
            answer = " ".join(self.final_answer.split())
            if len(answer) > 400:
                answer = answer[:400] + "..."
            lines.append(f"  final answer: {answer}")
        for check in self.checks:
            mark = "ok " if check.passed else "FAIL"
            lines.append(f"  [{mark}] {check.name}: {check.detail}")
        if self.error is not None:
            lines.append(f"  error: {self.error}")
        return "\n".join(lines)


def _parse_tool_args(raw: Any) -> dict[str, Any]:
    """Normalize a model tool-call argument payload to a dict."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {"_raw": raw}
        return parsed if isinstance(parsed, dict) else {"_raw": parsed}
    return {"_raw": raw}


def _model_tool_calls(result: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for item in result.new_items:
        if isinstance(item, ToolCallItem):
            name = item.tool_name
            if name is None:
                continue
            raw = item.raw_item
            if isinstance(raw, dict):
                raw_args = raw.get("arguments")
            else:
                raw_args = getattr(raw, "arguments", None)
            calls.append({"name": name, "arguments": _parse_tool_args(raw_args)})
    return calls


async def _build_provider(config: ConnectivityConfig) -> tuple[Any, AsyncOpenAI]:
    """Build the institutional model and the client that owns its resources."""
    client = AsyncOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        timeout=config.request_timeout_s,
    )
    model = OpenAIChatCompletionsModel(model=config.model, openai_client=client)
    return model, client


async def run_connectivity_check(
    config: ConnectivityConfig,
    *,
    model: Any | None = None,
    mcp_client: CstMcpClient | None = None,
) -> ConnectivityReport:
    """Run the full connectivity check and return a report.

    Args:
        config: Validated connectivity settings.
        model: An injected ``Model`` (used by offline tests). When ``None``, an
            :class:`OpenAIChatCompletionsModel` is built from ``config``.
        mcp_client: An injected MCP client (used by offline tests). When
            ``None``, one is built from ``config``.

    The function never raises for expected failures; it returns a report with
    ``success`` set accordingly. It always releases the model client it created
    and the MCP subprocess, on success or failure.
    """
    started = time.monotonic()
    checks: list[Check] = []
    state: dict[str, Any] = {
        "stage": "start",
        "error": None,
        "server_name": None,
        "server_version": None,
        "discovered": [],
        "exposed": [],
        "model_calls": [],
        "mcp_calls": [],
        "status_payload": None,
        "final_answer": None,
    }

    def add_check(name: str, passed: bool, detail: str) -> None:
        checks.append(Check(name=name, passed=passed, detail=detail))

    # Build the MCP client (or accept an injected one).
    if mcp_client is None:
        mcp_client = CstMcpClient(
            executable=config.mcp_executable,
            cwd=config.mcp_cwd,
            env=config.child_env(os.environ),
            startup_timeout_s=config.startup_timeout_s,
            shutdown_timeout_s=config.shutdown_timeout_s,
            request_timeout_s=config.mcp_request_timeout_s,
        )

    # Build the model/provider (or accept an injected one).
    provider_client: AsyncOpenAI | None = None
    if model is None:
        model, provider_client = await _build_provider(config)

    try:
        async with mcp_client as mcp:
            state["stage"] = "mcp_initialize"
            state["server_name"] = mcp.server_name
            state["server_version"] = mcp.server_version
            add_check(
                "mcp_initialized",
                mcp.server_name is not None,
                f"server={mcp.server_name!r} version={mcp.server_version!r}",
            )

            state["stage"] = "tool_discovery"
            discovered = await mcp.discover_tools()
            state["discovered"] = discovered
            add_check(
                "tools_discovered",
                len(discovered) > 0,
                f"{len(discovered)} tool(s) discovered",
            )
            add_check(
                "status_tool_discovered",
                "cst_connection_status" in discovered,
                "cst_connection_status present in catalog"
                if "cst_connection_status" in discovered
                else "cst_connection_status missing from catalog",
            )

            state["stage"] = "model_run"
            gateway = ToolGateway(mcp)
            status_tool = build_status_tool(gateway)
            exposed_name = getattr(status_tool, "name", "cst_connection_status")
            state["exposed"] = [exposed_name]
            add_check(
                "status_tool_exposed",
                state["exposed"] == sorted(ALLOWED_TOOLS),
                f"exposed={state['exposed']}",
            )

            agent = Agent(
                name="cst-connectivity-probe",
                model=model,
                instructions=SYSTEM_INSTRUCTIONS,
                tools=[status_tool],
            )
            result = await Runner.run(
                agent,
                USER_TASK,
                max_turns=config.max_turns,
                run_config=RunConfig(
                    tracing_disabled=True,
                    tool_not_found_behavior="return_error_to_model",
                ),
            )

            final_output = result.final_output
            state["final_answer"] = (
                final_output
                if isinstance(final_output, str)
                else (str(final_output) if final_output is not None else None)
            )
            state["model_calls"] = _model_tool_calls(result)

        # After the MCP context exits, summarize the recorded MCP calls.
        for call in mcp_client.calls:
            state["mcp_calls"].append(
                {
                    "name": call.name,
                    "arguments": call.arguments,
                    "is_error": call.is_error,
                }
            )
        status_call = next((c for c in mcp_client.calls if c.name == "cst_connection_status"), None)
        if isinstance(status_call, McpToolCall):
            state["status_payload"] = status_call.payload

        _verify(state, checks)
        state["stage"] = "complete"

    except McpError as exc:
        state["error"] = f"MCP {state['stage']} failed: {exc}"
    except Exception as exc:  # noqa: BLE001 - report, don't crash the CLI
        state["error"] = f"stage={state['stage']}: {type(exc).__name__}: {exc}"
    finally:
        if provider_client is not None:
            try:
                await provider_client.close()
            except Exception:  # noqa: BLE001 - best effort cleanup
                pass

    passed = all(check.passed for check in checks)
    success = passed and state["error"] is None

    return ConnectivityReport(
        success=success,
        stage=state["stage"],
        error=state["error"],
        server_name=state["server_name"],
        server_version=state["server_version"],
        discovered_tools=state["discovered"],
        exposed_tools=state["exposed"],
        model_tool_calls=state["model_calls"],
        mcp_tool_calls=state["mcp_calls"],
        status_payload=state["status_payload"],
        final_answer=state["final_answer"],
        checks=checks,
        duration_s=time.monotonic() - started,
    )


def _verify(state: dict[str, Any], checks: list[Check]) -> None:
    """Populate the model/MCP/answer verification checks from collected state."""
    model_calls = state["model_calls"]
    mcp_calls = state["mcp_calls"]
    payload = state["status_payload"]
    final_answer = state["final_answer"]

    status_model_calls = [c for c in model_calls if c["name"] == "cst_connection_status"]
    add = checks.append

    add(
        Check(
            "model_requested_status_tool",
            any(c["arguments"] == {} for c in status_model_calls),
            f"{len(status_model_calls)} model call(s) of cst_connection_status",
        )
    )
    add(
        Check(
            "no_other_model_tool_calls",
            all(c["name"] in ALLOWED_TOOLS for c in model_calls),
            f"model called: {sorted({c['name'] for c in model_calls}) or 'none'}",
        )
    )

    status_mcp_call = next(
        (c for c in mcp_calls if c["name"] == "cst_connection_status" and c["arguments"] == {}),
        None,
    )
    add(
        Check(
            "mcp_executed_status_call",
            status_mcp_call is not None,
            "cst_connection_status dispatched through MCP with {} args"
            if status_mcp_call is not None
            else "no cst_connection_status call reached MCP",
        )
    )

    if status_mcp_call is not None:
        add(
            Check(
                "mcp_no_error",
                not status_mcp_call["is_error"],
                f"is_error={status_mcp_call['is_error']}",
            )
        )

    if isinstance(payload, dict):
        mode = payload.get("mode")
        project_open = payload.get("project_open")
        add(
            Check(
                "payload_offline",
                mode == "offline",
                f"mode={mode!r}",
            )
        )
        add(
            Check(
                "payload_project_closed",
                project_open is False,
                f"project_open={project_open!r}",
            )
        )
        payload_status = payload.get("status")
        add(
            Check(
                "payload_no_error_status",
                payload_status not in {"error", "busy", "timeout"},
                f"payload status={payload_status!r}",
            )
        )
    else:
        add(Check("payload_offline", False, "no status payload returned"))
        add(Check("payload_project_closed", False, "no status payload returned"))
        add(Check("payload_no_error_status", False, "no status payload returned"))

    answer = (final_answer or "").lower()
    summarizes = "offline" in answer or "disconnected" in answer
    add(
        Check(
            "final_answer_summarizes",
            summarizes,
            "answer references offline/disconnected status"
            if summarizes
            else "answer does not reference the disconnected status",
        )
    )
