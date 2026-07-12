"""Owner-only overview and identity helpers."""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from code_engine.system_b.explorer.auth import generate_invite_code, hash_password, validate_display_name, validate_username
from code_engine.system_b.persistence.models import (
    Adjudication,
    Annotation,
    Assignment,
    AssignmentBatch,
    AuditEvent,
    EvaluationProject,
    GoldRecord,
    Invite,
    InviteUsageEvent,
    MetricResult,
    MetricRun,
    ReviewItem,
    SystemSetting,
    User,
    UserOnboardingAcknowledgement,
    utcnow,
)
from code_engine.system_b.annotation_schemas import schema_for_item_type
from code_engine.system_b.persistence.services.auth_service import create_invite, issue_password_reset
from code_engine.system_b.persistence.services.agreement_service import project_disagreements
from code_engine.system_b.persistence.services.audit_service import write_audit_event


def validate_single_owner(session: Session) -> dict:
    owners = session.execute(select(User).where(User.role == "owner", User.enabled == True)).scalars().all()  # noqa: E712
    configured = session.get(SystemSetting, "owner_user_id")
    if configured:
        matching = [x for x in owners if x.user_id == configured.value]
        return {"ok": len(matching) == 1, "owner_count": len(owners), "owner_user_id": configured.value}
    return {"ok": len(owners) == 1, "owner_count": len(owners), "owner_user_id": owners[0].user_id if len(owners) == 1 else None}


def owner_overview(session: Session) -> dict:
    total_users = session.execute(select(func.count()).select_from(User)).scalar() or 0
    active_reviewers = session.execute(select(func.count()).select_from(User).where(User.enabled == True, User.role == "reviewer")).scalar() or 0  # noqa: E712
    annotations = session.execute(select(Annotation)).scalars().all()
    by_namespace: dict[str, int] = {}
    for row in annotations:
        by_namespace[row.namespace] = by_namespace.get(row.namespace, 0) + 1
    assignments_total = session.execute(select(func.count()).select_from(Assignment)).scalar() or 0
    frozen_gold = session.execute(select(func.count()).select_from(GoldRecord).where(GoldRecord.status == "frozen")).scalar() or 0
    active_invites = session.execute(select(func.count()).select_from(Invite).where(Invite.enabled == True)).scalar() or 0  # noqa: E712
    disabled_users = session.execute(select(func.count()).select_from(User).where(User.enabled == False)).scalar() or 0  # noqa: E712
    never_logged = session.execute(select(func.count()).select_from(User).where(User.last_login_at == None)).scalar() or 0  # noqa: E711
    pending_first = session.execute(select(func.count()).select_from(User).where(User.must_change_password == True)).scalar() or 0  # noqa: E712
    review_items = session.execute(select(func.count()).select_from(ReviewItem)).scalar() or 0
    audit_events = session.execute(select(func.count()).select_from(AuditEvent)).scalar() or 0
    owner_state = validate_single_owner(session)
    warnings = []
    if not owner_state["ok"]:
        warnings.append({"code": "owner_configuration_invalid", "owner_count": owner_state["owner_count"]})
    if by_namespace.get("test", 0) and by_namespace.get("production", 0):
        warnings.append({"code": "test_and_production_annotations_present", "severity": "info"})
    for project in session.execute(select(EvaluationProject)).scalars().all():
        if "pilot" in project.name.casefold() and project.namespace == "production":
            warnings.append({"code": "pilot_named_project_in_production_namespace", "severity": "high", "project_id": project.project_id})
    return {
        "formal_user_count": total_users,
        "active_reviewer_count": active_reviewers,
        "active_users": total_users - disabled_users,
        "disabled_users": disabled_users,
        "never_logged_in": never_logged,
        "pending_first_login": pending_first,
        "active_invites": active_invites,
        "annotations_by_namespace": by_namespace,
        "production_annotations": by_namespace.get("production", 0),
        "pilot_annotations": by_namespace.get("pilot", 0),
        "test_annotations": by_namespace.get("test", 0),
        "calibration_annotations": by_namespace.get("calibration", 0),
        "assignment_count": assignments_total,
        "review_item_count": review_items,
        "frozen_gold_count": frozen_gold,
        "audit_event_count": audit_events,
        "waiting_second_reviewer_count": None,
        "disagreement_count": None,
        "waiting_adjudication_count": None,
        "data_quality_warnings": warnings,
        "owner_state": owner_state,
    }


