"""Command-line entry point for CST-Agentic.

Provides an explicit ``verify-connectivity`` command (milestone 1). Running the
check is intentional: it only starts when the subcommand is invoked, never as
an import-time side effect.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from cst_agentic.config import ConfigError, load_connectivity_config
from cst_agentic.connectivity import run_connectivity_check
from cst_agentic.controller_config import load_controller_config
from cst_agentic.controller_runtime import EXIT_WARNING, run_controller_terminal
from cst_agentic.mcp_client import McpStartupError
from cst_agentic.recovery import RecoveryError

ENV_PATH_DEFAULT = Path("./.env")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cst-agentic",
        description="Agentic control of CST Studio Suite through an MCP server.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser(
        "verify-connectivity",
        help="Verify the institutional model can reach the MCP server and call "
        "cst_connection_status with CST in disabled mode.",
        description=(
            "Start the configured MCP server with CST_CONNECT_MODE=disabled, "
            "initialize it, discover its tools, expose only "
            "cst_connection_status to the institutional model, and verify the "
            "model calls it through MCP and reports a disconnected status."
        ),
    )
    verify.add_argument(
        "--env",
        default=ENV_PATH_DEFAULT,
        metavar="PATH",
        help="Path to the .env file (default: ./.env in the working directory).",
    )
    controller = subparsers.add_parser(
        "controller",
        help="Start a separate manual-mode Controller lifecycle session (no CST launch).",
    )
    controller.add_argument(
        "--env",
        default=ENV_PATH_DEFAULT,
        metavar="PATH",
        help="Controller configuration file (default: ./.env).",
    )
    return parser


def _run_verify(env_path: str | None) -> int:
    try:
        config = load_connectivity_config(env_path=env_path)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    report = asyncio.run(run_connectivity_check(config))
    print(report.summary())
    return 0 if report.success else 1


def _controller_errors(error: BaseException) -> list[str]:
    if isinstance(error, BaseExceptionGroup):
        return [line for child in error.exceptions for line in _controller_errors(child)]
    if isinstance(error, (ConfigError, RecoveryError, McpStartupError)):
        return [str(error)]  # These application errors contain only safe categories/names.
    return ["Unexpected Controller failure; raw details withheld."]


def _run_controller(env_path: str | Path) -> int:
    try:
        config = load_controller_config(env_path=env_path)
        return asyncio.run(run_controller_terminal(config))
    except KeyboardInterrupt:
        print(EXIT_WARNING, file=sys.stderr)
        print("Controller interrupted; no orderly-exit or CST survival guarantee.", file=sys.stderr)
        return 130
    except (Exception, BaseExceptionGroup) as error:
        for line in _controller_errors(error):
            print(f"Controller failure: {line}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "verify-connectivity":
        return _run_verify(args.env)
    if args.command == "controller":
        return _run_controller(args.env)
    # Unreachable: the subcommand is required.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
