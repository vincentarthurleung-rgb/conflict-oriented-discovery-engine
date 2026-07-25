"""Lossless parsed payload comparisons; no scientific normalization is allowed."""
from __future__ import annotations

from typing import Any

from .identities import canonical_payload_hash
from ..identities import sha256_bytes


def compare_payloads(replayed: Any, historical: Any, *, replayed_bytes: bytes | None = None,
                     historical_bytes: bytes | None = None) -> dict[str, Any]:
    if replayed_bytes is not None and historical_bytes is not None and replayed_bytes == historical_bytes:
        level = "byte_exact"
    elif canonical_payload_hash(replayed) == canonical_payload_hash(historical):
        level = "canonical_exact"
    elif _shape(replayed) == _shape(historical):
        level = "structural_exact"
    elif _overlap(replayed, historical):
        level = "partial_overlap"
    else:
        level = "mismatch"
    return {
        "comparison_level": level,
        "replayed_canonical_hash": canonical_payload_hash(replayed),
        "historical_canonical_hash": canonical_payload_hash(historical),
        "replayed_byte_hash": sha256_bytes(replayed_bytes) if replayed_bytes is not None else None,
        "historical_byte_hash": sha256_bytes(historical_bytes) if historical_bytes is not None else None,
        "omitted_null_distinct": True, "list_order_preserved": True,
        "scientific_normalization_applied": False,
    }


def _shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_shape(item) for item in value]
    return type(value).__name__


def _overlap(left: Any, right: Any) -> bool:
    return isinstance(left, dict) and isinstance(right, dict) and bool(set(left) & set(right))

