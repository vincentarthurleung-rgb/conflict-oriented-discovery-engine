"""Deterministic validation helpers; no provider or network dependencies."""
from __future__ import annotations

from typing import Any

from .models import FORBIDDEN_DERIVED_FIELDS, ContextFieldEvidence, reject_derived_fields


def validate_asset_boundary(payload: dict[str, Any]) -> list[str]:
    try:
        reject_derived_fields(payload)
    except ValueError as exc:
        return [str(exc)]
    return []


def validate_field_evidence(payload: ContextFieldEvidence | dict[str, Any]) -> ContextFieldEvidence:
    return payload if isinstance(payload, ContextFieldEvidence) else ContextFieldEvidence.model_validate(payload)


def dependency_boundary_forbidden_tokens() -> set[str]:
    return FORBIDDEN_DERIVED_FIELDS | {
        "deepseek_client", "provider_client", "requests", "httpx",
        "context_difference", "conflict_candidate", "comparability",
    }
