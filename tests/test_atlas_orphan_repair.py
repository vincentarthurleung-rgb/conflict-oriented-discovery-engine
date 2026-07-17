import json
import os
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from code_engine.cli.atlas_db_repair_orphans import repair
from code_engine.system_b.persistence.database import create_atlas_engine, sqlite_health


def migrate(url, revision="0008_system_a_ingestion_ledger"):
    os.environ["ATLAS_DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, revision)


def write_orphan_fixture(tmp_path: Path) -> tuple[Path, str, Path]:
    db = tmp_path / "atlas.db"
    url = f"sqlite:///{db}"
    migrate(url)
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT INTO users(user_id,username,display_name,password_hash,role,enabled,created_at,updated_at) "
            "VALUES('owner-id','owner','Owner','x','owner',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "INSERT INTO review_items(review_item_id,case_id,item_type,payload_json,source_hash,import_run_id,namespace,created_at) "
            "VALUES('item-1','case','claim','{}','hash','import','pilot',CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "INSERT INTO annotation_events(event_id,annotation_id,project_id,review_item_id,actor_user_id,actor_username_snapshot,action,new_revision,changed_fields_json,full_snapshot_json,occurred_at) "
            "VALUES('event-1','missing-annotation','missing-project','item-1','owner-id','owner','annotation_submitted',1,'[]','{}',CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "INSERT INTO evaluation_protocols(protocol_id,project_id,version,protocol_json,case_ids_sha256,metric_registry_sha256,annotation_schema_sha256,dataset_split_sha256,frozen,created_by_user_id,created_at,frozen_at) "
            "VALUES('protocol-1','missing-protocol-project',1,'{}','a','b','c','d',1,'owner-id',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        conn.commit()
    sha = db.read_bytes()
    import hashlib

    digest = hashlib.sha256(sha).hexdigest()
    plan = {
        "schema_version": "fk_orphan_repair_plan_v1",
        "database_sha256": digest,
        "database_revision": "0008_system_a_ingestion_ledger",
        "violations": [
            {"table": "annotation_events", "rowid": 1, "parent_table": "evaluation_projects", "fk_id": 1},
            {"table": "annotation_events", "rowid": 1, "parent_table": "annotations", "fk_id": 2},
            {"table": "evaluation_protocols", "rowid": 1, "parent_table": "evaluation_projects", "fk_id": 0},
        ],
        "protected_tables": [
            "users",
            "evaluation_projects",
            "review_items",
            "assignments",
            "annotations",
            "adjudications",
            "gold_records",
            "metric_runs",
            "metric_results",
        ],
        "delete_actions": [
            {"table": "annotation_events", "rowid": 1, "match": {"event_id": "event-1", "annotation_id": "missing-annotation", "project_id": "missing-project"}},
            {"table": "evaluation_protocols", "rowid": 1, "match": {"protocol_id": "protocol-1", "project_id": "missing-protocol-project"}},
        ],
        "expected_count_changes": {"annotation_events": -1, "evaluation_protocols": -1},
    }
    plan_path = tmp_path / "repair-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    return db, digest, plan_path


def test_sqlite_connections_enable_foreign_keys(tmp_path):
    db = tmp_path / "atlas.db"
    url = f"sqlite:///{db}"
    migrate(url)
    health = sqlite_health(create_atlas_engine(url))
    assert health["foreign_keys"] == 1
    assert health["foreign_key_check"] == []
    assert health["status"] == "ok"


def test_annotation_event_parent_integrity(tmp_path):
    db, _, _ = write_orphan_fixture(tmp_path)
    health = sqlite_health(create_atlas_engine(f"sqlite:///{db}"))
    assert health["status"] == "failed"
    assert any(row["table"] == "annotation_events" and row["parent"] == "annotations" for row in health["foreign_key_check"])


def test_protocol_project_integrity(tmp_path):
    db, _, _ = write_orphan_fixture(tmp_path)
    health = sqlite_health(create_atlas_engine(f"sqlite:///{db}"))
    assert any(row["table"] == "evaluation_protocols" and row["parent"] == "evaluation_projects" for row in health["foreign_key_check"])


def test_orphan_repair_dry_run(tmp_path):
    db, digest, plan = write_orphan_fixture(tmp_path)
    result = repair(f"sqlite:///{db}", plan, apply=False, expected_sha=digest)
    assert result["status"] == "dry_run"
    assert sqlite3.connect(db).execute("SELECT count(*) FROM annotation_events").fetchone()[0] == 1


def test_orphan_repair_expected_hash_guard(tmp_path):
    db, _, plan = write_orphan_fixture(tmp_path)
    with pytest.raises(ValueError, match="database_sha256_mismatch"):
        repair(f"sqlite:///{db}", plan, apply=True, expected_sha="0" * 64)


def test_orphan_repair_unknown_violation_fails_closed(tmp_path):
    db, _, plan = write_orphan_fixture(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT INTO evaluation_protocols(protocol_id,project_id,version,protocol_json,case_ids_sha256,metric_registry_sha256,annotation_schema_sha256,dataset_split_sha256,frozen,created_at) "
            "VALUES('protocol-2','another-missing-project',1,'{}','a','b','c','d',1,CURRENT_TIMESTAMP)"
        )
        conn.commit()
    import hashlib

    digest = hashlib.sha256(db.read_bytes()).hexdigest()
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload["database_sha256"] = digest
    plan.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="foreign_key_violations_do_not_match_plan"):
        repair(f"sqlite:///{db}", plan, apply=True, expected_sha=digest)


def test_repaired_copy_migrates_0008_to_head(tmp_path):
    db, digest, plan = write_orphan_fixture(tmp_path)
    result = repair(f"sqlite:///{db}", plan, apply=True, expected_sha=digest)
    assert result["status"] == "applied"
    assert result["after"]["foreign_key_check"] == []
    url = f"sqlite:///{db}"
    os.environ["ATLAS_DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    assert sqlite3.connect(db).execute("PRAGMA foreign_key_check").fetchall() == []
    command.downgrade(cfg, "0008_system_a_ingestion_ledger")
    assert sqlite3.connect(db).execute("PRAGMA foreign_key_check").fetchall() == []
    command.upgrade(cfg, "head")
    assert sqlite3.connect(db).execute("PRAGMA foreign_key_check").fetchall() == []
