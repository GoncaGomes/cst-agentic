from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from agents import Agent, RunConfig, Runner
from agents.items import (
    ItemHelpers,
    MessageOutputItem,
    ReasoningItem,
    RunItem,
    ToolCallItem,
    ToolCallOutputItem,
)
from openai import AsyncOpenAI

from cst_agentic.config import ConnectivityConfig, load_connectivity_config
from cst_agentic.connectivity import _build_provider
from cst_agentic.mcp_client import CstMcpClient
from cst_agentic.tool_gateway import ToolGateway, build_discovery_tool, build_dispatch_tool
from cst_agentic.tool_groups import ToolGroups

MAX_TURNS = 1000
REPORT_NAME = "live_run.json"
REPORTS_PATH = Path("tests/reports")
ENV_PATH_DEFAULT = Path("./.env")

SYSTEM_INSTRUCTIONS = """You are a CST Studio Suite assistant. Use the available
MCP tools to carry out the user's current request. A request may describe an
entire project or one step in an ongoing project. Use the conversation history
to carry forward the target project and requirements. Perform the operations
authorized for the current step.

Before changing an existing project, verify its active path and state through
MCP. For a new project, use the requested path and type, then verify the active
project before editing it. Resolve the units, coordinate conventions, and
dependencies needed for the current step. Preserve stated dimensions, materials,
and relationships. State any material assumptions or delegated choices. Ask for
clarification when a conflict prevents faithful implementation.

Use discover_tools for the capabilities needed next and reuse known schemas.
Call dispatch_tool with the exact tool name and argument types. Define
parameters before using them in geometry expressions where supported. When
importing a library material, distinguish its library identifier from its name
in the project. Correct clear input validation errors and retry. If a call may
have changed CST state before failing, inspect the state before retrying. Pause
dependent work while a required operation remains unresolved.

When simulation is requested, check the relevant setup and wait for the solver
using bounded waits. Confirm that CST completed the simulation and that the
requested result entries or files exist. Compute or interpret performance
metrics only when the user explicitly requests an analysis. Treat checks of
supplied inputs, live project readback, solver status, result-tree entries, and
numerical results as distinct evidence.

In the final response, summarize what was executed and verified. Report relevant
assumptions, unresolved items, and solver warnings. Qualify each claim according
to the evidence returned by the tools."""

