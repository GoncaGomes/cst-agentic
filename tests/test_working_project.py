"""Selected-task admission through the terminal-shared coordinator and real client."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from agents.testing import ScriptedModel, function_call
from mcp.types import CallToolResult

from cst_agentic.controller import ControllerSession
from cst_agentic.conversation import ConversationCoordinator
from cst_agentic.mcp_client import CstMcpClient
from cst_agentic.recovery import RecoveryStore


class Peer:
    def __init__(self):
        self.calls = []
        self.sequence = 0

    async def call_tool(self, name, arguments, *, meta=None):
        self.calls.append((name, arguments, meta))
        context = meta["cst_controller"]
        stage = context["stage"]
        self.sequence += 1
        evidence = {"version": 1, "stage": stage, "sequence": self.sequence}
        if stage != "probe":
            evidence["connection"] = "controlled-owned-connection"
        if stage in {"select", "bound"}:
            Path(context["path"]).touch()
            evidence.update(
                path=context["path"],
                project="controlled-live-project",
                source="held-project.filename",
            )
        return CallToolResult(
            content=[], structured_content={"status": "ok", "controller": evidence}
        )


class Client(CstMcpClient):
    def __init__(self, peer):
        super().__init__(Path("unused"), Path.cwd(), {}, 1, 1, 1)
        self.peer = peer

    async def __aenter__(self):
        self._session = self.peer
        return self

    async def __aexit__(self, *args):
        self._session = None
        return False


@asynccontextmanager
async def selected(
    tmp_path, *, consequences=(), operations=None, peer=None, action="create", model=None, tools=()
):
    from cst_agentic.working_project import WorkingProject

    working = WorkingProject()
    peer = peer or Peer()
    store = RecoveryStore(tmp_path / "state")
    names = {
        "cst_connection_status",
        "cst_connect",
        "cst_create_project",
        "cst_open_project",
        "cst_save_project",
        "cst_delete_results",
        "cst_run_simulation_async",
        "cst_export_cad",
        "cst_export_structure_views",
    }
    async with ControllerSession(
        store,
        lambda: Client(peer),
        inventory=frozenset(names),
        dispatch_check=working.check,
        working_project=working,
    ) as session:
        from fakes import offline_context_budget

        coordinator = ConversationCoordinator(
            model=model or ScriptedModel([]),
            connection=session,
            store=store,
            tools=tools,
            allowlist=frozenset(names),
            request_admission=lambda request: None,
            context_budget=offline_context_budget(),
            interpreters={
                "cst_save_project": lambda result: result.structured_content["status"] == "ok"
            },
        )
        instruction = {
            "path": str(tmp_path / "exact.cst"),
            "action": action,
            "launch_new": True,
            "outcome": "Agreed controlled task",
            "changes": "Only the supplied exact operations",
            "consequences": list(consequences),
            "operations": operations or [{"name": "cst_save_project", "arguments": {}}],
        }
        reply = await coordinator.submit("task: " + json.dumps(instruction))
        yield coordinator, session, working, peer, reply


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,consequence",
    [
        ("cst_save_project", "save"),
        ("cst_run_simulation_async", "run_simulation"),
        ("cst_delete_results", "delete_results"),
    ],
)
async def test_exact_operation_does_not_implicitly_grant_distinct_consequence(
    tmp_path, name, consequence
):
    from cst_agentic.mcp_client import McpCallError

    async with selected(tmp_path, operations=[{"name": name, "arguments": {}}]) as (
        _,
        session,
        _,
        peer,
        reply,
    ):
        assert reply.state == "reply"
        with pytest.raises(McpCallError, match="guard refused"):
            await session.dispatch(name, {}, settled=lambda result: True)
        assert len(peer.calls) == 3


@pytest.mark.asyncio
async def test_agreed_operation_is_not_permission_to_repeat_it(tmp_path):
    from cst_agentic.mcp_client import McpCallError

    async with selected(tmp_path, consequences=("save",)) as (_, session, _, peer, reply):
        assert reply.state == "reply"
        await session.dispatch("cst_save_project", {}, settled=lambda result: True)
        with pytest.raises(McpCallError, match="guard refused"):
            await session.dispatch("cst_save_project", {}, settled=lambda result: True)
        assert len(peer.calls) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["permission", "target", "connection", "file"])
async def test_invalidation_while_queued_blocks_dependent_dispatch_and_stale_evidence(
    tmp_path, change
):
    from cst_agentic.mcp_client import McpCallError
    from cst_agentic.recovery import RecoveryError

    entered, release = asyncio.Event(), asyncio.Event()

    class BlockingPeer(Peer):
        async def call_tool(self, name, arguments, *, meta=None):
            if name == "cst_save_project":
                entered.set()
                await release.wait()
            return await super().call_tool(name, arguments, meta=meta)

    async with selected(tmp_path, consequences=("save",), peer=BlockingPeer()) as (
        _,
        session,
        working,
        peer,
        reply,
    ):
        assert reply.state == "reply"
        first = asyncio.create_task(
            session.dispatch("cst_save_project", {}, settled=lambda r: True)
        )
        await entered.wait()
        queued = asyncio.create_task(
            session.dispatch("cst_save_project", {}, settled=lambda r: True)
        )
        await asyncio.sleep(0)
        if change == "permission":
            working.invalidate()
        elif change == "target":
            from dataclasses import replace

            working.binding = replace(working.binding, project="different-live-project")
        elif change == "connection":
            working.connection = "different-connection"
        else:
            replacement = tmp_path / "replacement.tmp"
            replacement.write_text("replacement")
            replacement.replace(tmp_path / "exact.cst")
        release.set()
        await first
        with pytest.raises((RecoveryError, McpCallError)):
            await queued
        assert len(peer.calls) == 4
        assert session.paused
        assert session.store.incidents(unresolved_only=True)


@pytest.mark.asyncio
async def test_open_refuses_hard_link_alias_before_any_transport_work(tmp_path):
    import os

    source = tmp_path / "outside"
    source.mkdir()
    (source / "other.cst").write_text("native-placeholder")
    os.link(source / "other.cst", tmp_path / "exact.cst")
    async with selected(tmp_path, action="open") as (_, _, _, peer, reply):
        assert reply.state == "paused"
        assert not peer.calls


@pytest.mark.asyncio
async def test_exact_existing_project_opens_with_live_connection_binding(tmp_path):
    (tmp_path / "exact.cst").write_text("controlled-existing-project")
    async with selected(tmp_path, action="open") as (_, _, working, peer, reply):
        assert reply.state == "reply"
        assert peer.calls[-1][0] == "cst_open_project"
        assert working.binding.connection == "controlled-owned-connection"
        assert working.binding.provenance == "held-project.filename"
        assert working.binding.sequence == 3
        assert "uninspected" in reply.text


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["path", "connection", "source", "sequence", "missing"])
async def test_wrong_or_missing_actual_readback_blocks_setup_without_save(tmp_path, change):
    class ChangedPeer(Peer):
        async def call_tool(self, name, arguments, *, meta=None):
            result = await super().call_tool(name, arguments, meta=meta)
            if name == "cst_create_project":
                data = result.structured_content
                if change == "missing":
                    del data["controller"]
                else:
                    data["controller"][change] = {
                        "path": str(tmp_path / "fallback.cst"),
                        "connection": "other-connection",
                        "source": "requested-path-cache",
                        "sequence": 1,
                    }[change]
            return result

    async with selected(tmp_path, peer=ChangedPeer()) as (_, session, working, peer, reply):
        assert reply.state == "paused"
        assert session.paused and not working.valid
        assert len(peer.calls) == 3
        assert len(session.store.incidents(unresolved_only=True)) == 1


@pytest.mark.asyncio
async def test_model_work_reuses_gateway_schema_and_final_protected_boundary(tmp_path):
    from mcp.types import Tool

    from fakes import conversation_message

    model = ScriptedModel(
        [
            [function_call("cst_save_project", {}, call_id="save-exact")],
            [
                conversation_message(
                    "Save response received; native effects not independently verified."
                )
            ],
        ]
    )
    tool = Tool(
        name="cst_save_project",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    async with selected(tmp_path, consequences=("save",), model=model, tools=[tool]) as (
        coordinator,
        session,
        _,
        peer,
        reply,
    ):
        assert reply.state == "reply"
        result = await coordinator.submit("Perform the agreed save")
        assert result.state == "reply"
        assert peer.calls[-1][0] == "cst_save_project"
        assert session.attempts[-1].dispatched
        assert not session.store.incidents(unresolved_only=True)
        context = json.loads(model.calls[0].input[0]["content"])
        assert (
            context["working_project"]["selected_path"]
            == str((tmp_path / "exact.cst").resolve()).lower()
        )
        assert context["working_project"]["permission"]["consequences"] == ["save"]
        assert context["working_project"]["permission"]["remaining_operations"] == [
            {"name": "cst_save_project", "arguments": {}}
        ]
        assert context["working_project"]["binding"]["provenance"] == "held-project.filename"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["cst_export_cad", "cst_export_structure_views"])
async def test_unreviewed_export_overwrite_route_is_never_admitted(tmp_path, name):
    from cst_agentic.mcp_client import McpCallError

    async with selected(
        tmp_path,
        consequences=("overwrite",),
        operations=[{"name": name, "arguments": {"path": "existing-output"}}],
    ) as (_, session, _, peer, reply):
        assert reply.state == "reply"
        with pytest.raises(McpCallError, match="guard refused"):
            await session.dispatch(name, {"path": "existing-output"}, settled=lambda r: True)
        assert len(peer.calls) == 3


def test_typed_local_task_cannot_bypass_action_invariant(tmp_path):
    from cst_agentic.recovery import RecoveryError
    from cst_agentic.working_project import TaskPermission

    with pytest.raises(RecoveryError, match="create/open"):
        TaskPermission(
            str(tmp_path / "exact.cst"),
            "typo",
            True,
            "Outcome",
            "Changes",
            frozenset(),
            frozenset(),
        )


@pytest.mark.asyncio
async def test_detected_instance_conflict_stops_shared_coordinator_setup(tmp_path):
    class ConflictPeer(Peer):
        async def call_tool(self, name, arguments, *, meta=None):
            if name == "cst_connect":
                self.calls.append((name, arguments, meta))
                return CallToolResult(
                    content=[],
                    is_error=True,
                    structured_content={
                        "status": "error",
                        "message": "Detected existing CST instance; not closed.",
                    },
                )
            return await super().call_tool(name, arguments, meta=meta)

    async with selected(tmp_path, peer=ConflictPeer()) as (_, session, working, peer, reply):
        assert reply.state == "paused"
        assert session.paused and not working.valid
        assert [call[0] for call in peer.calls] == ["cst_connection_status", "cst_connect"]
        (incident,) = session.store.incidents(unresolved_only=True)
        assert incident.operation == "cst_connect" and incident.project is None
        assert session.attempts[-1].dispatched


@pytest.mark.asyncio
async def test_missing_protocol_probe_blocks_before_launch(tmp_path):
    class OldPeer(Peer):
        async def call_tool(self, name, arguments, *, meta=None):
            self.calls.append((name, arguments, meta))
            return CallToolResult(content=[], structured_content={"mode": "offline"})

    async with selected(tmp_path, peer=OldPeer()) as (_, session, _, peer, reply):
        assert reply.state == "paused"
        assert len(peer.calls) == 1
        assert session.paused


@pytest.mark.asyncio
async def test_explicit_task_creates_exact_target_and_admits_only_agreed_work(tmp_path):
    from cst_agentic.working_project import TaskPermission, WorkingProject

    path = tmp_path / "exact.cst"
    peer = Peer()
    working = WorkingProject()
    store = RecoveryStore(tmp_path / "state")
    inventory = frozenset(
        {"cst_connection_status", "cst_connect", "cst_create_project", "cst_save_project"}
    )
    async with ControllerSession(
        store,
        lambda: Client(peer),
        inventory=inventory,
        dispatch_check=working.check,
        working_project=working,
    ) as session:
        coordinator = ConversationCoordinator(
            model=ScriptedModel([]), connection=session, store=store
        )
        permission = TaskPermission.from_json(
            {
                "path": str(path),
                "action": "create",
                "launch_new": True,
                "outcome": "Create this exact project and save once later",
                "changes": "Initial empty project only",
                "consequences": ["save"],
                "operations": [{"name": "cst_save_project", "arguments": {}}],
            }
        )
        reply = await coordinator.establish_task(permission)
        assert reply.state == "reply"
        assert working.binding.path == str(path.resolve()).lower()
        await session.dispatch("cst_save_project", {}, settled=lambda result: True)
        assert [call[0] for call in peer.calls] == [
            "cst_connection_status",
            "cst_connect",
            "cst_create_project",
            "cst_save_project",
        ]
        assert not store.incidents(unresolved_only=True)
