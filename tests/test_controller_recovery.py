"""Exercise the shared safety seam with the real protected client and store."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any

import pytest
from mcp.types import CallToolResult, TextContent

from cst_agentic.controller import ControllerSession, DispatchEvidence
from cst_agentic.mcp_client import CstMcpClient, McpCallError
from cst_agentic.project_storage import ProjectLocation, ProjectStorageError
from cst_agentic.recovery import RecoveryError, RecoveryStore


class Peer:
    def __init__(self, store: RecoveryStore) -> None:
        self.store = store
        self.seen: list[str] = []
        self.fail = False
        self.error = False

    async def call_tool(self, name: str, arguments: Any) -> CallToolResult:
        # Inspect actual durable bytes, not a mocked persistence method.
        data = json.loads((self.store.directory / "recovery.json").read_text(encoding="utf-8"))
        assert data["incidents"][-1]["state"] == "in_flight"
        assert "arguments" not in data["incidents"][-1]
        self.seen.append(name)
        if self.fail:
            raise RuntimeError("synthetic transport failure")
        return CallToolResult(
            content=[TextContent(type="text", text="received")], is_error=self.error
        )


class Client(CstMcpClient):
    def __init__(self, peer: Peer) -> None:
        super().__init__(Path("unused"), Path.cwd(), {}, 1, 1, 1)
        self.peer = peer
        self.starts = 0

    async def __aenter__(self) -> Client:
        self.starts += 1
        self._session = self.peer
        return self

    async def __aexit__(self, *args: Any) -> bool:
        self._session = None
        return False


def location(tmp_path: Path, name: str = "a") -> Path:
    directory = tmp_path / name
    directory.mkdir(exist_ok=True)
    return directory / f"{name}.cst"


def session(store: RecoveryStore, client: Client, **kwargs: Any) -> ControllerSession:
    return ControllerSession(
        store,
        lambda: client,
        inventory=frozenset({"edit", "status", "stop", "save"}),
        dispatch_check=lambda *args: DispatchEvidence("pid123-created456"),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_persist_before_sdk_and_finalize_without_raw_arguments(tmp_path: Path) -> None:
    store = RecoveryStore(tmp_path / "state")
    peer = Peer(store)
    client = Client(peer)
    async with session(store, client) as controller:
        await controller.start_task(location(tmp_path), "Explicit synthetic task")
        await controller.dispatch(
            "edit", {"private_value": "not-for-the-ledger"}, settled=lambda r: True
        )
        assert store.incidents(unresolved_only=True) == ()
        assert "not-for-the-ledger" not in (store.directory / "recovery.json").read_text()
        assert peer.seen == ["edit"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["fsync", "replace"])
async def test_write_failure_refuses_sdk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    store = RecoveryStore(tmp_path / "state")
    peer = Peer(store)
    client = Client(peer)
    async with session(store, client) as controller:
        await controller.start_task(location(tmp_path), "Edit")

        def refuse(*args: Any) -> None:
            raise OSError("raw storage detail is not surfaced")

        monkeypatch.setattr(os, failure, refuse)
        with pytest.raises(McpCallError, match="guard refused"):
            await controller.dispatch("edit", {})
        assert peer.seen == []
        assert client.attempts[0].dispatched is False


@pytest.mark.asyncio
async def test_uncertainty_retains_block_and_old_latch_after_human_reconciliation(
    tmp_path: Path,
) -> None:
    store = RecoveryStore(tmp_path / "state")
    peer = Peer(store)
    peer.fail = True
    client = Client(peer)
    path = location(tmp_path)
    async with session(store, client) as controller:
        await controller.start_task(path, "Edit")
        with pytest.raises(McpCallError):
            await controller.dispatch("edit", {})
        incident = store.incidents(unresolved_only=True)[0]
        assert incident.state == "uncertain"
        for name in ("status", "stop"):
            with pytest.raises(RecoveryError, match="paused"):
                await controller.dispatch(name, {})
        store.reconcile(
            incident.id,
            project_confirmed=True,
            effects_resolved=True,
            activity_resolved=True,
            instance_closed=True,
        )
        with pytest.raises(RecoveryError, match="fresh explicit task"):
            await controller.dispatch("edit", {})
        with pytest.raises(McpCallError, match="uncertain"):
            await client.call_tool("status", {})
        assert peer.seen == ["edit"]
    # Reconciliation alone dispatched nothing. A fresh explicit task can start
    # with a different healthy client and re-established checks.
    fresh = Client(Peer(store))
    async with session(store, fresh) as controller:
        assert fresh.starts == 0
        await controller.start_task(path, "Fresh status request")
        await controller.dispatch("status", {}, settled=lambda r: True)


@pytest.mark.asyncio
async def test_compound_persistence_failure_survives_protected_guard(tmp_path, monkeypatch):
    store = RecoveryStore(tmp_path / "state")
    client = Client(Peer(store))
    async with session(store, client) as controller:
        await controller.start_task(location(tmp_path), "Edit")

        def refuse(*args, **kwargs):
            raise OSError("private filesystem detail")

        with monkeypatch.context() as patch:
            patch.setattr(os, "replace", refuse)
            patch.setattr(Path, "unlink", refuse)
            with pytest.raises(ExceptionGroup) as caught:
                await controller.dispatch("edit", {})
        assert [str(error) for error in caught.value.exceptions] == [
            "Recovery persistence failed; dispatch is blocked.",
            "Recovery temporary-file cleanup failed.",
        ]
        assert not client.peer.seen and not client.attempts[-1].dispatched


@pytest.mark.asyncio
async def test_received_failure_is_not_transport_uncertainty(tmp_path: Path) -> None:
    store = RecoveryStore(tmp_path / "state")
    peer = Peer(store)
    peer.error = True
    client = Client(peer)
    async with session(store, client) as controller:
        await controller.start_task(location(tmp_path), "Edit")
        result = await controller.dispatch("edit", {}, settled=lambda r: False)
        assert result.is_error
        assert client.attempts[0].state == "received"
        assert store.incidents(unresolved_only=True)[0].state == "received_unresolved"
        assert client._uncertain is False
        with pytest.raises(RecoveryError, match="paused"):
            await controller.dispatch("save", {})


@pytest.mark.asyncio
async def test_bounded_healthy_readback_preserves_original_failure(tmp_path: Path) -> None:
    store = RecoveryStore(tmp_path / "state")
    peer = Peer(store)
    client = Client(peer)
    async with session(store, client, readback_inventory=frozenset({"status"})) as controller:
        await controller.start_task(location(tmp_path), "Edit")
        await controller.dispatch("edit", {}, settled=lambda r: False)
        original = store.incidents(unresolved_only=True)[0]
        await controller.readback("status", {}, settled=lambda r: True)
        assert store.incidents(unresolved_only=True) == (original,)
        with pytest.raises(RecoveryError, match="unavailable"):
            await controller.readback("status", {}, settled=lambda r: True)
        with pytest.raises(RecoveryError, match="paused"):
            await controller.dispatch("save", {})
        assert peer.seen == ["edit", "status"]


@pytest.mark.asyncio
async def test_task_completion_keeps_transport_open_and_needs_fresh_request(tmp_path: Path) -> None:
    store = RecoveryStore(tmp_path / "state")
    client = Client(Peer(store))
    path = location(tmp_path)
    async with session(store, client) as controller:
        await controller.start_task(path, "First task")
        await controller.dispatch("edit", {}, settled=lambda r: True)
        controller.finish_task()
        assert client._session is not None
        with pytest.raises(RecoveryError):
            await controller.dispatch("edit", {})
        await controller.start_task(path, "Fresh explicit task")
        assert client.starts == 1
        await controller.dispatch("status", {}, settled=lambda r: True)
        assert len({r.task_id for r in store.incidents()}) == 2


@pytest.mark.asyncio
async def test_unresolved_instance_blocks_other_folder_before_transport(tmp_path: Path) -> None:
    store = RecoveryStore(tmp_path / "state")
    a, b = location(tmp_path), location(tmp_path, "b")
    with store.session():
        store.prepare(str(uuid.uuid4()), "edit", ProjectLocation.inspect(a), "pid123-created456")
    client = Client(Peer(store))
    async with session(store, client) as controller:
        with pytest.raises(RecoveryError, match="reconciliation"):
            await controller.start_task(b, "B")
        assert client.starts == 0
        assert client.peer.seen == []


@pytest.mark.asyncio
async def test_guard_budget_expiry_after_persistence_is_not_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time

    store = RecoveryStore(tmp_path / "state")
    client = Client(Peer(store))
    async with session(store, client) as controller:
        await controller.start_task(location(tmp_path), "Edit")
        prepare = store.prepare

        def slow_prepare(*args: Any) -> str:
            record_id = prepare(*args)
            time.sleep(0.03)
            return record_id

        monkeypatch.setattr(store, "prepare", slow_prepare)
        with pytest.raises(McpCallError, match="budget"):
            await controller.dispatch("edit", {}, timeout_s=0.01)
        assert client.peer.seen == []
        assert store.incidents()[0].state == "settled"
        assert client.attempts[0].dispatched is False


@pytest.mark.asyncio
async def test_settlement_write_failure_keeps_restart_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = RecoveryStore(tmp_path / "state")
    peer = Peer(store)
    client = Client(peer)
    async with session(store, client) as controller:
        await controller.start_task(location(tmp_path), "Edit")
        original_call = peer.call_tool

        async def fail_after_response(*args: Any, **kwargs: Any) -> CallToolResult:
            result = await original_call(*args, **kwargs)

            def refuse(*args: Any) -> None:
                raise OSError("synthetic storage failure")

            monkeypatch.setattr(os, "replace", refuse)
            return result

        monkeypatch.setattr(peer, "call_tool", fail_after_response)
        with pytest.raises(RecoveryError, match="persistence failed"):
            await controller.dispatch("edit", {}, settled=lambda r: True)
        assert client.attempts[0].state == "received"
    with RecoveryStore(store.directory).session() as reopened:
        assert reopened.incidents(unresolved_only=True)[0].state == "in_flight"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["same", "unknown", "different"])
async def test_restart_central_reconciliation_before_transport(tmp_path: Path, kind: str) -> None:
    store = RecoveryStore(tmp_path / "state")
    a, b = location(tmp_path), location(tmp_path, "b")
    with store.session():
        incident_id = store.prepare(
            str(uuid.uuid4()),
            "edit",
            None if kind == "unknown" else ProjectLocation.inspect(a),
            "a-pid-created",
        )
    peer = Peer(store)
    client = Client(peer)
    async with session(store, client) as controller:
        with pytest.raises(RecoveryError, match="reconciliation"):
            await controller.start_task(a if kind == "same" else b, "Fresh task")
        assert client.starts == 0
        assert [r.id for r in store.incidents(unresolved_only=True)] == [incident_id]


@pytest.mark.asyncio
async def test_directory_and_save_checks_repeat_at_dispatch(tmp_path: Path) -> None:
    store = RecoveryStore(tmp_path / "state")
    client = Client(Peer(store))
    a = location(tmp_path)
    async with session(store, client) as controller:
        await controller.start_task(a, "Save A")
        with pytest.raises(McpCallError):
            await controller.dispatch("save", {}, save_destination=location(tmp_path, "b"))
        (a.parent / "second.cst").touch()
        with pytest.raises(McpCallError):
            await controller.dispatch("edit", {})
        assert client.peer.seen == []
    async with session(store, Client(Peer(store))) as controller:
        with pytest.raises(ProjectStorageError):
            await controller.start_task(a, "Open A")


@pytest.mark.asyncio
async def test_revocation_rechecked_after_queueing(tmp_path: Path) -> None:
    store = RecoveryStore(tmp_path / "state")
    client = Client(Peer(store))
    permitted = True

    def check(*args: Any) -> DispatchEvidence | None:
        return DispatchEvidence("pid-created") if permitted else None

    controller = ControllerSession(
        store,
        lambda: client,
        inventory=frozenset({"edit"}),
        dispatch_check=check,
    )
    async with controller:
        await controller.start_task(location(tmp_path), "Edit")
        await client._call_lock.acquire()
        pending = asyncio.create_task(controller.dispatch("edit", {}))
        await asyncio.sleep(0)
        permitted = False
        client._call_lock.release()
        with pytest.raises(McpCallError):
            await pending
        assert store.incidents() == ()
        assert client.peer.seen == []


@pytest.mark.asyncio
async def test_coordinator_queue_is_included_in_call_allowance(tmp_path: Path) -> None:
    store = RecoveryStore(tmp_path / "state")
    client = Client(Peer(store))
    entered = asyncio.Event()
    release = asyncio.Event()
    original_call = client.peer.call_tool

    async def waiting_call(*args: Any, **kwargs: Any) -> CallToolResult:
        entered.set()
        await release.wait()
        return await original_call(*args, **kwargs)

    client.peer.call_tool = waiting_call
    async with session(store, client) as controller:
        await controller.start_task(location(tmp_path), "Edit")
        active = asyncio.create_task(controller.dispatch("edit", {}, settled=lambda r: True))
        await entered.wait()
        try:
            with pytest.raises(RecoveryError, match="queue-inclusive"):
                await controller.dispatch("stop", {}, timeout_s=0.01)
        finally:
            release.set()
            await active
        assert client.peer.seen == ["edit"]
        assert len(client.attempts) == 1
