from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents import Agent, RunConfig, Runner, SQLiteSession
from openai import AsyncOpenAI

from cst_agentic.config import ConnectivityConfig, load_connectivity_config
from cst_agentic.connectivity import (
    ConnectivityReport,
    _build_provider,
)
from cst_agentic.mcp_client import CstMcpClient
from cst_agentic.tool_gateway import ToolGateway, build_discovery_tool, build_dispatch_tool
from cst_agentic.tool_groups import ToolGroups

MAX_TURNS = 24
REPORT_NAME = "live_chat.json"
REPORTS_PATH = Path("tests/reports")
ENV_PATH_DEFAULT = Path("./.env")

SYSTEM_INSTRUCTIONS = """You are a CST Studio Suite assistant. Execute the
user's request using the available MCP tools.

Use discover_tools to find the relevant tools and their input schemas. Reuse
schemas already returned in the current session. Call dispatch_tool with the
exact MCP tool name and an arguments object that matches its schema. Use an
empty object for tools that take no arguments.

Before changing a project, verify the active project through MCP. When the user
requests parametric geometry, define the parameters first and pass their names
or expressions as geometry inputs. When the user requests a material from the
installed CST library, use cst_load_material and refer to the imported material
by its name in the project.

Base your answer on the tool results. For live operations, confirm that CST
executed the operation. If a call fails, stop the steps that depend on it and
report the error. Summarize what you executed and what you verified."""

USER_PROMPT = """Connect to CST. Open the existing project at
C:/dev/cst-probes/LiveProbe/LiveProbe.cst using cst_open_project.
Then use cst_project_info to confirm that this is the open project."""


@dataclass
class LiveChatReport(ConnectivityReport):
    """Chat evidence compatible with the shared JSON report writer."""

    turns: list[dict[str, Any]] = field(default_factory=list)


async def live_chat(
    config: ConnectivityConfig,
    *,
    model: Any | None = None,
    mcp_client: CstMcpClient | None = None,
    report_path: Path = REPORTS_PATH,
) -> None:
    """Run an interactive discovery chat and save every completed turn as JSON."""
    db_path = Path("tests/data") / "chat_history.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    session = SQLiteSession("live-chat", db_path=db_path)
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

            result = await Runner.run(
                agent,
                USER_PROMPT,
                max_turns=MAX_TURNS,
                session=session,
                run_config=RunConfig(
                    tracing_disabled=True,
                    tool_not_found_behavior="return_error_to_model",
                ),
            )
            print(result.final_output)
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
        asyncio.run(live_chat(config=config))
    except KeyboardInterrupt:
        print("\nChat interrupted.")
        return 130
    return 0


if __name__ == "__main__":
    SystemExit(main())
