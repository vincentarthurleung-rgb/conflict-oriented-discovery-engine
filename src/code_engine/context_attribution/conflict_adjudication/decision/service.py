from __future__ import annotations

from ...claim_alignment.models import AlignedClaimGroup
from ...conflict_candidate.contradiction import ContradictionSignal
from ...conflict_candidate.models import ConflictCandidate
from ...conflict_candidate.qualification.models import ConflictCandidateQualificationV1
from ...context_difference.migration import ContextDifferenceMigrationBinding
from ...context_difference.models import ContextDifference
from ...layer_identity import layer_identity
from ..bundle import FactorAttributionBundle
from ..comparability.models import FactorComparabilityAssessment
from ..divergence_explanation.models import FactorDivergenceExplanation
from .identities import conflict_adjudication_decision_identity
from .models import ConflictAdjudicationDecision


def adjudicate_pair_staging(
    *,
    alignment: AlignedClaimGroup,
    signal: ContradictionSignal,
    candidate: ConflictCandidate,
    difference: ContextDifference | None,
    difference_binding: ContextDifferenceMigrationBinding | None,
    bundle: FactorAttributionBundle | None,
    comparability: list[FactorComparabilityAssessment],
    explanations: list[FactorDivergenceExplanation],
    qualification: ConflictCandidateQualificationV1 | None = None,
) -> ConflictAdjudicationDecision:
    gate_identity = layer_identity(
        "conflict_adjudication_gate_policy",
        "conflict_adjudication_staging_gate_policy_v1",
        {
            "alignment_required": True,
            "contradiction_required": True,
            "both_attribution_branches_required": True,
            "scientific_aggregation_authorized": False,
            "authority_scope": "staging_only",
        },
    )
    if alignment.validation_status != "validated" or alignment.alignment_status != "aligned":
        status, rationale = (
            "blocked_alignment_unvalidated",
            "The proposition alignment is not fully aligned and validated.",
        )
    elif signal.validation_status != "validated" or signal.signal_status != "validated":
        status, rationale = (
            "blocked_contradiction_unvalidated",
            "A validated contradiction signal is required.",
        )
    elif qualification is not None and qualification.qualification_status != "qualified":
        status, rationale = (
            "blocked_candidate_unqualified",
            "Candidate Qualification does not grant future-standard L4 authority.",
        )
    elif candidate.validation_status != "validated":
        status, rationale = "candidate_only", "Candidate is not validated."
    elif candidate.context_readiness != "context_ready":
        status, rationale = (
            "blocked_context_unavailable",
            "One or both endpoint contexts are unavailable or failed.",
        )
    elif (
        difference is None
        or difference.validation_status != "validated"
        or difference_binding is None
        or difference_binding.validation_status != "validated"
    ):
        status, rationale = (
            "blocked_difference_unvalidated",
            "Validated difference and alignment/signal binding are required.",
        )
    elif bundle is None or not (
        bundle.all_comparability_assessed and bundle.all_explanations_assessed
    ):
        status, rationale = (
            "blocked_attribution_pending",
            "Comparability and divergence-explanation attribution must both complete.",
        )
    elif bundle.insufficient_factor_ids:
        status, rationale = (
            "insufficient_information",
            "At least one factor attribution reports insufficient information.",
        )
    elif any(
        item.comparability_severity == "blocking" for item in comparability
    ):
        status, rationale = (
            "non_comparable",
            "Validated comparability attribution contains a blocking factor.",
        )
    elif any(
        item.explanatory_effect == "sufficiently_explanatory"
        for item in explanations
    ):
        status, rationale = (
            "context_explained_divergence",
            "Validated explanation attribution sufficiently explains divergence.",
        )
    elif any(
        item.explanatory_effect == "potentially_explanatory"
        for item in explanations
    ):
        status, rationale = (
            "conditionally_comparable_disagreement",
            "Potential explanation remains without an approved aggregate rule.",
        )
    else:
        status, rationale = (
            "unresolved_disagreement",
            "Complete attribution does not itself authorize formal confirmation.",
        )
    # Staging authority can never create a formal conflict.
    confirmed = False
    payload = {
        "schema_version": "conflict_adjudication_decision_v1",
        "authority_scope": "staging_only",
        "pair_id": candidate.candidate_id,
        "claim_alignment_identity": alignment.claim_alignment_identity,
        "contradiction_signal_identity": signal.contradiction_signal_identity,
        "conflict_candidate_identity": candidate.conflict_candidate_identity,
        "candidate_qualification_identity": (
            qualification.qualification_identity if qualification else None
        ),
        "candidate_qualification_status": (
            qualification.qualification_status if qualification else None
        ),
        "context_difference_identity": (
            difference.context_difference_identity if difference else None
        ),
        "context_difference_binding_identity": (
            difference_binding.migration_binding_identity
            if difference_binding
            else None
        ),
        "comparability_assessment_bundle_identity": (
            bundle.comparability_assessment_bundle_identity if bundle else None
        ),
        "divergence_explanation_bundle_identity": (
            bundle.divergence_explanation_bundle_identity if bundle else None
        ),
        "factor_attribution_bundle_identity": (
            bundle.bundle_identity if bundle else None
        ),
        "formal_gate_policy_identity": gate_identity,
        "adjudication_status": status,
        "formal_conflict_confirmed": confirmed,
        "rationale": rationale,
        "provenance": {
            "production_authority": False,
            "both_attribution_branches_consumed": bundle is not None,
            "scientific_aggregation_performed": False,
            "formal_v3_modified": False,
            "legacy_decision_path": qualification is None,
            "candidate_qualification_consumed": qualification is not None,
        },
        "validator_version": "conflict_adjudication_validator_v1",
        "validation_status": "validated",
    }
    payload["conflict_adjudication_decision_identity"] = (
        conflict_adjudication_decision_identity(payload)
    )
    return ConflictAdjudicationDecision.model_validate(payload)
