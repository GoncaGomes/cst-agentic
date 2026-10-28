"""Reviewed CAD/view destinations; no semantic permission or silent replacement.

Ported selectively from the preserved issue-24 WIP. Model-visible schemas stay
canonical. Existing outputs require a different destination; replacement is not
currently exposed by those schemas and is never inferred from conversation.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .mcp_client import McpToolCall
from .project_storage import ProjectStorageError


def output_destination(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ProjectStorageError("Choose an explicit absolute export output path.")
    path = Path(value)
    if not path.is_absolute() or not path.suffix or path.suffix.lower() == ".cst":
        raise ProjectStorageError("Export requires an absolute non-project output file.")
    try:
        for part in (path, *path.parents):
            if part == part.parent:
                continue
            if (
                part.name.rstrip(" .") != part.name
                or ":" in part.name
                or part.is_reserved()
                or part.is_symlink()
                or part.is_junction()
            ):
                raise ProjectStorageError("Ambiguous or linked export paths are refused.")
        if not path.parent.is_dir():
            raise ProjectStorageError("Choose an existing export parent directory.")
        if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
            raise ProjectStorageError("Export destination has a directory or hard-link conflict.")
        return os.path.normcase(str(path.resolve()))
    except (OSError, ValueError, RuntimeError):
        raise ProjectStorageError("Export filesystem identity is unavailable.") from None


def export_outputs(name: str, arguments: Mapping[str, Any]) -> tuple[str, ...]:
    if name == "cst_export_cad":
        path = output_destination(arguments.get("file_path"))
        extensions = {
            "stl": {".stl"},
            "sat": {".sat"},
            "stp": {".stp", ".step"},
            "igs": {".igs", ".iges"},
            "obj": {".obj"},
            "nas": {".nas"},
        }
        format_name = arguments.get("format")
        if not isinstance(format_name, str) or Path(path).suffix.lower() not in extensions.get(
            format_name, set()
        ):
            raise ProjectStorageError("CAD output extension must match the explicit format.")
        return (path,)
    if name != "cst_export_structure_views":
        raise ProjectStorageError("Export route is not reviewed.")
    directory = arguments.get("out_dir")
    if not isinstance(directory, str) or not Path(directory).is_absolute():
        raise ProjectStorageError("Choose an explicit absolute structure-view output directory.")
    views = arguments.get("views") or ["perspective", "front", "top", "left", "right"]
    supported = {"perspective", "front", "back", "top", "bottom", "left", "right", "xy", "xz", "yz"}
    if not isinstance(views, list) or any(
        not isinstance(v, str) or v not in supported for v in views
    ):
        raise ProjectStorageError("Choose supported named structure views.")
    if len(set(views)) != len(views):
        raise ProjectStorageError("Duplicate structure views are refused.")
    return tuple(output_destination(str(Path(directory) / f"view_{view}.png")) for view in views)


def interpret_export_response(result: McpToolCall) -> bool:
    """Matching response/artifact presence, never CAD/image correctness."""
    if result.is_error or not result.evidence_complete:
        return False
    data = result.structured_content
    if not isinstance(data, dict):
        return False
    try:
        outputs = export_outputs(result.name, result.arguments)
        if any(not Path(path).is_file() or Path(path).stat().st_size == 0 for path in outputs):
            return False
        if result.name == "cst_export_cad":
            return (
                data.get("status") == "executed"
                and data.get("format") == result.arguments.get("format")
                and output_destination(data.get("exported_file")) == outputs[0]
            )
        images = data.get("images")
        return (
            data.get("status") == "ok"
            and isinstance(images, list)
            and len(images) == len(outputs)
            and all(
                isinstance(image, dict)
                and image.get("status") == "executed"
                and image.get("exists") is True
                and output_destination(image.get("path")) == path
                for image, path in zip(images, outputs, strict=True)
            )
        )
    except (OSError, ValueError, TypeError, ProjectStorageError):
        return False