def owner_projects(session: Session) -> dict:
    rows = session.execute(select(EvaluationProject).order_by(EvaluationProject.created_at.desc(), EvaluationProject.name)).scalars().all()
    items = []
    for project in rows:
        assignments = session.execute(select(func.count()).select_from(Assignment).where(Assignment.project_id == project.project_id)).scalar() or 0
        unique_items = session.execute(select(func.count(func.distinct(Assignment.review_item_id))).where(Assignment.project_id == project.project_id)).scalar() or 0
        unique_cases = session.execute(
            select(func.count(func.distinct(ReviewItem.case_id)))
            .join(Assignment, Assignment.review_item_id == ReviewItem.review_item_id)
            .where(Assignment.project_id == project.project_id)
        ).scalar() or 0
        frozen = session.execute(select(func.max(GoldRecord.gold_dataset_version)).where(GoldRecord.project_id == project.project_id, GoldRecord.status == "frozen")).scalar()
        items.append({
            "project_id": project.project_id,
            "name": project.name,
            "description": project.description,
            "namespace": project.namespace,
            "status": project.status,
            "created_at": project.created_at.isoformat() if project.created_at else "",
            "assignment_count": assignments,
            "unique_review_items": unique_items,
            "unique_cases": unique_cases,
            "gold_dataset_version": frozen,
        })
    return {"items": items, "total": len(items)}


