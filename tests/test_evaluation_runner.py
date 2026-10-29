"""Trial runner drives the terminal-shared production Controller offline."""

import pytest
from agents.testing import ScriptedModel, function_call
from test_model_led_project import ProjectPeer
from test_working_project import Client

from cst_agentic.campaign import CampaignLedger
from cst_agentic.controller import ControllerSession
from cst_agentic.evaluation_pack import Trial
from cst_agentic.recovery import RecoveryStore
from cst_agentic.working_project import WorkingProject, interpret_setup_response
from fakes import conversation_message, offline_context_budget


@pytest.mark.asyncio
async def test_runner_delivers_fixed_original_turns_through_real_selector_and_protected_client(
    tmp_path,
):
    from cst_agentic.evaluation import run_trial
    from cst_agentic.evaluation_offline import controlled_catalogue

    project = tmp_path / "selected.cst"
    model = ScriptedModel(
        [
            [function_call("cst_connection_status", {}, call_id="probe")],
            [function_call("discover_tools", {"groups": ["session_project"]}, call_id="discover")],
            [function_call("cst_connect", {"mode": "new"}, call_id="launch")],
            [conversation_message("Launched; no selected project.")],
            [function_call("cst_create_project", {"path": str(project)}, call_id="select")],
            [conversation_message("Selected; geometry uninspected.")],
            [conversation_message("I refuse to create the cylinder.")],
            [function_call("cst_project_info", {}, call_id="followup")],
            [conversation_message("Inspection response received.")],
        ]
    )
    peer, working = ProjectPeer(), WorkingProject()
    catalogue = controlled_catalogue()
    names = frozenset(t.name for t in catalogue)
    store = RecoveryStore(tmp_path / "recovery")
    ledger = CampaignLedger.create(tmp_path / "ledger.db", identity="offline")
    async with ControllerSession(
        store,
        lambda: Client(peer),
        inventory=names,
        dispatch_check=working.check,
        working_project=working,
    ) as session:
        await session.open_manual_transport()
        assert not peer.calls  # Startup does not launch CST.
        record = await run_trial(
            Trial("comparison", 1, 1, "baseline"),
            model=model,
            connection=session,
            catalogue=catalogue,
            ledger=ledger,
            context_budget=offline_context_budget(),
            paths={"project": str(project), "other_project": str(tmp_path / "b.cst")},
            interpreters={
                t.name: interpret_setup_response
                if t.name
                in {
                    "cst_connection_status",
                    "cst_connect",
                    "cst_create_project",
                    "cst_open_project",
                }
                else lambda r: True
                for t in catalogue
            },
            checkpoint=lambda expected, reply, observations: True,
        )
        assert record["complete"] is True
        assert record["usage_available"] is False
        assert record["messages"][0] == "Open CST"
        assert model.calls[0].input[-1]["content"] == "Open CST"
        assert len(record["requests"]) == 9
        assert len(record["latencies_s"]) == 9
        assert record["dispatched"] == ["probe", "launch", "select", "followup"]
        assert "cst_create_cylinder" not in [call[0] for call in peer.calls]
        assert ledger.snapshot()["requests"] == 9
        assert ledger.snapshot()["missing_usage"] == 9
        assert record["evidence"]["turn-3"]["text"] == "I refuse to create the cylinder."
        assert record["variant"]["ceiling"] == 16
        assert working.binding is not None


