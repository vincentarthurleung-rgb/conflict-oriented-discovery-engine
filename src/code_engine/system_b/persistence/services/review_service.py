"""Database-backed review item and annotation services."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from code_engine.system_b.explorer.annotation_store import FINAL_LABELS
from code_engine.system_b.explorer.explorer_api import _jsonl
from code_engine.system_b.persistence.models import (
    Annotation,
    AnnotationEvent,
    Assignment,
    EvaluationProject,
    ReviewItem,
    User,
    utcnow,
)


DEFAULT_PROJECT_NAME = "Atlas default review project"


class StaleAnnotationRevision(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ensure_local_developer(session: Session) -> User:
    user = session.get(User, "local-dev-user")
    if user:
        return user
    user = User(
        user_id="local-dev-user",
        username="local_dev",
        display_name="Local Developer",
        password_hash="no-auth-local-dev",
        role="developer",
        enabled=True,
    )
    session.add(user)
    return user


def ensure_project(session: Session, namespace: str = "test", name: str = DEFAULT_PROJECT_NAME) -> EvaluationProject:
    project = session.execute(
        select(EvaluationProject).where(EvaluationProject.name == name, EvaluationProject.namespace == namespace)
    ).scalar_one_or_none()
    if project:
        return project
    project = EvaluationProject(name=name, description="Default Atlas database-backed review project.", namespace=namespace, status="active")
    session.add(project)
    session.flush()
    return project


def import_review_items(session: Session, review_root: str | Path, *, namespace: str = "test", import_run_id: str | None = None) -> dict:
    root = Path(review_root)
    rows = _jsonl(root / "manual_review_queue.jsonl")
    run_id = import_run_id or sha256_text(str(root.resolve()))[:16]
    inserted = 0
    unchanged = 0
    for row in rows:
        item_id = row.get("review_item_id")
        if not item_id:
            continue
        payload = canonical_json(row)
        source_hash = sha256_text(payload)
        existing = session.get(ReviewItem, item_id)
        if existing:
            unchanged += 1
            continue
        session.add(ReviewItem(
            review_item_id=item_id,
            case_id=row.get("case_id") or "",
            item_type=row.get("item_type") or "unknown",
            source_scope=row.get("source_scope"),
            source_file=row.get("source_file"),
            source_line=row.get("source_line"),
            payload_json=payload,
            source_hash=source_hash,
            import_run_id=run_id,
            namespace=namespace,
        ))
        inserted += 1
    session.flush()
    return {"review_items_seen": len(rows), "review_items_inserted": inserted, "review_items_unchanged": unchanged, "import_run_id": run_id}


def annotation_to_dict(annotation: Annotation) -> dict:
    return {
        "annotation_id": annotation.annotation_id,
        "project_id": annotation.project_id,
        "review_item_id": annotation.review_item_id,
        "assignment_id": annotation.assignment_id,
        "reviewer_user_id": annotation.reviewer_user_id,
        "reviewer_username_snapshot": annotation.reviewer_username_snapshot,
        "reviewer_display_name_snapshot": annotation.reviewer_display_name_snapshot,
        "reviewer_role_snapshot": annotation.reviewer_role_snapshot,
        "namespace": annotation.namespace,
        "schema_version": annotation.schema_version,
        "final_label": annotation.final_label,
        "structured_fields": json.loads(annotation.structured_fields_json or "{}"),
        "notes": annotation.notes,
        "review_disposition": annotation.review_disposition,
        "uncertainty_reason": annotation.uncertainty_reason,
        "status": annotation.status,
        "revision": annotation.revision,
        "client_submission_id": annotation.client_submission_id,
        "created_at": annotation.created_at.isoformat() if annotation.created_at else "",
        "updated_at": annotation.updated_at.isoformat() if annotation.updated_at else "",
        "submitted_at": annotation.submitted_at.isoformat() if annotation.submitted_at else "",
    }


def _structured_fields(payload: dict) -> dict:
    direct = payload.get("structured_fields")
    if isinstance(direct, dict):
        return direct
    keys = (
        "evidence_supported", "subject_correct", "relation_correct", "object_correct",
        "direction_correct", "context_captured", "seed_relevance",
        "mechanistic_usefulness", "worth_followup", "error_type",
    )
    return {k: payload.get(k, "") for k in keys if payload.get(k, "") != ""}


def save_annotation(
    session: Session,
    *,
    review_item_id: str,
    payload: dict,
    identity: dict,
    namespace: str,
    project_name: str = DEFAULT_PROJECT_NAME,
    request_id: str | None = None,
    ip_hash: str | None = None,
    session_hash: str | None = None,
) -> dict:
    item = session.get(ReviewItem, review_item_id)
    if not item:
        raise KeyError("review_item_not_found")
    if namespace == "production" and (not identity.get("authenticated") or identity.get("user_id") == "local-dev-user"):
        raise PermissionError("production annotations require authenticated users")

    user = session.get(User, identity.get("user_id") or "")
    if not user:
        if identity.get("user_id") == "local-dev-user":
            user = ensure_local_developer(session)
        else:
            raise PermissionError("authenticated user is not present in Atlas database")

    project = ensure_project(session, namespace=namespace, name=project_name)
    assignment_id = payload.get("assignment_id") or None
    if assignment_id:
        assignment = session.get(Assignment, assignment_id)
        if not assignment or assignment.reviewer_user_id != user.user_id or assignment.review_item_id != review_item_id:
            raise PermissionError("assignment_not_owned_by_current_user")

    client_submission_id = payload.get("client_submission_id") or None
    if client_submission_id:
        prior = session.execute(select(Annotation).where(
            Annotation.project_id == project.project_id,
            Annotation.reviewer_user_id == user.user_id,
            Annotation.client_submission_id == client_submission_id,
        )).scalar_one_or_none()
        if prior:
            return annotation_to_dict(prior)

    current = session.execute(select(Annotation).where(
        Annotation.project_id == project.project_id,
        Annotation.review_item_id == review_item_id,
        Annotation.reviewer_user_id == user.user_id,
        Annotation.namespace == namespace,
    )).scalar_one_or_none()
    expected_revision = payload.get("expected_revision")
    if current and expected_revision not in (None, "") and int(expected_revision) != current.revision:
        raise StaleAnnotationRevision("stale_annotation_revision")

    disposition = str(payload.get("review_disposition") or "submitted").lower()
    final_label = str(payload.get("final_label") or "").upper()
    if disposition == "submitted" and final_label not in FINAL_LABELS:
        raise ValueError("final_label must be one of: " + ", ".join(sorted(FINAL_LABELS)))
    if disposition != "submitted" and final_label and final_label not in FINAL_LABELS:
        raise ValueError("final_label must be one of: " + ", ".join(sorted(FINAL_LABELS)))
    if disposition not in {"submitted", "skipped", "revisit", "draft"}:
        raise ValueError("review_disposition must be submitted, skipped, revisit, or draft")

    now = utcnow()
    structured = canonical_json(_structured_fields(payload))
    status = "submitted" if disposition in {"submitted", "skipped", "revisit"} else "draft"
    previous_revision = current.revision if current else None
    if current:
        annotation = current
        annotation.revision += 1
        action = "annotation_updated"
    else:
        annotation = Annotation(
            project_id=project.project_id,
            review_item_id=review_item_id,
            assignment_id=assignment_id,
            reviewer_user_id=user.user_id,
            reviewer_username_snapshot=user.username,
            reviewer_display_name_snapshot=user.display_name,
            reviewer_role_snapshot=user.role,
            namespace=namespace,
        )
        session.add(annotation)
        session.flush()
        action = "annotation_created"

    if disposition == "skipped":
        action = "marked_skipped"
    elif disposition == "revisit":
        action = "marked_revisit"
    elif status == "submitted" and not current:
        action = "annotation_submitted"
    elif status == "draft":
        action = "draft_saved"

    annotation.final_label = final_label if disposition == "submitted" else final_label
    annotation.structured_fields_json = structured
    annotation.notes = str(payload.get("notes") or "")
    annotation.review_disposition = disposition
    annotation.uncertainty_reason = str(payload.get("uncertainty_reason") or "")
    annotation.status = status
    annotation.client_submission_id = client_submission_id
    annotation.updated_at = now
    if status == "submitted":
        annotation.submitted_at = now
    session.flush()

    snapshot = annotation_to_dict(annotation)
    session.add(AnnotationEvent(
        annotation_id=annotation.annotation_id,
        project_id=project.project_id,
        review_item_id=review_item_id,
        actor_user_id=user.user_id,
        actor_username_snapshot=user.username,
        action=action,
        previous_revision=previous_revision,
        new_revision=annotation.revision,
        changed_fields_json=canonical_json(sorted(payload.keys())),
        full_snapshot_json=canonical_json(snapshot),
        request_id=request_id,
        ip_hash=ip_hash,
        session_hash=session_hash,
    ))
    return snapshot


def metrics(session: Session, *, namespace: str = "test", project_name: str = DEFAULT_PROJECT_NAME) -> dict:
    project = ensure_project(session, namespace=namespace, name=project_name)
    rows = session.execute(select(Annotation).where(Annotation.project_id == project.project_id, Annotation.namespace == namespace)).scalars().all()
    total = session.execute(select(func.count()).select_from(ReviewItem).where(ReviewItem.namespace == namespace)).scalar() or 0
    labels: dict[str, int] = {}
    dispositions: dict[str, int] = {}
    cases: dict[str, int] = {}
    for row in rows:
        if row.final_label:
            labels[row.final_label] = labels.get(row.final_label, 0) + 1
        dispositions[row.review_disposition] = dispositions.get(row.review_disposition, 0) + 1
        item = session.get(ReviewItem, row.review_item_id)
        if item:
            cases[item.case_id] = cases.get(item.case_id, 0) + 1
    return {
        "reviewed_count": len(rows),
        "unreviewed_count": max(0, total - len(rows)),
        "reviewed_fraction": round(len(rows) / total, 6) if total else None,
        "counts_by_final_label": labels,
        "counts_by_disposition": dispositions,
        "counts_by_case": cases,
        "note": "Database-backed metrics summarize annotation workflow state; paper metrics require frozen Gold.",
    }
