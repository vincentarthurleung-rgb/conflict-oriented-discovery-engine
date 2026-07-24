from __future__ import annotations

from typing import Any

from .identities import conflict_candidate_identity
from .models import ConflictCandidate

CONFLICT_CANDIDATE_VALIDATOR_VERSION = "conflict_candidate_validator_v1"


def validate_conflict_candidate(
    payload: ConflictCandidate | dict[str, Any],
) -> tuple[ConflictCandidate, list[str]]:
    value = (
        payload
        if isinstance(payload, ConflictCandidate)
        else ConflictCandidate.model_validate(payload)
    )
    errors: list[str] = []
    if value.observation_a_id == value.observation_b_id:
        errors.append("candidate_endpoints_must_differ")
    if value.conflict_candidate_identity != conflict_candidate_identity(
        value.model_dump()
    ):
        errors.append("conflict_candidate_identity_mismatch")
    expected_readiness = (
        "context_ready"
        if value.context_a_status == value.context_b_status == "validated"
        else "context_unavailable"
        if value.context_a_status == value.context_b_status == "unavailable"
        else "context_partial"
    )
    if value.context_readiness != expected_readiness:
        errors.append("candidate_context_readiness_mismatch")
    return value, errors
