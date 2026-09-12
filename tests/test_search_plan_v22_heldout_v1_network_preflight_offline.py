"""Focused checks for held-out v1 offline network preflight."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline"
RUN = ROOT / "runs/20260909_search_plan_v22_heldout_v1_network_preflight_offline"
NETWORK_RUN = ROOT / "runs/20260909_search_plan_v22_heldout_v1_network_retrieval"
EXPECTED = "2aac90361272de64eb055099602ae68e696c760628fec3835c0f29eca63ca127"


def j(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def jl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def object_sha(value):
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


class HeldoutV1NetworkPreflightTests(unittest.TestCase):
    def test_protocol_and_all_component_hashes(self):
        protocol = j(RUN / "protocol_verification.json")
        self.assertEqual(protocol["status"], "PASS")
        self.assertEqual(protocol["expected_protocol_sha256"], EXPECTED)
        self.assertEqual(protocol["recomputed_protocol_sha256"], EXPECTED)
        self.assertTrue(protocol["protocol_hash_match"])
        verification = j(RUN / "freeze_hash_verification.json")
        self.assertEqual(verification["component_count"], 10)
        self.assertTrue(verification["all_component_hashes_match"])
        self.assertTrue(all(row["match"] for row in verification["components"]))
        pairs = [(row["path"], sha(FREEZE / row["path"])) for row in verification["components"]]
        self.assertEqual(object_sha(pairs), EXPECTED)

    def test_counts_budget_and_freeze_flags(self):
        protocol = j(RUN / "protocol_verification.json")
        self.assertEqual(protocol["heldout_case_count"], 8)
        self.assertEqual((protocol["low_count"], protocol["medium_count"], protocol["high_count"]), (2, 2, 4))
        self.assertEqual((protocol["oncology_case_count"], protocol["non_oncology_case_count"]), (2, 6))
        self.assertEqual((protocol["query_family_count"], protocol["query_variant_count"], protocol["frozen_query_count"]), (48, 48, 48))
        self.assertEqual((protocol["metadata_soft_checkpoint"], protocol["metadata_hard_safety_ceiling"]), (120, 180))
        self.assertEqual(protocol["adaptive_early_stop_state"], "deferred")
        self.assertEqual(protocol["max_fulltext_selection_per_case"], 10)
        self.assertFalse(protocol["network_authorized"])

    def test_execution_plan_is_exact_and_unauthorized(self):
        frozen = jl(FREEZE / "heldout_frozen_queries.jsonl")
        plan = jl(RUN / "frozen_network_execution_plan.jsonl")
        self.assertEqual(len(plan), 48)
        for source, row in zip(frozen, plan):
            self.assertEqual(row["execution_order"], source["query_order"])
            self.assertEqual(row["case_id"], source["case_id"])
            self.assertEqual(row["query_family_id"], source["query_family_id"])
            self.assertEqual(row["query_variant_id"], source["query_variant_id"])
            self.assertEqual(row["query_text"], source["query_text"])
            self.assertEqual(row["sort"], source["sort"])
            self.assertFalse(row["network_authorized"])
            self.assertFalse(row["stop_at_soft_checkpoint"])
            self.assertEqual(row["maximum_unique_metadata_records_for_case"], 180)
        cases = jl(RUN / "heldout_case_execution_inventory.jsonl")
        self.assertEqual(len(cases), 8)
        self.assertTrue(all(row["frozen_query_count"] == 6 for row in cases))
        self.assertTrue(all(row["execution_state"] == "AWAITING_EXPLICIT_NETWORK_AUTHORIZATION" for row in cases))
        self.assertTrue(all(not row["network_authorized"] for row in cases))
        self.assertTrue(all(row["max_fulltext_selection"] == 10 for row in cases))

    def test_boundary_gate_and_prohibitions(self):
        boundary = j(RUN / "heldout_boundary_verification.json")
        self.assertEqual(boundary["status"], "PASS")
        self.assertEqual(boundary["prior_heldout_result_artifact_count"], 0)
        self.assertEqual(boundary["prior_heldout_adjudication_count"], 0)
        self.assertEqual(boundary["case_replacement_count"], 0)
        for key in ("query_modifications", "target_modifications", "gate_modifications", "budget_modifications"):
            self.assertEqual(boundary[key], 0)
        self.assertTrue(boundary["gate_hash_match"])
        self.assertFalse(boundary["calibration_tuning_reopened"])
        self.assertFalse(boundary["external_literature_inspected"])
        self.assertFalse(boundary["formal_network_run_exists"])

    def test_safety_validation_and_manifest(self):
        safety = j(RUN / "scientific_state_safety_audit.json")
        self.assertEqual(safety["sections_completed"], [1, 2, 3, 4])
        self.assertTrue(safety["offline_preflight_only"])
        self.assertFalse(safety["network_authorized"])
        for key in ("network_calls", "provider_calls", "llm_calls", "downloads", "extraction_calls"):
            self.assertEqual(safety[key], 0)
        self.assertFalse(safety["retrieval_performed"])
        self.assertFalse(safety["relevance_labels_created"])
        self.assertFalse(safety["historical_assets_modified"])
        validation = j(RUN / "validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        manifest = j(RUN / "manifest.json")
        self.assertEqual(manifest["required_artifact_count"], 9)
        self.assertTrue(all(sha(RUN / row["path"]) == row["sha256"] for row in manifest["files"]))


if __name__ == "__main__":
    unittest.main()
