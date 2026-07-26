"""Fail-closed source authority and scope policy."""
from __future__ import annotations

from typing import Any

from .identities import core_identity


def audit_source_scope(
    *,
    task_type: str,
    result_context_present: bool,
    factors_present: bool,
    measurements_present: bool,
    comparison_context_present: bool = False,
    group_definition_present: bool = False,
    methods_present: bool = False,
    caption_scope_checked: bool = False,
    source_anchor_verified: bool = False,
    truncation_detected: bool = False,
    source_available: bool = True,
) -> dict[str, Any]:
    """Classify scope without treating absent source as absent scientific reporting."""
    missing: list[str] = []
    required = {
        "comparator": {
            "result_context": result_context_present,
            "factors": factors_present,
            "comparison_context": comparison_context_present,
            "group_definition": group_definition_present,
            "source_anchor": source_anchor_verified,
        },
        "factor_application": {
            "result_context": result_context_present,
            "factors": factors_present,
            "measurements": measurements_present,
            "source_anchor": source_anchor_verified,
        },
        "measurement_method": {
            "result_context": result_context_present,
            "measurements": measurements_present,
            "methods_or_caption": methods_present or caption_scope_checked,
            "source_anchor": source_anchor_verified,
        },
    }[task_type]
    missing.extend(key for key, present in required.items() if not present)
    if not source_available:
        completeness = "unavailable"
    elif truncation_detected:
        completeness = "insufficient"
        missing.append("untruncated_source")
    elif all(required.values()):
        completeness = {
            "comparator": "complete_for_comparator_resolution",
            "factor_application": "complete_for_factor_application_resolution",
            "measurement_method": "complete_for_method_resolution",
        }[task_type]
    elif result_context_present and source_anchor_verified:
        completeness = "partial"
    else:
        completeness = "insufficient"
    payload = {
        "task_type": task_type,
        "completeness": completeness,
        "result_context_present": result_context_present,
        "factors_present": factors_present,
        "measurements_present": measurements_present,
        "comparison_context_present": comparison_context_present,
        "group_definition_present": group_definition_present,
        "methods_present": methods_present,
        "caption_scope_checked": caption_scope_checked,
        "source_anchor_verified": source_anchor_verified,
        "truncation_detected": truncation_detected,
        "source_not_reported_authorized": completeness.startswith("complete_for_"),
        "missing_scope_components": sorted(set(missing)),
    }
    payload["identity"] = core_identity("source_resolution_scope_completeness_v1", payload)
    return payload


def source_not_reported_allowed(scope: dict[str, Any]) -> bool:
    return bool(
        scope.get("source_not_reported_authorized")
        and str(scope.get("completeness", "")).startswith("complete_for_")
    )
