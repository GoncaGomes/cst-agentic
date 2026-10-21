"""Focused native-free logging/continuation checks; no peers, CST or offline drivers."""

import ast
import hashlib
import importlib.util
import inspect
import json
import shutil
import tempfile
from pathlib import Path

BASE = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode")
PROJECT = BASE / "cst-lifetime-offline"
SOURCE = PROJECT / "src/cst_agentic"
REAL_ROOT = BASE / "cst-lifetime-native"
spec = importlib.util.spec_from_file_location(
    "peer_logging_check", SOURCE / "windows_lifetime_native_peer.py"
)
peer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(peer)
signature = inspect.signature(peer.NativeFixture.event)
tree = ast.parse((SOURCE / "windows_lifetime_native_peer.py").read_text("utf-8"))
event_calls = 0
for node in ast.walk(tree):
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "event"
    ):
        assert all(keyword.arg is not None for keyword in node.keywords)
        signature.bind(
            None, *("value" for _ in node.args), **{k.arg: "fact" for k in node.keywords}
        )
        event_calls += 1
assert event_calls >= 7
driver_tree = ast.parse((SOURCE / "windows_lifetime_native.py").read_text("utf-8"))
prepare_node = next(
    n for n in driver_tree.body if isinstance(n, ast.FunctionDef) and n.name == "prepare_case"
)
with tempfile.TemporaryDirectory(prefix="native-logging-check-", dir=BASE) as directory:
    root = Path(directory)
    evidence = root / "evidence"
    evidence.mkdir()
    old = evidence / "leave-open"
    shutil.copytree(REAL_ROOT / "evidence/leave-open", old)
    original_bytes = {p.name: p.read_bytes() for p in old.iterdir() if p.is_file()}
    shutil.copyfile(REAL_ROOT / "round.json", root / "round.json")
    shutil.copyfile(
        REAL_ROOT / "logging-fix-continuation.json", root / "logging-fix-continuation.json"
    )
    here = root / "project/src/cst_agentic/windows_lifetime_native.py"
    archive = (
        here.parents[2] / "docs/prototypes/windows-lifetime-native-evidence/failed-attempt-source"
    )
    shutil.copytree(
        PROJECT / "docs/prototypes/windows-lifetime-native-evidence/failed-attempt-source", archive
    )

    def evidence_directory(case, resumed=False):
        return evidence / (case + "-logging-fix-1" if resumed else case)

    namespace = {
        "Path": Path,
        "json": json,
        "hashlib": hashlib,
        "ROOT": root,
        "HERE": here,
        "ROUND_FILE": root / "round.json",
        "CONTINUATION_FILE": root / "logging-fix-continuation.json",
        "WRAPPER_RESERVE_SECONDS": 30,
        "TARGETS": {case: root / (case + ".cst") for case in ("leave-open", "authorized-close")},
        "evidence_directory": evidence_directory,
        "durable_write": peer.durable_write,
    }
    exec(
        compile(ast.Module(body=[prepare_node], type_ignores=[]), "prepare-case-only", "exec"),
        namespace,
    )
    prepare = namespace["prepare_case"]

    def must_block(case, resumed):
        try:
            prepare(case, resumed)
        except RuntimeError:
            return
        raise AssertionError("Expected continuation guard to block")

    must_block("leave-open", False)
    must_block("authorized-close", True)
    approval_path = root / "logging-fix-continuation.json"
    approval = json.loads(approval_path.read_text("utf-8"))
    bad_approval = approval | {"user_authorized": False}
    peer.durable_write(approval_path, bad_approval)
    must_block("leave-open", True)
    peer.durable_write(approval_path, approval)
    ledger, scratch = prepare("leave-open", True)
    assert ledger["tool_calls"] == 1 and ledger["active_seconds"] == 210
    assert ledger["continuation"]["failed_ledger"]["active_seconds"] == 3.89
    assert ledger["cases"] == {"leave-open": "in_flight"}
    assert {p.name: p.read_bytes() for p in old.iterdir() if p.is_file()} == original_bytes
    must_block("leave-open", True)
    must_block("authorized-close", False)
    fixture = peer.NativeFixture("leave-open", None, None)
    fixture.scratch = scratch
    fixture.event("operation_entered", name="native_connect")
    logged = json.loads((scratch / "peer-events.jsonl").read_text("utf-8"))
    assert logged["event"] == "operation_entered" and logged["name"] == "native_connect"
    ledger["cases"] = {"leave-open": "completed"}
    peer.durable_write(root / "round.json", ledger)
    peer.durable_write(scratch / "observations.json", {"manual_confirmation_required": True})
    peer.durable_write(
        scratch / "outer-observation.json",
        {
            "exit_code": 0,
            "wrapper_reserve_exceeded": False,
            "ledger_matches": True,
            "round_ceiling_exceeded": False,
            "complete_allowance_exceeded": False,
        },
    )
    must_block("authorized-close", False)
    peer.durable_write(scratch / "observations.json", {"manual_confirmation_required": False})
    second, second_scratch = prepare("authorized-close", False)
    assert second["tool_calls"] == 1 and second["active_seconds"] == 240
    assert second_scratch.name == "authorized-close"
print(
    json.dumps(
        {
            "all_event_call_bindings_valid": True,
            "checked_event_calls": event_calls,
            "logging_write_valid": True,
            "continuation_guards_valid": True,
            "native_api_calls": 0,
            "mcp_peers_started": 0,
            "real_ledger_modified": False,
        }
    )
)
