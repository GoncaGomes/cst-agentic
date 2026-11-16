"""Model-led discovery of every tool group with CST connectivity disabled.

Only the application ``discover_tools`` function is exposed. The MCP catalogue
is read once; no MCP tools are executed or activated by this probe.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from agents import Agent, RunConfig, Runner
from agents.exceptions import AgentsException, MaxTurnsExceeded
from openai import AsyncOpenAI

from .config import ConnectivityConfig
from .connectivity import (
    REPORTS_PATH,
    Check,
    _build_provider,
    _model_tool_calls,
    save_json_report,
)
from .mcp_client import CstMcpClient
from .tool_gateway import build_discovery_tool
from .tool_groups import GROUPS, ToolGroups

MAX_TURNS = 24
REPORT_NAME = "one_call_tool_discovery.json"

SYSTEM_INSTRUCTIONS = (
    "You are testing tool discovery, not operating CST. Go through every group "
    "listed in the discover_tools catalogue. Call discover_tools once per group, "
    "passing only that group's identifier in groups. Do not skip or repeat groups. "
    "If a lookup reports missing tools, record that limitation and continue with "
    "the remaining groups. After visiting every group, report the exact MCP tool "
    "names returned, grouped by capability, and the number of unique tools found. "
    "Distinguish missing tools from tools found. Base the inventory only on the "
    "returned definitions; do not invent tools. Do not call any discovered MCP "
    "tool: this test does not activate or execute them. Finish within 24 turns."
)
USER_TASK = (
    "Go through each available tool group using discover_tools, then report all "
    "MCP tools found across the groups. Include their exact names and a deduplicated "
    "total, and note any missing tools or failed group lookups. Do not execute MCP tools."
)


@dataclass
class DiscoveryReport:
    """Outcome and evidence for one model-led discovery probe."""

    success: bool = False
    stage: str = "start"
    error: str | None = None
    server_name: str | None = None
    server_version: str | None = None
    discovered_tools: list[str] = field(default_factory=list)
    found_tools: list[str] = field(default_factory=list)
    exposed_tools: list[str] = field(default_factory=list)
    model_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    discovery_calls: list[dict[str, Any]] = field(default_factory=list)
    mcp_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str | None = None
    checks: list[Check] = field(default_factory=list)
    max_turns: int = MAX_TURNS
    duration_s: float = 0.0

    def summary(self) -> str:
        """Render a concise diagnostic summary without configuration values."""
        lines = [
            f"Tool group discovery: {'PASSED' if self.success else 'FAILED'} "
            f"(stage={self.stage}, {self.duration_s:.2f}s)",
            f"  server catalogue: {len(self.discovered_tools)} MCP tool(s)",
            f"  found through group lookups: {len(self.found_tools)} unique MCP tool(s)",
            f"  exposed to model: {', '.join(self.exposed_tools) or 'none'}",
            f"  discovery calls: {len(self.discovery_calls)}",
        ]
        for call in self.discovery_calls:
            lines.append(
                f"  groups={call['groups']} success={call['success']} "
                f"tools={[tool['name'] for tool in call['tools']]} "
                f"missing={call['missing_tools']}"
            )
        if self.final_answer is not None:
            answer = " ".join(self.final_answer.split())
            lines.append(f"  final answer: {answer[:400]}")
        for check in self.checks:
            mark = "ok " if check.passed else "FAIL"
            lines.append(f"  [{mark}] {check.name}: {check.detail}")
        if self.error is not None:
            lines.append(f"  error: {self.error}")
        return "\n".join(lines)


async def run_discovery_check(
    config: ConnectivityConfig,
    *,
    model: Any | None = None,
    mcp_client: CstMcpClient | None = None,
) -> DiscoveryReport:
    """Run and save the offline-mode probe, accepting substitutes for local tests."""
    started = time.monotonic()
    report = DiscoveryReport()
    provider_client: AsyncOpenAI | None = None
    groups: ToolGroups | None = None

    try:
        if mcp_client is None:
            mcp_client = CstMcpClient(
                executable=config.mcp_executable,
                cwd=config.mcp_cwd,
                env=config.discovery_child_env(os.environ),
                startup_timeout_s=config.startup_timeout_s,
                shutdown_timeout_s=config.shutdown_timeout_s,
                request_timeout_s=config.mcp_request_timeout_s,
            )
        if model is None:
            report.stage = "model_initialize"
            model, provider_client = await _build_provider(config)

        report.stage = "mcp_initialize"
        async with mcp_client as mcp:
            report.server_name = mcp.server_name
            report.server_version = mcp.server_version
            report.checks.append(
                Check("mcp_initialized", mcp.server_name is not None, "server identity received")
            )
            report.stage = "tool_discovery"
            definitions = await mcp.discover_tool_definitions()
            report.discovered_tools = [tool.name for tool in definitions]
            report.checks.append(
                Check("tools_discovered", bool(definitions), f"{len(definitions)} tool(s)")
            )
            groups = ToolGroups(definitions)
            discovery_tool = build_discovery_tool(groups)
            report.exposed_tools = [discovery_tool.name]
            agent = Agent(
                name="cst-tool-group-discovery-probe",
                model=model,
                instructions=SYSTEM_INSTRUCTIONS,
                tools=[discovery_tool],
            )
            report.stage = "model_run"
            result = await Runner.run(
                agent,
                USER_TASK,
                max_turns=MAX_TURNS,
                run_config=RunConfig(
                    tracing_disabled=True,
                    tool_not_found_behavior="return_error_to_model",
                ),
            )
            report.model_tool_calls = _model_tool_calls(result)
            output = result.final_output
            report.final_answer = str(output) if output is not None else None
        report.stage = "complete"
    except Exception as exc:  # noqa: BLE001 - return a diagnostic, not a CLI traceback
        if isinstance(exc, AgentsException) and exc.run_data is not None:
            report.model_tool_calls = _model_tool_calls(exc.run_data)
        # Do not retain raw provider/transport exception text: it can echo secrets.
        report.error = (
            f"Model exceeded the {MAX_TURNS}-turn limit."
            if isinstance(exc, MaxTurnsExceeded)
            else f"{report.stage} failed ({type(exc).__name__})."
        )
    finally:
        if groups is not None:
            report.discovery_calls = groups.calls
        if mcp_client is not None:
            report.mcp_tool_calls = [
                {"name": call.name, "arguments": call.arguments, "is_error": call.is_error}
                for call in mcp_client.calls
            ]
        if provider_client is not None:
            try:
                await provider_client.close()
            except Exception:  # noqa: BLE001 - preserve the primary failure, if any
                report.error = report.error or "Model client cleanup failed."
        _verify(report, mcp_client)
        report.duration_s = time.monotonic() - started
        report.success = (
            report.stage == "complete"
            and report.error is None
            and all(check.passed for check in report.checks)
        )

    save_json_report(report, REPORTS_PATH, REPORT_NAME)
    return report


def _verify(report: DiscoveryReport, mcp: CstMcpClient | None) -> None:
    """Score actual calls and returned evidence, not just the model's prose."""
    calls = report.discovery_calls
    report.found_tools = list(
        dict.fromkeys(tool["name"] for call in calls if call["success"] for tool in call["tools"])
    )
    reported_names = set(re.findall(r"\bcst_[A-Za-z0-9_]+\b", report.final_answer or ""))
    missing_names = {name for call in calls for name in call["missing_tools"]}
    report.checks.extend(
        [
            Check(
                "only_discovery_exposed",
                report.exposed_tools == ["discover_tools"],
                "only discover_tools may be exposed",
            ),
            Check(
                "model_requested_each_group",
                len(report.model_tool_calls) == len(GROUPS)
                and all(
                    {"name": "discover_tools", "arguments": {"groups": [name]}}
                    in report.model_tool_calls
                    for name in GROUPS
                ),
                f"{len(report.model_tool_calls)} model tool call(s); "
                f"expected one for each of {len(GROUPS)} groups",
            ),
            Check(
                "each_group_discovered",
                len(calls) == len(GROUPS)
                and all(any(call["groups"] == [name] for call in calls) for name in GROUPS),
                f"{len(calls)} executed group lookup(s); expected {len(GROUPS)}",
            ),
            Check(
                "canonical_groups_returned",
                bool(calls)
                and all(
                    call["success"]
                    and len(call["groups"]) == 1
                    and call["groups"][0] in GROUPS
                    and [tool["name"] for tool in call["tools"]] == list(GROUPS[call["groups"][0]])
                    for call in calls
                ),
                "every lookup must return its complete canonical group from MCP",
            ),
            Check(
                "no_mcp_tools_executed",
                mcp is not None and not mcp.calls and not mcp.attempts,
                "discovery must not dispatch any MCP tool",
            ),
            Check(
                "final_answer_reports_tools",
                bool(report.found_tools)
                and set(report.found_tools) <= reported_names
                and reported_names <= set(report.found_tools) | missing_names,
                f"answer must list all {len(report.found_tools)} tools found "
                "without inventing tool names",
            ),
        ]
    )
