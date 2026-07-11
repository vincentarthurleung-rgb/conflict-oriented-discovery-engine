"""Gold candidate readiness and freeze services."""
from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from code_engine.system_b.persistence.models import Adjudication, Annotation, Assignment, EvaluationProject, EvaluationProtocol, GoldRecord, utcnow
from code_engine.system_b.persistence.services.agreement_service import compare_annotations, project_disagreements
from code_engine.system_b.persistence.services.audit_service import write_audit_event


def gold_readiness(session: Session, *, project_id: str) -> dict:
    project = session.get(EvaluationProject, project_id)
    if not project:
        raise KeyError("project_not_found")
    protocol = session.execute(select(EvaluationProtocol).where(EvaluationProtocol.project_id == project_id, EvaluationProtocol.frozen == True).order_by(EvaluationProtocol.version.desc())).scalar_one_or_none()  # noqa: E712
    statuses = []
    for row in project_disagreements(session, project_id=project_id):
        if row.get("status") == "needs_adjudication":
            adjudicated = session.execute(select(Adjudication).where(Adjudication.project_id == project_id, Adjudication.review_item_id == row["review_item_id"], Adjudication.status == "submitted")).scalar_one_or_none()
            if adjudicated:
                row = {**row, "status": "adjudicated"}
        statuses.append(row)
    counts: dict[str, int] = {}
    for row in statuses:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    blocked = []
    if project.namespace != "production":
        blocked.append("namespace_not_production")
    if not protocol:
        blocked.append("protocol_not_frozen")
    if counts.get("waiting_for_second_annotation"):
        blocked.append("double_annotation_incomplete")
    if counts.get("needs_adjudication"):
        blocked.append("unresolved_disagreement")
    if counts.get("not_gold_eligible"):
        blocked.append("skip_or_revisit_present")
    return {"project_id": project_id, "ready": not blocked, "blocked_reasons": blocked, "counts_by_status": counts, "protocol_id": protocol.protocol_id if protocol else None}


def gold_candidates(session: Session, *, project_id: str) -> list[dict]:
    rows = session.execute(select(GoldRecord).where(GoldRecord.project_id == project_id).order_by(GoldRecord.review_item_id, GoldRecord.candidate_revision, GoldRecord.gold_dataset_version)).scalars().all()
    return [{
        "gold_record_id": row.gold_record_id,
        "review_item_id": row.review_item_id,
        "final_gold_label": row.final_gold_label,
        "status": row.status,
        "candidate_revision": row.candidate_revision,
        "gold_dataset_version": row.gold_dataset_version,
        "gold_version": row.gold_dataset_version or row.gold_version,
        "schema_id": row.schema_id,
        "schema_version": row.schema_version,
        "schema_hash": row.schema_hash,
    } for row in rows]


def freeze_gold(session: Session, *, owner: dict, project_id: str, confirm: bool) -> dict:
    if owner.get("role") != "owner":
        raise PermissionError("owner_required")
    if not confirm:
        raise ValueError("confirm_required")
    readiness = gold_readiness(session, project_id=project_id)
    if not readiness["ready"]:
        raise ValueError("gold_not_ready:" + ",".join(readiness["blocked_reasons"]))
    protocol = session.get(EvaluationProtocol, readiness["protocol_id"])
    if not protocol:
        raise ValueError("protocol_not_frozen")
    existing_version = session.execute(select(func.max(GoldRecord.gold_dataset_version)).where(GoldRecord.project_id == project_id, GoldRecord.status.in_(("frozen", "superseded")))).scalar() or 0
    new_version = int(existing_version) + 1
    now = utcnow()
    item_ids = session.execute(select(Assignment.review_item_id).where(Assignment.project_id == project_id, Assignment.assignment_role == "primary").order_by(Assignment.review_item_id)).scalars().all()
    created = 0
    for item_id in item_ids:
        comparison = compare_annotations(session, project_id=project_id, review_item_id=item_id)
        if comparison["status"] == "agreement":
            annotation = session.get(Annotation, comparison["annotation_a_id"])
            label = annotation.final_label
            structured = annotation.structured_fields_json
            adjudication_id = None
        else:
            candidate = session.execute(select(GoldRecord).where(GoldRecord.project_id == project_id, GoldRecord.review_item_id == item_id, GoldRecord.status.in_(("candidate", "adjudicated"))).order_by(GoldRecord.candidate_revision.desc())).scalar_one_or_none()
            if not candidate:
                raise ValueError("missing_adjudicated_candidate")
            label = candidate.final_gold_label
            structured = candidate.structured_gold_json
            adjudication_id = candidate.adjudication_id
            schema_id = candidate.schema_id
            schema_version = candidate.schema_version
            schema_hash = candidate.schema_hash
            candidate_revision = candidate.candidate_revision
        if comparison["status"] == "agreement":
            schema_id = annotation.schema_id
            schema_version = annotation.schema_version
            schema_hash = annotation.schema_hash
            candidate_revision = (session.execute(select(func.max(GoldRecord.candidate_revision)).where(GoldRecord.project_id == project_id, GoldRecord.review_item_id == item_id)).scalar() or 0) + 1
        session.add(GoldRecord(
            project_id=project_id,
            protocol_id=protocol.protocol_id,
            review_item_id=item_id,
            adjudication_id=adjudication_id,
            final_gold_label=label,
            structured_gold_json=structured,
            schema_id=schema_id,
            schema_version=schema_version,
            schema_hash=schema_hash,
            status="frozen",
            frozen_by_user_id=owner.get("user_id"),
            frozen_at=now,
            candidate_revision=candidate_revision,
            gold_dataset_version=new_version,
            gold_version=new_version,
        ))
        created += 1
    write_audit_event(session, action="gold_frozen", object_type="gold_dataset_version", object_id=str(new_version), actor=owner, project_id=project_id, metadata={"record_count": created, "gold_dataset_version": new_version})
    return {"project_id": project_id, "gold_dataset_version": new_version, "gold_version": new_version, "frozen_count": created}


def supersede_gold(session: Session, *, owner: dict, project_id: str, gold_version: int) -> dict:
    if owner.get("role") != "owner":
        raise PermissionError("owner_required")
    rows = session.execute(select(GoldRecord).where(GoldRecord.project_id == project_id, GoldRecord.gold_dataset_version == gold_version, GoldRecord.status == "frozen")).scalars().all()
    for row in rows:
        row.status = "superseded"
    write_audit_event(session, action="gold_superseded", object_type="gold_dataset_version", object_id=str(gold_version), actor=owner, project_id=project_id, metadata={"record_count": len(rows)})
    return {"project_id": project_id, "gold_dataset_version": gold_version, "gold_version": gold_version, "superseded_count": len(rows)}
