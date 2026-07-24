"""L3: high-recall conflict candidate structure."""

from .adapters import adapt_legacy_weak_candidate
from .models import ConflictCandidate
from .validation import validate_conflict_candidate

__all__ = [
    "ConflictCandidate",
    "adapt_legacy_weak_candidate",
    "validate_conflict_candidate",
]
