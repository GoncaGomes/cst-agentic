"""The documented catalogue is policy; actual definitions must come from MCP."""

from mcp.types import Tool

from cst_agentic.tool_groups import GROUP_CATALOGUE, ToolGroups, group_description


def definitions(*names: str) -> list[Tool]:
    return [
        Tool(
            name=name,
            description=f"Definition for {name}",
            input_schema={
                "type": "object",
                "properties": {"radius": {"anyOf": [{"type": "number"}, {"type": "string"}]}},
            },
        )
        for name in names
    ]


def test_description_has_every_group_and_purpose() -> None:
    description = group_description()
    assert len(GROUP_CATALOGUE) == 18
    assert len(description) < 5000
    for name, group in GROUP_CATALOGUE.items():
        assert f"- {name}: {group.purpose}" in description


def test_lookup_deduplicates_and_preserves_canonical_definitions() -> None:
    names = (
        "cst_configure_time_domain_solver",
        "cst_get_solver_info",
        "cst_configure_frequency_domain_solver",
    )
    tools = definitions(*names)
    groups = ToolGroups(tools)
    expected = [tool.model_dump(mode="json", by_alias=True, exclude_unset=True) for tool in tools]
    tools[0].input_schema.clear()
    result = groups.discover(
        ["solver_time_domain", "solver_frequency_domain", "solver_time_domain"]
    )
    assert result["success"]
    assert result["groups"] == ["solver_time_domain", "solver_frequency_domain"]
    assert result["tools"] == expected
    result["tools"][0]["inputSchema"].clear()
    assert groups.calls[0]["tools"] == expected
    assert groups.discover(["solver_time_domain"])["tools"] == expected[:2]


def test_missing_member_rejects_whole_lookup() -> None:
    groups = ToolGroups(definitions("cst_configure_time_domain_solver"))
    result = groups.discover(["solver_time_domain"])
    assert not result["success"]
    assert result["missing_tools"] == ["cst_get_solver_info"]
    assert result["tools"] == []


def test_unknown_group_rejects_whole_lookup() -> None:
    groups = ToolGroups(definitions("cst_add_field_monitor"))
    result = groups.discover(["field_monitors", "not_a_group"])
    assert not result["success"]
    assert result["unknown_groups"] == ["not_a_group"]
    assert result["tools"] == []


def test_empty_selection_returns_no_tools() -> None:
    assert ToolGroups([]).discover([]) == {
        "success": True,
        "groups": [],
        "unknown_groups": [],
        "missing_tools": [],
        "tools": [],
    }


def test_duplicate_definitions_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="duplicate"):
        ToolGroups(definitions("cst_add_field_monitor", "cst_add_field_monitor"))
