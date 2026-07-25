"""Projection-v2 reference and activation validation."""
from __future__ import annotations

from typing import Any


def validate_projection_refs(
    projection: dict[str, Any], known_refs: set[str],
) -> tuple[str, list[str]]:
    required = (
        projection["experimental_factor_refs"] + projection["measurement_refs"]
        + projection["observed_result_refs"] + projection["linkage_refs"]
    )
    missing = sorted(ref for ref in required if ref not in known_refs)
    status = (
        "blocked_invalid_links" if missing
        else "ready_for_offline_consumer_validation"
    )
    return status, missing
