"""Safely apply an audited Atlas orphan-row repair plan."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from code_engine.system_b.persistence.database import database_url, sqlite_path_from_url


PLAN_SCHEMA = "fk_orphan_repair_plan_v1"
QUARANTINE_SCHEMA = "fk_orphan_quarantine_manifest_v1"
PROTECTED_TABLES = {
    "users", "invites", "evaluation_projects", "review_items", "assignments",
    "annotations", "adjudications", "gold_records", "metric_runs", "metric_results",
    "source_ingestions", "prediction_runs", "source_artifacts",
}
REPAIR_MATCH_COLUMNS = {
    "annotation_events": {"event_id", "annotation_id", "project_id"},
    "evaluation_protocols": {"protocol_id", "project_id"},
}
REPAIR_TABLES = set(REPAIR_MATCH_COLUMNS)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_plan(plan: dict, plan_path: Path) -> dict:
    if not isinstance(plan, dict) or plan.get("schema_version") != PLAN_SCHEMA:
        raise ValueError("repair_plan_schema_invalid")
    if not plan.get("requires_human_approval"):
        raise ValueError("repair_plan_human_approval_marker_missing")
    protected = plan.get("protected_tables")
    if not isinstance(protected, list) or set(protected) != PROTECTED_TABLES or len(protected) != len(PROTECTED_TABLES):
        raise ValueError("repair_plan_protected_tables_incomplete")
    baseline_hashes = plan.get("row_hash_before")
    if not isinstance(baseline_hashes, dict) or not PROTECTED_TABLES.issubset(baseline_hashes):
        raise ValueError("repair_plan_protected_hashes_incomplete")
    actions = plan.get("delete_actions")
    if not isinstance(actions, list) or not actions:
        raise ValueError("repair_plan_delete_actions_invalid")
    action_keys: set[tuple[str, int]] = set()
    action_counts: dict[str, int] = {}
    for action in actions:
        if not isinstance(action, dict) or set(action) != {"table", "rowid", "match"}:
            raise ValueError("repair_plan_delete_action_schema_invalid")
        table, rowid, match = action.get("table"), action.get("rowid"), action.get("match")
        if table not in REPAIR_TABLES or not isinstance(rowid, int) or rowid < 1:
            raise ValueError("repair_plan_delete_target_not_allowed")
        if not isinstance(match, dict) or set(match) != REPAIR_MATCH_COLUMNS[table]:
            raise ValueError(f"repair_plan_match_columns_invalid:{table}")
        if any(not isinstance(value, str) or not value for value in match.values()):
            raise ValueError(f"repair_plan_match_values_invalid:{table}")
        key = (table, rowid)
        if key in action_keys:
            raise ValueError("repair_plan_duplicate_delete_target")
        action_keys.add(key)
        action_counts[table] = action_counts.get(table, 0) + 1
    expected_changes = plan.get("expected_count_changes")
    expected_exact = {table: -count for table, count in action_counts.items()}
    if expected_changes != expected_exact:
        raise ValueError("repair_plan_count_changes_invalid")
    violations = plan.get("violations")
    if not isinstance(violations, list) or not violations:
        raise ValueError("repair_plan_violations_invalid")
    quarantine = plan.get("quarantine_export")
    if not isinstance(quarantine, dict) or set(quarantine) != {"manifest_path", "path", "sha256"}:
        raise ValueError("repair_plan_quarantine_schema_invalid")
    export_path = Path(quarantine["path"])
    manifest_path = Path(quarantine["manifest_path"])
    if not export_path.is_absolute():
        export_path = (Path.cwd() / export_path).resolve()
    if not manifest_path.is_absolute():
        manifest_path = (Path.cwd() / manifest_path).resolve()
    if not export_path.is_file() or _sha256_file(export_path) != quarantine["sha256"]:
        raise ValueError("quarantine_export_sha256_mismatch")
    if not manifest_path.is_file():
        raise ValueError("quarantine_manifest_missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != QUARANTINE_SCHEMA:
        raise ValueError("quarantine_manifest_schema_invalid")
    if manifest.get("export_sha256") != quarantine["sha256"]:
        raise ValueError("quarantine_manifest_export_sha256_mismatch")
    if manifest.get("database_sha256") != plan.get("database_sha256"):
        raise ValueError("quarantine_manifest_database_sha256_mismatch")
    return {
        "plan_path": str(plan_path.resolve()),
        "quarantine_export_path": str(export_path),
        "quarantine_export_sha256": quarantine["sha256"],
        "quarantine_manifest_path": str(manifest_path),
    }


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
    if not set(tables).issubset(PROTECTED_TABLES | REPAIR_TABLES):
        raise ValueError("table_not_allowed")
    return {table: int(_scalar(conn, f"SELECT count(*) FROM {table}")) for table in tables}


def _table_hashes(conn, tables: list[str]) -> dict[str, str]:
    if not set(tables).issubset(PROTECTED_TABLES | REPAIR_TABLES):
        raise ValueError("table_not_allowed")
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
    integrity = _scalar(conn, "PRAGMA integrity_check")
    foreign_keys = _scalar(conn, "PRAGMA foreign_keys")
    if integrity != "ok" or foreign_keys != 1:
        raise ValueError(f"database_health_precondition_failed: integrity={integrity} foreign_keys={foreign_keys}")
    return {"database_sha256": actual_sha, "database_revision": revision, "integrity_check": integrity, "foreign_keys": foreign_keys, "foreign_key_check": actual}


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
    plan_validation = _validate_plan(plan, plan_path)
    tables = sorted(set(plan.get("protected_tables", [])) | {"annotation_events", "evaluation_protocols"})
    engine = create_engine(resolved, future=True)
    before: dict[str, Any] = {}
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        before = _verify_plan(conn, plan, expected_sha, db_path)
        before["counts"] = _table_counts(conn, tables)
        before["row_hashes"] = _table_hashes(conn, tables)
        mismatched_baselines = [
            table for table in sorted(PROTECTED_TABLES)
            if before["row_hashes"][table] != plan["row_hash_before"][table]
        ]
        if mismatched_baselines:
            raise ValueError(f"repair_plan_protected_hash_mismatch:{mismatched_baselines}")
        before["plan_validation"] = plan_validation
        if not apply:
            return {"schema_version": "atlas_db_repair_orphans_report_v1", "status": "dry_run", "apply": False, "before": before, "planned_actions": plan.get("delete_actions", [])}
        conn.commit()
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            if _scalar(conn, "PRAGMA foreign_keys") != 1:
                raise RuntimeError("foreign_keys_disabled_during_apply")
            for action in plan.get("delete_actions", []):
                table = action["table"]
                if table not in REPAIR_TABLES:
                    raise RuntimeError("repair_table_not_allowed")
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
