"""THROWAWAY: fixed-target native lifetime peer, NOT the production CST server.

Only the two human-approved blank projects are supported. No attachment, solver,
VBA, save retry, model client, SDK patch, or automatic native cleanup operation.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-native")
INSTALL = Path(r"C:\Program Files (x86)\CST Studio Suite 2025")
NAMES = ("native_connect", "native_create", "native_status", "native_disconnect", "native_close")
TARGETS = {case: ROOT / (case + ".cst") for case in ("leave-open", "authorized-close")}
RESUME_FLAG = "--resume-approved-logging-fix"


def evidence_directory(case: str, resumed: bool = False) -> Path:
    if case not in TARGETS or (resumed and case != "leave-open"):
        raise RuntimeError("fixed_case_required")
    return ROOT / "evidence" / (case + "-logging-fix-1" if resumed else case)


def durable_write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".writing")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def schema(name: str) -> dict:
    properties = {}
    if name == "native_connect":
        properties = {"mode": {"type": "string", "const": "new"}}
    elif name == "native_create":
        properties = {"path": {"type": "string", "enum": [str(p) for p in TARGETS.values()]}}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


class NativeFixture:
    """One fixed project, one owner thread, four admitted native operations."""

    def __init__(self, case: str, config, interface, resumed: bool = False) -> None:
        self.case = case
        self.config = config
        self.interface = interface
        self.target = TARGETS[case]
        self.scratch = evidence_directory(case, resumed)
        self.de = None
        self.project = None
        self.de_pid = None
        self.step = 0
        self.halted = False
        self.thread = None

    def event(self, event_type: str, **facts) -> None:
        with (self.scratch / "peer-events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps({"event": event_type, "monotonic": time.monotonic(), **facts}) + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())

    def verify_instance(self) -> None:
        if self.de is None or not self.de.is_connected() or self.de.pid() != self.de_pid:
            raise RuntimeError("instance_identity_not_established")

    def project_facts(self) -> dict:
        self.verify_instance()
        filename = Path(self.project.filename()).resolve()
        paths = [Path(p).resolve() for p in self.de.list_open_projects()]
        if filename != self.target or paths != [self.target]:
            raise RuntimeError("unexpected_live_project")
        if self.project.design_environment.pid() != self.de_pid:
            raise RuntimeError("project_instance_mismatch")
        return {"filename_matches": True, "only_expected_project_open": True}

    def perform(self, name: str, arguments: dict) -> dict:
        # All native calls are made by the registry's single dedicated worker.
        current = threading.get_ident()
        if self.thread is None:
            self.thread = current
        if current != self.thread or self.halted:
            raise RuntimeError("peer_halted_or_owner_changed")
        last = "native_disconnect" if self.case == "leave-open" else "native_close"
        expected = ("native_connect", "native_create", "native_status", last)
        if self.step >= len(expected) or name != expected[self.step]:
            raise RuntimeError("unexpected_operation_order")
        self.event("operation_entered", name=name)
        if name == "native_connect":
            if arguments != {"mode": "new"} or self.target.exists():
                raise RuntimeError("connect_scope_mismatch")
            before = {int(pid) for pid in self.interface.running_design_environments()}
            info = self.interface.DesignEnvironment.ProcessInfo()
            finished = threading.Event()

            def record_launch_pid():
                while not finished.wait(0.025):
                    pid = int(info.pid)
                    if pid > 0:
                        durable_write(self.scratch / "launch-identity.json", {"de_pid": pid})
                        return

            recorder = threading.Thread(target=record_launch_pid, daemon=True)
            recorder.start()
            try:
                # Public vendor new(), never connect/any or a fallback factory.
                self.de = self.interface.DesignEnvironment.new(process_info=info)
            finally:
                finished.set()
                recorder.join(timeout=1)
            self.de_pid = int(self.de.pid())
            durable_write(self.scratch / "launch-identity.json", {"de_pid": self.de_pid})
            self.verify_instance()
            if self.de_pid in before or self.de_pid != int(info.pid):
                raise RuntimeError("fresh_instance_not_established")
            if self.de.list_open_projects():
                raise RuntimeError("new_instance_has_unexpected_projects")
            value = {
                "status": "connected",
                "de_pid": self.de_pid,
                "newly_started": True,
                "existing_de_count": len(before),
                "open_project_count": 0,
            }
        elif name == "native_create":
            if arguments != {"path": str(self.target)} or self.target.exists():
                raise RuntimeError("creation_target_unavailable")
            self.verify_instance()
            if self.de.list_open_projects():
                raise RuntimeError("instance_not_empty")
            self.project = self.de.new_mws()
            if self.project.design_environment.pid() != self.de_pid:
                raise RuntimeError("new_project_instance_mismatch")
            self.event("save_entered")
            self.project.save(str(self.target), include_results=False, allow_overwrite=False)
            self.event("save_returned")
            value = {"status": "created", **self.project_facts()}
        elif name == "native_status":
            value = {"status": "observed", "de_pid": self.de_pid, **self.project_facts()}
        else:
            facts = self.project_facts()
            if name == "native_close":
                self.event("instance_close_entered")
                self.de.close()
                self.event("instance_close_returned")
                value = {"status": "close_returned", **facts}
            else:
                # Forget handles only. Do not call a native close, including on GC.
                value = {"status": "disconnected", **facts}
            self.project = None
            self.de = None
        self.step += 1
        self.event("operation_returned", name=name)
        return value


async def run_peer(case: str, stdout, resumed: bool = False) -> None:
    import anyio
    import cst.interface
    from cst_mcp.config import CSTConfig
    from cst_mcp.tools.registry import CSTWorker, ToolRegistry
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    config = CSTConfig.from_env()
    if config.cst_path != INSTALL or config.work_dir != ROOT or config.connect_mode != "manual":
        raise RuntimeError("fixed_native_configuration_mismatch")
    fixture = NativeFixture(case, config, cst.interface, resumed)
    durable_write(
        fixture.scratch / "peer-identity.json", {"pid": os.getpid(), "parent_pid": os.getppid()}
    )
    server = Server("THROWAWAY-FIXED-NATIVE-LIFETIME", version="0")
    tools = [
        Tool(name=name, description="Disposable lifetime probe only", input_schema=schema(name))
        for name in NAMES
    ]

    async def handle(name, arguments, client):
        try:
            value = client.perform(name, arguments)
        except BaseException as error:
            client.halted = True
            client.event("peer_halted", error_type=type(error).__name__)
            # No raw native errors, no recovery query, no retry, no automatic close.
            value = {"status": "error", "error_type": type(error).__name__}
        return [TextContent(type="text", text=json.dumps(value))]

    registry = ToolRegistry()
    registry.add_module(tools, handle, category="prototype")
    registry.bind(server, fixture, toolsets=None, worker=CSTWorker("native-prototype-owner"))
    async with stdio_server(stdout=anyio.wrap_file(stdout)) as streams:
        await server.run(*streams, server.create_initialization_options())
    fixture.event("server_eof_returned")


if __name__ == "__main__":
    # CST's documented vendor-library configuration is performed before importing
    # cst.interface. Never load .env or copy ambient Python/provider settings.
    logging.disable(logging.CRITICAL)
    try:
        import anyio
        from cst_mcp.config import CSTConfig
        from cst_mcp.server import protocol_output

        resumed = len(sys.argv) == 3 and sys.argv[2] == RESUME_FLAG
        if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and not resumed):
            raise RuntimeError("fixed_case_required")
        if sys.argv[1] not in TARGETS or (resumed and sys.argv[1] != "leave-open"):
            raise RuntimeError("fixed_case_required")
        with protocol_output() as protocol_stdout:
            CSTConfig.from_env()
            anyio.run(run_peer, sys.argv[1], protocol_stdout, resumed)
    except BaseException as error:
        print("Native peer stopped: " + type(error).__name__, file=sys.stderr, flush=True)
        sys.exit(1)