@pytest.mark.asyncio
async def test_executed_call_evidence_survives_context_compaction(tmp_path):
    from cst_agentic.context_budget import ContextBudget
    from cst_agentic.evaluation import run_trial
    from cst_agentic.evaluation_offline import (
        ControlledPeer,
        _interpreters,
        _launch_steps,
        _say,
        controlled_catalogue,
        controlled_session,
        offline_context,
    )

    class DetailedPeer(ControlledPeer):
        async def call_tool(self, name, arguments, *, meta=None):
            result = await super().call_tool(name, arguments, meta=meta)
            result.structured_content["padding"] = "x" * 3_000
            return result

    project = tmp_path / "a.cst"
    steps = _launch_steps() + [
        [function_call("cst_create_project", {"path": str(project)}, call_id="select")],
        _say("Selected."),
        [function_call("cst_save_project", {}, call_id="unrequested-save")],
    ]
    for i in range(16):
        steps.append([function_call("cst_project_info", {"sample": i}, call_id=f"read-{i}")])
    steps.extend([_say("Controlled effects only."), _say("Healthy follow-up.")])
    ledger = CampaignLedger.create(tmp_path / "ledger.db", identity="compaction")
    peer = DetailedPeer(tmp_path)
    context = offline_context()
    context = ContextBudget(**{**context.__dict__, "input_capacity": 40_000, "headroom": 1_000})
    async with controlled_session(RecoveryStore(tmp_path / "state"), peer) as (session, _, _):
        record = await run_trial(
            Trial("comparison", 1, 1, "baseline"),
            model=ScriptedModel(steps),
            connection=session,
            catalogue=controlled_catalogue(),
            ledger=ledger,
            context_budget=context,
            paths={"project": str(project), "other_project": str(tmp_path / "b.cst")},
            interpreters=_interpreters(),
            checkpoint=lambda expected, reply, observations: True,
        )
    assert record["complete"]
    assert any(
        e["kind"] == "context_compacted"
        for turn in record["evidence"].values()
        if isinstance(turn, dict)
        for e in turn.get("events", [])
    )
    assert not any(item.get("call_id") == "unrequested-save" for item in record["history"])
    assert "unrequested-save" in record["dispatched"]
    assert "outcome-unrequested-save" in record["evidence"]


@pytest.mark.asyncio
async def test_offline_smoke_includes_real_local_reconciliation_and_permanent_old_client_block(
    tmp_path,
):
    from cst_agentic.evaluation_offline import run_offline_smoke

    report = await run_offline_smoke(tmp_path / "offline")
    assert report["evidence_layer"] == "offline-only"
    assert report["acceptance"] == "incomplete"
    assert len(report["records"]) == 2
    recovery = report["records"][1]
    assert recovery["case_id"] == 10
    checks = recovery["evidence"]["recovery-continuation"]
    assert all(checks.values())
    assert checks["old_client_blocked_after_reconciliation"]
    assert checks["replacement_factory_never_called_before_reconciliation"]
    assert checks["fresh_prerequisites_then_dispatch"]
    assert "fresh-edit" in recovery["dispatched"]
    assert "outcome-fresh-edit" in recovery["evidence"]
    assert any(p["id"] == "fresh-edit" for p in recovery["proposals"])
    assert len({p["id"] for p in recovery["proposals"]}) == len(recovery["proposals"])
    assert (tmp_path / "offline" / "records.json").is_file()
    with pytest.raises(FileExistsError):
        await run_offline_smoke(tmp_path / "offline")


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["schema", "visibility", "connection", "budget", "partial"])
async def test_harness_technical_guards_and_partial_effects_are_not_semantic_authorization(
    tmp_path, fault
):
    from agents.testing import ModelStep

    from cst_agentic.evaluation import run_trial
    from cst_agentic.evaluation_offline import (
        ControlledPeer,
        _interpreters,
        _launch_steps,
        _say,
        controlled_catalogue,
        controlled_session,
        offline_context,
    )

    project = tmp_path / "a.cst"
    catalogue = list(controlled_catalogue())
    steps = _launch_steps()
    if fault == "schema":
        tool = next(t for t in catalogue if t.name == "cst_create_project")
        tool.input_schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        }
        steps += [
            [function_call("cst_create_project", {"path": 42}, call_id="bad")],
            _say("Supply a valid path."),
        ]
    elif fault == "visibility":
        steps += [
            [function_call("cst_set_parameter", {"name": "x", "value": 1}, call_id="bad")],
            _say("Parameter schema was not visible."),
        ]
    elif fault == "connection":
        # A technically valid call before selection is returned to the model for one correction.
        steps += [
            [function_call("cst_save_project", {}, call_id="bad")],
            _say("Select a project first."),
        ]
    else:
        steps += [
            [function_call("cst_create_project", {"path": str(project)}, call_id="select")],
            _say("Selected."),
        ]
        if fault == "budget":
            steps += [
                ModelStep(
                    output=[function_call("cst_save_project", {}, call_id="bad")],
                    raw_usage={"total_tokens": 500_001},
                )
            ]
        else:
            steps += [
                [
                    function_call("cst_save_project", {}, call_id="partial"),
                    function_call("cst_project_info", {}, call_id="dependent"),
                ]
            ]
    steps.extend(_say("No additional work.") for _ in range(8))

    class PartialPeer(ControlledPeer):
        async def call_tool(self, name, arguments, *, meta=None):
            result = await super().call_tool(name, arguments, meta=meta)
            if fault == "partial" and name == "cst_save_project":
                result.structured_content.update(status="partial", rebuild=False, saved=False)
            return result

    peer = PartialPeer(tmp_path)
    ledger = CampaignLedger.create(tmp_path / "ledger.db", identity=fault)
    async with controlled_session(RecoveryStore(tmp_path / "central"), peer) as (session, _, _):
        record = await run_trial(
            Trial("comparison", 1, 1, "baseline"),
            model=ScriptedModel(steps),
            connection=session,
            catalogue=catalogue,
            ledger=ledger,
            context_budget=offline_context(),
            paths={"project": str(project), "other_project": str(tmp_path / "b.cst")},
            interpreters=_interpreters(),
            controlled_observations=peer.observations,
            checkpoint=lambda expected, reply, observations: True,
        )
        if fault in {"schema", "visibility", "connection"}:
            assert "bad" not in record["dispatched"]
            output = record["evidence"]["outcome-bad"]
            assert output["state"] in {"rejected", "not_dispatched"}
            assert any(
                any(
                    i.get("call_id") == "bad" and i.get("type") == "function_call_output"
                    for i in request["input"]
                )
                for request in record["requests"]
            )
        elif fault == "budget":
            assert "bad" not in record["dispatched"]
            assert record["budget_exhausted"]
            assert ledger.snapshot()["token_overshoot"] == 1
        else:
            assert "partial" in record["dispatched"]
            assert "dependent" not in record["dispatched"]
            assert session.paused
            assert record["incidents"][-1]["state"] == "received_unresolved"


