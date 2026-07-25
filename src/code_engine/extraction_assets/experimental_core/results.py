"""Explicit-only observed-result migration."""
from __future__ import annotations

from typing import Any


def explicit_result_candidates(source: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(source.get("observed_results"), list):
        return [dict(item) for item in source["observed_results"] if isinstance(item, dict)]
    if isinstance(source.get("observation"), dict) and source["observation"].get("observed_result") is not None:
        return [dict(source["observation"])]
    return []

