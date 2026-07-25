"""Read-only context-field grouping for method recovery."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def fields_by_observation(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        identity = row.get("observation_identity") or row.get("observation_candidate_identity")
        if identity:
            grouped[str(identity)].append(row)
    return dict(grouped)
