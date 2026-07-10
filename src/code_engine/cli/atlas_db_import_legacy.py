"""Import legacy Atlas JSON/JSONL state into the SQLite database."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from code_engine.cli.atlas_db_backup import main as backup_main
from code_engine.system_b.explorer.auth import load_user_store
from code_engine.system_b.explorer.explorer_api import _json, _jsonl
from code_engine.system_b.persistence.database import create_atlas_engine, database_url, session_factory, session_scope
from code_engine.system_b.persistence.models import Annotation, Invite, User
from code_engine.system_b.persistence.services.review_service import (
    ensure_local_developer,
    ensure_project,
    import_review_items,
    save_annotation,
)


def _import_users(session, users_file: str | None) -> dict:
    if not users_file or not Path(users_file).is_file():
        return {"users_seen": 0, "users_inserted": 0, "invites_seen": 0, "invites_inserted": 0}
    store = load_user_store(users_file)
    inserted_users = 0
    for username, row in store.get("users", {}).items():
        normalized = str(row.get("username") or username).casefold()
        if session.execute(select(User).where(User.username == normalized)).scalar_one_or_none():
            continue
        session.add(User(
            username=normalized,
            display_name=row.get("display_name") or normalized,
            password_hash=row.get("password_hash") or "",
            role=row.get("role") if row.get("role") in {"owner", "admin", "developer", "reviewer", "pharma"} else "reviewer",
            enabled=bool(row.get("enabled", True)),
        ))
        inserted_users += 1
    inserted_invites = 0
    for row in store.get("invites", []):
        code_hash = row.get("code_hash")
        if not code_hash or session.execute(select(Invite).where(Invite.code_hash == code_hash)).scalar_one_or_none():
            continue
        role = row.get("role") if row.get("role") in {"owner", "admin", "developer", "reviewer", "pharma"} else "reviewer"
        session.add(Invite(
            code_hash=code_hash,
            label=row.get("label") or "legacy",
            role=role,
            enabled=bool(row.get("enabled", True)),
            max_uses=int(row.get("max_uses") or 1),
            uses=int(row.get("uses") or 0),
        ))
        inserted_invites += 1
    return {
        "users_seen": len(store.get("users", {})),
        "users_inserted": inserted_users,
        "invites_seen": len(store.get("invites", [])),
        "invites_inserted": inserted_invites,
    }


def _import_annotations(session, review_root: Path, namespace: str) -> dict:
    rows = []
    live = _json(review_root / "manual_review_annotations_live.json")
    if isinstance(live, dict):
        rows = live.get("annotations", [])
    if not rows:
        rows = _jsonl(review_root / "manual_review_annotations_live.jsonl")
    if not rows:
        return {"legacy_annotations_seen": 0, "legacy_annotations_imported": 0, "legacy_annotations_skipped": 0}
    user = ensure_local_developer(session)
    ensure_project(session, namespace=namespace)
    imported = 0
    skipped = 0
    for row in rows:
        item_id = row.get("review_item_id")
        if not item_id:
            skipped += 1
            continue
        if session.execute(select(Annotation).where(
            Annotation.review_item_id == item_id,
            Annotation.reviewer_user_id == user.user_id,
            Annotation.namespace == namespace,
        )).scalar_one_or_none():
            skipped += 1
            continue
        payload = dict(row)
        payload["review_disposition"] = row.get("review_disposition") or "submitted"
        payload["uncertainty_reason"] = row.get("uncertainty_reason") or "legacy_unattributed"
        payload["client_submission_id"] = f"legacy:{item_id}"
        save_annotation(
            session,
            review_item_id=item_id,
            payload=payload,
            identity={"user_id": user.user_id, "username": user.username, "display_name": user.display_name, "role": user.role, "authenticated": False},
            namespace=namespace,
        )
        imported += 1
    return {"legacy_annotations_seen": len(rows), "legacy_annotations_imported": imported, "legacy_annotations_skipped": skipped}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--users-file")
    parser.add_argument("--review-root", required=True)
    parser.add_argument("--namespace", default="test", choices=("pilot", "production", "calibration", "test"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args(argv)
    url = database_url(args.database_url)
    engine = create_atlas_engine(url)
    factory = session_factory(engine)
    report = {}
    if args.dry_run:
        session = factory()
        try:
            report.update(_import_users(session, args.users_file))
            report.update(import_review_items(session, args.review_root, namespace=args.namespace))
            report.update(_import_annotations(session, Path(args.review_root), args.namespace))
            session.rollback()
        finally:
            session.close()
        report["dry_run"] = True
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    if not args.no_backup:
        try:
            backup_main(["--database-url", url])
        except FileNotFoundError:
            pass
    with session_scope(factory) as session:
        report.update(_import_users(session, args.users_file))
        report.update(import_review_items(session, args.review_root, namespace=args.namespace))
        report.update(_import_annotations(session, Path(args.review_root), args.namespace))
    report["dry_run"] = False
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
