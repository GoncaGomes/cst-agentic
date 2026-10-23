"""Exercise the actual public client/SDK wrapper against a local fake process."""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

from cst_agentic import mcp_client
from cst_agentic.mcp_client import CstMcpClient, McpCallError


@pytest.fixture
def transport_client(tmp_path: Path) -> CstMcpClient:
    if sys.platform != "win32":
        pytest.skip("Windows executable launcher fixture")
    uv = shutil.which("uv")
    assert uv is not None
    root = Path(__file__).resolve().parents[1]
    peer = root / "tests" / "fixtures" / "fake_mcp_server.py"
    launcher = tmp_path / "fake-peer.cmd"
    launcher.write_text(f'@echo off\n"{uv}" run --no-sync python -u "{peer}"\n', encoding="utf-8")
    return CstMcpClient(
        executable=launcher,
        cwd=root,
        env={},
        startup_timeout_s=10,
        shutdown_timeout_s=10,
        request_timeout_s=5,
    )


@pytest.mark.asyncio
async def test_actual_wrapper_preserves_catalogue_and_complete_response(
    transport_client: CstMcpClient,
) -> None:
    async with transport_client as client:
        assert client.server_name == "offline-wrapper-peer"
        definitions = await client.discover_tool_definitions()
        assert [tool.name for tool in definitions] == ["inspect", "other"]
        assert definitions[0].input_schema["properties"]["note"] == {
            "type": ["string", "null"],
            "default": None,
        }
        assert await client.discover_tools() == ["inspect", "other"]
        record = await client.call_tool("inspect", {}, timeout_s=2, dispatch_guard=lambda: True)
        assert record.payload == {"status": "received"}
        assert record.structured_content == {"rebuilt": False}
        assert [block.type for block in record.content] == ["text", "text", "image"]
        assert record.evidence_complete is True
        assert client.attempts[0].state == "received"


@pytest.mark.asyncio
async def test_actual_wrapper_cleans_up_sdk_tasks_in_its_lifecycle_owner(
    transport_client: CstMcpClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exit_failures: list[str] = []

    class ObservedSdkContext:
        def __init__(self, context: Any) -> None:
            self.context = context

        async def __aenter__(self) -> Any:
            return await self.context.__aenter__()

        async def __aexit__(self, *args: Any) -> Any:
            try:
                return await self.context.__aexit__(*args)
            except BaseException as error:
                exit_failures.append(type(error).__name__)
                raise

    # Observe real external SDK exits, without replacing their behavior.
    session_factory = mcp_client.ClientSession
    transport_factory = mcp_client.stdio_client
    monkeypatch.setattr(
        mcp_client,
        "ClientSession",
        lambda *args, **kwargs: ObservedSdkContext(session_factory(*args, **kwargs)),
    )
    monkeypatch.setattr(
        mcp_client,
        "stdio_client",
        lambda *args, **kwargs: ObservedSdkContext(transport_factory(*args, **kwargs)),
    )
    before = asyncio.all_tasks()
    async with transport_client as client:
        await client.discover_tools()
    remaining = asyncio.all_tasks() - before
    assert not remaining, "client cleanup left SDK tasks running"
    assert exit_failures == [], "client suppressed actual SDK context-exit failures"


@pytest.mark.asyncio
async def test_actual_sdk_validation_failure_blocks_later_status_and_stop(
    transport_client: CstMcpClient,
) -> None:
    async with transport_client as client:
        await client.discover_tool_definitions()
        with pytest.raises(McpCallError):
            await client.call_tool("inspect", {"invalid": True})
        assert client.attempts[0].state == "uncertain"
        assert client.calls == []
        for name in ("cst_connection_status", "cst_stop_simulation"):
            with pytest.raises(McpCallError, match="uncertain"):
                await client.call_tool(name, {}, timeout_s=2, dispatch_guard=lambda: True)
        assert all(attempt.dispatched is False for attempt in client.attempts[1:])


@pytest.mark.asyncio
async def test_actual_wrapper_keeps_received_domain_failure_distinct_from_uncertainty(
    transport_client: CstMcpClient,
) -> None:
    async with transport_client as client:
        await client.discover_tool_definitions()
        failed = await client.call_tool("inspect", {"error": True})
        assert failed.is_error is True
        assert failed.structured_content == {"rebuilt": False}
        assert len(failed.content) == 3
        assert client.attempts[0].state == "received"
        assert (await client.call_tool("inspect", {})).is_error is False
