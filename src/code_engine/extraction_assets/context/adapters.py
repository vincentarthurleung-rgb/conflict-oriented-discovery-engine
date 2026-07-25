"""Non-destructive adapters from the current scientific context schema."""
from __future__ import annotations

from typing import Any

from ...context_attribution.observation_context.models import ObservationContext


def adapt_validated_observation_context(payload: dict[str, Any]) -> ObservationContext:
    """Validate through the existing owner; never reinterpret scientific facts."""
    return ObservationContext.model_validate(payload)
