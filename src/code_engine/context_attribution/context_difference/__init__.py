"""L4a: factual differences between validated endpoint contexts."""

from .adapters import adapt_legacy_pair_to_context_difference
from .models import ContextDifference, FactorDifference
from .validation import validate_context_difference
from .migration import (
    ContextDifferenceMigrationBinding,
    bind_context_difference_migration,
)

__all__ = [
    "ContextDifference",
    "FactorDifference",
    "adapt_legacy_pair_to_context_difference",
    "validate_context_difference",
    "ContextDifferenceMigrationBinding",
    "bind_context_difference_migration",
]
