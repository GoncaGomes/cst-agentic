"""Public production configuration, session and terminal boundaries; offline only."""

import json
import shutil
import sys
from pathlib import Path

import pytest

from cst_agentic.controller_config import load_controller_config


def test_controller_configuration_is_separate_and_allowlists_child_environment(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "peer.cmd"
    executable.touch()
    config_file = tmp_path / "controller.env"
    config_file.write_text(
        "SKYNET_BASE_URL=https://institution.invalid/v1\n"
        "SKYNET_API_KEY=synthetic-model-secret\nAGENT=Qwen-configured\n"
        f"CST_MCP_SERVER_EXECUTABLE={executable.as_posix()}\n"
        f"CST_MCP_SERVER_CWD={tmp_path.as_posix()}\n"
        f"CST_CONTROLLER_WORK_DIR={(tmp_path / 'work').as_posix()}\n",
        encoding="utf-8",
    )
    config = load_controller_config(env_path=config_file)
    child = config.child_env(
        {
            "PATH": "safe-path",
            "SKYNET_API_KEY": "synthetic-model-secret",
            "PYTHONPATH": "unreviewed",
            "PYTHONHOME": "unreviewed",
            "ARBITRARY_CONFIG": "unreviewed",
            "ACCESS_TOKEN": "unreviewed",
            "CST_CONNECT_MODE": "auto",
            "CST_TOOLSETS": "all",
        }
    )
    assert child == {
        "PATH": "safe-path",
        "CST_CONNECT_MODE": "manual",
        "CST_TOOLSETS": (
            "connection,official,project,geometry,boolean,transforms,materials,ports,boundaries,"
            "mesh,solvers,simulation,results,import_export,parameters,diagnostics,pcb,workflows"
        ),
        "CST_WORK_DIR": str(config.work_dir),
    }
    assert config.model == "Qwen-configured"
    assert config.startup_timeout_s == 120
    assert config.shutdown_timeout_s == 30
    assert "synthetic-model-secret" not in repr(config)


@pytest.mark.parametrize(
    "mismatch", [None, "endpoint", "model", "adapter", "validated", "headroom"]
)
def test_context_validation_record_is_bound_to_configured_endpoint_model_and_adapter(
    tmp_path, mismatch
):
    from cst_agentic.config import ConfigError
    from cst_agentic.context_budget import ACCOUNTING_METHOD, adapter_identity

    executable = tmp_path / "peer.cmd"
    executable.touch()
    record = {
        "method": ACCOUNTING_METHOD,
        "input_capacity": 32_000,
        "headroom": 4_000,
        "endpoint": "https://institution.invalid/v1",
        "model": "controlled-model",
        "adapter": adapter_identity(),
        "validated": True,
        "validation_reference": "synthetic-offline-fixture-not-real-evidence",
    }
    if mismatch is not None:
        record[mismatch] = False if mismatch == "validated" else "synthetic-private-mismatch"
    validation_file = tmp_path / "validation.json"
    validation_file.write_text(json.dumps(record), encoding="utf-8")
    config_file = tmp_path / "controller.env"
    config_file.write_text(
        "SKYNET_BASE_URL=https://institution.invalid/v1\n"
        "SKYNET_API_KEY=synthetic-only\nAGENT=controlled-model\n"
        f"CST_MCP_SERVER_EXECUTABLE={executable.as_posix()}\n"
        f"CST_MCP_SERVER_CWD={tmp_path.as_posix()}\n"
        f"CST_CONTROLLER_WORK_DIR={(tmp_path / 'work').as_posix()}\n"
        f"CST_CONTROLLER_CONTEXT_VALIDATION_FILE={validation_file.as_posix()}\n",
        encoding="utf-8",
    )
    if mismatch is not None:
        with pytest.raises(ConfigError, match="context validation") as caught:
            load_controller_config(env_path=config_file)
        assert "synthetic-private" not in str(caught.value)
    else:
        config = load_controller_config(env_path=config_file)
        assert config.context_budget is not None
        assert config.context_budget.blocker is None
        assert config.context_budget.input_capacity == 32_000
        assert "CST_CONTROLLER_CONTEXT_VALIDATION_FILE" not in config.child_env({})


def test_sdk_environment_expansion_requires_review_before_spawn(tmp_path: Path, monkeypatch):
    from mcp.client import stdio

    from cst_agentic.config import ConfigError

    config = manual_config(tmp_path)
    monkeypatch.setattr(
        stdio, "DEFAULT_INHERITED_ENV_VARS", [*stdio.DEFAULT_INHERITED_ENV_VARS, "ARBITRARY_TOKEN"]
    )
    with pytest.raises(ConfigError, match="requires review"):
        config.child_env({"ARBITRARY_TOKEN": "synthetic-only"})


@pytest.mark.asyncio
async def test_production_factory_refuses_incident_before_constructing_transport(
    tmp_path: Path,
) -> None:
    from cst_agentic.controller_config import ControllerConfig
    from cst_agentic.controller_runtime import create_controller_session
    from cst_agentic.recovery import RecoveryError, RecoveryStore

    state = tmp_path / "state"
    with RecoveryStore(state).session() as store:
        import uuid

        incident = store.prepare(str(uuid.uuid4()), "launch", None)
    config = ControllerConfig(
        "https://institution.invalid/v1",
        "synthetic",
        "Qwen",
        tmp_path / "DOES-NOT-EXIST.cmd",
        tmp_path,
        tmp_path,
    )
    with pytest.raises(RecoveryError, match="isolation evidence"):
        async with create_controller_session(config, state_directory=state):
            pytest.fail("unresolved route admitted")
    with RecoveryStore(state).session() as store:
        assert store.incidents(unresolved_only=True)[0].id == incident


def manual_config(tmp_path: Path, mode: str = "healthy"):
    from cst_agentic.controller_config import ControllerConfig

    if sys.platform != "win32":
        pytest.skip("Windows public stdio production factory")
    uv = shutil.which("uv")
    assert uv is not None
    peer = Path(__file__).parent / "fixtures" / "manual_peer.py"
    launcher = tmp_path / "manual-peer.cmd"
    observation = tmp_path / "observed.json"
    launcher.write_text(
        f'@echo off\n"{uv}" run --no-sync python -u "{peer}" {mode} "{observation}"\n',
        encoding="utf-8",
    )
    return ControllerConfig(
        "https://institution.invalid/v1",
        "synthetic",
        "Qwen",
        launcher,
        Path(__file__).resolve().parents[1],
        tmp_path,
    )


@pytest.mark.asyncio
async def test_actual_factory_manual_environment_no_dispatch_and_lease(
    tmp_path: Path, monkeypatch, capfd
):
    from cst_agentic.controller_runtime import create_controller_session
    from cst_agentic.recovery import RecoveryError, RecoveryStore

    config = manual_config(tmp_path)
    for key in ("SKYNET_API_KEY", "PYTHONPATH", "PYTHONHOME", "ARBITRARY_CONFIG", "ACCESS_TOKEN"):
        monkeypatch.setenv(key, "synthetic-secret")
    state = tmp_path / "state"
    async with create_controller_session(config, state_directory=state) as runtime:
        assert runtime.model.model == "Qwen"
        assert runtime.run_config.tracing_disabled
        assert runtime.coordinator is not None
        assert {tool.name for tool in runtime.coordinator.active_tools} == {
            "cst_connection_status",
            "cst_project_info",
            "discover_tools",
        }
        with pytest.raises(RecoveryError):
            with RecoveryStore(state).session():
                pytest.fail("second lease admitted")
    observation = json.loads((tmp_path / "observed.json").read_text(encoding="utf-8"))
    assert observation == {
        "manual": True,
        "toolsets": True,
        "work": True,
        "forbidden": [],
        "calls": [],
    }
    assert "synthetic-private-server-stderr" not in capfd.readouterr().err
    with RecoveryStore(state).session() as reopened:
        assert reopened.incidents() == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("validation", ["missing", "matched", "wrong_model"])
async def test_factory_wires_context_budget_without_bypassing_other_acceptance_gates(
    tmp_path, validation
):
    from dataclasses import replace

    from cst_agentic.controller_runtime import create_controller_session
    from cst_agentic.recovery import RecoveryError
    from fakes import offline_context_budget

    config = manual_config(tmp_path)
    if validation != "missing":
        config = replace(
            config,
            context_budget=replace(
                offline_context_budget(),
                endpoint=config.base_url,
                model=config.model if validation == "matched" else "different-model",
            ),
        )
    if validation == "wrong_model":
        with pytest.raises(RecoveryError, match="context validation"):
            async with create_controller_session(config, state_directory=tmp_path / "state"):
                pytest.fail("mismatched provider admitted")
        assert not (tmp_path / "observed.json").exists()
    else:
        async with create_controller_session(config, state_directory=tmp_path / "state") as runtime:
            reply = await runtime.coordinator.submit("Inspect only")
            assert reply.state == "paused"
            kind = "context_pause" if validation == "missing" else "context_accounting"
            assert any(e.kind == kind for e in reply.events)
            assert "#24" in reply.text
        assert json.loads((tmp_path / "observed.json").read_text(encoding="utf-8"))["calls"] == []


@pytest.mark.asyncio
async def test_terminal_warns_confirms_exit_and_never_dispatches_work(tmp_path: Path):
    from cst_agentic.controller_runtime import run_controller_terminal

    commands = iter(["launch CST", "quit", "no", "quit", "exit"])
    output: list[str] = []

    async def read_line(prompt: str) -> str:
        output.append(prompt)
        return next(commands)

    result = await run_controller_terminal(
        manual_config(tmp_path),
        read_line=read_line,
        write_line=output.append,
        state_directory=tmp_path / "state",
    )
    assert result == 0
    text = "\n".join(output).lower()
    assert "unsaved work" in text
    assert "active simulations" in text
    assert "unknown" in text
    assert "no survival guarantee" in text
    assert "exit cancelled" in text
    assert "#24" in text
    assert json.loads((tmp_path / "observed.json").read_text(encoding="utf-8"))["calls"] == []


def test_cli_controller_uses_isolated_central_state_and_confirms_exit(
    tmp_path: Path, monkeypatch, capsys
):
    from cst_agentic.cli import main

    config = manual_config(tmp_path)
    env_file = tmp_path / "cli.env"
    env_file.write_text(
        "SKYNET_BASE_URL=https://institution.invalid/v1\n"
        "SKYNET_API_KEY=synthetic-only\nAGENT=Qwen\n"
        f"CST_MCP_SERVER_EXECUTABLE={config.mcp_executable.as_posix()}\n"
        f"CST_MCP_SERVER_CWD={config.mcp_cwd.as_posix()}\n"
        f"CST_CONTROLLER_WORK_DIR={tmp_path.as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    import msvcrt

    characters = iter("quit\rexit\r")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(msvcrt, "kbhit", lambda: True)
    monkeypatch.setattr(msvcrt, "getwch", lambda: next(characters))
    assert main(["controller", "--env", str(env_file)]) == 0
    assert "manual mode" in capsys.readouterr().out
    assert (tmp_path / "user" / "CST-Agentic" / "recovery.json").is_file()


@pytest.mark.asyncio
async def test_blocked_console_reader_cancellation_does_not_leave_executor_thread(monkeypatch):
    import asyncio
    import msvcrt
    import threading

    from cst_agentic.controller_runtime import terminal_input

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(msvcrt, "kbhit", lambda: False)
    monkeypatch.setattr("builtins.input", lambda prompt: threading.Event().wait(0.5))
    before = set(threading.enumerate())
    reader = asyncio.create_task(terminal_input("Controller> "))
    await asyncio.sleep(0.05)
    reader.cancel()
    with pytest.raises(asyncio.CancelledError):
        await reader
    assert set(threading.enumerate()) == before


@pytest.mark.asyncio
async def test_terminal_interruption_while_console_waits_warns_and_releases_lease(
    tmp_path: Path, monkeypatch
):
    import asyncio
    import msvcrt

    from cst_agentic.controller_runtime import run_controller_terminal
    from cst_agentic.recovery import RecoveryStore

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(msvcrt, "kbhit", lambda: False)
    ready = asyncio.Event()
    output: list[str] = []

    def write_line(message: str) -> None:
        output.append(message)
        if "Controller ready" in message:
            ready.set()

    before = asyncio.all_tasks()
    task = asyncio.create_task(
        run_controller_terminal(
            manual_config(tmp_path),
            write_line=write_line,
            state_directory=tmp_path / "state",
        )
    )
    await asyncio.wait_for(ready.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert any("interrupted" in message for message in output)
    assert any("Unsaved work" in message for message in output)
    assert not (asyncio.all_tasks() - before)
    with RecoveryStore(tmp_path / "state").session() as store:
        assert store.incidents() == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["refusal", "timeout", "catalogue_timeout", "bad_catalogue", "missing_info"]
)
async def test_production_startup_failure_releases_lease_and_owner_tasks(tmp_path: Path, mode: str):
    import asyncio
    from dataclasses import replace

    from cst_agentic.controller_runtime import create_controller_session
    from cst_agentic.mcp_client import McpStartupError
    from cst_agentic.recovery import RecoveryStore

    config = manual_config(tmp_path, mode)
    if "timeout" in mode:
        config = replace(config, startup_timeout_s=1.5)
    before = asyncio.all_tasks()
    with pytest.raises(McpStartupError, match="startup failed"):
        async with create_controller_session(config, state_directory=tmp_path / "state"):
            pytest.fail("bad startup admitted")
    assert json.loads((tmp_path / "observed.json").read_text(encoding="utf-8"))["calls"] == []
    assert not (asyncio.all_tasks() - before)
    with RecoveryStore(tmp_path / "state").session() as store:
        assert store.incidents() == ()


@pytest.mark.asyncio
async def test_real_factory_cleanup_failures_preserve_primary_and_hold_lease(
    tmp_path: Path, monkeypatch
):
    import asyncio

    from mcp import ClientSession
    from openai import AsyncOpenAI

    from cst_agentic.controller_runtime import create_controller_session
    from cst_agentic.recovery import RecoveryError, RecoveryStore

    state = tmp_path / "state"
    owner = asyncio.current_task()
    session_exit = ClientSession.__aexit__
    provider_close = AsyncOpenAI.close
    exits: list[str] = []

    def assert_leased():
        assert asyncio.current_task() is owner
        with pytest.raises(RecoveryError):
            with RecoveryStore(state).session():
                pytest.fail("lease released before cleanup")

    async def fail_session_exit(self, *args):
        assert_leased()
        await session_exit(self, *args)
        exits.append("transport")
        raise RuntimeError("synthetic-private-sdk-cleanup")

    async def fail_provider_close(self):
        assert_leased()
        await provider_close(self)
        exits.append("provider")
        raise RuntimeError("synthetic-private-provider-cleanup")

    monkeypatch.setattr(ClientSession, "__aexit__", fail_session_exit)
    monkeypatch.setattr(AsyncOpenAI, "close", fail_provider_close)
    primary = ValueError("synthetic-primary")
    with pytest.raises(BaseExceptionGroup) as caught:
        async with create_controller_session(manual_config(tmp_path), state_directory=state):
            raise primary

    def leaves(error):
        if isinstance(error, BaseExceptionGroup):
            return [leaf for child in error.exceptions for leaf in leaves(child)]
        return [error]

    errors = leaves(caught.value)
    assert errors[0] is primary
    assert any("provider cleanup failed" in str(error) for error in errors)
    assert any("SDK context cleanup failed" in str(error) for error in errors)
    assert all("synthetic-private" not in str(error) for error in errors)
    assert exits == ["provider", "transport"]
    with RecoveryStore(state).session() as store:
        assert store.incidents() == ()


@pytest.mark.asyncio
async def test_provider_and_transport_share_one_cleanup_allowance(tmp_path: Path, monkeypatch):
    import asyncio
    from dataclasses import replace

    from openai import AsyncOpenAI

    from cst_agentic.controller_runtime import create_controller_session
    from cst_agentic.recovery import RecoveryStore

    original_close = AsyncOpenAI.close

    async def slow_close(self):
        await original_close(self)
        await asyncio.sleep(30)

    monkeypatch.setattr(AsyncOpenAI, "close", slow_close)
    config = replace(manual_config(tmp_path), shutdown_timeout_s=0.1)
    before = asyncio.all_tasks()
    with pytest.raises(BaseExceptionGroup) as caught:
        async with create_controller_session(config, state_directory=tmp_path / "state"):
            pass

    def messages(error):
        if isinstance(error, BaseExceptionGroup):
            return [message for child in error.exceptions for message in messages(child)]
        return [str(error)]

    errors = messages(caught.value)
    assert "Controller provider cleanup failed." in errors
    assert "Controller total cleanup allowance exceeded." in errors
    assert not (asyncio.all_tasks() - before)
    with RecoveryStore(tmp_path / "state").session() as store:
        assert store.incidents() == ()


@pytest.mark.asyncio
async def test_factory_eof_refusing_peer_still_unwinds_without_leaked_tasks(tmp_path: Path):
    import asyncio

    from cst_agentic.controller_runtime import create_controller_session
    from cst_agentic.recovery import RecoveryStore

    before = asyncio.all_tasks()
    async with create_controller_session(
        manual_config(tmp_path, "eof_refusal"), state_directory=tmp_path / "state"
    ):
        pass
    assert not (asyncio.all_tasks() - before)
    with RecoveryStore(tmp_path / "state").session() as store:
        assert store.incidents() == ()


@pytest.mark.asyncio
async def test_terminal_eof_warns_without_native_exit_actions(tmp_path: Path):
    from cst_agentic.controller_runtime import run_controller_terminal

    output: list[str] = []

    async def read_line(prompt: str) -> str:
        raise EOFError

    assert (
        await run_controller_terminal(
            manual_config(tmp_path),
            read_line=read_line,
            write_line=output.append,
            state_directory=tmp_path / "state",
        )
        == 1
    )
    assert any("without confirmation" in line for line in output)
    assert any("Unsaved work" in line for line in output)
    assert json.loads((tmp_path / "observed.json").read_text(encoding="utf-8"))["calls"] == []


def test_controller_configuration_errors_never_echo_values(tmp_path: Path, monkeypatch):
    from cst_agentic.cli import main

    env_file = tmp_path / "invalid.env"
    env_file.write_text(
        "SKYNET_BASE_URL=https://synthetic-user:synthetic-password@institution.invalid/v1\n",
        encoding="utf-8",
    )
    # CLI output boundary, including malformed credential-bearing endpoint.
    output: list[str] = []
    monkeypatch.setattr("builtins.print", lambda text, **kwargs: output.append(str(text)))
    assert main(["controller", "--env", str(env_file)]) == 1
    assert output == [
        "Controller failure: SKYNET_BASE_URL must be a credential-free HTTPS endpoint."
    ]
