"""Safely apply an audited Atlas orphan-row repair plan."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from code_engine.system_b.persistence.database import database_url, sqlite_path_from_url


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(conn, sql: str, params: dict | None = None) -> list[dict]:
    return [dict(row._mapping) for row in conn.execute(text(sql), params or {}).all()]


def _scalar(conn, sql: str) -> Any:
    return conn.execute(text(sql)).scalar()


def _fk_violations(conn) -> list[dict]:
    rows = _rows(conn, "PRAGMA foreign_key_check")
    return sorted(rows, key=lambda row: (row["table"], row["rowid"], row["parent"], row["fkid"]))


def _planned_violations(plan: dict) -> list[dict]:
    return sorted(
        [
            {"table": item["table"], "rowid": item["rowid"], "parent": item["parent_table"], "fkid": item["fk_id"]}
            for item in plan.get("violations", [])
        ],
        key=lambda row: (row["table"], row["rowid"], row["parent"], row["fkid"]),
    )


def _table_counts(conn, tables: list[str]) -> dict[str, int]:
    return {table: int(_scalar(conn, f"SELECT count(*) FROM {table}")) for table in tables}


def _table_hashes(conn, tables: list[str]) -> dict[str, str]:
    hashes = {}
    for table in tables:
        rows = _rows(conn, f"SELECT * FROM {table} ORDER BY rowid")
        hashes[table] = hashlib.sha256(_canonical(rows)).hexdigest()
    return hashes


def _verify_plan(conn, plan: dict, expected_sha: str | None, db_path: Path | None) -> dict:
    actual_sha = _sha256_file(db_path) if db_path and db_path.exists() else None
    if expected_sha and actual_sha != expected_sha:
        raise ValueError(f"database_sha256_mismatch: expected {expected_sha}, got {actual_sha}")
    if actual_sha and plan.get("database_sha256") and actual_sha != plan["database_sha256"]:
        raise ValueError("repair_plan_database_sha256_mismatch")
    revision = _scalar(conn, "SELECT version_num FROM alembic_version")
    if revision != plan.get("database_revision"):
        raise ValueError(f"database_revision_mismatch: expected {plan.get('database_revision')}, got {revision}")
    actual = _fk_violations(conn)
    planned = _planned_violations(plan)
    if actual != planned:
        raise ValueError(f"foreign_key_violations_do_not_match_plan: actual={actual} planned={planned}")
    return {"database_sha256": actual_sha, "database_revision": revision, "foreign_key_check": actual}


def _match_clause(match: dict) -> tuple[str, dict]:
    params = {}
    clauses = []
    for index, (key, value) in enumerate(sorted(match.items())):
        name = f"m{index}"
        clauses.append(f"{key} = :{name}")
        params[name] = value
    return " AND ".join(clauses), params


def repair(database: str | None, plan_path: Path, *, apply: bool, expected_sha: str | None) -> dict:
    resolved = database_url(database)
    db_path = sqlite_path_from_url(resolved)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    tables = sorted(set(plan.get("protected_tables", [])) | {"annotation_events", "evaluation_protocols"})
    engine = create_engine(resolved, future=True)
    before: dict[str, Any] = {}
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        before = _verify_plan(conn, plan, expected_sha, db_path)
        before["counts"] = _table_counts(conn, tables)
        before["row_hashes"] = _table_hashes(conn, tables)
        if not apply:
            return {"schema_version": "atlas_db_repair_orphans_report_v1", "status": "dry_run", "apply": False, "before": before, "planned_actions": plan.get("delete_actions", [])}
        conn.commit()
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            for action in plan.get("delete_actions", []):
                table = action["table"]
                rowid = action["rowid"]
                clause, params = _match_clause(action.get("match") or {})
                sql = f"DELETE FROM {table} WHERE rowid = :rowid"
                if clause:
                    sql += f" AND {clause}"
                result = conn.execute(text(sql), {"rowid": rowid, **params})
                if result.rowcount != 1:
                    raise RuntimeError(f"planned_delete_did_not_match_one_row: {table} rowid={rowid}")
            fk_after = _fk_violations(conn)
            integrity = _scalar(conn, "PRAGMA integrity_check")
            if fk_after or integrity != "ok":
                raise RuntimeError(f"post_repair_validation_failed: integrity={integrity} foreign_key_check={fk_after}")
            after_counts = _table_counts(conn, tables)
            expected = dict(before["counts"])
            for table, delta in (plan.get("expected_count_changes") or {}).items():
                expected[table] = expected.get(table, 0) + int(delta)
            if after_counts != expected:
                raise RuntimeError(f"post_repair_counts_do_not_match_plan: expected={expected} actual={after_counts}")
            protected = [table for table in plan.get("protected_tables", []) if table in before["row_hashes"]]
            after_hashes = _table_hashes(conn, tables)
            changed_protected = [table for table in protected if before["row_hashes"][table] != after_hashes[table]]
            if changed_protected:
                raise RuntimeError(f"protected_table_changed: {changed_protected}")
            owner_count = _scalar(conn, "SELECT count(*) FROM users WHERE role='owner' AND enabled=1")
            if owner_count != 1:
                raise RuntimeError(f"owner_uniqueness_failed: {owner_count}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return {
            "schema_version": "atlas_db_repair_orphans_report_v1",
            "status": "applied",
            "apply": True,
            "before": before,
            "after": {
                "integrity_check": integrity,
                "foreign_key_check": fk_after,
                "counts": after_counts,
                "row_hashes": after_hashes,
                "owner_enabled_count": owner_count,
            },
            "planned_actions": plan.get("delete_actions", []),
        }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--repair-plan", type=Path, required=True)
    parser.add_argument("--expected-database-sha256")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and not args.expected_database_sha256:
        raise ValueError("--apply requires --expected-database-sha256")
    result = repair(args.database_url, args.repair_plan, apply=bool(args.apply and not args.dry_run), expected_sha=args.expected_database_sha256)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
