"""The fixed comparison is distinct from operational discovery settings."""


def test_frozen_pack_pairs_repetitions_and_counterbalances_variants():
    from cst_agentic.evaluation_pack import ENGINEERING_CASES, SCENARIOS, VARIANTS, trial_schedule

    assert [case.id for case in SCENARIOS] == list(range(1, 11))
    assert len(ENGINEERING_CASES) == 6
    assert [(v.id, len(v.groups), v.ceiling) for v in VARIANTS] == [
        ("baseline", 18, 16),
        ("finer", 22, 16),
        ("smaller", 18, 12),
        ("larger", 18, 20),
        ("no-minimal", 18, 16),
        ("no-ceiling", 18, 16),
    ]
    fine = VARIANTS[1].groups
    assert fine["material_create_assign"].members == (
        "cst_create_material",
        "cst_create_lossy_metal",
        "cst_assign_material",
    )
    assert fine["session_lifecycle"].members == (
        "cst_connect",
        "cst_disconnect",
        "cst_open_project",
        "cst_create_project",
        "cst_close_project",
    )
    inventories = [{n for g in v.groups.values() for n in g.members} for v in VARIANTS]
    assert all(inventory == inventories[0] for inventory in inventories)
    assert len(inventories[0] | {"cst_connection_status"}) == 70
    schedule = trial_schedule()
    assert len(schedule) == 132
    assert len({trial.id for trial in schedule}) == 132
    for scenario in range(1, 11):
        runs = [t for t in schedule if t.suite == "comparison" and t.case_id == scenario]
        assert len(runs) == 12
        assert {t.pair for t in runs} == {f"comparison-{scenario}-1", f"comparison-{scenario}-2"}
        assert [t.variant for t in runs[:6]] == list(reversed([t.variant for t in runs[6:]]))
    assert all(s.messages and s.required and s.rubric for s in (*SCENARIOS, *ENGINEERING_CASES))


def test_experimental_discovery_changes_only_grouping_ceiling_and_named_prompt_guidance():
    from mcp.types import Tool

    from cst_agentic.discovery import APPROVED_MCP_TOOLS, ToolDiscovery
    from cst_agentic.evaluation_pack import VARIANTS, variant_discovery

    catalogue = [Tool(name=n, input_schema={"type": "object"}) for n in APPROVED_MCP_TOOLS]
    production = ToolDiscovery(catalogue)
    assert (
        production.select({"groups": ["materials_basic", "geometry_basic", "parameters"]})[
            "accepted"
        ]
        is False
    )
    for variant in VARIANTS:
        selector = variant_discovery(catalogue, variant.id)
        result = selector.select({"groups": ["geometry_basic", "solid_operations"]})
        if variant.id == "finer":
            assert result["accepted"] is False  # historical group no longer exists
            result = selector.select({"groups": ["geometry_primitives", "geometry_wire"]})
            assert result["accepted"] is True
        else:
            assert result["accepted"] is (variant.ceiling >= 16)
        assert result["limit"] == variant.ceiling
        assert ("smallest suitable" in selector.guidance) is variant.minimal_guidance
        assert (f"At most {variant.ceiling}" in selector.guidance) is variant.ceiling_guidance
        assert selector.select({"groups": ["dialog_recovery"]})["accepted"] is False
    assert production.select({"groups": ["parameters"]})["limit"] == 16
