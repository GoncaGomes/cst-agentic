"""Campaign admission is durable across evaluator restarts."""

import pytest


def test_requests_tokens_and_safe_settlement_overshoot_survive_reopen(tmp_path):
    from cst_agentic.campaign import CampaignLedger, CampaignStopped

    path = tmp_path / "campaign.sqlite3"
    ledger = CampaignLedger.create(path, identity="controlled-campaign-v1")
    first = ledger.admit("probe")
    second = ledger.admit("trial")
    ledger.settle(first, total_tokens=499_990, latency_s=1.5)
    ledger.settle(second, total_tokens=25, latency_s=2)
    reopened = CampaignLedger.open(path, identity="controlled-campaign-v1")
    assert reopened.snapshot()["requests"] == 2
    assert reopened.snapshot()["reported_tokens"] == 500_015
    assert reopened.snapshot()["token_overshoot"] == 15
    with pytest.raises(CampaignStopped, match="token"):
        reopened.admit("trial")
    with pytest.raises(CampaignStopped, match="settled"):
        reopened.settle(first, total_tokens=0, latency_s=0)


def test_active_tool_wait_counts_but_scripted_human_wait_does_not(tmp_path):
    from cst_agentic.campaign import CampaignLedger, CampaignStopped

    now = [100.0]
    ledger = CampaignLedger.create(tmp_path / "ledger.db", identity="timing")
    ledger.clock = lambda: now[0]
    active = ledger.begin_active()
    now[0] += 7_199
    request = ledger.admit("trial")
    now[0] += 3
    ledger.settle(request, total_tokens=None, latency_s=3)
    ledger.end_active(active)
    assert ledger.snapshot()["active_seconds"] == 7_202
    assert ledger.snapshot()["active_overshoot_s"] == 2
    now[0] += 10_000  # waiting at a human prompt is outside the active interval
    assert ledger.snapshot()["active_seconds"] == 7_202
    with pytest.raises(CampaignStopped, match="active"):
        ledger.admit("engineering")


def test_request_probe_and_retest_allowances_are_shared_and_cannot_be_reset(tmp_path):
    from cst_agentic.campaign import CampaignLedger, CampaignStopped

    path = tmp_path / "ledger.db"
    ledger = CampaignLedger.create(path, identity="bounds")
    for _ in range(16):
        ledger.settle(ledger.admit("probe"), total_tokens=0, latency_s=0)
    with pytest.raises(CampaignStopped, match="probe"):
        ledger.admit("probe")
    ledger.claim_revision()
    reopened = CampaignLedger.open(path, identity="bounds")
    with pytest.raises(CampaignStopped, match="revision"):
        reopened.claim_revision()
    for _ in range(1_584):
        reopened.settle(reopened.admit("trial"), total_tokens=0, latency_s=0)
    with pytest.raises(CampaignStopped, match="request"):
        reopened.admit("retest")
    with pytest.raises(CampaignStopped):
        CampaignLedger.create(path, identity="reset")
    with pytest.raises(CampaignStopped, match="identity"):
        CampaignLedger.open(path, identity="other-model")


def test_missing_corrupt_or_interrupted_ledgers_fail_closed(tmp_path):
    from cst_agentic.campaign import CampaignLedger, CampaignStopped

    path = tmp_path / "ledger.db"
    with pytest.raises(CampaignStopped):
        CampaignLedger.open(path, identity="test")
    ledger = CampaignLedger.create(path, identity="test")
    ledger.admit("trial")  # interrupted after durable admission
    reopened = CampaignLedger.open(path, identity="test")
    assert reopened.snapshot()["pending_requests"] == 1
    with pytest.raises(CampaignStopped, match="unsettled"):
        reopened.admit("trial")
    path.write_text("invalid", encoding="utf-8")
    with pytest.raises(CampaignStopped):
        ledger.snapshot()


def test_trial_admission_cannot_replay_the_pack_or_expand_the_one_retest(tmp_path):
    from cst_agentic.campaign import CampaignLedger, CampaignStopped

    path = tmp_path / "ledger.db"
    ledger = CampaignLedger.create(path, identity="trials")
    ledger.claim_trial("comparison-1-1-baseline")
    with pytest.raises(CampaignStopped, match="trial"):
        CampaignLedger.open(path, identity="trials").claim_trial("comparison-1-1-baseline")
    with pytest.raises(CampaignStopped, match="frozen"):
        ledger.claim_trial("comparison-11-1-baseline")
    with pytest.raises(CampaignStopped, match="revision"):
        ledger.claim_trial("retest-1-1-baseline")
    ledger.claim_revision()
    ledger.claim_trial("retest-1-1-baseline")


@pytest.mark.asyncio
async def test_probe_model_boundary_accounts_active_time_and_actual_reported_usage(tmp_path):
    from agents import ModelSettings
    from agents.models.interface import ModelTracing
    from agents.testing import ScriptedModel, assistant_message

    from cst_agentic.campaign import CampaignLedger
    from cst_agentic.evaluation import CampaignModel

    now = [100.0]
    ledger = CampaignLedger.create(tmp_path / "ledger.db", identity="probe")
    ledger.clock = lambda: now[0]

    class Probe(ScriptedModel):
        async def get_response(self, *args, **kwargs):
            now[0] += 7
            return await super().get_response(*args, **kwargs)

    wrapped = CampaignModel(
        Probe([[assistant_message("Harmless controlled probe")]]), ledger, purpose="probe"
    )
    await wrapped.get_response(
        system_instructions="Probe",
        input="Harmless probe",
        model_settings=ModelSettings(),
        tools=[],
        output_schema=None,
        handoffs=[],
        tracing=ModelTracing.DISABLED,
        previous_response_id=None,
        conversation_id=None,
        prompt=None,
    )
    state = ledger.snapshot()
    assert state["active_seconds"] == 7
    assert state["requests"] == 1
    assert state["missing_usage"] == 1  # SDK default zeros are not actual usage evidence.
    assert not ledger.active


def test_interrupted_active_interval_keeps_elapsed_time_after_reopen(tmp_path):
    from cst_agentic.campaign import CampaignLedger, CampaignStopped

    path = tmp_path / "ledger.db"
    ledger = CampaignLedger.create(path, identity="interrupted")
    ledger.clock = lambda: 100.0
    interval = ledger.begin_active()
    reopened = CampaignLedger.open(path, identity="interrupted")
    reopened.clock = lambda: 200.0
    state = reopened.snapshot()
    assert state["active_intervals"] == [{"id": interval, "started_at": 100.0, "ended_at": None}]
    assert state["active_seconds"] == 100
    with pytest.raises(CampaignStopped, match="explicit settlement"):
        reopened.begin_active()
    reopened.end_active(interval)
    reopened.clock = lambda: 300.0
    assert reopened.snapshot()["active_seconds"] == 100
