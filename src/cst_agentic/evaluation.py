"""Injectable fixed-pack trial driver; no implicit endpoint or CST startup.

Callers supply the model, already-owned Controller session and controlled peer
adapters. Records retain complete logical requests and outcomes for independent
review. Never supply credential-bearing inputs to an evaluation fixture.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from agents import Model, ModelSettings
from mcp.types import Tool

from .campaign import CampaignLedger, CampaignStopped
from .context_budget import ContextBudget
from .controller import ControllerSession
from .conversation import ConversationCoordinator, ConversationEvent, ConversationReply
from .evaluation_pack import (
    VARIANTS,
    Checkpoint,
    Trial,
    checkpoints_for,
    pack_identity,
    scenario_for,
    variant_discovery,
)
from .mcp_client import McpToolCall


def reported_tokens(response: Any) -> int | None:
    """Missing provider usage must not become the SDK's default zero tokens."""
    raw = response.raw_usage
    value = raw.get("total_tokens") if isinstance(raw, dict) else None
    return value if type(value) is int and value >= 0 else None


@dataclass
class TrialTrace:
    """Append-only evaluation evidence, independent of model-context compaction."""

    evidence: dict[str, Any] = field(default_factory=dict)
    proposals: list[dict[str, Any]] = field(default_factory=list)
    dispatched: list[str] = field(default_factory=list)

    def observe(self, coordinator: ConversationCoordinator, event: ConversationEvent) -> None:
        if event.kind != "outcome":
            return
        # Outcome events occur immediately after the whole batch has been settled
        # and appended. Capture through the public seam before any compaction.
        for value in coordinator.history:
            item: dict[str, Any] = dict(value)
            if item.get("type") != "function_call_output" or item.get("call_id") != event.call_id:
                continue
            outcome = json.loads(item["output"])
            self.evidence[f"outcome-{event.call_id}"] = outcome
            if outcome["state"] in {"received", "uncertain"} and "selection" not in outcome:
                self.dispatched.append(item["call_id"])
            return
        raise ValueError("Settled outcome evidence was unavailable at the event boundary.")

    def retain_requests(self, requests: list[dict[str, Any]], injected: frozenset[str]) -> None:
        for request in requests:
            self.evidence[f"request-{request['ledger_request']}"] = deepcopy(request)
            for item in request["output"]:
                if item["type"] == "function_call":
                    call_id = item["call_id"]
                    self.proposals.append(
                        {"id": call_id, "name": item["name"], "injected": call_id in injected}
                    )
                    self.evidence[call_id] = deepcopy(item)


class CampaignModel(Model):
    """All probes/trials/retests must share this accounting boundary and ledger.

    No streaming or hidden retry path. The caller must configure its provider
    with max_retries=0; this wrapper cannot inspect arbitrary provider internals.
    """

    def __init__(self, model: Model, ledger: CampaignLedger, *, purpose: str = "trial"):
        self.model, self.ledger, self.purpose = model, ledger, purpose
        self.requests: list[dict[str, Any]] = []
        self.stopped = False

    async def get_response(self, *args: Any, **kwargs: Any):
        active = None
        try:
            if not self.ledger.active:
                active = self.ledger.begin_active()
            request = self.ledger.admit(self.purpose)
        except CampaignStopped:
            self.stopped = True
            if active is not None:
                self.ledger.end_active(active)
            raise
        # Preserve raw usage locally; this setting sends no extra model parameter.
        settings: ModelSettings = kwargs["model_settings"]
        kwargs["model_settings"] = settings.resolve(ModelSettings(preserve_raw_usage=True))
        record: dict[str, Any] = {
            "ledger_request": request,
            "instructions": kwargs.get("system_instructions"),
            "input": deepcopy(kwargs.get("input")),
            "provider_adapter": f"{type(self.model).__module__}.{type(self.model).__qualname__}",
            "model_settings": {
                "temperature": settings.temperature,
                "top_p": settings.top_p,
                "max_tokens": settings.max_tokens,
                "parallel_tool_calls": settings.parallel_tool_calls,
            },
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "schema": deepcopy(t.params_json_schema),
                    "strict": t.strict_json_schema,
                }
                for t in kwargs.get("tools", [])
            ],
            "output_schema": kwargs["output_schema"].json_schema()
            if kwargs.get("output_schema") is not None
            else None,
            "output": [],
            "reported_tokens": None,
            "state": "failed",
        }
        started = time.monotonic()
        self.requests.append(record)
        try:
            response = await self.model.get_response(*args, **kwargs)
            record.update(
                output=[item.model_dump(mode="json") for item in response.output],
                reported_tokens=reported_tokens(response),
                state="received",
            )
            return response
        finally:
            record["latency_s"] = time.monotonic() - started
            try:
                self.ledger.settle(
                    request, total_tokens=record["reported_tokens"], latency_s=record["latency_s"]
                )
            finally:
                if active is not None:
                    self.ledger.end_active(active)

    async def stream_response(self, *args: Any, **kwargs: Any):
        raise CampaignStopped("Campaign streaming is unsupported; use complete responses.")
        yield  # pragma: no cover - SDK abstract async-iterator interface


