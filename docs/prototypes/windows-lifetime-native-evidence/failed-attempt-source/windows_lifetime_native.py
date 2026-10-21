"""THROWAWAY: one approved native blank-project lifetime case per invocation.

Exactly two fixed targets, <=12 tools/call, <=900 active experiment seconds
including cleanup, no solver/model requests. Re-execution of a case is refused.
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
    ROOT,
    TARGETS,
    durable_write,
    schema,
)

HERE = Path(__file__).resolve()
PEER = HERE.with_name("windows_lifetime_native_peer.py")
SERVER_PROJECT = Path(r"C:\dev\cst-studio-mcp")
ROUND_FILE = ROOT / "round.json"
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

    def __init__(self, session, case: str, ledger: dict, started: float, report: dict):
        self.session, self.case, self.ledger = session, case, ledger
        self.started, self.report = started, report
        self.lock = anyio.Lock()
        self.halted = False
        self.marker = ROOT / "evidence" / case / "recovery.json"
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


async def run_case(case: str) -> None:
    started = INVOCATION_STARTED
    ROOT.mkdir(exist_ok=True)
    (ROOT / "evidence").mkdir(exist_ok=True)
    if ROUND_FILE.exists():
        ledger = json.loads(ROUND_FILE.read_text("utf-8"))
        if case != "authorized-close" or ledger["cases"] != {"leave-open": "completed"}:
            raise RuntimeError("case_replay_or_unreconciled_round")
    else:
        if case != "leave-open":
            raise RuntimeError("leave_open_must_run_first")
        ledger = {
            "tool_calls": 0,
            "active_seconds": 0,
            "cases": {},
            "maximum_calls": 12,
            "maximum_active_seconds": 900,
        }
    if TARGETS[case].exists() or ledger["active_seconds"] >= 900:
        raise RuntimeError("fixed_target_or_round_unavailable")
    scratch = ROOT / "evidence" / case
    scratch.mkdir()
    ledger["cases"][case] = "in_flight"
    durable_write(ROUND_FILE, ledger)
    report = {
        "case": case,
        "target": str(TARGETS[case]),
        "attempts": [],
        "versions": {n: version(n) for n in ("mcp", "anyio")},
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in (HERE, PEER)
        },
        "manual_confirmation_required": True,
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
        ],
        cwd=SERVER_PROJECT,
        env=environment,
    )
    try:
        # Lifecycle scopes and both public SDK contexts enter/exit in this task.
        with anyio.fail_after(max(0.001, 120 - (time.monotonic() - started))) as lifecycle:
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
                            gateway = NativeDispatch(session, case, ledger, started, report)
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
                                30, gateway.remaining() if "gateway" in locals() else 30
                            )
                    report["session_exit_returned"] = time.monotonic()
                report["transport_exit_returned"] = time.monotonic()
        boundary = report["transport_exit_returned"]
        report["cleanup_s"] = round(boundary - cleanup_started, 6)
        if report["cleanup_s"] > 30:
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
        if len(sys.argv) != 2 or sys.argv[1] not in TARGETS:
            raise RuntimeError("fixed_case_required")
        anyio.run(run_case, sys.argv[1])
    except BaseException as error:
        print("Native case stopped: " + type(error).__name__, flush=True)
        sys.exit(1)
