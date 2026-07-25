"""Conservative deterministic experiment-scope construction."""
from __future__ import annotations

from typing import Any


AUTHORITATIVE_METHODS = {
    "historical_explicit_experiment_group", "stable_experiment_index",
    "deterministic_source_structure", "structured_object_scope_reference",
    "explicit_contract_scope",
}


def scope_authority(method: str, *, source_conflict: bool = False) -> str:
    if source_conflict:
        return "blocked"
    return "authoritative" if method in AUTHORITATIVE_METHODS else "candidate_only"


def same_paragraph_is_scope(_: Any, __: Any) -> bool:
    return False


def similar_text_is_scope(_: Any, __: Any) -> bool:
    return False
