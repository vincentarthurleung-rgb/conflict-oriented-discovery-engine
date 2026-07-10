"""Deterministic double-annotation agreement and disagreement detection."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from code_engine.system_b.persistence.models import Annotation, Assignment


SCHEMA_FIELDS = (
    "evidence_supported",
    "subject_correct",
    "relation_correct",
    "object_correct",
    "direction_correct",
    "context_captured",
)


def _fields(annotation: Annotation) -> dict:
    value = json.loads(annotation.structured_fields_json or "{}")
    value["final_label"] = annotation.final_label
    value["review_disposition"] = annotation.review_disposition
    return value


def compare_annotations(session: Session, *, project_id: str, review_item_id: str) -> dict:
    assignments = session.execute(select(Assignment).where(
        Assignment.project_id == project_id,
        Assignment.review_item_id == review_item_id,
        Assignment.assignment_role.in_(["primary", "secondary"]),
    )).scalars().all()
    by_role = {row.assignment_role: row for row in assignments}
    if "primary" not in by_role or "secondary" not in by_role:
        return {"review_item_id": review_item_id, "status": "needs_assignment", "field_differences": {}}
    annotations = session.execute(select(Annotation).where(
        Annotation.project_id == project_id,
        Annotation.review_item_id == review_item_id,
        Annotation.assignment_id.in_([by_role["primary"].assignment_id, by_role["secondary"].assignment_id]),
    )).scalars().all()
    by_assignment = {row.assignment_id: row for row in annotations if row.status == "submitted"}
    a = by_assignment.get(by_role["primary"].assignment_id)
    b = by_assignment.get(by_role["secondary"].assignment_id)
    if not a or not b:
        return {"review_item_id": review_item_id, "status": "waiting_for_second_annotation", "field_differences": {}}
    if a.review_disposition != "submitted" or b.review_disposition != "submitted":
        return {"review_item_id": review_item_id, "annotation_a_id": a.annotation_id, "annotation_b_id": b.annotation_id, "status": "not_gold_eligible", "field_differences": {}}
    af = _fields(a)
    bf = _fields(b)
    keys = sorted(set(SCHEMA_FIELDS) | set(af) | set(bf))
    diffs = {key: [af.get(key), bf.get(key)] for key in keys if af.get(key) != bf.get(key)}
    exact = not diffs
    return {
        "review_item_id": review_item_id,
        "annotation_a_id": a.annotation_id,
        "annotation_b_id": b.annotation_id,
        "exact_agreement": exact,
        "label_agreement": a.final_label == b.final_label,
        "field_differences": diffs,
        "status": "agreement" if exact else "needs_adjudication",
    }


def project_disagreements(session: Session, *, project_id: str) -> list[dict]:
    item_ids = session.execute(select(Assignment.review_item_id).where(Assignment.project_id == project_id).distinct().order_by(Assignment.review_item_id)).scalars().all()
    return [compare_annotations(session, project_id=project_id, review_item_id=item_id) for item_id in item_ids]
