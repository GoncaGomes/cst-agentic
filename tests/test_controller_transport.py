"""Actual wrapper, controlled subprocesses and process-death recovery on Windows."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from cst_agentic.controller import ControllerMcpClient, ControllerSession, DispatchEvidence
from cst_agentic.mcp_client import McpStartupError
from cst_agentic.recovery import RecoveryError, RecoveryStore


@pytest.fixture
def launcher(tmp_path: Path) -> Path:
    if sys.platform != "win32":
        pytest.skip("Windows public stdio lifetime tests")
    uv = shutil.which("uv")
    assert uv is not None
    peer = Path(__file__).parent / "fixtures" / "recovery_peer.py"
    command = tmp_path / "recovery-peer.cmd"
    command.write_text(f'@echo off\n"{uv}" run --no-sync python -u "{peer}"\n', encoding="utf-8")
    return command


def client(launcher: Path, state: Path, seen: Path, mode: str = "received") -> ControllerMcpClient:
    return ControllerMcpClient(
        executable=launcher,
        cwd=Path(__file__).resolve().parents[1],
        env={
            "RECOVERY_LEDGER": str(state / "recovery.json"),
            "RECOVERY_SEEN": str(seen),
            "RECOVERY_PEER_MODE": mode,
        },
        startup_timeout_s=5,
        shutdown_timeout_s=5,
        request_timeout_s=5,
    )


def project(tmp_path: Path) -> Path:
    directory = tmp_path / "project"
    directory.mkdir()
    return directory / "project.cst"


def assert_peer_terminated(seen: Path) -> None:
    """Read-only observation of the controlled peer; never kill a process tree."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x00100000, False, int(seen.read_text(encoding="utf-8")))
    if not handle:
        assert ctypes.get_last_error() == 87  # PID no longer exists.
        return
    try:
        assert kernel.WaitForSingleObject(handle, 5000) == 0, "controlled peer remained active"
    finally:
        assert kernel.CloseHandle(handle)


@pytest.mark.asyncio
async def test_real_wrapper_persists_before_peer_receives_call(
    tmp_path: Path, launcher: Path
) -> None:
    store = RecoveryStore(tmp_path / "state")
    seen = tmp_path / "seen"
    transport = client(launcher, store.directory, seen)
    before = asyncio.all_tasks()
    async with ControllerSession(
        store,
        lambda: transport,
        inventory=frozenset({"inspect"}),
        dispatch_check=lambda *args: DispatchEvidence("synthetic-pid-created"),
    ) as controller:
        await controller.start_task(project(tmp_path), "Controlled inspection")
        await controller.dispatch("inspect", {}, settled=lambda result: not result.is_error)
        assert store.incidents(unresolved_only=True) == ()
        assert seen.exists()
    assert not (asyncio.all_tasks() - before)
    assert_peer_terminated(seen)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["startup_refusal", "startup_timeout"])
async def test_actual_wrapper_startup_failure_releases_lease_and_tasks(
    tmp_path: Path,
    launcher: Path,
    mode: str,
) -> None:
    store = RecoveryStore(tmp_path / "state")
    transport = client(launcher, store.directory, tmp_path / "seen", mode)
    if mode == "startup_timeout":
        transport.startup_timeout_s = 0.4
    before = asyncio.all_tasks()
    with pytest.raises(McpStartupError, match="startup failed"):
        async with ControllerSession(
            store,
            lambda: transport,
            inventory=frozenset(),
            dispatch_check=lambda *args: None,
        ) as controller:
            await controller.start_task(project(tmp_path), "Controlled startup")
    assert not (asyncio.all_tasks() - before)
    with RecoveryStore(store.directory).session() as reopened:
        assert reopened.incidents() == ()


def test_whole_application_crash_blocks_restart_before_transport(
    tmp_path: Path, launcher: Path
) -> None:
    state = tmp_path / "state"
    seen = tmp_path / "seen"
    target = project(tmp_path)
    driver = Path(__file__).parent / "fixtures" / "recovery_driver.py"
    arguments = [str(state), str(target), str(launcher), str(seen)]
    crash = subprocess.run(
        ["uv", "run", "--no-sync", "python", str(driver), "crash", *arguments],
        capture_output=True,
        timeout=30,
    )
    assert crash.returncode == 23, "controlled crash did not reach its intended window"
    assert seen.exists()
    assert_peer_terminated(seen)
    ledger = json.loads((state / "recovery.json").read_text(encoding="utf-8"))
    assert ledger["incidents"][0]["state"] == "in_flight"
    (state / "transport-created").unlink()
    restart = subprocess.run(
        ["uv", "run", "--no-sync", "python", str(driver), "restart", *arguments],
        capture_output=True,
        timeout=30,
    )
    assert restart.returncode == 0, "fresh-process recovery refusal failed"
    assert not (state / "transport-created").exists()
    with RecoveryStore(state).session() as store:
        assert store.incidents()[0].state == "in_flight"


