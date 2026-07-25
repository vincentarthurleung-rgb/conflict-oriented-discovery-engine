"""Revision-safe context normalization helpers."""
from __future__ import annotations

from typing import Any


def normalization_view(
    *, raw_text: str | None, extracted_value: Any, canonical_value: Any,
    status: str, unresolved_reason: str | None = None,
) -> dict[str, Any]:
    """Return all value layers; unresolved values are never dropped."""
    return {
        "raw_text": raw_text,
        "extracted_value": extracted_value,
        "canonical_value": canonical_value,
        "normalization_status": status,
        "unresolved_reason": unresolved_reason,
    }
