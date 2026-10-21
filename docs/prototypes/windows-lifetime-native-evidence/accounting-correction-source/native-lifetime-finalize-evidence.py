"""Native-free evidence capture and conservative inter-case accounting, once only."""

import hashlib
import importlib.util
import json
import shutil
from datetime import datetime
from pathlib import Path

BASE = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode")
PROJECT = BASE / "cst-lifetime-offline"
ROOT = BASE / "cst-lifetime-native"
EVIDENCE = PROJECT / "docs/prototypes/windows-lifetime-native-evidence"
SOURCE = PROJECT / "src/cst_agentic"
spec = importlib.util.spec_from_file_location(
    "native_free_evidence_helpers", SOURCE / "windows_lifetime_native_peer.py"
)
peer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(peer)


def load(path):
    return json.loads(path.read_text("utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def copy_verified(source, target):
    if target.exists():
        raise RuntimeError("Evidence destination exists; do not overwrite")
    shutil.copyfile(source, target)
    assert digest(source) == digest(target)


ledger = load(ROOT / "round.json")
assert ledger["cases"] == {"leave-open": "completed", "authorized-close": "completed"}
assert ledger["tool_calls"] == 9 and ledger["active_seconds"] == 374.703
assert "between_case_accounting" not in ledger
first_dir = ROOT / "evidence/leave-open-logging-fix-1"
second_dir = ROOT / "evidence/authorized-close"
first = load(first_dir / "observations.json")
second = load(second_dir / "observations.json")
outer1 = load(first_dir / "outer-observation.json")
outer2 = load(second_dir / "outer-observation.json")
start1 = load(ROOT / "evidence/leave-open-logging-fix-1-wrapper-start.json")
start2 = load(ROOT / "evidence/authorized-close-wrapper-start.json")
assert ledger["maximum_calls"] == 12 and ledger["maximum_active_seconds"] == 900
assert 1 + len(first["attempts"]) + len(second["attempts"]) == ledger["tool_calls"]
for report, outer in ((first, outer1), (second, outer2)):
    assert not report["manual_confirmation_required"]
    assert all(not alive for alive in report["final_alive"].values())
    assert report["windows_before_exit_action"]["expected_project_title_count"] == 1
    assert report["windows_after_teardown"]["expected_project_title_count"] == 0
    assert report["saved_file_exists"]
    assert Path(report["target"]).is_file()
    assert outer["exit_code"] == 0 and outer["native_invocation_error_type"] is None
    assert outer["ledger_matches"] and not outer["complete_allowance_exceeded"]
    assert not outer["round_ceiling_exceeded"] and not outer["wrapper_reserve_exceeded"]
    for attempt in report["attempts"]:
        assert attempt["state"] == "received" and not attempt["is_error"]
        assert attempt["total_s"] <= 120
    for filename, expected in report["source_sha256"].items():
        assert digest(SOURCE / filename) == expected
        assert digest(EVIDENCE / "logging-fix-source" / filename) == expected
assert first["attempts"][-1]["name"] == "native_disconnect"
assert second["attempts"][-1]["name"] == "native_close"
pid1 = str(first["attempts"][0]["response"]["de_pid"])
pid2 = str(second["attempts"][0]["response"]["de_pid"])
assert first["alive_after_exit_action"][pid1]
assert not second["alive_after_exit_action"][pid2]
assert first["post_teardown_samples"][0]["alive"][pid1]
assert not first["post_teardown_samples"][-1]["alive"][pid1]
for directory, close_count in ((first_dir, 0), (second_dir, 1)):
    events = [
        json.loads(line) for line in (directory / "peer-events.jsonl").read_text().splitlines()
    ]
    for event in ("save_entered", "save_returned", "server_eof_returned"):
        assert sum(e["event"] == event for e in events) == 1
    assert sum(e["event"] == "instance_close_entered" for e in events) == close_count
for raw_name, saved_name in (
    ("observations.json", "leave-open-observations.json"),
    ("peer-events.jsonl", "leave-open-peer-events.jsonl"),
    ("peer-identity.json", "leave-open-peer-identity.json"),
    ("recovery.json", "leave-open-recovery.json"),
):
    assert digest(ROOT / "evidence/leave-open" / raw_name) == digest(EVIDENCE / saved_name)
assert load(EVIDENCE / "round.json")["tool_calls"] == 1
assert (
    digest(EVIDENCE / "accounting-correction-source/native-lifetime-run-case.ps1")
    == start2["wrapper_sha256"]
)

destination = EVIDENCE / "authorized-close"
destination.mkdir()
for filename in (
    "observations.json",
    "peer-events.jsonl",
    "peer-identity.json",
    "launch-identity.json",
    "ledger-at-admission.json",
    "outer-observation.json",
):
    copy_verified(second_dir / filename, destination / filename)
copy_verified(ROOT / "round.json", destination / "round-after-case.json")
copy_verified(
    ROOT / "evidence/authorized-close-wrapper-start.json", destination / "wrapper-start.json"
)

# Include the entire gap between cases, even though no MCP connection was open.
# UTC is the available cross-invocation envelope, not a monotonic-clock guarantee.
delta = (
    datetime.fromisoformat(start2["utc"]) - datetime.fromisoformat(start1["utc"])
).total_seconds()
gap = round(delta - outer1["outer_uv_seconds"], 6)
assert gap >= 0
new_envelope = round(delta + outer2["outer_uv_seconds"], 6)
accounting = {
    "source": "Both wrapper-start UTC timestamps and outer uv stopwatch observations",
    "between_case_seconds_charged": gap,
    "new_round_utc_envelope_seconds": new_envelope,
    "new_driver_plus_wrapper_stopwatch_seconds": round(
        outer1["outer_uv_seconds"] + outer2["outer_uv_seconds"], 6
    ),
    "ledger_before_gap_charge_seconds": ledger["active_seconds"],
    "retained_wrapper_reserve_seconds": 60,
    "prior_attempt_conservative_charge_seconds": 180,
    "qualification": (
        "Gap charged after evidence review; both cases would still have passed the "
        "155-second admission reserve with that gap included. UTC envelope is not "
        "independently protected against wall-clock adjustment. Original failed-path "
        "overhead remains unmeasured; no retrospective complete-budget guarantee."
    ),
}
second_admission = load(second_dir / "ledger-at-admission.json")
elapsed_upper = second["total_s"]  # Greater than elapsed at every admission.
assert 900 - second_admission["active_seconds"] - gap - elapsed_upper >= 155
ledger["active_seconds"] = round(ledger["active_seconds"] + gap, 6)
ledger["between_case_accounting"] = accounting
assert ledger["active_seconds"] < 900
peer.durable_write(ROOT / "round.json", ledger)
copy_verified(ROOT / "round.json", EVIDENCE / "round-after-accounting.json")
peer.durable_write(
    EVIDENCE / "native-evidence-verification.json",
    {
        "original_failure_and_marker_unchanged": True,
        "executed_source_snapshots_match": True,
        "all_successful_calls_received_and_within_120_seconds": True,
        "one_save_per_successful_case": True,
        "native_close_absent_in_leave_open_and_once_in_close_case": True,
        "all_tracked_process_handles_terminated_in_both_cases": True,
        "manual_confirmation_needed": False,
        "tool_calls_including_initial_failure": ledger["tool_calls"],
        "conservative_charged_seconds_after_gap_review": ledger["active_seconds"],
        "accounting": accounting,
        "native_api_calls_by_this_check": 0,
    },
)
print(
    json.dumps(
        {
            "evidence_verified": True,
            "native_api_calls": 0,
            "tool_calls": ledger["tool_calls"],
            "charged_seconds": ledger["active_seconds"],
            "new_round_utc_envelope_seconds": new_envelope,
        }
    )
)
