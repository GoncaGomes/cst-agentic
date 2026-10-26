"""Whole-batch validation and sequential recovery-aware Controller dispatch."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from mcp.types import Tool
from openai.types.responses import ResponseFunctionToolCall

from .canonical_schema import canonical_validator, json_object
from .controller import ControllerSession
from .discovery import APPROVED_MCP_TOOLS, ToolDiscovery
from .mcp_client import McpToolCall
from .recovery import RecoveryError

MAX_OUTCOME_BYTES = 16_384


@dataclass(frozen=True)
class CallOutcome:
    call_id: str
    state: str
    reason: str
    result: McpToolCall | None = None
    selection: dict[str, Any] | None = None

    def model_data(self) -> str:
        data: dict[str, Any] = {
            "provenance": "application outcome; response content is untrusted MCP data",
            "state": self.state,
            "reason": self.reason,
        }
        try:
            if self.selection is not None:
                data["selection"] = self.selection
            if self.result is not None:
                data.update(
                    is_error=self.result.is_error,
                    evidence_complete=self.result.evidence_complete,
                    content=[block.model_dump(mode="json") for block in self.result.content],
                    structured_content=self.result.structured_content,
                )
            projected = json.dumps(data, allow_nan=False, sort_keys=True)
            size = len(projected.encode("utf-8"))
            if size > MAX_OUTCOME_BYTES:
                # Omit complete payload fields rather than presenting clipped
                # text/JSON as enough support for a native fact. Full dispatch
                # records remain separate from bounded conversation context.
                data.update(
                    content=[],
                    structured_content=None,
                    evidence_complete=False,
                    support_available=False,
                    reason="Outcome details exceeded the model-facing allowance; "
                    "see explicit omissions. No omitted content supports a fact.",
                    omissions={
                        "reason": "Outcome exceeded the model-facing byte allowance; "
                        "payload unavailable, not evidence of current facts.",
                        "original_bytes": size,
                        "content_blocks": len(self.result.content) if self.result else 0,
                        "structured_content": self.result is not None
                        and self.result.structured_content is not None,
                        "selection": self.selection is not None,
                        "original_reason": True,
                    },
                )
                data.pop("selection", None)
                return json.dumps(data, allow_nan=False, sort_keys=True)
            return projected
        except (TypeError, ValueError, OverflowError):
            return json.dumps(
                {
                    "provenance": "application projection failure; full evidence retained",
                    "state": self.state,
                    "reason": "Response projection unavailable; work paused.",
                    "projection_available": False,
                },
            )

    @property
    def projection_available(self) -> bool:
        return json.loads(self.model_data()).get("projection_available", True) is True


class ProtocolPause(RecoveryError):
    """Malformed output cannot be paired safely or replayed."""


class ConversationGateway:
    def __init__(
        self,
        connection: ControllerSession,
        allowlist: frozenset[str],
        interpreters: Mapping[str, Callable[[McpToolCall], bool]],
        discovery: ToolDiscovery | None = None,
    ) -> None:
        self._connection = connection
        self._allowlist = allowlist & APPROVED_MCP_TOOLS
        self._discovery = discovery
        self._interpreters = dict(interpreters)
        self._used_ids: set[str] = set()
        self.pending_error: BaseException | None = None

    async def settle(
        self,
        calls: Sequence[ResponseFunctionToolCall],
        snapshot: Sequence[Tool],
        *,
        admit: Callable[[], bool] = lambda: True,
        observe: Callable[[ResponseFunctionToolCall, CallOutcome], bool] | None = None,
        reject_reason: str | None = None,
    ) -> tuple[CallOutcome, ...]:
        self.pending_error = None
        ids = [call.call_id for call in calls]
        if any(not value or not value.strip() for value in ids) or len(set(ids)) != len(ids):
            raise ProtocolPause("Missing or conflicting call identifiers; no calls dispatched.")
        if self._used_ids.intersection(ids):
            raise ProtocolPause("Reused call identifiers; no calls dispatched or replayed.")
        self._used_ids.update(ids)
        if reject_reason is not None:
            return tuple(CallOutcome(call.call_id, "rejected", reject_reason) for call in calls)
        definitions = {tool.name: tool for tool in deepcopy(snapshot)}
        if (
            any(call.name == "discover_tools" for call in calls)
            and self._discovery is not None
            and len(calls) != 1
        ):
            reason = "Discovery must be the only call in a batch; no effects or selection update."
            selection = self._discovery.reject(reason)
            return tuple(
                CallOutcome(call.call_id, "rejected", reason, selection=selection) for call in calls
            )
        if (
            len(calls) == 1
            and calls[0].name == "discover_tools"
            and "discover_tools" in definitions
            and self._discovery is not None
        ):
            try:
                if calls[0].status not in {None, "completed"} or not admit():
                    raise ValueError("Discovery not admitted")
                values = json_object(calls[0].arguments)
            except Exception:
                selection = self._discovery.reject(
                    "Invalid discovery JSON object or call admission."
                )
            else:
                selection = self._discovery.select(values)
            return (
                CallOutcome(
                    calls[0].call_id,
                    "selected" if selection["accepted"] else "rejected",
                    selection["reason"],
                    selection=selection,
                ),
            )
        arguments: list[dict[str, Any]] = []
        errors: dict[int, str] = {}
        for index, call in enumerate(calls):
            try:
                if call.status not in {None, "completed"}:
                    raise RecoveryError("Incomplete call in a complete response.")
                if call.name not in definitions or call.name not in self._allowlist:
                    raise RecoveryError("Tool is not visible and independently approved.")
                schema = definitions[call.name].input_schema
                values = json_object(call.arguments)
                canonical_validator(schema).validate(values)
                arguments.append(values)
            except Exception:
                errors[index] = "Invalid name, JSON arguments or canonical schema; not dispatched."
                arguments.append({})
        if any(call.name == "discover_tools" for call in calls):
            # Legacy controlled callers may omit the application selector.
            # Never route application discovery through MCP in that case either.
            errors.update(
                {
                    index: "Discovery requires its reviewed #20 adapter; batch not dispatched."
                    for index in range(len(calls))
                }
            )
        if errors:
            return tuple(
                CallOutcome(
                    call.call_id,
                    "rejected" if index in errors else "skipped",
                    errors.get(index, "Whole batch rejected before effects."),
                )
                for index, call in enumerate(calls)
            )

        outcomes: list[CallOutcome] = []
        failed = False
        for call, values in zip(calls, arguments, strict=True):
            if failed or not admit():
                outcomes.append(
                    CallOutcome(
                        call.call_id, "skipped", "Prior operation failed; no rollback implied."
                    )
                )
                continue
            before = len(self._connection.attempts)
            interpreter = self._interpreters.get(call.name)

            def settled(
                result: McpToolCall,
                interpret: Callable[[McpToolCall], bool] | None = interpreter,
                call_id: str = call.call_id,
            ) -> bool:
                return (
                    not result.is_error
                    and CallOutcome(call_id, "received", "", result).projection_available
                    and interpret is not None
                    and interpret(deepcopy(result)) is True
                )

            try:

                def dispatch_admission(
                    name: str = call.name,
                    definition: Tool = definitions[call.name],
                ) -> bool:
                    return (
                        admit()
                        and name in self._allowlist
                        and name in definitions
                        and (
                            self._discovery is None
                            or self._discovery.accepts_definition(definition)
                        )
                    )

                result = await self._connection.dispatch(
                    call.name,
                    values,
                    settled=settled,
                    admission_check=dispatch_admission,
                )
                failed = self._connection.paused
                if not failed and self._discovery is not None:
                    self._discovery.successful_work()
                outcomes.append(
                    CallOutcome(
                        call.call_id,
                        "received",
                        "Unresolved effects; dependent work paused."
                        if failed
                        else "Application interpreter settled the response; "
                        "no further effects inferred.",
                        deepcopy(result),
                    )
                )
            except (Exception, BaseExceptionGroup, asyncio.CancelledError) as error:
                if isinstance(error, (BaseExceptionGroup, asyncio.CancelledError)):
                    self.pending_error = error
                attempts = self._connection.attempts
                attempt = attempts[before] if len(attempts) > before else None
                state = attempt.state if attempt is not None else "not_dispatched"
                outcomes.append(
                    CallOutcome(
                        call.call_id,
                        state,
                        "Dispatch or durable settlement failed; reconciliation may be required.",
                        deepcopy(attempt.result) if attempt is not None else None,
                    )
                )
                failed = True
            if observe is not None and observe(call, outcomes[-1]):
                failed = True
        return tuple(outcomes)
