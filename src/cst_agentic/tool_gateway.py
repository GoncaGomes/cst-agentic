"""Model-facing tools for the connectivity and discovery checks.

Connectivity exposes only ``cst_connection_status`` and gates MCP dispatch
with an allowlist. Discovery exposes only a local catalogue lookup with no
MCP dispatch route. Prompt instructions alone are not an execution control.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from agents import FunctionTool, function_tool

from .mcp_client import CstMcpClient, McpToolCall
from .tool_groups import GROUP_CATALOGUE, ToolGroups, group_description

#: The only MCP tool this check is allowed to execute.
ALLOWED_TOOLS: frozenset[str] = frozenset({"cst_connection_status"})


class ToolNotAllowedError(Exception):
    """Raised when a tool outside the allowlist is dispatched."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Tool {name!r} is not in the allowlist and was not dispatched.")
        self.name = name


class ToolGateway:
    """Routes tool dispatches to the MCP client, enforcing the allowlist.

    A name that is not in ``allowlist`` raises :class:`ToolNotAllowedError`
    before any MCP request is made.
    """

    def __init__(self, mcp: CstMcpClient, allowlist: frozenset[str] = ALLOWED_TOOLS) -> None:
        self._mcp = mcp
        self._allowlist = allowlist

    @property
    def allowlist(self) -> frozenset[str]:
        return self._allowlist

    def is_allowed(self, name: str) -> bool:
        return name in self._allowlist

    async def dispatch(self, name: str, arguments: Mapping[str, Any] | None) -> McpToolCall:
        if not self.is_allowed(name):
            raise ToolNotAllowedError(name)
        return await self._mcp.call_tool(name, arguments)


def build_status_tool(gateway: ToolGateway) -> FunctionTool:
    """Build the single function tool exposed to the model.

    The tool has an empty argument object (matching the server's schema) and
    proxies the call through :meth:`ToolGateway.dispatch`, so it is subject to
    the allowlist gate and is recorded by the MCP client.
    """

    # ``failure_error_function=None`` disables the SDK default of returning a
    # generic error message to the model: any tool failure (for example an MCP
    # timeout or transport error) must propagate out of the run so the
    # connectivity check fails with a diagnostic instead of letting the model
    # continue on a fabricated or missing result.
    @function_tool(failure_error_function=None)
    async def cst_connection_status() -> str:
        """Get the current CST Studio connection status.

        Returns a JSON object describing the connection mode (connected or
        offline), whether a project is open, the CST version, and the work
        directory. Takes no arguments.
        """
        call = await gateway.dispatch("cst_connection_status", {})
        if call.text is None:
            return json.dumps({"status": "error", "message": "empty tool response"})
        return call.text

    return cst_connection_status


def build_discovery_tool(group: ToolGroups) -> FunctionTool:
    """Build a discovery-only tool with no MCP execution route."""

    @function_tool(failure_error_function=None)
    async def discover_tools(groups: list[str]) -> str:
        """Look up MCP tool definitions for the selected capability groups."""
        return json.dumps(group.discover(groups))

    discover_tools.description = group_description()
    discover_tools.params_json_schema["properties"]["groups"]["items"]["enum"] = list(
        GROUP_CATALOGUE
    )
    return discover_tools


# Retain the factory spelling requested for the one-call discovery test.
build_discovery_too = build_discovery_tool
