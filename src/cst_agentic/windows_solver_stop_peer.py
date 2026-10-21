"""THROWAWAY fixed-target peer; reviewed handlers, no watcher/private SDK hooks."""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

from windows_solver_stop_plan import (
    BAD,
    INSTALL,
    ROOT,
    TARGET,
    Sequence,
    digest,
    durable,
    load_tools,
    setup_plan,
    validate_approval,
    validate_plan,
)


def event(event_type: str, **facts) -> None:
    with (ROOT / "peer-events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {"event": event_type, "monotonic": time.monotonic(), **facts}, allow_nan=False
            )
            + "\n"
        )
        stream.flush()
        os.fsync(stream.fileno())


def safe_payload(value: dict) -> dict:
    """No raw native errors/dialogs; owned-project log is classified, not dumped."""
    result = {
        k: value[k]
        for k in (
            "status",
            "running",
            "command",
            "confirmed",
            "solve_observed",
            "elapsed_s",
            "polls",
            "max_wait_s",
            "active_solver",
        )
        if k in value
    }
    if value.get("status") in BAD:
        return {**result, "failure_category": "received_upstream_failure"}
    info = value.get("run_info")
    if isinstance(info, dict):
        result["run_info"] = {
            k: v
            for k, v in info.items()
            if k in {"state", "last_reported_state", "state_note", "reported_at"}
            and (v is None or isinstance(v, (str, int, float, bool)))
        }
    return result


