from __future__ import annotations

from ...context_difference.migration import ContextDifferenceMigrationBinding
from ...context_difference.models import ContextDifference
from .identities import factor_comparability_identity
from .models import FactorComparabilityAssessment


def validate_factor_comparability(
    payload: FactorComparabilityAssessment | dict,
    *,
    difference: ContextDifference,
    difference_binding: ContextDifferenceMigrationBinding,
) -> tuple[FactorComparabilityAssessment, list[str]]:
    value = (
        payload
        if isinstance(payload, FactorComparabilityAssessment)
        else FactorComparabilityAssessment.model_validate(payload)
    )
    errors: list[str] = []
    factor_ids = {item.factor_id for item in difference.factor_differences}
    if difference.validation_status != "validated":
        errors.append("factor_comparability_requires_validated_difference")
    if difference_binding.validation_status != "validated":
        errors.append("factor_comparability_requires_validated_binding")
    if (
        value.context_difference_identity != difference.context_difference_identity
        or value.context_difference_binding_identity
        != difference_binding.migration_binding_identity
        or value.factor_id not in factor_ids
    ):
        errors.append("factor_comparability_upstream_identity_mismatch")
    if value.assessment_status == "validated":
        if value.validation_status != "validated":
            errors.append("comparability_validation_status_mismatch")
        if not value.provenance.get("authority_validated"):
            errors.append("comparability_authority_not_validated")
    elif value.validation_status == "validated":
        errors.append("pending_comparability_cannot_be_validated")
    if value.factor_comparability_identity != factor_comparability_identity(
        value.model_dump()
    ):
        errors.append("factor_comparability_identity_mismatch")
    return value, errors
