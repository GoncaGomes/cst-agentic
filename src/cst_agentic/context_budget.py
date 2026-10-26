"""Reproducible logical-request accounting, never model-name capacity inference.

Byte accounting is an estimate, not a tokenizer compatibility claim. A reviewed
endpoint validation record must establish its safe use (including headroom) for
the exact adapter/model before production admission.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .conversation import ModelRequest

from .canonical_schema import json_object

ACCOUNTING_METHOD = "logical-json-utf8-v1"


def adapter_identity() -> str:
    return (
        f"OpenAIChatCompletionsModel/openai-agents={version('openai-agents')};"
        f"openai={version('openai')};{ACCOUNTING_METHOD}"
    )


def json_bytes(value: Any) -> int:
    return len(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    )


@dataclass(frozen=True)
class ContextAccounting:
    sections: dict[str, int]
    input_capacity: int
    headroom: int

    @property
    def fits(self) -> bool:
        return sum(self.sections.values()) + self.headroom <= self.input_capacity

    def diagnostic(self) -> str:
        return json.dumps(
            {
                "method": ACCOUNTING_METHOD,
                "sections": self.sections,
                "estimated_input_tokens": sum(self.sections.values()),
                "input_capacity": self.input_capacity,
                "headroom": self.headroom,
            },
            sort_keys=True,
        )


@dataclass(frozen=True)
class ContextBudget:
    input_capacity: int
    headroom: int
    validation_reference: str | None = None
    endpoint: str | None = None
    model: str | None = None
    adapter: str | None = None

    def __post_init__(self) -> None:
        if (
            type(self.input_capacity) is not int
            or type(self.headroom) is not int
            or not 0 < self.headroom < self.input_capacity
        ):
            raise ValueError("Context capacity and explicit headroom must be positive integers.")

    @property
    def blocker(self) -> str | None:
        if (
            not all(
                isinstance(value, str) and value.strip()
                for value in (self.validation_reference, self.endpoint, self.model, self.adapter)
            )
            or self.adapter != adapter_identity()
        ):
            return "Context capacity is not validated; no model request sent."
        return None

    def account(self, request: ModelRequest) -> ContextAccounting:
        """Account for the complete logical request, including structured output.

        Every UTF-8 byte is charged as one estimated input token. Actual wire
        framing/tokenizer differences must be covered by validated headroom.
        This method makes no universal byte/token or endpoint-capacity claim.
        """
        sections = {
            "instructions": json_bytes(request.instructions),
            "schemas": json_bytes(
                [
                    {
                        "type": "function",
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": t.input_schema,
                        "strict": False,
                    }
                    for t in request.tools
                ]
            ),
            "input": json_bytes(request.input),
            "response_format": json_bytes(
                request.output_schema.json_schema() if request.output_schema is not None else None
            ),
            "request_options": json_bytes(
                {
                    "parallel_tool_calls": False,
                    "handoffs": [],
                    "previous_response_id": None,
                    "conversation_id": None,
                    "prompt": None,
                }
            ),
        }
        return ContextAccounting(sections, self.input_capacity, self.headroom)

    def matches(self, endpoint: str, model: str) -> bool:
        return self.blocker is None and self.endpoint == endpoint and self.model == model


def load_context_budget(path: Path, *, endpoint: str, model: str) -> ContextBudget:
    """Load an operator-reviewed validation attestation, not an automatic probe.

    The record is configuration, not proof produced by this application. Never
    include its contents or a raw parsing/filesystem exception in diagnostics.
    """
    try:
        with path.open("rb") as source:
            raw = source.read(65_537)
        if len(raw) > 65_536:
            raise ValueError
        data = json_object(raw.decode("utf-8"))
        if data.pop("validated") is not True or data.pop("method") != ACCOUNTING_METHOD:
            raise ValueError
        budget = ContextBudget(**data)
        if not budget.matches(endpoint, model):
            raise ValueError
        return budget
    except Exception:
        raise ValueError("Controller context validation record is invalid or mismatched.") from None
