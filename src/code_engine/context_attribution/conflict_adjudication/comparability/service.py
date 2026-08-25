from __future__ import annotations

from typing import Sequence

from code_engine.extraction_assets.scientific_entity_integrity import (
    ScientificEntityIntegrityGateResultV1, require_scientific_entity_integrity,
)

from ...context_difference.migration import ContextDifferenceMigrationBinding
from ...context_difference.models import ContextDifference
from .identities import factor_comparability_identity
from .models import FactorComparabilityAssessment


def create_pending_factor_comparability(
    *,
    difference: ContextDifference,
    difference_binding: ContextDifferenceMigrationBinding,
    factor_id: str,
    entity_integrity_decisions: Sequence[ScientificEntityIntegrityGateResultV1] | None = None,
) -> FactorComparabilityAssessment:
    require_scientific_entity_integrity("l4b_comparability", entity_integrity_decisions)
    if difference.validation_status != "validated":
        raise ValueError("factor_comparability_requires_validated_difference")
    if difference_binding.validation_status != "validated":
        raise ValueError("factor_comparability_requires_validated_binding")
    payload = {
        "schema_version": "factor_comparability_assessment_v1",
        "pair_id": difference.candidate_id,
        "context_difference_identity": difference.context_difference_identity,
        "context_difference_binding_identity": (
            difference_binding.migration_binding_identity
        ),
        "factor_id": factor_id,
        "factor_registry_identity": difference.factor_registry_identity,
        "assessment_status": "pending_policy",
        "effect_assessment_status": None,
        "comparability_severity": None,
        "comparability_policy_identity": None,
        "adjudication_identity": None,
        "rationale": "No activated factor comparability policy or adjudication.",
        "provenance": {
            "model_b_activated": False,
            "legacy_provider_effect_consumed": False,
            "missing_mapped_to_unknown": False,
            "severity_automatically_assigned": False,
        },
        "validator_version": "factor_comparability_validator_v1",
        "validation_status": "unvalidated",
    }
    payload["factor_comparability_identity"] = factor_comparability_identity(
        payload
    )
    return FactorComparabilityAssessment.model_validate(payload)
