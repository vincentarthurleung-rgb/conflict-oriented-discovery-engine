"""Database-backed Atlas identity and invite registration services."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash

from code_engine.system_b.explorer.auth import hash_invite_code, hash_password, validate_display_name, validate_password_strength, validate_username
from code_engine.system_b.persistence.models import Invite, InviteUsageEvent, PasswordResetToken, SystemSetting, User, utcnow
from code_engine.system_b.persistence.services.audit_service import write_audit_event


class AuthError(RuntimeError):
    pass


def identity_from_user(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "must_change_password": user.must_change_password,
        "session_version": user.session_version,
        "authenticated": True,
    }


def load_identity(session: Session, user_id: str | None, session_version: int | None = None) -> dict | None:
    if not user_id:
        return None
    user = session.get(User, user_id)
    if not user or not user.enabled:
        return None
    if session_version is not None and int(session_version) != int(user.session_version):
        return None
    return identity_from_user(user)


def authenticate_user(
    session: Session,
    *,
    username: str,
    password: str,
    request_context: dict | None = None,
) -> User:
    normalized = validate_username(username)
    user = session.execute(select(User).where(User.username == normalized)).scalar_one_or_none()
    ok = bool(user and user.enabled and check_password_hash(user.password_hash, password))
    write_audit_event(
        session,
        action="db_login_success" if ok else "db_login_failure",
        object_type="user",
        object_id=user.user_id if user else normalized,
        actor=identity_from_user(user) if ok and user else {"username": normalized},
        metadata={"username": normalized, "enabled": bool(user.enabled) if user else None},
        **(request_context or {}),
    )
    if not ok or not user:
        raise AuthError("invalid_credentials")
    user.last_login_at = utcnow()
    return user


def hash_reset_token(token: str) -> str:
    return "sha256:" + hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def change_password(session: Session, *, user_id: str, current_password: str, new_password: str, confirm_password: str, actor: dict | None = None) -> dict:
    user = session.get(User, user_id)
    if not user or not user.enabled:
        raise AuthError("invalid_account")
    if not check_password_hash(user.password_hash, current_password):
        raise AuthError("invalid_current_password")
    password = validate_password_strength(new_password)
    if password != str(confirm_password or ""):
        raise ValueError("password_mismatch")
    user.password_hash = hash_password(password)
    user.must_change_password = False
    user.session_version += 1
    write_audit_event(session, action="password_changed", object_type="user", object_id=user.user_id, actor=actor or identity_from_user(user), metadata={"target_user_id": user.user_id})
    return {"ok": True, "session_version": user.session_version}


def issue_password_reset(session: Session, *, target_user: User, owner: dict, expires_minutes: int = 60) -> dict:
    if target_user.role == "owner" and target_user.user_id != owner.get("user_id"):
        raise PermissionError("owner_password_reset_forbidden")
    now = utcnow()
    session.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == target_user.user_id,
        PasswordResetToken.used_at == None,
        PasswordResetToken.revoked_at == None,
    ).update({PasswordResetToken.revoked_at: now}, synchronize_session=False)  # noqa: E711
    token = secrets.token_urlsafe(36)
    row = PasswordResetToken(
        user_id=target_user.user_id,
        token_hash=hash_reset_token(token),
        created_by_user_id=owner.get("user_id"),
        expires_at=now + timedelta(minutes=expires_minutes),
    )
    session.add(row)
    session.flush()
    write_audit_event(session, action="password_reset_issued", object_type="user", object_id=target_user.user_id, actor=owner, metadata={"target_user_id": target_user.user_id, "reset_token_id": row.reset_token_id, "expires_minutes": expires_minutes})
    return {"reset_token_id": row.reset_token_id, "token": token, "expires_at": row.expires_at.isoformat()}


def complete_password_reset(session: Session, *, token: str, new_password: str, confirm_password: str) -> dict:
    row = session.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(token))).scalar_one_or_none()
    now = utcnow()
    expires_at = row.expires_at.replace(tzinfo=timezone.utc) if row and row.expires_at and row.expires_at.tzinfo is None else (row.expires_at if row else None)
    if not row or row.used_at or row.revoked_at or now > expires_at:
        raise AuthError("invalid_reset_token")
    password = validate_password_strength(new_password)
    if password != str(confirm_password or ""):
        raise ValueError("password_mismatch")
    user = session.get(User, row.user_id)
    if not user or not user.enabled:
        raise AuthError("invalid_account")
    user.password_hash = hash_password(password)
    user.must_change_password = False
    user.session_version += 1
    row.used_at = now
    write_audit_event(session, action="password_reset_completed", object_type="user", object_id=user.user_id, actor=identity_from_user(user), metadata={"reset_token_id": row.reset_token_id})
    return {"ok": True, "user_id": user.user_id}


def create_owner(session: Session, *, username: str, display_name: str, password: str) -> User:
    username = validate_username(username)
    display_name = validate_display_name(display_name)
    password = validate_password_strength(password)
    existing_owner = session.execute(select(User).where(User.role == "owner", User.enabled == True)).scalar_one_or_none()  # noqa: E712
    if existing_owner:
        raise ValueError("enabled owner already exists")
    owner = User(username=username, display_name=display_name, password_hash=hash_password(password), role="owner", enabled=True)
    session.add(owner)
    session.flush()
    session.merge(SystemSetting(key="owner_user_id", value=owner.user_id))
    write_audit_event(session, action="owner_created", object_type="user", object_id=owner.user_id, actor=identity_from_user(owner))
    return owner


def create_invite(
    session: Session,
    *,
    code: str,
    label: str,
    role: str = "reviewer",
    max_uses: int = 1,
    expires_at: datetime | None = None,
    created_by: dict | None = None,
    project_scope: dict | None = None,
    notes: str = "",
) -> Invite:
    if role not in {"admin", "developer", "reviewer", "pharma"}:
        raise ValueError("owner invites are not allowed")
    invite = Invite(
        code_hash=hash_invite_code(code),
        label=str(label or "").strip()[:160] or "invite",
        role=role,
        enabled=True,
        max_uses=max_uses,
        uses=0,
        expires_at=expires_at,
        created_by_user_id=(created_by or {}).get("user_id"),
        project_scope_json=json.dumps(project_scope or {}, sort_keys=True),
        notes=str(notes or "")[:500],
    )
    session.add(invite)
    session.flush()
    write_audit_event(session, action="invite_created", object_type="invite", object_id=invite.invite_id, actor=created_by, metadata={"label": invite.label, "role": role, "max_uses": max_uses, "project_scope": project_scope or {}})
    return invite


def register_with_invite(
    session: Session,
    *,
    username: str,
    display_name: str,
    password: str,
    confirm_password: str,
    invite_code: str,
    request_context: dict | None = None,
) -> User:
    # Serialize invite consumption in SQLite so max_uses cannot be overrun.
    if session.bind and session.bind.dialect.name == "sqlite":
        session.execute(text("BEGIN IMMEDIATE"))
    username = validate_username(username)
    display_name = validate_display_name(display_name)
    password = validate_password_strength(password)
    if password != str(confirm_password or ""):
        raise ValueError("password_mismatch")
    if session.execute(select(User).where(User.username == username)).scalar_one_or_none():
        raise ValueError("duplicate_username")
    now = datetime.now(timezone.utc)
    invite = session.execute(select(Invite).where(Invite.code_hash == hash_invite_code(invite_code))).scalar_one_or_none()
    if not invite or not invite.enabled:
        raise ValueError("invalid_invite")
    if invite.expires_at and now > invite.expires_at.replace(tzinfo=timezone.utc):
        raise ValueError("expired_invite")
    if invite.max_uses is not None and int(invite.uses) >= int(invite.max_uses):
        raise ValueError("invite_exhausted")
    if invite.role == "owner":
        raise ValueError("owner_invite_forbidden")
    user = User(username=username, display_name=display_name, password_hash=hash_password(password), role=invite.role, enabled=True, invite_source_id=invite.invite_id)
    invite.uses = int(invite.uses) + 1
    invite.last_used_at = utcnow()
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        raise ValueError("registration_conflict") from None
    session.add(InviteUsageEvent(invite_id=invite.invite_id, user_id=user.user_id, request_id=(request_context or {}).get("request_id"), ip_hash=(request_context or {}).get("ip_hash")))
    write_audit_event(
        session,
        action="user_registered_by_invite",
        object_type="user",
        object_id=user.user_id,
        actor=identity_from_user(user),
        metadata={"invite_id": invite.invite_id, "role": invite.role},
        **(request_context or {}),
    )
    write_audit_event(session, action="invite_used", object_type="invite", object_id=invite.invite_id, actor=identity_from_user(user), metadata={"invite_id": invite.invite_id, "user_id": user.user_id, "uses": invite.uses, "max_uses": invite.max_uses})
    if invite.uses >= invite.max_uses:
        write_audit_event(session, action="invite_exhausted", object_type="invite", object_id=invite.invite_id, actor=identity_from_user(user), metadata={"invite_id": invite.invite_id})
    return user
