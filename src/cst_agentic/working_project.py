"""Application-owned exact task permission and session-bound live target evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .mcp_client import McpToolCall
from .project_storage import ProjectLocation, ProjectStorageError
from .recovery import RecoveryError


def _signature(name: str, arguments: Mapping[str, Any]) -> str:
    return json.dumps([name, dict(arguments)], sort_keys=True, allow_nan=False)


@dataclass(frozen=True)
class TaskPermission:
    path: str
    action: str
    launch_new: bool
    outcome: str
    changes: str
    consequences: frozenset[str]
    operations: frozenset[str]

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> TaskPermission:
        """Only explicit local human input may call this; never model output."""
        if set(value) != {
            "path",
            "action",
            "launch_new",
            "outcome",
            "changes",
            "consequences",
            "operations",
        }:
            raise RecoveryError("Task instruction requires exact documented fields.")
        if value["action"] not in {"create", "open"} or value["launch_new"] is not True:
            raise RecoveryError("Explicit new-instance launch and create/open action required.")
        for field in ("path", "outcome", "changes"):
            if not isinstance(value[field], str) or not value[field].strip():
                raise RecoveryError("Task destination, outcome and agreed changes are required.")
        if not Path(value["path"]).is_absolute():
            raise RecoveryError("Task destination must be absolute.")
        consequences = value["consequences"]
        if not isinstance(consequences, list) or any(
            item not in {"save", "overwrite", "discard", "delete_results", "run_simulation"}
            for item in consequences
        ):
            raise RecoveryError("Unknown task consequence permission.")
        operations = value["operations"]
        if not isinstance(operations, list):
            raise RecoveryError("Exact agreed operations are required.")
        signatures = set()
        for operation in operations:
            if (
                not isinstance(operation, dict)
                or set(operation) != {"name", "arguments"}
                or not isinstance(operation["name"], str)
                or not isinstance(operation["arguments"], dict)
            ):
                raise RecoveryError("Each operation requires a name and exact arguments.")
            signatures.add(_signature(operation["name"], operation["arguments"]))
        return cls(
            value["path"],
            value["action"],
            True,
            value["outcome"],
            value["changes"],
            frozenset(consequences),
            frozenset(signatures),
        )


@dataclass(frozen=True)
class LiveBinding:
    path: str
    connection: str
    project: str
    sequence: int
    location: ProjectLocation
    provenance: str = "held-project.filename"


class WorkingProject:
    """Evidence is local to this transport/task; a pause never renews permission."""

    def __init__(self) -> None:
        self.permission: TaskPermission | None = None
        self.binding: LiveBinding | None = None
        self.connection: str | None = None
        self.stage = "unselected"
        self.generation = 0
        self.sequence = 0
        self.valid = False
        self._remaining: set[str] = set()

    def begin(self, permission: TaskPermission) -> None:
        if permission.launch_new is not True:
            raise RecoveryError("Explicit new-instance launch permission required.")
        if self.connection is not None:
            raise RecoveryError("New-instance task requires a fresh Controller session.")
        location = ProjectLocation.inspect(Path(permission.path))
        if permission.action == "create" and location.file_id is not None:
            raise RecoveryError("Creation destination exists; no overwrite or suffix fallback.")
        if permission.action == "open" and location.file_id is None:
            raise RecoveryError("Requested existing project is unavailable.")
        self.permission = permission
        self._remaining = set(permission.operations)
        self.stage = "probe"
        self.generation += 1
        self.valid = True

    def invalidate(self) -> None:
        self.valid = False
        self.generation += 1

    def metadata(self) -> dict[str, Any]:
        if self.permission is None or not self.valid:
            raise RecoveryError("Task permission/live target requires renewed prerequisites.")
        return {
            "version": 1,
            "stage": self.stage,
            "path": ProjectLocation.inspect(Path(self.permission.path)).path,
            "connection": self.connection,
            "project": self.binding.project if self.binding else None,
            "generation": self.generation,
        }

    def admits(
        self,
        project: ProjectLocation,
        name: str,
        arguments: Mapping[str, Any],
        metadata: dict | None,
    ) -> bool:
        if (
            not self.valid
            or self.permission is None
            or metadata is None
            or metadata != self.metadata()
        ):
            return False
        if project.path != metadata["path"]:
            return False
        if self.stage == "probe":
            return name == "cst_connection_status" and not arguments
        if self.stage == "launch":
            return name == "cst_connect" and dict(arguments) == {"mode": "new"}
        if self.stage == "select":
            expected = (
                "cst_create_project" if self.permission.action == "create" else "cst_open_project"
            )
            return name == expected and dict(arguments) == {"path": project.path}
        if self.stage != "bound" or self.binding is None:
            return False
        current = ProjectLocation.inspect(Path(project.path))
        if current != self.binding.location:
            self.invalidate()
            return False
        if _signature(name, arguments) not in self._remaining:
            return False
        if name in {"cst_connect", "cst_create_project", "cst_open_project"} or name.startswith(
            "cst_workflow"
        ):
            return False
        required = set()
        if name == "cst_save_project":
            required.add("save")
            if arguments.get("path") is not None:
                destination = ProjectLocation.inspect(Path(arguments["path"]))
                if destination.path != project.path:
                    return False
        if name in {"cst_close_project", "cst_disconnect"}:
            required.add("discard")
        if "delete" in name and "result" in name:
            required.add("delete_results")
        if name in {"cst_run_simulation", "cst_start_simulation", "cst_run_simulation_async"}:
            required.add("run_simulation")
        return required <= self.permission.consequences

    def check(self, project: ProjectLocation, name: str, arguments: Mapping[str, Any]):
        from .controller import DispatchEvidence

        if self.admits(project, name, arguments, self.metadata()):
            return DispatchEvidence(self.connection, project_scoped=self.stage == "bound")
        return None

    def accept(self, result: McpToolCall) -> bool:
        """Interpret protocol evidence, not response echoes or requested path caches."""
        if not self.valid:
            return False
        try:
            data = result.structured_content
            evidence = data["controller"] if isinstance(data, dict) else None
            if result.is_error or not result.evidence_complete or not isinstance(evidence, dict):
                raise ValueError
            if evidence.get("version") != 1:
                raise ValueError
            if self.stage == "probe":
                if evidence.get("stage") != "probe":
                    raise ValueError
                self.stage = "launch"
                return True
            sequence = evidence["sequence"]
            connection = evidence["connection"]
            if (
                type(sequence) is not int
                or sequence <= self.sequence
                or not isinstance(connection, str)
                or not connection
            ):
                raise ValueError
            if self.stage == "launch":
                if evidence.get("stage") != "launch":
                    raise ValueError
                self.connection = connection
                self.stage = "select"
            else:
                if (
                    connection != self.connection
                    or evidence.get("source") != "held-project.filename"
                ):
                    raise ValueError
                path = ProjectLocation.inspect(Path(evidence["path"])).path
                if (
                    path != self.metadata()["path"]
                    or not isinstance(evidence["project"], str)
                    or not evidence["project"]
                ):
                    raise ValueError
                if self.binding is not None and evidence["project"] != self.binding.project:
                    raise ValueError
                if (
                    self.stage == "bound"
                    and self.binding is not None
                    and self.binding.location != ProjectLocation.inspect(Path(path))
                ):
                    raise ValueError
                if self.stage == "bound":
                    self._remaining.discard(_signature(result.name, result.arguments))
                self.binding = LiveBinding(
                    path,
                    connection,
                    evidence["project"],
                    sequence,
                    ProjectLocation.inspect(Path(path)),
                )
                self.stage = "bound"
            self.sequence = sequence
            return True
        except (KeyError, ValueError, TypeError, OSError, ProjectStorageError, RecoveryError):
            self.invalidate()
            return False
