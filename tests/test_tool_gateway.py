"""Offline tests for the tool allowlist gate."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cst_agentic.mcp_client import McpToolCall
from cst_agentic.tool_gateway import (
    ALLOWED_TOOLS,
    ToolGateway,
    ToolNotAllowedError,
    build_status_tool,
)


class RecordingMcp:
    def __init__(self) -> None:
        self.calls: list[McpToolCall] = []

    async def call_tool(self, name: str, arguments: dict[str, Any] | None) -> McpToolCall:
        record = McpToolCall(
            name=name,
            arguments=dict(arguments or {}),
            is_error=False,
            text=json.dumps({"mode": "offline", "project_open": False}),
            payload={"mode": "offline", "project_open": False},
        )
        self.calls.append(record)
        return record


@pytest.mark.asyncio
async def test_dispatch_allowed_reaches_mcp() -> None:
    mcp = RecordingMcp()
    gateway = ToolGateway(mcp)  # type: ignore[arg-type]
    record = await gateway.dispatch("cst_connection_status", {})
    assert record.name == "cst_connection_status"
    assert mcp.calls and mcp.calls[0].name == "cst_connection_status"


@pytest.mark.asyncio
async def test_dispatch_rejects_before_mcp() -> None:
    mcp = RecordingMcp()
    gateway = ToolGateway(mcp)  # type: ignore[arg-type]
    with pytest.raises(ToolNotAllowedError):
        await gateway.dispatch("cst_connect", {"mode": "new"})
    # Nothing was dispatched to the MCP transport.
    assert mcp.calls == []


def test_allowlist_is_only_status_tool() -> None:
    assert ALLOWED_TOOLS == frozenset({"cst_connection_status"})


def test_status_tool_metadata() -> None:
    mcp = RecordingMcp()
    gateway = ToolGateway(mcp)  # type: ignore[arg-type]
    tool = build_status_tool(gateway)
    assert tool.name == "cst_connection_status"
    # The exposed tool takes an empty argument object.
    schema = tool.params_json_schema
    assert schema.get("type") == "object"
    assert not schema.get("required")
