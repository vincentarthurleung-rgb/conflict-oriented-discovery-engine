from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..models import ContextPairAttributionV3


def read_legacy_pair_attribution(payload: dict[str, Any]) -> ContextPairAttributionV3:
    """Validate and read a copy. Historical payloads are never mutated."""
    copied = deepcopy(payload)
    if copied.get("schema_version") == "context_pair_attribution_v2":
        copied["schema_version"] = "context_pair_attribution_v3"
    return ContextPairAttributionV3.model_validate(copied)
