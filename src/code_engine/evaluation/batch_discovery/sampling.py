"""Deterministic candidate sampling for human annotation."""

from __future__ import annotations

import hashlib


def sample_conflicts(candidates: list[dict], sample_size: int) -> list[dict]:
    ordered = sorted(
        candidates,
        key=lambda item: hashlib.sha256(f"{item.get('prompt_id')}|{item.get('candidate_id')}".encode()).hexdigest(),
    )
    return [{**item, "annotation_label": None, "annotator_notes": ""} for item in ordered[:max(0, sample_size)]]


__all__ = ["sample_conflicts"]
