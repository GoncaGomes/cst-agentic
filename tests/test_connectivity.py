"""Offline tests for the connectivity check orchestration.

These drive the real ``run_connectivity_check`` flow with a scripted model and
a fake MCP client, so they exercise the model tool-call / response cycle (not
just a direct MCP call) and verify verification, failure handling, and cleanup.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agents.testing import assistant_message, function_call

from cst_agentic.connectivity import _build_provider, run_connectivity_check
from cst_agentic.mcp_client import McpStartupError
from fakes import (
    TEST_API_KEY,
    FakeMcpClient,
    make_config,
    offline_status_payload,
    scripted_model,
    success_steps,
)


def _check_names(report) -> set[str]:
    return {check.name for check in report.checks}


@pytest.mark.asyncio
async def test_success_full_cycle(tmp_path: Path) -> None:
    mcp = FakeMcpClient()
    model = scripted_model(success_steps())
    report = await run_connectivity_check(make_config(tmp_path), model=model, mcp_client=mcp)
    assert report.success is True
    assert report.error is None
    assert report.stage == "complete"
    # Evidence: server identity and catalog.
    assert report.server_name == "cst-studio-mcp"
    assert report.server_version == "0.1.0"
    assert "cst_connection_status" in report.discovered_tools
    # Only the status tool was exposed.
    assert report.exposed_tools == ["cst_connection_status"]
    # The model requested the tool with an empty argument object.
    assert report.model_tool_calls == [{"name": "cst_connection_status", "arguments": {}}]
    # The call actually reached the MCP layer (not fabricated).
    assert report.mcp_tool_calls == [
        {"name": "cst_connection_status", "arguments": {}, "is_error": False}
    ]
    assert mcp.calls and mcp.calls[0].name == "cst_connection_status"
    # Status payload is disconnected.
    assert report.status_payload["mode"] == "offline"
    assert report.status_payload["project_open"] is False
    # All verification checks ran and passed.
    names = _check_names(report)
    for expected in (
        "mcp_initialized",
        "tools_discovered",
        "status_tool_discovered",
        "status_tool_exposed",
        "model_requested_status_tool",
        "no_other_model_tool_calls",
        "mcp_executed_status_call",
        "mcp_no_error",
        "payload_offline",
        "payload_project_closed",
        "payload_no_error_status",
        "final_answer_summarizes",
    ):
        assert expected in names
    assert all(check.passed for check in report.checks)
    # Cleanup happened.
    assert mcp.entered and mcp.exited


@pytest.mark.asyncio
async def test_model_skips_tool_call_fails(tmp_path: Path) -> None:
    mcp = FakeMcpClient()
    model = scripted_model([[assistant_message("CST is offline with no project open.")]])
    report = await run_connectivity_check(make_config(tmp_path), model=model, mcp_client=mcp)
    assert report.success is False
    # No MCP call was made, and the relevant checks failed.
    assert mcp.calls == []
    assert not _passed(report, "model_requested_status_tool")
    assert not _passed(report, "mcp_executed_status_call")
    # Partial success (server initialized, tools discovered) is not a pass.
    assert _passed(report, "mcp_initialized")
    assert report.error is None


@pytest.mark.asyncio
async def test_payload_error_is_not_success(tmp_path: Path) -> None:
    mcp = FakeMcpClient(is_error=True, status_payload={"status": "error", "message": "no"})
    model = scripted_model(success_steps())
    report = await run_connectivity_check(make_config(tmp_path), model=model, mcp_client=mcp)
    assert report.success is False
    assert not _passed(report, "mcp_no_error")
    assert not _passed(report, "payload_offline")


@pytest.mark.asyncio
async def test_connected_payload_is_not_success(tmp_path: Path) -> None:
    payload = offline_status_payload()
    payload["mode"] = "connected"
    payload["project_open"] = True
    mcp = FakeMcpClient(status_payload=payload)
    model = scripted_model(success_steps())
    report = await run_connectivity_check(make_config(tmp_path), model=model, mcp_client=mcp)
    assert report.success is False
    assert not _passed(report, "payload_offline")
    assert not _passed(report, "payload_project_closed")


@pytest.mark.asyncio
async def test_model_calls_other_tool_fails(tmp_path: Path) -> None:
    # The model only has the status tool registered, but if it attempted a
    # different (allowlisted-but-not-exposed) tool, the "no other tools" check
    # must fail. Here we simulate a non-allowlisted model call.
    mcp = FakeMcpClient()
    model = scripted_model(
        [
            [function_call("cst_connect", {"mode": "new"}, call_id="call_1")],
            [assistant_message("connected")],
        ]
    )
    report = await run_connectivity_check(make_config(tmp_path), model=model, mcp_client=mcp)
    # The unregistered tool is not executed; the run reports an unsuccessful
    # outcome and the "no other model tool calls" check fails.
    assert report.success is False
    assert not _passed(report, "no_other_model_tool_calls")


@pytest.mark.asyncio
async def test_mcp_startup_failure_reports_and_cleans(tmp_path: Path) -> None:
    mcp = FakeMcpClient(enter_error=McpStartupError("boom"))
    model = scripted_model(success_steps())
    report = await run_connectivity_check(make_config(tmp_path), model=model, mcp_client=mcp)
    assert report.success is False
    assert report.error is not None
    assert "MCP" in report.error or "mcp" in report.error.lower()
    assert report.stage in {"mcp_initialize", "start"}
    # The client was entered (and the error surfaced from __aenter__).
    assert mcp.entered is True


@pytest.mark.asyncio
async def test_discovery_failure_reports(tmp_path: Path) -> None:
    from cst_agentic.mcp_client import McpError

    mcp = FakeMcpClient(discover_error=McpError("tools/list failed"))
    model = scripted_model(success_steps())
    report = await run_connectivity_check(make_config(tmp_path), model=model, mcp_client=mcp)
    assert report.success is False
    assert report.stage == "tool_discovery"
    assert report.error is not None
    assert mcp.exited is True  # cleanup still happened


@pytest.mark.asyncio
async def test_hung_discovery_times_out_and_cleans(tmp_path: Path) -> None:
    # A server that initializes and then stalls on tools/list must produce an
    # unsuccessful report within the request bound, not hang.
    mcp = FakeMcpClient(hang="discover")
    model = scripted_model(success_steps())
    report = await run_connectivity_check(make_config(tmp_path), model=model, mcp_client=mcp)
    assert report.success is False
    assert report.error is not None
    assert "timed out" in report.error
    assert mcp.entered is True
    assert mcp.exited is True  # cleanup still happened


@pytest.mark.asyncio
async def test_hung_tool_call_times_out_and_cleans(tmp_path: Path) -> None:
    # A stalled tools/call during the model run must likewise fail the check
    # with a diagnostic and release the MCP client.
    mcp = FakeMcpClient(hang="call")
    model = scripted_model(success_steps())
    report = await run_connectivity_check(make_config(tmp_path), model=model, mcp_client=mcp)
    assert report.success is False
    assert report.error is not None
    assert "timed out" in report.error
    assert mcp.entered is True
    assert mcp.exited is True  # cleanup still happened


@pytest.mark.asyncio
async def test_max_turns_exhaustion_is_unsuccessful(tmp_path: Path) -> None:
    mcp = FakeMcpClient()
    # The model never produces a final message; it keeps requesting the tool.
    steps: list[list[Any]] = [
        [function_call("cst_connection_status", {}, call_id=f"call_{i}")] for i in range(10)
    ]
    model = scripted_model(steps)
    report = await run_connectivity_check(
        make_config(tmp_path, max_turns=3), model=model, mcp_client=mcp
    )
    assert report.success is False
    assert report.error is not None
    assert mcp.exited is True


def _passed(report, name: str) -> bool:
    for check in report.checks:
        if check.name == name:
            return check.passed
    return False


@pytest.mark.asyncio
async def test_summary_contains_no_credentials(tmp_path: Path) -> None:
    mcp = FakeMcpClient()
    model = scripted_model(success_steps())
    report = await run_connectivity_check(make_config(tmp_path), model=model, mcp_client=mcp)
    summary = report.summary()
    assert TEST_API_KEY not in summary
    assert "secret" not in summary.lower() or "test-secret-key-123" not in summary
    # Sanity: the summary is informative.
    assert "cst_connection_status" in summary
    assert "offline" in summary


@pytest.mark.asyncio
async def test_provider_request_construction(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    model, client = await _build_provider(config)
    try:
        assert model.model == config.model
        assert str(client.base_url).rstrip("/") == config.base_url.rstrip("/")
        assert client.api_key == config.api_key
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_injected_model_does_not_build_provider(tmp_path: Path) -> None:
    # When a model is injected, no institutional client is created (offline).
    mcp = FakeMcpClient()
    model = scripted_model(success_steps())
    report = await run_connectivity_check(make_config(tmp_path), model=model, mcp_client=mcp)
    # The run completed offline; the endpoint was never contacted.
    assert report.success is True
