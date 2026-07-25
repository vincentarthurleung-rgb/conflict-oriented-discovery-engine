"""Filesystem inventory predicates for experimental-core assets."""
from __future__ import annotations

CORE_TOKENS = (
    "observation", "experiment", "evidence", "extraction", "parsed",
    "validated", "context", "candidate", "lineage", "projection",
)


def is_core_related_artifact(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in CORE_TOKENS)

