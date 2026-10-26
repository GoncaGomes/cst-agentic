"""Controller-only configuration. Never reuse connectivity's child environment."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values
from mcp.client import stdio

from .config import ConfigError

# Reviewed category spellings at cst-mcp a4a177a; availability only, not authority.
# Some categories also advertise excluded tools, which discovery/gateway never approve.
CONTROLLER_TOOLSETS = (
    "connection,official,project,geometry,boolean,transforms,materials,ports,boundaries,"
    "mesh,solvers,simulation,results,import_export,parameters,diagnostics,pcb,workflows"
)

# Reviewed against public SDK environment merging. New SDK defaults require review
# rather than silently expanding the child's inherited environment.
CHILD_OS_KEYS = frozenset(
    {
        "APPDATA",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "PROCESSOR_ARCHITECTURE",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "USERNAME",
        "USERPROFILE",
        "HOME",
        "LOGNAME",
        "SHELL",
        "TERM",
        "TMPDIR",
        "USER",
    }
)


@dataclass(frozen=True)
class ControllerConfig:
    base_url: str
    api_key: str = field(repr=False)
    model: str
    mcp_executable: Path
    mcp_cwd: Path
    work_dir: Path
    startup_timeout_s: float = 120
    shutdown_timeout_s: float = 30

    def child_env(self, parent_env: Mapping[str, str]) -> dict[str, str]:
        if not set(stdio.DEFAULT_INHERITED_ENV_VARS) <= CHILD_OS_KEYS:
            raise ConfigError("MCP SDK inherited environment requires review.")
        env = {
            key: value
            for key, value in parent_env.items()
            if key in CHILD_OS_KEYS and not value.startswith("()")
        }
        env.update(
            CST_CONNECT_MODE="manual",
            CST_TOOLSETS=CONTROLLER_TOOLSETS,
            CST_WORK_DIR=str(self.work_dir),
        )
        return env


def load_controller_config(*, env_path: str | Path = ".env") -> ControllerConfig:
    """Retain configured institutional provider/model without performing requests."""
    try:
        path = Path(env_path)
        values = dotenv_values(path, interpolate=False) if path.exists() else {}

        def required(name: str) -> str:
            value = values.get(name) or os.environ.get(name)
            if not value or not value.strip() or "\x00" in value:
                raise ConfigError(f"{name} is missing or invalid.")
            return value.strip()

        base_url = required("SKYNET_BASE_URL")
        try:
            url = urlsplit(base_url)
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                raise ValueError
            if url.query or url.fragment:
                raise ValueError
        except ValueError:
            raise ConfigError("SKYNET_BASE_URL must be a credential-free HTTPS endpoint.") from None
        executable = Path(required("CST_MCP_SERVER_EXECUTABLE"))
        cwd = Path(required("CST_MCP_SERVER_CWD"))
        if not executable.is_absolute() or not executable.is_file():
            raise ConfigError(
                "CST_MCP_SERVER_EXECUTABLE must identify an absolute executable file."
            )
        if not cwd.is_absolute() or not cwd.is_dir():
            raise ConfigError("CST_MCP_SERVER_CWD must identify an absolute directory.")
        work = Path(required("CST_CONTROLLER_WORK_DIR"))
        if not work.is_absolute():
            raise ConfigError("CST_CONTROLLER_WORK_DIR must identify an absolute directory.")
        work.mkdir(parents=True, exist_ok=True)
        return ControllerConfig(
            base_url, required("SKYNET_API_KEY"), required("AGENT"), executable, cwd, work.resolve()
        )
    except (OSError, ValueError):
        raise ConfigError("Controller configuration or filesystem is unavailable.") from None
