"""Saved-evidence re-verification only; no application, peer or SDK session starts."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import windows_lifecycle_remaining as driver
from mcp import MCPError

ROOT = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifecycle-final-02")


def run() -> None:
    report = driver.read(ROOT / "observations.json")
    case = copy.deepcopy(next(c for c in report["cases"] if c["name"] == "partial_startup_failure"))
    assert case["application_report"]["primary_exception_types"] == [MCPError.__name__]
    # Exercise the actual verifier against unchanged evidence. This fails on the
    # old hard-coded spelling, not on a simulated replacement application.
    driver.verify_case(ROOT / "partial_startup_failure", case)
    assert case["verification"] == "passed_synthetic_design_observation"
    failure = driver.failure_details(ValueError("DO_NOT_RECORD_EXCEPTION_TEXT"))
    assert "DO_NOT_RECORD_EXCEPTION_TEXT" not in json.dumps(failure)
    print(
        json.dumps(
            {
                "status": "passed",
                "public_sdk_exception_class": MCPError.__name__,
                "saved_startup_refusal_verification": case,
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
                    "failure": driver.failure_details(error),
                    "scenario_executions": 0,
                    "processes_or_SDK_contexts_started": 0,
                }
            )
        )
        raise SystemExit(1) from None
