"""Small offline orchestration facade."""
from __future__ import annotations

from pathlib import Path

from .raw_replay import extract_raw_features


class HistoricalLineageForensicsService:
    """Read-only facade deliberately exposing no provider/network operation."""

    def inspect_raw(self, path: Path) -> dict:
        return extract_raw_features(path)

