"""Read-only captured-trace check. No harness imports, processes or SDK sessions."""

import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace

root = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifecycle-final-01")
scratch = root / "crash_restart"
source = root / "sources/windows_lifecycle_final.py"
tree = ast.parse(source.read_text("utf-8"))
function = next(
    n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_application"
)
candidate = next(
    n
    for n in ast.walk(function)
    if isinstance(n, ast.If)
    and isinstance(n.test, ast.BoolOp)
    and ast.unparse(n.test) == "scratch.name == 'crash_restart' and (not restart)"
)


def read(path):
    return json.loads(path.read_text("utf-8"))


observer = read(scratch / "app-observer.json")
assert (scratch / "crash-permitted.flag").exists()
assert any(
    e["event"] == "abrupt_application_exit"
    for e in [
        json.loads(line) for line in (scratch / "app-events.jsonl").read_text("utf-8").splitlines()
    ]
)
peer_pid = read(scratch / "peer-identity.json")["pid"]
assert observer["alive_after_containment_release"][str(peer_pid)] is False
assert read(scratch / "observer-precrash.json")["alive"][str(peer_pid)] is True

# Re-evaluate ONLY the actual observer conditional against a recorded dead peer.
# No loop, sleep, writes, context creation or process launch can be reached.
namespace = {
    "scratch": scratch,
    "restart": False,
    "identity": scratch / "peer-identity.json",
    "read": read,
    "handles": {peer_pid: SimpleNamespace(alive=lambda: False)},
}
module = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(candidate)], type_ignores=[]))
try:
    exec(compile(module, "captured-observer-conditional", "exec"), namespace)
except RuntimeError as error:
    assert error.args == ("peer_exact_handle_not_established_before_crash",)
else:
    raise AssertionError("captured_condition_did_not_expose_race")

# Check a PROPOSED predicate change in memory only, not in the consumed source:
# the pre-crash guard must stop applying after the observer authorizes the crash.
proposed = copy.deepcopy(candidate)
proposed.test = ast.BoolOp(
    op=ast.And(),
    values=[
        proposed.test,
        ast.parse("not (scratch / 'crash-permitted.flag').exists()", mode="eval").body,
    ],
)
module = ast.fix_missing_locations(ast.Module(body=[proposed], type_ignores=[]))
exec(compile(module, "proposed-predicate-only-not-a-live-test", "exec"), namespace)
print(
    json.dumps(
        {
            "read_only_captured_conditional_check": "passed",
            "confirmed_observer_defect": (
                "Pre-crash peer-liveness requirement remains active after crash permission."
            ),
            "proposed_predicate_skips_post_permission_liveness_check": True,
            "original_runtime_throw_site_proven": False,
            "qualification": (
                "Original evidence retained only RuntimeError, not its throw-site category. "
                "The confirmed race is sufficient to explain the recorded sequence, "
                "not independently proven as the exact thrown error."
            ),
            "scenario_replays": 0,
            "SDK_sessions_or_subprocesses_started": 0,
        }
    )
)
