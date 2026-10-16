"""Offline tests for configuration loading, precedence, and child env."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from cst_agentic.config import (
    ConfigError,
    ConnectivityConfig,
    _is_credential_key,
    load_connectivity_config,
)


def _write_env(tmp_path: Path, body: str) -> Path:
    env = tmp_path / ".env"
    env.write_text(textwrap.dedent(body), encoding="utf-8")
    return env


def _valid_body() -> str:
    return """
        SKYNET_BASE_URL=https://example.invalid/openai
        SKYNET_API_KEY=file-secret
        AGENT=qwen3.8-27b
        CST_MCP_SERVER_EXECUTABLE=C:\\fake\\server.exe
        CST_MCP_SERVER_CWD=C:\\fake\\cwd
    """


def test_loads_all_values_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point the executable/cwd at real temp paths so validation passes.
    exe = tmp_path / "server.exe"
    exe.write_text("")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    env = _write_env(
        tmp_path,
        f"""
        SKYNET_BASE_URL=https://example.invalid/openai
        SKYNET_API_KEY=file-secret
        AGENT=qwen3.8-27b
        CST_MCP_SERVER_EXECUTABLE={exe}
        CST_MCP_SERVER_CWD={cwd}
    """,
    )
    # Clear ambient values that could interfere.
    for key in (
        "SKYNET_BASE_URL",
        "SKYNET_API_KEY",
        "AGENT",
        "CST_MCP_SERVER_EXECUTABLE",
        "CST_MCP_SERVER_CWD",
    ):
        monkeypatch.delenv(key, raising=False)
    cfg = load_connectivity_config(env_path=env)
    assert cfg.base_url == "https://example.invalid/openai"
    assert cfg.api_key == "file-secret"
    assert cfg.model == "qwen3.8-27b"
    assert cfg.mcp_executable == exe
    assert cfg.mcp_cwd == cwd


def test_override_beats_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exe = tmp_path / "server.exe"
    exe.write_text("")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    env = _write_env(
        tmp_path,
        _valid_body().replace("C:\\fake\\server.exe", str(exe)).replace("C:\\fake\\cwd", str(cwd)),
    )
    for key in (
        "SKYNET_BASE_URL",
        "SKYNET_API_KEY",
        "AGENT",
        "CST_MCP_SERVER_EXECUTABLE",
        "CST_MCP_SERVER_CWD",
    ):
        monkeypatch.delenv(key, raising=False)
    cfg = load_connectivity_config(env_path=env, model="other-model")
    assert cfg.model == "other-model"


def test_file_beats_ambient_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exe = tmp_path / "server.exe"
    exe.write_text("")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    env = _write_env(
        tmp_path,
        f"""
        SKYNET_BASE_URL=https://example.invalid/openai
        SKYNET_API_KEY=file-secret
        AGENT=qwen3.8-27b
        CST_MCP_SERVER_EXECUTABLE={exe}
        CST_MCP_SERVER_CWD={cwd}
    """,
    )
    # An unrelated ambient AGENT (e.g. from a host harness) must not win.
    monkeypatch.setenv("AGENT", "1")
    for key in (
        "SKYNET_BASE_URL",
        "SKYNET_API_KEY",
        "CST_MCP_SERVER_EXECUTABLE",
        "CST_MCP_SERVER_CWD",
    ):
        monkeypatch.delenv(key, raising=False)
    cfg = load_connectivity_config(env_path=env)
    assert cfg.model == "qwen3.8-27b"


def test_missing_file_falls_back_to_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SKYNET_BASE_URL", "https://example.invalid/openai")
    monkeypatch.setenv("SKYNET_API_KEY", "env-secret")
    monkeypatch.setenv("AGENT", "qwen3.8-27b")
    exe = tmp_path / "server.exe"
    exe.write_text("")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setenv("CST_MCP_SERVER_EXECUTABLE", str(exe))
    monkeypatch.setenv("CST_MCP_SERVER_CWD", str(cwd))
    cfg = load_connectivity_config(env_path=tmp_path / "does-not-exist.env")
    assert cfg.api_key == "env-secret"
    assert cfg.model == "qwen3.8-27b"


def test_missing_required_raises_without_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exe = tmp_path / "server.exe"
    exe.write_text("")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    env = _write_env(
        tmp_path,
        f"""
        SKYNET_BASE_URL=https://example.invalid/openai
        AGENT=qwen3.8-27b
        CST_MCP_SERVER_EXECUTABLE={exe}
        CST_MCP_SERVER_CWD={cwd}
    """,
    )
    for key in (
        "SKYNET_BASE_URL",
        "SKYNET_API_KEY",
        "AGENT",
        "CST_MCP_SERVER_EXECUTABLE",
        "CST_MCP_SERVER_CWD",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ConfigError) as excinfo:
        load_connectivity_config(env_path=env)
    message = str(excinfo.value)
    assert "SKYNET_API_KEY" in message
    # The (absent) secret value must never appear; guard against echoing values.
    assert "file-secret" not in message


def test_empty_required_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exe = tmp_path / "server.exe"
    exe.write_text("")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    env = _write_env(
        tmp_path,
        f"""
        SKYNET_BASE_URL=https://example.invalid/openai
        SKYNET_API_KEY=
        AGENT=qwen3.8-27b
        CST_MCP_SERVER_EXECUTABLE={exe}
        CST_MCP_SERVER_CWD={cwd}
    """,
    )
    for key in (
        "SKYNET_BASE_URL",
        "SKYNET_API_KEY",
        "AGENT",
        "CST_MCP_SERVER_EXECUTABLE",
        "CST_MCP_SERVER_CWD",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ConfigError):
        load_connectivity_config(env_path=env)


def test_invalid_executable_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    env = _write_env(
        tmp_path,
        f"""
        SKYNET_BASE_URL=https://example.invalid/openai
        SKYNET_API_KEY=file-secret
        AGENT=qwen3.8-27b
        CST_MCP_SERVER_EXECUTABLE={tmp_path / "nope.exe"}
        CST_MCP_SERVER_CWD={cwd}
    """,
    )
    for key in (
        "SKYNET_BASE_URL",
        "SKYNET_API_KEY",
        "AGENT",
        "CST_MCP_SERVER_EXECUTABLE",
        "CST_MCP_SERVER_CWD",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ConfigError) as excinfo:
        load_connectivity_config(env_path=env)
    assert "CST_MCP_SERVER_EXECUTABLE" in str(excinfo.value)


def test_invalid_cwd_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exe = tmp_path / "server.exe"
    exe.write_text("")
    env = _write_env(
        tmp_path,
        f"""
        SKYNET_BASE_URL=https://example.invalid/openai
        SKYNET_API_KEY=file-secret
        AGENT=qwen3.8-27b
        CST_MCP_SERVER_EXECUTABLE={exe}
        CST_MCP_SERVER_CWD={tmp_path / "nope-cwd"}
    """,
    )
    for key in (
        "SKYNET_BASE_URL",
        "SKYNET_API_KEY",
        "AGENT",
        "CST_MCP_SERVER_EXECUTABLE",
        "CST_MCP_SERVER_CWD",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ConfigError) as excinfo:
        load_connectivity_config(env_path=env)
    assert "CST_MCP_SERVER_CWD" in str(excinfo.value)


def test_is_credential_key() -> None:
    assert _is_credential_key("SKYNET_API_KEY")
    assert _is_credential_key("OPENAI_API_KEY")
    assert _is_credential_key("MY_TOKEN")
    assert _is_credential_key("DB_SECRET")
    assert not _is_credential_key("CST_WORK_DIR")
    assert not _is_credential_key("PATH")


def _cfg(tmp_path: Path) -> ConnectivityConfig:
    return ConnectivityConfig(
        base_url="https://example.invalid/openai",
        api_key="secret",
        model="qwen3.8-27b",
        mcp_executable=tmp_path / "s.exe",
        mcp_cwd=tmp_path / "cwd",
        work_dir=tmp_path / "work",
        max_turns=4,
        request_timeout_s=10.0,
        startup_timeout_s=10.0,
        shutdown_timeout_s=10.0,
        mcp_request_timeout_s=10.0,
    )


def test_child_env_strips_credentials_and_forces_mode(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    parent = {
        "PATH": "C:\\bin",
        "SKYNET_API_KEY": "leak1",
        "OPENAI_API_KEY": "leak2",
        "CST_CONNECT_MODE": "auto",
        "CST_WORK_DIR": "C:\\evil",
        "CST_TOOLSETS": "all",
        "SOME_TOKEN": "leak3",
    }
    env = cfg.child_env(parent)
    assert "SKYNET_API_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    assert "SOME_TOKEN" not in env
    assert env["CST_CONNECT_MODE"] == "disabled"
    assert env["CST_WORK_DIR"] == str(cfg.work_dir)
    assert env["CST_TOOLSETS"] == "core"
    assert env["PATH"] == "C:\\bin"