async def run_trial(
    trial: Trial,
    *,
    model: Model,
    connection: ControllerSession,
    catalogue: Sequence[Tool],
    ledger: CampaignLedger,
    context_budget: ContextBudget,
    paths: Mapping[str, str],
    interpreters: Mapping[str, Callable[[McpToolCall], bool]],
    controlled_observations: Callable[[], dict[str, Any]] = dict,
    injected_call_ids: frozenset[str] = frozenset(),
    checkpoint: Callable[[Checkpoint, ConversationReply, dict[str, Any]], bool | None]
    | None = None,
) -> dict[str, Any]:
    """Run the fixed ordinary messages, not user-authored manifests or tool JSON.

    Human input waits fall between active intervals. Controlled adapters may
    retain partial/uncertain effects; no outcome is graded here. Scenario 10's
    local-recovery continuation is a separate explicit offline driver.
    """
    case = scenario_for(trial.suite, trial.case_id)
    variant = next(v for v in VARIANTS if v.id == trial.variant)
    if trial.repetition not in {1, 2} or trial.suite not in {"comparison", "engineering", "retest"}:
        raise ValueError("Trial is outside the frozen pack.")
    if trial.suite != "comparison" and trial.variant != "baseline":
        raise ValueError("Engineering/retest trials use baseline only.")
    ledger.claim_trial(trial.id)
    wrapped = CampaignModel(
        model, ledger, purpose="trial" if trial.suite == "comparison" else trial.suite
    )
    trace = TrialTrace()
    messages = [message.format_map(paths) for message in case.messages]
    record: dict[str, Any] = {
        "trial_id": trial.id,
        "suite": trial.suite,
        "case_id": trial.case_id,
        "campaign_identity": ledger.identity,
        "pair": trial.pair,
        "pack_identity": pack_identity(),
        "variant": {
            "id": variant.id,
            "groups": len(variant.groups),
            "ceiling": variant.ceiling,
            "minimal_guidance": variant.minimal_guidance,
            "ceiling_guidance": variant.ceiling_guidance,
        },
        "evidence_layer": "controlled-adapters; model identity supplied by campaign manifest",
        "messages": messages,
        "evidence": trace.evidence,
        "proposals": trace.proposals,
        "dispatched": trace.dispatched,
        "requests": wrapped.requests,
        "complete": False,
        "budget_exhausted": False,
        "turn_latency_samples_s": [],
        "checkpoint_results": [],
        "requires_recovery_review": case.fixture in {"discovery_faults", "partial", "uncertain"},
    }
    coordinator = ConversationCoordinator(
        model=wrapped,
        connection=connection,
        store=connection.store,
        discovery=variant_discovery(catalogue, variant.id),
        allowlist=frozenset(t.name for t in catalogue),
        context_budget=context_budget,
        request_admission=lambda request: None,
        interpreters=interpreters,
        execution_admission=ledger.work_allowed,
        on_event=lambda event: trace.observe(coordinator, event),
    )
    checkpoints = checkpoints_for(trial.suite, trial.case_id)
    for index, (message, expected) in enumerate(zip(messages, checkpoints, strict=True), 1):
        try:
            active = ledger.begin_active()
        except CampaignStopped:
            record["budget_exhausted"] = True
            break
        try:
            started = time.monotonic()
            reply = await coordinator.submit(message)
            record["turn_latency_samples_s"].append(time.monotonic() - started)
            record["evidence"][f"turn-{index}"] = {
                "message": message,
                "text": reply.text,
                "state": reply.state,
                "events": [asdict(event) for event in reply.events],
            }
            observed = deepcopy(controlled_observations())
            record["evidence"][f"observations-{index}"] = observed
        finally:
            ledger.end_active(active)
        judgment = checkpoint(expected, reply, observed) if checkpoint is not None else None
        stage_matches = reply.state == expected.state and judgment is True
        record["checkpoint_results"].append(
            {"expected": asdict(expected), "passed": stage_matches, "judgment": judgment}
        )
        if wrapped.stopped:
            record["budget_exhausted"] = True
            break
        if not stage_matches:
            break  # Never advance scripted answers/permission through an unexpected stage.
    else:
        record["complete"] = True
    history: list[dict[str, Any]] = [dict(item) for item in coordinator.history]
    record["history"] = history
    trace.retain_requests(wrapped.requests, injected_call_ids)
    record["attempts"] = [asdict(attempt) for attempt in connection.attempts]
    record["incidents"] = [asdict(incident) for incident in connection.store.incidents()]
    record["evidence"]["attempts"] = deepcopy(record["attempts"])
    record["evidence"]["incidents"] = deepcopy(record["incidents"])
    record["latencies_s"] = [request["latency_s"] for request in wrapped.requests]
    record["active_trial_latency_s"] = sum(record["turn_latency_samples_s"])
    record["usage_available"] = bool(wrapped.requests) and all(
        request["reported_tokens"] is not None for request in wrapped.requests
    )
    record["budget_exhausted"] |= not ledger.work_allowed()
    return deepcopy(record)
