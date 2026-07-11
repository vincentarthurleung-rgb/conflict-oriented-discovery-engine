"""Adjudication workflow services."""
from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from code_engine.system_b.persistence.models import Adjudication, AdjudicationSource, Annotation, Assignment, GoldRecord, EvaluationProtocol, User, utcnow
from code_engine.system_b.persistence.services.agreement_service import compare_annotations, project_disagreements
from code_engine.system_b.persistence.services.audit_service import write_audit_event
from code_engine.system_b.persistence.services.review_service import StaleAnnotationRevision, canonical_json


def _can_adjudicate(session: Session, *, identity: dict, project_id: str, review_item_id: str) -> bool:
    if identity.get("role") == "owner":
        return True
    assignment = session.execute(select(Assignment).where(
        Assignment.project_id == project_id,
        Assignment.review_item_id == review_item_id,
        Assignment.reviewer_user_id == identity.get("user_id"),
        Assignment.assignment_role == "adjudicator",
    )).scalar_one_or_none()
    return bool(assignment)


def adjudication_queue(session: Session, *, identity: dict, project_id: str | None = None) -> list[dict]:
    rows = []
    project_ids = [project_id] if project_id else sorted({x.project_id for x in session.execute(select(Assignment)).scalars().all()})
    for pid in project_ids:
        for item in project_disagreements(session, project_id=pid):
            if item.get("status") != "needs_adjudication":
                continue
            if _can_adjudicate(session, identity=identity, project_id=pid, review_item_id=item["review_item_id"]):
                rows.append({**item, "project_id": pid})
    return rows


def adjudication_detail(session: Session, *, identity: dict, project_id: str, review_item_id: str) -> dict:
    if not _can_adjudicate(session, identity=identity, project_id=project_id, review_item_id=review_item_id):
        raise PermissionError("not_assigned_adjudicator")
    comparison = compare_annotations(session, project_id=project_id, review_item_id=review_item_id)
    annotations = session.execute(select(Annotation).where(Annotation.project_id == project_id, Annotation.review_item_id == review_item_id).order_by(Annotation.created_at)).scalars().all()
    return {"project_id": project_id, "review_item_id": review_item_id, "comparison": comparison, "annotations": [json.loads(canonical_json({
        "annotation_id": a.annotation_id,
        "assignment_id": a.assignment_id,
        "reviewer_username_snapshot": a.reviewer_username_snapshot,
        "schema_id": a.schema_id,
        "schema_version": a.schema_version,
        "schema_hash": a.schema_hash,
        "final_label": a.final_label,
        "structured_fields": json.loads(a.structured_fields_json or "{}"),
        "revision": a.revision,
        "submitted_at": a.submitted_at.isoformat() if a.submitted_at else "",
    })) for a in annotations]}


def submit_adjudication(
    session: Session,
    *,
    identity: dict,
    project_id: str,
    review_item_id: str,
    payload: dict,
    request_context: dict | None = None,
) -> dict:
    if not _can_adjudicate(session, identity=identity, project_id=project_id, review_item_id=review_item_id):
        raise PermissionError("not_assigned_adjudicator")
    user = session.get(User, identity.get("user_id") or "")
    if not user:
        raise PermissionError("adjudicator_not_found")
    comparison = compare_annotations(session, project_id=project_id, review_item_id=review_item_id)
    if comparison.get("status") not in {"needs_adjudication", "agreement"}:
        raise ValueError(comparison.get("status") or "not_ready_for_adjudication")
    current = session.execute(select(Adjudication).where(Adjudication.project_id == project_id, Adjudication.review_item_id == review_item_id)).scalar_one_or_none()
    expected = payload.get("expected_revision")
    if current and expected not in (None, "") and int(expected) != current.revision:
        raise StaleAnnotationRevision("stale_adjudication_revision")
    structured = payload.get("structured_gold") if isinstance(payload.get("structured_gold"), dict) else {}
    source_annotation = session.get(Annotation, comparison.get("annotation_a_id") or "") if comparison.get("annotation_a_id") else None
    now = utcnow()
    if current:
        adjudication = current
        adjudication.revision += 1
    else:
        adjudication = Adjudication(project_id=project_id, review_item_id=review_item_id, adjudicator_user_id=user.user_id, adjudicator_username_snapshot=user.username)
        session.add(adjudication)
        session.flush()
        for annotation_id in (comparison.get("annotation_a_id"), comparison.get("annotation_b_id")):
            if annotation_id:
                session.add(AdjudicationSource(adjudication_id=adjudication.adjudication_id, annotation_id=annotation_id))
    adjudication.status = "submitted"
    adjudication.final_label = str(payload.get("final_label") or "").upper()
    adjudication.structured_gold_json = canonical_json(structured)
    adjudication.notes = str(payload.get("notes") or "")
    adjudication.schema_version = str(payload.get("schema_version") or "atlas_gold_v1")
    adjudication.schema_id = str(payload.get("schema_id") or (source_annotation.schema_id if source_annotation else "claim_review_v1"))
    adjudication.schema_hash = str(payload.get("schema_hash") or (source_annotation.schema_hash if source_annotation else ""))
    adjudication.submitted_at = now
    protocol = session.execute(select(EvaluationProtocol).where(EvaluationProtocol.project_id == project_id, EvaluationProtocol.frozen == True).order_by(EvaluationProtocol.version.desc())).scalar_one_or_none()  # noqa: E712
    if protocol:
        candidate_revision = (session.execute(select(func.max(GoldRecord.candidate_revision)).where(GoldRecord.project_id == project_id, GoldRecord.review_item_id == review_item_id)).scalar() or 0) + 1
        session.add(GoldRecord(
            project_id=project_id,
            protocol_id=protocol.protocol_id,
            review_item_id=review_item_id,
            adjudication_id=adjudication.adjudication_id,
            final_gold_label=adjudication.final_label,
            structured_gold_json=adjudication.structured_gold_json,
            schema_id=adjudication.schema_id,
            schema_version=adjudication.schema_version,
            schema_hash=adjudication.schema_hash,
            status="candidate",
            candidate_revision=candidate_revision,
            gold_dataset_version=None,
            gold_version=candidate_revision,
        ))
    write_audit_event(session, action="adjudication_submitted", object_type="adjudication", object_id=adjudication.adjudication_id, actor=identity, project_id=project_id, review_item_id=review_item_id, metadata={"revision": adjudication.revision}, **(request_context or {}))
    return {"adjudication_id": adjudication.adjudication_id, "project_id": project_id, "review_item_id": review_item_id, "status": adjudication.status, "revision": adjudication.revision}