async def run_peer() -> None:
    import anyio
    from cst_mcp.config import CSTConfig

    config = CSTConfig.from_env()
    if config.cst_path != INSTALL or config.work_dir != ROOT or config.connect_mode != "manual":
        raise RuntimeError("fixed_configuration_mismatch")
    validate_approval(json.loads((ROOT / "authorization.json").read_text("utf-8")))
    ledger = json.loads((ROOT / "round.json").read_text("utf-8"))
    if ledger["state"] != "in_flight" or ledger["source_sha256"][Path(__file__).name] != digest(
        Path(__file__)
    ):
        raise RuntimeError("peer_source_or_admission_mismatch")

    import cst.interface
    from cst_mcp.cst_client import CSTClient
    from cst_mcp.tools.registry import CSTWorker, ToolRegistry
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent

    class FixtureClient(CSTClient):
        def read_dialogs(self) -> dict:
            # An upstream error path must not inspect unrelated window text.
            return {"status": "unsupported", "count": 0}

    client = FixtureClient(config)
    tools, handlers = load_tools()
    validate_plan(tools)
    sequence = Sequence()
    pid = None
    owner_thread = None
    halted = False
    durable(ROOT / "peer-identity.json", {"pid": os.getpid(), "parent_pid": os.getppid()})

    def verify_instance() -> None:
        if client._de is None or not client._de.is_connected() or client._de.pid() != pid:
            raise RuntimeError("owned_instance_not_established")

    def verify_project() -> dict:
        verify_instance()
        if client._project is None or client._project.design_environment.pid() != pid:
            raise RuntimeError("owned_project_not_established")
        if Path(client._project.filename()).resolve() != TARGET or [
            Path(p).resolve() for p in client._de.list_open_projects()
        ] != [TARGET]:
            raise RuntimeError("unexpected_live_project")
        return {"filename_matches": True, "sole_project_matches": True, "de_pid": pid}

    async def handle(name: str, arguments: dict, unused) -> list:
        nonlocal pid, owner_thread, halted
        try:
            current = threading.get_ident()
            if owner_thread is None:
                owner_thread = current
            if halted or current != owner_thread:
                raise RuntimeError("peer_halted_or_owner_changed")
            marker = json.loads((ROOT / "recovery.json").read_text("utf-8"))
            ledger_now = json.loads((ROOT / "round.json").read_text("utf-8"))
            if (
                marker["operation"] != name
                or marker["arguments"] != arguments
                or marker["ordinal"] != ledger_now["tool_calls"]
                or ledger_now["tool_calls"] > 50
                or marker["state"] != "in_flight"
            ):
                raise RuntimeError("driver_admission_marker_mismatch")
            sequence.check(name, arguments)
            event("operation_entered", operation=name)
            if name == "fixture_connect":
                if TARGET.exists():
                    raise RuntimeError("target_already_exists")
                before = {int(p) for p in cst.interface.running_design_environments()}
                info = cst.interface.DesignEnvironment.ProcessInfo()
                finished = threading.Event()

                def record_pid() -> None:
                    while not finished.wait(0.025):
                        if int(info.pid) > 0:
                            durable(ROOT / "launch-identity.json", {"de_pid": int(info.pid)})
                            return

                recorder = threading.Thread(target=record_pid, daemon=True)
                recorder.start()
                try:
                    client._de = cst.interface.DesignEnvironment.new(process_info=info)
                finally:
                    finished.set()
                    recorder.join(timeout=1)
                pid = int(client._de.pid())
                durable(ROOT / "launch-identity.json", {"de_pid": pid})
                verify_instance()
                if pid in before or pid != int(info.pid) or client._de.list_open_projects():
                    raise RuntimeError("fresh_empty_instance_not_established")
                payload = {"status": "connected", "de_pid": pid, "existing_de_count": len(before)}
            elif name == "fixture_create":
                verify_instance()
                if TARGET.exists() or client._de.list_open_projects():
                    raise RuntimeError("creation_scope_unavailable")
                client._project = client._de.new_mws()
                event("initial_save_entered")
                client._project.save(str(TARGET), include_results=False, allow_overwrite=False)
                client._project_path = str(TARGET)
                payload = {"status": "created", **verify_project()}
            else:
                facts = verify_project()
                if name == "fixture_save":
                    # Save only our already-created, independently identified project.
                    # No external target, save fallback, alternate path or overwrite retry.
                    event("prepared_fixture_save_entered")
                    client._project.save()
                    payload = {"status": "saved", **verify_project()}
                elif name == "fixture_identity":
                    payload = {"status": "observed", **facts}
                elif name == "fixture_close":
                    if sequence.last_running is not False:
                        raise RuntimeError("idle_not_established")
                    event("orderly_instance_close_entered")
                    client._de.close()
                    event("orderly_instance_close_returned")
                    payload = {"status": "closed", **facts}
                    client._project = client._de = None
                else:
                    if name == "cst_wait_for_simulation":
                        durable(ROOT / "wait-entered.json", {"monotonic": time.monotonic()})
                    if name == "cst_stop_simulation":
                        event("stop_handler_entered")
                    blocks = await handlers[name](name, arguments, client)
                    if len(blocks) != 1 or blocks[0].type != "text":
                        raise RuntimeError("unexpected_handler_payload")
                    raw = json.loads(blocks[0].text)
                    payload = safe_payload(raw)
                    if name == "cst_execute_vba" and raw.get("status") not in BAD:
                        code = arguments["code"]
                        queries = [a["code"] for n, a in setup_plan() if n == "cst_execute_vba"]
                        if code == queries[1]:
                            values = dict(
                                line.split("\t", 1)
                                for line in str(raw.get("output", "")).splitlines()
                                if "\t" in line
                            )
                            if values != {"Length": "mm", "Frequency": "GHz", "Time": "ns"}:
                                raise RuntimeError("units_readback_mismatch")
                            payload["verified_units"] = values
                        elif code == queries[2]:
                            rows = [
                                line.split("\t") for line in str(raw.get("output", "")).splitlines()
                            ]
                            shapes = {r[2]: r[3] for r in rows if len(r) == 4 and r[0] == "SOLID"}
                            if shapes != {
                                "Dipole:ArmNegative": "DipoleCopper",
                                "Dipole:ArmPositive": "DipoleCopper",
                            }:
                                raise RuntimeError("shapes_readback_mismatch")
                            payload["verified_shapes"] = shapes
                    elif name == "cst_read_project_log" and raw.get("status") not in BAD:
                        # This is the identified disposable project's bounded native log,
                        # not server stderr, a provider error or unrelated window text.
                        durable(
                            ROOT / "owned-native-log.json",
                            {
                                "source": raw.get("source", "saved_project_log"),
                                "tail": str(raw.get("tail", ""))[-4000:],
                                "reported_size": raw.get("size"),
                                "target_checks": facts,
                                "coverage": "bounded tail; no complete run-history guarantee",
                            },
                        )
                        text = json.dumps(raw).casefold()
                        payload["owned_log_classification"] = {
                            "abort_or_cancel_mentioned": "abort" in text or "cancel" in text,
                            "normal_completion_mentioned": "finished" in text
                            or "completed" in text,
                            "owned_log_tail_retained": True,
                            "qualification": (
                                "Keyword hints only, not causal proof or timestamped attribution."
                            ),
                        }
                    payload["target_checks"] = facts
            sequence.settled(name, payload)
            event("operation_returned", operation=name, payload=payload)
            return [TextContent(type="text", text=json.dumps(payload))]
        except BaseException as error:
            halted = True
            event("peer_halted", operation=name, error_type=type(error).__name__)
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"status": "error", "error_type": type(error).__name__}),
                )
            ]

    server = Server("THROWAWAY-DIPOLE-STOP-01", version="0")
    registry = ToolRegistry()
    registry.add_module(list(tools.values()), handle, category="prototype")
    registry.bind(server, client, toolsets=None, worker=CSTWorker("dipole-stop-owner"))
    from cst_mcp.server import protocol_output

    with protocol_output() as stdout:
        async with stdio_server(stdout=anyio.wrap_file(stdout)) as streams:
            await server.run(*streams, server.create_initialization_options())
    event("server_eof_returned")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        import anyio

        if sys.argv[1:] != ["--approved-peer"]:
            raise RuntimeError("explicit_peer_flag_required")
        anyio.run(run_peer)
    except BaseException as error:
        print("Disposable peer stopped: " + type(error).__name__, file=sys.stderr, flush=True)
        sys.exit(1)