def owner_system_state(session: Session, *, database_path: str = "data/code_atlas.db", schema_head: str | None = None) -> dict:
    owner_state = validate_single_owner(session)
    owner = session.get(User, owner_state.get("owner_user_id")) if owner_state.get("owner_user_id") else None
    projects = owner_projects(session)["items"]
    review_items_by_namespace = [
        {"namespace": ns, "review_items": count, "unique_cases": cases}
        for ns, count, cases in session.execute(select(ReviewItem.namespace, func.count(), func.count(func.distinct(ReviewItem.case_id))).group_by(ReviewItem.namespace)).all()
    ]
    review_items_by_project = []
    for project_id, name, namespace, item_type, count, cases in session.execute(
        select(EvaluationProject.project_id, EvaluationProject.name, EvaluationProject.namespace, ReviewItem.item_type, func.count(func.distinct(ReviewItem.review_item_id)), func.count(func.distinct(ReviewItem.case_id)))
        .join(Assignment, Assignment.project_id == EvaluationProject.project_id)
        .join(ReviewItem, ReviewItem.review_item_id == Assignment.review_item_id)
        .group_by(EvaluationProject.project_id, ReviewItem.item_type)
    ).all():
        review_items_by_project.append({"project_id": project_id, "project_name": name, "namespace": namespace, "item_type": item_type, "review_items": count, "unique_cases": cases})
    assignment_rows = []
    for project_id, role, status, count, items, cases in session.execute(
        select(Assignment.project_id, Assignment.assignment_role, Assignment.status, func.count(), func.count(func.distinct(Assignment.review_item_id)), func.count(func.distinct(ReviewItem.case_id)))
        .join(ReviewItem, ReviewItem.review_item_id == Assignment.review_item_id)
        .group_by(Assignment.project_id, Assignment.assignment_role, Assignment.status)
    ).all():
        assignment_rows.append({"project_id": project_id, "assignment_role": role, "status": status, "assignments": count, "unique_review_items": items, "unique_cases": cases})
    annotation_rows = []
    for namespace, disposition, count, items, cases in session.execute(
        select(Annotation.namespace, Annotation.review_disposition, func.count(), func.count(func.distinct(Annotation.review_item_id)), func.count(func.distinct(ReviewItem.case_id)))
        .join(ReviewItem, ReviewItem.review_item_id == Annotation.review_item_id, isouter=True)
        .group_by(Annotation.namespace, Annotation.review_disposition)
    ).all():
        annotation_rows.append({"namespace": namespace, "review_disposition": disposition, "annotations": count, "unique_review_items": items, "unique_cases": cases})
    gold_rows = [{"project_id": p, "status": s, "gold_version": gv, "gold_dataset_version": gdv, "count": c} for p, s, gv, gdv, c in session.execute(select(GoldRecord.project_id, GoldRecord.status, GoldRecord.gold_version, GoldRecord.gold_dataset_version, func.count()).group_by(GoldRecord.project_id, GoldRecord.status, GoldRecord.gold_version, GoldRecord.gold_dataset_version)).all()]
    metric_runs = [{"project_id": p, "status": s, "count": c} for p, s, c in session.execute(select(MetricRun.project_id, MetricRun.status, func.count()).group_by(MetricRun.project_id, MetricRun.status)).all()]
    warnings = owner_quality_alerts(session)["items"]
    pilot_projects = [p for p in projects if p["namespace"] == "pilot"]
    for project in pilot_projects:
        if project["assignment_count"] and project["unique_cases"] < 3:
            warnings.append({"code": "pilot_assignments_cover_fewer_than_three_cases", "severity": "medium", "project_id": project["project_id"], "unique_cases": project["unique_cases"], "explanation": "Pilot assignments should cover at least 3 unique cases for internal smoke coverage."})
    return {
        "database_path": database_path,
        "schema_head": schema_head or "unknown",
        "owner": serialize_user(session, owner) if owner else None,
        "owner_state": owner_state,
        "user_counts_by_role": [{"role": role, "enabled": bool(enabled), "count": count} for role, enabled, count in session.execute(select(User.role, User.enabled, func.count()).group_by(User.role, User.enabled)).all()],
        "projects": projects,
        "review_items_by_namespace": review_items_by_namespace,
        "review_items_by_project": review_items_by_project,
        "assignment_counts": assignment_rows,
        "annotation_counts": annotation_rows,
        "gold_counts": gold_rows,
        "metric_run_counts": metric_runs,
        "metric_result_count": session.execute(select(func.count()).select_from(MetricResult)).scalar() or 0,
        "adjudication_count": session.execute(select(func.count()).select_from(Adjudication)).scalar() or 0,
        "assignment_batch_count": session.execute(select(func.count()).select_from(AssignmentBatch)).scalar() or 0,
        "audit_event_count": session.execute(select(func.count()).select_from(AuditEvent)).scalar() or 0,
        "active_invite_count": session.execute(select(func.count()).select_from(Invite).where(Invite.enabled == True)).scalar() or 0,  # noqa: E712
        "quality_warnings": warnings,
    }


