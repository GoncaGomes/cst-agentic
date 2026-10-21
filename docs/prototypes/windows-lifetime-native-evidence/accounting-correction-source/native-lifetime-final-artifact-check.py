"""Read-only final artifact checks. Never starts MCP/CST or changes a ledger."""

import hashlib
import json
import re
from pathlib import Path

BASE = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode")
PROJECT = BASE / "cst-lifetime-offline"
EVIDENCE = PROJECT / "docs/prototypes/windows-lifetime-native-evidence"
REPORT = PROJECT / "docs/prototypes/windows-lifetime-native.md"
ROOT = BASE / "cst-lifetime-native"


def load(path):
    return json.loads(path.read_text("utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


json_count = 0
for path in EVIDENCE.rglob("*.json"):
    load(path)
    json_count += 1
for path in EVIDENCE.rglob("*.jsonl"):
    for line in path.read_text("utf-8").splitlines():
        json.loads(line)
for link in re.findall(r"\]\(([^)]+)\)", REPORT.read_text("utf-8")):
    if not link.startswith(("https://", "http://", "#")):
        assert (REPORT.parent / link).exists(), "Missing local report link"
manifest = load(EVIDENCE / "logging-fix-static-checks.json")["source_manifest"]
for entry in manifest:
    assert digest(EVIDENCE / "logging-fix-source" / entry["filename"]) == entry["sha256"]
ledger = load(EVIDENCE / "round-after-accounting.json")
assert ledger == load(ROOT / "round.json")
assert ledger["tool_calls"] == 9
assert ledger["active_seconds"] == 521.245152
assert ledger["cases"] == {"leave-open": "completed", "authorized-close": "completed"}
assert ledger["continuation"]["failed_ledger"] == load(EVIDENCE / "round.json")
assert ledger["maximum_calls"] == 12 and ledger["maximum_active_seconds"] == 900
assert load(EVIDENCE / "native-evidence-verification.json")["native_api_calls_by_this_check"] == 0
for label in ("leave-open-logging-fix-1", "authorized-close"):
    report = load(EVIDENCE / label / "observations.json")
    assert digest(EVIDENCE / label / "observations.json") == digest(
        ROOT / "evidence" / label / "observations.json"
    )
    for filename, expected in report["source_sha256"].items():
        assert digest(PROJECT / "src/cst_agentic" / filename) == expected
    for name in (
        "peer-events.jsonl",
        "peer-identity.json",
        "launch-identity.json",
        "ledger-at-admission.json",
        "outer-observation.json",
    ):
        assert digest(EVIDENCE / label / name) == digest(ROOT / "evidence" / label / name)
for raw_name, copied_name in (
    ("observations.json", "leave-open-observations.json"),
    ("peer-events.jsonl", "leave-open-peer-events.jsonl"),
    ("peer-identity.json", "leave-open-peer-identity.json"),
    ("recovery.json", "leave-open-recovery.json"),
):
    assert digest(ROOT / "evidence/leave-open" / raw_name) == digest(EVIDENCE / copied_name)
print(
    json.dumps(
        {
            "artifact_checks_passed": True,
            "json_files_checked": json_count,
            "local_report_links_valid": True,
            "failed_evidence_preserved": True,
            "executed_sources_and_copies_match": True,
            "native_api_calls": 0,
        }
    )
)
