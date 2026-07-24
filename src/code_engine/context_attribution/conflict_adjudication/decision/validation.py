from __future__ import annotations

from ...claim_alignment.models import AlignedClaimGroup
from ...conflict_candidate.contradiction import ContradictionSignal
from ...conflict_candidate.models import ConflictCandidate
from ..bundle import FactorAttributionBundle
from .identities import conflict_adjudication_decision_identity
from .models import ConflictAdjudicationDecision


def validate_conflict_adjudication(
    decision: ConflictAdjudicationDecision,
    *,
    alignment: AlignedClaimGroup,
    signal: ContradictionSignal,
    candidate: ConflictCandidate,
    bundle: FactorAttributionBundle | None,
) -> list[str]:
    errors: list[str] = []
    if (
        decision.claim_alignment_identity != alignment.claim_alignment_identity
        or decision.contradiction_signal_identity
        != signal.contradiction_signal_identity
        or decision.conflict_candidate_identity
        != candidate.conflict_candidate_identity
    ):
        errors.append("adjudication_upstream_identity_mismatch")
    if bundle and (
        decision.factor_attribution_bundle_identity != bundle.bundle_identity
        or decision.comparability_assessment_bundle_identity
        != bundle.comparability_assessment_bundle_identity
        or decision.divergence_explanation_bundle_identity
        != bundle.divergence_explanation_bundle_identity
    ):
        errors.append("adjudication_attribution_bundle_identity_mismatch")
    if decision.authority_scope == "staging_only" and decision.formal_conflict_confirmed:
        errors.append("staging_authority_cannot_confirm_formal_conflict")
    if decision.conflict_adjudication_decision_identity != (
        conflict_adjudication_decision_identity(decision.model_dump())
    ):
        errors.append("conflict_adjudication_decision_identity_mismatch")
    return errors
