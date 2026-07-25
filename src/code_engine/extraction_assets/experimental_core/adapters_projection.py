"""Read-only adapters for historical projection identities."""
from __future__ import annotations

from typing import Any


def historical_projection_ref(observation: dict[str, Any]) -> str | None:
    return observation.get("source_projection_identity")
