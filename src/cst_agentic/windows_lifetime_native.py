"""THROWAWAY: one approved native blank-project lifetime case per invocation.

Exactly two fixed targets, <=12 tools/call, <=900 active experiment seconds
including cleanup, no solver/model requests. Re-execution is refused except for
the single explicitly reconciled, pre-native logging failure recorded on disk.
This is not the production client and does not validate production handlers.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import logging
import os
import shutil
import sys
import time
from ctypes import wintypes
from importlib.metadata import version
from pathlib import Path

INVOCATION_STARTED = time.monotonic()

import anyio  # noqa: E402
import win32api  # noqa: E402
import win32event  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import get_default_environment, stdio_client  # noqa: E402
from windows_lifetime_native_peer import (  # noqa: E402
    INSTALL,
    NAMES,
    RESUME_FLAG,
    ROOT,
    TARGETS,
    durable_write,
    evidence_directory,
    schema,
)

HERE = Path(__file__).resolve()
PEER = HERE.with_name("windows_lifetime_native_peer.py")
SERVER_PROJECT = Path(r"C:\dev\cst-studio-mcp")
ROUND_FILE = ROOT / "round.json"
CONTINUATION_FILE = ROOT / "logging-fix-continuation.json"
WRAPPER_RESERVE_SECONDS = 30
KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
USER = ctypes.WinDLL("user32", use_last_error=True)
logging.disable(logging.CRITICAL)


class ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("pid", wintypes.DWORD),
        ("heap", ctypes.c_size_t),
        ("module", wintypes.DWORD),
        ("threads", wintypes.DWORD),
        ("parent_pid", wintypes.DWORD),
        ("priority", wintypes.LONG),
        ("flags", wintypes.DWORD),
        ("exe", wintypes.WCHAR * 260),
    ]


KERNEL.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
KERNEL.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
KERNEL.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
KERNEL.Process32NextW.argtypes = KERNEL.Process32FirstW.argtypes
KERNEL.CloseHandle.argtypes = [wintypes.HANDLE]
KERNEL.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
KERNEL.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
WINDOW_CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
USER.EnumWindows.argtypes = [WINDOW_CALLBACK, wintypes.LPARAM]
USER.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
USER.IsWindowVisible.argtypes = [wintypes.HWND]
USER.GetWindowTextLengthW.argtypes = [wintypes.HWND]
USER.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]


def checked(ok, operation: str) -> None:
    if not ok:
        raise RuntimeError(operation + "_winerror_" + str(ctypes.get_last_error()))


def snapshot() -> dict[int, dict]:
    handle = KERNEL.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        checked(False, "snapshot")
    entries = {}
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        checked(KERNEL.Process32FirstW(handle, ctypes.byref(entry)), "process_first")
        while True:
            entries[entry.pid] = {
                "pid": entry.pid,
                "parent_pid": entry.parent_pid,
                "executable_basename": entry.exe,
            }
            if not KERNEL.Process32NextW(handle, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:
                    checked(False, "process_next")
                break
    finally:
        checked(KERNEL.CloseHandle(handle), "snapshot_close")
    return entries


def handle_facts(handle) -> dict:
    inside = wintypes.BOOL()
    checked(KERNEL.IsProcessInJob(int(handle), None, ctypes.byref(inside)), "job_membership")
    times = [wintypes.FILETIME() for _ in range(4)]
    checked(KERNEL.GetProcessTimes(int(handle), *(ctypes.byref(t) for t in times)), "process_times")
    return {
        "in_any_job": bool(inside.value),
        "creation_filetime": times[0].dwLowDateTime | (times[0].dwHighDateTime << 32),
    }


def alive(handle) -> bool:
    outcome = win32event.WaitForSingleObject(handle, 0)
    if outcome not in (win32event.WAIT_TIMEOUT, win32event.WAIT_OBJECT_0):
        raise RuntimeError("process_wait_failed")
    return outcome == win32event.WAIT_TIMEOUT


def windows_for(pid: int, target: Path) -> dict:
    # No foreign window text, screenshots, commands, UI actions or raw titles.
    facts = {"visible_count": 0, "expected_project_title_count": 0}

    @WINDOW_CALLBACK
    def collect(hwnd, unused):
        owner = wintypes.DWORD()
        USER.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and USER.IsWindowVisible(hwnd):
            facts["visible_count"] += 1
            length = min(4096, USER.GetWindowTextLengthW(hwnd))
            buffer = ctypes.create_unicode_buffer(length + 1)
            USER.GetWindowTextW(hwnd, buffer, length + 1)
            if target.stem.casefold() in buffer.value.casefold():
                facts["expected_project_title_count"] += 1
        return True

    checked(USER.EnumWindows(collect, 0), "enum_windows")
    return facts


class NativeDispatch:
    """Sole tools/call route: fixed batch, schemas, ledger, lock, durable latch."""

    def __init__(
        self, session, case: str, ledger: dict, started: float, report: dict, scratch: Path
    ):
        self.session, self.case, self.ledger = session, case, ledger
        self.started, self.report = started, report
        self.lock = anyio.Lock()
        self.halted = False
        self.marker = scratch / "recovery.json"
        self.plan = [
            ("native_connect", {"mode": "new"}),
            ("native_create", {"path": str(TARGETS[case])}),
            ("native_status", {}),
            ("native_disconnect" if case == "leave-open" else "native_close", {}),
        ]

    def remaining(self) -> float:
        return 900 - self.ledger["active_seconds"] - (time.monotonic() - self.started)

    async def call(self, name: str, arguments: dict) -> dict:
        admitted = time.monotonic()
        attempt = {"name": name, "admitted": admitted, "state": "not_dispatched"}
        index = len(self.report["attempts"])
        self.report["attempts"].append(attempt)
        dispatched = False
        try:
            with anyio.fail_after(120):
                async with self.lock:
                    if self.halted or self.marker.exists() or (name, arguments) != self.plan[index]:
                        raise RuntimeError("dispatch_guard_blocked")
                    if self.ledger["tool_calls"] >= 12 or self.remaining() < 155:
                        raise RuntimeError("approved_budget_exhausted")
                    if name == "native_create" and TARGETS[self.case].exists():
                        raise RuntimeError("target_now_exists")
                    durable_write(
                        self.marker,
                        {
                            "state": "in_flight",
                            "operation": name,
                            "target": str(TARGETS[self.case]),
                        },
                    )
                    self.ledger["tool_calls"] += 1
                    durable_write(ROUND_FILE, self.ledger)
                    dispatched = True
                    attempt["dispatch"] = time.monotonic()
                    response = await self.session.call_tool(name, arguments)
                    attempt["state"] = "received"
                    payload = response.structured_content
                    if not isinstance(payload, dict):
                        raise RuntimeError("missing_structured_response")
                    attempt["response"] = payload
                    attempt["is_error"] = response.is_error
                    if response.is_error or payload.get("status") == "error":
                        self.halted = True
                        durable_write(
                            self.marker,
                            {"state": "received_failure_reconciliation", "operation": name},
                        )
                        raise RuntimeError("received_native_failure")
                    self.marker.unlink()
                    return payload
        except BaseException as error:
            self.halted = True
            if dispatched and attempt["state"] != "received":
                attempt["state"] = "uncertain"
            attempt["error_type"] = type(error).__name__
            raise
        finally:
            attempt["settled"] = time.monotonic()
            attempt["total_s"] = round(attempt["settled"] - admitted, 6)


def prepare_case(case: str, resumed: bool) -> tuple[dict, Path]:
    """Admit one reconciled retry without deleting or rewriting failed evidence."""
    if case not in TARGETS or (resumed and case != "leave-open"):
        raise RuntimeError("fixed_case_required")
    if not ROUND_FILE.is_file():
        raise RuntimeError("existing_round_required")
    ledger = json.loads(ROUND_FILE.read_text("utf-8"))
    if ledger["maximum_calls"] != 12 or ledger["maximum_active_seconds"] != 900:
        raise RuntimeError("original_limits_required")
    if resumed:
        approval = json.loads(CONTINUATION_FILE.read_text("utf-8"))
        old = evidence_directory("leave-open")
        failure = json.loads((old / "observations.json").read_text("utf-8"))
        marker = json.loads((old / "recovery.json").read_text("utf-8"))
        events = [json.loads(line) for line in (old / "peer-events.jsonl").read_text().splitlines()]
        attempts = failure["attempts"]
        if (
            approval["id"] != "logging-fix-1"
            or approval["user_authorized"] is not True
            or approval["user_message"] != "Go ahead."
            or approval["human_observation"] != "No cst window appeared."
            or approval["prior_attempt_charge_seconds"] != 180
            or approval["maximum_calls"] != 12
            or approval["maximum_active_seconds"] != 900
            or ledger["cases"] != {"leave-open": "blocked_reconciliation"}
            or ledger["tool_calls"] != 1
            or ledger["active_seconds"] != failure["total_s"]
            or "continuation" in ledger
            or len(attempts) != 1
            or attempts[0]["name"] != "native_connect"
            or attempts[0]["state"] != "received"
            or attempts[0]["is_error"] is not True
            or attempts[0]["response"] != {"status": "error", "error_type": "TypeError"}
            or marker != {"state": "received_failure_reconciliation", "operation": "native_connect"}
            or any(e["event"] == "operation_entered" for e in events)
            or (old / "launch-identity.json").exists()
            or any(target.exists() for target in TARGETS.values())
        ):
            raise RuntimeError("logging_failure_reconciliation_mismatch")
        archive = (
            HERE.parents[2]
            / "docs/prototypes/windows-lifetime-native-evidence/failed-attempt-source"
        )
        for filename, expected in failure["source_sha256"].items():
            actual = hashlib.sha256((archive / filename).read_bytes()).hexdigest().upper()
            if actual != expected:
                raise RuntimeError("failed_executed_source_not_preserved")
        ledger["continuation"] = {
            "id": approval["id"],
            "authorization_sha256": hashlib.sha256(CONTINUATION_FILE.read_bytes()).hexdigest(),
            "failed_evidence_directory": str(old),
            "failed_ledger": json.loads(ROUND_FILE.read_text("utf-8")),
            "prior_attempt_charge_seconds": 180,
            "qualification": "Conservative charge, not retrospective proof of unmeasured overhead.",
        }
        ledger["active_seconds"] = 180
    else:
        if case != "authorized-close" or ledger["cases"] != {"leave-open": "completed"}:
            raise RuntimeError("case_replay_or_unreconciled_round")
        first = evidence_directory("leave-open", resumed=True)
        previous = json.loads((first / "observations.json").read_text("utf-8"))
        outer = json.loads((first / "outer-observation.json").read_text("utf-8"))
        if (
            previous["manual_confirmation_required"]
            or outer["exit_code"] != 0
            or outer.get("native_invocation_error_type") is not None
            or outer["wrapper_reserve_exceeded"]
            or not outer["ledger_matches"]
            or outer["round_ceiling_exceeded"]
            or outer["complete_allowance_exceeded"]
        ):
            raise RuntimeError("first_case_requires_human_reconciliation")
    if TARGETS[case].exists() or ledger["active_seconds"] + WRAPPER_RESERVE_SECONDS >= 900:
        raise RuntimeError("fixed_target_or_round_unavailable")
    scratch = evidence_directory(case, resumed)
    scratch.mkdir()  # Exclusive attempt directory: never reuse failed evidence/markers.
    ledger["active_seconds"] += WRAPPER_RESERVE_SECONDS
    ledger["cases"][case] = "in_flight"
    durable_write(ROUND_FILE, ledger)
    durable_write(scratch / "ledger-at-admission.json", ledger)
    return ledger, scratch


async def run_case(case: str, resumed: bool = False) -> None:
    started = INVOCATION_STARTED
    ledger, scratch = prepare_case(case, resumed)
    report = {
        "case": case,
        "target": str(TARGETS[case]),
        "attempts": [],
        "versions": {n: version(n) for n in ("mcp", "anyio")},
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in (HERE, PEER)
        },
        "manual_confirmation_required": True,
        "continuation": "logging-fix-1" if resumed else None,
        "wrapper_reserve_seconds": WRAPPER_RESERVE_SECONDS,
    }
    handles = {}
    de_pid = None
    cleanup_started = None
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv_missing")
    environment = get_default_environment() | {
        "UV_OFFLINE": "1",
        "CST_PATH": str(INSTALL),
        "CST_VERSION": "2025",
        "CST_CONNECT_MODE": "manual",
        "CST_WORK_DIR": str(ROOT),
        "CST_TOOLSETS": "connection,project",
        "CST_LOG_LEVEL": "CRITICAL",
    }
    params = StdioServerParameters(
        command=uv,
        args=[
            "run",
            "--offline",
            "--no-sync",
            "--project",
            str(SERVER_PROJECT),
            "python",
            str(PEER),
            case,
            *([RESUME_FLAG] if resumed else []),
        ],
        cwd=SERVER_PROJECT,
        env=environment,
    )
    try:
        # Lifecycle scopes and both public SDK contexts enter/exit in this task.
        startup_remaining = min(120 - WRAPPER_RESERVE_SECONDS, 900 - ledger["active_seconds"])
        with anyio.fail_after(
            max(0.001, startup_remaining - (time.monotonic() - started))
        ) as lifecycle:
            with open(os.devnull, "w") as stderr:
                async with stdio_client(params, errlog=stderr) as (read, write):
                    async with ClientSession(read, write) as session:
                        try:
                            await session.initialize()
                            tools = (await session.list_tools()).tools
                            if {t.name: t.input_schema for t in tools} != {
                                n: schema(n) for n in NAMES
                            }:
                                raise RuntimeError("unexpected_native_catalogue")
                            report["startup_s"] = round(time.monotonic() - started, 6)
                            lifecycle.deadline = float("inf")
                            gateway = NativeDispatch(
                                session, case, ledger, started, report, scratch
                            )
                            connected = await gateway.call("native_connect", {"mode": "new"})
                            de_pid = connected["de_pid"]
                            identity = json.loads(
                                (scratch / "peer-identity.json").read_text("utf-8")
                            )
                            entries = snapshot()
                            selected = {de_pid: "cst_instance", identity["pid"]: "peer"}
                            cursor = identity["pid"]
                            for _ in range(10):
                                cursor = entries[cursor]["parent_pid"]
                                if cursor == os.getpid():
                                    break
                                selected[cursor] = "launcher"
                            else:
                                raise RuntimeError("peer_chain_does_not_reach_observer")
                            # Track currently observed descendants, without touching them.
                            for _ in range(10):
                                added = {
                                    pid: "observed_descendant"
                                    for pid, e in entries.items()
                                    if e["parent_pid"] in selected and pid not in selected
                                }
                                if not added:
                                    break
                                selected.update(added)
                            report["processes"] = []
                            for pid, role in selected.items():
                                handle = win32api.OpenProcess(0x1000 | 0x100000, False, pid)
                                handles[pid] = handle
                                report["processes"].append(
                                    entries[pid] | {"role": role} | handle_facts(handle)
                                )
                            await gateway.call("native_create", {"path": str(TARGETS[case])})
                            await gateway.call("native_status", {})
                            report["windows_before_exit_action"] = windows_for(
                                de_pid, TARGETS[case]
                            )
                            report["alive_before_exit_action"] = {
                                str(p): alive(h) for p, h in handles.items()
                            }
                            last = "native_disconnect" if case == "leave-open" else "native_close"
                            await gateway.call(last, {})
                            report["alive_after_exit_action"] = {
                                str(p): alive(h) for p, h in handles.items()
                            }
                        finally:
                            cleanup_started = time.monotonic()
                            lifecycle.deadline = cleanup_started + min(
                                25, gateway.remaining() if "gateway" in locals() else 25
                            )
                    report["session_exit_returned"] = time.monotonic()
                report["transport_exit_returned"] = time.monotonic()
        boundary = report["transport_exit_returned"]
        report["cleanup_s"] = round(boundary - cleanup_started, 6)
        if report["cleanup_s"] > 25:
            raise RuntimeError("cleanup_allowance_exceeded")
        report["post_teardown_samples"] = []
        previous = None
        while True:
            state = {str(p): alive(h) for p, h in handles.items()}
            elapsed = time.monotonic() - boundary
            if state != previous:
                report["post_teardown_samples"].append(
                    {"after_teardown_s": round(elapsed, 6), "alive": state}
                )
                previous = state
            if elapsed >= 5 or not any(state.values()):
                break
            await anyio.sleep(0.05)
        report["observation_window_s"] = round(elapsed, 6)
        report["final_alive"] = state
        report["windows_after_teardown"] = windows_for(de_pid, TARGETS[case])
        report["saved_file_exists"] = TARGETS[case].is_file()
        de_alive = state[str(de_pid)]
        if not de_alive:
            report["instance_observation"] = "identified_DE_process_terminated"
            report["manual_confirmation_required"] = False
        elif report["windows_after_teardown"]["expected_project_title_count"]:
            report["instance_observation"] = "identified_DE_alive_with_expected_project_window"
            report["manual_confirmation_required"] = False
        else:
            report["instance_observation"] = "process_alive_project_window_unconfirmed"
        ledger["cases"][case] = "completed"
    except BaseException as error:
        report["error_type"] = type(error).__name__
        ledger["cases"][case] = "blocked_reconciliation"
        raise
    finally:
        for handle in handles.values():
            handle.Close()
        report["total_s"] = round(time.monotonic() - started, 6)
        ledger["active_seconds"] += report["total_s"]
        durable_write(scratch / "observations.json", report)
        durable_write(ROUND_FILE, ledger)
        print(
            json.dumps(
                {
                    k: report.get(k)
                    for k in (
                        "case",
                        "instance_observation",
                        "manual_confirmation_required",
                        "error_type",
                        "total_s",
                    )
                }
            ),
            flush=True,
        )
        print("Evidence: " + str(scratch / "observations.json"), flush=True)


if __name__ == "__main__":
    try:
        resumed = len(sys.argv) == 3 and sys.argv[2] == RESUME_FLAG
        if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and not resumed):
            raise RuntimeError("fixed_case_required")
        if sys.argv[1] not in TARGETS or (resumed and sys.argv[1] != "leave-open"):
            raise RuntimeError("fixed_case_required")
        anyio.run(run_case, sys.argv[1], resumed)
    except BaseException as error:
        print("Native case stopped: " + type(error).__name__, flush=True)
        sys.exit(1)
