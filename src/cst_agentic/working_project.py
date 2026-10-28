"""Session-bound live target evidence, independent of conversational interpretation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .mcp_client import McpToolCall
from .output_storage import export_outputs
from .project_storage import ProjectLocation, ProjectStorageError
from .recovery import RecoveryError


def _signature(name: str, arguments: Mapping[str, Any]) -> str:
    return json.dumps([name, dict(arguments)], sort_keys=True, allow_nan=False)


@dataclass(frozen=True)
class TaskPermission:
    """Legacy local setup input; operation/consequence fields are not execution grants."""

    path: str
    action: Literal["create", "open"]
    launch_new: bool
    outcome: str
    changes: str
    consequences: frozenset[str]
    operations: frozenset[str]

    def __post_init__(self) -> None:
        if self.action not in {"create", "open"} or self.launch_new is not True:
            raise RecoveryError("Explicit new-instance launch and create/open action required.")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (self.path, self.outcome, self.changes)
        ):
            raise RecoveryError("Task destination, outcome and agreed changes are required.")
        if not Path(self.path).is_absolute():
            raise RecoveryError("Task destination must be absolute.")
        if not isinstance(self.consequences, frozenset) or not self.consequences <= {
            "save",
            "overwrite",
            "discard",
            "delete_results",
            "run_simulation",
        }:
            raise RecoveryError("Unknown task consequence permission.")
        if not isinstance(self.operations, frozenset):
            raise RecoveryError("Immutable exact operation grants are required.")
        for signature in self.operations:
            try:
                name, arguments = json.loads(signature)
                if (
                    not isinstance(name, str)
                    or not isinstance(arguments, dict)
                    or _signature(name, arguments) != signature
                ):
                    raise ValueError
            except (TypeError, ValueError):
                raise RecoveryError("Invalid exact operation grant.") from None

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


def _selection_location(path: object, action: Literal["create", "open"]) -> ProjectLocation:
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise RecoveryError("Choose an exact absolute .cst destination.")
    location = ProjectLocation.inspect(Path(path))
    if location.file_id is not None and Path(location.path).stat().st_nlink != 1:
        raise RecoveryError("Project hard-link destinations are refused.")
    if action == "create" and location.file_id is not None:
        raise RecoveryError(
            "Creation destination exists; choose another path, no overwrite or suffix fallback."
        )
    if action == "open" and location.file_id is None:
        raise RecoveryError("Requested existing project is unavailable; choose a file.")
    return location


class WorkingProject:
    """Live evidence belongs to one connection; conversational tasks do not renew it."""

    def __init__(self) -> None:
        self.permission: TaskPermission | None = None
        self.target_path: str | None = None
        self.selection_action: Literal["create", "open"] | None = None
        self.binding: LiveBinding | None = None
        self.connection: str | None = None
        self.stage = "unselected"
        self.generation = 0
        self.sequence = 0
        self.valid = False
        self.refusal: str | None = None

    def launch(self) -> None:
        """Prepare protocol checks from a proposed call, not a semantic grant."""
        if self.stage != "unselected" or self.connection is not None:
            raise RecoveryError("Use the current Controller-owned instance; no extra launch.")
        self.stage = "probe"
        self.valid = True
        self.generation += 1

    def begin(self, permission: TaskPermission) -> None:
        if permission.launch_new is not True:
            raise RecoveryError("Explicit new-instance launch permission required.")
        if self.connection is not None:
            raise RecoveryError("New-instance task requires a fresh Controller session.")
        location = _selection_location(permission.path, permission.action)
        self.permission = permission
        self.target_path = location.path
        self.selection_action = permission.action
        self.stage = "probe"
        self.generation += 1
        self.valid = True

    def select(self, name: str, arguments: Mapping[str, Any]) -> ProjectLocation:
        """Validate the actual proposed destination; never adopt an active project."""
        if not self.valid or self.stage != "connection" or self.binding is not None:
            raise RecoveryError("Launch a Controller-owned instance before selecting a project.")
        if name not in {"cst_create_project", "cst_open_project"}:
            raise RecoveryError("Selection requires a supported create/open operation.")
        action = "create" if name == "cst_create_project" else "open"
        location = _selection_location(arguments.get("path"), action)
        self.target_path = location.path
        self.selection_action = action
        self.stage = "select"
        self.generation += 1
        return location

    def selection_not_dispatched(self, metadata: dict | None) -> bool:
        """Release only this unexecuted selection; never restore invalid evidence."""
        if (
            not self.valid
            or self.stage != "select"
            or self.binding is not None
            or self.connection is None
            or metadata is None
            or metadata.get("generation") != self.generation
            or metadata.get("connection") != self.connection
            or metadata.get("path") != self.target_path
        ):
            return False
        self.target_path = None
        self.selection_action = None
        self.stage = "connection"
        self.generation += 1
        return True

    def invalidate(self) -> None:
        self.valid = False
        self.generation += 1

    def context(self) -> dict[str, Any]:
        """Detached authoritative scope, not an additional model capability."""
        binding = self.binding
        return {
            "provenance": "application-owned technical state and session-bound API readback",
            "valid": self.valid,
            "stage": self.stage,
            "owned_connection": self.connection,
            "generation": self.generation,
            "selected_path": binding.path if binding else self.target_path,
            "interpretation": "Qwen follows original user messages and agreed consequences; "
            "this state does not independently prove consent.",
            "inspection_gaps": ["geometry", "units", "parameters", "solver/setup", "results"],
            "binding": {
                "connection": binding.connection,
                "project": binding.project,
                "sequence": binding.sequence,
                "provenance": binding.provenance,
                "scope": "target readback only; model/setup/result facts remain uninspected",
            }
            if binding
            else None,
        }

    def metadata(self) -> dict[str, Any]:
        if not self.valid:
            raise RecoveryError("Live target requires renewed technical prerequisites.")
        return {
            "version": 1,
            "stage": self.stage,
            "path": ProjectLocation.inspect(Path(self.target_path)).path
            if self.target_path
            else None,
            "connection": self.connection,
            "project": self.binding.project if self.binding else None,
            "generation": self.generation,
        }

    def admits(
        self,
        project: ProjectLocation | None,
        name: str,
        arguments: Mapping[str, Any],
        metadata: dict | None,
    ) -> bool:
        self.refusal = None
        try:
            admitted = self._admits(project, name, arguments, metadata)
        except (ProjectStorageError, RecoveryError) as error:
            self.refusal = str(error)
            return False
        if not admitted:
            self.refusal = (
                "Select and verify an exact project before project-dependent operations."
                if self.stage == "connection"
                else "Live target, connection or queued technical state changed; "
                "re-establish relevant prerequisites."
            )
        return admitted

    def _admits(
        self,
        project: ProjectLocation | None,
        name: str,
        arguments: Mapping[str, Any],
        metadata: dict | None,
    ) -> bool:
        if not self.valid or metadata is None or metadata != self.metadata():
            return False
        if self.stage == "probe":
            return name == "cst_connection_status" and not arguments
        if self.stage == "launch":
            if name != "cst_connect" or dict(arguments) != {"mode": "new"}:
                raise RecoveryError(
                    "Only mode=new launch is supported; no existing-instance attachment."
                )
            return True
        if self.stage == "connection":
            return name == "cst_connection_status" and not arguments
        if project is None or project.path != metadata["path"]:
            return False
        if self.stage == "select":
            expected = (
                "cst_create_project" if self.selection_action == "create" else "cst_open_project"
            )
            return (
                name == expected
                and self.selection_action is not None
                and _selection_location(arguments.get("path"), self.selection_action).path
                == project.path
            )
        if self.stage != "bound" or self.binding is None:
            return False
        if self.binding.connection != self.connection:
            self.invalidate()
            return False
        current = ProjectLocation.inspect(Path(project.path))
        if current != self.binding.location or Path(current.path).stat().st_nlink != 1:
            self.invalidate()
            return False
        if name in {
            "cst_connect",
            "cst_create_project",
            "cst_open_project",
        } or name.startswith("cst_workflow"):
            return False
        if name in {"cst_export_cad", "cst_export_structure_views"}:
            outputs = export_outputs(name, arguments)
            if any(Path(path).exists() for path in outputs):
                raise ProjectStorageError(
                    "Export destination exists; choose unused outputs. Replacement is unsupported "
                    "on this route; no file was overwritten."
                )
        if name == "cst_save_project":
            if arguments.get("path") is not None:
                destination = ProjectLocation.inspect(Path(arguments["path"]))
                if destination.path != project.path:
                    raise ProjectStorageError(
                        "Save destination differs from the selected project. Cross-project "
                        "Save As is unsupported; choose the verified target."
                    )
        return True

    def check(self, project: ProjectLocation | None, name: str, arguments: Mapping[str, Any]):
        from .controller import DispatchEvidence

        if self.admits(project, name, arguments, self.metadata()):
            return DispatchEvidence(self.connection, project_scoped=self.stage == "bound")
        return None

    def accept(self, result: McpToolCall) -> bool:
        """Interpret protocol evidence, not response echoes or requested path caches."""
        if not self.valid:
            return False
        data = None
        try:
            data = result.structured_content
            evidence = data["controller"] if isinstance(data, dict) else None
            if result.is_error or not result.evidence_complete or not isinstance(evidence, dict):
                raise ValueError
            if type(evidence.get("version")) is not int or evidence["version"] != 1:
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
                self.stage = "select" if self.target_path else "connection"
            elif self.stage == "connection":
                if connection != self.connection or evidence.get("stage") != "connection":
                    raise ValueError
            else:
                if (
                    connection != self.connection
                    or evidence.get("source") != "held-project.filename"
                ):
                    raise ValueError
                path = ProjectLocation.inspect(Path(evidence["path"])).path
                if Path(path).stat().st_nlink != 1:
                    raise ValueError
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
            self.refusal = "Missing or stale actual live-target readback; inspect locally."
            # Only fixed server diagnostics are surfaced; never arbitrary vendor text.
            message = data.get("message") if isinstance(data, dict) else None
            if not isinstance(message, str):
                message = None
            if message in {
                "CST must be closed; conflicting instance or unknown instance check.",
                "Detected existing CST instance; not closed.",
                "Conflicting CST instance detected, or instance check unavailable.",
            }:
                self.refusal = "CST instance conflict; inspect locally. No instance was closed."
            elif message in {
                "Creation destination already exists.",
                "Selection destination does not match.",
                "Each project requires its own dedicated directory.",
            }:
                self.refusal = "Destination conflict; choose an exact available dedicated path."
            self.invalidate()
            return False


def interpret_setup_response(result: McpToolCall) -> bool:
    """Narrow setup settlement; ControllerSession independently checks live evidence."""
    expected = {
        "cst_connection_status": {"probe", "connection", "bound", None},
        "cst_connect": {"launch"},
        "cst_create_project": {"select", None},
        "cst_open_project": {"select", None},
    }
    data = result.structured_content
    evidence = data.get("controller") if isinstance(data, dict) else None
    return (
        not result.is_error
        and result.evidence_complete
        and isinstance(data, dict)
        and data.get("status") not in {"error", "busy", "timeout", "offline"}
        and isinstance(evidence, dict)
        and type(evidence.get("version")) is int
        and evidence.get("version") == 1
        and evidence.get("stage") in expected.get(result.name, set())
    )
