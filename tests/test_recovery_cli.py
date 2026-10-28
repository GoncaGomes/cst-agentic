"""Local human recovery is usable without configuration, model or CST access."""

import uuid

import pytest

from cst_agentic.cli import main
from cst_agentic.recovery import RecoveryStore


def test_local_recovery_reports_and_records_findings_without_transport(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    store = RecoveryStore()
    with store.session():
        incident = store.prepare(str(uuid.uuid4()), "cst_create_project", None)
        store.finish(incident, "uncertain")

    def forbidden(*args, **kwargs):
        pytest.fail("Local reconciliation must not configure or start Controller transport")

    monkeypatch.setattr("cst_agentic.cli.load_controller_config", forbidden)
    monkeypatch.setattr("cst_agentic.cli.run_controller_terminal", forbidden)
    assert main(["recovery", "status"]) == 0
    output = capsys.readouterr().out
    assert incident in output and "uncertain" in output
    assert "not independently verified" in output

    answers = iter(["yes", "yes", "no", "yes"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert main(["recovery", "reconcile", incident]) == 1
    with store.session():
        record = store.incidents(unresolved_only=True)[0]
        assert record.human_evidence and not record.activity_resolved
        assert len(record.findings) == 1

    answers = iter(["yes"] * 4)
    assert main(["recovery", "reconcile", incident]) == 0
    output = capsys.readouterr().out
    assert "fresh Controller session" in output and "new task" in output
    with store.session():
        assert not store.incidents(unresolved_only=True)
        assert len(store.incidents()[0].findings) == 2


def test_interrupted_local_reconciliation_does_not_clear_incident(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    store = RecoveryStore()
    with store.session():
        incident = store.prepare(str(uuid.uuid4()), "cst_connect", None)
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(EOFError()))
    assert main(["recovery", "reconcile", incident]) == 1
    with store.session():
        assert store.incidents(unresolved_only=True)[0].human_evidence is False
