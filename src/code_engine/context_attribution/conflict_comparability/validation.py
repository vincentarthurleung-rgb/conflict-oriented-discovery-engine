from __future__ import annotations

from typing import Any

from ..conflict_candidate.models import ConflictCandidate
from ..context_difference.models import ContextDifference
from .identities import conflict_comparability_identity
from .models import ConflictComparabilityAssessment

CONFLICT_COMPARABILITY_VALIDATOR_VERSION = "conflict_comparability_validator_v1"


def validate_conflict_comparability(
    payload: ConflictComparabilityAssessment | dict[str, Any],
    *,
    candidate: ConflictCandidate,
    difference: ContextDifference,
) -> tuple[ConflictComparabilityAssessment, list[str]]:
    value = (
        payload
        if isinstance(payload, ConflictComparabilityAssessment)
        else ConflictComparabilityAssessment.model_validate(payload)
    )
    errors: list[str] = []
    if candidate.validation_status != "validated":
        errors.append("conflict_candidate_not_validated")
    if difference.validation_status != "validated":
        errors.append("context_difference_not_validated")
    if value.source_difference_validation_status != "validated":
        errors.append("comparability_requires_validated_difference")
    if (
        value.candidate_id != candidate.candidate_id
        or value.conflict_candidate_identity
        != candidate.conflict_candidate_identity
        or value.context_difference_identity
        != difference.context_difference_identity
    ):
        errors.append("comparability_upstream_identity_mismatch")
    if value.assessment_status == "validated":
        if value.validation_status != "validated":
            errors.append("validated_assessment_validation_status_mismatch")
        if not value.provenance.get("authority_validated"):
            errors.append("comparability_authority_not_validated")
    elif value.validation_status == "validated":
        errors.append("pending_assessment_cannot_be_validated")
    if value.conflict_comparability_identity != conflict_comparability_identity(
        value.model_dump()
    ):
        errors.append("conflict_comparability_identity_mismatch")
    return value, errors
