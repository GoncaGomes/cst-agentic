"""MCP stdio client wrapper for the CST server.

This module owns the MCP subprocess lifecycle: it starts the configured
executable with a sanitized environment, performs the MCP ``initialize``
handshake, discovers tools following pagination, records every ``tools/call``,
and always tears the subprocess down (bounded, and safe under cancellation).

Every request to the server is bounded by ``request_timeout_s``: each
``tools/list`` page and each ``tools/call`` must complete within it. A timeout
raises :class:`McpError`/:class:`McpCallError` with a diagnostic instead of
hanging, so a server that initializes and then stalls cannot keep the caller
alive indefinitely.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

# Safety bound so a misbehaving server cannot loop pagination forever.
_MAX_DISCOVERED_TOOLS = 10_000


class McpError(Exception):
    """Base error for MCP transport, discovery, or call failures."""


class McpStartupError(McpError):
    """The MCP subprocess could not be started or initialized in time."""


class McpCallError(McpError):
    """A tools/call request failed at the transport level."""


@dataclass
class McpToolCall:
    """A single recorded ``tools/call`` and its decoded response."""

    name: str
    arguments: dict[str, Any]
    is_error: bool
    text: str | None
    payload: dict[str, Any] | None


@dataclass
class CstMcpClient:
    """Async context manager that drives one MCP stdio session.

    Attributes populated after ``__aenter__``:
        server_name, server_version: identity reported by ``initialize``.
        instructions: optional server instructions (may be ``None``).
        calls: every ``tools/call`` issued through this client, in order.
    """

    executable: Path
    cwd: Path
    env: Mapping[str, str]
    startup_timeout_s: float
    shutdown_timeout_s: float
    request_timeout_s: float

    server_name: str | None = None
    server_version: str | None = None
    instructions: str | None = None
    calls: list[McpToolCall] = field(default_factory=list)

    _stdio_cm: Any = field(default=None, init=False, repr=False)
    _session_cm: Any = field(default=None, init=False, repr=False)
    _session: Any = field(default=None, init=False, repr=False)

    async def __aenter__(self) -> CstMcpClient:
        params = StdioServerParameters(
            command=str(self.executable),
            args=[],
            env=dict(self.env),
            cwd=str(self.cwd),
        )
        self._stdio_cm = stdio_client(params)
        try:
            read, write = await self._stdio_cm.__aenter__()
        except Exception as exc:
            raise McpStartupError(
                f"Failed to start MCP server {self.executable}: {_describe(exc)}"
            ) from exc

        self._session_cm = ClientSession(read, write)
        try:
            self._session = await self._session_cm.__aenter__()
            init = await asyncio.wait_for(
                self._session.initialize(), timeout=self.startup_timeout_s
            )
        except TimeoutError:
            await self._aclose()
            raise McpStartupError(
                f"MCP initialize timed out after {self.startup_timeout_s:g}s."
            ) from None
        except Exception as exc:
            await self._aclose()
            raise McpStartupError(f"MCP initialize failed: {_describe(exc)}") from exc

        self.server_name = init.server_info.name
        self.server_version = init.server_info.version
        self.instructions = init.instructions
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        await self._aclose()
        return False

    async def discover_tools(self) -> list[str]:
        """List every tool, following the ``nextCursor`` pagination chain.

        Returns:
            The tool names in discovery order (duplicates preserved if a
            server repeats them across pages).

        Raises:
            McpError: when the transport fails mid-discovery, or when a page
                does not complete within ``request_timeout_s``.
        """
        names: list[str] = []
        cursor: str | None = None
        while True:
            try:
                result = await asyncio.wait_for(
                    self._session.list_tools(
                        params={"cursor": cursor} if cursor is not None else None
                    ),
                    timeout=self.request_timeout_s,
                )
            except TimeoutError:
                raise McpError(
                    f"tools/list timed out after {self.request_timeout_s:g}s (cursor={cursor!r})."
                ) from None
            except Exception as exc:
                raise McpError(f"tools/list failed: {_describe(exc)}") from exc
            for tool in result.tools:
                names.append(tool.name)
                if len(names) > _MAX_DISCOVERED_TOOLS:
                    raise McpError("Aborted tools/list: too many tools returned.")
            cursor = result.next_cursor
            if cursor is None:
                return names

    async def call_tool(self, name: str, arguments: Mapping[str, Any] | None) -> McpToolCall:
        """Issue one ``tools/call`` and record the decoded result.

        Raises:
            McpCallError: when the request cannot be completed (transport
                failure, timeout, or no response within ``request_timeout_s``).
                A tool that returns a payload error does NOT raise; it is
                recorded with ``is_error=True`` so callers can distinguish
                transport failure from an unsuccessful tool result.
        """
        args = dict(arguments or {})
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, arguments=args),
                timeout=self.request_timeout_s,
            )
        except TimeoutError:
            raise McpCallError(
                f"tools/call {name!r} timed out after {self.request_timeout_s:g}s."
            ) from None
        except Exception as exc:
            raise McpCallError(f"tools/call {name!r} failed: {_describe(exc)}") from exc

        record = McpToolCall(
            name=name,
            arguments=args,
            is_error=bool(getattr(result, "is_error", False)),
            text=_first_text(result),
            payload=_decode_payload(result),
        )
        self.calls.append(record)
        return record

    async def _aclose(self) -> None:
        if self._session_cm is not None:
            with suppress(Exception):
                await asyncio.wait_for(
                    self._session_cm.__aexit__(None, None, None),
                    timeout=self.shutdown_timeout_s,
                )
            self._session_cm = None
            self._session = None
        if self._stdio_cm is not None:
            with suppress(Exception):
                await asyncio.wait_for(
                    self._stdio_cm.__aexit__(None, None, None),
                    timeout=self.shutdown_timeout_s,
                )
            self._stdio_cm = None


def _describe(exc: BaseException) -> str:
    """A one-line, credential-safe description of an error."""
    text = str(exc).strip() or exc.__class__.__name__
    return text[:300]


def _first_text(result: Any) -> str | None:
    for block in getattr(result, "content", None) or []:
        if getattr(block, "type", None) == "text":
            return getattr(block, "text", None)
    return None


def _decode_payload(result: Any) -> dict[str, Any] | None:
    text = _first_text(result)
    if text is None:
        return None
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None
