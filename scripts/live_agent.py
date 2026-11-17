from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents import Agent, RunConfig, Runner, SQLiteSession
from openai import AsyncOpenAI
from pydantic import TypeAdapter

from cst_agentic.config import ConnectivityConfig, load_connectivity_config
from cst_agentic.connectivity import (
    ConnectivityReport,
    _build_provider,
    _model_tool_calls,
    save_json_report,
)
from cst_agentic.mcp_client import CstMcpClient
from cst_agentic.tool_gateway import build_discovery_tool
from cst_agentic.tool_groups import ToolGroups

MAX_TURNS = 24
REPORT_NAME = "live_chat.json"
REPORTS_PATH = Path("tests/reports")
ENV_PATH_DEFAULT = Path("./.env")

SYSTEM_INSTRUCTIONS = """You are a CST Studio Suite assistant and antenna
designer. Given a user's
request, propose the MCP tools you would use to carry it out and explain why
each tool is needed.

Use `discover_tools` to inspect the capability groups relevant to the request.
Reuse tool definitions already returned in the conversation when they cover the
current request. `discover_tools` is the only tool you may call. Describe CST
operations as proposed steps. Everything needs to be parameterized.

Present the plan as a numbered list in execution order. For each step, give the
exact MCP tool name from the catalogue and explain how it helps complete the
user's request. Include known argument values using the parameter names from the
tool definition. Flag any required values that are still missing.

Use the conversation history to resolve references in follow-up requests. If a
missing detail changes which tool you would recommend, ask a focused question.
If the catalogue does not support part of the request, identify that part and
explain what the available tools can cover.

Keep the explanation concise, Do not use emojis."""


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
            report = LiveChatReport(
                success=True,
                stage="chat",
                error=None,
                server_name=mcp.server_name,
                server_version=mcp.server_version,
                discovered_tools=[tool.name for tool in definitions],
                exposed_tools=[discovery_tool.name],
            )
            json_adapter = TypeAdapter(Any)
            while True:
                message = input("User:").strip()
                if message.casefold() == "/exit":
                    break
                result = await Runner.run(
                    agent,
                    message,
                    max_turns=MAX_TURNS,
                    session=session,
                    run_config=RunConfig(
                        tracing_disabled=True,
                        tool_not_found_behavior="return_error_to_model",
                    ),
                )
                model_tool_calls = _model_tool_calls(result)
                report.turns.append(
                    json_adapter.dump_python(
                        {
                            "user_message": message,
                            "model_tool_calls": model_tool_calls,
                            "response": result.final_output,
                            "items": [item.to_input_item() for item in result.new_items],
                            "raw_responses": result.raw_responses,
                        },
                        mode="json",
                    )
                )
                report.model_tool_calls.extend(model_tool_calls)
                report.final_answer = result.final_output
                save_json_report(report, report_path, REPORT_NAME)
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
