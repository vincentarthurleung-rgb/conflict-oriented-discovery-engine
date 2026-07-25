"""Deterministic extraction-asset validation helpers."""
from __future__ import annotations

from .identities import sha256_bytes
from .models import SourceSnapshot


def validate_source_snapshot(snapshot: SourceSnapshot) -> list[str]:
    errors: list[str] = []
    if snapshot.input_text is None:
        errors.append("input_text_missing")
    elif sha256_bytes(snapshot.input_text.encode("utf-8")) != snapshot.input_text_sha256:
        errors.append("input_text_hash_mismatch")
    if not snapshot.block_id:
        errors.append("block_id_missing")
    return errors
