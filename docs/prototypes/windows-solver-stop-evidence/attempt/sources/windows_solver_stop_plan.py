"""THROWAWAY: fixed, human-approved dipole experiment; no native imports."""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import os
from pathlib import Path

ROOT = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-solver-stop-dipole-01")
TARGET = ROOT / "dipole.cst"
UPSTREAM = Path(r"C:\dev\cst-studio-mcp")
REVISION = "a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2"
INSTALL = Path(r"C:\Program Files (x86)\CST Studio Suite 2025")
FIXTURE = UPSTREAM / "capabilities_test/04_antenna_simulation/run_dipole.py"
MAX_CALLS = 50
MAX_SECONDS = 1800
RESERVE_SECONDS = 45  # Includes <=30 s cleanup, <=5 s observation, finalization/outer headroom.
FIXED_NAMES = (
    "fixture_connect",
    "fixture_create",
    "fixture_save",
    "fixture_identity",
    "fixture_close",
)
LAUNCH = ("cst_run_simulation_async", {"solver_type": "Time Domain", "timeout_s": 30})
STATUS = ("cst_get_simulation_status", {"timeout_s": 10})
WAIT = ("cst_wait_for_simulation", {"max_wait_s": 5})
STOP = ("cst_stop_simulation", {"timeout_s": 30})
LOG = ("cst_read_project_log", {})
MODULES = (
    "vba",
    "materials",
    "geometry",
    "ports",
    "boundaries",
    "mesh",
    "solvers",
    "results",
    "simulation",
    "diagnostics",
)
BAD = {"error", "failed", "failure", "timeout", "offline", "busy", "partial", "unsupported"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def durable(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".writing")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def read_manifest() -> list[dict]:
    """Parse only the literal: never import or execute the historical runner."""
    tree = ast.parse(FIXTURE.read_text("utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "MANIFEST" for t in node.targets
        ):
            if not isinstance(node.value, ast.Call) or len(node.value.args) != 1:
                raise RuntimeError("fixture_manifest_not_literal")
            return json.loads(ast.literal_eval(node.value.args[0]))
    raise RuntimeError("fixture_manifest_missing")


def setup_plan() -> list[tuple[str, dict]]:
    manifest = read_manifest()
    excluded = {
        "cst_read_project_log",
        "cst_project_tree",
        "cst_save_project",
        "cst_check_model_setup",
        "cst_get_mesh_quality",
    }
    units = [m for m in manifest if m["phase"] == "A" and m["tool"] == "cst_execute_vba"]
    model = [m for m in manifest if m["phase"] in {"B", "C"} and m["tool"] not in excluded]
    if len(units) != 2 or len(model) != 23:
        raise RuntimeError("unexpected_fixture_setup")
    return [(m["tool"], m["arguments"]) for m in units + model]


def prefix_plan() -> list[tuple[str, dict]]:
    return [
        ("fixture_connect", {}),
        ("fixture_create", {}),
        *setup_plan(),
        ("fixture_save", {}),
        ("fixture_identity", {}),
    ]


def all_operations() -> list[tuple[str, dict]]:
    return [*prefix_plan(), LAUNCH, STATUS, WAIT, STOP, LOG, ("fixture_close", {})]


def allowance(name: str) -> int:
    return {LAUNCH[0]: 480, WAIT[0]: 45, STOP[0]: 60}.get(name, 120)


def schema(name: str) -> dict:
    return {"type": "object", "properties": {}, "required": [], "additionalProperties": False}


def load_tools() -> tuple[dict, dict]:
    """Only schemas/handlers; no CST connection or instance construction."""
    from mcp.types import Tool

    names = {n for n, _ in all_operations()} - set(FIXED_NAMES)
    tools, handlers = {}, {}
    for module_name in MODULES:
        module = importlib.import_module("cst_mcp.tools." + module_name)
        for tool in module.TOOLS:
            if tool.name in names:
                if tool.name in tools:
                    raise RuntimeError("duplicate_tool")
                tools[tool.name], handlers[tool.name] = tool, module.handle
    if set(tools) != names:
        raise RuntimeError("required_tool_missing")
    for name in FIXED_NAMES:
        tools[name] = Tool(
            name=name, description="Fixed disposable dipole fixture only", input_schema=schema(name)
        )
    return tools, handlers


def validate_plan(tools: dict) -> None:
    from jsonschema.validators import validator_for

    for name, args in all_operations():
        contract = tools[name].input_schema
        validator = validator_for(contract)
        validator.check_schema(contract)
        validator(contract).validate(args)
        if set(args) - set(contract.get("properties", {})):
            raise RuntimeError("undocumented_argument")


def validate_approval(value: dict) -> None:
    expected = {
        "id": "dipole-stop-01",
        "user_confirmation": "Yes",
        "target": str(TARGET),
        "maximum_calls": MAX_CALLS,
        "maximum_seconds": MAX_SECONDS,
        "launches": 1,
        "stop_attempts": 1,
        "retries": 0,
        "publication": False,
    }
    if any(value.get(k) != v for k, v in expected.items()):
        raise RuntimeError("approval_scope_mismatch")


def validate_new_root(root: Path) -> None:
    if root.exists():
        raise RuntimeError("consumed_or_existing_experiment_root")
    if root.parent.is_symlink() or root.parent.is_junction():
        raise RuntimeError("linked_experiment_parent")


class Sequence:
    """Same state machine enforced independently by driver and peer."""

    def __init__(self) -> None:
        self.prefix = prefix_plan()
        self.index = 0
        self.phase = "prefix"
        self.start_reads = self.end_reads = 0
        self.last_running = None

    def check(self, name: str, args: dict) -> None:
        operation = (name, args)
        if self.phase == "prefix":
            valid = operation == self.prefix[self.index]
        elif self.phase == "launch":
            valid = operation == LAUNCH
        elif self.phase == "starting":
            valid = operation == STATUS and self.start_reads < 3
        elif self.phase == "wait":
            valid = operation == WAIT
        elif self.phase == "stop":
            valid = operation == STOP
        elif self.phase == "verifying":
            valid = operation == STATUS and self.end_reads < 3
        elif self.phase == "log":
            valid = operation == LOG
        elif self.phase == "close":
            valid = operation == ("fixture_close", {}) and self.last_running is False
        else:
            valid = False
        if not valid:
            raise RuntimeError("operation_outside_fixed_sequence")

    def settled(self, name: str, payload: dict) -> None:
        if not isinstance(payload.get("status"), str):
            raise RuntimeError("missing_handler_status")
        if payload.get("status") in BAD:
            self.phase = "halted"
            raise RuntimeError("received_failure")
        if self.phase == "prefix":
            self.index += 1
            if self.index == len(self.prefix):
                self.phase = "launch"
        elif self.phase == "launch":
            if payload.get("status") != "started":
                raise RuntimeError("launch_not_established")
            self.phase = "starting"
        elif self.phase == "starting":
            self.start_reads += 1
            self.last_running = payload.get("running")
            if self.last_running is True:
                self.phase = "wait"
            elif self.last_running is not False:
                raise RuntimeError("solver_activity_unknown")
            elif self.start_reads == 3:
                # Idle samples during asynchronous startup do not prove a run settled.
                raise RuntimeError("running_not_established_within_bounded_checks")
        elif self.phase == "wait":
            self.last_running = payload.get("running")
            if self.last_running is True:
                self.phase = "stop"
            elif self.last_running is False:
                self.phase = "log"  # Natural finish before stop: inconclusive.
            else:
                raise RuntimeError("wait_activity_unknown")
        elif self.phase == "stop":
            if payload.get("status") != "executed":
                raise RuntimeError("stop_not_accepted")
            self.phase = "verifying"
        elif self.phase == "verifying":
            self.end_reads += 1
            self.last_running = payload.get("running")
            if self.last_running is False:
                self.phase = "log"
            elif self.last_running is not True:
                raise RuntimeError("solver_activity_unknown")
            elif self.end_reads == 3:
                raise RuntimeError("solver_still_running_after_bounded_checks")
        elif self.phase == "log":
            self.phase = "close"
        elif self.phase == "close":
            self.phase = "done"
