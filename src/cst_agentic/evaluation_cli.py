"""Offline evaluation commands; never load .env or construct a provider."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from .evaluation_offline import run_offline_smoke
from .evaluation_pack import pack_manifest, scenario_for
from .evaluation_scoring import CallRating, Finding, Review, score_campaign


def add_evaluation_parser(subparsers) -> None:
    parser = subparsers.add_parser(
        "evaluate", help="Offline fixed-pack harness and independent scoring."
    )
    actions = parser.add_subparsers(dest="evaluation_action", required=True)
    manifest = actions.add_parser(
        "manifest", help="Export frozen scenarios, variants and paired order."
    )
    manifest.add_argument("--output", type=Path, required=True)
    offline = actions.add_parser("offline", help="Run two synthetic tracer trials; no Qwen or CST.")
    offline.add_argument("--output-directory", type=Path, required=True)
    score = actions.add_parser(
        "score", help="Score retained evidence against an independent review."
    )
    score.add_argument("--records", type=Path, required=True)
    score.add_argument("--reviews", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)


def review_template(records: list[dict]) -> dict:
    template = {}
    for record in records:
        case = scenario_for(record["suite"], record["case_id"])
        template[record["trial_id"]] = asdict(
            Review(
                requirements={key: Finding(None) for key in case.required},
                calls={proposal["id"]: CallRating() for proposal in record["proposals"]},
            )
        )
    return template


def load_reviews(path: Path) -> dict[str, Review]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for key, data in raw.items():
        data = dict(data)
        data["requirements"] = {
            name: Finding(value["passed"], tuple(value["evidence"]))
            for name, value in data["requirements"].items()
        }
        data["calls"] = {name: CallRating(**value) for name, value in data["calls"].items()}
        for field in ("safety", "bounded_recovery", "truthful_engineering"):
            value = data[field]
            data[field] = Finding(value["passed"], tuple(value["evidence"]))
        result[key] = Review(**data)
    return result


def run_evaluation(args: argparse.Namespace) -> int:
    try:
        if args.evaluation_action == "manifest":
            with args.output.open("x", encoding="utf-8") as output:
                json.dump(pack_manifest(), output, indent=2)
            print("Frozen evaluation manifest exported; no trials run.")
            return 0
        if args.evaluation_action == "offline":
            report = asyncio.run(run_offline_smoke(args.output_directory))
            with (args.output_directory / "reviews.json").open("x", encoding="utf-8") as output:
                json.dump(review_template(report["records"]), output, indent=2)
            print(
                "Two offline tracer trials recorded. Full campaign/native acceptance: incomplete."
            )
            return 0
        report = json.loads(args.records.read_text(encoding="utf-8"))
        scored = score_campaign(report["records"], load_reviews(args.reviews), report["ledger"])
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(scored, output, indent=2)
        print(f"Mocked-model screening: {scored['status']}. No native CST acceptance claim.")
        return 0 if scored["status"] == "pass" else 1
    except (Exception, BaseExceptionGroup):
        print(
            "Evaluation failed: invalid input, unavailable storage or existing output; "
            "raw details withheld."
        )
        return 1
