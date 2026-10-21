"""THROWAWAY: exactly one admitted dipole solver-stop attempt, no model calls."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

import anyio
from jsonschema.validators import validator_for
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client
from windows_solver_stop_plan import (
    BAD,
    FIXTURE,
    INSTALL,
    LAUNCH,
    LOG,
    MAX_CALLS,
    MAX_SECONDS,
    RESERVE_SECONDS,
    REVISION,
    ROOT,
    STATUS,
    STOP,
    TARGET,
    UPSTREAM,
    WAIT,
    Sequence,
    allowance,
    digest,
    durable,
    prefix_plan,
    validate_approval,
    validate_new_root,
)
from windows_solver_stop_processes import Handle, snapshot

HERE = Path(__file__).resolve()
PEER = HERE.with_name("windows_solver_stop_peer.py")
ARTIFACT = HERE.parents[2] / "docs/prototypes/windows-solver-stop-evidence"
SOURCE_FILES = [
    HERE,
    PEER,
    HERE.with_name("windows_solver_stop_plan.py"),
    HERE.with_name("windows_solver_stop_processes.py"),
    HERE.with_name("windows_solver_stop_checks.py"),
]


def upstream_state() -> None:
    for args, expected in ((["rev-parse", "HEAD"], REVISION), (["status", "--porcelain"], "")):
        result = subprocess.run(
            ["git", *args], cwd=UPSTREAM, capture_output=True, text=True, check=True
        )
        if result.stdout.strip() != expected:
            raise RuntimeError("upstream_revision_or_cleanliness_changed")


def admit() -> tuple[dict, dict]:
    approval = json.loads((ARTIFACT / "authorization.json").read_text("utf-8"))
    validate_approval(approval)
    validate_new_root(ROOT)
    upstream_state()
    prepared = json.loads((ARTIFACT / "native-free-checks.json").read_text("utf-8"))
    sources = {p.name: digest(p) for p in SOURCE_FILES}
    if (
        prepared["source_sha256"] != sources
        or prepared["fixture_sha256"] != digest(FIXTURE)
        or prepared["passed"] is not True
    ):
        raise RuntimeError("sources_not_the_checked_versions")
    if prepared["catalogue_sha256"] != digest(ARTIFACT / "catalogue.json"):
        raise RuntimeError("checked_catalogue_changed")
    ROOT.mkdir()  # Exclusive admission: any previous directory blocks replay.
    (ROOT / "sources").mkdir()
    for path in [*SOURCE_FILES, FIXTURE]:
        shutil.copyfile(path, ROOT / "sources" / path.name)
    shutil.copyfile(ARTIFACT / "authorization.json", ROOT / "authorization.json")
    shutil.copyfile(ARTIFACT / "native-free-checks.json", ROOT / "native-free-checks.json")
    shutil.copyfile(ARTIFACT / "catalogue.json", ROOT / "catalogue.json")
    ledger = {
        "state": "in_flight",
        "target": str(TARGET),
        "tool_calls": 0,
        "maximum_calls": MAX_CALLS,
        "maximum_seconds": MAX_SECONDS,
        "source_sha256": sources,
        "fixture_sha256": digest(FIXTURE),
        "authorization_sha256": digest(ARTIFACT / "authorization.json"),
    }
    durable(ROOT / "round.json", ledger)
    return ledger, json.loads((ROOT / "catalogue.json").read_text("utf-8"))


class Dispatch:
    """Sole tools/call path, with queue-inclusive timeouts and a durable latch."""

    def __init__(
        self,
        session,
        ledger: dict,
        catalogue: dict,
        started: float,
        report: dict,
        root: Path = ROOT,
    ) -> None:
        self.session, self.ledger, self.catalogue = session, ledger, catalogue
        self.started, self.report, self.root = started, report, root
        self.lock = anyio.Lock()
        self.halted = False
        self.marker = root / "recovery.json"
        self.sequence = Sequence()
        self.wait_dispatched = anyio.Event()
        self.wait_settled = anyio.Event()

    def remaining(self) -> float:
        return MAX_SECONDS - (time.monotonic() - self.started)

    async def call(
        self, name: str, arguments: dict, *, skip_stop_if_finished: bool = False
    ) -> dict:
        admitted = time.monotonic()
        attempt = {
            "name": name,
            "requested": admitted,
            "state": "not_dispatched",
            "allowance_s": allowance(name),
        }
        self.report["attempts"].append(attempt)
        dispatched = False
        try:
            with anyio.fail_after(allowance(name)):
                async with self.lock:
                    if self.halted or self.marker.exists():
                        raise RuntimeError("latched_or_unresolved_client")
                    if (
                        skip_stop_if_finished
                        and (name, arguments) == STOP
                        and self.sequence.phase == "log"
                        and self.sequence.last_running is False
                    ):
                        attempt["reason"] = "natural_completion_before_stop_dispatch"
                        return {"status": "not_dispatched", "reason": attempt["reason"]}
                    self.sequence.check(name, arguments)
                    validator_for(self.catalogue[name])(self.catalogue[name]).validate(arguments)
                    if (
                        self.ledger["tool_calls"] >= MAX_CALLS
                        or self.remaining() < allowance(name) + RESERVE_SECONDS
                    ):
                        raise RuntimeError("insufficient_approved_budget")
                    if name == "fixture_create" and (self.root / "dipole.cst").exists():
                        raise RuntimeError("target_already_exists")
                    ordinal = self.ledger["tool_calls"] + 1
                    durable(
                        self.marker,
                        {
                            "state": "in_flight",
                            "operation": name,
                            "arguments": arguments,
                            "ordinal": ordinal,
                            "target": str(TARGET),
                        },
                    )
                    self.ledger["tool_calls"] = ordinal
                    durable(self.root / "round.json", self.ledger)
                    dispatched = True
                    attempt["dispatch"] = time.monotonic()
                    if name == WAIT[0]:
                        self.wait_dispatched.set()
                    response = await self.session.call_tool(name, arguments)
                    attempt["state"] = "received"
                    payload = response.structured_content
                    if not isinstance(payload, dict):
                        raise RuntimeError("missing_structured_response")
                    attempt["response"] = payload
                    if response.is_error or payload.get("status") in BAD:
                        raise RuntimeError("received_native_failure")
                    self.sequence.settled(name, payload)
                    # Keep an append-only settlement audit in addition to current marker.
                    with (self.root / "settlements.jsonl").open("a", encoding="utf-8") as stream:
                        stream.write(
                            json.dumps(
                                {
                                    "ordinal": ordinal,
                                    "operation": name,
                                    "state": "received",
                                    "monotonic": time.monotonic(),
                                }
                            )
                            + "\n"
                        )
                        stream.flush()
                        os.fsync(stream.fileno())
                    self.marker.unlink()
                    return payload
        except BaseException as error:
            self.halted = True
            if dispatched and attempt["state"] != "received":
                attempt["state"] = "uncertain"
            attempt["error_type"] = type(error).__name__
            if self.marker.exists():
                durable(
                    self.root / "incident.json",
                    {
                        "operation": name,
                        "state": attempt["state"],
                        "error_type": type(error).__name__,
                        "human_reconciliation_required": True,
                    },
                )
            raise
        finally:
            attempt["settled"] = time.monotonic()
            attempt["total_s"] = attempt["settled"] - admitted
            if "dispatch" in attempt:
                attempt["queue_s"] = attempt["dispatch"] - admitted
                attempt["dispatch_to_settlement_s"] = attempt["settled"] - attempt["dispatch"]
            if name == WAIT[0]:
                self.wait_settled.set()
            durable(self.root / "observations.json", self.report)


def track_chain(handles: dict, report: dict, pid: int) -> None:
    identity = json.loads((ROOT / "peer-identity.json").read_text("utf-8"))
    entries = snapshot()
    selected = {pid: "owned_CST_instance", identity["pid"]: "peer"}
    cursor = identity["pid"]
    for _ in range(10):
        cursor = entries[cursor]["parent_pid"]
        if cursor == os.getpid():
            break
        selected[cursor] = "launcher"
    else:
        raise RuntimeError("peer_chain_not_owned")
    for _ in range(10):
        extra = {
            p: "observed_descendant"
            for p, e in entries.items()
            if e["parent_pid"] in selected and p not in selected
        }
        if not extra:
            break
        selected.update(extra)
    for p, role in selected.items():
        if p not in handles:
            handle = Handle(p)
            handles[p] = handle
            report["processes"].append({**entries[p], "role": role, **handle.facts()})


async def queued_stop(gateway: Dispatch, report: dict) -> None:
    try:
        await gateway.wait_dispatched.wait()
        # Observe peer entry without native calls or a second transport.
        with anyio.fail_after(45):
            while not (gateway.root / "wait-entered.json").exists():
                if gateway.wait_settled.is_set():
                    report["queued_stop"] = "wait_settled_before_control_intent"
                    return
                await anyio.sleep(0.005)
        if gateway.wait_settled.is_set():
            report["queued_stop"] = "wait_settled_before_control_intent"
            return
        report["stop_intent"] = {"monotonic": time.monotonic(), "wait_pending": True}
        # Same lock; a naturally finished wait skips stop without latching/resetting.
        outcome = await gateway.call(*STOP, skip_stop_if_finished=True)
        if outcome.get("status") == "not_dispatched":
            report["queued_stop"] = "not_dispatched_after_natural_completion"
    except BaseException as error:
        # A failed/expired queued control must NOT cancel already-dispatched work.
        # The lifecycle owner raises only AFTER that work settles on its own deadline.
        gateway.halted = True
        report["stop_control_error_type"] = type(error).__name__


async def run() -> None:
    started = time.monotonic()
    ledger, catalogue = admit()
    report = {
        "target": str(TARGET),
        "attempts": [],
        "processes": [],
        "versions": {n: version(n) for n in ("mcp", "anyio")},
        "status": "in_flight",
        "human_reconciliation_required": True,
    }
    handles = {}
    cleanup_started = None
    de_pid = None
    caught = None
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv_missing")
    env = get_default_environment() | {
        "UV_OFFLINE": "1",
        "CST_PATH": str(INSTALL),
        "CST_VERSION": "2025",
        "CST_CONNECT_MODE": "manual",
        "CST_WORK_DIR": str(ROOT),
        "CST_ALLOW_RAW_VBA": "1",
        "CST_LOG_LEVEL": "CRITICAL",
    }
    params = StdioServerParameters(
        command=uv,
        args=[
            "run",
            "--offline",
            "--no-sync",
            "--project",
            str(UPSTREAM),
            "python",
            str(PEER),
            "--approved-peer",
        ],
        cwd=UPSTREAM,
        env=env,
    )
    try:
        # Same task owns both public contexts and their encompassing cancel scope.
        with anyio.fail_after(max(0.001, 100 - (time.monotonic() - started))) as lifecycle:
            with open(os.devnull, "w") as stderr:
                async with stdio_client(params, errlog=stderr) as (read, write):
                    async with ClientSession(read, write) as session:
                        try:
                            await session.initialize()
                            tools = (await session.list_tools()).tools
                            if {t.name: t.input_schema for t in tools} != catalogue:
                                raise RuntimeError("catalogue_changed")
                            report["startup_s"] = time.monotonic() - started
                            lifecycle.deadline = started + MAX_SECONDS - RESERVE_SECONDS
                            gateway = Dispatch(session, ledger, catalogue, started, report)
                            for name, arguments in prefix_plan():
                                payload = await gateway.call(name, arguments)
                                if name == "fixture_connect":
                                    de_pid = payload["de_pid"]
                                    track_chain(handles, report, de_pid)
                            await gateway.call(*LAUNCH)
                            for index in range(3):
                                status = await gateway.call(*STATUS)
                                if status.get("running") is True:
                                    break
                                if index < 2:
                                    await anyio.sleep(2)
                            if gateway.sequence.phase == "wait":
                                track_chain(handles, report, de_pid)
                                async with anyio.create_task_group() as group:
                                    group.start_soon(queued_stop, gateway, report)
                                    await gateway.call(*WAIT)
                                if gateway.halted:
                                    raise RuntimeError("stop_control_failed_after_wait_settlement")
                                if gateway.sequence.phase == "stop":
                                    # Do not manufacture evidence of queue overlap.
                                    report["queued_stop"] = (
                                        "no_overlap_observed_stop_sent_after_wait"
                                    )
                                    await gateway.call(*STOP)
                            if gateway.sequence.phase == "verifying":
                                for index in range(3):
                                    status = await gateway.call(*STATUS)
                                    if status.get("running") is False:
                                        report["independent_idle_observed"] = time.monotonic()
                                        report["CST_alive_at_idle_observation"] = handles[
                                            de_pid
                                        ].alive()
                                        break
                                    if index < 2:
                                        await anyio.sleep(2)
                            if gateway.sequence.phase != "log":
                                raise RuntimeError("solver_state_not_settled")
                            await gateway.call(*LOG)
                            report["alive_before_orderly_close"] = {
                                str(p): h.alive() for p, h in handles.items()
                            }
                            await gateway.call("fixture_close", {})
                            report["alive_after_orderly_close"] = {
                                str(p): h.alive() for p, h in handles.items()
                            }
                            report["status"] = (
                                "completed"
                                if "independent_idle_observed" in report
                                else "inconclusive_no_stop_verification"
                            )
                        finally:
                            cleanup_started = time.monotonic()
                            lifecycle.deadline = cleanup_started + min(
                                25, max(0.001, MAX_SECONDS - (cleanup_started - started) - 10)
                            )
                    report["session_exit_returned"] = time.monotonic()
                report["transport_exit_returned"] = time.monotonic()
        report["cleanup_s"] = report["transport_exit_returned"] - cleanup_started
        if report["cleanup_s"] > 25:
            raise RuntimeError("cleanup_allowance_exceeded")
    except BaseException as error:
        caught = error
        report["status"] = "blocked_reconciliation"
        report["error_type"] = type(error).__name__
        if cleanup_started is not None:
            report["cleanup_attempt_s"] = time.monotonic() - cleanup_started
    finally:
        # Even failed calls retain their evidence and receive a bounded OS-only observation.
        try:
            if de_pid is None and (ROOT / "launch-identity.json").is_file():
                de_pid = json.loads((ROOT / "launch-identity.json").read_text("utf-8"))["de_pid"]
                track_chain(handles, report, de_pid)
            boundary = time.monotonic()
            samples = []
            while handles:
                state = {str(p): h.alive() for p, h in handles.items()}
                samples.append(
                    {"after_observation_start_s": time.monotonic() - boundary, "alive": state}
                )
                if not any(state.values()) or time.monotonic() - boundary >= 5:
                    break
                await anyio.sleep(0.05)
            report["post_cleanup_samples"] = samples
            report["all_tracked_terminated"] = bool(handles) and not any(
                h.alive() for h in handles.values()
            )
            report["human_reconciliation_required"] = (
                caught is not None or not report["all_tracked_terminated"]
            )
        except BaseException as error:
            report["observation_error_type"] = type(error).__name__
            report["human_reconciliation_required"] = True
        finally:
            for handle in handles.values():
                handle.close()
            report["total_driver_s"] = time.monotonic() - started
            report["saved_fixture_exists"] = TARGET.is_file()
            ledger.update(
                state=report["status"],
                active_seconds=report["total_driver_s"],
                human_reconciliation_required=report["human_reconciliation_required"],
            )
            durable(ROOT / "observations.json", report)
            durable(ROOT / "round.json", ledger)
            print(
                json.dumps(
                    {
                        k: report.get(k)
                        for k in (
                            "status",
                            "error_type",
                            "total_driver_s",
                            "all_tracked_terminated",
                            "human_reconciliation_required",
                        )
                    }
                    | {"tool_calls": ledger["tool_calls"]}
                ),
                flush=True,
            )
    if caught is not None:
        raise RuntimeError("experiment_stopped_see_sanitized_evidence") from None


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        if sys.argv[1:] != ["--run-approved-once"]:
            raise RuntimeError("explicit_one_time_flag_required")
        anyio.run(run)
    except BaseException as error:
        print("Dipole experiment stopped: " + type(error).__name__, flush=True)
        sys.exit(1)
