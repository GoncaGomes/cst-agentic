"""Offline regression checks for the explicit diagnostic command surface."""

import pytest

from cst_agentic import cli


def test_help_lists_connectivity_and_discovery(capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["--help"])
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert "{verify-connectivity,discover-tools}" in output
    assert "controller" not in output.lower()
    assert "recovery" not in output.lower()
    assert "evaluate" not in output.lower()


@pytest.mark.parametrize("command", ["controller", "recovery", "evaluate"])
def test_removed_commands_are_rejected(command, capsys):
    with pytest.raises(SystemExit) as error:
        cli.main([command])
    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_verify_dispatches_with_explicit_env(monkeypatch):
    received = []

    def run_verify(env_path):
        received.append(env_path)
        return 1

    monkeypatch.setattr(cli, "_run_verify", run_verify)
    assert cli.main(["verify-connectivity", "--env", "local.env"]) == 1
    assert received == ["local.env"]


def test_discover_dispatches_with_explicit_env(monkeypatch):
    received = []

    def run_discover(env_path):
        received.append(env_path)
        return 1

    monkeypatch.setattr(cli, "_run_discover", run_discover)
    assert cli.main(["discover-tools", "--env", "local.env"]) == 1
    assert received == ["local.env"]


@pytest.mark.parametrize("success", [True, False])
def test_discover_loads_24_turn_config_and_prints_result(monkeypatch, capsys, success):
    from types import SimpleNamespace

    from cst_agentic.discovery import DiscoveryReport

    received = {}
    config = SimpleNamespace()

    def load_config(**kwargs):
        received.update(kwargs)
        return config

    async def run_check(actual):
        assert actual is config
        return DiscoveryReport(success=success)

    monkeypatch.setattr(cli, "load_connectivity_config", load_config)
    monkeypatch.setattr(cli, "run_discovery_check", run_check)
    assert cli.main(["discover-tools", "--env", "local.env"]) == (0 if success else 1)
    assert received == {"env_path": "local.env", "max_turns": 24}
    assert ("PASSED" if success else "FAILED") in capsys.readouterr().out


def test_discover_configuration_failure_does_not_start_probe(monkeypatch, capsys):
    from cst_agentic.config import ConfigError

    def load_config(**kwargs):
        raise ConfigError("Required setting AGENT is missing.")

    monkeypatch.setattr(cli, "load_connectivity_config", load_config)
    assert cli.main(["discover-tools"]) == 1
    assert "Configuration error" in capsys.readouterr().err
