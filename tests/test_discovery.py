"""Offline model/tool cycles for discovery across every catalogue group."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from agents.testing import assistant_message, function_call

from cst_agentic import discovery
from cst_agentic.discovery import MAX_TURNS, REPORT_NAME, run_discovery_check
from cst_agentic.mcp_client import McpError, McpStartupError
from cst_agentic.tool_groups import GROUPS
from fakes import FakeMcpClient, make_config, scripted_model


@pytest.fixture(autouse=True)
def reports_in_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discovery, "REPORTS_PATH", tmp_path / "reports")


ALL_TOOLS = list(dict.fromkeys(tool for members in GROUPS.values() for tool in members))


def inventory_answer() -> str:
    return "\n".join(
        [f"{name}: {', '.join(members)}" for name, members in GROUPS.items()]
        + [f"Unique tools found: {len(ALL_TOOLS)}."]
    )


def success_steps(*, groups: list[str] | None = None, answer: str | None = None) -> list[list[Any]]:
    return [
        [function_call("discover_tools", {"groups": [name]}, call_id=f"lookup_{i}")]
        for i, name in enumerate(groups if groups is not None else GROUPS)
    ] + [
        [assistant_message(answer if answer is not None else inventory_answer())],
    ]


def catalogue_mcp(**kwargs: Any) -> FakeMcpClient:
    return FakeMcpClient(tools=ALL_TOOLS, **kwargs)


def passed(report: discovery.DiscoveryReport, name: str) -> bool:
    return next(check.passed for check in report.checks if check.name == name)


async def test_success_reads_catalogue_without_executing_tools(tmp_path: Path) -> None:
    mcp = catalogue_mcp()
    report = await run_discovery_check(
        make_config(tmp_path), model=scripted_model(success_steps()), mcp_client=mcp
    )
    assert report.success
    assert report.stage == "complete"
    assert report.error is None
    assert report.server_name == mcp.server_name
    assert report.exposed_tools == ["discover_tools"]
    assert report.model_tool_calls == [
        {"name": "discover_tools", "arguments": {"groups": [name]}} for name in GROUPS
    ]
    assert len(report.discovery_calls) == len(GROUPS)
    for call, (name, members) in zip(report.discovery_calls, GROUPS.items(), strict=True):
        assert call["success"]
        assert call["groups"] == [name]
        assert [tool["name"] for tool in call["tools"]] == list(members)
    assert report.found_tools == ALL_TOOLS
    assert report.found_tools.count("cst_get_solver_info") == 1
    assert report.mcp_tool_calls == mcp.calls == mcp.attempts == []
    assert mcp.entered and mcp.exited
    assert report.max_turns == 24
    saved = json.loads((tmp_path / "reports" / REPORT_NAME).read_text(encoding="utf-8"))
    assert saved == asdict(report)
    assert "PASSED" in report.summary()
    for tool in ALL_TOOLS:
        assert tool in report.summary()


async def test_every_group_can_be_visited_in_another_order(tmp_path: Path) -> None:
    report = await run_discovery_check(
        make_config(tmp_path),
        model=scripted_model(success_steps(groups=list(reversed(GROUPS)))),
        mcp_client=catalogue_mcp(),
    )
    assert report.success
    assert set(report.found_tools) == set(ALL_TOOLS)


@pytest.mark.parametrize(
    ("steps", "failed_check"),
    [
        (
            [[assistant_message(inventory_answer())]],
            "model_requested_each_group",
        ),
        (
            success_steps()[:-1]
            + [
                [function_call("discover_tools", {"groups": ["geometry_basic"]}, call_id="repeat")],
                [assistant_message(inventory_answer())],
            ],
            "each_group_discovered",
        ),
        (
            success_steps(groups=list(GROUPS)[:-1]),
            "each_group_discovered",
        ),
        (
            [
                [function_call("discover_tools", {"groups": []}, call_id="empty")],
                [assistant_message(inventory_answer())],
            ],
            "canonical_groups_returned",
        ),
        (
            [
                [function_call("discover_tools", {"groups": ["not_a_group"]}, call_id="unknown")],
                [assistant_message("Discovery failed.")],
            ],
            "canonical_groups_returned",
        ),
        (
            [
                [function_call("cst_create_cylinder", {}, call_id="forbidden")],
                [assistant_message("Use cst_create_cylinder.")],
            ],
            "model_requested_each_group",
        ),
        (
            success_steps(answer="No tools found."),
            "final_answer_reports_tools",
        ),
        (
            success_steps(answer=inventory_answer() + " cst_invented_tool"),
            "final_answer_reports_tools",
        ),
        (
            success_steps(answer=", ".join(ALL_TOOLS[:-1])),
            "final_answer_reports_tools",
        ),
        (
            [
                [function_call("discover_tools", {"groups": list(GROUPS)}, call_id="combined")],
                [assistant_message(inventory_answer())],
            ],
            "model_requested_each_group",
        ),
    ],
)
async def test_model_must_visit_each_group_and_report_its_tools(
    tmp_path: Path, steps: list[list[Any]], failed_check: str
) -> None:
    mcp = catalogue_mcp()
    report = await run_discovery_check(
        make_config(tmp_path), model=scripted_model(steps), mcp_client=mcp
    )
    assert not report.success
    assert not passed(report, failed_check)
    assert passed(report, "no_mcp_tools_executed")
    assert mcp.exited


async def test_incomplete_group_is_not_success(tmp_path: Path) -> None:
    mcp = FakeMcpClient(tools=[tool for tool in ALL_TOOLS if tool != "cst_create_cylinder"])
    report = await run_discovery_check(
        make_config(tmp_path), model=scripted_model(success_steps()), mcp_client=mcp
    )
    assert not report.success
    geometry_call = next(
        call for call in report.discovery_calls if call["groups"] == ["geometry_basic"]
    )
    assert geometry_call["missing_tools"] == ["cst_create_cylinder"]
    assert geometry_call["tools"] == []
    assert not passed(report, "canonical_groups_returned")
    assert len(report.discovery_calls) == len(GROUPS)
    assert "cst_create_cylinder" not in report.found_tools
    assert "cst_add_sma_edge_connector" in report.found_tools


@pytest.mark.parametrize(
    ("options", "stage"),
    [
        ({"enter_error": McpStartupError("startup failure")}, "mcp_initialize"),
        ({"discover_error": McpError("catalogue failure")}, "tool_discovery"),
        ({"hang": "discover"}, "tool_discovery"),
    ],
)
async def test_mcp_failures_are_saved(tmp_path: Path, options: dict[str, Any], stage: str) -> None:
    mcp = catalogue_mcp(**options)
    report = await run_discovery_check(
        make_config(tmp_path), model=scripted_model(success_steps()), mcp_client=mcp
    )
    assert not report.success
    assert report.stage == stage
    assert report.error
    assert (tmp_path / "reports" / REPORT_NAME).is_file()
    if stage == "tool_discovery":
        assert mcp.exited


async def test_24_turn_limit_retains_partial_evidence(tmp_path: Path) -> None:
    steps = [
        [function_call("discover_tools", {"groups": ["geometry_basic"]}, call_id=f"call_{i}")]
        for i in range(MAX_TURNS + 1)
    ]
    mcp = catalogue_mcp()
    report = await run_discovery_check(
        make_config(tmp_path, max_turns=1), model=scripted_model(steps), mcp_client=mcp
    )
    assert not report.success
    assert report.error == "Model exceeded the 24-turn limit."
    assert len(report.discovery_calls) == MAX_TURNS
    assert len(report.model_tool_calls) == MAX_TURNS
    assert mcp.exited


async def test_default_client_uses_all_toolsets_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mcp = catalogue_mcp()
    received = {}

    def client_factory(**kwargs: Any) -> FakeMcpClient:
        received.update(kwargs)
        return mcp

    monkeypatch.setattr(discovery, "CstMcpClient", client_factory)
    report = await run_discovery_check(make_config(tmp_path), model=scripted_model(success_steps()))
    assert report.success
    assert received["env"]["CST_CONNECT_MODE"] == "disabled"
    assert received["env"]["CST_TOOLSETS"] == "all"
    assert received["env"]["CST_WORK_DIR"] == str(tmp_path / "work")


async def test_provider_is_closed_on_mcp_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = AsyncMock()
    monkeypatch.setattr(
        discovery,
        "_build_provider",
        AsyncMock(return_value=(scripted_model(success_steps()), provider)),
    )
    report = await run_discovery_check(
        make_config(tmp_path), mcp_client=catalogue_mcp(discover_error=McpError("failure"))
    )
    assert not report.success
    provider.close.assert_awaited_once()


async def test_provider_failure_does_not_echo_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = "provider-private-value"
    monkeypatch.setattr(discovery, "_build_provider", AsyncMock(side_effect=RuntimeError(marker)))
    mcp = catalogue_mcp()
    report = await run_discovery_check(make_config(tmp_path), mcp_client=mcp)
    assert not report.success
    assert report.stage == "model_initialize"
    assert marker not in report.summary()
    assert marker not in (tmp_path / "reports" / REPORT_NAME).read_text(encoding="utf-8")
    assert not mcp.entered