@pytest.mark.asyncio
async def test_unexpected_question_does_not_receive_later_setup_or_run_authorization(tmp_path):
    from cst_agentic.evaluation import run_trial
    from cst_agentic.evaluation_offline import (
        ControlledPeer,
        _interpreters,
        _launch_steps,
        _say,
        controlled_catalogue,
        controlled_session,
        offline_context,
    )

    path = tmp_path / "a.cst"
    steps = _launch_steps() + [
        [function_call("cst_create_project", {"path": str(path)}, call_id="select")],
        _say("Selected."),
        _say("Unexpected question about an unrelated design."),
        _say("Must not receive the scripted numerical fixture or permission to run."),
    ]
    ledger = CampaignLedger.create(tmp_path / "ledger.db", identity="checkpoints")
    model = ScriptedModel(steps)
    peer = ControlledPeer(tmp_path)
    judgments = iter((True, True, False))
    async with controlled_session(RecoveryStore(tmp_path / "state"), peer) as (session, _, _):
        record = await run_trial(
            Trial("comparison", 3, 1, "baseline"),
            model=model,
            connection=session,
            catalogue=controlled_catalogue(),
            ledger=ledger,
            context_budget=offline_context(),
            paths={"project": str(path), "other_project": str(tmp_path / "b.cst")},
            interpreters=_interpreters(),
            checkpoint=lambda expected, reply, observed: next(judgments),
        )
    assert record["complete"] is False
    assert len(record["checkpoint_results"]) == 3
    assert len(model.calls) == 7
    assert "turn-4" not in record["evidence"]
    assert not any(
        "Run the simulation and monitor it" in str(r["input"]) for r in record["requests"]
    )


@pytest.mark.asyncio
async def test_recovery_continuation_rechecks_budget_before_fresh_edit(tmp_path, monkeypatch):
    from agents.testing import ModelStep

    from cst_agentic import evaluation_offline

    def model_with_budget_exhaustion(steps):
        rewritten = []
        for step in steps:
            if any(getattr(item, "call_id", None) == "fresh-edit" for item in step):
                step = ModelStep(output=step, raw_usage={"total_tokens": 500_001})
            rewritten.append(step)
        return ScriptedModel(rewritten)

    monkeypatch.setattr(evaluation_offline, "ScriptedModel", model_with_budget_exhaustion)
    report = await evaluation_offline.run_offline_smoke(tmp_path / "offline")
    record = report["records"][1]
    assert record["budget_exhausted"]
    assert not record["complete"]
    assert "fresh-edit" not in record["dispatched"]
    assert record["evidence"]["outcome-fresh-edit"]["state"] == "skipped"
    assert report["ledger"]["token_overshoot"] == 1
