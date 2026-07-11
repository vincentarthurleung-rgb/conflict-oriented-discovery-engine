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
from code_engine.system_b.annotation_schemas import SchemaValidationError, schema_for_item_type, validate_annotation_payload
from code_engine.system_b.annotation_schemas.render_projection import form_projection
from code_engine.system_b.persistence.models import (
    Annotation,
    AnnotationEvent,
    Assignment,
    EvaluationProject,
    ReviewItem,
    User,
    utcnow,
)
from code_engine.system_b.persistence.services.audit_service import write_audit_event


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
    warnings = []
    for row in rows:
        item_id = row.get("review_item_id")
        if not item_id:
            continue
        payload = canonical_json(row)
        source_hash = sha256_text(payload)
        existing = session.get(ReviewItem, item_id)
        if existing:
            if existing.source_hash != source_hash:
                warnings.append({"review_item_id": item_id, "warning": "source_hash_changed", "old_hash": existing.source_hash, "new_hash": source_hash})
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
    return {"review_items_seen": len(rows), "review_items_inserted": inserted, "review_items_unchanged": unchanged, "import_run_id": run_id, "warnings": warnings}


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
        "schema_id": annotation.schema_id,
        "schema_version": annotation.schema_version,
        "schema_hash": annotation.schema_hash,
        "instructions_version": annotation.instructions_version,
        "instructions_hash": annotation.instructions_hash,
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


def _legacy_structured_fields(payload: dict) -> dict:
    direct = payload.get("structured_fields")
    if isinstance(direct, dict):
        return direct
    keys = (
        "evidence_supported", "subject_correct", "relation_correct", "object_correct",
        "direction_correct", "context_captured", "seed_relevance",
        "mechanistic_usefulness", "worth_followup", "error_type",
    )
    return {k: payload.get(k, "") for k in keys if payload.get(k, "") != ""}


def review_item_schema_payload(item: ReviewItem) -> dict:
    schema = schema_for_item_type(item.item_type)
    payload = {
        "schema_id": schema.schema_id if schema else None,
        "schema_version": schema.version if schema else None,
        "schema_hash": schema.sha256 if schema else None,
        "form_definition": form_projection(schema),
    }
    if schema:
        payload.update({
            "instructions_version": schema.instructions_version,
            "instructions_hash": schema.instructions_hash,
        })
    return payload


def review_item_to_dict(item: ReviewItem, annotation: Annotation | None = None, *, assignment: Assignment | None = None, project: EvaluationProject | None = None) -> dict:
    payload = json.loads(item.payload_json or "{}")
    payload.update(review_item_schema_payload(item))
    if annotation:
        payload["annotation"] = annotation_to_dict(annotation)
    if assignment:
        payload.update({
            "assignment_id": assignment.assignment_id,
            "assignment_role": assignment.assignment_role,
            "assignment_status": assignment.status,
            "project_id": assignment.project_id,
        })
    if project:
        payload["evaluation_project"] = {
            "project_id": project.project_id,
            "name": project.name,
            "namespace": project.namespace,
            "status": project.status,
        }
    return payload


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

    project = None
    assignment_id = payload.get("assignment_id") or None
    assignment = None
    if assignment_id:
        assignment = session.get(Assignment, assignment_id)
        if not assignment or assignment.reviewer_user_id != user.user_id or assignment.review_item_id != review_item_id:
            raise PermissionError("assignment_not_owned_by_current_user")
    elif namespace == "production":
        rows = session.execute(select(Assignment).where(
            Assignment.review_item_id == review_item_id,
            Assignment.reviewer_user_id == user.user_id,
        )).scalars().all()
        if len(rows) != 1:
            raise PermissionError("assignment_required")
        assignment = rows[0]
        assignment_id = assignment.assignment_id
    if assignment:
        project = session.get(EvaluationProject, assignment.project_id)
        if not project or project.status != "active" or project.namespace != namespace:
            raise PermissionError("assignment_project_not_active")
        if assignment.assignment_role not in {"primary", "secondary", "expert"}:
            raise PermissionError("assignment_role_cannot_submit_annotation")
        if assignment.status not in {"assigned", "in_progress", "revisit"}:
            raise PermissionError("assignment_not_open")
    else:
        project = ensure_project(session, namespace=namespace, name=project_name)
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
    if disposition not in {"submitted", "skipped", "revisit", "draft"}:
        raise ValueError("review_disposition must be submitted, skipped, revisit, or draft")
    schema = schema_for_item_type(item.item_type)
    if not schema:
        if namespace == "production" and disposition == "submitted":
            raise ValueError("annotation_schema_not_configured")
        structured_values = _legacy_structured_fields(payload)
        final_label = str(payload.get("final_label") or "").upper()
        if disposition == "submitted" and final_label not in FINAL_LABELS:
            raise ValueError("final_label must be one of: " + ", ".join(sorted(FINAL_LABELS)))
    else:
        raw_fields = payload.get("structured_fields") if isinstance(payload.get("structured_fields"), dict) else None
        schema_field_ids = {field["field_id"] for field in schema.definition.get("fields", [])}
        if raw_fields is None:
            raw_fields = {key: payload[key] for key in schema_field_ids if key in payload}
        if "final_label" in schema_field_ids and "final_label" not in raw_fields and payload.get("final_label"):
            raw_fields["final_label"] = str(payload.get("final_label") or "").upper()
        try:
            structured_values = validate_annotation_payload(schema, raw_fields, allow_draft=disposition in {"draft", "skipped", "revisit"})
        except SchemaValidationError:
            raise
        final_label = str(structured_values.get("final_label") or payload.get("final_label") or "").upper()
        if disposition == "submitted" and not final_label:
            raise ValueError("final_label_required")

    now = utcnow()
    structured = canonical_json({k: v for k, v in structured_values.items() if k != "final_label"})
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
    if schema:
        annotation.schema_id = schema.schema_id
        annotation.schema_version = schema.version
        annotation.schema_hash = schema.sha256
        annotation.instructions_version = schema.instructions_version
        annotation.instructions_hash = schema.instructions_hash
    annotation.notes = str(payload.get("notes") or "")
    annotation.review_disposition = disposition
    annotation.uncertainty_reason = str(payload.get("uncertainty_reason") or "")
    annotation.status = status
    annotation.client_submission_id = client_submission_id
    annotation.updated_at = now
    if status == "submitted":
        annotation.submitted_at = now
    if assignment:
        assignment.status = {"submitted": "submitted", "skipped": "skipped", "revisit": "revisit", "draft": "in_progress"}[disposition]
        if assignment.status in {"submitted", "skipped", "revisit"}:
            assignment.completed_at = now
        elif not assignment.started_at:
            assignment.started_at = now
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
    write_audit_event(
        session,
        action=action,
        object_type="annotation",
        object_id=annotation.annotation_id,
        actor=identity,
        project_id=project.project_id,
        review_item_id=review_item_id,
        metadata={"assignment_id": assignment_id, "disposition": disposition, "revision": annotation.revision, "schema_id": annotation.schema_id, "schema_hash": annotation.schema_hash},
        request_id=request_id,
        ip_hash=ip_hash,
        session_hash=session_hash,
    )
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
