from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agents import Agent, RunConfig, Runner
from openai import AsyncOpenAI

from cst_agentic.config import ConnectivityConfig, load_connectivity_config
from cst_agentic.connectivity import (
    _build_provider,
    _model_tool_calls,
)
from cst_agentic.mcp_client import CstMcpClient
from cst_agentic.tool_gateway import build_discovery_tool
from cst_agentic.tool_groups import ToolGroups

MAX_TURNS = 24
REPORT_NAME = "model_eval.json"
REPORTS_PATH = Path("tests/reports")
ENV_PATH_DEFAULT = Path("./.env")

SYSTEM_INSTRUCTIONS = """You are a CST Studio Suite assistant and antenna
designer. Identify the MCP tools you would use for the user's request and
briefly explain why each is needed.

Use `discover_tools` to inspect the capability groups relevant to the request.
Reuse tool definitions already returned in the conversation when they cover the
current request. `discover_tools` is the only tool you may call; do not execute
the proposed MCP tools.

Return only one line per proposed tool, in execution order, using this format:
<exact MCP tool name from the catalogue> — <concise reasoning>

Do not include an introduction, conclusion, headings, numbering, argument values,
code examples, or emojis. Do not list `discover_tools` as a proposed MCP tool.

If no tool can be recommended because the request is ambiguous, unsupported, or
conflicts with the user's constraints, return only:
None — <concise reasoning identifying the missing detail or limitation>"""

CASES = [
    {
        "id": "set_parameter",
        "user_message": (
            "In an open project that uses millimeters and has no simulation "
            "results, set the width parameter patch_w to 30 mm."
        ),
        "expected_discovery_groups": [["parameters"]],
        "expected_recommended_tools": ["cst_set_parameter"],
        "expected_behavior": 'Propose name="patch_w" and value=30.',
    },
    {
        "id": "create_parametric_brick",
        "user_message": (
            "In an open project that uses millimeters and has no simulation "
            "results, set patch_w to 30. In the Antenna component, create a PEC "
            "brick named Patch that spans x=0 to patch_w, y=0 to 20, and z=0 "
            "to 0.035. The width should update whenever patch_w changes."
        ),
        "expected_discovery_groups": [["parameters", "geometry_basic"]],
        "expected_recommended_tools": [
            "cst_set_parameter",
            "cst_create_brick",
        ],
        "expected_behavior": (
            'Set patch_w before creating the brick. Keep x_max="patch_w" '
            "and use the requested component, material, and remaining bounds."
        ),
    },
    {
        "id": "add_discrete_port",
        "user_message": (
            "Add discrete port 1 with an impedance of 75 ohms to the existing "
            "dipole. Place it between z=-0.5 mm and z=+0.5 mm. "
            "Both endpoints have x=y=0."
        ),
        "expected_discovery_groups": [["ports_basic"]],
        "expected_recommended_tools": ["cst_add_discrete_port"],
        "expected_behavior": (
            "Use port_number=1, impedance=75, x1=0, y1=0, z1=-0.5, x2=0, y2=0, and z2=0.5."
        ),
    },
    {
        "id": "prepare_and_run_simulation",
        "user_message": (
            "The geometry and port are already set up. Set the simulation "
            "band to 2300-2500 MHz, add a far-field monitor at 2450 MHz, "
            "and run the time-domain simulation."
        ),
        "expected_discovery_groups": [
            [
                "simulation_domain",
                "field_monitors",
                "solver_time_domain",
                "simulation_run",
            ],
        ],
        "expected_recommended_tools": [
            "cst_set_frequency_range",
            "cst_add_field_monitor",
            "cst_configure_time_domain_solver",
            "cst_run_simulation_async",
        ],
        "expected_behavior": (
            'Use f_min=2.3, f_max=2.5, monitor_type="Farfield", and frequency=2.45. '
            "Place the simulation launch after the setup steps."
        ),
    },
    {
        "id": "inspect_project",
        "user_message": ("Which project is open, and what objects are in the project tree?"),
        "expected_discovery_groups": [["session_project"], ["project_context"]],
        "expected_recommended_tools": ["cst_project_info", "cst_project_tree"],
        "expected_behavior": (
            "Propose retrieving the project information and inspecting the "
            "project tree. Present both as steps to perform."
        ),
    },
    {
        "id": "clarify_antenna_port",
        "user_message": "Add a port to the antenna.",
        "expected_discovery_groups": [],
        "expected_recommended_tools": [],
        "expected_behavior": (
            "Ask a focused question about the feed type or port location. "
            "Leave the coordinates unspecified."
        ),
    },
    {
        "id": "recognize_unsupported_s11_export",
        "user_message": ("The simulation has finished. Export the S11 curve to a CSV file."),
        "expected_discovery_groups": [],
        "expected_recommended_tools": [],
        "expected_behavior": (
            "Explain that direct S11 export to CSV is unavailable in the current tool catalog."
        ),
    },
    {
        "id": "preserve_simulation_results",
        "user_message": (
            "This project already has simulation results that I need to keep. "
            "Can I change patch_w to 32 mm in this same project?"
        ),
        "expected_discovery_groups": [["parameters"]],
        "expected_recommended_tools": [],
        "expected_behavior": (
            "Explain that changing the parameter with cst_set_parameter "
            "requires deleting the existing results. Conclude that the change "
            "must wait while those results need to be preserved."
        ),
    },
]


@dataclass
class ModelEval:
    case: list[Case]


@dataclass
class Case:
    case: dict[str, Any]
    final_model_response: str
    case_completion_time: float
    expected_tools_present: bool
    model_tool_calls: list[dict[str, Any]] = field(default_factory=list)


async def model_eval(
    config: ConnectivityConfig,
    *,
    model: Any | None = None,
    mcp_client: CstMcpClient | None = None,
    report_path: Path = REPORTS_PATH,
) -> None:
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
            model, provider_client = await _build_provider(config)

        async with mcp_client as mcp:
            definitions = await mcp.discover_tool_definitions()
            groups = ToolGroups(definitions)
            discovery_tool = build_discovery_tool(groups)
            agent = Agent(
                name="cst-tool-group-discovery-probe",
                model=model,
                instructions=SYSTEM_INSTRUCTIONS,
                tools=[discovery_tool],
            )
            list_cases = []
            for case in CASES:
                message = case["user_message"]
                started = time.monotonic()
                result = await Runner.run(
                    agent,
                    message,
                    max_turns=MAX_TURNS,
                    run_config=RunConfig(
                        tracing_disabled=True,
                        tool_not_found_behavior="return_error_to_model",
                    ),
                )
                finished = time.monotonic()
                model_case = Case(
                    case=case,
                    model_tool_calls=_model_tool_calls(result),
                    final_model_response=result.final_output,
                    case_completion_time=finished - started,
                    expected_tools_present=all(
                        re.search(rf"\b{re.escape(tool)}\b", result.final_output) is not None
                        for tool in case["expected_recommended_tools"]
                    ),
                )
                list_cases.append(model_case)
            report = ModelEval(case=list_cases)
            report_path.mkdir(parents=True, exist_ok=True)
            with (report_path / REPORT_NAME).open("w", encoding="utf-8") as report_file:
                json.dump(asdict(report), report_file, indent=4)
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
        asyncio.run(model_eval(config=config))
    except KeyboardInterrupt:
        print("\nChat interrupted.")
        return 130
    return 0


if __name__ == "__main__":
    SystemExit(main())
