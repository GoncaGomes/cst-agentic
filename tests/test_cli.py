"""Offline regression checks for the connectivity-only command surface."""

import pytest

from cst_agentic import cli


def test_help_lists_only_verify_connectivity(capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["--help"])
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert "{verify-connectivity}" in output
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
