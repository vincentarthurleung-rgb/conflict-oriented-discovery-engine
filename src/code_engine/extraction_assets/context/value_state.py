"""Context value-state construction with fail-closed evidence requirements."""
from __future__ import annotations

from .models import ContextValueState, ContextValueStateBasis


def classify_missing_provider_field(*, prompt_requested: bool) -> ContextValueState:
    return ContextValueState.not_extracted if prompt_requested else ContextValueState.unknown


def legacy_null_basis() -> ContextValueStateBasis:
    return ContextValueStateBasis(
        value_state="legacy_null_unresolved", state_basis_type="historical_null",
        state_authority="legacy_unresolved", limitations=["legacy_null_not_semantically_resolved"],
    )
