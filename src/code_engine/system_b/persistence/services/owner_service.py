"""Owner-only overview and identity helpers."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from code_engine.system_b.persistence.models import (
    Annotation,
    Assignment,
    AuditEvent,
    GoldRecord,
    ReviewItem,
    SystemSetting,
    User,
)
from code_engine.system_b.persistence.services.agreement_service import project_disagreements


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
    review_items = session.execute(select(func.count()).select_from(ReviewItem)).scalar() or 0
    audit_events = session.execute(select(func.count()).select_from(AuditEvent)).scalar() or 0
    owner_state = validate_single_owner(session)
    warnings = []
    if not owner_state["ok"]:
        warnings.append({"code": "owner_configuration_invalid", "owner_count": owner_state["owner_count"]})
    if by_namespace.get("test", 0) and by_namespace.get("production", 0):
        warnings.append({"code": "test_and_production_annotations_present", "severity": "info"})
    return {
        "formal_user_count": total_users,
        "active_reviewer_count": active_reviewers,
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
            "assigned": assignments,
            "submitted": dispositions.get("submitted", 0),
            "skipped": dispositions.get("skipped", 0),
            "revisit": dispositions.get("revisit", 0),
            "namespaces": namespaces,
            "last_activity": max([a.updated_at for a in annotations], default=user.last_login_at or user.updated_at).isoformat() if (annotations or user.last_login_at or user.updated_at) else "",
        })
    return {"items": rows, "total": len(rows)}


def owner_quality_alerts(session: Session) -> dict:
    alerts = []
    production_unattributed = session.execute(select(func.count()).select_from(Annotation).where(Annotation.namespace == "production", Annotation.reviewer_user_id == None)).scalar() or 0  # noqa: E711
    if production_unattributed:
        alerts.append({"code": "production_annotation_without_user", "severity": "high", "count": production_unattributed})
    duplicate_role_rows = session.execute(select(Assignment.project_id, Assignment.review_item_id, Assignment.reviewer_user_id, func.count()).where(Assignment.assignment_role.in_(["primary", "secondary"])).group_by(Assignment.project_id, Assignment.review_item_id, Assignment.reviewer_user_id).having(func.count() > 1)).all()
    if duplicate_role_rows:
        alerts.append({"code": "same_user_primary_secondary", "severity": "high", "count": len(duplicate_role_rows)})
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
