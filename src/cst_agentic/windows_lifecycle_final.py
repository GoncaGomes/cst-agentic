"""THROWAWAY / NATIVE-FREE: four one-time lifecycle scenarios, <=300 seconds.

Only this file's fake application and fake JSON-RPC peer may be launched. No CST,
provider, dotenv, production client, private SDK state or arbitrary process kills.
All Python invocations use uv run. Existing experiment targets are never reused.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client
from windows_lifecycle_final_processes import ExactProcess, discover

STARTED = time.monotonic()
HERE = Path(__file__).resolve()
BRANCH = HERE.parents[2]
PROJECT = Path(r"C:\dev\cst-agentic")
ROOT = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifecycle-final-01")
ARCHIVE = BRANCH / "docs/prototypes/windows-lifecycle-final-evidence"
SOURCES = (HERE, HERE.with_name("windows_lifecycle_final_processes.py"))
CASES = ("crash_restart", "partial_startup_failure", "startup_timeout", "stalled_shutdown")
TOOLS = ("work", "status", "stop")
SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text("utf-8-sig"))


def durable(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".writing")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, allow_nan=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def event(scratch: Path, actor: str, kind: str, **facts) -> None:
    # Each actor owns its own file. Event metadata is fixed/synthetic, never raw errors.
    with (scratch / (actor + "-events.jsonl")).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": kind, "monotonic": time.monotonic(), **facts}) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def exception_types(error: BaseException) -> list[str]:
    result = [type(error).__name__]
    if isinstance(error, BaseExceptionGroup):
        for child in error.exceptions:
            result.extend(exception_types(child))
    return result


def environment() -> dict[str, str]:
    # No provider/config initialization or ambient environment dump.
    return get_default_environment() | {
        "UV_OFFLINE": "1",
        "UV_PROJECT_ENVIRONMENT": sys.prefix,
        "PYTHONUTF8": "1",
    }


def command(role: str, scratch: Path) -> list[str]:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv_missing")
    return [
        uv,
        "run",
        "--offline",
        "--no-sync",
        "--project",
        str(PROJECT),
        "python",
        str(HERE),
        role,
        str(scratch),
    ]


def validate_child(scratch: Path) -> str:
    if scratch.parent != ROOT or scratch.name not in CASES or not scratch.is_dir():
        raise RuntimeError("not_the_fixed_synthetic_target")
    ledger = read(ROOT / "round.json")
    if ledger["state"] != "in_flight" or ledger["source_sha256"][HERE.name] != sha(HERE):
        raise RuntimeError("not_the_admitted_sources")
    return scratch.name


def watchdog(scratch: Path, actor: str, seconds: float) -> None:
    """Self-exit only, with an exact scratch release flag. No external PID kills."""

    def watch() -> None:
        end = time.monotonic() + seconds
        release = "restart-release.flag" if actor == "restart" else "containment-release.flag"
        while time.monotonic() < end:
            if (scratch / release).exists():
                event(scratch, actor, "containment_release_self_exit")
                os._exit(90)
            time.sleep(0.025)
        event(scratch, actor, "watchdog_self_exit")
        os._exit(91)

    threading.Thread(target=watch, daemon=True).start()


def peer(scratch: Path) -> None:
    mode = validate_child(scratch)
    if (scratch / "peer-identity.json").exists():
        raise RuntimeError("peer_replay_forbidden")
    durable(scratch / "peer-identity.json", {"pid": os.getpid(), "parent_pid": os.getppid()})
    watchdog(scratch, "peer", 35)
    event(scratch, "peer", "ready")
    # Hold the fake server until the external observer has exact process handles.
    # This avoids losing fast failing-startup processes between observation samples.
    end = time.monotonic() + 10
    while not (scratch / "peer-observed.flag").exists():
        if time.monotonic() >= end:
            raise RuntimeError("external_peer_observation_not_established")
        time.sleep(0.01)
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method = request["method"]
        event(scratch, "peer", "request", method=method)
        response = {"jsonrpc": "2.0", "id": request["id"]}
        if method == "initialize":
            if mode == "partial_startup_failure":
                response["error"] = {"code": -32000, "message": "Synthetic initialization refusal"}
            else:
                if mode == "startup_timeout":
                    event(scratch, "peer", "initialization_stalled")
                    time.sleep(25)
                response["result"] = {
                    "protocolVersion": request["params"]["protocolVersion"],
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "THROWAWAY-NATIVE-FREE", "version": "0"},
                }
        elif method == "tools/list":
            response["result"] = {
                "tools": [
                    {"name": name, "description": "Synthetic only", "inputSchema": SCHEMA}
                    for name in TOOLS
                ]
            }
        elif method == "tools/call":
            name = request["params"]["name"]
            if mode != "crash_restart" or name != "work" or request["params"].get("arguments"):
                raise RuntimeError("unexpected_synthetic_operation")
            marker = read(scratch / "central-recovery.json")
            if marker != {"state": "in_flight", "operation": "work", "target": "synthetic-only"}:
                raise RuntimeError("missing_predispatch_record")
            durable(scratch / "work-entered.json", {"marker_verified_before_work": True})
            event(scratch, "peer", "work_entered_with_marker", operation=name)
            time.sleep(25)  # Application deliberately crashes before any response.
            response["result"] = {
                "content": [{"type": "text", "text": "synthetic result"}],
                "isError": False,
            }
        elif method == "ping":
            response["result"] = {}
        else:
            raise RuntimeError("unexpected_jsonrpc_method")
        print(json.dumps(response), flush=True)
    event(scratch, "peer", "stdin_eof")
    if mode == "stalled_shutdown":
        event(scratch, "peer", "refusing_orderly_exit")
        time.sleep(25)
    event(scratch, "peer", "normal_exit")


class Guard:
    """One protected dispatch route, one application-owned recovery location."""

    def __init__(self, scratch: Path, session=None) -> None:
        self.scratch, self.session = scratch, session
        self.marker = scratch / "central-recovery.json"
        self.lock = anyio.Lock()
        # Any retained/partial marker is a block; do not parse-and-forget malformed state.
        self.blocked = (
            self.marker.exists() or self.marker.with_name(self.marker.name + ".writing").exists()
        )

    async def call(self, name: str) -> dict:
        async with self.lock:
            if self.blocked:
                event(self.scratch, "restart", "blocked_before_dispatch", operation=name)
                return {
                    "operation": name,
                    "state": "not_dispatched",
                    "reconciliation_required": True,
                }
            if name != "work" or self.session is None:
                raise RuntimeError("outside_fixed_authorization")
            self.blocked = True
            durable(
                self.marker, {"state": "in_flight", "operation": name, "target": "synthetic-only"}
            )
            event(self.scratch, "app", "durable_marker_before_dispatch", operation=name)
            try:
                # Only tools/call site; no alternate status/stop route on restart.
                response = await self.session.call_tool(name, {})
            except BaseException:
                # Never clear an unresolved marker, even during context unwinding.
                raise
            durable(
                self.scratch / "settled.json", {"operation": name, "is_error": response.is_error}
            )
            self.marker.unlink()
            self.blocked = False
            return {"state": "received"}


@asynccontextmanager
async def observed_context(context, scratch: Path, report: dict, name: str):
    owner = anyio.get_current_task().id
    body_error = None
    entered = False
    try:
        async with context as resource:
            entered = True
            event(scratch, "app", "context_entered", context=name, task_id=owner)
            try:
                yield resource
            except BaseException as error:
                body_error = error
                raise
            finally:
                if "cleanup_started" not in report:
                    report["cleanup_started"] = time.monotonic()
                event(
                    scratch,
                    "app",
                    "context_exit_started",
                    context=name,
                    task_id=anyio.get_current_task().id,
                )
    except BaseException as error:
        report.setdefault("context_outcomes", []).append(
            {
                "context": name,
                "entered": entered,
                "owner_task_id": owner,
                "exit_task_id": anyio.get_current_task().id,
                "boundary_exception_types": exception_types(error),
                "body_exception_types": exception_types(body_error) if body_error else [],
                "same_exception_object_as_body": error is body_error,
            }
        )
        raise
    else:
        report.setdefault("context_outcomes", []).append(
            {
                "context": name,
                "entered": entered,
                "owner_task_id": owner,
                "exit_task_id": anyio.get_current_task().id,
                "boundary_exception_types": [],
            }
        )
    finally:
        event(
            scratch,
            "app",
            "context_boundary_finished",
            context=name,
            entered=entered,
            task_id=anyio.get_current_task().id,
        )


class SyntheticTaskFailure(RuntimeError):
    pass


async def crash_when_armed(scratch: Path) -> None:
    with anyio.fail_after(15):
        while not (
            (scratch / "crash-permitted.flag").exists() and (scratch / "work-entered.json").exists()
        ):
            await anyio.sleep(0.01)
    event(scratch, "app", "abrupt_application_exit", code=23)
    os._exit(23)  # Whole disposable application process; never the observer or CST.


class SafeLog(logging.Handler):
    def __init__(self, report: dict) -> None:
        super().__init__(logging.WARNING)
        self.report = report

    def emit(self, record: logging.LogRecord) -> None:
        # Levels/logger names only: no raw SDK errors, stderr or environment content.
        self.report.setdefault("sdk_log_metadata", []).append(
            {
                "logger": record.name,
                "level": record.levelname,
            }
        )


async def application(scratch: Path, restart: bool) -> int:
    mode = validate_child(scratch)
    actor = "restart" if restart else "app"
    identity = scratch / (actor + "-identity.json")
    if identity.exists():
        raise RuntimeError("application_replay_forbidden")
    durable(identity, {"pid": os.getpid(), "parent_pid": os.getppid()})
    watchdog(scratch, actor, 42)
    report = {"mode": mode, "synthetic_only": True, "status": "in_flight"}
    if restart:
        if mode != "crash_restart":
            raise RuntimeError("restart_not_authorized_here")
        guard = Guard(scratch)
        report["startup_reconciliation_required"] = guard.blocked
        report["attempts"] = [await guard.call(name) for name in TOOLS]
        report["sdk_transport_opened"] = False
        report["status"] = "reconciliation_required"
        durable(scratch / "restart-result.json", report)
        return (
            0
            if guard.blocked and all(a["state"] == "not_dispatched" for a in report["attempts"])
            else 1
        )
    if Guard(scratch).blocked:
        raise RuntimeError("initial_launch_already_has_recovery_state")
    log = SafeLog(report)
    logging.getLogger().handlers = [log]
    logging.getLogger().setLevel(logging.WARNING)
    argv = command("--peer", scratch)
    parameters = StdioServerParameters(
        command=argv[0], args=argv[1:], env=environment(), cwd=PROJECT
    )
    started = time.monotonic()
    startup_allowance = 3 if mode == "startup_timeout" else 10
    report["startup_allowance_s"] = startup_allowance
    report["cleanup_allowance_s"] = 10
    report["startup_started"] = started
    try:
        # The same application task owns both public contexts and this outer scope.
        with anyio.fail_after(20) as lifecycle:
            with open(os.devnull, "w") as stderr:
                async with observed_context(
                    stdio_client(parameters, errlog=stderr), scratch, report, "transport"
                ) as streams:
                    async with observed_context(
                        ClientSession(*streams), scratch, report, "session"
                    ) as session:
                        try:
                            # This inner scope exits before either SDK context unwinds.
                            with anyio.fail_after(
                                max(0.001, started + startup_allowance - time.monotonic())
                            ):
                                await session.initialize()
                                catalogue = await session.list_tools()
                                if {t.name: t.input_schema for t in catalogue.tools} != {
                                    n: SCHEMA for n in TOOLS
                                }:
                                    raise RuntimeError("unexpected_synthetic_catalogue")
                            report["startup_completed"] = time.monotonic()
                            if mode == "crash_restart":
                                async with anyio.create_task_group() as group:
                                    group.start_soon(crash_when_armed, scratch)
                                    await Guard(scratch, session).call("work")
                                raise RuntimeError("crash_scenario_unexpectedly_settled")
                            if mode == "stalled_shutdown":
                                raise SyntheticTaskFailure("synthetic-only")
                            raise RuntimeError("expected_startup_failure_not_observed")
                        except BaseException as error:
                            report["primary_exception_types"] = exception_types(error)
                            report["startup_or_task_failure_observed"] = time.monotonic()
                            raise
                        finally:
                            report["cleanup_started"] = time.monotonic()
                            lifecycle.deadline = report["cleanup_started"] + 10
    except BaseException as error:
        report["status"] = "failed_not_success"
        report["final_exception_types"] = exception_types(error)
    finally:
        ended = time.monotonic()
        report["application_total_s"] = ended - started
        if "cleanup_started" in report:
            report["cleanup_s"] = ended - report["cleanup_started"]
            report["cleanup_allowance_exceeded"] = report["cleanup_s"] > 10
        report["recovery_marker_retained"] = (scratch / "central-recovery.json").exists()
        durable(scratch / "app-result.json", report)
    return 20


def events(scratch: Path, actor: str) -> list[dict]:
    path = scratch / (actor + "-events.jsonl")
    return (
        [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []
    )


def observed_alive(handles: dict[int, ExactProcess]) -> dict[str, bool]:
    return {str(pid): handle.alive() for pid, handle in handles.items()}


def run_application(scratch: Path, restart: bool, result: dict, round_deadline: float) -> None:
    role = "--restart" if restart else "--app"
    process = subprocess.Popen(
        command(role, scratch),
        cwd=PROJECT,
        env=environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    handles: dict[int, ExactProcess] = {}
    facts = []
    started = time.monotonic()
    phase = {}
    result["restart_process" if restart else "application_process"] = phase
    try:
        while process.poll() is None:
            discover(process.pid, handles, facts)
            identity = scratch / "peer-identity.json"
            if not restart and identity.exists():
                peer_pid = read(identity)["pid"]
                if peer_pid in handles and handles[peer_pid].alive():
                    (scratch / "peer-observed.flag").touch(exist_ok=True)
            if scratch.name == "crash_restart" and not restart:
                if identity.exists() and (scratch / "work-entered.json").exists():
                    peer_pid = read(identity)["pid"]
                    if peer_pid not in handles or not handles[peer_pid].alive():
                        raise RuntimeError("peer_exact_handle_not_established_before_crash")
                    if not (scratch / "crash-permitted.flag").exists():
                        durable(
                            scratch / "observer-precrash.json",
                            {
                                "processes": facts,
                                "alive": observed_alive(handles),
                                "central_marker": read(scratch / "central-recovery.json"),
                            },
                        )
                        (scratch / "crash-permitted.flag").touch(exist_ok=False)
            if time.monotonic() >= min(started + 48, round_deadline - 10):
                raise RuntimeError("application_complete_allowance_exceeded")
            time.sleep(0.015)
        phase["exit_code"] = process.returncode
        phase["complete_invocation_s"] = time.monotonic() - started
        phase["alive_at_application_exit"] = observed_alive(handles)
        phase["post_exit_samples"] = []
        end = min(time.monotonic() + 3, round_deadline - 5)
        while True:
            state = observed_alive(handles)
            phase["post_exit_samples"].append({"monotonic": time.monotonic(), "alive": state})
            if not any(state.values()) or time.monotonic() >= end:
                break
            time.sleep(0.025)
        phase["all_tracked_terminated_before_containment_release"] = not any(state.values())
    finally:
        phase["processes"] = facts
        # Only our newly created fake application/peer see this exact flag.
        # The peer self-exits even if SDK job assignment missed an intermediate child.
        release = "restart-release.flag" if restart else "containment-release.flag"
        (scratch / release).touch(exist_ok=True)
        end = min(time.monotonic() + 4, round_deadline)
        while (
            process.poll() is None or any(h.alive() for h in handles.values())
        ) and time.monotonic() < end:
            time.sleep(0.025)
        phase["alive_after_containment_release"] = observed_alive(handles)
        phase["all_tracked_terminated_after_containment_release"] = (
            process.poll() is not None
            and not any(phase["alive_after_containment_release"].values())
        )
        for handle in handles.values():
            handle.close()
        phase["total_observed_s"] = time.monotonic() - started
        durable(scratch / ("restart-observer.json" if restart else "app-observer.json"), phase)
    if not phase["all_tracked_terminated_after_containment_release"]:
        raise RuntimeError("fake_process_containment_unresolved")


def verify_case(scratch: Path, result: dict) -> None:
    mode = scratch.name
    peer_events = events(scratch, "peer")
    calls = [e for e in peer_events if e["event"] == "request" and e["method"] == "tools/call"]
    result["tools_call_count"] = len(calls)
    result["peer_identity"] = read(scratch / "peer-identity.json")
    if mode == "crash_restart":
        if result["application_process"]["exit_code"] != 23:
            raise RuntimeError("whole_application_did_not_exit_at_controlled_crash")
        marker = read(scratch / "central-recovery.json")
        restart = read(scratch / "restart-result.json")
        if (
            len(calls) != 1
            or marker["state"] != "in_flight"
            or not read(scratch / "work-entered.json")["marker_verified_before_work"]
            or (scratch / "settled.json").exists()
            or result["restart_process"]["exit_code"] != 0
            or not restart["startup_reconciliation_required"]
            or restart["sdk_transport_opened"]
            or [a["operation"] for a in restart["attempts"]] != list(TOOLS)
            or any(a["state"] != "not_dispatched" for a in restart["attempts"])
        ):
            raise RuntimeError("crash_restart_contract_not_demonstrated")
        result["marker_retained_and_fresh_process_blocks_all_tools"] = True
    else:
        app = read(scratch / "app-result.json")
        result["application_report"] = app
        expected = {
            "partial_startup_failure": "McpError",
            "startup_timeout": "TimeoutError",
            "stalled_shutdown": "SyntheticTaskFailure",
        }[mode]
        if (
            result["application_process"]["exit_code"] != 20
            or calls
            or app["status"] != "failed_not_success"
            or expected not in app.get("primary_exception_types", [])
            or expected not in app.get("final_exception_types", [])
            or app.get("cleanup_allowance_exceeded", True)
        ):
            raise RuntimeError("failure_not_preserved_or_cleanup_over_budget")
        if not result["application_process"]["all_tracked_terminated_before_containment_release"]:
            raise RuntimeError("sdk_cleanup_left_observed_processes_alive")
        overhead = max(
            0.0,
            result["application_process"]["complete_invocation_s"] - app["application_total_s"],
        )
        result["outer_invocation_overhead_s"] = overhead
        result["cleanup_conservative_upper_s"] = app["cleanup_s"] + overhead
        startup_end = app.get("startup_completed", app["startup_or_task_failure_observed"])
        result["startup_conservative_upper_s"] = startup_end - app["startup_started"] + overhead
        result["provisional_120s_startup_30s_cleanup_bounds_met"] = (
            result["startup_conservative_upper_s"] <= 120
            and result["cleanup_conservative_upper_s"] <= 30
        )
        if not result["provisional_120s_startup_30s_cleanup_bounds_met"]:
            raise RuntimeError("complete_provisional_lifecycle_bounds_exceeded")
        outcomes = app.get("context_outcomes", [])
        if {o["context"] for o in outcomes} != {"session", "transport"} or any(
            not o["entered"] or o["owner_task_id"] != o["exit_task_id"] for o in outcomes
        ):
            raise RuntimeError("same_owner_context_unwind_not_established")
        if mode == "startup_timeout":
            startup_s = app["startup_or_task_failure_observed"] - app["startup_started"]
            result["startup_observed_s"] = startup_s
            # Measurement is evidence, not a promise of exact scheduler precision.
            if not any(e["event"] == "initialization_stalled" for e in peer_events):
                raise RuntimeError("initialization_stall_not_observed")
        if mode == "stalled_shutdown":
            if not any(e["event"] == "refusing_orderly_exit" for e in peer_events):
                raise RuntimeError("shutdown_stall_not_observed")
            if any(e["event"] == "normal_exit" for e in peer_events):
                raise RuntimeError("peer_unexpectedly_exited_normally")
            result["orderly_exit_refused_and_primary_failure_preserved"] = True
    peer_pid = str(result["peer_identity"]["pid"])
    observed = result["application_process"]["alive_after_containment_release"]
    if peer_pid not in observed:
        raise RuntimeError("peer_handle_observation_missing")
    result["verification"] = "passed_synthetic_design_observation"


def prepare() -> None:
    """Static preparation only; no application, peer, scenario or native code starts."""
    if ROOT.exists():
        raise RuntimeError("round_target_already_consumed")
    for path in SOURCES:
        source = path.read_text("utf-8")
        ast.parse(source)
        compile(source, str(path), "exec")
    tree = ast.parse(HERE.read_text("utf-8"))
    call_sites = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "call_tool"
    ]
    if len(call_sites) != 1:
        raise RuntimeError("expected_exactly_one_guarded_dispatch_site")
    prior = {}
    for folder in (BRANCH / "docs/prototypes", BRANCH / "src/cst_agentic"):
        for path in folder.rglob("*"):
            if (
                path.is_file()
                and path not in SOURCES
                and ARCHIVE not in path.parents
                and "__pycache__" not in path.parts
            ):
                if path.name.startswith("windows_") or "windows-" in str(path.relative_to(BRANCH)):
                    prior[str(path)] = sha(path)
    for directory in ("cst-lifetime-native", "cst-solver-stop-dipole-01"):
        path = ROOT.parent / directory / "round.json"
        if path.is_file():
            prior[str(path)] = sha(path)
    durable(ARCHIVE / "prior-evidence-sha256.json", prior)
    durable(
        ARCHIVE / "preparation.json",
        {
            "static_only": True,
            "scenario_executions": 0,
            "source_sha256": {p.name: sha(p) for p in SOURCES},
            "versions": {n: version(n) for n in ("mcp", "anyio")},
            "installed_sdk_source_sha256": {
                name: sha(Path(sys.modules[name].__file__))
                for name in ("mcp.client.stdio", "mcp.os.win32.utilities")
            },
            "prior_files_fingerprinted": len(prior),
            "guarded_call_tool_sites": len(call_sites),
        },
    )
    print(
        json.dumps(
            {
                "static_preparation": "passed",
                "scenario_executions": 0,
                "prior_files_fingerprinted": len(prior),
            }
        )
    )


def run_round() -> None:
    prepared = read(ARCHIVE / "preparation.json")
    approval = read(ARCHIVE / "authorization.json")
    if (
        prepared["source_sha256"] != {p.name: sha(p) for p in SOURCES}
        or approval["maximum_scenarios"] != 4
        or approval["maximum_seconds"] != 300
        or approval["scenarios"] != list(CASES)
        or approval["retries"] != 0
        or approval["user_confirmation"] != "I authorize it."
    ):
        raise RuntimeError("preparation_or_authorization_mismatch")
    if any(
        sha(Path(path)) != expected
        for path, expected in read(ARCHIVE / "prior-evidence-sha256.json").items()
    ):
        raise RuntimeError("prior_evidence_changed_before_admission")
    ROOT.mkdir()  # Exclusive, one-time admission. No replay after partial failure.
    (ROOT / "sources").mkdir()
    for path in SOURCES:
        shutil.copyfile(path, ROOT / "sources" / path.name)
    for name in ("authorization.json", "preparation.json", "prior-evidence-sha256.json"):
        shutil.copyfile(ARCHIVE / name, ROOT / name)
    ledger = {
        "state": "in_flight",
        "maximum_seconds": 300,
        "maximum_scenarios": 4,
        "scenarios_admitted": [],
        "source_sha256": prepared["source_sha256"],
    }
    durable(ROOT / "round.json", ledger)
    report = {
        "scope": "NATIVE-FREE, SYNTHETIC DESIGN EVIDENCE ONLY",
        "cases": [],
        "status": "in_flight",
        "versions": prepared["versions"],
        "CST_solver_endpoint_executions": 0,
        "publication_authorized": False,
    }
    deadline = STARTED + 270  # Leave outer invocation/evidence headroom within 300 s.
    try:
        for mode in CASES:
            if time.monotonic() + 60 >= deadline:
                raise RuntimeError("insufficient_remaining_round_budget")
            scratch = ROOT / mode
            scratch.mkdir()
            ledger["scenarios_admitted"].append(mode)
            durable(ROOT / "round.json", ledger)
            result = {"name": mode, "synthetic_only": True}
            report["cases"].append(result)
            case_started = time.monotonic()
            try:
                run_application(scratch, False, result, deadline)
                if mode == "crash_restart":
                    run_application(scratch, True, result, deadline)
                verify_case(scratch, result)
            finally:
                result["complete_scenario_s"] = time.monotonic() - case_started
                durable(ROOT / "observations.json", report)
            print(
                json.dumps(
                    {
                        "name": mode,
                        "verification": result["verification"],
                        "complete_scenario_s": result["complete_scenario_s"],
                    }
                ),
                flush=True,
            )
        prior = read(ROOT / "prior-evidence-sha256.json")
        if any(sha(Path(path)) != expected for path, expected in prior.items()):
            raise RuntimeError("prior_evidence_changed")
        report["prior_files_unchanged"] = len(prior)
        report["status"] = "completed_synthetic_observations"
    except BaseException as error:
        report["status"] = "blocked_review_required"
        report["error_types"] = exception_types(error)
        raise
    finally:
        report["elapsed_s"] = time.monotonic() - STARTED
        report["internal_round_limit_met"] = report["elapsed_s"] <= 270
        ledger["state"] = report["status"]
        ledger["elapsed_s"] = report["elapsed_s"]
        durable(ROOT / "round.json", ledger)
        durable(ROOT / "observations.json", report)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "elapsed_s": report["elapsed_s"],
                    "scenarios_admitted": len(ledger["scenarios_admitted"]),
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--prepare-static-only"]:
            prepare()
        elif sys.argv[1:] == ["--run-authorized-once"]:
            run_round()
        elif len(sys.argv) == 3 and sys.argv[1] in {"--peer", "--app", "--restart"}:
            target = Path(sys.argv[2]).resolve()
            if sys.argv[1] == "--peer":
                peer(target)
            else:
                sys.exit(anyio.run(application, target, sys.argv[1] == "--restart"))
        else:
            raise RuntimeError("explicit_fixed_scope_flag_required")
    except Exception as error:
        print(json.dumps({"stopped": True, "error_types": exception_types(error)}), flush=True)
        sys.exit(1)
