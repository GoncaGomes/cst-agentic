"""Offline tests for the MCP client: paginated discovery and call recording."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from cst_agentic.mcp_client import CstMcpClient, McpCallError, McpError


def _tool(name: str) -> Tool:
    return Tool(name=name, description=f"desc {name}", input_schema={"type": "object"})


class FakeListSession:
    """Serves a fixed chain of tools/list pages keyed by cursor."""

    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._pages = pages
        self._by_cursor: dict[str | None, int] = {None: 0}
        for index, page in enumerate(pages):
            cursor = page.get("next_cursor")
            if cursor is not None:
                self._by_cursor[cursor] = index + 1
        self.requested_cursors: list[str | None] = []

    async def list_tools(self, params: dict[str, Any] | None = None) -> ListToolsResult:
        cursor = (params or {}).get("cursor")
        self.requested_cursors.append(cursor)
        page = self._pages[self._by_cursor[cursor]]
        return ListToolsResult(tools=page["tools"], next_cursor=page.get("next_cursor"))


def _client(tmp_path: Path, request_timeout_s: float = 1.0) -> CstMcpClient:
    return CstMcpClient(
        executable=tmp_path / "s.exe",
        cwd=tmp_path / "cwd",
        env={},
        startup_timeout_s=1.0,
        shutdown_timeout_s=1.0,
        request_timeout_s=request_timeout_s,
    )


@pytest.mark.asyncio
async def test_discovery_follows_pagination(tmp_path: Path) -> None:
    session = FakeListSession(
        [
            {"tools": [_tool("a"), _tool("b")], "next_cursor": "c1"},
            {"tools": [_tool("c")], "next_cursor": None},
        ]
    )
    client = _client(tmp_path)
    client._session = session
    names = await client.discover_tools()
    assert names == ["a", "b", "c"]
    assert session.requested_cursors == [None, "c1"]


@pytest.mark.asyncio
async def test_discovery_single_page(tmp_path: Path) -> None:
    session = FakeListSession([{"tools": [_tool("only")], "next_cursor": None}])
    client = _client(tmp_path)
    client._session = session
    assert await client.discover_tools() == ["only"]
    assert session.requested_cursors == [None]


class FakeCallSession:
    def __init__(self, result: CallToolResult | Exception) -> None:
        self._result = result
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        self.calls.append((name, dict(arguments or {})))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class HangSession:
    """A session whose requests block until cancelled (simulates a hung server)."""

    async def list_tools(self, params: dict[str, Any] | None = None) -> None:
        await asyncio.sleep(3600)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> None:
        await asyncio.sleep(3600)


@pytest.mark.asyncio
async def test_discovery_page_timeout_is_bounded_error(tmp_path: Path) -> None:
    client = _client(tmp_path, request_timeout_s=0.05)
    client._session = HangSession()
    with pytest.raises(McpError, match="timed out"):
        await client.discover_tools()


@pytest.mark.asyncio
async def test_call_tool_timeout_is_bounded_error(tmp_path: Path) -> None:
    client = _client(tmp_path, request_timeout_s=0.05)
    client._session = HangSession()
    with pytest.raises(McpCallError, match="timed out"):
        await client.call_tool("cst_connection_status", {})
    # A timed-out call is not recorded as a call.
    assert client.calls == []


def _text_result(payload: dict[str, Any], is_error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))], is_error=is_error
    )


@pytest.mark.asyncio
async def test_call_tool_records_success(tmp_path: Path) -> None:
    session = FakeCallSession(_text_result({"mode": "offline", "project_open": False}))
    client = _client(tmp_path)
    client._session = session
    record = await client.call_tool("cst_connection_status", {})
    assert record.name == "cst_connection_status"
    assert record.arguments == {}
    assert record.is_error is False
    assert record.payload == {"mode": "offline", "project_open": False}
    assert client.calls == [record]
    assert session.calls == [("cst_connection_status", {})]


@pytest.mark.asyncio
async def test_call_tool_records_payload_error_without_raising(tmp_path: Path) -> None:
    session = FakeCallSession(_text_result({"status": "error", "message": "no"}, is_error=True))
    client = _client(tmp_path)
    client._session = session
    record = await client.call_tool("cst_connection_status", {})
    assert record.is_error is True
    assert record.payload == {"status": "error", "message": "no"}
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_call_tool_transport_failure_raises(tmp_path: Path) -> None:
    session = FakeCallSession(RuntimeError("boom"))
    client = _client(tmp_path)
    client._session = session
    with pytest.raises(McpCallError):
        await client.call_tool("cst_connection_status", {})
    # A transport failure is not recorded as a successful call.
    assert client.calls == []
