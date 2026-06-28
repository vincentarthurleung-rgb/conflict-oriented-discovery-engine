"""Human annotation labels for conflict validity and actionability."""

from __future__ import annotations

import json
from pathlib import Path


ANNOTATION_LABELS = [
    "valid_contextual_conflict", "valid_direct_conflict", "valid_but_low_actionability",
    "extraction_error", "normalization_error", "relation_polarity_error",
    "context_missing_error", "duplicate_or_redundant", "not_a_real_conflict",
    "insufficient_evidence", "manual_review_uncertain",
]


def annotation_schema() -> dict:
    return {
        "schema_version": "conflict_annotation_v1",
        "primary_label": {"type": "string", "enum": ANNOTATION_LABELS},
        "required_fields": ["prompt_id", "candidate_id", "annotation_label"],
        "optional_fields": ["annotator_id", "annotator_notes", "actionability_score"],
    }


def write_annotation_schema(path: str | Path) -> Path:
    target = Path(path)
    target.write_text(json.dumps(annotation_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


__all__ = ["ANNOTATION_LABELS", "annotation_schema", "write_annotation_schema"]
