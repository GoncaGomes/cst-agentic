"""Native-free, one-time evidence capture; never imports/reruns the harness."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifecycle-final-01")
BRANCH = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-offline")
ARCHIVE = BRANCH / "docs/prototypes/windows-lifecycle-final-evidence"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text("utf-8-sig"))


def events(folder: Path, actor: str) -> list[dict]:
    path = folder / (actor + "-events.jsonl")
    return (
        [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []
    )


destination = ARCHIVE / "attempt"
shutil.copytree(ROOT, destination)  # Exclusive capture; no overwrite/replay.
launch = ROOT.with_name(ROOT.name + "-launch.json")
shutil.copyfile(launch, destination / "wrapper-launch.json")
inventory = {}
for path in destination.rglob("*"):
    if path.is_file():
        name = path.relative_to(destination).as_posix()
        original = launch if name == "wrapper-launch.json" else ROOT / name
        assert sha(path) == sha(original), "captured_bytes_differ"
        inventory[name] = sha(path)
        if path.suffix == ".json":
            read(path)

report = read(destination / "observations.json")
ledger = read(destination / "round.json")
outer = read(destination / "outer-observation.json")
prepared = read(destination / "preparation.json")
prior = read(destination / "prior-evidence-sha256.json")
checks = {
    "prior_evidence_unchanged": all(sha(Path(p)) == expected for p, expected in prior.items()),
    "executed_sources_match": all(
        sha(destination / "sources" / name) == expected
        and sha(BRANCH / "src/cst_agentic" / name) == expected
        for name, expected in prepared["source_sha256"].items()
    ),
    "outer_round_within_300_seconds": outer["outer_elapsed_s"] <= 300,
    "round_completed": report["status"] == "completed_synthetic_observations",
    "exactly_four_scenarios_admitted_once": ledger["scenarios_admitted"]
    == [
        "crash_restart",
        "partial_startup_failure",
        "startup_timeout",
        "stalled_shutdown",
    ],
}
outer_overhead = max(0.0, outer["outer_elapsed_s"] - report["elapsed_s"])
summaries = []
total_calls = 0
for case in report["cases"]:
    folder = destination / case["name"]
    peer_events = events(folder, "peer")
    app_events = events(folder, "app")
    total_calls += sum(e["event"] == "request" and e["method"] == "tools/call" for e in peer_events)
    summary = {
        "name": case["name"],
        "complete_scenario_s": case["complete_scenario_s"],
        "verification": case.get("verification"),
        "tools_calls": case.get("tools_call_count"),
        "tracked_process_count": sum(
            "creation_time" in p for p in case["application_process"]["processes"]
        ),
        "all_tracked_terminated_before_containment_release": case["application_process"].get(
            "all_tracked_terminated_before_containment_release"
        ),
        "all_tracked_terminated_after_containment_release": case["application_process"].get(
            "all_tracked_terminated_after_containment_release"
        ),
        "handle_open_gaps": [
            p for p in case["application_process"]["processes"] if "handle_open_error_type" in p
        ],
    }
    if case["name"] == "crash_restart":
        marker_events = [e for e in app_events if e["event"] == "durable_marker_before_dispatch"]
        work_events = [e for e in peer_events if e["event"] == "work_entered_with_marker"]
        crash_events = [e for e in app_events if e["event"] == "abrupt_application_exit"]
        restart_path = folder / "restart-result.json"
        restart = read(restart_path) if restart_path.exists() else None
        checks["marker_before_work_before_deliberate_crash_event"] = (
            len(marker_events) == len(work_events) == len(crash_events) == 1
            and marker_events[0]["monotonic"]
            <= work_events[0]["monotonic"]
            <= crash_events[0]["monotonic"]
            and read(folder / "observer-precrash.json")["central_marker"]["state"] == "in_flight"
        )
        checks["restart_blocks_work_status_stop"] = (
            restart is not None
            and restart["startup_reconciliation_required"]
            and not restart["sdk_transport_opened"]
            and [a["operation"] for a in restart["attempts"]] == ["work", "status", "stop"]
            and all(a["state"] == "not_dispatched" for a in restart["attempts"])
            and (folder / "central-recovery.json").is_file()
            and not (folder / "settled.json").exists()
        )
        summary["application_crash_exit_code"] = case["application_process"].get("exit_code")
        summary["restart_was_launched"] = "restart_process" in case
        summary["restart_exit_code"] = case.get("restart_process", {}).get("exit_code")
        summary["restart_tracked_process_count"] = len(
            case.get("restart_process", {}).get("processes", [])
        )
    elif (folder / "app-result.json").exists():
        app = read(folder / "app-result.json")
        summary["failure_status"] = app["status"]
        summary["primary_exception_types"] = app.get("primary_exception_types", [])
        summary["final_exception_types"] = app.get("final_exception_types", [])
        summary["cleanup_s"] = app.get("cleanup_s")
        summary["context_outcomes"] = app.get("context_outcomes", [])
        summary["sdk_log_metadata"] = app.get("sdk_log_metadata", [])
        # Conservatively charge ALL per-case overhead plus outer invocation
        # overhead to each lifecycle phase; these upper bounds are not summed.
        overhead = (
            max(0.0, case["complete_scenario_s"] - app["application_total_s"]) + outer_overhead
        )
        summary["complete_cleanup_conservative_upper_s"] = app["cleanup_s"] + overhead
        summary["complete_startup_conservative_upper_s"] = (
            app.get("startup_completed", app["startup_or_task_failure_observed"])
            - app["startup_started"]
            + overhead
        )
        checks[case["name"] + "_complete_provisional_bounds"] = (
            summary["complete_cleanup_conservative_upper_s"] <= 30
            and summary["complete_startup_conservative_upper_s"] <= 120
        )
        checks[case["name"] + "_same_owner_contexts"] = len(
            summary["context_outcomes"]
        ) == 2 and all(
            o["entered"] and o["owner_task_id"] == o["exit_task_id"]
            for o in summary["context_outcomes"]
        )
        checks[case["name"] + "_failure_not_success"] = app["status"] == "failed_not_success"
        checks[case["name"] + "_sdk_cleanup_terminated_observed_chain"] = bool(
            summary["all_tracked_terminated_before_containment_release"]
        )
        if case["name"] == "startup_timeout":
            summary["startup_cancellation_observed_s"] = (
                app["startup_or_task_failure_observed"] - app["startup_started"]
            )
        if case["name"] == "stalled_shutdown":
            summary["peer_eof_observed"] = any(e["event"] == "stdin_eof" for e in peer_events)
            summary["orderly_exit_refusal_observed"] = any(
                e["event"] == "refusing_orderly_exit" for e in peer_events
            )
            summary["normal_peer_exit_recorded"] = any(
                e["event"] == "normal_exit" for e in peer_events
            )
    summaries.append(summary)
checks["only_one_synthetic_tool_dispatched"] = total_calls == 1
verification = {
    "record_kind": "native-free post-run verification; no scenario replay",
    "checks": checks,
    "all_checks_passed": all(checks.values()),
    "capture_integrity_passed": all(
        checks[k]
        for k in (
            "prior_evidence_unchanged",
            "executed_sources_match",
            "outer_round_within_300_seconds",
        )
    ),
    "round_status": report["status"],
    "scenarios_admitted": ledger["scenarios_admitted"],
    "scenarios_not_run": [
        name
        for name in (
            "partial_startup_failure",
            "startup_timeout",
            "stalled_shutdown",
        )
        if name not in ledger["scenarios_admitted"]
    ],
    "outer_elapsed_s": outer["outer_elapsed_s"],
    "driver_elapsed_s": report["elapsed_s"],
    "outer_overhead_s": outer_overhead,
    "prior_files_unchanged": len(prior) if checks["prior_evidence_unchanged"] else False,
    "total_synthetic_tools_calls": total_calls,
    "scenarios": summaries,
    "inventory_sha256": inventory,
    "capture_script_sha256": sha(Path(__file__)),
    "CST_solver_endpoint_executions": 0,
    "publication_authorized": False,
    "limitations": [
        (
            "Disposable application/fake-peer design evidence, not execution of the "
            "production Controller or native CST failure recovery."
        ),
        (
            "Controlled process exit with a pre-dispatch flushed/replaced file; no power-loss, "
            "disk-loss, concurrent-session lease or reconciliation-clearance procedure was tested."
        ),
        (
            "SDK escalation would not establish behavior on an induced SDK cleanup exception, "
            "unkillable process or universal cleanup-time guarantee; shutdown case did not run."
        ),
        (
            "Exact SDK Job Object ownership remains unisolated; process termination "
            "does not identify its mechanism."
        ),
    ],
}
(ARCHIVE / "verification.json").write_text(
    json.dumps(verification, indent=2) + "\n", encoding="utf-8"
)
print(
    json.dumps(
        {
            k: verification[k]
            for k in (
                "capture_integrity_passed",
                "all_checks_passed",
                "round_status",
                "outer_elapsed_s",
                "driver_elapsed_s",
                "prior_files_unchanged",
                "total_synthetic_tools_calls",
            )
        }
    )
)
if not verification["capture_integrity_passed"]:
    raise RuntimeError("capture_integrity_requires_review_do_not_replay")
