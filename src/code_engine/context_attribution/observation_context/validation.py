from __future__ import annotations

from typing import Any

from .identities import observation_context_identity
from .models import ObservationContext

OBSERVATION_CONTEXT_VALIDATOR_VERSION = "observation_context_validator_v1"


def validate_observation_context(
    payload: ObservationContext | dict[str, Any],
) -> tuple[ObservationContext, list[str]]:
    value = (
        payload
        if isinstance(payload, ObservationContext)
        else ObservationContext.model_validate(payload)
    )
    errors: list[str] = []
    expected = observation_context_identity(value.model_dump())
    if value.observation_context_identity != expected:
        errors.append("observation_context_identity_mismatch")
    if value.validation_status != "validated":
        errors.append("observation_context_source_not_validated")
    factor_ids = [factor.factor_id for factor in value.facts]
    if len(factor_ids) != len(set(factor_ids)):
        errors.append("duplicate_observation_context_factor")
    return value, errors
