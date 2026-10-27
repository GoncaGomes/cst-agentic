"""Dedicated project directory checks; never move, save or create native files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ProjectStorageError(Exception):
    """A project cannot be safely identified in a dedicated directory."""


@dataclass(frozen=True)
class ProjectLocation:
    """Canonical location, including filesystem identity for alias detection.

    The directory must already exist; the requested CST file may be new.
    Directory creation/selection is an explicit caller responsibility.
    """

    path: str
    directory: str
    directory_id: str
    file_id: str | None

    @classmethod
    def inspect(cls, path: Path) -> ProjectLocation:
        try:
            if path.suffix.lower() != ".cst":
                raise ProjectStorageError("A .cst project path is required.")
            if path.name.rstrip(" .") != path.name or ":" in path.name or path.is_reserved():
                raise ProjectStorageError("Ambiguous Windows destination names are refused.")
            directory = path.parent.resolve(strict=True)
            if not directory.is_dir():
                raise ProjectStorageError("The project directory is unavailable.")
            requested = directory / path.name
            # Reject a symlink/reparse alias to a file outside the dedicated directory.
            resolved = requested.resolve(strict=False)
            if resolved.parent != directory:
                raise ProjectStorageError("Project file aliases outside its directory are refused.")
            for entry in directory.iterdir():
                if entry.suffix.lower() == ".cst" and (
                    os.path.normcase(str(entry)) != os.path.normcase(str(requested))
                ):
                    raise ProjectStorageError("Each project requires a dedicated directory.")
            if requested.exists() and not requested.is_file():
                raise ProjectStorageError("The project path is not a regular file.")
            stat = directory.stat()
            file_stat = requested.stat() if requested.exists() else None
            if file_stat is not None and file_stat.st_nlink != 1:
                raise ProjectStorageError("Project hard-link aliases are refused.")
            if not stat.st_ino or (file_stat is not None and not file_stat.st_ino):
                raise ProjectStorageError("Stable filesystem identity is unavailable.")
            return cls(
                path=os.path.normcase(str(resolved)),
                directory=os.path.normcase(str(directory)),
                directory_id=f"{stat.st_dev}:{stat.st_ino}",
                file_id=f"{file_stat.st_dev}:{file_stat.st_ino}" if file_stat else None,
            )
        except (OSError, ValueError, RuntimeError):
            raise ProjectStorageError("Project filesystem identity is unavailable.") from None

    def overlaps(self, other: ProjectLocation) -> bool:
        return (
            self.path == other.path
            or self.directory == other.directory
            or self.directory_id == other.directory_id
            or (self.file_id is not None and self.file_id == other.file_id)
        )
