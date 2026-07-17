"""Pilot operations available to Admin without Owner governance authority."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from code_engine.system_b.authorization import ADMIN_CREATABLE_ROLES
from code_engine.system_b.persistence.models import Assignment, EvaluationProject, Invite, ReviewItem, User
from code_engine.system_b.persistence.services.owner_service import (
    owner_change_role,
    owner_create_invite,
    owner_create_user,
    owner_invites,
    owner_pilot_preview,
    owner_projects,
    owner_quality_alerts,
    owner_set_invite_enabled,
    owner_update_user,
    serialize_user,
)

PROTECTED_ROLES = {"owner", "admin", "developer"}


def _target(session: Session, user_id: str) -> User:
    user = session.get(User, user_id)
    if not user:
        raise KeyError("user_not_found")
    if user.role in PROTECTED_ROLES:
        raise PermissionError("admin_cannot_modify_privileged_user")
    return user


def admin_overview(session: Session) -> dict:
    users = session.execute(select(User)).scalars().all()
    pilots = session.execute(select(EvaluationProject).where(EvaluationProject.namespace == "pilot")).scalars().all()
    open_statuses = {"assigned", "in_progress", "revisit"}
    assignments = session.execute(select(Assignment)).scalars().all()
    return {
        "active_users": sum(user.enabled for user in users),
        "disabled_users": sum(not user.enabled for user in users),
        "pending_first_login": sum(bool(user.must_change_password) for user in users if user.enabled),
        "never_logged_in": sum(user.last_login_at is None for user in users if user.enabled),
        "pilot_project_count": len(pilots),
        "assignment_count": len(assignments),
        "open_assignment_count": sum(row.status in open_statuses for row in assignments),
        "second_review_backlog": session.execute(select(func.count()).select_from(Assignment).where(Assignment.assignment_role == "secondary", Assignment.status.in_(sorted(open_statuses)))).scalar_one(),
        "review_item_count": session.execute(select(func.count()).select_from(ReviewItem)).scalar_one(),
        "notice": "Admin may operate Pilot users and assignments, but cannot access Owner governance, blind answers, Production Gold, metrics, audit secrets, or the Developer Console.",
    }


def admin_users(session: Session) -> dict:
    rows = session.execute(select(User).order_by(User.username)).scalars().all()
    items = []
    for user in rows:
        value = serialize_user(session, user)
        value["admin_mutable"] = user.role not in PROTECTED_ROLES
        items.append(value)
    return {"items": items, "total": len(items), "creatable_roles": list(ADMIN_CREATABLE_ROLES)}


def admin_create_user(session: Session, *, admin: dict, username: str, display_name: str, role: str) -> dict:
    if role not in ADMIN_CREATABLE_ROLES:
        raise PermissionError("admin_role_target_forbidden")
    return owner_create_user(session, owner=admin, username=username, display_name=display_name, role=role, temporary_password=True)


def admin_update_user(session: Session, *, admin: dict, user_id: str, enabled: bool) -> dict:
    _target(session, user_id)
    return owner_update_user(session, owner=admin, user_id=user_id, enabled=enabled)


def admin_change_role(session: Session, *, admin: dict, user_id: str, role: str) -> dict:
    _target(session, user_id)
    if role not in ADMIN_CREATABLE_ROLES:
        raise PermissionError("admin_role_target_forbidden")
    return owner_change_role(session, owner=admin, user_id=user_id, role=role)


def admin_invites(session: Session) -> dict:
    result = owner_invites(session)
    result["items"] = [row for row in result["items"] if row.get("role") in ADMIN_CREATABLE_ROLES]
    result["total"] = len(result["items"])
    return result


def admin_create_invite(session: Session, *, admin: dict, label: str, role: str, max_uses: int, project_scope: dict, notes: str, base_url: str) -> dict:
    if role not in ADMIN_CREATABLE_ROLES:
        raise PermissionError("admin_role_target_forbidden")
    return owner_create_invite(session, owner=admin, label=label, role=role, max_uses=max_uses, project_scope=project_scope, notes=notes, base_url=base_url)


def admin_set_invite_enabled(session: Session, *, admin: dict, invite_id: str, enabled: bool) -> dict:
    invite = session.get(Invite, invite_id)
    if not invite:
        raise KeyError("invite_not_found")
    if invite.role not in ADMIN_CREATABLE_ROLES:
        raise PermissionError("admin_invite_target_forbidden")
    return owner_set_invite_enabled(session, owner=admin, invite_id=invite_id, enabled=enabled)


def admin_projects(session: Session) -> dict:
    result = owner_projects(session)
    result["items"] = [row for row in result["items"] if row.get("namespace") == "pilot"]
    result["total"] = len(result["items"])
    return result


def admin_pilot_preview(session: Session, **kwargs) -> dict:
    return owner_pilot_preview(session, namespace="pilot", **kwargs)


def admin_quality(session: Session) -> dict:
    # Counts and codes only; no annotation labels or reviewer answers.
    result = owner_quality_alerts(session)
    return {"items": [{key: value for key, value in row.items() if key not in {"annotation", "annotations", "answers"}} for row in result.get("items", [])]}
