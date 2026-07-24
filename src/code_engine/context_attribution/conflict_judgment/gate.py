from __future__ import annotations

from ..conflict_candidate.models import ConflictCandidate
from ..conflict_comparability.models import ConflictComparabilityAssessment
from ..context_difference.models import ContextDifference
from ..layer_identity import layer_identity
from .identities import formal_conflict_decision_identity
from .models import FormalConflictDecision

FORMAL_GATE_POLICY_VERSION = "formal_conflict_staging_gate_policy_v1"
SCIENTIFIC_DECISION_VERSION = "formal_conflict_scientific_decision_v1"


def stage_formal_conflict_decision(
    *,
    candidate: ConflictCandidate,
    difference: ContextDifference | None,
    comparability: ConflictComparabilityAssessment | None,
) -> FormalConflictDecision:
    gate_identity = layer_identity(
        "formal_gate_policy",
        FORMAL_GATE_POLICY_VERSION,
        {
            "validated_comparability_required": True,
            "authority_scope": "staging_only",
        },
    )
    if candidate.validation_status != "validated":
        status, rationale = "candidate_only", "Candidate is not validated."
    elif candidate.context_readiness != "context_ready":
        status, rationale = (
            "blocked_context_unavailable",
            "One or both endpoint contexts are unavailable or failed.",
        )
    elif difference is None or difference.validation_status != "validated":
        status, rationale = (
            "blocked_difference_unvalidated",
            "A validated ContextDifference is required.",
        )
    elif (
        comparability is None
        or comparability.assessment_status != "validated"
        or comparability.validation_status != "validated"
    ):
        status, rationale = (
            "blocked_comparability_pending",
            "A validated, policy/adjudication-backed comparability is required.",
        )
    elif (
        comparability.context_difference_identity
        != difference.context_difference_identity
        or comparability.conflict_candidate_identity
        != candidate.conflict_candidate_identity
    ):
        status, rationale = (
            "blocked_comparability_pending",
            "Comparability upstream identities do not match.",
        )
    elif comparability.comparability_class == "non_comparable":
        status, rationale = "non_comparable", "Validated policy marks non-comparable."
    elif comparability.comparability_class == "insufficient_information":
        status, rationale = (
            "insufficient_information",
            "Validated assessment reports insufficient information.",
        )
    elif comparability.comparability_class == "conditionally_comparable":
        status, rationale = (
            "conditionally_comparable",
            "Further scientific judgment is required; staging does not confirm.",
        )
    else:
        # This architecture-only gate cannot change an existing scientific result.
        status, rationale = (
            "candidate_only",
            "Comparability alone cannot confirm a formal conflict.",
        )
    payload = {
        "schema_version": "formal_conflict_decision_v1",
        "authority_scope": "staging_only",
        "candidate_id": candidate.candidate_id,
        "conflict_candidate_identity": candidate.conflict_candidate_identity,
        "context_difference_identity": (
            difference.context_difference_identity if difference else None
        ),
        "conflict_comparability_identity": (
            comparability.conflict_comparability_identity if comparability else None
        ),
        "decision_status": status,
        "formal_conflict_confirmed": False,
        "rationale": rationale,
        "formal_gate_policy_identity": gate_identity,
        "scientific_decision_version": SCIENTIFIC_DECISION_VERSION,
        "provenance": {
            "production_authority": False,
            "raw_provider_effect_consumed": False,
            "formal_v3_modified": False,
        },
        "validator_version": "formal_conflict_judgment_validator_v1",
        "validation_status": "validated",
    }
    payload["formal_conflict_decision_identity"] = (
        formal_conflict_decision_identity(payload)
    )
    return FormalConflictDecision.model_validate(payload)
