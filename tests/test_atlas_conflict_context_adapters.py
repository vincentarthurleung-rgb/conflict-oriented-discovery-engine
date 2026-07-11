import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.evaluation.adapters.conflict_adapter import build_conflict_rows, conflict_metrics
from code_engine.system_b.evaluation.adapters.context_adapter import build_context_rows, context_metrics, normalize_factor
from code_engine.system_b.persistence.models import EvaluationProject, EvaluationProtocol, GoldRecord, utcnow
from code_engine.system_b.persistence.services.review_service import canonical_json
from tests.atlas_db_test_utils import add_review_item, add_user, migrate, session_for
from tests.test_system_b_knowledge_explorer import write_jsonl


def add_project_protocol(session):
    project = EvaluationProject(project_id="p", name="prod", namespace="production", status="active")
    protocol = EvaluationProtocol(
        protocol_id="proto",
        project_id="p",
        version=1,
        protocol_json="{}",
        case_ids_sha256="case",
        metric_registry_sha256="metric",
        annotation_schema_sha256="schema",
        dataset_split_sha256="split",
        frozen=True,
        frozen_at=utcnow(),
    )
    session.add(project)
    session.add(protocol)


class AtlasConflictContextAdapterTests(unittest.TestCase):
    def test_conflict_adapter_excludes_insufficient_and_non_comparable_is_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            pred_root = Path(tmp) / "pred"
            pred_root.mkdir()
            write_jsonl(pred_root / "conflict_lens_records.jsonl", [
                {"review_item_id": "conflict1", "record_type": "non_comparable_direction_pair"},
                {"review_item_id": "conflict2", "record_type": "weak_candidate"},
            ])
            with Session.begin() as session:
                owner = add_user(session, "owner", "owner")
                add_project_protocol(session)
                add_review_item(session, "conflict1", item_type="conflict_pair")
                add_review_item(session, "conflict2", item_type="conflict_pair")
                session.add(GoldRecord(project_id="p", protocol_id="proto", review_item_id="conflict1", final_gold_label="different_context_non_comparable", structured_gold_json=canonical_json({"true_conflict": False, "non_conflict_reason": "different_context_non_comparable"}), schema_id="conflict_pair_v1", schema_version="1.0.0", schema_hash="h", status="frozen", frozen_by_user_id=owner.user_id, candidate_revision=1, gold_dataset_version=1, gold_version=1))
                session.add(GoldRecord(project_id="p", protocol_id="proto", review_item_id="conflict2", final_gold_label="insufficient_information", structured_gold_json=canonical_json({"true_conflict": False, "non_conflict_reason": "insufficient_information"}), schema_id="conflict_pair_v1", schema_version="1.0.0", schema_hash="h", status="frozen", frozen_by_user_id=owner.user_id, candidate_revision=1, gold_dataset_version=1, gold_version=1))
                session.flush()
                result = build_conflict_rows(session, project_id="p", gold_dataset_version=1, prediction_root=pred_root)
                self.assertEqual(result["status"], "ready")
                self.assertEqual(result["items"][0]["gold_label"], "different_context_non_comparable")
                self.assertTrue(result["items"][0]["included"])
                self.assertFalse(result["items"][1]["included"])
                self.assertEqual(result["items"][1]["exclusion_reason"], "gold_insufficient_information")
                metrics = conflict_metrics(result["items"])
                self.assertEqual(metrics["conflict_auprc"]["status"], "not_applicable")

    def test_context_alias_mapping_and_metrics(self):
        self.assertEqual(normalize_factor("time"), ("duration", "alias"))
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            pred_root = Path(tmp) / "pred"
            pred_root.mkdir()
            write_jsonl(pred_root / "triple_contexts.jsonl", [{"review_item_id": "ctx1", "context_factors": ["cell_type", "time", "method"]}])
            with Session.begin() as session:
                owner = add_user(session, "owner", "owner")
                add_project_protocol(session)
                add_review_item(session, "ctx1", item_type="context_attribution")
                session.add(GoldRecord(project_id="p", protocol_id="proto", review_item_id="ctx1", final_gold_label="VALID", structured_gold_json=canonical_json({"gold_context_factors": ["cell_type", "duration"], "minimal_context_set": ["cell_type", "duration"], "insufficient_context_information": False}), schema_id="context_attribution_v1", schema_version="1.0.0", schema_hash="h", status="frozen", frozen_by_user_id=owner.user_id, candidate_revision=1, gold_dataset_version=1, gold_version=1))
                session.flush()
                result = build_context_rows(session, project_id="p", gold_dataset_version=1, prediction_root=pred_root)
                self.assertEqual(result["status"], "ready")
                self.assertIn("duration", result["items"][0]["predicted_ranked_factors"])
                metrics = context_metrics(result["items"])
                self.assertEqual(metrics["context_recall_at_3"]["status"], "ready")
                self.assertGreater(metrics["context_set_jaccard"]["value"], 0)


if __name__ == "__main__":
    unittest.main()
