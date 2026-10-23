"""Central, single-writer recovery ledger, independent of project decision notes.

File flush/fsync and atomic replacement protect controlled process-crash
windows. This is not a power-loss, hostile-tampering or disk-failure guarantee.
Complete deletion of the central state directory cannot be detected locally.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .project_storage import ProjectLocation


class RecoveryError(Exception):
    """Bounded, credential-safe storage or admission failure."""


IncidentState = Literal["in_flight", "received_unresolved", "uncertain", "settled", "reconciled"]
_STATES = {"in_flight", "received_unresolved", "uncertain", "settled", "reconciled"}
_SETTLED = {"settled", "reconciled"}


@dataclass(frozen=True)
class Incident:
    id: str
    task_id: str
    operation: str
    project: ProjectLocation | None
    instance_id: str | None = None
    state: IncidentState = "in_flight"
    # No raw arguments, responses, exception messages, or user prose persisted.
    human_evidence: bool = False
    effects_resolved: bool = False
    activity_resolved: bool = False


def controller_state_directory() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local or not Path(local).is_absolute():
        raise RecoveryError("LOCALAPPDATA must identify the Windows user state directory.")
    return Path(local) / "CST-Agentic"


class RecoveryStore:
    """Hold the OS lease for the entire session, including startup and cleanup.

    One versioned ledger makes incident updates atomic together. The persistent
    lease header marks that a ledger is expected, including an initial-write
    crash. Missing header/ledger combinations fail closed. OS locking releases
    on process death, but the header and incidents remain. Paths are injectable
    only for isolated tests or explicitly configured application storage.
    """

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory if directory is not None else controller_state_directory()
        self._lease = None
        self._failed = False
        self._owned_incidents: set[str] = set()

    @contextmanager
    def session(self) -> Iterator[RecoveryStore]:
        if self._lease is not None:
            raise RecoveryError("A Controller session is already active.")
        lease = None
        locked = False
        yielded = False
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            lock_path = self.directory / "session.lock"
            ledger = self.directory / "recovery.json"
            if not lock_path.exists() and ledger.exists():
                raise RecoveryError("Expected recovery lease metadata is missing.")
            lease = lock_path.open("a+b")
            lease.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            self._lease = lease
            self._failed = False
            self._owned_incidents = set()
            lease.seek(0)
            header = lease.read()
            if not header:
                if ledger.exists():
                    raise RecoveryError("Recovery lease metadata is corrupt.")
                lease.write(b"CST-Agentic recovery v1\n")
                lease.flush()
                os.fsync(lease.fileno())
                self._write([])
            elif header != b"CST-Agentic recovery v1\n":
                raise RecoveryError("Recovery lease metadata is corrupt.")
            self.incidents()  # Missing/corrupt expected ledger blocks before transport.
            yielded = True
            yield self
        except OSError:
            if yielded:
                raise  # Do not relabel or suppress an application primary error.
            raise RecoveryError("Controller lease or recovery storage is unavailable.") from None
        finally:
            primary = sys.exception()
            self._lease = None
            if lease is not None:
                try:
                    try:
                        if locked:
                            lease.seek(0)
                            if os.name == "nt":
                                import msvcrt

                                msvcrt.locking(lease.fileno(), msvcrt.LK_UNLCK, 1)
                            else:
                                import fcntl

                                fcntl.flock(lease.fileno(), fcntl.LOCK_UN)
                    finally:
                        lease.close()
                except OSError:
                    cleanup = RecoveryError("Controller lease cleanup failed.")
                    if primary is not None:
                        raise BaseExceptionGroup(
                            "Controller lease exit failed", [primary, cleanup]
                        ) from None
                    raise cleanup from None

    def _require_session(self) -> None:
        if self._lease is None or self._failed:
            raise RecoveryError("Recovery storage is not ready; dispatch is blocked.")

    def incidents(self, *, unresolved_only: bool = False) -> tuple[Incident, ...]:
        self._require_session()
        try:
            data = json.loads((self.directory / "recovery.json").read_text(encoding="utf-8"))
            if (
                set(data) != {"version", "incidents"}
                or type(data["version"]) is not int
                or data["version"] != 1
            ):
                raise ValueError
            if not isinstance(data["incidents"], list):
                raise ValueError
            records = []
            for item in data["incidents"]:
                item = dict(item)
                if set(item) != {
                    "id",
                    "task_id",
                    "operation",
                    "project",
                    "instance_id",
                    "state",
                    "human_evidence",
                    "effects_resolved",
                    "activity_resolved",
                }:
                    raise ValueError
                if item["project"] is not None:
                    item["project"] = ProjectLocation(**item["project"])
                    if not all(
                        isinstance(value, str) and value
                        for value in (
                            item["project"].path,
                            item["project"].directory,
                            item["project"].directory_id,
                        )
                    ):
                        raise ValueError
                    location = item["project"]
                    if (
                        not Path(location.path).is_absolute()
                        or str(Path(location.path).parent) != location.directory
                        or Path(location.path).suffix.lower() != ".cst"
                        or not re.fullmatch(r"\d+:\d+", location.directory_id)
                        or (
                            location.file_id is not None
                            and not re.fullmatch(r"\d+:\d+", location.file_id)
                        )
                    ):
                        raise ValueError
                record = Incident(**item)
                if record.instance_id is not None and not re.fullmatch(
                    r"[A-Za-z0-9_.:-]{1,160}", record.instance_id
                ):
                    raise ValueError
                uuid.UUID(record.id)
                uuid.UUID(record.task_id)
                if record.state not in _STATES or not re.fullmatch(
                    r"[A-Za-z0-9_]{1,100}", record.operation
                ):
                    raise ValueError
                if any(
                    type(value) is not bool
                    for value in (
                        record.human_evidence,
                        record.effects_resolved,
                        record.activity_resolved,
                    )
                ):
                    raise ValueError
                if record.state == "reconciled" and not (
                    record.human_evidence and record.effects_resolved and record.activity_resolved
                ):
                    raise ValueError
                records.append(record)
            if len({record.id for record in records}) != len(records):
                raise ValueError
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            self._failed = True
            raise RecoveryError("Expected recovery state is missing or corrupt.") from None
        return tuple(r for r in records if not unresolved_only or r.state not in _SETTLED)

    def prepare(
        self,
        task_id: str,
        operation: str,
        project: ProjectLocation | None,
        instance_id: str | None = None,
    ) -> str:
        uuid.UUID(task_id)
        if not re.fullmatch(r"[A-Za-z0-9_]{1,100}", operation):
            raise RecoveryError("Operation identifier is invalid.")
        if instance_id is not None and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", instance_id):
            raise RecoveryError("Instance identifier is invalid.")
        records = list(self.incidents())
        record = Incident(str(uuid.uuid4()), task_id, operation, project, instance_id)
        self._write([*records, record])
        self._owned_incidents.add(record.id)
        return record.id

    def finish(self, incident_id: str, state: IncidentState) -> None:
        """Called by trusted outcome interpretation, never directly by model output."""
        if state not in {"settled", "received_unresolved", "uncertain"}:
            raise RecoveryError("Invalid recovery settlement.")
        record = next((r for r in self.incidents() if r.id == incident_id), None)
        if (
            record is None
            or incident_id not in self._owned_incidents
            or record.state == "uncertain"
        ):
            raise RecoveryError("An uncertain or restored incident requires human reconciliation.")
        self._update(incident_id, state=state)

    def reconcile(
        self,
        incident_id: str,
        *,
        project_confirmed: bool,
        effects_resolved: bool,
        activity_resolved: bool,
    ) -> None:
        """Record explicit human findings as flags, not independent readback.

        Detailed discussion stays session-only. Unresolved effects/activity retain
        the block. This never changes a protected client's latch or starts a task.
        """
        if any(
            type(v) is not bool for v in (project_confirmed, effects_resolved, activity_resolved)
        ):
            raise RecoveryError("Explicit human reconciliation findings are required.")
        if any(
            r.id == incident_id and r.state == "in_flight" and r.id in self._owned_incidents
            for r in self.incidents()
        ):
            raise RecoveryError("Cannot reconcile an operation still in flight in this session.")
        self._update(
            incident_id,
            state="reconciled"
            if project_confirmed and effects_resolved and activity_resolved
            else None,
            human_evidence=True,
            effects_resolved=effects_resolved,
            activity_resolved=activity_resolved,
        )

    def _update(self, incident_id: str, **changes: object) -> None:
        records = list(self.incidents())
        for index, record in enumerate(records):
            if record.id == incident_id:
                if record.state in _SETTLED:
                    raise RecoveryError("Recovery record is already finalized.")
                values = asdict(record)
                values.update({key: value for key, value in changes.items() if value is not None})
                values["project"] = record.project
                records[index] = Incident(**values)
                self._write(records)
                return
        raise RecoveryError("Recovery record was not found.")

    def _write(self, records: list[Incident]) -> None:
        self._require_session()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.directory,
                prefix="recovery-",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump({"version": 1, "incidents": [asdict(r) for r in records]}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.directory / "recovery.json")
        except OSError:
            self._failed = True
            raise RecoveryError("Recovery persistence failed; dispatch is blocked.") from None
        finally:
            if temporary is not None and temporary.exists():
                # Do not suppress cleanup failures or expose OS exception text.
                try:
                    temporary.unlink()
                except OSError:
                    self._failed = True
                    raise RecoveryError("Recovery temporary-file cleanup failed.") from None
