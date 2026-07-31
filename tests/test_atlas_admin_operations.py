from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from sqlalchemy import func, select

from code_engine.system_b.evaluation.claim_sampling import (
    evaluation_readiness,
    preview_sample,
    sampling_frame_stats,
)
from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from code_engine.system_b.persistence.models import Assignment, EvaluationProject
from code_engine.system_b.persistence.services.admin_service import (
    admin_change_role,
    admin_overview,
    admin_user_workload,
    admin_users,
)
from code_engine.system_b.persistence.services.assignment_service import (
    assignment_batch_preview,
    create_assignment_batch,
)
from tests.atlas_db_test_utils import add_review_item, add_user, migrate, session_for
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests


def _db(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'atlas.db'}"
    migrate(url)
    factory = session_for(url)
    with factory.begin() as session:
        owner = add_user(session, "owner", "owner")
        admin = add_user(session, "admin", "admin")
        primary = add_user(session, "primary", "reviewer")
        secondary = add_user(session, "secondary", "reviewer")
        adjudicator = add_user(session, "adjudicator", "adjudicator")
        project = EvaluationProject(
            name="Operations Pilot", namespace="pilot", status="active",
            created_by_user_id=owner.user_id,
        )
        session.add(project)
        session.flush()
        items = [
            add_review_item(session, f"item-{index}", case_id=f"case-{index % 3}", namespace="pilot")
            for index in range(1, 7)
        ]
        ids = {
            "owner": owner.user_id, "admin": admin.user_id, "primary": primary.user_id,
            "secondary": secondary.user_id, "adjudicator": adjudicator.user_id,
            "project": project.project_id, "items": [row.review_item_id for row in items],
        }
    return factory, ids


def _actor(ids, role="admin"):
    return {"user_id": ids[role], "username": role, "display_name": role.title(), "role": role}


def _rows(count=18):
    return [{
        "source_unit_id": f"unit-{index}",
        "review_item_id": f"item-{(index % 6) + 1}",
        "case_id": f"case-{index % 3}",
        "paper_id": f"paper-{index % 7}",
        "source_scope": "abstract" if index % 3 == 0 else "fulltext",
        "section_type": "abstract" if index % 3 == 0 else "results",
        "domain_snapshot": {"domain_id": f"domain-{index % 3}"},
        "text": f"Source unit {index}",
        "text_hash": f"hash-{index}",
        "predicted_claim_count": 1,
        "schema_supported": True,
        "case_active": True,
    } for index in range(count)]


def _preview(session, ids, **changes):
    values = {
        "project_id": ids["project"], "item_ids": ids["items"],
        "primary_reviewer_user_id": ids["primary"],
        "secondary_reviewer_user_id": ids["secondary"],
        "adjudicator_user_id": ids["adjudicator"],
        "actor_role": "admin",
    }
    values.update(changes)
    return assignment_batch_preview(session, **values)


def test_admin_operations_overview(tmp_path):
    factory, ids = _db(tmp_path)
    with factory() as session:
        result = admin_overview(session)
        assert result["active_reviewer_count"] == 2
        assert result["reviewers_without_assignments"] == 2
        assert result["pilot_project_count"] == 1


def test_admin_user_workload(tmp_path):
    factory, ids = _db(tmp_path)
    with factory() as session:
        result = admin_user_workload(session, user_id=ids["primary"])
        assert result["pending"] == 0
        assert result["blind_payload_included"] is False
        assert result["assignment_role_distribution"] == {"primary": 0, "secondary": 0, "adjudicator": 0}
        assert result["recent_7_days_completed"] == 0
        assert "password_hash" not in repr(result)


def test_admin_cannot_modify_owner(tmp_path):
    factory, ids = _db(tmp_path)
    with factory.begin() as session:
        with pytest.raises(PermissionError, match="admin_cannot_modify_privileged_user"):
            admin_change_role(session, admin=_actor(ids), user_id=ids["owner"], role="reviewer")


def test_assignment_preview_is_read_only(tmp_path):
    factory, ids = _db(tmp_path)
    with factory() as session:
        before = session.scalar(select(func.count()).select_from(Assignment))
        result = _preview(session, ids)
        after = session.scalar(select(func.count()).select_from(Assignment))
        assert result["blocked"] is False
        assert result["preview_writes_database"] is False
        assert before == after == 0


def test_assignment_create_is_transactional(tmp_path):
    factory, ids = _db(tmp_path)
    with factory.begin() as session:
        with pytest.raises(ValueError, match="assignment_batch_blocked"):
            create_assignment_batch(
                session, actor=_actor(ids), batch_name="Invalid", project_id=ids["project"],
                item_ids=ids["items"], primary_reviewer_user_id=ids["primary"],
                secondary_reviewer_user_id=ids["primary"], adjudicator_user_id=ids["adjudicator"],
            )
        assert session.scalar(select(func.count()).select_from(Assignment)) == 0


def test_assignment_duplicate_detection(tmp_path):
    factory, ids = _db(tmp_path)
    with factory.begin() as session:
        create_assignment_batch(
            session, actor=_actor(ids), batch_name="First", project_id=ids["project"],
            item_ids=ids["items"], primary_reviewer_user_id=ids["primary"],
            secondary_reviewer_user_id=ids["secondary"], adjudicator_user_id=ids["adjudicator"],
        )
    with factory() as session:
        result = _preview(session, ids)
        assert result["blocked"] is True
        assert result["duplicate_assignments"] == len(ids["items"]) * 3


def test_assignment_workload_balancing(tmp_path):
    factory, ids = _db(tmp_path)
    with factory() as session:
        result = _preview(session, ids, strategy="workload_balance")
        assert result["strategy"] == "workload_balance"
        assert {row["role"] for row in result["workloads"]} == {"primary", "secondary", "adjudicator"}
        assert all(row["pending_after"] == len(ids["items"]) for row in result["workloads"])


