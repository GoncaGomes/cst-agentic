"""Native-free checks of this NEW harness; never starts a peer, CST or model."""

from __future__ import annotations

import ast
import inspect
import json
import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import anyio
import windows_solver_stop as driver
import windows_solver_stop_peer as peer
from windows_solver_stop import ARTIFACT, SOURCE_FILES, Dispatch, queued_stop, upstream_state
from windows_solver_stop_peer import event, safe_payload
from windows_solver_stop_plan import (
    FIXTURE,
    LAUNCH,
    MAX_CALLS,
    MAX_SECONDS,
    ROOT,
    STATUS,
    STOP,
    WAIT,
    Sequence,
    digest,
    durable,
    load_tools,
    prefix_plan,
    setup_plan,
    validate_approval,
    validate_new_root,
    validate_plan,
)


class Fake:
    def __init__(self, payload: dict | None = None, delay: float = 0) -> None:
        self.payload = payload or {"status": "ok"}
        self.delay = delay
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.delay:
            await anyio.sleep(self.delay)
        return SimpleNamespace(structured_content=self.payload, is_error=False)


def must_refuse(function, *args) -> None:
    try:
        function(*args)
    except RuntimeError:
        return
    raise AssertionError("guard_did_not_refuse")


async def checks() -> list[str]:
    passed = []
    tools, _ = load_tools()
    validate_plan(tools)
    assert len(setup_plan()) == 25 and len(prefix_plan()) == 29
    assert len(prefix_plan()) + 1 + 3 + 1 + 1 + 3 + 1 + 1 <= MAX_CALLS
    passed.append("literal fixture extraction, fixed manifest length and real upstream schemas")
    approval = json.loads((ARTIFACT / "authorization.json").read_text("utf-8"))
    validate_approval(approval)
    must_refuse(validate_approval, {**approval, "maximum_calls": 51})
    must_refuse(validate_approval, {**approval, "publication": True})
    passed.append("authorization rejects enlarged scope")

    with tempfile.TemporaryDirectory(
        prefix="solver-stop-guards-", dir=Path(os.environ["TEMP"]) / "opencode"
    ) as directory:
        base = Path(directory)
        must_refuse(validate_new_root, base)
        validate_new_root(base / "absent")
        passed.append("exclusive admission blocks replay/existing targets using private fixtures")
        old_root = peer.ROOT
        try:
            peer.ROOT = base
            event("operation_entered", operation="native-free-example")
            entry = json.loads((base / "peer-events.jsonl").read_text("utf-8"))
            assert entry["event"] == "operation_entered"
        finally:
            peer.ROOT = old_root
        passed.append("actual event write works in a private temporary fixture")
        catalogue = {name: tool.input_schema for name, tool in tools.items()}

        def gateway(label: str, session=None):
            root = base / label
            root.mkdir()
            ledger = {"state": "in_flight", "tool_calls": 0}
            return Dispatch(
                session or Fake(), ledger, catalogue, time.monotonic(), {"attempts": []}, root
            )

        async def refused(g: Dispatch, operation) -> None:
            try:
                await g.call(*operation)
            except RuntimeError:
                return
            raise AssertionError("dispatch_did_not_refuse")

        g = gateway("wrong-order")
        await refused(g, LAUNCH)
        assert not g.session.calls
        passed.append("fixed order blocks early launch and hidden operations")
        g = gateway("call-ceiling")
        g.ledger["tool_calls"] = MAX_CALLS
        await refused(g, ("fixture_connect", {}))
        assert not g.session.calls
        g = gateway("time-ceiling")
        g.started -= MAX_SECONDS - 100
        await refused(g, ("fixture_connect", {}))
        assert not g.session.calls
        passed.append("call/time admission reserves complete operation plus cleanup")
        g = gateway("existing-target")
        g.sequence.index = 1
        (g.root / "dipole.cst").write_text("private fixture", encoding="utf-8")
        await refused(g, ("fixture_create", {}))
        assert not g.session.calls
        passed.append("preexisting target is never overwritten")
        g = gateway("marker")
        durable(g.marker, {"state": "in_flight"})
        await refused(g, ("fixture_connect", {}))
        assert g.marker.exists() and not g.session.calls
        passed.append("durable unresolved marker blocks dispatch")
        g = gateway("marker-write-failure")
        original_durable = driver.durable

        def fail_marker(path, data):
            if path.name == "recovery.json":
                raise RuntimeError("synthetic_durable_write_failure")
            return original_durable(path, data)

        try:
            driver.durable = fail_marker
            await refused(g, ("fixture_connect", {}))
            assert not g.session.calls
        finally:
            driver.durable = original_durable
        passed.append("failed durable marker write prevents SDK dispatch")
        g = gateway("received-failure", Fake({"status": "error", "error_type": "Synthetic"}))
        await refused(g, ("fixture_connect", {}))
        assert g.marker.exists() and g.halted
        await refused(g, STATUS)
        await refused(g, STOP)
        assert len(g.session.calls) == 1
        passed.append("received failure retains marker and blocks dependent calls")

        g = gateway("uncertainty", Fake(delay=1))
        with anyio.move_on_after(0.02):
            await g.call("fixture_connect", {})
        assert g.halted and g.marker.exists() and g.report["attempts"][0]["state"] == "uncertain"
        await refused(g, STATUS)
        await refused(g, STOP)
        assert len(g.session.calls) == 1
        passed.append("synthetic interrupted attempt latches; no status/stop exception")

        class WaitFake(Fake):
            async def call_tool(self, name, arguments):
                self.calls.append((name, arguments))
                if name == WAIT[0]:
                    await anyio.sleep(0.04)
                    value = {"status": "running", "running": True}
                else:
                    value = {"status": "executed"}
                return SimpleNamespace(structured_content=value, is_error=False)

        g = gateway("queue", WaitFake())
        g.sequence.phase = "wait"

        async def stop_after_dispatch():
            await g.wait_dispatched.wait()
            await g.call(*STOP, skip_stop_if_finished=True)

        async with anyio.create_task_group() as group:
            group.start_soon(stop_after_dispatch)
            await g.call(*WAIT)
        assert g.session.calls == [WAIT, STOP]
        assert g.report["attempts"][1]["queue_s"] >= 0.02
        assert g.sequence.phase == "verifying"
        passed.append("queued stop waits for active request, without concurrent native dispatch")

        g = gateway("queued-expiry", WaitFake())
        g.sequence.phase = "wait"
        durable(g.root / "wait-entered.json", {"monotonic": time.monotonic()})
        original_allowance = driver.allowance
        try:
            driver.allowance = lambda name: 0.01 if name == STOP[0] else original_allowance(name)
            async with anyio.create_task_group() as group:
                group.start_soon(queued_stop, g, g.report)
                await g.call(*WAIT)
            assert g.halted and g.report["stop_control_error_type"] == "TimeoutError"
            assert g.report["attempts"][0]["state"] == "received"
            assert g.session.calls == [WAIT]
        finally:
            driver.allowance = original_allowance
        passed.append("queued stop expiry does not cancel an already-dispatched wait")

        g = gateway("natural-finish", Fake({"status": "finished", "running": False}))
        g.sequence.phase = "wait"
        await g.call(*WAIT)
        result = await g.call(*STOP, skip_stop_if_finished=True)
        assert result["status"] == "not_dispatched" and not g.halted and len(g.session.calls) == 1
        passed.append("natural completion skips stop without latch reset or relaunch")

        s = Sequence()
        s.phase = "verifying"
        for _ in range(2):
            s.check(*STATUS)
            s.settled(STATUS[0], {"status": "ok", "running": True})
        must_refuse(s.settled, STATUS[0], {"status": "ok", "running": True})
        s.phase = "close"
        must_refuse(s.check, "fixture_close", {})
        passed.append("finite verification and no close without observed idle")
        s = Sequence()
        s.phase = "starting"
        for _ in range(2):
            s.settled(STATUS[0], {"status": "ok", "running": False})
        must_refuse(s.settled, STATUS[0], {"status": "ok", "running": False})
        passed.append("unobserved async startup cannot be mistaken for settled completion")

    # Bind every event call without running it; catches the previous logging defect.
    tree = ast.parse(SOURCE_FILES[1].read_text("utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "event"
        ):
            inspect.signature(event).bind(
                *([None] * len(node.args)), **{kw.arg: None for kw in node.keywords}
            )
    assert safe_payload(
        {"status": "error", "message": "do-not-retain", "cst_dialogs": "foreign"}
    ) == {"status": "error", "failure_category": "received_upstream_failure"}
    passed.append("event binding and raw-error/dialog output filtering")
    return passed


if __name__ == "__main__":
    upstream_state()
    # Live experiment state is not created or modified by checks.
    if ROOT.exists():
        raise RuntimeError("native_free_check_not_to_be_replayed_after_live_admission")
    results = anyio.run(checks)
    tools, _ = load_tools()
    durable(ARTIFACT / "catalogue.json", {n: t.input_schema for n, t in tools.items()})
    baseline = {}
    old = SOURCE_FILES[0].parents[2]
    for p in [
        *list((old / "docs/prototypes").glob("windows-lifetime*.md")),
        *list((old / "docs/prototypes/windows-lifetime-native-evidence").rglob("*")),
        old / "src/cst_agentic/windows_lifetime_native.py",
        old / "src/cst_agentic/windows_lifetime_native_peer.py",
        Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-native\round.json"),
    ]:
        if p.is_file():
            baseline[str(p)] = digest(p)
    durable(ARTIFACT / "prior-evidence-sha256.json", baseline)
    durable(
        ARTIFACT / "native-free-checks.json",
        {
            "passed": True,
            "checks": results,
            "source_sha256": {p.name: digest(p) for p in SOURCE_FILES},
            "fixture_sha256": digest(FIXTURE),
            "catalogue_sha256": digest(ARTIFACT / "catalogue.json"),
            "CST_or_peer_started": False,
            "endpoint_requests": 0,
        },
    )
    print(
        json.dumps(
            {"passed": len(results), "prepared_maximum_tool_calls": 40, "live_state_created": False}
        )
    )
