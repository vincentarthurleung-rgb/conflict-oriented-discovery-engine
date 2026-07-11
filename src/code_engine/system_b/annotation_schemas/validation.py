"""Server-side annotation payload validation."""
from __future__ import annotations

from typing import Any

from .registry import AnnotationSchema


class SchemaValidationError(ValueError):
    def __init__(self, message: str, *, field_errors: dict[str, str] | None = None):
        super().__init__(message)
        self.field_errors = field_errors or {}


def _visible(field: dict, values: dict[str, Any]) -> bool:
    rule = field.get("visible_when")
    if not rule:
        return True
    source = rule.get("field")
    expected = rule.get("equals")
    if "in" in rule:
        return values.get(source) in set(rule.get("in") or [])
    return values.get(source) == expected


def _validate_value(field: dict, value: Any) -> str | None:
    ftype = field.get("type")
    allowed = field.get("allowed_values")
    if value in (None, ""):
        return None
    if ftype in {"single_choice", "boolean", "likert_1_5"}:
        if allowed and value not in allowed:
            return "value_not_allowed"
    if ftype in {"multi_choice", "ranked_list", "context_slot_set", "entity_reference"}:
        if not isinstance(value, list):
            return "expected_list"
        if allowed:
            extra = [x for x in value if x not in allowed]
            if extra:
                return "value_not_allowed"
    if ftype == "boolean" and not isinstance(value, bool):
        return "expected_boolean"
    if ftype == "integer" and not isinstance(value, int):
        return "expected_integer"
    if ftype == "number" and not isinstance(value, (int, float)):
        return "expected_number"
    if ftype == "likert_1_5" and value not in {1, 2, 3, 4, 5}:
        return "expected_1_to_5"
    return None


def validate_annotation_payload(schema: AnnotationSchema, values: dict[str, Any], *, allow_draft: bool = False) -> dict[str, Any]:
    fields = schema.definition.get("fields", [])
    field_ids = {field["field_id"] for field in fields}
    errors: dict[str, str] = {}
    unknown = sorted(set(values) - field_ids)
    if unknown:
        raise SchemaValidationError("annotation_schema_unknown_fields", field_errors={key: "unknown_field" for key in unknown})
    normalized: dict[str, Any] = {}
    for field in fields:
        field_id = field["field_id"]
        if not _visible(field, values):
            continue
        value = values.get(field_id, field.get("default"))
        if field.get("required") and not allow_draft and value in (None, "", []):
            errors[field_id] = "required"
            continue
        problem = _validate_value(field, value)
        if problem:
            errors[field_id] = problem
            continue
        if value not in (None, ""):
            normalized[field_id] = value
    if errors:
        raise SchemaValidationError("annotation_schema_validation_failed", field_errors=errors)
    return normalized
