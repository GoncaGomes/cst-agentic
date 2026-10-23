"""Fresh-process crash/restart driver for the production safety seam."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from cst_agentic.controller import ControllerMcpClient, ControllerSession, DispatchEvidence
from cst_agentic.recovery import RecoveryError, RecoveryStore


async def main() -> None:
    mode, state_arg, project_arg, launcher_arg, seen_arg = sys.argv[1:]
    state, project, launcher, seen = map(Path, (state_arg, project_arg, launcher_arg, seen_arg))

    def factory() -> ControllerMcpClient:
        # Restart must not even construct/open a fresh transport.
        (state / "transport-created").touch()
        return ControllerMcpClient(
            executable=launcher,
            cwd=Path(__file__).resolve().parents[2],
            env={
                "RECOVERY_LEDGER": str(state / "recovery.json"),
                "RECOVERY_SEEN": str(seen),
                "RECOVERY_PEER_MODE": "in_flight",
            },
            startup_timeout_s=10,
            shutdown_timeout_s=5,
            request_timeout_s=10,
        )

    controller = ControllerSession(
        RecoveryStore(state),
        factory,
        inventory=frozenset({"inspect", "status", "stop"}),
        dispatch_check=lambda *args: DispatchEvidence("synthetic-pid-created"),
    )
    try:
        async with controller:
            await controller.start_task(project, "Explicit controlled task")
            if mode == "restart":
                raise AssertionError("restart admitted transport")
            pending = asyncio.create_task(controller.dispatch("inspect", {}))
            # The peer confirms actual SDK delivery and durable pre-dispatch state.
            async with asyncio.timeout(10):
                while not seen.exists():
                    if pending.done():
                        await pending  # Surface failure instead of hiding it.
                    await asyncio.sleep(0.01)
            os._exit(23)  # Deliberately skip all application cleanup/finalizers.
    except RecoveryError:
        if mode != "restart":
            raise


if __name__ == "__main__":
    asyncio.run(main())
