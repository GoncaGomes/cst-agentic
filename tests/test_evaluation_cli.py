"""Evaluation CLI is offline unless an external caller explicitly supplies a model."""

import json

from cst_agentic.cli import main


def test_manifest_and_offline_scoring_need_no_environment_or_credentials(tmp_path, monkeypatch):
    import cst_agentic.cli as cli

    monkeypatch.setattr(
        cli,
        "load_controller_config",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Evaluation must not load Controller credentials")
        ),
    )
    manifest = tmp_path / "manifest.json"
    assert main(["evaluate", "manifest", "--output", str(manifest)]) == 0
    frozen = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(frozen["schedule"]) == 132
    output = tmp_path / "offline"
    assert main(["evaluate", "offline", "--output-directory", str(output)]) == 0
    scored = tmp_path / "score.json"
    assert (
        main(
            [
                "evaluate",
                "score",
                "--records",
                str(output / "records.json"),
                "--reviews",
                str(output / "reviews.json"),
                "--output",
                str(scored),
            ]
        )
        == 1
    )
    report = json.loads(scored.read_text(encoding="utf-8"))
    assert report["status"] == "incomplete"
    assert report["missing_trials"] == 130
    assert main(["evaluate", "manifest", "--output", str(manifest)]) == 1
