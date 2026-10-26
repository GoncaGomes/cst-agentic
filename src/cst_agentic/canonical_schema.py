"""Non-narrowing native-function schemas and local JSON argument validation."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote

from jsonschema import validators
from jsonschema.protocols import Validator

from .recovery import RecoveryError


def json_object(raw: str) -> dict[str, Any]:
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
    # Reject overflow such as 1e999 as well as literal NaN/Infinity.
    json.dumps(value, allow_nan=False)
    return value


_DIALECTS = {
    "https://json-schema.org/draft/2020-12/schema",
    "https://json-schema.org/draft/2019-09/schema",
    "http://json-schema.org/draft-07/schema#",
}
_ANNOTATIONS = {
    "$schema",
    "$comment",
    "$defs",
    "definitions",
    "title",
    "description",
    "default",
    "examples",
    "deprecated",
    "readOnly",
    "writeOnly",
    "format",
    "contentEncoding",
    "contentMediaType",
    "contentSchema",
}
_MAPS = {"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"}
_SINGLES = {
    "additionalProperties",
    "additionalItems",
    "contains",
    "not",
    "if",
    "then",
    "else",
    "propertyNames",
    "unevaluatedProperties",
    "unevaluatedItems",
    "contentSchema",
}


def canonical_validator(schema: dict[str, Any]) -> Validator:
    """Accept only schemas we can preserve and validate without external retrieval.

    Refuse unsupported vocabularies/reference scopes rather than silently ignoring
    assertions. Annotation/default data is not traversed as if it were a schema.
    No defaults, required fields, union branches or extra-property rules are changed.
    Provider acceptance still needs the separately bounded endpoint evidence.
    """
    json.dumps(schema, allow_nan=False)
    if schema.get("type") != "object":
        raise RecoveryError("Native function inputs require an object schema.")
    dialect = schema.get("$schema")
    if dialect is not None and dialect not in _DIALECTS:
        raise RecoveryError("Unsupported schema dialect.")
    validator = validators.validator_for(schema)
    validator.check_schema(schema)
    refs: list[str] = []
    nodes: set[int] = set()

    def visit(node: Any) -> None:
        if isinstance(node, bool):
            nodes.add(id(node))
            return
        if not isinstance(node, dict):
            raise RecoveryError("Invalid canonical subschema.")
        nodes.add(id(node))
        if node.get("$schema", dialect) != dialect:
            raise RecoveryError("Mixed schema dialects require review.")
        if set(node) - (set(validator.VALIDATORS) | _ANNOTATIONS):
            raise RecoveryError("Unsupported schema keywords require review.")
        # Dynamic/recursive scope changes require a separately reviewed adapter.
        if set(node) & {
            "$dynamicRef",
            "$recursiveRef",
            "$dynamicAnchor",
            "$recursiveAnchor",
            "$id",
        }:
            raise RecoveryError("Unsupported schema reference scope.")
        if "$ref" in node:
            ref = node["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/"):
                raise RecoveryError("Only local JSON-pointer schema references are supported.")
            refs.append(ref)
        for key, value in node.items():
            if key in _MAPS:
                for child in value.values():
                    visit(child)
            elif key == "dependencies":
                for child in value.values():
                    if isinstance(child, (dict, bool)):
                        visit(child)
            elif key in {"allOf", "anyOf", "oneOf", "prefixItems"}:
                for child in value:
                    visit(child)
            elif key == "items" and isinstance(value, list):
                for child in value:
                    visit(child)
            elif key in _SINGLES or key == "items":
                visit(value)

    visit(schema)
    for ref in refs:
        target: Any = schema
        try:
            for part in unquote(ref[2:]).split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                target = target[int(part)] if isinstance(target, list) else target[part]
        except (KeyError, IndexError, ValueError, TypeError):
            raise RecoveryError("Unresolved local schema reference.") from None
        if id(target) not in nodes:
            raise RecoveryError("Reference does not point to a canonical subschema.")
    return validator(schema)