def owner_pilot_preview(
    session: Session,
    *,
    namespace: str = "pilot",
    case_ids: list[str] | None = None,
    item_types: list[str] | None = None,
    source_scope: str | None = None,
    item_ids: list[str] | None = None,
    primary_reviewer_user_id: str | None = None,
    secondary_reviewer_user_id: str | None = None,
    adjudicator_user_id: str | None = None,
    batch_size: int = 20,
    random_seed: str | int | None = None,
) -> dict:
    if namespace != "pilot":
        raise ValueError("pilot_wizard_namespace_is_fixed_to_pilot")
    query = select(ReviewItem).where(ReviewItem.namespace == "pilot")
    if case_ids:
        query = query.where(ReviewItem.case_id.in_(sorted(set(case_ids))))
    if item_types:
        query = query.where(ReviewItem.item_type.in_(sorted(set(item_types))))
    if source_scope:
        query = query.where(ReviewItem.source_scope == source_scope)
    if item_ids:
        query = query.where(ReviewItem.review_item_id.in_(sorted(set(item_ids))))
    rows = session.execute(query.order_by(ReviewItem.case_id, ReviewItem.item_type, ReviewItem.review_item_id)).scalars().all()
    schema_distribution: dict[str, int] = {}
    missing_schemas: dict[str, int] = {}
    by_case: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for item in rows:
        by_case[item.case_id] = by_case.get(item.case_id, 0) + 1
        by_source[item.source_scope or "当前数据未提供"] = by_source.get(item.source_scope or "当前数据未提供", 0) + 1
        schema = schema_for_item_type(item.item_type)
        if schema:
            schema_distribution[schema.schema_id] = schema_distribution.get(schema.schema_id, 0) + 1
        else:
            missing_schemas[item.item_type] = missing_schemas.get(item.item_type, 0) + 1
    warnings = []
    errors = []
    if primary_reviewer_user_id and secondary_reviewer_user_id and primary_reviewer_user_id == secondary_reviewer_user_id:
        errors.append({"code": "primary_secondary_must_differ"})
    for label, user_id in (("primary", primary_reviewer_user_id), ("secondary", secondary_reviewer_user_id), ("adjudicator", adjudicator_user_id)):
        if not user_id:
            continue
        user = session.get(User, user_id)
        if not user or not user.enabled:
            errors.append({"code": "user_not_available", "role": label, "user_id": user_id})
        elif label in {"primary", "secondary"} and user.role not in {"reviewer", "pharma", "developer"}:
            errors.append({"code": "reviewer_role_mismatch", "role": label, "user_id": user_id, "actual_role": user.role})
        elif label == "adjudicator" and user.role not in {"reviewer", "developer", "admin"}:
            errors.append({"code": "adjudicator_role_mismatch", "user_id": user_id, "actual_role": user.role})
        if user and not session.execute(select(func.count()).select_from(UserOnboardingAcknowledgement).where(UserOnboardingAcknowledgement.user_id == user.user_id)).scalar():
            warnings.append({"code": "onboarding_not_yet_acknowledged", "role": label, "user_id": user.user_id})
    if missing_schemas:
        errors.append({"code": "formal_schema_missing", "item_types": missing_schemas})
    if not rows:
        errors.append({"code": "no_review_items_selected"})
    duplicate_assignments = 0
    if rows and primary_reviewer_user_id and secondary_reviewer_user_id:
        selected = [r.review_item_id for r in rows]
        duplicate_assignments = session.execute(
            select(func.count()).select_from(Assignment).where(Assignment.review_item_id.in_(selected), Assignment.reviewer_user_id.in_([primary_reviewer_user_id, secondary_reviewer_user_id]))
        ).scalar() or 0
        if duplicate_assignments:
            warnings.append({"code": "duplicate_assignments_existing", "count": duplicate_assignments})
    return {
        "namespace": "pilot",
        "unique_cases": len(by_case),
        "unique_review_items": len(rows),
        "review_item_count_is_not_case_count": True,
        "item_count_by_case": by_case,
        "item_count_by_schema": schema_distribution,
        "source_distribution": by_source,
        "primary_assignments": len(rows) if primary_reviewer_user_id else None,
        "secondary_assignments": len(rows) if secondary_reviewer_user_id else None,
        "adjudication_assignments": len(rows) if adjudicator_user_id else None,
        "expected_batches": ((len(rows) + max(batch_size, 1) - 1) // max(batch_size, 1)) if rows else 0,
        "duplicate_assignments": duplicate_assignments,
        "assignment_order": "case_id,item_type,review_item_id",
        "random_seed": str(random_seed or ""),
        "warnings": warnings,
        "errors": errors,
        "blocked": bool(errors),
        "selected_review_item_ids": [r.review_item_id for r in rows],
    }


def owner_people(session: Session) -> dict:
    users = session.execute(select(User).order_by(User.username)).scalars().all()
    rows = []
    for user in users:
        assignments = session.execute(select(func.count()).select_from(Assignment).where(Assignment.reviewer_user_id == user.user_id)).scalar() or 0
        annotations = session.execute(select(Annotation).where(Annotation.reviewer_user_id == user.user_id)).scalars().all()
        dispositions: dict[str, int] = {}
        namespaces: dict[str, int] = {}
        for row in annotations:
            dispositions[row.review_disposition] = dispositions.get(row.review_disposition, 0) + 1
            namespaces[row.namespace] = namespaces.get(row.namespace, 0) + 1
        rows.append({
            "user_id": user.user_id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "enabled": user.enabled,
            "must_change_password": user.must_change_password,
            "status": user_status(user),
            "assigned": assignments,
            "submitted": dispositions.get("submitted", 0),
            "skipped": dispositions.get("skipped", 0),
            "revisit": dispositions.get("revisit", 0),
            "namespaces": namespaces,
            "last_activity": max([a.updated_at for a in annotations], default=user.last_login_at or user.updated_at).isoformat() if (annotations or user.last_login_at or user.updated_at) else "",
        })
    return {"items": rows, "total": len(rows)}


def user_status(user: User) -> str:
    if not user.enabled:
        return "disabled"
    if user.locked_until and user.locked_until > utcnow():
        return "locked"
    if user.must_change_password or not user.last_login_at:
        return "pending_first_login"
    return "active"


def serialize_user(session: Session, user: User) -> dict:
    annotations = session.execute(select(Annotation).where(Annotation.reviewer_user_id == user.user_id)).scalars().all()
    assignments = session.execute(select(Assignment).where(Assignment.reviewer_user_id == user.user_id)).scalars().all()
    audit_count = session.execute(select(func.count()).select_from(AuditEvent).where(AuditEvent.actor_user_id == user.user_id)).scalar() or 0
    return {
        "user_id": user.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "enabled": user.enabled,
        "status": user_status(user),
        "must_change_password": user.must_change_password,
        "session_version": user.session_version,
        "created_at": user.created_at.isoformat() if user.created_at else "",
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else "",
        "last_activity_at": max([a.updated_at for a in annotations], default=user.last_login_at or user.updated_at).isoformat() if (annotations or user.last_login_at or user.updated_at) else "",
        "assigned_count": len(assignments),
        "submitted_count": sum(1 for a in annotations if a.review_disposition == "submitted"),
        "pilot_annotation_count": sum(1 for a in annotations if a.namespace == "pilot"),
        "production_annotation_count": sum(1 for a in annotations if a.namespace == "production"),
        "open_assignment_count": sum(1 for a in assignments if a.status in {"assigned", "in_progress", "revisit"}),
        "invite_source": user.invite_source_id,
        "audit_event_count": audit_count,
    }


def owner_users(session: Session, *, q: str | None = None, role: str | None = None, enabled: str | None = None) -> dict:
    query = select(User).order_by(User.username)
    if q:
        term = f"%{q.casefold()}%"
        query = query.where((User.username.ilike(term)) | (User.display_name.ilike(term)) | (User.user_id.ilike(term)))
    if role:
        query = query.where(User.role == role)
    if enabled in {"true", "false"}:
        query = query.where(User.enabled == (enabled == "true"))
    rows = session.execute(query).scalars().all()
    return {"items": [serialize_user(session, user) for user in rows], "total": len(rows)}


def owner_create_user(session: Session, *, owner: dict, username: str, display_name: str, role: str, temporary_password: bool = True) -> dict:
    if role == "owner" or role not in {"admin", "developer", "reviewer", "pharma"}:
        raise ValueError("invalid_role")
    username = validate_username(username)
    display_name = validate_display_name(display_name)
    if session.execute(select(User).where(User.username == username)).scalar_one_or_none():
        raise ValueError("user_create_failed")
    password = secrets.token_urlsafe(18)
    user = User(username=username, display_name=display_name, role=role, enabled=True, password_hash=hash_password(password), must_change_password=temporary_password, session_version=1)
    session.add(user)
    session.flush()
    write_audit_event(session, action="user_created_by_owner", object_type="user", object_id=user.user_id, actor=owner, metadata={"target_user_id": user.user_id, "role": role, "temporary_password": temporary_password})
    return {"user": serialize_user(session, user), "temporary_password": password, "one_time_notice": "This temporary password is shown once only."}


def owner_update_user(session: Session, *, owner: dict, user_id: str, display_name: str | None = None, enabled: bool | None = None) -> dict:
    user = session.get(User, user_id)
    if not user:
        raise KeyError("user_not_found")
    if display_name is not None and display_name != user.display_name:
        old = user.display_name
        user.display_name = validate_display_name(display_name)
        write_audit_event(session, action="user_display_name_changed", object_type="user", object_id=user.user_id, actor=owner, metadata={"target_user_id": user.user_id, "old_display_name": old})
    if enabled is not None and enabled != user.enabled:
        if user.role == "owner" and not enabled:
            raise ValueError("cannot_disable_owner")
        user.enabled = enabled
        user.session_version += 1
        write_audit_event(session, action="user_enabled" if enabled else "user_disabled", object_type="user", object_id=user.user_id, actor=owner, metadata={"target_user_id": user.user_id, "open_assignment_count": serialize_user(session, user)["open_assignment_count"]})
    return serialize_user(session, user)


def owner_change_role(session: Session, *, owner: dict, user_id: str, role: str) -> dict:
    user = session.get(User, user_id)
    if not user:
        raise KeyError("user_not_found")
    if role == "owner" or role not in {"admin", "developer", "reviewer", "pharma"}:
        raise ValueError("invalid_role")
    if user.role == "owner":
        raise ValueError("cannot_change_owner_role")
    old = user.role
    user.role = role
    user.session_version += 1
    impact = serialize_user(session, user)
    write_audit_event(session, action="user_role_changed", object_type="user", object_id=user.user_id, actor=owner, metadata={"target_user_id": user.user_id, "old_role": old, "new_role": role, "open_assignment_count": impact["open_assignment_count"]})
    return impact


def owner_revoke_sessions(session: Session, *, owner: dict, user_id: str) -> dict:
    user = session.get(User, user_id)
    if not user:
        raise KeyError("user_not_found")
    user.session_version += 1
    write_audit_event(session, action="sessions_revoked", object_type="user", object_id=user.user_id, actor=owner, metadata={"target_user_id": user.user_id})
    return {"user_id": user.user_id, "session_version": user.session_version}


def owner_issue_temporary_password(session: Session, *, owner: dict, user_id: str) -> dict:
    user = session.get(User, user_id)
    if not user:
        raise KeyError("user_not_found")
    if user.role == "owner" and user.user_id != owner.get("user_id"):
        raise ValueError("cannot_reset_other_owner")
    password = secrets.token_urlsafe(18)
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.session_version += 1
    write_audit_event(session, action="password_reset_issued", object_type="user", object_id=user.user_id, actor=owner, metadata={"target_user_id": user.user_id, "method": "temporary_password"})
    return {"user_id": user.user_id, "temporary_password": password, "one_time_notice": "This temporary password is shown once only."}


def owner_issue_reset_link(session: Session, *, owner: dict, user_id: str, base_url: str = "") -> dict:
    user = session.get(User, user_id)
    if not user:
        raise KeyError("user_not_found")
    result = issue_password_reset(session, target_user=user, owner=owner)
    link = (base_url.rstrip("/") if base_url else "") + "/password-reset/" + result["token"]
    return {"user_id": user.user_id, "reset_link": link, "token": result["token"], "expires_at": result["expires_at"], "one_time_notice": "This reset token is shown once only."}


def invite_status(invite: Invite) -> str:
    now = utcnow()
    if not invite.enabled:
        return "disabled"
    if invite.expires_at and now > invite.expires_at:
        return "expired"
    if invite.uses >= invite.max_uses:
        return "exhausted"
    return "active"


def serialize_invite(invite: Invite) -> dict:
    return {
        "invite_id": invite.invite_id,
        "label": invite.label,
        "role": invite.role,
        "status": invite_status(invite),
        "enabled": invite.enabled,
        "created_by_user_id": invite.created_by_user_id,
        "created_at": invite.created_at.isoformat() if invite.created_at else "",
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else "",
        "max_uses": invite.max_uses,
        "uses": invite.uses,
        "remaining_uses": max(0, invite.max_uses - invite.uses),
        "project_scope": json.loads(invite.project_scope_json or "{}"),
        "last_used_at": invite.last_used_at.isoformat() if invite.last_used_at else "",
        "notes": invite.notes,
    }


def owner_invites(session: Session) -> dict:
    rows = session.execute(select(Invite).order_by(Invite.created_at.desc())).scalars().all()
    return {"items": [serialize_invite(row) for row in rows], "total": len(rows)}


def owner_create_invite(session: Session, *, owner: dict, label: str, role: str, max_uses: int, expires_at: datetime | None = None, project_scope: dict | None = None, notes: str = "", base_url: str = "") -> dict:
    code = generate_invite_code()
    invite = create_invite(session, code=code, label=label, role=role, max_uses=max_uses, expires_at=expires_at, created_by=owner, project_scope=project_scope, notes=notes)
    link = (base_url.rstrip("/") if base_url else "") + "/register?invite=" + code
    return {"invite": serialize_invite(invite), "invite_code": code, "registration_link": link, "one_time_notice": "This invite code is shown once only."}


def owner_set_invite_enabled(session: Session, *, owner: dict, invite_id: str, enabled: bool) -> dict:
    invite = session.get(Invite, invite_id)
    if not invite:
        raise KeyError("invite_not_found")
    if enabled and invite_status(invite) in {"expired", "exhausted"}:
        raise ValueError("invite_not_reenableable")
    invite.enabled = enabled
    write_audit_event(session, action="invite_enabled" if enabled else "invite_disabled", object_type="invite", object_id=invite.invite_id, actor=owner, metadata={"invite_id": invite.invite_id})
    return serialize_invite(invite)


def owner_invite_usage(session: Session, *, invite_id: str) -> dict:
    rows = session.execute(select(InviteUsageEvent).where(InviteUsageEvent.invite_id == invite_id).order_by(InviteUsageEvent.used_at.desc())).scalars().all()
    return {"items": [{"user_id": r.user_id, "used_at": r.used_at.isoformat() if r.used_at else "", "request_id": r.request_id} for r in rows], "total": len(rows)}


def correct_empty_pilot_project_namespace(session: Session, *, owner: dict, project_id: str) -> dict:
    project = session.get(EvaluationProject, project_id)
    if not project:
        raise KeyError("project_not_found")
    if project.namespace != "production" or "pilot" not in project.name.casefold():
        return {"changed": False, "project_id": project_id, "namespace": project.namespace}
    annotations = session.execute(select(func.count()).select_from(Annotation).where(Annotation.project_id == project_id)).scalar() or 0
    if annotations:
        raise ValueError("project_has_annotations_create_new_pilot")
    old = project.namespace
    project.namespace = "pilot"
    write_audit_event(session, action="project_namespace_corrected", object_type="evaluation_project", object_id=project.project_id, actor=owner, project_id=project.project_id, metadata={"old_namespace": old, "new_namespace": "pilot", "reason": "empty_pilot_readiness_project"})
    return {"changed": True, "project_id": project_id, "old_namespace": old, "namespace": project.namespace}


def owner_quality_alerts(session: Session) -> dict:
    alerts = []
    production_unattributed = session.execute(select(func.count()).select_from(Annotation).where(Annotation.namespace == "production", Annotation.reviewer_user_id == None)).scalar() or 0  # noqa: E711
    if production_unattributed:
        alerts.append({"code": "production_annotation_without_user", "severity": "high", "count": production_unattributed})
    duplicate_role_rows = session.execute(select(Assignment.project_id, Assignment.review_item_id, Assignment.reviewer_user_id, func.count()).where(Assignment.assignment_role.in_(["primary", "secondary"])).group_by(Assignment.project_id, Assignment.review_item_id, Assignment.reviewer_user_id).having(func.count() > 1)).all()
    if duplicate_role_rows:
        alerts.append({"code": "same_user_primary_secondary", "severity": "high", "count": len(duplicate_role_rows)})
    for project in session.execute(select(EvaluationProject)).scalars().all():
        if "pilot" in project.name.casefold() and project.namespace == "production":
            alerts.append({"code": "namespace_contamination_pilot_project_in_production", "severity": "high", "project_id": project.project_id})
    disabled_open = session.execute(select(Assignment, User).join(User, Assignment.reviewer_user_id == User.user_id).where(User.enabled == False, Assignment.status.in_(["assigned", "in_progress", "revisit"]))).all()  # noqa: E712
    if disabled_open:
        alerts.append({"code": "disabled_user_still_has_open_assignments", "severity": "medium", "count": len(disabled_open)})
    incompatible = session.execute(select(Assignment, User).join(User, Assignment.reviewer_user_id == User.user_id).where(Assignment.assignment_role.in_(["primary", "secondary"]), User.role.notin_(["reviewer", "pharma", "developer", "owner"]))).all()
    if incompatible:
        alerts.append({"code": "account_role_incompatible_with_assignment", "severity": "medium", "count": len(incompatible)})
    for invite in session.execute(select(Invite)).scalars().all():
        status = invite_status(invite)
        if status in {"expired", "exhausted"}:
            alerts.append({"code": f"invite_{status}", "severity": "info", "invite_id": invite.invite_id, "label": invite.label})
    for project_id in sorted({row.project_id for row in session.execute(select(Assignment.project_id)).all()}):
        statuses = project_disagreements(session, project_id=project_id)
        unresolved = sum(1 for row in statuses if row.get("status") == "needs_adjudication")
        if unresolved:
            alerts.append({"code": "unresolved_disagreement", "severity": "medium", "project_id": project_id, "count": unresolved})
    if not session.execute(select(GoldRecord).where(GoldRecord.status == "frozen")).first():
        alerts.append({"code": "gold_not_frozen", "severity": "info"})
    return {"items": alerts, "total": len(alerts), "note": "Alerts indicate review risk and do not automatically imply misconduct."}


def owner_audit_events(session: Session, *, actor: str | None = None, action: str | None = None, project_id: str | None = None, limit: int = 200) -> dict:
    query = select(AuditEvent).order_by(AuditEvent.occurred_at.desc()).limit(min(max(limit, 1), 1000))
    if actor:
        query = query.where(AuditEvent.actor_username_snapshot == actor)
    if action:
        query = query.where(AuditEvent.action == action)
    if project_id:
        query = query.where(AuditEvent.project_id == project_id)
    rows = session.execute(query).scalars().all()
    return {"items": [{
        "event_id": row.event_id,
        "actor_user_id": row.actor_user_id,
        "actor_username_snapshot": row.actor_username_snapshot,
        "action": row.action,
        "object_type": row.object_type,
        "object_id": row.object_id,
        "project_id": row.project_id,
        "case_id": row.case_id,
        "review_item_id": row.review_item_id,
        "metadata_json": row.metadata_json,
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else "",
    } for row in rows], "total": len(rows)}
