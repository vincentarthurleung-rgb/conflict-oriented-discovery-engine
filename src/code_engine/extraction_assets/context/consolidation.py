"""Deterministic field consolidation; direct evidence always wins."""
from __future__ import annotations

from typing import Any

PRIORITY = {
    "validated_direct_local": 1,
    "validated_same_observation": 2,
    "validated_scope_inheritance": 3,
    "historical_validated_consolidation": 4,
}


def resolve_field(records: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [r for r in records if r.get("validation_status") in {"validated", "validated_legacy"}]
    if not valid:
        return {"selected": None, "resolution_method": "unresolved", "conflict_status": "unresolved"}
    best_rank = min(PRIORITY.get(r.get("resolution_method", ""), 99) for r in valid)
    best = [r for r in valid if PRIORITY.get(r.get("resolution_method", ""), 99) == best_rank]
    values = {repr(r.get("extracted_value")) for r in best}
    if len(values) != 1:
        return {"selected": None, "resolution_method": "unresolved", "conflict_status": "conflict"}
    return {"selected": best[0], "resolution_method": best[0]["resolution_method"], "conflict_status": "clear"}
