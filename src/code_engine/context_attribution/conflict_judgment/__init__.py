"""L4c: fail-closed staging formal-conflict gate."""

from .gate import stage_formal_conflict_decision
from .models import FormalConflictDecision

__all__ = ["FormalConflictDecision", "stage_formal_conflict_decision"]