@pytest.mark.parametrize(
    ("window", "expected", "durable_state"),
    [
        ("lease-created", "blocked", None),
        ("header-before-fsync", "blocked", None),
        ("header-after-fsync", "blocked", None),
        ("initial-before-fsync", "blocked", None),
        ("initial-after-fsync", "blocked", None),
        ("initial-before-replace", "blocked", None),
        ("initial-after-replace", "clean", "empty"),
        ("prepare-before-fsync", "clean", "empty"),
        ("prepare-after-fsync", "clean", "empty"),
        ("prepare-before-replace", "clean", "empty"),
        ("prepare-after-replace", "blocked", "in_flight"),
        ("sdk-admission", "blocked", "in_flight"),
        ("response-received", "blocked", "in_flight"),
        ("receipt-before-fsync", "blocked", "in_flight"),
        ("receipt-after-fsync", "blocked", "in_flight"),
        ("receipt-before-replace", "blocked", "in_flight"),
        ("receipt-after-replace", "blocked", "received_unresolved"),
        ("trusted-interpretation", "blocked", "received_unresolved"),
        ("settle-before-fsync", "blocked", "received_unresolved"),
        ("settle-after-fsync", "blocked", "received_unresolved"),
        ("settle-before-replace", "blocked", "received_unresolved"),
        ("settle-after-replace", "clean", "settled"),
    ],
)
def test_abrupt_death_windows_through_actual_wrapper(
    tmp_path: Path, launcher: Path, window: str, expected: str, durable_state: str | None
) -> None:
    state = tmp_path / "state"
    seen = tmp_path / "seen"
    target = project(tmp_path)
    driver = Path(__file__).parent / "fixtures" / "recovery_window_driver.py"
    args = [window, expected, str(state), str(target), str(launcher), str(seen)]
    crash = subprocess.run(
        ["uv", "run", "--no-sync", "python", str(driver), "crash", *args],
        capture_output=True,
        timeout=40,
    )
    assert crash.returncode == 23, f"Crash window not reached: {window}"
    if seen.exists():
        assert_peer_terminated(seen)
        seen.unlink()
    if durable_state is not None:
        data = json.loads((state / "recovery.json").read_text(encoding="utf-8"))
        assert [record["state"] for record in data["incidents"]] == (
            [] if durable_state == "empty" else [durable_state]
        )
    (state / "transport-created").unlink(missing_ok=True)
    restart = subprocess.run(
        ["uv", "run", "--no-sync", "python", str(driver), "restart", *args],
        capture_output=True,
        timeout=40,
    )
    assert restart.returncode == 0, f"Incorrect fresh-process admission: {window}"
    assert (state / "transport-created").exists() == (expected == "clean")
    assert not seen.exists(), "Restart replayed a tool call"
    if window == "response-received":
        other = tmp_path / "b"
        other.mkdir()
        b_args = [window, expected, str(state), str(other / "b.cst"), str(launcher), str(seen)]
        restart_b = subprocess.run(
            ["uv", "run", "--no-sync", "python", str(driver), "restart", *b_args],
            capture_output=True,
            timeout=40,
        )
        assert restart_b.returncode == 0, "Fresh-process B bypassed unresolved A"
        assert not (state / "transport-created").exists()
        assert not seen.exists()


@pytest.mark.asyncio
async def test_cleanup_failure_retains_primary_error(tmp_path: Path, launcher: Path) -> None:
    """Focused failure injection at the wrapper's real SDK context-exit seam."""
    transport = client(launcher, tmp_path / "state", tmp_path / "seen")
    primary = RecoveryError("primary failure")
    with pytest.raises(BaseExceptionGroup) as caught:
        async with transport:
            original = transport._session_cm

            class ExitFailure:
                async def __aexit__(self, *args: object) -> None:
                    await original.__aexit__(*args)
                    raise RuntimeError("private injected error detail")

            transport._session_cm = ExitFailure()
            raise primary
    assert caught.value.exceptions[0] is primary
    assert "private injected" not in str(caught.value)


@pytest.mark.asyncio
async def test_real_eof_refusing_peer_uses_bounded_visible_cleanup(
    tmp_path: Path, launcher: Path
) -> None:
    store = RecoveryStore(tmp_path / "state")
    seen = tmp_path / "seen"
    transport = client(launcher, store.directory, seen, "eof_refusal")
    before = asyncio.all_tasks()
    async with ControllerSession(
        store,
        lambda: transport,
        inventory=frozenset({"inspect"}),
        dispatch_check=lambda *args: DispatchEvidence("synthetic-pid-created"),
    ) as controller:
        await controller.start_task(project(tmp_path), "Controlled inspection")
        await controller.dispatch("inspect", {}, settled=lambda r: True)
    assert not (asyncio.all_tasks() - before)
    assert_peer_terminated(seen)
