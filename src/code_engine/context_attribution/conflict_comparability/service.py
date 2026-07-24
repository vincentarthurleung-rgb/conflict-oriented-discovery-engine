from __future__ import annotations

from ..conflict_candidate.models import ConflictCandidate
from ..context_difference.models import ContextDifference
from .identities import conflict_comparability_identity
from .models import ConflictComparabilityAssessment


def create_pending_comparability(
    *, candidate: ConflictCandidate, difference: ContextDifference
) -> ConflictComparabilityAssessment:
    if candidate.validation_status != "validated":
        raise ValueError("conflict_candidate_not_validated")
    if difference.validation_status != "validated":
        raise ValueError("context_difference_not_validated")
    payload = {
        "schema_version": "conflict_comparability_assessment_v1",
        "candidate_id": candidate.candidate_id,
        "conflict_candidate_identity": candidate.conflict_candidate_identity,
        "context_difference_identity": difference.context_difference_identity,
        "source_difference_validation_status": "validated",
        "comparability_policy_identity": None,
        "adjudication_identity": None,
        "assessment_status": "pending_policy",
        "comparability_class": None,
        "rationale": (
            "No activated comparability policy or completed adjudication is "
            "available; legacy Provider effect fields are non-authoritative."
        ),
        "provenance": {
            "legacy_provider_effect_consumed": False,
            "pending_adjudication_consumed": False,
            "model_b_activated": False,
            "authority_validated": False,
        },
        "validator_version": "conflict_comparability_validator_v1",
        "validation_status": "unvalidated",
    }
    payload["conflict_comparability_identity"] = conflict_comparability_identity(
        payload
    )
    return ConflictComparabilityAssessment.model_validate(payload)
