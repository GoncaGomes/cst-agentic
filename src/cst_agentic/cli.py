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


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "verify-connectivity":
        return _run_verify(args.env)
    # Unreachable: the subcommand is required.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
