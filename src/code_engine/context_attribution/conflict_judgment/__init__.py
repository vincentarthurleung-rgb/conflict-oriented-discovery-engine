"""L4c: fail-closed staging formal-conflict gate."""

# Compatibility facade. New standard code delegates to unified pair-level
# conflict adjudication, which cannot bypass alignment/signal/explanation.

from .gate import stage_formal_conflict_decision
from .models import FormalConflictDecision
from ..conflict_adjudication.decision import (
    ConflictAdjudicationDecision,
    adjudicate_pair_staging,
    validate_conflict_adjudication,
)

__all__ = [
    "FormalConflictDecision",
    "stage_formal_conflict_decision",
    "ConflictAdjudicationDecision",
    "adjudicate_pair_staging",
    "validate_conflict_adjudication",
]
