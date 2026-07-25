"""Field evidence construction and deterministic exact anchor reconstruction."""
from __future__ import annotations

import unicodedata
from typing import Literal

from .identities import sha256_bytes

NORMALIZATION_VERSION = "unicode_nfc_exact_substring_v1"


def reconstruct_exact_anchor(
    source_text: str,
    evidence_text: str,
    *,
    expected_source_sha256: str,
) -> dict[str, object]:
    actual = sha256_bytes(source_text.encode("utf-8"))
    base = {
        "algorithm": "exact_substring",
        "algorithm_version": NORMALIZATION_VERSION,
        "source_hash_valid": actual == expected_source_sha256,
        "authoritative": False,
        "character_spans": [],
    }
    if actual != expected_source_sha256:
        return {**base, "status": "unresolved", "reason": "source_hash_mismatch"}
    source = unicodedata.normalize("NFC", source_text)
    needle = unicodedata.normalize("NFC", evidence_text)
    if not needle:
        return {**base, "status": "unresolved", "reason": "empty_evidence_text"}
    positions: list[int] = []
    start = 0
    while True:
        index = source.find(needle, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    spans = [(index, index + len(needle)) for index in positions]
    if len(spans) == 1:
        return {**base, "status": "exact", "reason": None, "authoritative": True, "character_spans": spans}
    if len(spans) > 1:
        return {**base, "status": "ambiguous", "reason": "multiple_exact_matches", "character_spans": spans}
    return {**base, "status": "unresolved", "reason": "no_exact_match"}
