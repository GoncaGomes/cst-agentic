"""Explicitly synthetic evaluation adapters; never import CST or load credentials."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from agents.testing import ScriptedModel, assistant_message, function_call
from mcp.types import CallToolResult, Tool

from .campaign import CampaignLedger
from .context_budget import ContextBudget, adapter_identity
from .controller import ControllerSession
from .discovery import APPROVED_MCP_TOOLS
from .evaluation import CampaignModel, run_trial
from .evaluation_pack import Trial, pack_identity, pack_manifest
from .mcp_client import CstMcpClient, McpCallError
from .recovery import RecoveryError, RecoveryStore
from .recovery_cli import run_local_recovery
from .working_project import WorkingProject, interpret_setup_response


def controlled_catalogue() -> tuple[Tool, ...]:
    """Synthetic schemas, not evidence of provider/native canonical compatibility."""
    return tuple(
        Tool(
            name=name,
            description="Controlled fixture only; not native CST evidence.",
            input_schema={"type": "object"},
        )
        for name in sorted(APPROVED_MCP_TOOLS)
    )


class ControlledPeer:
    """Stateful fake at the external SDK boundary, not an alternative Controller."""

    def __init__(self, root: Path, *, uncertain: bool = False):
        self.root = root.resolve()
        self.path: Path | None = None
        self.sequence = 0
        self.uncertain = uncertain
        self.calls: list[str] = []
        self.effects: list[dict[str, Any]] = []
        self.live_path: Path | None = None

    async def call_tool(self, name, arguments, *, meta=None):
        if meta is None:
            raise ValueError("Controlled Controller metadata is required.")
        self.calls.append(name)
        stage = meta["cst_controller"]["stage"]
        self.sequence += 1
        if name in {"cst_create_project", "cst_open_project"}:
            path = Path(arguments["path"]).resolve()
            if not path.is_relative_to(self.root):
                raise ValueError("Controlled path must remain inside the isolated fixture.")
            if name == "cst_create_project":
                path.write_text("Synthetic project, never CST data.", encoding="utf-8")
            self.path = self.live_path = path
        if name in {"cst_create_cylinder", "cst_set_parameter"}:
            self.effects.append({"operation": name, "arguments": dict(arguments)})
        if self.uncertain and name == "cst_set_parameter":
            raise RuntimeError("Controlled post-effect transport failure")
        evidence = {"version": 1, "stage": stage, "sequence": self.sequence}
        if stage != "probe":
            evidence["connection"] = "controlled-owned-instance"
        if self.live_path is not None:
            evidence.update(
                path=str(self.live_path),
                project="controlled-held-project",
                source="held-project.filename",
            )
        return CallToolResult(
            content=[],
            structured_content={
                "status": "ok",
                "controller": evidence,
                "units": "mm",
                "effects": self.effects,
            },
        )

    def observations(self) -> dict[str, Any]:
        return {
            "source": "controlled-peer-state, not response echo or native evidence",
            "effects": list(self.effects),
            "live_path": str(self.live_path),
            "units": "mm",
        }


class ControlledClient(CstMcpClient):
    def __init__(self, peer: ControlledPeer):
        super().__init__(Path("unused"), Path.cwd(), {}, 1, 1, 1)
        self.peer = peer

    async def __aenter__(self):
        self._session = self.peer
        return self

    async def __aexit__(self, *args):
        self._session = None
        return False


@asynccontextmanager
async def controlled_session(store: RecoveryStore, peer: ControlledPeer):
    working = WorkingProject()
    client = ControlledClient(peer)
    async with ControllerSession(
        store,
        lambda: client,
        inventory=APPROVED_MCP_TOOLS,
        dispatch_check=working.check,
        working_project=working,
    ) as session:
        await session.open_manual_transport()
        yield session, working, client


def _say(text: str):
    return [assistant_message(json.dumps({"text": text, "new_objective": None}))]


def _call(name: str, arguments: dict, call_id: str):
    return [function_call(name, arguments, call_id=call_id)]


def _launch_steps():
    return [
        _call("cst_connection_status", {}, "probe"),
        _call("discover_tools", {"groups": ["session_project"]}, "session-tools"),
        _call("cst_connect", {"mode": "new"}, "launch"),
        _say("Controlled launch without a selected project."),
    ]


def offline_context() -> ContextBudget:
    return ContextBudget(
        input_capacity=100_000,
        headroom=4_000,
        validation_reference="offline synthetic only; not endpoint admission",
        endpoint="https://example.invalid",
        model="scripted-offline",
        adapter=adapter_identity(),
    )


def _interpreters():
    return {
        name: interpret_setup_response
        if name
        in {"cst_connection_status", "cst_connect", "cst_create_project", "cst_open_project"}
        else lambda result: (
            result.structured_content is not None
            and result.structured_content.get("status") == "ok"
        )
        for name in APPROVED_MCP_TOOLS
    }


async def uncertainty_continuation(
    state: Path,
    peer: ControlledPeer,
    client: ControlledClient,
    project: Path,
    other: Path,
    ledger: CampaignLedger,
) -> tuple[dict[str, bool], list[dict[str, Any]]]:
    """Synthetic human findings through the same local CLI path, no transport there."""
    checks: dict[str, bool] = {}
    with RecoveryStore(state).session() as store:
        incidents = store.incidents(unresolved_only=True)
        checks["incident_retained"] = len(incidents) == 1 and incidents[0].state == "uncertain"
        incident_id = incidents[0].id
    constructed = []

    def forbidden_factory():
        constructed.append(True)
        return ControlledClient(peer)

    # Fresh objects/new chat, A, B and spelling aliases cannot erase central state.
    for label, path in (
        ("A", project),
        ("B", other),
        ("alias", project.parent / ".." / project.parent.name / project.name),
    ):
        refused = False
        try:
            async with ControllerSession(
                RecoveryStore(state),
                forbidden_factory,
                inventory=APPROVED_MCP_TOOLS,
                dispatch_check=lambda *args: None,
            ) as fresh:
                await fresh.start_task(path, "Fresh chat; explicit request")
        except RecoveryError:
            refused = True
        checks[f"restart_{label}_blocked"] = refused
    notes = project.parent / "decision-notes.md"
    notes.write_text("Synthetic discussion, not recovery authority.", encoding="utf-8")
    notes.unlink()
    with RecoveryStore(state).session() as store:
        checks["deleted_notes_do_not_clear_incident"] = bool(store.incidents(unresolved_only=True))
    checks["replacement_factory_never_called_before_reconciliation"] = not constructed
    before = len(peer.calls)
    result = run_local_recovery(
        "reconcile", incident_id, store=RecoveryStore(state), read_input=lambda prompt: "yes"
    )
    checks["local_reconciliation_without_calls"] = result == 0 and len(peer.calls) == before
    try:
        await client.call_tool("cst_connection_status", {})
    except McpCallError:
        checks["old_client_blocked_after_reconciliation"] = len(peer.calls) == before
    else:
        checks["old_client_blocked_after_reconciliation"] = False
    # Fresh session still has no selected target and cannot dispatch a parameter edit.
    fresh_peer = ControlledPeer(project.parent.parent)
    async with controlled_session(RecoveryStore(state), fresh_peer) as (session, working, _):
        try:
            await session.dispatch("cst_set_parameter", {"name": "patch_l", "value": 30})
        except RecoveryError:
            checks["fresh_session_requires_prerequisites"] = not fresh_peer.calls
        else:
            checks["fresh_session_requires_prerequisites"] = False
        # Real coordinator, explicit fresh task, normal launch/open prerequisites.
        model = CampaignModel(
            ScriptedModel(
                _launch_steps()
                + [
                    _call("cst_open_project", {"path": str(project)}, "fresh-open"),
                    _call("discover_tools", {"groups": ["parameters"]}, "fresh-parameters"),
                    _call("cst_set_parameter", {"name": "patch_l", "value": 30}, "fresh-edit"),
                    _say("Controlled new task completed; no native effect claim."),
                ]
            ),
            ledger,
        )
        from .conversation import ConversationCoordinator
        from .evaluation_pack import variant_discovery

        coordinator = ConversationCoordinator(
            model=model,
            connection=session,
            store=session.store,
            discovery=variant_discovery(controlled_catalogue(), "baseline"),
            allowlist=APPROVED_MCP_TOOLS,
            context_budget=offline_context(),
            request_admission=lambda request: None,
            interpreters=_interpreters(),
        )
        await coordinator.submit("Open CST")
        reply = await coordinator.submit(f"Open {project} and set patch_l to 30 mm, no save/run.")
        checks["fresh_prerequisites_then_dispatch"] = (
            reply.state == "reply"
            and working.binding is not None
            and fresh_peer.calls[-1] == "cst_set_parameter"
        )
        # A central settled record is not proof the live target has stayed valid.
        fresh_peer.live_path = other
        # Direct controlled call checks response interpretation against held live state.
        response = await session.dispatch("cst_project_info", {}, settled=working.accept)
        checks["central_state_does_not_prove_live_target"] = session.paused and not working.valid
        checks["live_state_evidence_retained"] = response.structured_content is not None
    return checks, model.requests


async def run_offline_smoke(directory: Path) -> dict[str, Any]:
    """Two tracer trials, not 132 behavioral trials or acceptance certification."""
    directory.mkdir(parents=True, exist_ok=False)
    ledger = CampaignLedger.create(
        directory / "campaign.sqlite3", identity="offline:" + pack_identity()
    )
    records = []
    for case_id in (1, 10):
        root = directory / f"scenario-{case_id}"
        root.mkdir()
        a, b = root / "A", root / "B"
        a.mkdir()
        b.mkdir()
        project, other = a / "project.cst", b / "other.cst"
        if case_id == 10:
            project.write_text("Controlled solved fixture, not CST.", encoding="utf-8")
        paths = {"project": str(project.resolve()), "other_project": str(other.resolve())}
        steps = _launch_steps() + [
            _call(
                "cst_create_project" if case_id == 1 else "cst_open_project",
                {"path": paths["project"]},
                "select",
            ),
            _say("Controlled target selected."),
        ]
        if case_id == 1:
            steps += [
                _call("discover_tools", {"groups": ["materials_basic"]}, "materials"),
                _call("cst_load_material", {"name": "PEC", "library_name": "PEC"}, "pec"),
                _call("discover_tools", {"groups": ["geometry_basic"]}, "geometry"),
                _call(
                    "cst_create_cylinder",
                    {
                        "radius": 5,
                        "height": 10,
                        "axis": "z",
                        "center": [0, 0, 0],
                        "material": "PEC",
                    },
                    "cylinder",
                ),
                _say("Controlled cylinder effect recorded; no native verification."),
                _call("cst_project_info", {}, "healthy-followup"),
                _say("Same healthy session/project; no extra launch."),
            ]
        else:
            steps += [
                _call("discover_tools", {"groups": ["parameters"]}, "parameters"),
                _call("cst_set_parameter", {"name": "patch_l", "value": 30}, "uncertain-edit"),
            ]
        peer = ControlledPeer(root, uncertain=case_id == 10)
        state = root / "central-state"
        async with controlled_session(RecoveryStore(state), peer) as (session, _, client):
            record = await run_trial(
                Trial("comparison", case_id, 1, "baseline"),
                model=ScriptedModel(steps),
                connection=session,
                catalogue=controlled_catalogue(),
                ledger=ledger,
                context_budget=offline_context(),
                paths=paths,
                interpreters=_interpreters(),
                controlled_observations=peer.observations,
                injected_call_ids=frozenset({"uncertain-edit"}) if case_id == 10 else frozenset(),
            )
            if case_id == 10:
                before = len(peer.calls)
                try:
                    await client.call_tool("cst_connection_status", {})
                except McpCallError:
                    record["evidence"]["old-client-direct-block"] = len(peer.calls) == before
        if case_id == 10:
            active = ledger.begin_active()
            try:
                checks, requests = await uncertainty_continuation(
                    state, peer, client, project.resolve(), other.resolve(), ledger
                )
                record["evidence"]["recovery-continuation"] = checks
                record["evidence"]["continuation-requests"] = requests
                record["requests"].extend(requests)
                record["latencies_s"].extend(r["latency_s"] for r in requests)
            finally:
                ledger.end_active(active)
        record["evidence_layer"] = "offline-only"
        records.append(record)
    report = {
        "evidence_layer": "offline-only",
        "acceptance": "incomplete",
        "records": records,
        "ledger": ledger.snapshot(),
        "pack_identity": pack_identity(),
    }
    for name, data in (("manifest.json", pack_manifest()), ("records.json", report)):
        with (directory / name).open("x", encoding="utf-8") as target:
            json.dump(data, target, indent=2)
    return report
