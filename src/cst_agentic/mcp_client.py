"""MCP stdio client wrapper for the CST server.

This module owns the MCP subprocess lifecycle: it starts the configured
executable with a sanitized environment, performs the MCP ``initialize``
handshake, discovers tools following pagination, serializes every
``tools/call`` per client instance, records one :class:`McpAttempt` per
admitted invocation, and always tears the subprocess down (bounded, and safe
under cancellation).

Each ``tools/list`` page uses ``request_timeout_s``. Each ``tools/call`` uses
that default or its explicit ``timeout_s`` allowance, including queueing, the
final synchronous admission guard and SDK execution. A timeout raises
:class:`McpError`/:class:`McpCallError`
with a diagnostic instead of hanging, so a server that initializes and then
stalls cannot keep the caller alive indefinitely.

A ``tools/call`` may reach the server before a local failure is observed: a
timeout, a transport or SDK-validation error, and caller cancellation can all
follow delivery, and a missing usable response cannot prove that CST performed
no operation. Such an attempt is recorded ``uncertain`` and the client then
permanently refuses further tool dispatches, because replaying or continuing
could duplicate an operation whose effects cannot be ruled out. Constructing
a new client does not reconcile the previous one.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import math
import time
from collections.abc import Callable, Mapping
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.extension import UnexpectedClaimedResult
from mcp.client.stdio import stdio_client
from mcp.types import ContentBlock, PaginatedRequestParams, Tool
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)

# Safety bound so a misbehaving server cannot loop pagination forever.
_MAX_DISCOVERED_TOOLS = 10_000

# States of an :class:`McpAttempt` record; pending until finalized, then one
# of the three terminal outcomes.
ATTEMPT_PENDING = "pending"
ATTEMPT_NOT_DISPATCHED = "not_dispatched"
ATTEMPT_RECEIVED = "received"
ATTEMPT_UNCERTAIN = "uncertain"

# Bounded diagnostic categories carried by attempt records. These are stable
# labels only: never raw exception text, configuration values, or secrets.
DIAG_ACCEPTED = "accepted"
DIAG_QUEUED_TIMEOUT = "queued_timeout"
DIAG_QUEUED_CANCELLED = "queued_cancelled"
DIAG_BLOCKED_UNCERTAIN = "blocked_uncertain"
DIAG_NOT_READY = "not_ready"
DIAG_TIMEOUT = "timeout"
DIAG_TRANSPORT_FAILURE = "transport_failure"
DIAG_SDK_VALIDATION_FAILURE = "sdk_validation_failure"
DIAG_CANCELLED_AFTER_DISPATCH = "cancelled_after_dispatch"
DIAG_RECEIVED = "received"
DIAG_GUARD_REJECTED = "guard_rejected"
DIAG_GUARD_FAILED = "guard_failed"

# SDK failures that reject an otherwise well-formed transport response because
# its shape or structured content does not validate.
_SDK_VALIDATION_ERRORS = (PydanticValidationError, UnexpectedClaimedResult)


class McpError(Exception):
    """Base error for MCP transport, discovery, or call failures."""


class McpStartupError(McpError):
    """The MCP subprocess could not be started or initialized in time."""


class McpCallError(McpError):
    """A tools/call request failed at the transport level."""


@dataclass
class McpToolCall:
    """A received response with complete evidence and legacy convenience fields.

    ``text`` and ``payload`` still refer only to the first text block. They are
    not a complete account of effects. Client-created records retain every
    content block and structured content without truncation; ``evidence_complete``
    distinguishes these from older manually constructed records. This flag says
    nothing about evidence the server itself omitted or native success.
    """

    name: str
    arguments: dict[str, Any]
    is_error: bool
    text: str | None
    payload: dict[str, Any] | None
    content: list[ContentBlock] = field(default_factory=list)
    structured_content: dict[str, Any] | None = None
    evidence_complete: bool = False


@dataclass
class McpAttempt:
    """One admitted ``call_tool`` invocation, kept in admission order.

    The record is appended when the invocation is admitted and, for the
    handled outcomes (a returned response, or a timeout, transport/SDK
    validation failure, or cancellation), is finalized exactly once,
    synchronously, before the invocation returns or raises. Unhandled
    process-exit exceptions are not caught by the client and may leave the
    record :data:`ATTEMPT_PENDING`.

    ``arguments`` is a frozen copy taken before the first await. The
    top-level mapping and every nested mapping or sequence are detached from
    the caller, so later mutation of the caller's arguments (at any depth)
    cannot alter the admitted values or the values actually sent. JSON
    scalars are immutable and pass through as-is. Values that are not
    JSON-compatible are retained by reference. ``started_monotonic`` and
    ``ended_monotonic`` are ``time.monotonic()`` readings.

    ``state`` is :data:`ATTEMPT_PENDING` until finalized, then a terminal
    outcome: ``not_dispatched`` (no request reached the SDK), ``received``
    (a response was returned), or ``uncertain`` (the request may have reached
    the server and no usable response was observed). A ``received`` outcome
    is not proof that CST executed the operation successfully or that partial
    effects are absent. ``diagnostic`` is a stable bounded category, never a
    raw exception message.
    """

    name: str
    arguments: dict[str, Any]
    started_monotonic: float
    state: str = ATTEMPT_PENDING
    diagnostic: str = DIAG_ACCEPTED
    dispatched: bool = False
    ended_monotonic: float | None = None
    result: McpToolCall | None = None

    def finalize(
        self,
        state: str,
        diagnostic: str,
        now: float,
        result: McpToolCall | None = None,
    ) -> None:
        """Move the record to a terminal outcome.

        The client calls this exactly once for every handled outcome (a
        returned response, or a timeout, transport/SDK-validation failure,
        or cancellation). Unhandled process-exit exceptions bypass it and
        leave the record pending.
        """
        self.state = state
        self.diagnostic = diagnostic
        self.ended_monotonic = now
        if result is not None:
            self.result = result


@dataclass
class CstMcpClient:
    """Async context manager that drives one MCP stdio session.

    Attributes populated after ``__aenter__``:
        server_name, server_version: identity reported by ``initialize``.
        instructions: optional server instructions (may be ``None``).
        calls: every ``tools/call`` that returned a response, in order.
        attempts: every admitted ``call_tool`` invocation, in admission
            order, each finalized to a terminal outcome for handled
            completions (see :class:`McpAttempt`).

    ``tools/call`` dispatch is serialized: at most one call is active per
    client, and concurrent callers queue until their individual
    allowance expires (measured from each invocation's entry,
    covering queueing plus SDK execution) expires. Once any attempt ends
    uncertain, every later dispatch on this instance is blocked before it
    reaches the SDK.

    Raises:
        ValueError: from construction (and before every dispatch) when
            ``request_timeout_s`` is not a finite positive number.
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
    attempts: list[McpAttempt] = field(default_factory=list)

    _stdio_cm: Any = field(default=None, init=False, repr=False)
    _session_cm: Any = field(default=None, init=False, repr=False)
    _session: Any = field(default=None, init=False, repr=False)
    _call_lock: Any = field(default_factory=asyncio.Lock, init=False, repr=False)
    _uncertain: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        # A non-finite or non-positive bound cannot bound anything; reject it
        # before any dispatch can occur.
        self._check_request_timeout()

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
        return [tool.name for tool in await self.discover_tool_definitions()]

    async def discover_tool_definitions(self) -> list[Tool]:
        """Return detached canonical definitions, following every catalogue page.

        Preserve discovery order, duplicates, schemas and metadata without any
        strict-schema conversion. Each page uses the existing request allowance.
        This is catalogue access, not tool activation or execution permission.
        """
        tools: list[Tool] = []
        cursor: str | None = None
        while True:
            try:
                result = await asyncio.wait_for(
                    self._session.list_tools(
                        params=PaginatedRequestParams(cursor=cursor) if cursor is not None else None
                    ),
                    timeout=self.request_timeout_s,
                )
            except TimeoutError:
                raise McpError("tools/list timed out within the request budget.") from None
            except Exception:
                raise McpError("tools/list failed: transport_failure") from None
            for tool in result.tools:
                tools.append(tool.model_copy(deep=True))
                if len(tools) > _MAX_DISCOVERED_TOOLS:
                    raise McpError("Aborted tools/list: too many tools returned.")
            cursor = result.next_cursor
            if cursor is None:
                return tools

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any] | None,
        *,
        timeout_s: float | None = None,
        dispatch_guard: Callable[[], bool] | None = None,
    ) -> McpToolCall:
        """Issue one serialized ``tools/call`` and record the attempt.

        At most one ``tools/call`` is active per client. Concurrent callers
        queue on an instance lock. ``timeout_s`` overrides ``request_timeout_s``
        for this invocation only. Its deadline starts at entry and covers
        queueing, the guard and SDK execution. The caller, not the model or this
        transport, owns operation-specific maximum-allowance policy. Every
        admitted invocation appends an :class:`McpAttempt` to ``attempts``
        before any SDK work; only a returned response is appended to
        ``calls``, preserving its response-only meaning. The recorded and
        dispatched arguments are a frozen copy taken before the first await,
        so later mutation of the caller's mapping (at any depth) cannot alter
        them.

        ``dispatch_guard`` is an optional synchronous, no-argument callback
        supplied by the execution gateway. It rechecks current prerequisites
        (and may persist required recovery metadata) after acquiring the lock,
        only on a healthy, ready client with budget remaining. Only literal
        ``True`` admits dispatch. False, non-boolean/async results and exceptions
        fail closed as not dispatched. No await occurs between the decision
        and the dispatch marker. Keep the callback short and nonblocking; the
        client checks its elapsed time but cannot preempt synchronous code.

        Raises:
            ValueError: when the selected allowance is not a finite positive
                number (booleans excluded). No attempt is recorded.
            McpCallError: when the request cannot be completed (transport
                failure, timeout, or no response within the allowance), when
                the final guard refuses, or when no active session exists. In the session case the
                attempt is recorded ``not_ready`` and the client is not
                poisoned, so later calls with a live session still work.
                A tool that returns a payload error does NOT raise; it is
                recorded with ``is_error=True`` so callers can distinguish
                transport failure from an unsuccessful tool result.

        After SDK entry, a timeout, a transport or SDK-validation failure,
        and caller cancellation all leave the outcome uncertain (the request
        may already have reached the server): the attempt is recorded
        ``uncertain`` and every later dispatch on this instance is blocked
        before it reaches the SDK. Caller cancellation always propagates.
        """
        allowance = self.request_timeout_s if timeout_s is None else timeout_s
        _validate_timeout(allowance)
        started = time.monotonic()
        deadline = started + allowance
        attempt = McpAttempt(
            name=name,
            arguments=_freeze_arguments(arguments),
            started_monotonic=started,
        )
        self.attempts.append(attempt)
        lock_acquired = False
        try:
            try:
                lock_acquired = await self._acquire_call_lock(deadline)
            except asyncio.CancelledError:
                attempt.finalize(ATTEMPT_NOT_DISPATCHED, DIAG_QUEUED_CANCELLED, time.monotonic())
                raise
            if not lock_acquired:
                attempt.finalize(ATTEMPT_NOT_DISPATCHED, DIAG_QUEUED_TIMEOUT, time.monotonic())
                raise McpCallError(
                    f"tools/call {name!r} was not dispatched: the request budget "
                    "expired before the call could start."
                ) from None

            if self._uncertain:
                attempt.finalize(ATTEMPT_NOT_DISPATCHED, DIAG_BLOCKED_UNCERTAIN, time.monotonic())
                raise McpCallError(
                    f"tools/call {name!r} was not dispatched: an earlier attempt on "
                    "this client ended uncertain, so further dispatches are blocked."
                ) from None

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                # Queueing consumed the whole budget; do not enter the SDK.
                attempt.finalize(ATTEMPT_NOT_DISPATCHED, DIAG_QUEUED_TIMEOUT, time.monotonic())
                raise McpCallError(
                    f"tools/call {name!r} was not dispatched: the request budget "
                    "expired before the call could start."
                ) from None

            if self._session is None:
                # No active session: the SDK could not be entered, so the
                # outcome is not uncertain and the client is not poisoned.
                attempt.finalize(ATTEMPT_NOT_DISPATCHED, DIAG_NOT_READY, time.monotonic())
                raise McpCallError(
                    f"tools/call {name!r} was not dispatched: no active MCP session."
                ) from None

            if dispatch_guard is not None:
                try:
                    allowed = dispatch_guard()
                    # A mistaken async guard must never be treated as truthy
                    # approval. Close bare coroutines without running them.
                    if inspect.iscoroutine(allowed):
                        allowed.close()
                    diagnostic = DIAG_GUARD_REJECTED if allowed is False else DIAG_GUARD_FAILED
                except asyncio.CancelledError:
                    attempt.finalize(
                        ATTEMPT_NOT_DISPATCHED, DIAG_QUEUED_CANCELLED, time.monotonic()
                    )
                    raise
                except Exception:
                    allowed = False
                    diagnostic = DIAG_GUARD_FAILED
                if allowed is not True:
                    attempt.finalize(ATTEMPT_NOT_DISPATCHED, diagnostic, time.monotonic())
                    raise McpCallError(
                        f"tools/call {name!r} was not dispatched: final dispatch guard refused."
                    ) from None

            # The guard may consume synchronous time (e.g. persisting a marker).
            # No await is allowed between its decision and the dispatch marker.
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                attempt.finalize(ATTEMPT_NOT_DISPATCHED, DIAG_QUEUED_TIMEOUT, time.monotonic())
                raise McpCallError(
                    f"tools/call {name!r} was not dispatched: the request budget "
                    "expired before the call could start."
                ) from None
            attempt.dispatched = True
            try:
                result = await asyncio.wait_for(
                    self._session.call_tool(name, arguments=attempt.arguments),
                    timeout=remaining,
                )
            except asyncio.CancelledError:
                self._uncertain = True
                attempt.finalize(ATTEMPT_UNCERTAIN, DIAG_CANCELLED_AFTER_DISPATCH, time.monotonic())
                raise
            except TimeoutError:
                self._uncertain = True
                attempt.finalize(ATTEMPT_UNCERTAIN, DIAG_TIMEOUT, time.monotonic())
                # Bounded message: identifies the timeout without echoing the
                # configured bound.
                raise McpCallError(
                    f"tools/call {name!r} timed out: no response within the request budget."
                ) from None
            except Exception as exc:
                self._uncertain = True
                category = _diagnose_sdk_failure(exc)
                attempt.finalize(ATTEMPT_UNCERTAIN, category, time.monotonic())
                # Only the bounded category is surfaced; the original
                # exception (which may carry sensitive content) is neither
                # described nor chained.
                raise McpCallError(f"tools/call {name!r} failed: {category}") from None

            record = McpToolCall(
                name=name,
                arguments=attempt.arguments,
                is_error=bool(getattr(result, "is_error", False)),
                text=_first_text(result),
                payload=_decode_payload(result),
                content=deepcopy(result.content),
                structured_content=deepcopy(result.structured_content),
                evidence_complete=True,
            )
            attempt.finalize(ATTEMPT_RECEIVED, DIAG_RECEIVED, time.monotonic(), result=record)
            self.calls.append(record)
            return record
        finally:
            if lock_acquired:
                self._call_lock.release()

    async def _acquire_call_lock(self, deadline: float) -> bool:
        """Acquire the per-client dispatch lock within the shared deadline.

        Returns ``False`` when the remaining budget is already exhausted, so
        the caller records a not-dispatched attempt instead of entering the
        SDK. Propagates ``asyncio.CancelledError`` when the caller is
        cancelled while queued.
        """
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        try:
            await asyncio.wait_for(self._call_lock.acquire(), timeout=remaining)
        except TimeoutError:
            return False
        return True

    def _check_request_timeout(self) -> None:
        """Reject a request bound that cannot bound a request.

        Raises:
            ValueError: when ``request_timeout_s`` is not a finite positive
                number. The message never echoes the configured value.
        """
        _validate_timeout(self.request_timeout_s)

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


