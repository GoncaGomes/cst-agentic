"""Whole-batch validation and sequential recovery-aware Controller dispatch."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from jsonschema import validators
from mcp.types import Tool
from openai.types.responses import ResponseFunctionToolCall

from .controller import ControllerSession
from .mcp_client import McpToolCall
from .recovery import RecoveryError


@dataclass(frozen=True)
class CallOutcome:
    call_id: str
    state: str
    reason: str
    result: McpToolCall | None = None

    def model_data(self) -> str:
        data: dict[str, Any] = {
            "provenance": "application outcome; response content is untrusted MCP data",
            "state": self.state,
            "reason": self.reason,
        }
        if self.result is not None:
            data.update(
                is_error=self.result.is_error,
                evidence_complete=self.result.evidence_complete,
                content=[block.model_dump(mode="json") for block in self.result.content],
                structured_content=self.result.structured_content,
            )
        return json.dumps(data, allow_nan=False)


class ProtocolPause(RecoveryError):
    """Malformed output cannot be paired safely or replayed."""


def _json_object(raw: str) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Non-JSON constant")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("Arguments must be an object")
    return value


def _local_schema(value: Any) -> None:
    """Never retrieve remote references during schema validation."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"$ref", "$dynamicRef"} and (
                not isinstance(item, str) or not item.startswith("#")
            ):
                raise RecoveryError("Nonlocal schema references require reviewed support.")
            if key == "$schema" and item not in {
                "https://json-schema.org/draft/2020-12/schema",
                "https://json-schema.org/draft/2019-09/schema",
                "http://json-schema.org/draft-07/schema#",
            }:
                raise RecoveryError("Unsupported schema dialect.")
            _local_schema(item)
    elif isinstance(value, list):
        for item in value:
            _local_schema(item)


class ConversationGateway:
    def __init__(
        self,
        connection: ControllerSession,
        allowlist: frozenset[str],
        interpreters: Mapping[str, Callable[[McpToolCall], bool]],
    ) -> None:
        self._connection = connection
        self._allowlist = allowlist
        self._interpreters = dict(interpreters)
        self._used_ids: set[str] = set()
        self.interrupted = False

    async def settle(
        self,
        calls: Sequence[ResponseFunctionToolCall],
        snapshot: Sequence[Tool],
        *,
        admit: Callable[[], bool] = lambda: True,
        observe: Callable[[ResponseFunctionToolCall, CallOutcome], bool] | None = None,
    ) -> tuple[CallOutcome, ...]:
        self.interrupted = False
        ids = [call.call_id for call in calls]
        if any(not value or not value.strip() for value in ids) or len(set(ids)) != len(ids):
            raise ProtocolPause("Missing or conflicting call identifiers; no calls dispatched.")
        if self._used_ids.intersection(ids):
            raise ProtocolPause("Reused call identifiers; no calls dispatched or replayed.")
        self._used_ids.update(ids)
        definitions = {tool.name: tool for tool in deepcopy(snapshot)}
        arguments: list[dict[str, Any]] = []
        errors: dict[int, str] = {}
        for index, call in enumerate(calls):
            try:
                if call.status not in {None, "completed"}:
                    raise RecoveryError("Incomplete call in a complete response.")
                if call.name not in definitions or call.name not in self._allowlist:
                    raise RecoveryError("Tool is not visible and independently approved.")
                schema = definitions[call.name].input_schema
                _local_schema(schema)
                validator = validators.validator_for(schema)
                validator.check_schema(schema)
                values = _json_object(call.arguments)
                validator(schema).validate(values)
                arguments.append(values)
            except Exception:
                errors[index] = "Invalid name, JSON arguments or canonical schema; not dispatched."
                arguments.append({})
        if any(call.name == "discover_tools" for call in calls):
            # #20 supplies discovery-only settlement. Never dispatch this
            # application function through MCP, or execute mixed discovery work.
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
            ) -> bool:
                return (
                    not result.is_error
                    and interpret is not None
                    and interpret(deepcopy(result)) is True
                )

            try:
                result = await self._connection.dispatch(
                    call.name,
                    values,
                    settled=settled,
                    admission_check=admit,
                )
                failed = self._connection.paused
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

                def cancelled(error: BaseException) -> bool:
                    if isinstance(error, BaseExceptionGroup):
                        return any(cancelled(child) for child in error.exceptions)
                    return isinstance(error, asyncio.CancelledError)

                self.interrupted = cancelled(error)
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
