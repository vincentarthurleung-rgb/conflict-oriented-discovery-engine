from __future__ import annotations

from typing import Any

from .identities import formal_conflict_decision_identity
from .models import FormalConflictDecision


def validate_formal_conflict_decision(
    payload: FormalConflictDecision | dict[str, Any],
) -> tuple[FormalConflictDecision, list[str]]:
    value = (
        payload
        if isinstance(payload, FormalConflictDecision)
        else FormalConflictDecision.model_validate(payload)
    )
    errors: list[str] = []
    if value.formal_conflict_confirmed != (
        value.decision_status == "formal_conflict_confirmed"
    ):
        errors.append("formal_conflict_boolean_status_mismatch")
    if value.formal_conflict_decision_identity != formal_conflict_decision_identity(
        value.model_dump()
    ):
        errors.append("formal_conflict_decision_identity_mismatch")
    return value, errors
