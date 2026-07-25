"""Fail-closed deterministic shared-experiment context propagation."""
from __future__ import annotations

from typing import Any


def propagate(
    shared_record: dict[str, Any], *,
    scope_validated: bool,
    registry_allows: bool,
    observation_is_member: bool,
    same_document: bool,
    local_conflict: bool = False,
    scope_conflict: bool = False,
) -> dict[str, Any]:
    blockers = []
    if not scope_validated: blockers.append("scope_not_validated")
    if not registry_allows: blockers.append("registry_propagation_forbidden")
    if not observation_is_member: blockers.append("observation_not_in_scope")
    if not same_document: blockers.append("cross_document_forbidden")
    if local_conflict: blockers.append("local_value_conflict")
    if scope_conflict: blockers.append("scope_value_conflict")
    if not shared_record.get("evidence_anchor_ids"):
        blockers.append("shared_source_evidence_missing")
    if blockers:
        return {"status": "blocked_conflict" if local_conflict or scope_conflict else "blocked", "blockers": blockers}
    result = dict(shared_record)
    result.update({
        "value_origin": "deterministic_scope_inheritance",
        "propagation_validation_status": "validated",
    })
    return result
