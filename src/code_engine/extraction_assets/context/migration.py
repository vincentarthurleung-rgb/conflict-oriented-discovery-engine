"""Sidecar-only historical context migration."""
from __future__ import annotations

from typing import Any


def map_legacy_field(field_name: str, mapping: dict[str, tuple[str, str]]) -> dict[str, Any]:
    if field_name not in mapping:
        return {"original_field_name": field_name, "field_id": None, "mapping_status": "unresolved"}
    field_id, status = mapping[field_name]
    return {"original_field_name": field_name, "field_id": field_id, "mapping_status": status}


def migrated_semantic_authority(*, validated: bool, candidate_present: bool) -> str:
    if validated:
        return "validated_legacy"
    if candidate_present:
        return "candidate_only"
    return "unresolved"
