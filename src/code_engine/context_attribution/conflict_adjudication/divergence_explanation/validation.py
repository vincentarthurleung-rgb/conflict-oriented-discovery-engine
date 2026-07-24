from __future__ import annotations

from ...conflict_candidate.contradiction import ContradictionSignal
from ...context_difference.migration import ContextDifferenceMigrationBinding
from ...context_difference.models import ContextDifference
from .identities import factor_divergence_explanation_identity
from .models import FactorDivergenceExplanation


def validate_divergence_explanation(
    payload: FactorDivergenceExplanation | dict,
    *,
    difference: ContextDifference,
    difference_binding: ContextDifferenceMigrationBinding,
    signal: ContradictionSignal,
) -> tuple[FactorDivergenceExplanation, list[str]]:
    value = (
        payload
        if isinstance(payload, FactorDivergenceExplanation)
        else FactorDivergenceExplanation.model_validate(payload)
    )
    errors: list[str] = []
    factor_ids = {item.factor_id for item in difference.factor_differences}
    if difference.validation_status != "validated":
        errors.append("explanation_requires_validated_difference")
    if signal.validation_status != "validated":
        errors.append("explanation_requires_validated_signal")
    if (
        value.context_difference_identity != difference.context_difference_identity
        or value.context_difference_binding_identity
        != difference_binding.migration_binding_identity
        or value.contradiction_signal_identity
        != signal.contradiction_signal_identity
        or value.factor_id not in factor_ids
    ):
        errors.append("explanation_upstream_identity_mismatch")
    if value.assessment_status == "assessed":
        if value.validation_status != "validated":
            errors.append("explanation_validation_status_mismatch")
        if not value.provenance.get("authority_validated"):
            errors.append("explanation_authority_not_validated")
    elif value.validation_status == "validated":
        errors.append("pending_explanation_cannot_be_validated")
    if (
        value.factor_divergence_explanation_identity
        != factor_divergence_explanation_identity(value.model_dump())
    ):
        errors.append("factor_divergence_explanation_identity_mismatch")
    return value, errors
