"""Restore an Atlas SQLite backup."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from code_engine.cli.atlas_db_backup import main as backup_main
from code_engine.system_b.persistence.database import create_atlas_engine, database_url, session_factory, session_scope, sqlite_path_from_url
from code_engine.system_b.persistence.services.audit_service import write_audit_event


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--backup-file", required=True)
    parser.add_argument("--confirm-restore", action="store_true")
    parser.add_argument("--actor-user-id")
    args = parser.parse_args(argv)
    if not args.confirm_restore:
        raise ValueError("--confirm-restore is required")
    url = database_url(args.database_url)
    target = sqlite_path_from_url(url)
    if not target:
        raise ValueError("restore currently supports sqlite:/// URLs")
    if target.exists():
        backup_main(["--database-url", url])
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(Path(args.backup_file)) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    engine = create_atlas_engine(url)
    with session_scope(session_factory(engine)) as session:
        write_audit_event(session, action="database_restored", object_type="database", object_id=str(target), actor={"user_id": args.actor_user_id}, metadata={"backup_file": str(args.backup_file)})
    print(f"restored {args.backup_file} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
