"""THROWAWAY: exactly two OFFLINE lifetime probes; maximum 180 s per round.

No CST, provider, arbitrary executable, SDK monkey-patch, or job-handle access.
Observe an exact fake process chain through normal and escalated stdio cleanup.
All Python process launches use uv. The previous eight scenarios are NOT rerun.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import time
import uuid
from ctypes import wintypes
from importlib.metadata import version
from pathlib import Path

ROUND_STARTED = time.monotonic()
HERE = Path(__file__).resolve()

import windows_lifetime_prototype as baseline  # noqa: E402


def fake_peer(scratch: Path, mode: str) -> None:
    baseline.durable_write(
        scratch / "peer-identity.json", {"pid": os.getpid(), "parent_pid": os.getppid()}
    )
    baseline.fake_server(scratch, mode)
    baseline.durable_write(scratch / "peer-eof.json", {"monotonic": time.monotonic()})
    if mode == "stalled_after_eof":
        # Ignore EOF long enough to trigger ordinary SDK escalation, but remain
        # self-bounded and releaseable via this exact scratch directory.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not (scratch / "peer-release.flag").exists():
            time.sleep(0.025)
    baseline.durable_write(scratch / "peer-exit.json", {"monotonic": time.monotonic()})


if len(sys.argv) > 1 and sys.argv[1] == "--followup-server":
    fake_peer(Path(sys.argv[2]), sys.argv[3])
    sys.exit(0)

anyio = baseline.anyio
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = kernel32.Process32FirstW.argtypes
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
kernel32.IsProcessInJob.restype = wintypes.BOOL
kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
kernel32.GetProcessTimes.restype = wintypes.BOOL
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL


def native_check(success: int, operation: str) -> None:
    if not success:
        raise RuntimeError(f"{operation}_winerror_{ctypes.get_last_error()}")


def process_snapshot() -> dict:
    # Read-only Windows Toolhelp API. Retain only our selected fake chain later;
    # never query or emit command lines, environment blocks or full image paths.
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        native_check(0, "snapshot")
    entries = {}
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        native_check(kernel32.Process32FirstW(snapshot, ctypes.byref(entry)), "process_first")
        while True:
            entries[entry.th32ProcessID] = {
                "pid": entry.th32ProcessID,
                "parent_pid": entry.th32ParentProcessID,
                "executable_basename": entry.szExeFile,
            }
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                    native_check(0, "process_next")
                break
    finally:
        native_check(kernel32.CloseHandle(snapshot), "snapshot_close")
    return entries


def handle_facts(handle) -> dict:
    inside = wintypes.BOOL()
    native_check(kernel32.IsProcessInJob(int(handle), None, ctypes.byref(inside)), "job_membership")
    times = [wintypes.FILETIME() for _ in range(4)]
    native_check(
        kernel32.GetProcessTimes(int(handle), *(ctypes.byref(value) for value in times)),
        "process_times",
    )
    return {
        "in_any_job": bool(inside.value),
        "creation_filetime": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
    }


def track_chain(server_pid: int, child_pid: int, handles: dict) -> list[dict]:
    entries = process_snapshot()
    chain = []
    cursor = server_pid
    while cursor != os.getpid():
        if len(chain) >= 10 or cursor not in entries:
            raise RuntimeError("fake_chain_does_not_reach_observer")
        chain.append(entries[cursor] | {"role": "peer" if cursor == server_pid else "launcher"})
        cursor = entries[cursor]["parent_pid"]
    if entries[child_pid]["parent_pid"] != server_pid:
        raise RuntimeError("unexpected_fake_child_parent")
    chain.append(entries[child_pid] | {"role": "fake_descendant"})
    for entry in chain:
        handle = baseline.win32api.OpenProcess(0x1000 | 0x100000, False, entry["pid"])
        handles[entry["pid"]] = handle
        entry.update(handle_facts(handle))
    return chain


def command(scratch: Path, mode: str) -> list[str]:
    if baseline.UV is None:
        raise RuntimeError("uv_missing")
    return [
        baseline.UV,
        "run",
        "--offline",
        "--no-sync",
        "--project",
        str(Path.cwd()),
        "python",
        str(HERE),
        "--followup-server",
        str(scratch),
        mode,
    ]


async def probe(mode: str, root: Path, result: dict) -> None:
    scratch = root / mode
    scratch.mkdir()
    handles = {}
    started = time.monotonic()
    result.update({"name": mode, "post_teardown_window_s": 5, "poll_interval_s": 0.01})
    invocation = command(scratch, mode)
    params = baseline.StdioServerParameters(
        command=invocation[0], args=invocation[1:], env=baseline.child_environment()
    )
    try:
        # One owner enters/exits SDK contexts. No job handle is duplicated or
        # kept alive by this observer; process handles are read/synchronize only.
        with anyio.fail_after(20) as lifecycle:
            with open(os.devnull, "w") as stderr:
                async with baseline.stdio_client(params, errlog=stderr) as (read, write):
                    async with baseline.ClientSession(read, write) as session:
                        await session.initialize()
                        await session.list_tools()
                        result["startup_s"] = round(time.monotonic() - started, 6)
                        gateway = baseline.GuardedFakeDispatch(session, scratch)
                        child = await gateway.call("begin")
                        if child["state"] != "received":
                            raise RuntimeError("fake_begin_did_not_settle")
                        identity = json.loads((scratch / "peer-identity.json").read_text("utf-8"))
                        result["chain"] = track_chain(
                            identity["pid"], child["value"]["pid"], handles
                        )
                        result["peer_reported_parent_pid"] = identity["parent_pid"]
                        observer = baseline.win32api.OpenProcess(0x1000, False, os.getpid())
                        try:
                            result["observer"] = {"pid": os.getpid()} | handle_facts(observer)
                        finally:
                            observer.Close()
                        result["alive_before_teardown"] = {
                            str(pid): baseline.is_running(handle) for pid, handle in handles.items()
                        }
                        result["attempts"] = gateway.attempts
                        result["cleanup_started"] = time.monotonic()
                        lifecycle.deadline = result["cleanup_started"] + 30
                    result["session_exit_returned"] = time.monotonic()
                result["transport_exit_returned"] = time.monotonic()
        boundary = result["transport_exit_returned"]
        result["cleanup_s"] = round(boundary - result["cleanup_started"], 6)
        result["first_samples"] = []
        last_state = None
        while True:
            state = {str(pid): baseline.is_running(handle) for pid, handle in handles.items()}
            elapsed = time.monotonic() - boundary
            if state != last_state:
                result["first_samples"].append(
                    {"after_teardown_s": round(elapsed, 6), "alive": state}
                )
                last_state = state
            if not any(state.values()) or elapsed >= 5:
                result["window_ended_after_s"] = round(elapsed, 6)
                result["survived_window"] = state
                break
            await anyio.sleep(0.01)
    finally:
        # Scratch flags affect only these exact fake helpers. No tools/call,
        # arbitrary PID kill, tree kill, job ownership change or retry is added.
        (scratch / "child-stop.flag").touch()
        (scratch / "peer-release.flag").touch()
        deadline = time.monotonic() + 3
        while any(baseline.is_running(handle) for handle in handles.values()):
            if time.monotonic() >= deadline:
                break
            await anyio.sleep(0.01)
        result["alive_after_scratch_cleanup"] = {
            str(pid): baseline.is_running(handle) for pid, handle in handles.items()
        }
        result["exit_codes"] = {}
        for pid, handle in handles.items():
            code = wintypes.DWORD()
            native_check(kernel32.GetExitCodeProcess(int(handle), ctypes.byref(code)), "exit_code")
            result["exit_codes"][str(pid)] = code.value
            handle.Close()
        for event in ("peer-eof", "peer-exit"):
            path = scratch / (event + ".json")
            result[event] = json.loads(path.read_text("utf-8")) if path.exists() else None
        result["total_s"] = round(time.monotonic() - started, 6)
        calls = scratch / "server-calls.jsonl"
        result["actual_server_calls"] = (
            [json.loads(line)["name"] for line in calls.read_text("utf-8").splitlines()]
            if calls.exists()
            else []
        )


async def main() -> None:
    root = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode") / (
        "cst-lifetime-followup-" + uuid.uuid4().hex[:8]
    )
    root.mkdir()
    report = {
        "scope": "OFFLINE ONLY: two lifetime probes, 180 s, no CST or provider requests",
        "versions": {name: version(name) for name in ("mcp", "openai-agents", "anyio")},
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest().upper()
            for path in (
                HERE,
                baseline.HERE,
                baseline.HERE.with_name("windows_lifetime_fake_child.ps1"),
            )
        },
        "cases": [],
    }
    try:
        with anyio.fail_after(max(0.001, 180 - (time.monotonic() - ROUND_STARTED))):
            for mode in ("graceful_eof", "stalled_after_eof"):
                result = {}
                report["cases"].append(result)
                try:
                    await probe(mode, root, result)
                except BaseException as error:
                    result["error_type"] = type(error).__name__
                    raise
                print(json.dumps(result), flush=True)
    finally:
        report["elapsed_s"] = round(time.monotonic() - ROUND_STARTED, 6)
        baseline.durable_write(root / "observations.json", report)
        print("Evidence: " + str(root / "observations.json"), flush=True)


if __name__ == "__main__":
    try:
        anyio.run(main)
    except BaseException as error:
        print("Follow-up stopped: " + type(error).__name__, flush=True)
        sys.exit(1)
