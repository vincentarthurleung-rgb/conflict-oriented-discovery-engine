from __future__ import annotations

from typing import Any

from ..conflict_candidate.models import ConflictCandidate
from ..observation_context.models import ObservationContext
from .identities import context_difference_identity
from .models import ContextDifference

CONTEXT_DIFFERENCE_VALIDATOR_VERSION = "context_difference_validator_v1"


def validate_context_difference(
    payload: ContextDifference | dict[str, Any],
    *,
    candidate: ConflictCandidate,
    context_a: ObservationContext,
    context_b: ObservationContext,
    known_factor_ids: set[str],
) -> tuple[ContextDifference, list[str]]:
    value = (
        payload
        if isinstance(payload, ContextDifference)
        else ContextDifference.model_validate(payload)
    )
    errors: list[str] = []
    if candidate.validation_status != "validated":
        errors.append("conflict_candidate_not_validated")
    for label, context in (("a", context_a), ("b", context_b)):
        if context.validation_status != "validated":
            errors.append(f"observation_context_{label}_not_validated")
    expected_bindings = (
        value.candidate_id == candidate.candidate_id,
        value.conflict_candidate_identity
        == candidate.conflict_candidate_identity,
        value.observation_a_id == candidate.observation_a_id == context_a.observation_id,
        value.observation_b_id == candidate.observation_b_id == context_b.observation_id,
        value.claim_a_identity
        == candidate.claim_a_identity
        == context_a.normalized_claim_identity,
        value.claim_b_identity
        == candidate.claim_b_identity
        == context_b.normalized_claim_identity,
        value.observation_context_a_identity
        == context_a.observation_context_identity,
        value.observation_context_b_identity
        == context_b.observation_context_identity,
    )
    if not all(expected_bindings):
        errors.append("context_difference_endpoint_identity_mismatch")
    anchors_a = {
        anchor for fact in context_a.facts for anchor in fact.evidence_anchor_ids
    }
    anchors_b = {
        anchor for fact in context_b.facts for anchor in fact.evidence_anchor_ids
    }
    seen: set[str] = set()
    for factor in value.factor_differences:
        if factor.factor_id in seen:
            errors.append(f"duplicate_factor:{factor.factor_id}")
        seen.add(factor.factor_id)
        if factor.factor_id not in known_factor_ids:
            errors.append(f"unsupported_factor:{factor.factor_id}")
        for anchor in factor.claim_a_anchor_ids:
            if anchor not in anchors_a:
                errors.append(f"claim_a_cross_or_unknown_anchor:{anchor}")
        for anchor in factor.claim_b_anchor_ids:
            if anchor not in anchors_b:
                errors.append(f"claim_b_cross_or_unknown_anchor:{anchor}")
    if value.context_difference_identity != context_difference_identity(
        value.model_dump()
    ):
        errors.append("context_difference_identity_mismatch")
    return value, errors
