"""Explicit-only measurement migration."""
from __future__ import annotations

from typing import Any


def explicit_measurement_candidates(source: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(source.get("measurements"), list):
        return [dict(item) for item in source["measurements"] if isinstance(item, dict)]
    if isinstance(source.get("measurement"), dict) and source["measurement"]:
        return [dict(source["measurement"])]
    return []

