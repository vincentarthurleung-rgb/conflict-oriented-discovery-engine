"""Deterministic immutable recovery selection."""
from __future__ import annotations

from typing import Any


RECOVERY_ORDER = (
    "existing_structured_observation", "parsed_payload", "validated_observation",
    "fulltext_v3", "evidence_projection", "authoritative_raw_response",
)


def select_explicit_source(stage_payloads: dict[str, dict[str, Any] | None], component: str):
    """Return the first explicit non-empty component; never infer from claim/context."""
    keys = {
        "factors": ("experimental_factors", "interventions"),
        "measurements": ("measurements", "measurement"),
        "results": ("observed_results", "observation"),
    }[component]
    for stage in RECOVERY_ORDER:
        payload = stage_payloads.get(stage)
        if not isinstance(payload, dict):
            continue
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list) and value:
                return stage, key, value
            if isinstance(value, dict) and value:
                return stage, key, [value]
    return None, None, []


def claim_text_recovery_allowed() -> bool:
    return False


def context_result_recovery_allowed() -> bool:
    return False

