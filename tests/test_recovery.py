"""Real isolated filesystem/OS lease checks; no CST or provider requests."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

import pytest

from cst_agentic.project_storage import ProjectLocation, ProjectStorageError
from cst_agentic.recovery import RecoveryError, RecoveryStore, controller_state_directory


def project(tmp_path: Path, name: str = "a") -> ProjectLocation:
    directory = tmp_path / name
    directory.mkdir(exist_ok=True)
    return ProjectLocation.inspect(directory / f"{name}.cst")


def test_storage_location(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert controller_state_directory() == tmp_path / "CST-Agentic"
    monkeypatch.delenv("LOCALAPPDATA")
    with pytest.raises(RecoveryError, match="LOCALAPPDATA"):
        controller_state_directory()


def test_dedicated_directories_and_aliases(tmp_path: Path) -> None:
    first = project(tmp_path)
    alias = ProjectLocation.inspect(tmp_path / "a" / ".." / "a" / "a.cst")
    assert first.overlaps(alias)
    (tmp_path / "a" / "a.cst").touch()
    with pytest.raises(ProjectStorageError, match="dedicated"):
        ProjectLocation.inspect(tmp_path / "a" / "second.cst")
    (tmp_path / "a" / "second.cst").touch()
    with pytest.raises(ProjectStorageError, match="dedicated"):
        ProjectLocation.inspect(tmp_path / "a" / "a.cst")
    with pytest.raises(ProjectStorageError):
        ProjectLocation.inspect(tmp_path / "missing" / "x.cst")


def test_hardlinks_across_directories_are_not_independent(tmp_path: Path) -> None:
    a, b = project(tmp_path, "a"), project(tmp_path, "b")
    Path(a.path).touch()
    os.link(a.path, b.path)
    assert ProjectLocation.inspect(Path(a.path)).overlaps(ProjectLocation.inspect(Path(b.path)))


def test_lease_is_exclusive_and_released(tmp_path: Path) -> None:
    state = tmp_path / "state"
    with RecoveryStore(state).session():
        with pytest.raises(RecoveryError):
            with RecoveryStore(state).session():
                pytest.fail("second session admitted")
    with RecoveryStore(state).session() as store:
        assert store.incidents() == ()


def test_lease_context_preserves_application_primary_error(tmp_path: Path) -> None:
    primary = OSError("synthetic application failure")
    with pytest.raises(OSError) as caught:
        with RecoveryStore(tmp_path / "state").session():
            raise primary
    assert caught.value is primary


@pytest.mark.parametrize("corruption", ["missing", "invalid", "missing_field", "bad_clearance"])
def test_expected_missing_or_corrupt_state_blocks(tmp_path: Path, corruption: str) -> None:
    state = tmp_path / "state"
    with RecoveryStore(state).session() as store:
        store.prepare(str(uuid.uuid4()), "create", project(tmp_path))
    ledger = state / "recovery.json"
    if corruption == "missing":
        ledger.unlink()
    elif corruption == "invalid":
        ledger.write_text("{", encoding="utf-8")
    else:
        data = json.loads(ledger.read_text(encoding="utf-8"))
        if corruption == "missing_field":
            del data["incidents"][0]["state"]
        else:
            data["incidents"][0]["state"] = "reconciled"
        ledger.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RecoveryError, match="missing or corrupt"):
        with RecoveryStore(state).session():
            pytest.fail("corrupt state admitted")


def test_human_findings_do_not_clear_unresolved_activity(tmp_path: Path) -> None:
    with RecoveryStore(tmp_path / "state").session() as store:
        incident = store.prepare(str(uuid.uuid4()), "launch", project(tmp_path))
        store.finish(incident, "uncertain")
        store.reconcile(
            incident, project_confirmed=True, effects_resolved=True, activity_resolved=False
        )
        assert store.incidents(unresolved_only=True)[0].human_evidence is True
        store.reconcile(
            incident, project_confirmed=True, effects_resolved=True, activity_resolved=True
        )
        assert store.incidents(unresolved_only=True) == ()
        assert store.incidents()[0].state == "reconciled"


def test_uncertainty_or_restart_cannot_be_finalized_without_human(tmp_path: Path) -> None:
    state = tmp_path / "state"
    with RecoveryStore(state).session() as store:
        record = store.prepare(str(uuid.uuid4()), "edit", project(tmp_path))
        with pytest.raises(RecoveryError, match="still in flight"):
            store.reconcile(
                record, project_confirmed=True, effects_resolved=True, activity_resolved=True
            )
        store.finish(record, "uncertain")
        with pytest.raises(RecoveryError, match="human reconciliation"):
            store.finish(record, "settled")
    with RecoveryStore(state).session() as store:
        with pytest.raises(RecoveryError, match="human reconciliation"):
            store.finish(record, "settled")
        store.reconcile(
            record, project_confirmed=True, effects_resolved=True, activity_resolved=True
        )
        assert store.incidents(unresolved_only=True) == ()


def test_notes_deletion_and_project_movement_do_not_clear_incident(tmp_path: Path) -> None:
    location = project(tmp_path)
    notes = Path(location.directory) / "a.cst.agentic.json"
    notes.write_text("{}", encoding="utf-8")
    state = tmp_path / "state"
    with RecoveryStore(state).session() as store:
        store.prepare(str(uuid.uuid4()), "edit", location)
    notes.unlink()
    Path(location.directory).rename(tmp_path / "moved")
    moved = ProjectLocation.inspect(tmp_path / "moved" / "a.cst")
    with RecoveryStore(state).session() as store:
        assert len(store.incidents(unresolved_only=True)) == 1
        assert moved.overlaps(store.incidents()[0].project)


def test_failed_initial_write_leaves_expected_state_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    with monkeypatch.context() as patch:

        def refuse(*args: object) -> None:
            raise OSError("must not surface this raw error")

        patch.setattr(os, "replace", refuse)
        with pytest.raises(RecoveryError, match="persistence failed"):
            with RecoveryStore(state).session():
                pytest.fail("failed initialization admitted")
    with pytest.raises(RecoveryError, match="missing or corrupt"):
        with RecoveryStore(state).session():
            pytest.fail("missing expected initial ledger admitted")


def test_fresh_process_lease_refusal(tmp_path: Path) -> None:
    """Invoke helpers through uv, as required for every Python execution."""
    state = tmp_path / "state"
    script = tmp_path / "lease_probe.py"
    script.write_text(
        "from pathlib import Path\n"
        "from cst_agentic.recovery import RecoveryStore, RecoveryError\n"
        "import sys\n"
        "try:\n"
        "    with RecoveryStore(Path(sys.argv[1])).session():\n"
        "        sys.exit(9)\n"
        "except RecoveryError:\n"
        "    sys.exit(0)\n",
        encoding="utf-8",
    )
    with RecoveryStore(state).session():
        result = subprocess.run(
            ["uv", "run", "--no-sync", "python", str(script), str(state)],
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0