USER_PROMPT = """
Create a new CST Microwave Studio (MWS) project at
<C:/dev/projects-cst-attempts/attempt_patch> with the name second_simple_patch. The
working configuration is a single printed rectangular-plate monopole on one FR4
slab.

**Structure and materials.** One FR4 substrate, 90 mm (length) x 50 mm (width) x
1.52 mm thick, carries a 35 μm-thick metallization on both faces (copper
assumed, H001). On the front face the metallization forms the radiating
rectangular plate and the microstrip feedline; on the opposite (back) face it
forms the ground plane.

**Ground plane (back face).** A 50 mm x 50 mm square, flush with the substrate's
feed edge and with both side edges, extending 50 mm (hg) in from the feed edge.

**Radiating plate (front face).** A 20 mm (wp, across width) x 30 mm (hp, along
length) rectangle, its long axis parallel to the feedline. It is centered across
the substrate width [A013] and positioned at the far (non-feed) end of the
substrate so that its feed-side edge is offset from the ground plane's far edge
by hgap = 2 mm; the plate does not overlap the ground plane in projection.

**Microstrip feedline (front face).** A 2.5 mm-wide (wf) strip on the plate's
face, along the width centerline, running from the substrate feed edge to the
midpoint of the plate's 20 mm feed-side edge .

**Feed / excitation.** A standard coaxial SMA connector is mounted at the
"Feedpoint," where the feedline meets the substrate feed edge (width center),
providing the external feed; the 2.5 mm microstrip then feeds the plate. The
back-face ground plane is the reference return path for the feedline over the
region directly beneath it.

**Placement summary.** Feed edge → feedline (2.5 mm, front face) → plate (20 x
30 mm, front face, offset 2 mm beyond the ground's far edge); ground (50 x 50
mm, back face, flush to feed edge and side edges); SMA at the feed edge. All
lateral (width) features are centered. The S11 monitor should range from 0.1 to
10 GHz. Then simulate it for with the specificatins you see fit."""


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def _report_events(items: Iterable[RunItem]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    tools_by_call: dict[str | None, str | None] = {}
    for item in items:
        if isinstance(item, ToolCallItem):
            tools_by_call[item.call_id] = item.tool_name
            events.append(
                {
                    "type": "tool_call",
                    "call_id": item.call_id,
                    "tool": item.tool_name,
                    "arguments": _decode_json(item.to_input_item().get("arguments")),
                }
            )
        elif isinstance(item, ToolCallOutputItem):
            tool = tools_by_call.get(item.call_id)
            output = _decode_json(item.output)
            event: dict[str, Any] = {"type": "tool_result", "call_id": item.call_id, "tool": tool}
            if tool == "discover_tools" and isinstance(output, dict):
                if isinstance(output.get("tools"), list):
                    output = {
                        **output,
                        "tools": [
                            entry.get("name", entry) if isinstance(entry, dict) else entry
                            for entry in output["tools"]
                        ],
                    }
            elif tool == "dispatch_tool" and isinstance(output, dict) and "is_error" in output:
                event["is_error"] = output["is_error"]
                output = _decode_json(output.get("result", output.get("message", output)))
            event["result"] = output
            events.append(event)
        elif isinstance(item, MessageOutputItem):
            text = ItemHelpers.text_message_output(item)
            refusal = ItemHelpers.extract_refusal(item.raw_item)
            events.append({"type": "assistant_message", "text": text or refusal or ""})
        elif isinstance(item, ReasoningItem) and item.raw_item.summary:
            events.append(
                {"type": "reasoning", "summary": [part.text for part in item.raw_item.summary]}
            )
    return events


def _save_report(report: dict[str, Any], report_path: Path) -> None:
    report_path.mkdir(parents=True, exist_ok=True)
    (report_path / REPORT_NAME).write_text(
        json.dumps(report, indent=4, ensure_ascii=False) + "\n", encoding="utf-8"
    )


async def live_run(
    config: ConnectivityConfig,
    *,
    model: Any | None = None,
    mcp_client: CstMcpClient | None = None,
    report_path: Path = REPORTS_PATH,
) -> None:
    """Run the live CST probe and save a JSON report."""
    provider_client: AsyncOpenAI | None = None
    groups: ToolGroups | None = None
    try:
        if mcp_client is None:
            mcp_client = CstMcpClient(
                executable=config.mcp_executable,
                cwd=config.mcp_cwd,
                env=config.online_discovery_child_env(os.environ),
                startup_timeout_s=config.startup_timeout_s,
                shutdown_timeout_s=config.shutdown_timeout_s,
                request_timeout_s=config.mcp_request_timeout_s,
            )
        if model is None:
            model, provider_client = await _build_provider(config)

        async with mcp_client as mcp:
            definitions = await mcp.discover_tool_definitions()
            groups = ToolGroups(definitions)

            gateway = ToolGateway(
                mcp,
                allowlist=frozenset(tool.name for tool in definitions),
            )
            discovery_tool = build_discovery_tool(groups)
            dispatch_tool = build_dispatch_tool(gateway)
            agent = Agent(
                name="cst-tool-group-discovery-probe",
                model=model,
                instructions=SYSTEM_INSTRUCTIONS,
                tools=[discovery_tool, dispatch_tool],
            )
            report: dict[str, Any] = {
                "model": config.model,
                "system_prompt": SYSTEM_INSTRUCTIONS,
                "user_prompt": USER_PROMPT,
            }
            started = time.monotonic()
            try:
                result = await Runner.run(
                    agent,
                    USER_PROMPT,
                    max_turns=MAX_TURNS,
                    run_config=RunConfig(
                        tracing_disabled=True,
                        tool_not_found_behavior="return_error_to_model",
                    ),
                )
            except BaseException as exc:
                duration = time.monotonic() - started
                try:
                    run_data = getattr(exc, "run_data", None)
                    message = str(exc)
                    if config.api_key:
                        message = message.replace(config.api_key, "[redacted]")
                    report.update(
                        duration_s=duration,
                        run_status="failed",
                        events=_report_events(run_data.new_items if run_data is not None else ()),
                        final_output=None,
                        error=f"{type(exc).__name__}: {message}",
                    )
                    _save_report(report, report_path)
                except Exception:
                    exc.add_note("Could not save the live probe report.")
                raise

            duration = time.monotonic() - started
            print(result.final_output)
            print(f"Elapsed time: {duration:.2f} seconds")
            usage = result.context_wrapper.usage
            generated_tokens = (usage.output_tokens,)
            peak_request_tokens = (
                max(
                    (request.total_tokens for request in usage.request_usage_entries),
                    default=None,
                ),
            )
            report.update(
                duration_s=duration,
                run_status="completed",
                events=_report_events(result.new_items),
                final_output=result.final_output,
                output_tokens=generated_tokens,
                peak_request_tokens=peak_request_tokens,
            )
            _save_report(report, report_path)
    finally:
        if provider_client is not None:
            try:
                await provider_client.close()
            except Exception:  # noqa: BLE001 - preserve the primary failure, if any
                print("Model client cleanup failed.")
    return


def main() -> int:
    config = load_connectivity_config(env_path=ENV_PATH_DEFAULT)
    try:
        asyncio.run(live_run(config=config))
    except KeyboardInterrupt:
        print("\nChat interrupted.")
        return 130
    return 0


if __name__ == "__main__":
    SystemExit(main())
