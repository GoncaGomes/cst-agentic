"""Configuration loading and validation for the connectivity check.

The check reads its settings from the repository ``.env`` file (without
modifying it) and, as a fallback, from the process environment.

Precedence (highest first):

1. Explicit overrides passed to :func:`load_connectivity_config` (tests).
2. Values in the ``.env`` file.
3. Process environment variables.

The ``.env`` file is treated as authoritative because it is the project's
explicit configuration, whereas the process environment is ambient and can
contain unrelated variables that happen to share a project key name (for
example a generic ``AGENT``). Preferring the file keeps the check bound to the
configured institutional model and endpoint instead of an ambient value.
Credentials are only ever referenced by name and are never included in error
messages or logs.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

#: Environment variables that carry secrets; these must never reach the MCP
#: child process or appear in diagnostics.
_CREDENTIAL_KEY_MARKERS = ("API_KEY", "APIKEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")

#: Environment variables that drive the MCP server child process.
_MCP_CHILD_KEYS = ("CST_PATH", "CST_VERSION", "CST_WORK_DIR", "CST_CONNECT_MODE", "CST_TOOLSETS")


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid.

    Messages name the offending variable or path but never include secret
    values, so they are safe to print or store as evidence.
    """


@dataclass(frozen=True)
class ConnectivityConfig:
    """Validated settings for one connectivity check run."""

    base_url: str
    api_key: str
    model: str
    mcp_executable: Path
    mcp_cwd: Path
    work_dir: Path
    max_turns: int
    request_timeout_s: float
    startup_timeout_s: float
    shutdown_timeout_s: float
    mcp_request_timeout_s: float

    def child_env(self, parent_env: Mapping[str, str]) -> dict[str, str]:
        """Build the environment for the MCP child process.

        The parent environment is copied with credential-bearing entries
        removed. ``CST_CONNECT_MODE`` is forced to ``disabled`` regardless of
        what the parent environment specifies, and ``CST_WORK_DIR`` is pinned
        to the client-owned work directory so the server only writes there.
        """
        env = {key: value for key, value in parent_env.items() if not _is_credential_key(key)}
        for key in _MCP_CHILD_KEYS:
            env.pop(key, None)
        env["CST_CONNECT_MODE"] = "disabled"
        env["CST_WORK_DIR"] = str(self.work_dir)
        env["CST_TOOLSETS"] = "core"
        return env


def _is_credential_key(key: str) -> bool:
    """Return True when a variable name looks like it carries a secret."""
    upper = key.upper()
    return any(marker in upper for marker in _CREDENTIAL_KEY_MARKERS)


def _resolve(
    env_file: Mapping[str, str],
    key: str,
    override: str | None,
) -> str | None:
    """Resolve one setting: explicit override, then the .env file, then env."""
    if override is not None:
        return override
    file_value = env_file.get(key)
    if file_value is not None and file_value.strip():
        return file_value.strip()
    env_value = os.environ.get(key)
    if env_value is not None and env_value.strip():
        return env_value.strip()
    return None


def _require(
    env_file: Mapping[str, str],
    key: str,
    override: str | None,
) -> str:
    value = _resolve(env_file, key, override)
    if value is None:
        raise ConfigError(
            f"Required setting {key} is missing or empty. Provide it in the "
            "environment or the .env file."
        )
    return value


def _default_work_dir() -> Path:
    return Path(tempfile.gettempdir()) / "opencode" / "cst-agentic" / "work"


def load_connectivity_config(
    *,
    env_path: str | Path | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    mcp_executable: str | None = None,
    mcp_cwd: str | None = None,
    work_dir: str | None = None,
    max_turns: int | None = None,
    request_timeout_s: float | None = None,
    startup_timeout_s: float | None = None,
    shutdown_timeout_s: float | None = None,
    mcp_request_timeout_s: float | None = None,
) -> ConnectivityConfig:
    """Load and validate connectivity settings.

    Arguments other than ``env_path`` act as explicit overrides (highest
    precedence, mainly for tests). ``env_path`` defaults to ``.env`` in the
    current working directory; a missing file is tolerated as long as the
    process environment already provides every required value. See the module
    docstring for the full precedence order.

    Raises:
        ConfigError: when a required value is missing/empty, or the MCP
            executable or working directory does not exist.
    """
    path = Path(env_path) if env_path is not None else Path(".env")
    env_file = dotenv_values(path) if path.exists() else {}

    resolved_base_url = _require(env_file, "SKYNET_BASE_URL", base_url)
    resolved_api_key = _require(env_file, "SKYNET_API_KEY", api_key)
    resolved_model = _require(env_file, "AGENT", model)
    resolved_executable = _require(env_file, "CST_MCP_SERVER_EXECUTABLE", mcp_executable)
    resolved_cwd = _require(env_file, "CST_MCP_SERVER_CWD", mcp_cwd)

    executable = Path(resolved_executable)
    if not executable.is_file():
        raise ConfigError(
            f"MCP executable {executable} does not exist or is not a file. "
            "Check CST_MCP_SERVER_EXECUTABLE."
        )
    cwd = Path(resolved_cwd)
    if not cwd.is_dir():
        raise ConfigError(
            f"MCP working directory {cwd} does not exist or is not a directory. "
            "Check CST_MCP_SERVER_CWD."
        )

    if work_dir is not None:
        resolved_work_dir = Path(work_dir)
    else:
        resolved_work_dir = Path(
            _resolve(env_file, "CST_MCP_WORK_DIR", None) or _default_work_dir()
        )
    resolved_work_dir = resolved_work_dir.expanduser().resolve()
    resolved_work_dir.mkdir(parents=True, exist_ok=True)

    turns = max_turns if max_turns is not None else 6
    if turns < 1:
        raise ConfigError("max_turns must be a positive integer.")
    request_timeout = request_timeout_s if request_timeout_s is not None else 120.0
    startup_timeout = startup_timeout_s if startup_timeout_s is not None else 60.0
    shutdown_timeout = shutdown_timeout_s if shutdown_timeout_s is not None else 15.0
    mcp_request_timeout = mcp_request_timeout_s if mcp_request_timeout_s is not None else 30.0
    for label, value in (
        ("request_timeout_s", request_timeout),
        ("startup_timeout_s", startup_timeout),
        ("shutdown_timeout_s", shutdown_timeout),
        ("mcp_request_timeout_s", mcp_request_timeout),
    ):
        if value <= 0:
            raise ConfigError(f"{label} must be positive, got {value}.")

    return ConnectivityConfig(
        base_url=resolved_base_url,
        api_key=resolved_api_key,
        model=resolved_model,
        mcp_executable=executable,
        mcp_cwd=cwd,
        work_dir=resolved_work_dir,
        max_turns=turns,
        request_timeout_s=request_timeout,
        startup_timeout_s=startup_timeout,
        shutdown_timeout_s=shutdown_timeout,
        mcp_request_timeout_s=mcp_request_timeout,
    )
