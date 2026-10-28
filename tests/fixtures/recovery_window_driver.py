"""Abrupt whole-process death at real filesystem/public SDK boundaries, no CST."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession

from cst_agentic.controller import ControllerMcpClient, ControllerSession, DispatchEvidence
from cst_agentic.recovery import RecoveryError, RecoveryStore


def install_crash(window: str) -> None:
    original_open = Path.open
    original_fsync = os.fsync
    original_replace = os.replace
    original_call = ClientSession.call_tool
    fsync_count = 0

    def crash(point: str) -> None:
        if point == window:
            os._exit(23)  # No exception unwinding, context exits, or finalizers.

    def open_file(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        if path.name == "session.lock" and mode == "x+b":
            crash("lease-created")
        return stream

    def fsync(fd):
        nonlocal fsync_count
        fsync_count += 1
        phase = {1: "header", 2: "initial", 3: "prepare", 4: "receipt", 5: "settle"}[fsync_count]
        crash(f"{phase}-before-fsync")
        original_fsync(fd)
        crash(f"{phase}-after-fsync")

    def replace(source, destination):
        data = json.loads(Path(source).read_text(encoding="utf-8"))
        phase = (
            {"in_flight": "prepare", "received_unresolved": "receipt", "settled": "settle"}[
                data["incidents"][-1]["state"]
            ]
            if data["incidents"]
            else "initial"
        )
        crash(f"{phase}-before-replace")
        original_replace(source, destination)
        crash(f"{phase}-after-replace")

    async def call(session, *args, **kwargs):
        crash("sdk-admission")
        result = await original_call(session, *args, **kwargs)
        crash("response-received")
        return result

    Path.open = open_file
    os.fsync = fsync
    os.replace = replace
    ClientSession.call_tool = call


async def main() -> None:
    mode, window, expected, state_arg, project_arg, launcher_arg, seen_arg = sys.argv[1:]
    state, project, launcher, seen = map(Path, (state_arg, project_arg, launcher_arg, seen_arg))
    if mode == "crash":
        install_crash(window)

    def factory():
        (state / "transport-created").touch()
        return ControllerMcpClient(
            executable=launcher,
            cwd=Path(__file__).resolve().parents[2],
            env={
                "RECOVERY_LEDGER": str(state / "recovery.json"),
                "RECOVERY_SEEN": str(seen),
                "RECOVERY_PEER_MODE": "received",
            },
            startup_timeout_s=10,
            shutdown_timeout_s=5,
            request_timeout_s=10,
        )

    def interpret(result):
        if window == "trusted-interpretation":
            os._exit(23)
        return not result.is_error

    try:
        async with ControllerSession(
            RecoveryStore(state),
            factory,
            inventory=frozenset({"inspect"}),
            dispatch_check=lambda *args: DispatchEvidence("controlled-connection"),
        ) as controller:
            await controller.start_task(project, "Fresh explicit controlled inspection")
            if mode == "restart":
                if expected != "clean":
                    raise AssertionError("Unresolved or incomplete state admitted transport")
                return  # No replay or implicit new SDK call.
            await controller.dispatch("inspect", {}, settled=interpret)
            raise AssertionError("Crash window was not reached")
    except RecoveryError:
        if mode != "restart" or expected == "clean":
            raise


if __name__ == "__main__":
    asyncio.run(main())
