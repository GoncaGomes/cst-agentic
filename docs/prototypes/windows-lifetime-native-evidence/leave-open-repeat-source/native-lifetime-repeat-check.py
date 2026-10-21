"""Native-free repeat-admission, logging and budget checks. No MCP peer or CST."""

import ast
import hashlib
import importlib.util
import inspect
import json
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

BASE = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode")
PROJECT = BASE / "cst-lifetime-offline"
SOURCE = PROJECT / "src/cst_agentic"
REAL_ROOT = BASE / "cst-lifetime-native"
EVIDENCE = PROJECT / "docs/prototypes/windows-lifetime-native-evidence"
real_ledger_before = (REAL_ROOT / "round.json").read_bytes()
spec = importlib.util.spec_from_file_location(
    "repeat_peer_definitions_only", SOURCE / "windows_lifetime_native_peer.py"
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
        signature.bind(
            None, *("value" for _ in node.args), **{k.arg: "fact" for k in node.keywords}
        )
        event_calls += 1
assert event_calls == 8
assert (
    str(REAL_ROOT / "leave-open-repeat.cst")
    in peer.schema("native_create")["properties"]["path"]["enum"]
)
driver_tree = ast.parse((SOURCE / "windows_lifetime_native.py").read_text("utf-8"))
functions = [
    n
    for n in driver_tree.body
    if isinstance(n, ast.FunctionDef) and n.name in ("prepare_repeat", "prepare_case")
]
dispatch = next(
    n for n in driver_tree.body if isinstance(n, ast.ClassDef) and n.name == "NativeDispatch"
)
methods = [
    n
    for n in dispatch.body
    if isinstance(n, ast.FunctionDef) and n.name in ("__init__", "remaining")
]
with tempfile.TemporaryDirectory(prefix="native-repeat-check-", dir=BASE) as directory:
    root = Path(directory)
    (root / "evidence").mkdir()
    here = root / "project/src/cst_agentic/windows_lifetime_native.py"
    archive = here.parents[2] / "docs/prototypes/windows-lifetime-native-evidence"
    archive.mkdir(parents=True)
    initial = json.loads((EVIDENCE / "round-after-accounting.json").read_text("utf-8"))
    peer.durable_write(archive / "round-after-accounting.json", initial)
    peer.durable_write(root / "round.json", initial)
    for label in ("leave-open-logging-fix-1", "authorized-close"):
        (root / "evidence" / label).mkdir()
        shutil.copyfile(
            EVIDENCE / label / "observations.json", root / "evidence" / label / "observations.json"
        )
    approval = json.loads((REAL_ROOT / "leave-open-repeat-authorization.json").read_text("utf-8"))
    assert approval["target"] == str(REAL_ROOT / "leave-open-repeat.cst")
    approval["target"] = str(root / "leave-open-repeat.cst")
    approval_path = root / "leave-open-repeat-authorization.json"
    peer.durable_write(approval_path, approval)
    clock = SimpleNamespace(monotonic=lambda: 100.0)

    def evidence_directory(case, resumed=False):
        return root / "evidence" / (case + "-logging-fix-1" if resumed else case)

    namespace = {
        "Path": Path,
        "json": json,
        "hashlib": hashlib,
        "ROOT": root,
        "HERE": here,
        "ROUND_FILE": root / "round.json",
        "WRAPPER_RESERVE_SECONDS": 30,
        "TARGETS": {case: root / (case + ".cst") for case in peer.TARGETS},
        "evidence_directory": evidence_directory,
        "durable_write": peer.durable_write,
        "time": clock,
        "anyio": SimpleNamespace(Lock=object),
    }
    exec(
        compile(ast.Module(body=functions + methods, type_ignores=[]), "repeat-guard-only", "exec"),
        namespace,
    )
    prepare = namespace["prepare_case"]

    def must_block(case="leave-open-repeat", resumed=False):
        try:
            prepare(case, resumed)
        except RuntimeError:
            return
        raise AssertionError("Expected repeat guard to block")

    must_block("leave-open")
    must_block("authorized-close")
    must_block(resumed=True)
    for key, value in (
        ("maximum_calls", 14),
        ("case_maximum_seconds", 360),
        ("no_remote_updates", False),
    ):
        peer.durable_write(approval_path, approval | {key: value})
        must_block()
    peer.durable_write(approval_path, approval)
    target = root / "leave-open-repeat.cst"
    target.write_text("native-free guard fixture", encoding="utf-8")
    must_block()
    target.unlink()  # Only this check's temporary fixture, never a CST target.
    peer.durable_write(root / "round.json", initial | {"tool_calls": 10})
    must_block()
    peer.durable_write(root / "round.json", initial)
    ledger, scratch = prepare("leave-open-repeat", False)
    assert ledger["tool_calls"] == 9 and ledger["maximum_calls"] == 13
    assert ledger["active_seconds"] == initial["active_seconds"] + 30
    assert ledger["maximum_active_seconds"] == 900
    assert ledger["cases"]["leave-open-repeat"] == "in_flight"
    assert json.loads((scratch / "ledger-before-authorization.json").read_text()) == initial
    assert ledger["continuation"] == initial["continuation"]
    must_block()
    gateway = SimpleNamespace()
    namespace["__init__"](gateway, None, "leave-open-repeat", ledger, 100.0, {}, scratch)
    assert [name for name, _ in gateway.plan] == [
        "native_connect",
        "native_create",
        "native_status",
        "native_disconnect",
    ]
    assert namespace["remaining"](gateway) == 270
    clock.monotonic = lambda: 216.0
    assert namespace["remaining"](gateway) == 154  # Cannot admit another 120 s call.
    fixture = peer.NativeFixture("leave-open-repeat", None, None)
    fixture.scratch = scratch
    fixture.event("operation_entered", name="native_connect")
    logged = json.loads((scratch / "peer-events.jsonl").read_text())
    assert logged["event"] == "operation_entered" and logged["name"] == "native_connect"
    fixture.step = 3
    try:
        fixture.perform("native_close", {})
    except RuntimeError:
        pass
    else:
        raise AssertionError("Repeat must not admit native_close")
assert (REAL_ROOT / "round.json").read_bytes() == real_ledger_before
print(
    json.dumps(
        {
            "repeat_guards_valid": True,
            "event_bindings_checked": event_calls,
            "repeat_300_second_budget_enforced": True,
            "no_instance_close_in_repeat_plan": True,
            "real_ledger_modified": False,
            "native_api_calls": 0,
            "mcp_peers_started": 0,
        }
    )
)
