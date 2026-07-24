"""L4a: factual differences between validated endpoint contexts."""

from .adapters import adapt_legacy_pair_to_context_difference
from .models import ContextDifference, FactorDifference
from .validation import validate_context_difference

__all__ = [
    "ContextDifference",
    "FactorDifference",
    "adapt_legacy_pair_to_context_difference",
    "validate_context_difference",
]
