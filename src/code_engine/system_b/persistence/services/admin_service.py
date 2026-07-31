"""Pilot operations available to Admin without Owner governance authority."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from code_engine.system_b.authorization import ADMIN_CREATABLE_ROLES
from code_engine.system_b.persistence.models import Adjudication, Assignment, EvaluationProject, Invite, ReviewItem, User
from code_engine.system_b.persistence.services.owner_service import (
    owner_change_role,
    owner_create_invite,
    owner_create_user,
    owner_invites,
    owner_issue_reset_link,
    owner_revoke_sessions,
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
    active_reviewers = [user for user in users if user.enabled and user.role == "reviewer"]
    active_adjudicators = [user for user in users if user.enabled and user.role == "adjudicator"]
    assigned_user_ids = {row.reviewer_user_id for row in assignments}
    unstarted_user_ids = {row.reviewer_user_id for row in assignments if row.status == "assigned"}
    waiting_adjudication = session.execute(select(func.count()).select_from(Assignment).where(
        Assignment.assignment_role == "adjudicator", Assignment.status.in_(sorted(open_statuses))
    )).scalar_one()
    blocked_pilots = sum(project.status != "active" for project in pilots)
    return {
        "active_users": sum(user.enabled for user in users),
        "disabled_users": sum(not user.enabled for user in users),
        "pending_first_login": sum(bool(user.must_change_password) for user in users if user.enabled),
        "never_logged_in": sum(user.last_login_at is None for user in users if user.enabled),
        "pending_registration": sum((user.last_login_at is None or user.must_change_password) for user in users if user.enabled),
        "temporary_password_pending": sum(bool(user.must_change_password) for user in users if user.enabled),
        "pilot_project_count": len(pilots),
        "assignment_count": len(assignments),
        "open_assignment_count": sum(row.status in open_statuses for row in assignments),
        "second_review_backlog": session.execute(select(func.count()).select_from(Assignment).where(Assignment.assignment_role == "secondary", Assignment.status.in_(sorted(open_statuses)))).scalar_one(),
        "active_reviewer_count": len(active_reviewers),
        "active_adjudicator_count": len(active_adjudicators),
        "reviewers_without_assignments": sum(user.user_id not in assigned_user_ids for user in active_reviewers),
        "users_with_unstarted_tasks": len(unstarted_user_ids),
        "waiting_adjudication": waiting_adjudication,
        "draft_sampling_batches": 0,
        "blocked_batch_count": blocked_pilots,
        "review_item_count": session.execute(select(func.count()).select_from(ReviewItem)).scalar_one(),
        "notice": "Admin may operate Pilot users and assignments, but cannot access Owner governance, blind answers, Production Gold, metrics, audit secrets, or the Developer Console.",
    }


def admin_users(
    session: Session,
    *,
    q: str | None = None,
    role: str | None = None,
    enabled: str | None = None,
    onboarding: str | None = None,
    has_tasks: str | None = None,
    project_id: str | None = None,
    never_logged_in: str | None = None,
    recent_days: int | None = None,
    sort_by: str | None = None,
    sort_direction: str | None = None,
) -> dict:
    rows = session.execute(select(User).order_by(User.username)).scalars().all()
    items = []
    review_items = {
        row.review_item_id: row
        for row in session.execute(select(ReviewItem)).scalars().all()
    }
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for user in rows:
        value = {
            key: item
            for key, item in serialize_user(session, user).items()
            if key not in {"session_version", "invite_source"}
        }
        value["admin_mutable"] = user.role not in PROTECTED_ROLES
        assignments = session.execute(select(Assignment).where(Assignment.reviewer_user_id == user.user_id)).scalars().all()
        project_ids = sorted({row.project_id for row in assignments})
        projects = [session.get(EvaluationProject, value) for value in project_ids]
        value["active_projects"] = [{"project_id": row.project_id, "name": row.name} for row in projects if row and row.status == "active"]
        value["current_project_names"] = [row["name"] for row in value["active_projects"]]
        value["completed_assignment_count"] = sum(row.status in {"submitted", "completed", "skipped"} for row in assignments)
        value["pending_assignment_count"] = sum(row.status in {"assigned", "in_progress", "revisit"} for row in assignments)
        value["revisit_assignment_count"] = sum(row.status == "revisit" for row in assignments)
        value["adjudication_pending"] = sum(row.assignment_role == "adjudicator" and row.status in {"assigned", "in_progress", "revisit"} for row in assignments)
        value["recent_7_days_completed"] = sum(
            bool(row.completed_at)
            and (row.completed_at.replace(tzinfo=timezone.utc) if row.completed_at.tzinfo is None else row.completed_at) >= recent_cutoff
            for row in assignments
        )
        value["assignment_role_distribution"] = {
            assignment_role: sum(row.assignment_role == assignment_role for row in assignments)
            for assignment_role in ("primary", "secondary", "adjudicator")
        }
        case_distribution: dict[str, int] = {}
        domain_distribution: dict[str, int] = {}
        for assignment in assignments:
            review_item = review_items.get(assignment.review_item_id)
            if not review_item:
                continue
            case_distribution[review_item.case_id] = case_distribution.get(review_item.case_id, 0) + 1
            try:
                payload = json.loads(review_item.payload_json or "{}")
            except (TypeError, json.JSONDecodeError):
                payload = {}
            domain = payload.get("domain_id") or (payload.get("domain_snapshot") or {}).get("domain_id") or "unclassified"
            domain_distribution[domain] = domain_distribution.get(domain, 0) + 1
        value["case_distribution"] = case_distribution
        value["domain_distribution"] = domain_distribution
        value["onboarding_status"] = "temporary_password" if user.must_change_password else ("never_logged_in" if not user.last_login_at else "complete")
        value["account_warning"] = "账号已禁用" if not user.enabled else ("从未登录" if not user.last_login_at else "")
        value["audit_reference"] = f"user:{user.user_id}"
        items.append(value)
    all_items = list(items)
    term = (q or "").casefold().strip()
    if term:
        items = [row for row in items if term in " ".join([
            row["username"], row["display_name"], row["role"], *row["current_project_names"]
        ]).casefold()]
    if role:
        items = [row for row in items if row["role"] == role]
    if enabled in {"true", "false"}:
        items = [row for row in items if row["enabled"] == (enabled == "true")]
    if onboarding:
        items = [row for row in items if row["onboarding_status"] == onboarding]
    if has_tasks in {"true", "false"}:
        items = [row for row in items if bool(row["assigned_count"]) == (has_tasks == "true")]
    if project_id:
        items = [row for row in items if any(project["project_id"] == project_id for project in row["active_projects"])]
    if never_logged_in in {"true", "false"}:
        items = [row for row in items if (not bool(row["last_login_at"])) == (never_logged_in == "true")]
    if recent_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(recent_days)))
        items = [
            row for row in items
            if row["last_activity_at"] and datetime.fromisoformat(row["last_activity_at"]).replace(
                tzinfo=datetime.fromisoformat(row["last_activity_at"]).tzinfo or timezone.utc
            ) >= cutoff
        ]
    sort_keys = {
        "pending": lambda row: row["pending_assignment_count"],
        "completed": lambda row: row["completed_assignment_count"],
        "recent_activity": lambda row: row["last_activity_at"] or "",
        "created_at": lambda row: row["created_at"] or "",
        "username": lambda row: row["username"].casefold(),
    }
    if sort_by in sort_keys:
        items.sort(key=sort_keys[sort_by], reverse=sort_direction == "desc")
    summary = {
        "all": len(rows),
        "enabled": sum(row["enabled"] for row in all_items),
        "pending_registration": sum(row["onboarding_status"] != "complete" for row in all_items),
        "never_logged_in": sum(not row["last_login_at"] for row in all_items),
        "with_tasks": sum(bool(row["pending_assignment_count"]) for row in all_items),
        "reviewers_without_tasks": sum(row["role"] == "reviewer" and not row["pending_assignment_count"] and row["enabled"] for row in all_items),
        "adjudication_pending": sum(bool(row["adjudication_pending"]) for row in all_items),
        "disabled": sum(not row["enabled"] for row in all_items),
    }
    return {"items": items, "total": len(items), "summary": summary, "creatable_roles": list(ADMIN_CREATABLE_ROLES)}


def admin_user_workload(session: Session, *, user_id: str) -> dict:
    user = session.get(User, user_id)
    if not user:
        raise KeyError("user_not_found")
    assignments = session.execute(select(Assignment).where(Assignment.reviewer_user_id == user_id)).scalars().all()
    projects = {row.project_id: row for row in session.execute(select(EvaluationProject)).scalars().all()}
    by_project: dict[str, dict] = {}
    for assignment in assignments:
        project = projects.get(assignment.project_id)
        bucket = by_project.setdefault(assignment.project_id, {
            "project_id": assignment.project_id,
            "project_name": project.name if project else "未知项目",
            "pending": 0,
            "completed": 0,
        })
        bucket["pending" if assignment.status in {"assigned", "in_progress", "revisit"} else "completed"] += 1
    safe_user = next((
        {key: value for key, value in row.items() if key not in {"session_version", "invite_source"}}
        for row in admin_users(session)["items"] if row["user_id"] == user_id
    ), {})
    return {
        "user": safe_user,
        "projects": list(by_project.values()),
        "pending": sum(row["pending"] for row in by_project.values()),
        "workload_model": "open_assignment_count_v1",
        "current_open_assignments": sum(row["pending"] for row in by_project.values()),
        "difficulty_weighted": False,
        "workload_limitations": [
            "text_length_not_weighted",
            "task_difficulty_not_weighted",
            "reviewer_speed_not_weighted",
        ],
        "completed": sum(row["completed"] for row in by_project.values()),
        "revisit": safe_user.get("revisit_assignment_count", 0),
        "adjudication_pending": safe_user.get("adjudication_pending", 0),
        "recent_7_days_completed": safe_user.get("recent_7_days_completed", 0),
        "assignment_role_distribution": safe_user.get("assignment_role_distribution", {}),
        "domain_distribution": safe_user.get("domain_distribution", {}),
        "case_distribution": safe_user.get("case_distribution", {}),
        "blind_payload_included": False,
    }


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


def admin_revoke_sessions(session: Session, *, admin: dict, user_id: str) -> dict:
    _target(session, user_id)
    return owner_revoke_sessions(session, owner=admin, user_id=user_id)


def admin_issue_reset_link(session: Session, *, admin: dict, user_id: str, base_url: str) -> dict:
    _target(session, user_id)
    return owner_issue_reset_link(session, owner=admin, user_id=user_id, base_url=base_url)


def admin_bulk_update_users(session: Session, *, admin: dict, user_ids: list[str], action: str) -> dict:
    targets = [_target(session, user_id) for user_id in sorted(set(user_ids or []))]
    if not targets:
        raise ValueError("no_users_selected")
    if action not in {"enable", "disable"}:
        raise ValueError("unsupported_bulk_action")
    changed = []
    for user in targets:
        changed.append(admin_update_user(session, admin=admin, user_id=user.user_id, enabled=action == "enable"))
    return {
        "action": action,
        "affected_count": len(changed),
        "sessions_invalidated": len(changed),
        "users": [{"user_id": row["user_id"], "username": row["username"], "enabled": row["enabled"]} for row in changed],
    }


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
