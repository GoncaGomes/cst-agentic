"""One-time local-only evidence copy/verification. No native, Git or tracker calls."""

import hashlib
import json
import math
import re
import shutil
from pathlib import Path

BASE = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode")
PROJECT = BASE / "cst-lifetime-offline"
ROOT = BASE / "cst-lifetime-native"
EVIDENCE = PROJECT / "docs/prototypes/windows-lifetime-native-evidence"
RAW = ROOT / "evidence/leave-open-repeat"
DESTINATION = EVIDENCE / "leave-open-repeat"
SNAPSHOT = EVIDENCE / "leave-open-repeat-source"


def load(path):
    return json.loads(path.read_text("utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def copy_verified(source, target):
    if target.exists():
        raise RuntimeError("Evidence destination exists; do not overwrite")
    shutil.copyfile(source, target)
    assert digest(source) == digest(target)


report = load(RAW / "observations.json")
outer = load(RAW / "outer-observation.json")
before = load(SNAPSHOT / "pre-repeat-ledger.json")
after = load(ROOT / "round.json")
assert report["case"] == "leave-open-repeat"
assert report["target"] == str(ROOT / "leave-open-repeat.cst")
assert Path(report["target"]).is_file()
assert [a["name"] for a in report["attempts"]] == [
    "native_connect",
    "native_create",
    "native_status",
    "native_disconnect",
]
for attempt in report["attempts"]:
    assert attempt["state"] == "received" and not attempt["is_error"]
    assert attempt["total_s"] <= 120
assert before["tool_calls"] == 9 and before["maximum_calls"] == 12
assert after["tool_calls"] == 13 and after["maximum_calls"] == 13
assert after["maximum_active_seconds"] == 900
assert after["cases"] == before["cases"] | {"leave-open-repeat": "completed"}
assert after["continuation"] == before["continuation"]
assert after["between_case_accounting"] == before["between_case_accounting"]
assert math.isclose(after["active_seconds"], before["active_seconds"] + 30 + report["total_s"])
assert after["active_seconds"] < 900
pid = str(report["attempts"][0]["response"]["de_pid"])
assert report["alive_after_exit_action"][pid]
assert report["post_teardown_samples"][0]["alive"][pid]
assert not any(report["final_alive"].values())
assert not report["manual_confirmation_required"]
assert report["windows_before_exit_action"]["expected_project_title_count"] == 1
assert report["windows_after_teardown"]["expected_project_title_count"] == 0
assert report["instance_observation"] == "identified_DE_process_terminated"
assert outer["exit_code"] == 0 and outer["native_invocation_error_type"] is None
assert outer["ledger_matches"] and not outer["round_ceiling_exceeded"]
assert not outer["complete_allowance_exceeded"] and not outer["case_300_second_ceiling_exceeded"]
assert outer["outer_uv_seconds"] < 300
events = [json.loads(line) for line in (RAW / "peer-events.jsonl").read_text().splitlines()]
for name in ("save_entered", "save_returned", "server_eof_returned"):
    assert sum(e["event"] == name for e in events) == 1
assert not any(e["event"].startswith("instance_close") for e in events)
for filename, expected in report["source_sha256"].items():
    assert digest(PROJECT / "src/cst_agentic" / filename) == expected
    assert digest(SNAPSHOT / filename) == expected
for entry in load(SNAPSHOT / "static-checks.json")["source_manifest"]:
    assert digest(SNAPSHOT / entry["filename"]) == entry["sha256"]
for raw_name, saved_name in (
    ("observations.json", "leave-open-observations.json"),
    ("peer-events.jsonl", "leave-open-peer-events.jsonl"),
    ("peer-identity.json", "leave-open-peer-identity.json"),
    ("recovery.json", "leave-open-recovery.json"),
):
    assert digest(ROOT / "evidence/leave-open" / raw_name) == digest(EVIDENCE / saved_name)
DESTINATION.mkdir()
for filename in (
    "observations.json",
    "peer-events.jsonl",
    "peer-identity.json",
    "launch-identity.json",
    "ledger-before-authorization.json",
    "ledger-at-admission.json",
    "outer-observation.json",
):
    copy_verified(RAW / filename, DESTINATION / filename)
copy_verified(
    ROOT / "evidence/leave-open-repeat-wrapper-start.json", DESTINATION / "wrapper-start.json"
)
copy_verified(ROOT / "round.json", DESTINATION / "round-after-repeat.json")
copy_verified(Path(__file__), SNAPSHOT / Path(__file__).name)
verification = {
    "repeat_evidence_verified": True,
    "new_native_calls": 4,
    "cumulative_calls": 13,
    "maximum_cumulative_calls": 13,
    "maximum_cumulative_seconds": 900,
    "charged_seconds_rounded": round(after["active_seconds"], 6),
    "outer_case_seconds": outer["outer_uv_seconds"],
    "case_maximum_seconds": 300,
    "old_failure_and_recovery_marker_preserved": True,
    "executed_source_snapshots_match": True,
    "one_save_and_no_explicit_instance_close": True,
    "identified_de_and_all_tracked_processes_terminated": True,
    "manual_lifetime_confirmation_required": False,
    "human_ui_actions_during_repeat": "Not independently observed or separately confirmed",
    "native_api_calls_by_this_check": 0,
    "git_or_tracker_writes_by_this_check": 0,
    "verification_source_sha256": digest(Path(__file__)),
    "qualification": (
        "Prior timing qualifications retained; no causal isolation of native "
        "finalization, transport cleanup or human UI interaction."
    ),
}
with (DESTINATION / "verification.json").open("x", encoding="utf-8") as stream:
    json.dump(verification, stream, indent=2)
document = PROJECT / "docs/prototypes/windows-lifetime-native.md"
for link in re.findall(r"\]\(([^)]+)\)", document.read_text("utf-8")):
    if not link.startswith(("http://", "https://", "#")):
        assert (document.parent / link).exists()
print(
    json.dumps(
        {
            "repeat_evidence_verified": True,
            "report_links_valid": True,
            "native_api_calls": 0,
            "git_or_tracker_writes": 0,
        }
    )
)
