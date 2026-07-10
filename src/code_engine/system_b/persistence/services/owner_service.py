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
