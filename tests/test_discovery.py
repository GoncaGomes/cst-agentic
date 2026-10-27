"""Progressive discovery through the approved conversation coordinator seam."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from agents.testing import ScriptedModel, function_call
from mcp.types import Tool
from test_conversation import Client, Peer

from cst_agentic.controller import ControllerSession, DispatchEvidence
from cst_agentic.conversation import ConversationCoordinator, UserMessage
from cst_agentic.recovery import RecoveryStore
from fakes import conversation_message as assistant_message
from fakes import offline_context_budget


def definition(name, schema=None):
    if name in DELETIONS and schema is None:
        return DELETIONS[name].model_copy(deep=True)
    return Tool(
        name=name,
        description="Canonical server data",
        input_schema=schema or {"type": "object", "additionalProperties": False},
    )


STARTUP = {"cst_connection_status", "cst_project_info", "discover_tools"}
PARAMETERS = {
    "cst_set_parameter",
    "cst_get_parameter",
    "cst_list_parameters",
    "cst_delete_parameter",
}
DELETIONS = {
    tool["name"]: Tool.model_validate(tool)
    for tool in json.loads(
        (Path(__file__).parent / "fixtures" / "canonical_deletions.json").read_text(
            encoding="utf-8"
        )
    )["tools"]
}
EXPECTED_GROUPS = json.loads(
    (Path(__file__).parent / "fixtures" / "approved_discovery.json").read_text(encoding="utf-8")
)["groups"]


@asynccontextmanager
async def discovering(
    tmp_path,
    model,
    *,
    catalogue=None,
    allowlist=None,
    session_inventory=None,
    dispatch_check=None,
    peer=None,
    **kwargs,
):
    from cst_agentic.discovery import APPROVED_MCP_TOOLS, ToolDiscovery

    tools = (
        catalogue
        if catalogue is not None
        else [
            definition(name)
            for name in sorted({"cst_connection_status"}.union(*EXPECTED_GROUPS.values()))
        ]
    )
    peer, store = peer or Peer(), RecoveryStore(tmp_path / "state")
    async with ControllerSession(
        store,
        lambda: Client(peer),
        inventory=APPROVED_MCP_TOOLS if session_inventory is None else session_inventory,
        dispatch_check=dispatch_check
        or (lambda *args: DispatchEvidence("controlled-process-created-1")),
    ) as session:
        directory = tmp_path / "project"
        directory.mkdir()
        await session.start_task(directory / "a.cst", "Explicit controlled task")
        coordinator = ConversationCoordinator(
            model=model,
            connection=session,
            store=store,
            discovery=ToolDiscovery(tools),
            allowlist=APPROVED_MCP_TOOLS if allowlist is None else allowlist,
            request_admission=lambda request: None,
            context_budget=kwargs.pop("context_budget", offline_context_budget()),
            interpreters={name: lambda result: True for name in APPROVED_MCP_TOOLS},
            **kwargs,
        )
        yield coordinator, store, peer


def names(call):
    return {tool.name for tool in call.tools}


@pytest.mark.asyncio
async def test_oversized_discovery_rejections_bound_explanations_not_call_arguments(tmp_path):
    arguments = {"groups": ["unrecognized-" + "x" * 20_000]}
    model = ScriptedModel(
        [
            [function_call("discover_tools", arguments, call_id="large-rejection")],
            [assistant_message("Please choose a known group.")],
        ]
    )
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        reply = await coordinator.submit("Inspect available choices")
        assert reply.state == "reply"
        output = next(
            item["output"]
            for item in coordinator.history
            if item.get("type") == "function_call_output"
        )
        assert len(output.encode("utf-8")) <= 16_384
        assert json.loads(output)["omissions"]["selection"] is True
        call = next(item for item in coordinator.history if item.get("type") == "function_call")
        assert json.loads(call["arguments"]) == arguments
        assert {tool.name for tool in coordinator.active_tools} == STARTUP
        assert peer.seen == []


@pytest.mark.asyncio
async def test_selection_activates_canonical_definitions_next_request_with_paired_history(tmp_path):
    schema = {
        "type": "object",
        "properties": {
            "value": {"anyOf": [{"type": "number"}, {"type": "null"}], "default": None},
        },
        "additionalProperties": False,
    }
    tools = [definition(name) for name in STARTUP - {"discover_tools"} | PARAMETERS]
    tools = [definition(t.name, schema) if t.name == "cst_get_parameter" else t for t in tools]
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="select")],
            [function_call("cst_get_parameter", {}, call_id="read")],
            [assistant_message("Received; native effects unverified.")],
        ]
    )
    async with discovering(tmp_path, model, catalogue=tools) as (coordinator, store, peer):
        reply = await coordinator.submit("Inspect parameters")
        assert reply.state == "reply"
        assert names(model.calls[0]) == STARTUP
        assert names(model.calls[1]) == STARTUP | PARAMETERS
        active = next(t for t in model.calls[1].tools if t.name == "cst_get_parameter")
        assert active.params_json_schema == schema
        assert active.strict_json_schema is False
        assert peer.seen == ["cst_get_parameter"]
        pairs = [i for i in model.calls[1].input if i.get("type") == "function_call_output"]
        assert pairs[0]["call_id"] == "select"
        result = json.loads(pairs[0]["output"])["selection"]
        assert result["accepted"] is True
        assert result["visible_count"] == 7
        assert result["limit"] == 16
        assert result["activation"] == "next internal request"
        assert len(store.incidents()) == 1  # Discovery is not an MCP operation.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid, expected",
    [
        ({"groups": ["dialog_recovery"]}, "dialog_recovery"),
        ({"groups": "parameters"}, "array"),
        ({"groups": ["parameters"], "extra": True}, "extra"),
        ({}, "groups"),
        ({"groups": ["geometry_basic", "solid_operations", "materials_basic"]}, "23"),
    ],
)
async def test_invalid_selection_is_atomic_explained_and_can_be_corrected(
    tmp_path, invalid, expected
):
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": ["reference"]}, call_id="valid")],
            [function_call("discover_tools", invalid, call_id="invalid")],
            [assistant_message("Please clarify the unavailable selection.")],
        ]
    )
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        assert (await coordinator.submit("Inspect help")).state == "reply"
        assert names(model.calls[2]) == STARTUP | {"cst_search_help", "cst_read_help"}
        result = json.loads(coordinator.history[-2]["output"])["selection"]
        assert result["accepted"] is False
        assert result["current_groups"] == ["reference"]
        assert result["visible_count"] == 5
        assert expected in result["reason"]
        assert peer.seen == [] and store.incidents() == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_schema",
    [
        None,
        {"type": "object", "properties": {"value": {"type": "imaginary"}}},
        {"type": "object", "unreviewedAssertion": True},
        {"type": "object", "properties": {"value": {"$ref": "https://example.invalid/schema"}}},
        {"type": "object", "properties": {"value": {"$ref": "#/$defs/absent"}}},
    ],
)
async def test_unavailable_or_unfaithful_group_rejects_without_partial_activation(
    tmp_path, bad_schema
):
    tools = [definition(name) for name in STARTUP - {"discover_tools"} | PARAMETERS]
    tools = [t for t in tools if t.name != "cst_set_parameter"]
    if bad_schema is not None:
        tools.append(definition("cst_set_parameter", bad_schema))
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="unavailable")],
            [assistant_message("Required parameter capability is missing or unverified.")],
        ]
    )
    async with discovering(tmp_path, model, catalogue=tools) as (coordinator, store, peer):
        assert (await coordinator.submit("Inspect parameters")).state == "reply"
        assert names(model.calls[1]) == STARTUP
        result = json.loads(coordinator.history[-2]["output"])["selection"]
        assert result["accepted"] is False
        assert "cst_set_parameter" in result["reason"]
        assert peer.seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["three-rejections", "normalized-cycle", "mixed", "multiple"])
async def test_discovery_escape_is_bounded_and_entire_batches_are_effect_free(tmp_path, fault):
    def select(groups, call_id):
        return function_call("discover_tools", {"groups": groups}, call_id=call_id)

    if fault == "three-rejections":
        steps = [[select(["unknown"], f"reject-{i}")] for i in range(4)]
        expected_requests, expected_pairs = 3, 3
    elif fault == "normalized-cycle":
        steps = [
            [select(["parameters", "reference"], "first")],
            [select(["reference", "parameters", "reference"], "cycle")],
        ]
        expected_requests, expected_pairs = 2, 2
    else:
        second = (
            function_call("cst_connection_status", {}, call_id="read")
            if fault == "mixed"
            else select(["reference"], "other-discovery")
        )
        steps = [
            [select(["parameters"], "first"), second],
            [assistant_message("Retry discovery alone.")],
        ]
        expected_requests, expected_pairs = 2, 2
    model = ScriptedModel(steps)
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        reply = await coordinator.submit("Inspect project")
        assert len(model.calls) == expected_requests
        assert peer.seen == [] and store.incidents() == ()
        outputs = [
            json.loads(i["output"])
            for i in coordinator.history
            if i.get("type") == "function_call_output"
        ]
        assert len(outputs) == expected_pairs
        if fault in {"mixed", "multiple"}:
            assert names(model.calls[1]) == STARTUP
            assert all(o["state"] == "rejected" for o in outputs)
            assert "only call" in outputs[0]["reason"]
        else:
            assert reply.state == "paused"
            assert "guidance" in reply.text
            assert ("three" if fault == "three-rejections" else "Repeated") in reply.text


@pytest.mark.asyncio
async def test_selection_replaces_deduplicates_and_survives_clarification_but_not_new_objective(
    tmp_path,
):
    from cst_agentic.conversation import UserMessage

    groups = [
        "session_project",
        "project_context",
        "solver_time_domain",
        "solver_frequency_domain",
        "reference",
    ]
    model = ScriptedModel(
        [
            [
                function_call(
                    "discover_tools", {"groups": [*groups, "reference"]}, call_id="sixteen"
                )
            ],
            [assistant_message("Which parameter?")],
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="replace")],
            [assistant_message("Clarification retained.")],
            [assistant_message("New objective starts at startup.")],
        ]
    )
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        await coordinator.submit("Inspect project")
        assert len(model.calls[1].tools) == 16
        await coordinator.submit("The width parameter")
        assert len(model.calls[2].tools) == 16
        assert model.calls[2].input[-1]["content"] == "The width parameter"
        assert names(model.calls[3]) == STARTUP | PARAMETERS
        old_history = coordinator.history
        await coordinator.submit(UserMessage("Separate objective", new_objective=True))
        assert names(model.calls[4]) == STARTUP
        assert coordinator.history[: len(old_history)] == old_history
        assert peer.seen == []


@pytest.mark.asyncio
async def test_successful_work_breaks_discovery_cycle_and_empty_selection_returns_startup(tmp_path):
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="first")],
            [function_call("cst_list_parameters", {}, call_id="work")],
            [
                function_call(
                    "discover_tools", {"groups": ["parameters", "parameters"]}, call_id="again"
                )
            ],
            [function_call("discover_tools", {"groups": []}, call_id="startup")],
            [assistant_message("Done.")],
        ]
    )
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        assert (await coordinator.submit("Inspect parameters")).state == "reply"
        assert names(model.calls[-1]) == STARTUP
        assert peer.seen == ["cst_list_parameters"]


@pytest.mark.asyncio
async def test_catalogue_is_frozen_until_authorized_refresh_and_drift_disables_whole_group(
    tmp_path,
):
    from cst_agentic.discovery import APPROVED_MCP_TOOLS

    tools = [definition(name) for name in sorted(APPROVED_MCP_TOOLS)]

    async def load():
        return tools

    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="select")],
            [assistant_message("Which parameter?")],
            [assistant_message("Still the same task snapshot.")],
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="drift")],
            [assistant_message("Schema review is needed.")],
        ]
    )
    async with discovering(tmp_path, model, catalogue=tools, catalogue_loader=load) as (
        coordinator,
        store,
        peer,
    ):
        await coordinator.submit("Inspect parameters")
        original = next(
            t for t in model.calls[1].tools if t.name == "cst_get_parameter"
        ).params_json_schema
        changed = next(t for t in tools if t.name == "cst_get_parameter")
        changed.input_schema = {"type": "object", "properties": {"new": {"type": "boolean"}}}
        refused = await coordinator.refresh_catalogue()
        assert refused.state == "paused" and "explicit" in refused.text
        await coordinator.submit(UserMessage("The width"))
        assert names(model.calls[2]) == STARTUP | PARAMETERS
        assert (
            next(t for t in model.calls[2].tools if t.name == changed.name).params_json_schema
            == original
        )
        refreshed = await coordinator.refresh_catalogue(explicitly_authorized=True)
        assert "drift" in refreshed.text and "cst_get_parameter" in refreshed.text
        await coordinator.submit(UserMessage("Inspect parameters again"))
        assert names(model.calls[3]) == STARTUP
        assert names(model.calls[4]) == STARTUP
        assert peer.seen == []


@pytest.mark.asyncio
async def test_refresh_startup_loss_blocks_requests_and_new_objective_refreshes_at_settled_boundary(
    tmp_path,
):
    from cst_agentic.conversation import UserMessage
    from cst_agentic.discovery import APPROVED_MCP_TOOLS

    tools = [definition(name) for name in sorted(APPROVED_MCP_TOOLS)]
    loads = []

    async def load():
        loads.append(True)
        return tools

    async def during_response(call):
        assert (await coordinator.refresh_catalogue(explicitly_authorized=True)).state == "paused"
        assert loads == []
        return [assistant_message("Settled.")]

    model = ScriptedModel([{"responder": during_response}])
    async with discovering(tmp_path, model, catalogue=tools, catalogue_loader=load) as (
        coordinator,
        store,
        peer,
    ):
        await coordinator.submit("Inspect project")
        tools[:] = [t for t in tools if t.name != "cst_project_info"]
        reply = await coordinator.submit(UserMessage("New separate objective", new_objective=True))
        assert reply.state == "paused" and "cst_project_info" in reply.text
        assert loads == [True]
        assert len(model.calls) == 1
        assert (await coordinator.submit("continue")).state == "paused"
        assert len(model.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("gate", ["hidden", "inventory", "permission", "unreviewed"])
async def test_selection_cannot_grant_originating_visibility_inventory_or_execution_permission(
    tmp_path, gate
):
    from cst_agentic.discovery import APPROVED_MCP_TOOLS

    tools = [definition(name) for name in sorted(APPROVED_MCP_TOOLS)]
    tools.append(definition("cst_execute_vba"))
    steps = [[function_call("discover_tools", {"groups": ["parameters"]}, call_id="selection")]]
    name = "cst_list_parameters"
    if gate == "hidden":
        steps = []
    elif gate == "unreviewed":
        name = "cst_execute_vba"
    model = ScriptedModel([*steps, [function_call(name, {}, call_id="blocked")]])
    async with discovering(
        tmp_path,
        model,
        catalogue=tools,
        allowlist=frozenset({"cst_execute_vba"}) if gate in {"inventory", "unreviewed"} else None,
        dispatch_check=(lambda *args: None) if gate == "permission" else None,
    ) as (coordinator, store, peer):
        assert (await coordinator.submit("Inspect parameters")).state == "paused"
        assert peer.seen == [] and store.incidents() == ()
        assert all("cst_execute_vba" not in names(call) for call in model.calls)


@pytest.mark.asyncio
async def test_uncertainty_cannot_be_cleared_by_new_objective_or_refresh(tmp_path):
    from cst_agentic.conversation import UserMessage

    loads = []

    async def load():
        loads.append(True)
        return []

    peer = Peer()
    peer.failure = "transport"
    model = ScriptedModel([[function_call("cst_connection_status", {}, call_id="uncertain")]])
    async with discovering(tmp_path, model, peer=peer, catalogue_loader=load) as (
        coordinator,
        store,
        peer,
    ):
        assert (await coordinator.submit("Read status")).state == "paused"
        assert (await coordinator.refresh_catalogue(explicitly_authorized=True)).state == "paused"
        assert (
            await coordinator.submit(UserMessage("Separate objective", new_objective=True))
        ).state == "paused"
        assert loads == []
        assert len(model.calls) == 1 and peer.seen == ["cst_connection_status"]
        assert store.incidents(unresolved_only=True)[0].state == "uncertain"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing", ["cst_connection_status", "cst_project_info", "duplicate", "invalid-schema"]
)
async def test_unusable_required_startup_blocks_before_any_model_request(tmp_path, missing):
    tools = [definition(name) for name in STARTUP - {"discover_tools", missing}]
    if missing == "duplicate":
        tools.append(definition("cst_project_info"))
    elif missing == "invalid-schema":
        tools = [definition(t.name, {"type": "object", "unknownAssertion": True}) for t in tools]
    model = ScriptedModel([])
    async with discovering(tmp_path, model, catalogue=tools) as (coordinator, store, peer):
        reply = await coordinator.submit("Inspect project")
        assert reply.state == "paused" and "startup" in reply.text
        assert model.calls == () and peer.seen == []
        assert (await coordinator.submit("continue")).state == "paused"
        assert model.calls == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("group", EXPECTED_GROUPS)
async def test_each_operational_group_exposes_exact_authoritative_membership(tmp_path, group):
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": [group]}, call_id="group")],
            [assistant_message("Selected.")],
        ]
    )
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        assert (await coordinator.submit("Select tools")).state == "reply"
        assert names(model.calls[1]) == STARTUP | set(EXPECTED_GROUPS[group])
        discovery = next(t for t in model.calls[0].tools if t.name == "discover_tools")
        enum = discovery.params_json_schema["properties"]["groups"]["items"]["enum"]
        assert set(enum) == set(EXPECTED_GROUPS) and len(enum) == 18
        assert len({"cst_connection_status"}.union(*EXPECTED_GROUPS.values())) == 72


@pytest.mark.asyncio
async def test_terminal_text_controls_reset_new_tasks_and_explicitly_refresh_without_model_calls(
    tmp_path,
):
    tools = [definition(name) for name in STARTUP - {"discover_tools"} | PARAMETERS]
    loads = []

    async def load():
        loads.append(True)
        return tools

    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="select")],
            [assistant_message("Which parameter?")],
            [assistant_message("Separate objective.")],
        ]
    )
    async with discovering(tmp_path, model, catalogue=tools, catalogue_loader=load) as (
        coordinator,
        store,
        peer,
    ):
        await coordinator.submit("Inspect parameters")
        await coordinator.submit("new task: Inspect project")
        assert names(model.calls[-1]) == STARTUP
        assert loads == [True]
        assert (await coordinator.submit("refresh tools")).state == "reply"
        assert len(model.calls) == 3 and loads == [True, True]
        assert peer.seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", [{}, {"value": None}, {"value": 2.5}, {"value": True}])
async def test_canonical_local_refs_defaults_and_unions_are_validated_without_argument_rewriting(
    tmp_path, arguments
):
    schema = {
        "type": "object",
        "$defs": {"quantity": {"type": ["number", "null"]}},
        "properties": {"value": {"$ref": "#/$defs/quantity", "default": None}},
        "additionalProperties": False,
    }
    tools = [definition(name) for name in STARTUP - {"discover_tools"} | PARAMETERS]
    tools = [definition(t.name, schema) if t.name == "cst_get_parameter" else t for t in tools]
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="select")],
            [function_call("cst_get_parameter", arguments, call_id="canonical")],
            [assistant_message("Received.")],
        ]
    )
    async with discovering(tmp_path, model, catalogue=tools) as (coordinator, store, peer):
        reply = await coordinator.submit("Inspect parameters")
        if arguments == {"value": True}:
            assert reply.state == "paused" and peer.seen == []
        else:
            assert reply.state == "reply" and peer.seen == ["cst_get_parameter"]
            assert coordinator.evidence[0].result.arguments == arguments
        assert (
            next(
                t for t in model.calls[1].tools if t.name == "cst_get_parameter"
            ).params_json_schema
            == schema
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw", ["[", "null", '{"groups":[],"groups":["parameters"]}', '{"groups":[1e999]}']
)
async def test_malformed_discovery_arguments_have_matched_results_without_selection_changes(
    tmp_path, raw
):
    call = function_call("discover_tools", {}, call_id="malformed")
    call.arguments = raw
    model = ScriptedModel([[call], [assistant_message("Please correct the selection.")]])
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        assert (await coordinator.submit("Inspect project")).state == "reply"
        assert names(model.calls[1]) == STARTUP
        output = next(i for i in coordinator.history if i.get("type") == "function_call_output")
        assert output["call_id"] == "malformed"
        assert json.loads(output["output"])["selection"]["accepted"] is False
        assert peer.seen == []


@pytest.mark.asyncio
async def test_acceptance_breaks_rejection_streak_and_pause_needs_guidance_not_bare_continue(
    tmp_path,
):
    steps = [
        [function_call("discover_tools", {"groups": ["unknown"]}, call_id=f"bad-{i}")]
        for i in range(2)
    ]
    steps.append([function_call("discover_tools", {"groups": ["parameters"]}, call_id="valid")])
    steps.extend(
        [
            [function_call("discover_tools", {"groups": ["unknown"]}, call_id=f"bad-after-{i}")]
            for i in range(3)
        ]
    )
    model = ScriptedModel([*steps, [assistant_message("Guidance received.")]])
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        assert (await coordinator.submit("Inspect parameters")).state == "paused"
        assert len(model.calls) == 6
        assert (await coordinator.submit("continue")).state == "paused"
        assert len(model.calls) == 6
        assert (
            await coordinator.submit(UserMessage("Only inspect existing parameter names"))
        ).state == "reply"
        assert names(model.calls[-1]) == STARTUP | PARAMETERS


@pytest.mark.asyncio
async def test_discovery_and_refresh_through_actual_protected_stdio_wrapper(tmp_path):
    from test_controller_runtime import manual_config

    from cst_agentic.controller import ControllerMcpClient
    from cst_agentic.controller_runtime import admit_manual_catalogue
    from cst_agentic.discovery import APPROVED_MCP_TOOLS, ToolDiscovery

    config = manual_config(tmp_path, "discovery")
    client = ControllerMcpClient(
        config.mcp_executable,
        config.mcp_cwd,
        {},
        5,
        5,
        5,
        catalogue_admission=admit_manual_catalogue,
    )
    store = RecoveryStore(tmp_path / "state")
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="select")],
            [function_call("cst_get_parameter", {}, call_id="read")],
            [assistant_message("Controlled response received.")],
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="missing")],
            [assistant_message("Parameter group unavailable after refresh.")],
        ]
    )
    async with ControllerSession(
        store,
        lambda: client,
        inventory=APPROVED_MCP_TOOLS,
        dispatch_check=lambda *args: DispatchEvidence("controlled-stdio-created-1"),
    ) as session:
        directory = tmp_path / "project"
        directory.mkdir()
        await session.start_task(directory / "a.cst", "Inspect controlled peer")
        coordinator = ConversationCoordinator(
            model=model,
            connection=session,
            store=store,
            discovery=ToolDiscovery(session.catalogue),
            catalogue_loader=session.refresh_catalogue,
            allowlist=APPROVED_MCP_TOOLS,
            request_admission=lambda request: None,
            context_budget=offline_context_budget(),
            interpreters={
                "cst_get_parameter": lambda result: result.structured_content == {"mode": "offline"}
            },
        )
        assert (await coordinator.submit("Inspect parameters")).state == "reply"
        assert names(model.calls[1]) == STARTUP | PARAMETERS
        assert (
            next(
                t for t in model.calls[1].tools if t.name == "cst_delete_parameter"
            ).params_json_schema
            == DELETIONS["cst_delete_parameter"].input_schema
        )
        assert (
            "cst_set_parameter"
            in (await coordinator.refresh_catalogue(explicitly_authorized=True)).text
        )
        assert (await coordinator.submit(UserMessage("Inspect parameters again"))).state == "reply"
        assert names(model.calls[3]) == names(model.calls[4]) == STARTUP
        assert [attempt.name for attempt in session.attempts] == ["cst_get_parameter"]
    observation = json.loads((tmp_path / "observed.json").read_text(encoding="utf-8"))
    assert observation["calls"] == ["tools/call"]


@pytest.mark.asyncio
async def test_ordinary_clarification_reaches_model_with_original_wording_and_selection(tmp_path):
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="select")],
            [assistant_message("Which parameter?")],
            [assistant_message("Width clarification received.")],
        ]
    )
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        await coordinator.submit("Inspect parameters")
        history = coordinator.history
        followup = "The width parameter"
        reply = await coordinator.submit(followup)
        assert reply.state == "reply" and reply.text == "Width clarification received."
        assert len(model.calls) == 3
        assert names(model.calls[-1]) == STARTUP | PARAMETERS
        context = json.loads(model.calls[-1].input[0]["content"])
        assert context["objective"] == "Inspect parameters"
        assert model.calls[-1].input[-1]["content"] == followup
        assert model.calls[-1].input[1:-1] == history
        assert peer.seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer,new_objective",
    [
        ("same task", None),
        ("new task", "Inspect materials"),
        ("Continue the same design; I mean its substrate.", None),
    ],
)
async def test_model_boundary_question_and_ordinary_answer_remain_in_conversation(
    tmp_path, answer, new_objective
):
    question = "Do materials belong to this design, or are you starting a separate objective?"
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="select")],
            [assistant_message("Which parameter?")],
            [assistant_message(question)],
            [assistant_message("Boundary understood.", new_objective=new_objective)],
            [assistant_message("Ready for the new objective.")],
        ]
    )
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        await coordinator.submit("Inspect parameters")
        reply = await coordinator.submit("What about materials?")
        assert reply.text == question and reply.state == "reply"
        assert model.calls[-1].input[-1]["content"] == "What about materials?"
        reply = await coordinator.submit(answer)
        assert reply.text == (
            "Ready for the new objective." if new_objective else "Boundary understood."
        )
        assert model.calls[3].input[-1]["content"] == answer
        assert json.loads(model.calls[3].input[-2]["content"][0]["text"])["text"] == question
        assert names(model.calls[-1]) == (STARTUP if new_objective else STARTUP | PARAMETERS)
        assert json.loads(model.calls[-1].input[0]["content"])["objective"] == (
            new_objective or "Inspect parameters"
        )
        assert peer.seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stale", [None, "cst_get_parameter", "cst_connection_status", "discover_tools", "mixed"]
)
async def test_model_transition_resets_before_work_and_preserves_history_and_safety(
    tmp_path, stale
):
    from cst_agentic.discovery import APPROVED_MCP_TOOLS
    from cst_agentic.project_storage import ProjectLocation

    loads = []

    async def load():
        loads.append(True)
        return [definition(name) for name in sorted(APPROVED_MCP_TOOLS)]

    transition = [
        assistant_message("Inspecting a separate design.", new_objective="Inspect materials")
    ]
    if stale == "mixed":
        transition.extend(
            [
                function_call("cst_get_parameter", {}, call_id="stale"),
                function_call(
                    "discover_tools", {"groups": ["materials_basic"]}, call_id="stale-discovery"
                ),
            ]
        )
    elif stale is not None:
        arguments = {"groups": ["materials_basic"]} if stale == "discover_tools" else {}
        transition.append(function_call(stale, arguments, call_id="stale"))
    model = ScriptedModel(
        [
            [function_call("cst_connection_status", {}, call_id="evidence")],
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="first")],
            [function_call("discover_tools", {"groups": ["unknown"]}, call_id="bad-1")],
            [function_call("discover_tools", {"groups": ["unknown"]}, call_id="bad-2")],
            [assistant_message("Which parameter?")],
            transition,
            [function_call("discover_tools", {"groups": ["unknown"]}, call_id="new-bad")],
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="new-select")],
            [assistant_message("Ready for the next step.")],
        ]
    )
    async with discovering(tmp_path, model, catalogue_loader=load) as (coordinator, store, peer):
        await coordinator.submit("Inspect parameters")
        history, evidence = coordinator.history, coordinator.evidence
        other = tmp_path / "other"
        other.mkdir()
        incident = store.prepare(
            "10000000-0000-0000-0000-000000000001",
            "cst_run_simulation_async",
            ProjectLocation.inspect(other / "b.cst"),
            "other-instance",
        )
        # Historical settled incidents survive objective transitions. An
        # unresolved incident now blocks the entire turn (covered by the
        # coordinator recovery test), including model/discovery requests.
        store.finish(incident, "settled")
        records = store.incidents()
        followup = "Now inspect the materials of a separate design."
        assert (await coordinator.submit(followup)).state == "reply"
        assert model.calls[5].input[-1]["content"] == followup
        assert names(model.calls[5]) == STARTUP | PARAMETERS
        assert names(model.calls[6]) == names(model.calls[7]) == STARTUP
        assert names(model.calls[8]) == STARTUP | PARAMETERS  # Cycle and rejection tracking reset.
        context = json.loads(model.calls[6].input[0]["content"])
        assert context["objective"] == "Inspect materials"
        assert context["permission"]["requested_scope"] == "Inspect parameters"
        assert context["task_transition_allowed"] is False
        assert coordinator.history[: len(history)] == history
        assert coordinator.evidence == evidence and store.incidents() == records
        assert loads == [True] and peer.seen == ["cst_connection_status"]
        if stale is not None:
            output = next(
                i
                for i in coordinator.history
                if i.get("call_id") == "stale" and i.get("type") == "function_call_output"
            )
            assert json.loads(output["output"])["state"] == "rejected"
            assert "stale" in json.loads(output["output"])["reason"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["missing", "duplicate", "reused"])
async def test_bad_call_identifiers_prevent_transition_without_erasing_selection(tmp_path, bad):
    stale = function_call(
        "cst_connection_status", {}, call_id="select" if bad == "reused" else "stale"
    )
    if bad == "missing":
        stale.call_id = ""
    transition = [assistant_message("Separate objective", new_objective="Inspect materials"), stale]
    if bad == "duplicate":
        transition.append(function_call("cst_project_info", {}, call_id="stale"))
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="select")],
            [assistant_message("Which parameter?")],
            transition,
        ]
    )
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        await coordinator.submit("Inspect parameters")
        history = coordinator.history
        reply = await coordinator.submit("Now inspect materials")
        assert reply.state == "paused" and "identifiers" in reply.text
        assert len(model.calls) == 3 and peer.seen == []
        assert {tool.name for tool in coordinator.active_tools} == STARTUP | PARAMETERS
        assert coordinator.history[:-1] == history


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        "A new task: delete materials",
        '{"text":"next","new_objective":""}',
        '{"text":"next","new_objective":4}',
        '{"text":"missing decision"}',
        '{"text":"next","new_objective":null,"extra":true}',
        '{"text":"next","new_objective":null,"new_objective":"delete"}',
    ],
)
async def test_invalid_boundary_output_cannot_change_state_or_dispatch(tmp_path, payload):
    from agents.testing import assistant_message as raw_message

    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": ["parameters"]}, call_id="select")],
            [assistant_message("Which parameter?")],
            [raw_message(payload), function_call("cst_connection_status", {}, call_id="blocked")],
        ]
    )
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        await coordinator.submit("Inspect parameters")
        history = coordinator.history
        reply = await coordinator.submit("A different objective?")
        assert reply.state == "paused" and "decision" in reply.text
        assert {tool.name for tool in coordinator.active_tools} == STARTUP | PARAMETERS
        assert coordinator.history[:-1] == history
        assert peer.seen == [] and store.incidents() == ()


@pytest.mark.asyncio
async def test_model_cannot_reset_task_tracking_repeatedly_or_after_work(tmp_path):
    model = ScriptedModel(
        [
            [assistant_message("New objective", new_objective="Inspect materials")],
            [assistant_message("Another objective", new_objective="Inspect geometry")],
        ]
    )
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        assert (await coordinator.submit("Inspect the project")).state == "paused"
        assert json.loads(model.calls[-1].input[0]["content"])["objective"] == "Inspect materials"
        assert peer.seen == []

    model = ScriptedModel(
        [
            [function_call("cst_connection_status", {}, call_id="work")],
            [assistant_message("Changing scope after work", new_objective="Delete materials")],
        ]
    )
    async with discovering(tmp_path / "second", model) as (coordinator, store, peer):
        assert (await coordinator.submit("Inspect the project")).state == "paused"
        assert json.loads(model.calls[-1].input[0]["content"])["objective"] == "Inspect the project"
        assert peer.seen == ["cst_connection_status"]


@pytest.mark.asyncio
async def test_initial_prompt_contains_operational_purposes_generated_counts_and_boundary_schema(
    tmp_path,
):
    from cst_agentic.discovery import APPROVED_MCP_TOOLS, GROUP_CATALOGUE

    model = ScriptedModel([[assistant_message("Which design?")]])
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        await coordinator.submit("Inspect project")
        initial = model.calls[0]
        assert names(initial) == STARTUP and len(APPROVED_MCP_TOOLS) == 72
        assert set(GROUP_CATALOGUE) == set(EXPECTED_GROUPS)
        for name, members in EXPECTED_GROUPS.items():
            assert (
                f"{name} ({len(members)}): {GROUP_CATALOGUE[name].purpose}"
                in initial.system_instructions
            )
        for qualification in (
            "explicitly targeted",
            "not visual verification",
            "do not establish stored expressions",
            "exact library entries first",
            "not verify project material properties",
            "wire/bondwire",
            "profile-based",
            "copies to identified geometry",
            "units/argument contract",
            "do not preserve parameter-expression",
            "ordinary time-domain",
            "ordinary frequency-domain",
            "compatible mesh",
            "before a solve",
            "bounded waits",
            "numerical success",
            "not live project validation",
            "arbitrary code execution",
            "scoped paths and targets",
            "assumptions match",
            "smallest suitable",
            "whole set",
            "16 total unique",
            "overlaps count once",
            "only call in its batch",
            "without granting execution permission",
        ):
            assert qualification in initial.system_instructions
        schema = initial.output_schema.json_schema()
        assert set(schema["properties"]) == {"text", "new_objective"}
        assert schema["additionalProperties"] is False
        assert (
            initial.output_schema.validate_json(
                '{"text":"Which design?","new_objective":null}'
            ).text
            == "Which design?"
        )


@pytest.mark.asyncio
async def test_revised_groups_fill_sixteen_function_budget_and_reject_seventeen(tmp_path):
    groups = ["parameters", "materials_basic", "reference"]
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": groups}, call_id="sixteen")],
            [
                function_call(
                    "discover_tools", {"groups": [*groups, "field_monitors"]}, call_id="seventeen"
                )
            ],
            [assistant_message("Keep the accepted selection.")],
        ]
    )
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        assert (
            await coordinator.submit("Inspect parameters and materials with help")
        ).state == "reply"
        assert len(model.calls[1].tools) == len(model.calls[2].tools) == 16
        outputs = [
            json.loads(i["output"])["selection"]
            for i in coordinator.history
            if i.get("type") == "function_call_output"
        ]
        assert outputs[0]["accepted"] and outputs[0]["visible_count"] == 16
        assert not outputs[1]["accepted"] and "17" in outputs[1]["reason"]
        assert outputs[1]["current_groups"] == sorted(groups)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "group,name",
    [("parameters", "cst_delete_parameter"), ("materials_basic", "cst_delete_material")],
)
@pytest.mark.parametrize("explicit_flag", [False, True])
async def test_deletions_activate_exact_canonical_schemas_and_preserve_arguments(
    tmp_path, group, name, explicit_flag
):
    arguments = {"name": "Unused"}
    if explicit_flag and name == "cst_delete_parameter":
        arguments["delete_results"] = True
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": [group]}, call_id="select")],
            [function_call(name, arguments, call_id="delete")],
            [assistant_message("Controlled response received; native effect unverified.")],
        ]
    )
    async with discovering(tmp_path, model) as (coordinator, store, peer):
        assert (
            await coordinator.submit("Delete the explicitly identified unused entry")
        ).state == "reply"
        assert set(DELETIONS).isdisjoint(names(model.calls[0]))
        active = next(t for t in model.calls[1].tools if t.name == name)
        assert active.params_json_schema == DELETIONS[name].input_schema
        assert (
            active.description == DELETIONS[name].description and active.strict_json_schema is False
        )
        assert peer.seen == [name] and coordinator.evidence[0].result.arguments == arguments
        assert store.incidents(unresolved_only=True) == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "group,name",
    [("parameters", "cst_delete_parameter"), ("materials_basic", "cst_delete_material")],
)
@pytest.mark.parametrize(
    "gate", ["hidden", "allowlist", "session-inventory", "permission", "target", "arguments"]
)
async def test_deletions_have_independent_execution_enforcement(tmp_path, group, name, gate):
    from cst_agentic.discovery import APPROVED_MCP_TOOLS

    arguments = {"name": 17} if gate == "arguments" else {"name": "Unused"}

    def propose(call):
        if gate == "target":
            (tmp_path / "project").rename(tmp_path / "replaced-project")
            (tmp_path / "project").mkdir()
        return [function_call(name, arguments, call_id="blocked")]

    steps = (
        []
        if gate == "hidden"
        else [[function_call("discover_tools", {"groups": [group]}, call_id="select")]]
    )
    model = ScriptedModel([*steps, {"responder": propose}])
    async with discovering(
        tmp_path,
        model,
        allowlist=APPROVED_MCP_TOOLS - {name} if gate == "allowlist" else None,
        session_inventory=APPROVED_MCP_TOOLS - {name} if gate == "session-inventory" else None,
        dispatch_check=(lambda *args: None) if gate == "permission" else None,
    ) as (coordinator, store, peer):
        assert (await coordinator.submit("Delete the unused entry")).state == "paused"
        assert peer.seen == [] and store.incidents() == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "group,name",
    [("parameters", "cst_delete_parameter"), ("materials_basic", "cst_delete_material")],
)
@pytest.mark.parametrize("failure", ["transport", "domain"])
async def test_uncertain_or_unresolved_work_blocks_deletions_and_new_task_bypass(
    tmp_path, group, name, failure
):
    peer = Peer()
    peer.failure = failure
    model = ScriptedModel(
        [
            [function_call("discover_tools", {"groups": [group]}, call_id="select")],
            [
                function_call("cst_connection_status", {}, call_id="uncertain"),
                function_call(name, {"name": "Unused"}, call_id="skipped"),
            ],
        ]
    )
    async with discovering(tmp_path, model, peer=peer) as (coordinator, store, peer):
        assert (await coordinator.submit("Delete the unused entry")).state == "paused"
        history, evidence, records = coordinator.history, coordinator.evidence, store.incidents()
        assert (
            await coordinator.submit("This is a separate objective: delete the entry")
        ).state == "paused"
        assert (
            await coordinator.submit(UserMessage("Delete", new_objective=True))
        ).state == "paused"
        assert coordinator.history == history and coordinator.evidence == evidence
        assert store.incidents() == records and store.incidents(unresolved_only=True)
        assert len(model.calls) == 2 and peer.seen == ["cst_connection_status"]