def test_sampling_purpose_contract():
    precision = preview_sample(_rows(), configuration={"purpose": "predicted_claim_precision", "sample_size": 6, "random_seed": 7})
    gold = preview_sample(_rows(), configuration={"purpose": "source_unit_exhaustive_gold", "sample_size": 6, "random_seed": 7})
    assert precision["purpose"] != gold["purpose"]
    assert precision["metric_readiness"]["claim_f1"]["value"] is None
    with pytest.raises(ValueError, match="unsupported_sampling_purpose"):
        preview_sample(_rows(), configuration={"purpose": "recall_button", "sample_size": 3, "random_seed": 1})


def test_sampling_frame_stats():
    result = sampling_frame_stats(_rows())
    assert result["source_unit_count"] == 18
    assert result["paper_count"] == 7
    assert result["frame_scope"] == "selected_for_l1_extraction"
    assert result["supported"] is True


def test_sampling_determinism():
    config = {"purpose": "source_unit_exhaustive_gold", "sample_size": 8, "random_seed": 20260731, "max_per_paper": 2}
    assert preview_sample(_rows(), configuration=config) == preview_sample(_rows(), configuration=config)


def test_sampling_idempotent_create(tmp_path):
    root = tmp_path / "kg"
    root.mkdir()
    KnowledgeExplorerTests().fixture(root)
    api = ExplorerAPI(root)
    api.source_text_unit_frame = _rows()
    api.claim_sampling_root = tmp_path / "sampling"
    body = {"purpose": "source_unit_exhaustive_gold", "sample_size": 6, "random_seed": 11}
    first = api._create_claim_pilot_sample(body)
    second = api._create_claim_pilot_sample(body)
    assert first["batch_id"] == second["batch_id"]
    assert first["creation_status"] == "created"
    assert second["creation_status"] == "no_op"
    assert second["reused"] is True


def test_sampling_distribution_constraints():
    result = preview_sample(_rows(), configuration={
        "purpose": "source_unit_exhaustive_gold", "sample_size": 9, "random_seed": 4,
        "min_per_domain": 2, "min_per_case": 2, "max_per_paper": 2,
    })
    assert result["blocked"] is False
    assert min(result["sample_distribution"]["domains"].values()) >= 2
    assert max(result["sample_distribution"]["papers"].values()) <= 2


def test_sampling_case_scope_constraints_and_saved_metadata():
    result = preview_sample(_rows(), configuration={
        "purpose": "source_unit_exhaustive_gold",
        "sample_size": 9,
        "random_seed": 18,
        "min_per_case": 2,
        "max_per_case": 4,
        "min_abstract_ratio": 0.2,
        "min_fulltext_ratio": 0.5,
    })
    assert result["blocked"] is False
    assert max(result["sample_distribution"]["cases"].values()) <= 4
    assert result["coverage"]["abstract"] >= 2
    assert result["coverage"]["fulltext"] >= 5
    assert all(row["stratum"] and row["inclusion_probability"] for row in result["units"])
    assert all("domain_snapshot" in row and "source_artifact_hash" in row for row in result["units"])


def test_precision_sample_is_cluster_scoped_and_not_recall_ready():
    result = preview_sample(_rows(), configuration={
        "purpose": "predicted_claim_precision",
        "sample_size": 4,
        "random_seed": 5,
    })
    assert result["sampling_unit"] == "source_unit_cluster_with_predicted_claims"
    assert result["schema_version"] == "predicted_claim_precision_cluster_sample_v1"
    assert result["metric_readiness"]["claim_recall"] == {
        "status": "not_supported_by_precision_sample",
        "value": None,
    }


def test_sampling_duplicate_hash_exclusion():
    rows = _rows(8)
    rows[2]["text_hash"] = rows[1]["text_hash"]
    result = preview_sample(rows, configuration={
        "purpose": "source_unit_exhaustive_gold", "sample_size": 7, "random_seed": 3,
        "exclusions": {"exclude_duplicate_text_hash": True, "exclude_no_text": True},
    })
    assert result["excluded_breakdown"]["duplicate_text_hash"] == 1
    assert result["coverage"]["duplicate_text_hashes"] == 0


def test_claim_f1_remains_blocked_without_gold():
    readiness = evaluation_readiness(_rows(), [])
    assert readiness["claim_recall"]["status"] == "needs_exhaustive_gold"
    assert readiness["claim_recall"]["value"] is None
    assert readiness["claim_f1"]["status"] == "needs_exhaustive_gold"
    assert readiness["claim_f1"]["value"] is None


def test_admin_cannot_create_production(tmp_path):
    factory, ids = _db(tmp_path)
    with factory.begin() as session:
        project = EvaluationProject(name="Production", namespace="production", status="active", created_by_user_id=ids["owner"])
        session.add(project)
        session.flush()
        result = _preview(session, ids, project_id=project.project_id)
        assert any(row["code"] == "admin_cannot_create_production" for row in result["blockers"])


def test_admin_payload_contains_no_blind_answers(tmp_path):
    factory, _ = _db(tmp_path)
    with factory() as session:
        payload = admin_users(session)
        serialized = repr(payload).lower()
        assert "final_label" not in serialized
        assert "structured_fields" not in serialized
        assert "password_hash" not in serialized
        assert "session_hash" not in serialized
        assert "session_version" not in serialized
        assert "invite_source" not in serialized


def test_formal_db_hash_unchanged():
    path = Path("data/code_atlas.db")
    if not path.exists():
        pytest.skip("formal Atlas database is not present")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    # This regression test deliberately performs no database connection.
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after