def _validate_timeout(bound: float) -> None:
    if (
        isinstance(bound, bool)
        or not isinstance(bound, (int, float))
        or not math.isfinite(bound)
        or bound <= 0
    ):
        raise ValueError("The request allowance must be a finite positive number.")


def _freeze_arguments(arguments: Mapping[str, Any] | None) -> dict[str, Any]:
    """Detach an admitted arguments mapping before the first await.

    The top-level mapping and every nested mapping or sequence are copied, so
    later caller mutation of the arguments (at any depth) cannot alter the
    admitted values or the values actually sent to the server. JSON scalars
    are immutable and pass through as-is. Values that are not
    JSON-compatible are retained by reference.
    """
    return _freeze_value(dict(arguments or {}))


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _freeze_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_freeze_value(item) for item in value]
    return value


def _diagnose_sdk_failure(exc: BaseException) -> str:
    """Map a post-dispatch SDK failure to a stable bounded diagnostic.

    Response-shape or structured-content validation failures are reported as
    ``sdk_validation_failure``; everything else (transport, protocol, or
    server-reported errors) is ``transport_failure``. The category never
    includes the exception text.
    """
    if isinstance(exc, _SDK_VALIDATION_ERRORS):
        return DIAG_SDK_VALIDATION_FAILURE
    return DIAG_TRANSPORT_FAILURE


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
