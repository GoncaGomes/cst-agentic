"""One-time native-free capture AFTER the approved attempt; never runs the harness."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-solver-stop-dipole-01")
BRANCH = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-offline")
ARCHIVE = BRANCH / "docs/prototypes/windows-solver-stop-evidence"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text("utf-8-sig"))


baseline = read(ARCHIVE / "prior-evidence-sha256.json")
assert all(sha(Path(p)) == expected for p, expected in baseline.items()), "prior evidence changed"
report = read(ROOT / "observations.json")
ledger = read(ROOT / "round.json")
outer = read(ROOT / "outer-observation.json")
attempts = report["attempts"]
dispatched = [a for a in attempts if "dispatch" in a]
assert len(dispatched) == ledger["tool_calls"] <= 50
assert ledger["maximum_seconds"] == 1800
assert all(a["total_s"] <= a["allowance_s"] for a in dispatched if a["state"] == "received")
assert all(
    sha(ROOT / "sources" / name) == expected for name, expected in ledger["source_sha256"].items()
)
assert all(
    sha(BRANCH / "src/cst_agentic" / name) == expected
    for name, expected in ledger["source_sha256"].items()
)
assert sha(ROOT / "sources/run_dipole.py") == ledger["fixture_sha256"]
assert sha(ROOT / "authorization.json") == ledger["authorization_sha256"]
assert outer["outer_elapsed_s"] <= 1800
events = [json.loads(line) for line in (ROOT / "peer-events.jsonl").read_text("utf-8").splitlines()]
entered = [e for e in events if e["event"] == "operation_entered"]
returned = [e for e in events if e["event"] == "operation_returned"]
assert len(entered) == len(returned) == len(dispatched)
assert [e["operation"] for e in entered] == [a["name"] for a in dispatched]
assert [e["operation"] for e in returned] == [a["name"] for a in dispatched]
assert len([a for a in dispatched if a["name"] == "cst_run_simulation_async"]) == 1
assert len([a for a in dispatched if a["name"] == "cst_stop_simulation"]) <= 1
if report["status"] == "completed":
    assert not (ROOT / "recovery.json").exists() and not (ROOT / "incident.json").exists()
    assert report["CST_alive_at_idle_observation"] is True
    assert report["all_tracked_terminated"] is True
    assert not any(
        v
        for p, v in report["alive_after_orderly_close"].items()
        if p == str(read(ROOT / "launch-identity.json")["de_pid"])
    )

destination = ARCHIVE / "attempt"
destination.mkdir()  # Exclusive finalization; no silent replacement or replay.
inventory = {}
for name in (
    "authorization.json",
    "round.json",
    "observations.json",
    "native-free-checks.json",
    "catalogue.json",
    "peer-identity.json",
    "launch-identity.json",
    "peer-events.jsonl",
    "settlements.jsonl",
    "wait-entered.json",
    "owned-native-log.json",
    "incident.json",
    "recovery.json",
    "outer-observation.json",
):
    path = ROOT / name
    if path.is_file():
        shutil.copyfile(path, destination / name)
        assert sha(path) == sha(destination / name)
        inventory[name] = sha(path)
shutil.copytree(ROOT / "sources", destination / "sources")
for path in (ROOT / "sources").iterdir():
    assert sha(path) == sha(destination / "sources" / path.name)
    inventory["sources/" + path.name] = sha(path)
launch = ROOT.with_name(ROOT.name + "-launch.json")
shutil.copyfile(launch, destination / "wrapper-launch.json")
inventory["wrapper-launch.json"] = sha(launch)
stops = [a for a in dispatched if a["name"] == "cst_stop_simulation"]
waits = [a for a in dispatched if a["name"] == "cst_wait_for_simulation"]
status_reads = [a for a in dispatched if a["name"] == "cst_get_simulation_status"]
summary = {
    "native_free_post_run_verification": True,
    "prior_evidence_files_unchanged": len(baseline),
    "status": report["status"],
    "tool_calls": ledger["tool_calls"],
    "outer_elapsed_s": outer["outer_elapsed_s"],
    "complete_time_allowances_verified": outer.get("complete_allowances_verified", False),
    "all_tracked_terminated": report.get("all_tracked_terminated"),
    "human_reconciliation_required": report["human_reconciliation_required"],
    "stop_calls": len(stops),
    "wait_calls": len(waits),
    "solver_states_observed": [a.get("response", {}).get("running") for a in status_reads],
    "CST_alive_at_idle_observation": report.get("CST_alive_at_idle_observation"),
    "queue_overlap_evidenced": bool(
        stops and waits and stops[0]["requested"] < waits[0]["settled"] <= stops[0]["dispatch"]
    ),
    "stop_metrics": [
        {k: a[k] for k in ("queue_s", "dispatch_to_settlement_s", "total_s", "state") if k in a}
        for a in stops
    ],
    "idle_observation_after_stop_response_s": report.get("independent_idle_observed", 0)
    - stops[0]["settled"]
    if stops and "independent_idle_observed" in report
    else None,
    "idle_observation_after_stop_intent_s": report.get("independent_idle_observed", 0)
    - stops[0]["requested"]
    if stops and "independent_idle_observed" in report
    else None,
    "native_abort_message_observed": "Solver run aborted."
    in read(ROOT / "owned-native-log.json").get("tail", "")
    if (ROOT / "owned-native-log.json").exists()
    else False,
    "evidence_finalizer_sha256": sha(Path(__file__)),
    "inventory_sha256": inventory,
    "publication_authorized": False,
    "qualification": (
        "Running->accepted stop->idle is a bounded observation, not numerical success, "
        "isolated abort causation or production/crash-recovery acceptance."
    ),
}
(ARCHIVE / "verification.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in summary.items() if k != "inventory_sha256"}))
