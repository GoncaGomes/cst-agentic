"""Local substitutes for offline connectivity tests.

Everything here is a stand-in: no credentials, no institutional endpoint, no
CST, and no real MCP subprocess. :class:`FakeMcpClient` subclasses the real
client so the tests exercise the same bounded request code paths (paginated
discovery, tool calls, timeout handling) against an injected fake session —
including the model tool-call / response cycle rather than only a direct MCP
call.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agents.testing import ScriptedModel, assistant_message, function_call
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from cst_agentic.config import ConnectivityConfig
from cst_agentic.mcp_client import CstMcpClient

TEST_API_KEY = "test-secret-key-123"
TEST_BASE_URL = "https://example.invalid/openai"


def make_config(tmp_path: Path, **overrides: Any) -> ConnectivityConfig:
    """Build a valid config pointing at nonexistent paths (no subprocess runs)."""
    base: dict[str, Any] = {
        "base_url": TEST_BASE_URL,
        "api_key": TEST_API_KEY,
        "model": "qwen3.8-27b",
        "mcp_executable": tmp_path / "fake-server.exe",
        "mcp_cwd": tmp_path / "server-cwd",
        "work_dir": tmp_path / "work",
        "max_turns": 4,
        "request_timeout_s": 10.0,
        "startup_timeout_s": 10.0,
        "shutdown_timeout_s": 10.0,
        "mcp_request_timeout_s": 10.0,
    }
    base.update(overrides)
    return ConnectivityConfig(**base)


def offline_status_payload() -> dict[str, Any]:
    return {
        "mode": "offline",
        "cst_available": False,
        "cst_version": "2025",
        "work_dir": "C:\\work",
        "project_open": False,
        "project_path": None,
        "solver_running": False,
        "solver_status": "unavailable",
        "last_error": None,
    }


class _FakeSession:
    """A fake MCP session serving canned tools and payloads.

    A ``hang`` of ``"discover"`` or ``"call"`` makes the corresponding requests
    block until the client's bound cancels them, simulating a server that
    initializes and then stalls.
    """

    def __init__(self, owner: FakeMcpClient) -> None:
        self._owner = owner

    async def list_tools(self, params: dict[str, Any] | None = None) -> ListToolsResult:
        owner = self._owner
        if owner._hang == "discover":
            await asyncio.sleep(3600)  # blocked until the client's bound cancels it
        if owner._discover_error is not None:
            raise owner._discover_error
        return ListToolsResult(
            tools=[
                Tool(name=name, description=f"fake {name}", input_schema={"type": "object"})
                for name in owner._tools
            ],
            next_cursor=None,
        )

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        owner = self._owner
        if owner._hang == "call":
            await asyncio.sleep(3600)  # blocked until the client's bound cancels it
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(owner._status_payload))],
            is_error=owner._is_error,
        )


class FakeMcpClient(CstMcpClient):
    """A stand-in for :class:`CstMcpClient` used by the orchestration tests.

    It reuses the real client's bounded ``discover_tools`` and ``call_tool``
    against an injected fake session (no subprocess, no endpoint, no CST), so
    tests exercise the same request code paths as production, including
    timeout handling. ``hang`` simulates a server that initializes and then
    stalls on the given kind of request; the short default request bound keeps
    the tests fast.
    """

    def __init__(
        self,
        *,
        server_name: str = "cst-studio-mcp",
        server_version: str = "0.1.0",
        tools: list[str] | None = None,
        status_payload: dict[str, Any] | None = None,
        is_error: bool = False,
        enter_error: Exception | None = None,
        discover_error: Exception | None = None,
        hang: str | None = None,
        request_timeout_s: float = 0.05,
    ) -> None:
        super().__init__(
            executable=Path("fake-server.exe"),
            cwd=Path("server-cwd"),
            env={},
            startup_timeout_s=0.05,
            shutdown_timeout_s=0.05,
            request_timeout_s=request_timeout_s,
        )
        self.server_name = server_name
        self.server_version = server_version
        self.instructions = "test server instructions"
        self._tools = (
            tools
            if tools is not None
            else [
                "cst_connection_status",
                "cst_connect",
                "cst_disconnect",
                "cst_list_project_items",
            ]
        )
        self._status_payload = (
            status_payload if status_payload is not None else offline_status_payload()
        )
        self._is_error = is_error
        self._enter_error = enter_error
        self._discover_error = discover_error
        self._hang = hang
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> FakeMcpClient:
        self.entered = True
        if self._enter_error is not None:
            raise self._enter_error
        self._session = _FakeSession(self)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.exited = True
        return False


def scripted_model(steps: list[list[Any]]) -> ScriptedModel:
    return ScriptedModel(steps)


def success_steps() -> list[list[Any]]:
    """A model that calls the status tool once, then summarizes the result."""
    return [
        [function_call("cst_connection_status", {}, call_id="call_1")],
        [assistant_message("CST is offline and no project is open.")],
    ]
