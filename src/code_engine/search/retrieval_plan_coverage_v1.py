"""Structural proposition coverage validation for Search Plan v2.4-dev."""

from __future__ import annotations

from typing import Any

from code_engine.search.retrieval_intent_v1 import DIMENSION_ORDER


COVERAGE_VERSION = "RetrievalPlanCoverageV1"
COVERAGE_STATES = frozenset({"REPRESENTED", "UNDERREPRESENTED", "OMITTED", "NOT_APPLICABLE"})
RELATION_STATES = frozenset({"REPRESENTED", "RELATION_UNDERREPRESENTED", "NOT_APPLICABLE"})


class RetrievalCoverageError(ValueError):
    """Raised for incomplete or internally inconsistent proposition coverage."""


def validate_blueprint_coverage(blueprint: dict[str, Any], target: dict[str, Any]) -> None:
    rows = blueprint.get("dimension_coverage")
    if not isinstance(rows, list) or len(rows) != len(DIMENSION_ORDER):
        raise RetrievalCoverageError("coverage must contain exactly eleven dimension records")
    dimensions = [row.get("dimension") for row in rows]
    if dimensions != list(DIMENSION_ORDER):
        raise RetrievalCoverageError("coverage dimensions must use the complete frozen stable order")
    for row in rows:
        if row.get("coverage_state") not in COVERAGE_STATES:
            raise RetrievalCoverageError(f"invalid coverage state for {row.get('dimension')}")
        for key in ("source_concept_ids", "query_term_ids"):
            if not isinstance(row.get(key), list) or len(row[key]) != len(set(row[key])):
                raise RetrievalCoverageError(f"{key} must be a unique list")
        if not str(row.get("rationale") or "").strip():
            raise RetrievalCoverageError("coverage rationale is required")
    relation_state = blueprint.get("relation_representation_state")
    if relation_state not in RELATION_STATES:
        raise RetrievalCoverageError("relation representation state is invalid")
    relation = rows[DIMENSION_ORDER.index("relation")]
    target_has_relation = bool(str(target.get("relation_family") or "").strip())
    if target_has_relation:
        if relation["coverage_state"] == "NOT_APPLICABLE" or relation_state == "NOT_APPLICABLE":
            raise RetrievalCoverageError("an applicable target relation cannot be marked not applicable")
        if relation["coverage_state"] in {"UNDERREPRESENTED", "OMITTED"}:
            if relation_state != "RELATION_UNDERREPRESENTED":
                raise RetrievalCoverageError("relation omission must be explicit")
        elif relation["coverage_state"] == "REPRESENTED" and relation_state != "REPRESENTED":
            raise RetrievalCoverageError("represented relation state is inconsistent")
    elif relation_state != "NOT_APPLICABLE":
        raise RetrievalCoverageError("absent relation must be not applicable")
    unit_row = rows[DIMENSION_ORDER.index("biological_unit")]
    if unit_row["coverage_state"] == "REPRESENTED":
        if not unit_row["source_concept_ids"]:
            raise RetrievalCoverageError("represented biological unit lacks an independent concept")
        subject_ids = set(rows[DIMENSION_ORDER.index("subject")]["source_concept_ids"])
        if subject_ids & set(unit_row["source_concept_ids"]):
            raise RetrievalCoverageError("biological-unit concept cannot double as subject identity")


__all__ = [
    "COVERAGE_STATES",
    "COVERAGE_VERSION",
    "RELATION_STATES",
    "RetrievalCoverageError",
    "validate_blueprint_coverage",
]
