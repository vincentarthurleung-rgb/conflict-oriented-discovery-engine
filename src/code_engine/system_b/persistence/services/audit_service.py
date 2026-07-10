"""Append-only audit helpers for Atlas database-backed operations."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from code_engine.system_b.persistence.models import AuditEvent


def canonical_json(value: Any) -> str:
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def write_audit_event(
    session: Session,
    *,
    action: str,
    object_type: str,
    object_id: str = "",
    actor: dict | None = None,
    project_id: str | None = None,
    case_id: str = "",
    review_item_id: str = "",
    metadata: dict | None = None,
    request_id: str | None = None,
    ip_hash: str | None = None,
    session_hash: str | None = None,
) -> AuditEvent:
    actor = actor or {}
    event = AuditEvent(
        actor_user_id=actor.get("user_id"),
        actor_username_snapshot=actor.get("username") or "",
        action=action,
        object_type=object_type,
        object_id=object_id or "",
        project_id=project_id,
        case_id=case_id or "",
        review_item_id=review_item_id or "",
        metadata_json=canonical_json(metadata),
        request_id=request_id,
        ip_hash=ip_hash,
        session_hash=session_hash,
    )
    session.add(event)
    session.flush()
    return event
