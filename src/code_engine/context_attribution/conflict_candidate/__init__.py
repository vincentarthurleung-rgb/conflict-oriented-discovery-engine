"""L3: high-recall conflict candidate structure."""

from .adapters import adapt_legacy_weak_candidate
from .models import ConflictCandidate
from .validation import validate_conflict_candidate
from .contradiction import ContradictionSignal, validate_contradiction_signal
from .migration import CandidateMigrationBinding, bind_historical_candidate

__all__ = [
    "ConflictCandidate",
    "adapt_legacy_weak_candidate",
    "validate_conflict_candidate",
    "ContradictionSignal",
    "validate_contradiction_signal",
    "CandidateMigrationBinding",
    "bind_historical_candidate",
]
