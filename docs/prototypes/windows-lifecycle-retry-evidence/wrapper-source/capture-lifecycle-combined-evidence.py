"""One-time capture and independent verification of four unique synthetic cases.

No harness imports, application/peer execution, SDK contexts or scenario retries.
Raw blocked ledgers are preserved; derived verification is explicitly separate.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from mcp import MCPError

BRANCH = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-offline")
BASE = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode")
ARCHIVE = BRANCH / "docs/prototypes/windows-lifecycle-retry-evidence"
NAMES = ("crash_restart", "partial_startup_failure", "startup_timeout", "stalled_shutdown")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text("utf-8-sig"))


def events(folder: Path, actor: str) -> list[dict]:
    path = folder / (actor + "-events.jsonl")
    return (
        [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []
    )


def leaves(error: dict) -> list[str]:
    children = error.get("children", [])
    if children:
        return [name for child in children for name in leaves(child)]
    return [
        name
        for name in error.get("exception_types", [])
        if name not in {"ExceptionGroup", "BaseExceptionGroup"}
    ]


inventory = {}
parts = []
checks = {}
for number, relative in (("02", "attempt"), ("03", "continuation/attempt")):
    root = BASE / ("cst-lifecycle-final-" + number)
    destination = ARCHIVE / relative
    shutil.copytree(root, destination)  # Exclusive capture, never overwrite evidence.
    launch = root.with_name(root.name + "-launch.json")
    shutil.copyfile(launch, destination / "wrapper-launch.json")
    for path in destination.rglob("*"):
        if path.is_file():
            name = path.relative_to(destination).as_posix()
            original = launch if name == "wrapper-launch.json" else root / name
            assert sha(path) == sha(original), "captured_bytes_differ"
            inventory[relative + "/" + name] = sha(path)
            if path.suffix == ".json":
                read(path)
    prepared = read(destination / "preparation.json")
    checks[number + "_executed_sources_match"] = all(
        sha(destination / "sources" / name) == expected
        and sha(BRANCH / "src/cst_agentic" / name) == expected
        for name, expected in prepared["source_sha256"].items()
    )
    prior = read(destination / "prior-evidence-sha256.json")
    checks[number + "_prior_files_unchanged"] = all(
        sha(Path(p)) == expected for p, expected in prior.items()
    )
    parts.append(
        {
            "number": number,
            "folder": destination,
            "report": read(destination / "observations.json"),
            "ledger": read(destination / "round.json"),
            "outer": read(destination / "outer-observation.json"),
            "prior_file_count": len(prior),
        }
    )

execution_seconds = sum(p["outer"]["outer_elapsed_s"] for p in parts)
admitted = [name for p in parts for name in p["ledger"]["scenarios_admitted"]]
checks["four_unique_scenarios_no_execution_retries"] = admitted == list(NAMES)
checks["cumulative_300_second_budget_met"] = execution_seconds <= 300
checks["continuation_records_same_cumulative_budget"] = (
    abs(parts[1]["outer"]["cumulative_outer_elapsed_s"] - execution_seconds) < 0.000001
)
summaries = []
total_calls = 0
tracked_count = 0
for part in parts:
    overhead = max(0.0, part["outer"]["outer_elapsed_s"] - part["report"]["elapsed_s"])
    for case in part["report"]["cases"]:
        name = case["name"]
        folder = part["folder"] / name
        peer_events = events(folder, "peer")
        app_events = events(folder, "app")
        calls = [e for e in peer_events if e["event"] == "request" and e["method"] == "tools/call"]
        total_calls += len(calls)
        observer = case["application_process"]
        tracked = len([p for p in observer["processes"] if "creation_time" in p])
        tracked_count += tracked
        summary = {
            "name": name,
            "execution_part": part["number"],
            "runtime_verification": case.get("verification"),
            "original_verifier_failure": case.get("failure"),
            "complete_scenario_s": case["complete_scenario_s"],
            "tools_calls": len(calls),
            "tracked_process_count": tracked,
            "all_tracked_terminated_before_containment_release": observer.get(
                "all_tracked_terminated_before_containment_release", False
            ),
        }
        local = {}
        local["exact_processes_terminated_before_release"] = summary[
            "all_tracked_terminated_before_containment_release"
        ]
        local["no_handle_open_gaps"] = not any(
            "handle_open_error_type" in p for p in observer["processes"]
        )
        if name == "crash_restart":
            restart = read(folder / "restart-result.json")
            marker = read(folder / "central-recovery.json")
            marker_events = [
                e for e in app_events if e["event"] == "durable_marker_before_dispatch"
            ]
            work_events = [e for e in peer_events if e["event"] == "work_entered_with_marker"]
            crash_events = [e for e in app_events if e["event"] == "abrupt_application_exit"]
            local["marker_before_work_before_crash"] = (
                len(marker_events) == len(work_events) == len(crash_events) == 1
                and marker_events[0]["monotonic"]
                <= work_events[0]["monotonic"]
                <= crash_events[0]["monotonic"]
                and read(folder / "work-entered.json")["marker_verified_before_work"]
                and marker
                == {"state": "in_flight", "operation": "work", "target": "synthetic-only"}
            )
            local["controlled_application_exit_observed"] = observer["exit_code"] == 23
            local["fresh_restart_blocks_all_tools_before_transport"] = (
                case["restart_process"]["exit_code"] == 0
                and restart["startup_reconciliation_required"]
                and not restart["sdk_transport_opened"]
                and [a["operation"] for a in restart["attempts"]] == ["work", "status", "stop"]
                and all(a["state"] == "not_dispatched" for a in restart["attempts"])
                and len(calls) == 1
                and not (folder / "settled.json").exists()
                and read(folder / "app-identity.json")["pid"]
                != read(folder / "restart-identity.json")["pid"]
                and case["restart_process"]["all_tracked_terminated_before_containment_release"]
            )
            restart_count = len(case["restart_process"]["processes"])
            tracked_count += restart_count
            summary["restart_tracked_process_count"] = restart_count
            summary["application_exit_code"] = observer["exit_code"]
            summary["restart_exit_code"] = case["restart_process"]["exit_code"]
        else:
            app = read(folder / "app-result.json")
            expected = {
                "partial_startup_failure": MCPError.__name__,
                "startup_timeout": "TimeoutError",
                "stalled_shutdown": "SyntheticTaskFailure",
            }[name]
            local["expected_failure_preserved_without_success_or_extra_exception"] = (
                observer["exit_code"] == 20
                and app["status"] == "failed_not_success"
                and not calls
                and leaves(app["primary_failure"]) == [expected]
                and leaves(app["final_failure"]) == [expected]
            )
            outcomes = app["context_outcomes"]
            local["same_owner_context_unwind"] = (
                len(outcomes) == 2
                and {o["context"] for o in outcomes} == {"session", "transport"}
                and all(o["entered"] and o["owner_task_id"] == o["exit_task_id"] for o in outcomes)
            )
            complete_overhead = (
                max(0.0, case["complete_scenario_s"] - app["application_total_s"]) + overhead
            )
            startup_s = (
                app.get("startup_completed", app["startup_or_task_failure_observed"])
                - app["startup_started"]
            )
            summary.update(
                {
                    "expected_exception_class": expected,
                    "primary_exception_types": app["primary_exception_types"],
                    "final_exception_types": app["final_exception_types"],
                    "startup_s": startup_s,
                    "cleanup_s": app["cleanup_s"],
                    "complete_startup_conservative_upper_s": startup_s + complete_overhead,
                    "complete_cleanup_conservative_upper_s": app["cleanup_s"] + complete_overhead,
                    "sdk_log_metadata": app.get("sdk_log_metadata", []),
                }
            )
            local["measured_cleanup_within_10_second_experimental_allowance"] = (
                not app["cleanup_allowance_exceeded"] and app["cleanup_s"] <= 10
            )
            local["complete_120_second_startup_30_second_cleanup_bounds"] = (
                summary["complete_startup_conservative_upper_s"] <= 120
                and summary["complete_cleanup_conservative_upper_s"] <= 30
            )
            if name == "startup_timeout":
                summary["startup_timeout_requested_s"] = app["startup_allowance_s"]
                summary["startup_timeout_observed_s"] = (
                    app["startup_or_task_failure_observed"] - app["startup_started"]
                )
                local["initialization_stall_observed"] = any(
                    e["event"] == "initialization_stalled" for e in peer_events
                )
            if name == "stalled_shutdown":
                local["refused_eof_exit_and_did_not_record_normal_exit"] = (
                    any(e["event"] == "stdin_eof" for e in peer_events)
                    and any(e["event"] == "refusing_orderly_exit" for e in peer_events)
                    and not any(e["event"] == "normal_exit" for e in peer_events)
                )
        summary["derived_checks"] = local
        summary["derived_verification_passed"] = all(local.values())
        checks[name] = summary["derived_verification_passed"]
        summaries.append(summary)
checks["only_one_synthetic_tools_call"] = total_calls == 1
verification = {
    "record_kind": "independent derived verification, raw stopped ledger retained unchanged",
    "all_checks_passed": all(checks.values()),
    "checks": checks,
    "total_unique_scenario_executions": len(admitted),
    "execution_retries": 0,
    "cumulative_outer_execution_s": execution_seconds,
    "part_outer_execution_s": {p["number"]: p["outer"]["outer_elapsed_s"] for p in parts},
    "raw_part_statuses": {p["number"]: p["report"]["status"] for p in parts},
    "public_sdk_error_class": MCPError.__name__,
    "verification_correction": (
        "Part 02 expected McpError instead of public MCPError. "
        "Rechecked unchanged startup-refusal evidence; did not rerun that scenario."
    ),
    "prior_files_unchanged": parts[1]["prior_file_count"],
    "total_synthetic_tools_calls": total_calls,
    "tracked_process_handle_observations": tracked_count,
    "scenarios": summaries,
    "inventory_sha256": inventory,
    "capture_script_sha256": sha(Path(__file__)),
    "CST_solver_endpoint_executions": 0,
    "publication_authorized": False,
    "limitations": [
        (
            "Synthetic disposable application and fake peer, not production Controller/client "
            "or native CST failure recovery."
        ),
        (
            "Controlled process crash with pre-dispatch persistence; not power-loss/disk-failure "
            "durability, concurrent-session lease or recovery clearance."
        ),
        (
            "No induced SDK cleanup exception or unkillable-process case; measured bounds "
            "are not universal timing guarantees."
        ),
        (
            "Exact SDK Job Object ownership remains unisolated; process outcomes "
            "do not identify the termination mechanism."
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
                "all_checks_passed",
                "total_unique_scenario_executions",
                "execution_retries",
                "cumulative_outer_execution_s",
                "prior_files_unchanged",
                "tracked_process_handle_observations",
            )
        }
    )
)
if not verification["all_checks_passed"]:
    raise RuntimeError("derived_verification_failed_preserve_evidence_no_replay")
