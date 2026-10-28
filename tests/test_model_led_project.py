"""Model-led conversation through the real session, gateway and protected client.

The scripted model proves application integration, not Qwen instruction-following.
Only the external MCP session and model are controlled adapters.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from agents.testing import ScriptedModel, function_call
from mcp.types import CallToolResult, Tool
from test_working_project import Client

from cst_agentic.controller import ControllerSession
from cst_agentic.conversation import ConversationCoordinator, UserMessage
from cst_agentic.output_storage import interpret_export_response
from cst_agentic.recovery import RecoveryStore
from cst_agentic.working_project import WorkingProject, interpret_setup_response
from fakes import conversation_message, offline_context_budget


class ProjectPeer:
    """Canned typed server evidence, independent of requested target metadata."""

    def __init__(self):
        self.calls = []
        self.sequence = 0
        self.path = None

    async def call_tool(self, name, arguments, *, meta=None):
        self.calls.append((name, arguments, meta))
        stage = meta["cst_controller"]["stage"]
        self.sequence += 1
        evidence = {"version": 1, "stage": stage, "sequence": self.sequence}
        if stage != "probe":
            evidence["connection"] = "owned-connection"
        if name in {"cst_create_project", "cst_open_project"}:
            self.path = arguments["path"]
            Path(self.path).touch()
        if self.path:
            evidence.update(path=self.path, project="held-project", source="held-project.filename")
        return CallToolResult(
            content=[], structured_content={"status": "ok", "controller": evidence}
        )


def definition(name, properties=None, required=()):
    return Tool(
        name=name,
        input_schema={
            "type": "object",
            "properties": properties or {},
            "required": list(required),
            "additionalProperties": False,
        },
    )


TOOLS = (
    definition("cst_connection_status"),
    definition("cst_connect", {"mode": {"enum": ["new"]}}, ("mode",)),
    # Canonical, unmodified create/open/save schemas from the pinned companion.
    *(
        Tool.model_validate(value)
        for value in json.loads(
            (Path(__file__).parent / "fixtures" / "project_schemas.json").read_text(
                encoding="utf-8"
            )
        )["tools"]
    ),
    definition("cst_project_info"),
)


@asynccontextmanager
async def flow(tmp_path, steps, *, peer=None, tools=TOOLS, discovery=None):
    peer = peer or ProjectPeer()
    model = ScriptedModel(steps)
    working = WorkingProject()
    store = RecoveryStore(tmp_path / "state")
    client = Client(peer)
    names = frozenset(tool.name for tool in tools)
    async with ControllerSession(
        store,
        lambda: client,
        inventory=names,
        dispatch_check=working.check,
        working_project=working,
    ) as session:
        await session.open_manual_transport()
        coordinator = ConversationCoordinator(
            model=model,
            connection=session,
            store=store,
            tools=tools,
            discovery=discovery,
            allowlist=names,
            request_admission=lambda request: None,
            context_budget=offline_context_budget(),
            interpreters={
                **{name: lambda r: r.structured_content["status"] == "ok" for name in names},
                **dict.fromkeys(
                    (
                        "cst_connection_status",
                        "cst_connect",
                        "cst_create_project",
                        "cst_open_project",
                    ),
                    interpret_setup_response,
                ),
                **dict.fromkeys(
                    ("cst_export_cad", "cst_export_structure_views"), interpret_export_response
                ),
            },
        )
        yield coordinator, session, working, peer, model, client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message", ["Abre o CST, por favor.", "Lança uma nova instância.", "  Open CST.  "]
)
async def test_original_message_can_launch_without_intent_response_or_project(tmp_path, message):
    steps = [
        [function_call("cst_connection_status", {}, call_id="probe")],
        [function_call("cst_connect", {"mode": "new"}, call_id="launch")],
        [conversation_message("CST aberto; nenhum projeto selecionado.")],
    ]
    async with flow(tmp_path, steps) as (coordinator, session, working, peer, model, _):
        reply = await coordinator.submit(message)
        assert reply.state == "reply", reply.text
        assert model.calls[0].input[-1]["content"] == message
        assert [c[0] for c in peer.calls] == ["cst_connection_status", "cst_connect"]
        assert working.connection == "owned-connection" and working.binding is None
        assert not session.paused and not session.store.incidents(unresolved_only=True)
        assert peer.calls[-1][2]["cst_controller"]["path"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["create", "open"])
async def test_separate_selection_clarification_and_healthy_tasks_need_no_manifest(
    tmp_path, action
):
    path = tmp_path / "exact.cst"
    if action == "open":
        path.write_text("existing project")
    steps = [
        [function_call("cst_connection_status", {}, call_id="probe")],
        [function_call("cst_connect", {"mode": "new"}, call_id="launch")],
        [conversation_message("Nenhum projeto selecionado.")],
        [conversation_message("Qual é o caminho completo?")],
        [function_call(f"cst_{action}_project", {"path": str(path)}, call_id="select")],
        [conversation_message("Destino verificado; conteúdo ainda não inspecionado.")],
        [function_call("cst_project_info", {}, call_id="inspect")],
        [conversation_message("Inspeção recebida.")],
        [function_call("cst_save_project", {}, call_id="save")],
        [conversation_message("Gravação recebida.")],
    ]
    async with flow(tmp_path, steps) as (coordinator, session, working, peer, model, _):
        for message in (
            "Abre CST",
            "Quero selecionar um projeto",
            str(path),
            "Inspeciona o projeto",
            "Agora guarda o projeto",
        ):
            reply = await coordinator.submit(message)
            assert reply.state == "reply", reply.text
        assert [c[0] for c in peer.calls] == [
            "cst_connection_status",
            "cst_connect",
            f"cst_{action}_project",
            "cst_project_info",
            "cst_save_project",
        ]
        assert working.binding.path == str(path.resolve()).lower()
        assert not session.paused and not session.store.incidents(unresolved_only=True)
        assert all(any(i.get("content") == "Abre CST" for i in call.input) for call in model.calls)


def setup_steps(path):
    return [
        [function_call("cst_connection_status", {}, call_id="probe")],
        [function_call("cst_connect", {"mode": "new"}, call_id="launch")],
        [function_call("cst_create_project", {"path": str(path)}, call_id="select")],
    ]


@pytest.mark.asyncio
async def test_session_restriction_survives_healthy_objectives_or_pauses_before_context_loss(
    tmp_path,
):
    restriction = "For this entire session, never save or run a simulation."
    steps = setup_steps(tmp_path / "exact.cst") + [
        [conversation_message("Selected.")],
        [function_call("cst_project_info", {}, call_id="first-inspection")],
        [conversation_message("Inspection received.")],
        [conversation_message("Discussion noted.")],
        [function_call("cst_project_info", {}, call_id="later-inspection")],
        [conversation_message("Inspection received.")],
    ]
    async with flow(tmp_path, steps) as (coordinator, session, working, peer, model, _):
        assert (await coordinator.submit(restriction)).state == "reply"
        assert (
            await coordinator.submit(UserMessage("Inspect the project", new_objective=True))
        ).state == "reply"
        discussion = "Additional agreed discussion: " + "x" * 60_000
        assert (await coordinator.submit(discussion)).state == "reply"
        requests_before = len(model.calls)
        dispatches_before = len(peer.calls)
        reply = await coordinator.submit(
            UserMessage("Inspect again. Details: " + "y" * 15_000, new_objective=True)
        )

        # Retention is structural; the model need not declare or remember a rule.
        assert all(
            any(item.get("content") == restriction for item in request.input)
            for request in model.calls
        )
        assert any(item.get("content") == restriction for item in coordinator.history)
        assert any(item.get("content") == discussion for item in coordinator.history)
        if reply.state == "paused":
            assert any(event.kind == "context_pause" for event in reply.events)
            assert len(model.calls) == requests_before
            assert len(peer.calls) == dispatches_before
        else:
            assert reply.state == "reply"
            assert any(event.kind == "context_compacted" for event in reply.events)
        assert working.valid and working.binding is not None
        assert not session.paused and not session.store.incidents(unresolved_only=True)
        assert {call[0] for call in peer.calls} == {
            "cst_connection_status",
            "cst_connect",
            "cst_create_project",
            "cst_project_info",
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["cad", "views"])
async def test_reviewed_exports_dispatch_only_to_new_explicit_outputs(tmp_path, route):
    class ExportPeer(ProjectPeer):
        async def call_tool(self, name, arguments, *, meta=None):
            result = await super().call_tool(name, arguments, meta=meta)
            if name in {"cst_export_cad", "cst_export_structure_views"}:
                output.write_bytes(b"controlled artifact, not native CAD/image")
                if route == "cad":
                    result.structured_content.update(
                        status="executed", format="stp", exported_file=str(output)
                    )
                else:
                    result.structured_content["images"] = [
                        {"status": "executed", "exists": True, "path": str(output)}
                    ]
            return result

    output = tmp_path / ("part.stp" if route == "cad" else "view_front.png")
    name = "cst_export_cad" if route == "cad" else "cst_export_structure_views"
    arguments = (
        {"file_path": str(output), "format": "stp"}
        if route == "cad"
        else {"out_dir": str(tmp_path), "views": ["front"]}
    )
    tool = definition(name, {key: {} for key in arguments}, tuple(arguments))
    steps = setup_steps(tmp_path / "exact.cst") + [
        [function_call(name, arguments, call_id="export")],
        [conversation_message("Export response received, not content validation.")],
    ]
    async with flow(tmp_path, steps, tools=(*TOOLS, tool), peer=ExportPeer()) as (
        coordinator,
        session,
        _,
        peer,
        _,
        _,
    ):
        reply = await coordinator.submit("Create the project and export the requested view/CAD.")
        assert reply.state == "reply", reply.text
        assert peer.calls[-1][0] == name
        assert peer.calls[-1][1] == arguments
        assert not session.store.incidents(unresolved_only=True)


@pytest.mark.asyncio
async def test_recoverable_preselection_rejection_reaches_model_with_paired_history(tmp_path):
    steps = [
        [function_call("cst_connection_status", {}, call_id="probe")],
        [function_call("cst_connect", {"mode": "new"}, call_id="launch")],
        [function_call("cst_save_project", {}, call_id="premature")],
        [conversation_message("Escolhe primeiro o caminho exato do projeto.")],
    ]
    async with flow(tmp_path, steps) as (coordinator, session, _, peer, model, _):
        reply = await coordinator.submit("Abre CST e guarda o projeto")
        assert reply.text == "Escolhe primeiro o caminho exato do projeto."
        output = next(
            i
            for i in model.calls[-1].input
            if i.get("type") == "function_call_output" and i["call_id"] == "premature"
        )
        data = json.loads(output["output"])
        assert data["state"] == "not_dispatched"
        assert "select" in data["reason"].lower()
        assert [c[0] for c in peer.calls] == ["cst_connection_status", "cst_connect"]
        assert not session.paused


@pytest.mark.asyncio
async def test_one_correction_allowance_cannot_reset_by_changing_tool_or_arguments(tmp_path):
    steps = [
        [function_call("cst_connect", {"mode": "attach"}, call_id="bad-mode")],
        [function_call("cst_open_project", {}, call_id="different-bad-call")],
        [function_call("cst_connection_status", {}, call_id="must-not-run")],
    ]
    async with flow(tmp_path, steps) as (coordinator, _, _, peer, model, _):
        reply = await coordinator.submit("Abre uma instância nova")
        assert reply.state == "paused"
        assert len(model.calls) == 2
        assert not peer.calls
        assert [
            i["call_id"] for i in coordinator.history if i.get("type") == "function_call_output"
        ] == ["bad-mode", "different-bad-call"]


@pytest.mark.asyncio
async def test_a_canonical_rejection_can_be_corrected_to_successful_supported_setup(tmp_path):
    steps = [
        [function_call("cst_connect", {"mode": "existing"}, call_id="bad-mode")],
        *setup_steps(tmp_path / "exact.cst"),
        [conversation_message("Target verified.")],
    ]
    async with flow(tmp_path, steps) as (coordinator, session, working, peer, model, _):
        reply = await coordinator.submit("Launch a new instance and create the exact project")
        assert reply.state == "reply" and working.binding is not None and not session.paused
        assert len(peer.calls) == 3
        rejection = json.loads(
            next(
                i["output"] for i in model.calls[1].input if i.get("type") == "function_call_output"
            )
        )
        assert rejection["state"] == "rejected"
        context = json.loads(model.calls[-1].input[0]["content"])
        assert context["working_project"]["inspection_gaps"] == [
            "geometry",
            "units",
            "parameters",
            "solver/setup",
            "results",
        ]


@pytest.mark.asyncio
async def test_discovery_can_precede_launch_without_any_intent_declaration(tmp_path):
    from cst_agentic.discovery import GROUP_CATALOGUE, ToolDiscovery

    definitions = {tool.name: tool for tool in TOOLS}
    definitions.update(
        {
            name: definition(name)
            for name in GROUP_CATALOGUE["session_project"].members
            if name not in definitions
        }
    )
    catalogue = tuple(definitions.values())
    steps = [
        [function_call("discover_tools", {"groups": ["session_project"]}, call_id="discover")],
        *setup_steps(tmp_path / "exact.cst"),
        [conversation_message("Destino verificado, geometria e unidades por inspecionar.")],
    ]
    async with flow(tmp_path, steps, tools=catalogue, discovery=ToolDiscovery(catalogue)) as (
        coordinator,
        session,
        working,
        peer,
        model,
        _,
    ):
        message = "Não uses uma instância existente; abre CST e cria o ficheiro combinado."
        reply = await coordinator.submit(message)
        assert reply.state == "reply", reply.text
        assert model.calls[0].input[-1]["content"] == message
        assert {t.name for t in model.calls[0].tools} == {
            "discover_tools",
            "cst_connection_status",
            "cst_project_info",
        }
        assert "cst_create_project" in {t.name for t in model.calls[1].tools}
        assert working.binding is not None and not session.paused
        assert all(c[0] != "discover_tools" for c in peer.calls)
        assert [i["call_id"] for i in coordinator.history if i.get("type") == "function_call"] == [
            i["call_id"] for i in coordinator.history if i.get("type") == "function_call_output"
        ]


@pytest.mark.asyncio
async def test_create_conflict_returns_reason_then_a_new_message_can_choose_exact_destination(
    tmp_path,
):
    occupied = tmp_path / "occupied.cst"
    occupied.write_text("must not change")
    other = tmp_path / "other"
    other.mkdir()
    requested = other / "chosen.cst"
    steps = setup_steps(occupied) + [
        [conversation_message("Esse destino já existe. Qual é o outro caminho?")],
        [function_call("cst_create_project", {"path": str(requested)}, call_id="new-destination")],
        [conversation_message("Novo destino exato verificado.")],
    ]
    async with flow(tmp_path, steps) as (coordinator, session, working, peer, model, _):
        reply = await coordinator.submit("Cria o projeto no caminho ocupado")
        assert reply.state == "reply"
        assert occupied.read_text() == "must not change"
        assert len(peer.calls) == 2
        rejected = json.loads(
            next(
                i["output"]
                for i in model.calls[-1].input
                if i.get("type") == "function_call_output" and i["call_id"] == "select"
            )
        )
        assert "destination exists" in rejected["reason"].lower()
        reply = await coordinator.submit(str(requested))
        assert reply.state == "reply", reply.text
        assert peer.calls[-1][1]["path"] == str(requested)
        assert working.binding.path == str(requested.resolve()).lower()
        assert not session.paused


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["destination", "connection", "source", "sequence", "missing", "version"]
)
async def test_actual_readback_not_requested_path_or_model_assertion_establishes_binding(
    tmp_path, change
):
    class WrongPeer(ProjectPeer):
        async def call_tool(self, name, arguments, *, meta=None):
            result = await super().call_tool(name, arguments, meta=meta)
            if name == "cst_create_project":
                data = result.structured_content["controller"]
                if change == "missing":
                    del result.structured_content["controller"]
                elif change == "destination":
                    data["path"] = str(tmp_path / "fallback.cst")
                else:
                    data[change] = {
                        "connection": "unrelated",
                        "source": "requested-path-cache",
                        "sequence": 1,
                        "version": True,
                    }[change]
            return result

    steps = setup_steps(tmp_path / "exact.cst") + [
        [function_call("cst_save_project", {}, call_id="dependent-save")]
    ]
    async with flow(tmp_path, steps, peer=WrongPeer()) as (
        coordinator,
        session,
        working,
        peer,
        model,
        _,
    ):
        reply = await coordinator.submit("Create the exact project, then save it")
        assert reply.state == "paused" and session.paused and not working.valid
        assert len(model.calls) == 3 and len(peer.calls) == 3
        assert session.store.incidents(unresolved_only=True)[0].state == "received_unresolved"


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["cad", "views"])
@pytest.mark.parametrize(
    "conflict", ["existing", "directory", "missing-parent", "relative", "project"]
)
async def test_export_destination_conflicts_are_model_visible_and_never_dispatch(
    tmp_path, route, conflict
):
    output = tmp_path / "part.stp"
    directory = tmp_path
    if conflict == "existing":
        output.write_text("keep")
        (tmp_path / "view_front.png").write_text("keep")
    elif conflict == "directory":
        output.mkdir()
        (tmp_path / "view_front.png").mkdir()
    elif conflict == "missing-parent":
        directory = tmp_path / "missing"
        output = directory / "part.stp"
    elif conflict == "relative":
        directory = Path("relative-output")
        output = Path("part.stp")
    elif conflict == "project":
        output = tmp_path / "exact.cst"
        directory = tmp_path / "exact.cst"
    name = "cst_export_cad" if route == "cad" else "cst_export_structure_views"
    arguments = (
        {"file_path": str(output), "format": "stp"}
        if route == "cad"
        else {"out_dir": str(directory), "views": ["front"]}
    )
    tool = definition(name, {key: {} for key in arguments}, tuple(arguments))
    steps = setup_steps(tmp_path / "exact.cst") + [
        [function_call(name, arguments, call_id="unsafe-output")],
        [conversation_message("Escolhe outro destino de exportação.")],
    ]
    async with flow(tmp_path, steps, tools=(*TOOLS, tool)) as (
        coordinator,
        session,
        _,
        peer,
        model,
        _,
    ):
        reply = await coordinator.submit("Create the project and export")
        assert reply.text == "Escolhe outro destino de exportação."
        assert len(peer.calls) == 3 and not session.paused
        rejection = json.loads(
            next(
                i["output"]
                for i in model.calls[-1].input
                if i.get("type") == "function_call_output" and i["call_id"] == "unsafe-output"
            )
        )
        assert rejection["state"] == "not_dispatched"
        assert "Dispatch or durable settlement failed" not in rejection["reason"]


@pytest.mark.asyncio
async def test_output_created_while_waiting_on_real_client_queue_is_not_overwritten(tmp_path):
    entered, release = asyncio.Event(), asyncio.Event()

    class QueuePeer(ProjectPeer):
        async def call_tool(self, name, arguments, *, meta=None):
            if meta is None:
                entered.set()
                await release.wait()
                return CallToolResult(content=[])
            return await super().call_tool(name, arguments, meta=meta)

    output = tmp_path / "part.stp"
    arguments = {"file_path": str(output), "format": "stp"}
    tool = definition("cst_export_cad", {key: {} for key in arguments}, tuple(arguments))
    steps = setup_steps(tmp_path / "exact.cst") + [
        [conversation_message("Selected.")],
        [function_call("cst_export_cad", arguments, call_id="queued-export")],
        [conversation_message("Output appeared; choose another path.")],
    ]
    async with flow(tmp_path, steps, tools=(*TOOLS, tool), peer=QueuePeer()) as (
        coordinator,
        session,
        _,
        peer,
        _,
        client,
    ):
        assert (await coordinator.submit("Create the exact project")).state == "reply"
        # Occupy the public protected-client serialization seam, not an internal lock.
        blocker = asyncio.create_task(client.call_tool("cst_connection_status", {}))
        await entered.wait()
        turn = asyncio.create_task(coordinator.submit("Export CAD"))
        async with asyncio.timeout(5):
            while client.attempts[-1].name != "cst_export_cad":
                await asyncio.sleep(0)
        output.write_text("new external output; must not replace")
        release.set()
        await blocker
        reply = await turn
        assert reply.text == "Output appeared; choose another path."
        assert client.attempts[-1].state == "not_dispatched"
        assert output.read_text() == "new external output; must not replace"
        assert len(peer.calls) == 3 and not session.paused


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["instance", "protocol", "private"])
async def test_setup_failure_has_specific_sanitized_reason_and_blocks_dependent_work(
    tmp_path, failure
):
    class FailedPeer(ProjectPeer):
        async def call_tool(self, name, arguments, *, meta=None):
            if (failure == "protocol" and name == "cst_connection_status") or (
                failure != "protocol" and name == "cst_connect"
            ):
                self.calls.append((name, arguments, meta))
                return CallToolResult(
                    content=[],
                    is_error=True,
                    structured_content={
                        "status": "error",
                        "message": (
                            "CST must be closed; conflicting instance or unknown instance check."
                            if failure == "instance"
                            else "synthetic-private-vendor-data"
                        ),
                    },
                )
            return await super().call_tool(name, arguments, meta=meta)

    async with flow(tmp_path, setup_steps(tmp_path / "exact.cst"), peer=FailedPeer()) as (
        coordinator,
        session,
        _,
        peer,
        model,
        _,
    ):
        reply = await coordinator.submit("Create the project")
        assert reply.state == "paused" and session.paused
        rendered = reply.text + " ".join(event.text for event in reply.events)
        assert "synthetic-private" not in rendered
        assert ("instance conflict" if failure == "instance" else "readback") in rendered
        assert len(peer.calls) == (1 if failure == "protocol" else 2)
        assert (await coordinator.submit("Open project B")).state == "paused"
        assert len(model.calls) == len(peer.calls)


@pytest.mark.asyncio
async def test_not_dispatched_queued_selection_can_choose_another_exact_destination(tmp_path):
    entered, release = asyncio.Event(), asyncio.Event()

    class QueuePeer(ProjectPeer):
        async def call_tool(self, name, arguments, *, meta=None):
            if meta is None:
                entered.set()
                await release.wait()
                return CallToolResult(content=[])
            return await super().call_tool(name, arguments, meta=meta)

    path = tmp_path / "exact.cst"
    other = tmp_path / "other"
    other.mkdir()
    replacement = other / "chosen.cst"
    steps = setup_steps(path)[:2] + [
        [conversation_message("Launched, unselected.")],
        [function_call("cst_create_project", {"path": str(path)}, call_id="queued-select")],
        [conversation_message("Destination appeared; choose another path.")],
        [function_call("cst_create_project", {"path": str(replacement)}, call_id="new-select")],
        [conversation_message("New exact target verified.")],
    ]
    async with flow(tmp_path, steps, peer=QueuePeer()) as (
        coordinator,
        session,
        working,
        peer,
        _,
        client,
    ):
        assert (await coordinator.submit("Launch CST")).state == "reply"
        blocker = asyncio.create_task(client.call_tool("cst_connection_status", {}))
        await entered.wait()
        turn = asyncio.create_task(coordinator.submit("Create the project"))
        async with asyncio.timeout(5):
            while client.attempts[-1].name != "cst_create_project":
                await asyncio.sleep(0)
        path.write_text("external file; keep")
        release.set()
        await blocker
        assert (await turn).state == "reply"
        assert client.attempts[-1].state == "not_dispatched"
        reply = await coordinator.submit(str(replacement))
        assert reply.state == "reply", reply.text
        assert working.binding.path == str(replacement.resolve()).lower()
        assert len(peer.calls) == 3 and not session.paused
        assert path.read_text() == "external file; keep"


@pytest.mark.asyncio
async def test_current_destination_error_is_not_hidden_by_previous_selection_refusal(tmp_path):
    path = tmp_path / "occupied.cst"
    path.write_text("keep")
    steps = setup_steps(path)[:2] + [
        [function_call("cst_save_project", {}, call_id="premature")],
        [conversation_message("Select a project first.")],
        [function_call("cst_create_project", {"path": str(path)}, call_id="occupied")],
        [conversation_message("Choose an available destination.")],
    ]
    async with flow(tmp_path, steps) as (coordinator, _, _, peer, model, _):
        await coordinator.submit("Launch and save")
        reply = await coordinator.submit("Create at this exact path")
        assert reply.state == "reply"
        reason = json.loads(
            next(
                i["output"]
                for i in model.calls[-1].input
                if i.get("type") == "function_call_output" and i["call_id"] == "occupied"
            )
        )["reason"]
        assert "destination exists" in reason.lower()
        assert len(peer.calls) == 2 and path.read_text() == "keep"


@pytest.mark.asyncio
async def test_canonical_explicit_project_type_passes_the_real_selection_guard(tmp_path):
    steps = setup_steps(tmp_path / "exact.cst")
    arguments = {"path": str(tmp_path / "exact.cst"), "project_type": "MWS"}
    steps[-1] = [function_call("cst_create_project", arguments, call_id="typed-create")]
    steps.append([conversation_message("Exact target verified.")])
    async with flow(tmp_path, steps) as (coordinator, session, working, peer, _, _):
        reply = await coordinator.submit("Create the requested MWS project")
        assert reply.state == "reply" and working.binding is not None and not session.paused
        assert peer.calls[-1][1] == arguments
