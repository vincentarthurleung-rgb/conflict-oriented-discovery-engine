"""Coverage and completeness calculations."""
from __future__ import annotations

from collections import Counter
from typing import Any


def rate(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(bool(row.get(key)) for row in rows) / len(rows), 6) if rows else 0.0


def category_state_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, Counter] = {}
    for row in rows:
        result.setdefault(row["semantic_category"], Counter())[row["coverage_state"]] += 1
    return {key: dict(value) for key, value in result.items()}
