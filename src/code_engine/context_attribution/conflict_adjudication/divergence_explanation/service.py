from __future__ import annotations

from typing import Sequence

from code_engine.extraction_assets.scientific_entity_integrity import (
    ScientificEntityIntegrityGateResultV1, require_scientific_entity_integrity,
)

from ...conflict_candidate.contradiction import ContradictionSignal
from ...context_difference.migration import ContextDifferenceMigrationBinding
from ...context_difference.models import ContextDifference
from .identities import factor_divergence_explanation_identity
from .models import FactorDivergenceExplanation


def create_pending_divergence_explanation(
    *,
    difference: ContextDifference,
    difference_binding: ContextDifferenceMigrationBinding,
    signal: ContradictionSignal,
    factor_id: str,
    entity_integrity_decisions: Sequence[ScientificEntityIntegrityGateResultV1] | None = None,
) -> FactorDivergenceExplanation:
    require_scientific_entity_integrity(
        "divergence_explanatory_power", entity_integrity_decisions
    )
    if difference.validation_status != "validated":
        raise ValueError("explanation_requires_validated_difference")
    if signal.validation_status != "validated":
        raise ValueError("explanation_requires_validated_signal")
    payload = {
        "schema_version": "factor_divergence_explanation_v1",
        "pair_id": difference.candidate_id,
        "context_difference_identity": difference.context_difference_identity,
        "context_difference_binding_identity": (
            difference_binding.migration_binding_identity
        ),
        "contradiction_signal_identity": signal.contradiction_signal_identity,
        "factor_id": factor_id,
        "assessment_status": "pending_policy",
        "explanatory_effect": None,
        "explanation_policy_identity": None,
        "adjudication_identity": None,
        "rationale": "No activated explanation policy or completed adjudication.",
        "provenance": {
            "semantics_activated": False,
            "provider_raw_text_consumed": False,
            "comparability_mapped_to_explanation": False,
            "factor_name_rule_used": False,
            "effect_automatically_derived": False,
        },
        "validator_version": "factor_divergence_explanation_validator_v1",
        "validation_status": "unvalidated",
    }
    payload["factor_divergence_explanation_identity"] = (
        factor_divergence_explanation_identity(payload)
    )
    return FactorDivergenceExplanation.model_validate(payload)
