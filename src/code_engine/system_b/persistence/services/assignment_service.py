"""Assignment-scoped review queue services."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Iterable

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from code_engine.system_b.persistence.models import Annotation, Assignment, AssignmentBatch, EvaluationProject, EvaluationProtocol, ReviewItem, User, utcnow
from code_engine.system_b.persistence.services.audit_service import write_audit_event
from code_engine.system_b.persistence.services.review_service import review_item_to_dict
from code_engine.system_b.authorization import REVIEW_ASSIGNMENT_ROLES


def _json(value) -> str:
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _user(session: Session, user_id: str, expected_role: str | None = None) -> User:
    user = session.get(User, user_id)
    if not user or not user.enabled:
        raise ValueError("user_not_found")
    if expected_role and user.role != expected_role:
        raise ValueError(f"user_must_be_{expected_role}")
    return user


def create_project_with_assignments(
    session: Session,
    *,
    owner: dict,
    name: str,
    namespace: str,
    annotation_schema_version: str,
    primary_reviewer_user_id: str,
    secondary_reviewer_user_id: str,
    adjudicator_user_id: str,
    batch_size: int = 50,
    due_at: datetime | None = None,
    case_ids: Iterable[str] | None = None,
    item_ids: Iterable[str] | None = None,
) -> dict:
    if namespace not in {"pilot", "production"}:
        raise ValueError("projects_must_use_pilot_or_production_namespace")
    if primary_reviewer_user_id == secondary_reviewer_user_id:
        raise ValueError("primary_secondary_must_differ")
    primary = _user(session, primary_reviewer_user_id)
    secondary = _user(session, secondary_reviewer_user_id)
    adjudicator = _user(session, adjudicator_user_id)
    if primary.role != "reviewer" or secondary.role != "reviewer":
        raise ValueError("primary_secondary_must_be_reviewers")
    if adjudicator.role not in {"adjudicator", "reviewer"}:
        raise ValueError("adjudicator_role_required")
    if primary.user_id == adjudicator.user_id or secondary.user_id == adjudicator.user_id:
        raise ValueError("adjudicator_must_be_distinct")

    query = select(ReviewItem).where(ReviewItem.namespace == namespace)
    cases = sorted(set(case_ids or []))
    items = sorted(set(item_ids or []))
    if cases:
        query = query.where(ReviewItem.case_id.in_(cases))
    if items:
        query = query.where(ReviewItem.review_item_id.in_(items))
    review_items = session.execute(query.order_by(ReviewItem.case_id, ReviewItem.item_type, ReviewItem.review_item_id)).scalars().all()
    if not review_items:
        raise ValueError("no_review_items_selected")

    project = EvaluationProject(
        name=name,
        description="Owner-created formal production evaluation project.",
        namespace=namespace,
        status="active",
        created_by_user_id=owner.get("user_id"),
    )
    session.add(project)
    session.flush()
    protocol_payload = {
        "annotation_schema_version": annotation_schema_version,
        "case_ids": [item.case_id for item in review_items],
        "item_ids": [item.review_item_id for item in review_items],
    }
    protocol = EvaluationProtocol(
        project_id=project.project_id,
        version=1,
        protocol_json=_json(protocol_payload),
        case_ids_sha256=_sha(protocol_payload["case_ids"]),
        metric_registry_sha256=_sha({"registry": "atlas_metric_registry_v1"}),
        annotation_schema_sha256=_sha({"annotation_schema_version": annotation_schema_version}),
        dataset_split_sha256=_sha(protocol_payload["item_ids"]),
        frozen=True,
        created_by_user_id=owner.get("user_id"),
        frozen_at=utcnow(),
    )
    session.add(protocol)

    created_assignments = []
    for role, reviewer in (("primary", primary), ("secondary", secondary), ("adjudicator", adjudicator)):
        batch = AssignmentBatch(
            project_id=project.project_id,
            reviewer_user_id=reviewer.user_id,
            batch_index=0,
            batch_size=batch_size,
            filter_json=_json({"case_ids": cases, "item_ids": items}),
            status="assigned",
            assigned_by_user_id=owner.get("user_id"),
            due_at=due_at,
        )
        session.add(batch)
        session.flush()
        for item in review_items:
            existing = session.execute(select(Assignment).where(
                Assignment.project_id == project.project_id,
                Assignment.review_item_id == item.review_item_id,
                Assignment.reviewer_user_id == reviewer.user_id,
                Assignment.assignment_role == role,
            )).scalar_one_or_none()
            if existing:
                continue
            assignment = Assignment(
                project_id=project.project_id,
                batch_id=batch.batch_id,
                review_item_id=item.review_item_id,
                reviewer_user_id=reviewer.user_id,
                assignment_role=role,
                status="assigned",
                assigned_by_user_id=owner.get("user_id"),
            )
            session.add(assignment)
            created_assignments.append(assignment)
    session.flush()
    write_audit_event(session, action="assignment_batch_created", object_type="project", object_id=project.project_id, actor=owner, project_id=project.project_id, metadata={"items": len(review_items), "primary": primary.user_id, "secondary": secondary.user_id, "adjudicator": adjudicator.user_id})
    return {
        "project_id": project.project_id,
        "protocol_id": protocol.protocol_id,
        "review_item_count": len(review_items),
        "assignment_count": len(created_assignments),
    }


def assignment_to_dict(row: Assignment) -> dict:
    return {
        "assignment_id": row.assignment_id,
        "project_id": row.project_id,
        "batch_id": row.batch_id,
        "review_item_id": row.review_item_id,
        "reviewer_user_id": row.reviewer_user_id,
        "assignment_role": row.assignment_role,
        "status": row.status,
        "assigned_at": row.assigned_at.isoformat() if row.assigned_at else "",
        "completed_at": row.completed_at.isoformat() if row.completed_at else "",
    }


def my_assignments(session: Session, *, user_id: str) -> list[dict]:
    rows = session.execute(select(Assignment).where(Assignment.reviewer_user_id == user_id).order_by(Assignment.assigned_at, Assignment.assignment_id)).scalars().all()
    return [assignment_to_dict(row) for row in rows]


def my_batches(session: Session, *, user_id: str) -> list[dict]:
    rows = session.execute(select(AssignmentBatch, EvaluationProject).join(EvaluationProject, AssignmentBatch.project_id == EvaluationProject.project_id).where(AssignmentBatch.reviewer_user_id == user_id).order_by(AssignmentBatch.batch_index, AssignmentBatch.batch_id)).all()
    return [{
        "batch_id": row.batch_id,
        "project_id": row.project_id,
        "project_name": project.name,
        "project_namespace": project.namespace,
        "batch_index": row.batch_index,
        "batch_size": row.batch_size,
        "status": row.status,
        "assigned_at": row.assigned_at.isoformat() if row.assigned_at else "",
        "due_at": row.due_at.isoformat() if row.due_at else "",
    } for row, project in rows]


def my_review_items(
    session: Session,
    *,
    user_id: str,
    case_id: str | None = None,
    item_type: str | None = None,
    project_id: str | None = None,
) -> list[dict]:
    query = (
        select(Assignment, ReviewItem, EvaluationProject, Annotation)
        .join(ReviewItem, Assignment.review_item_id == ReviewItem.review_item_id)
        .join(EvaluationProject, Assignment.project_id == EvaluationProject.project_id)
        .outerjoin(Annotation, and_(
            Annotation.project_id == Assignment.project_id,
            Annotation.review_item_id == Assignment.review_item_id,
            Annotation.reviewer_user_id == Assignment.reviewer_user_id,
        ))
        .where(Assignment.reviewer_user_id == user_id, Assignment.assignment_role.in_(REVIEW_ASSIGNMENT_ROLES))
        .order_by(Assignment.assigned_at, ReviewItem.case_id, ReviewItem.review_item_id)
    )
    if case_id:
        query = query.where(ReviewItem.case_id == case_id)
    if item_type:
        query = query.where(ReviewItem.item_type == item_type)
    if project_id:
        query = query.where(Assignment.project_id == project_id)
    rows = session.execute(query).all()
    items = []
    for assignment, item, project, annotation in rows:
        payload = review_item_to_dict(item, annotation, assignment=assignment, project=project)
        payload["review_status"] = "reviewed" if assignment.status in {"submitted", "skipped", "revisit", "completed"} else "unreviewed"
        items.append(payload)
    return items


def my_review_workspace(session: Session, *, user_id: str) -> dict:
    items = my_review_items(session, user_id=user_id)
    cases: dict[str, dict] = {}
    for item in items:
        case_id = item.get("case_id") or "unknown"
        item_type = item.get("item_type") or "unknown"
        case = cases.setdefault(case_id, {"case_id": case_id, "total": 0, "reviewed": 0, "unreviewed": 0, "layers": {}})
        layer = case["layers"].setdefault(item_type, {
            "layer_id": item_type,
            "label": item_type.replace("_", " ").title(),
            "total": 0,
            "reviewed": 0,
            "unreviewed": 0,
            "valid": 0,
            "partial": 0,
            "invalid": 0,
            "unclear": 0,
        })
        reviewed = item.get("review_status") == "reviewed"
        case["total"] += 1
        case["reviewed" if reviewed else "unreviewed"] += 1
        layer["total"] += 1
        layer["reviewed" if reviewed else "unreviewed"] += 1
        label = str((item.get("annotation") or {}).get("final_label") or "").lower()
        if label in {"valid", "partial", "invalid", "unclear"}:
            layer[label] += 1
    result = []
    for case in cases.values():
        case["layers"] = sorted(case["layers"].values(), key=lambda row: (row["label"], row["layer_id"]))
        result.append(case)
    return {"cases": sorted(result, key=lambda row: row["case_id"]), "total_items": len(items)}


def my_review_metrics(session: Session, *, user_id: str) -> dict:
    items = my_review_items(session, user_id=user_id)
    reviewed = [item for item in items if item.get("review_status") == "reviewed"]
    labels: dict[str, int] = {}
    dispositions: dict[str, int] = {}
    cases: dict[str, int] = {}
    for item in reviewed:
        annotation = item.get("annotation") or {}
        label = annotation.get("final_label")
        disposition = annotation.get("review_disposition")
        if label:
            labels[label] = labels.get(label, 0) + 1
        if disposition:
            dispositions[disposition] = dispositions.get(disposition, 0) + 1
        case_id = item.get("case_id") or "unknown"
        cases[case_id] = cases.get(case_id, 0) + 1
    total = len(items)
    return {
        "reviewed_count": len(reviewed),
        "unreviewed_count": total - len(reviewed),
        "reviewed_fraction": round(len(reviewed) / total, 6) if total else None,
        "counts_by_final_label": labels,
        "counts_by_disposition": dispositions,
        "counts_by_case": cases,
        "note": "Assignment-scoped live metrics for the current reviewer.",
    }


def my_progress(session: Session, *, user_id: str) -> dict:
    rows = session.execute(select(Assignment.status, func.count()).where(Assignment.reviewer_user_id == user_id, Assignment.assignment_role.in_(REVIEW_ASSIGNMENT_ROLES)).group_by(Assignment.status)).all()
    counts = {status: count for status, count in rows}
    total = sum(counts.values())
    done = sum(counts.get(status, 0) for status in ("submitted", "skipped", "revisit", "completed"))
    return {"total": total, "completed": done, "remaining": max(0, total - done), "counts_by_status": counts, "fraction_complete": round(done / total, 6) if total else None}
