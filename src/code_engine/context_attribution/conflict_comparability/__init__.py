"""L4b: policy/adjudication-backed comparability assessment."""

# Compatibility facade. New orchestration uses per-factor assessments from
# ``conflict_adjudication.comparability``.

from .models import ConflictComparabilityAssessment
from .service import create_pending_comparability
from .validation import validate_conflict_comparability
from ..conflict_adjudication.comparability import (
    FactorComparabilityAssessment,
    create_pending_factor_comparability,
    validate_factor_comparability,
)

__all__ = [
    "ConflictComparabilityAssessment",
    "create_pending_comparability",
    "validate_conflict_comparability",
    "FactorComparabilityAssessment",
    "create_pending_factor_comparability",
    "validate_factor_comparability",
]
