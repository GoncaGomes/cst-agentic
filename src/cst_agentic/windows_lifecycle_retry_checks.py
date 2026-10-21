"""In-memory regression checks only: no processes, SDK contexts or native scenarios."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import windows_lifecycle_retry as driver


class Leaf:
    def __init__(self, name: str, files: set[str]) -> None:
        self.name, self.files = name, files

    def exists(self) -> bool:
        return self.name in self.files

    def touch(self, *, exist_ok: bool) -> None:
        if not exist_ok and self.exists():
            raise AssertionError("duplicate_permission")
        self.files.add(self.name)


class Scratch:
    name = "crash_restart"

    def __init__(self, files: set[str]) -> None:
        self.files = files

    def __truediv__(self, name: str) -> Leaf:
        return Leaf(name, self.files)


def conditional(path: Path) -> ast.If:
    tree = ast.parse(path.read_text("utf-8"))
    function = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_application"
    )
    return next(
        n
        for n in ast.walk(function)
        if isinstance(n, ast.If)
        and ast.unparse(n.test).startswith("scratch.name == 'crash_restart' and")
    )


def evaluate(node: ast.If, *, permitted: bool, alive: bool, restart: bool = False) -> list[dict]:
    files = {"peer-identity.json", "work-entered.json"}
    if permitted:
        files.add("crash-permitted.flag")
    scratch = Scratch(files)
    snapshots = []
    namespace = {
        "scratch": scratch,
        "restart": restart,
        "identity": scratch / "peer-identity.json",
        "handles": {7: SimpleNamespace(alive=lambda: alive)},
        "facts": [],
        "phase": {},
        "read": lambda path: (
            {"pid": 7} if path.name == "peer-identity.json" else {"state": "in_flight"}
        ),
        "observed_alive": lambda handles: {"7": alive},
        "durable": lambda path, data: snapshots.append(data),
        "ExperimentFailure": getattr(driver, "ExperimentFailure", RuntimeError),
    }
    tree = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(node)], type_ignores=[]))
    exec(compile(tree, "actual-observer-conditional-regression", "exec"), namespace)
    return snapshots


def run() -> None:
    old = conditional(driver.HERE.with_name("windows_lifecycle_final.py"))
    try:
        evaluate(old, permitted=True, alive=False)
    except RuntimeError as error:
        assert error.args == ("peer_exact_handle_not_established_before_crash",)
    else:
        raise AssertionError("old_defect_not_detected")
    fixed = conditional(driver.HERE)
    checks = []
    # This fails on the unmodified copy, at the real observer condition.
    assert evaluate(fixed, permitted=True, alive=False) == []
    checks.append("post-permission dead peer is allowed; no duplicate permission/snapshot")
    assert evaluate(fixed, permitted=True, alive=True) == []
    checks.append("post-permission live peer causes no duplicate admission")
    try:
        evaluate(fixed, permitted=False, alive=False)
    except RuntimeError as error:
        assert error.args == ("peer_exact_handle_not_established_before_crash",)
    else:
        raise AssertionError("precrash_dead_peer_must_still_fail")
    checks.append("pre-permission peer liveness remains mandatory")
    assert len(evaluate(fixed, permitted=False, alive=True)) == 1
    checks.append("pre-permission live peer records observation and admits exactly once")
    assert evaluate(fixed, permitted=False, alive=False, restart=True) == []
    checks.append("restart never receives crash permission")
    sentinel = "DO_NOT_RECORD_PRIVATE_EXCEPTION_TEXT"
    details = driver.failure_details(ValueError(sentinel))
    assert sentinel not in json.dumps(details) and details["category"] == "external_exception"
    details = driver.failure_details(
        driver.ExperimentFailure("peer_exact_handle_not_established_before_crash")
    )
    assert details["category"] == "peer_exact_handle_not_established_before_crash"
    checks.append("safe failure categories retained; external exception values not emitted")
    print(
        json.dumps(
            {
                "status": "passed",
                "checks": checks,
                "original_defect_detected": True,
                "scenario_executions": 0,
                "processes_or_SDK_contexts_started": 0,
                "checked_driver_sha256": driver.sha(driver.HERE),
            }
        )
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "exception_type": type(error).__name__,
                    "scenario_executions": 0,
                    "processes_or_SDK_contexts_started": 0,
                }
            )
        )
        raise SystemExit(1) from None
