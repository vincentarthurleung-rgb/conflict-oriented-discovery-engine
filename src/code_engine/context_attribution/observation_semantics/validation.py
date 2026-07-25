from __future__ import annotations

from typing import Any

from .identities import proposition_core_identity
from .models import ObservationSemanticViews, PropositionCoreView

FORBIDDEN_CORE_KEYS = {
    "observation_id", "direction", "sign", "polarity", "dose", "duration", "species",
    "measurement_method", "comparability", "explanation", "final",
}


def validate_proposition_core(payload: PropositionCoreView | dict[str, Any]) -> tuple[PropositionCoreView, list[str]]:
    raw = payload.model_dump() if isinstance(payload, PropositionCoreView) else payload
    errors = [f"forbidden_core_dimension:{key}" for key in FORBIDDEN_CORE_KEYS if key in raw]
    value = payload if isinstance(payload, PropositionCoreView) else PropositionCoreView.model_validate(payload)
    if value.proposition_core_identity != proposition_core_identity(value.model_dump()):
        errors.append("proposition_core_identity_mismatch")
    return value, errors


def validate_observation_semantic_views(payload: ObservationSemanticViews | dict[str, Any]) -> tuple[ObservationSemanticViews, list[str]]:
    value = payload if isinstance(payload, ObservationSemanticViews) else ObservationSemanticViews.model_validate(payload)
    _, errors = validate_proposition_core(value.proposition_core_view)
    if value.observation_id != value.contradiction_result_view.observation_id:
        errors.append("result_view_observation_mismatch")
    if value.observation_id != value.context_envelope_ref.observation_id:
        errors.append("context_ref_observation_mismatch")
    if value.observation_id != value.granularity_qualification_view.observation_id:
        errors.append("qualification_view_observation_mismatch")
    return value, errors
