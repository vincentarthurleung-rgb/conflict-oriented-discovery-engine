"""Focused invariants for the authorized held-out v1 PubMed/PMC run."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline"
RUN = ROOT / "runs/20260909_search_plan_v22_heldout_v1_network_retrieval"
EXPECTED = "2aac90361272de64eb055099602ae68e696c760628fec3835c0f29eca63ca127"
REQUIRED = {
    "protocol_verification.json", "freeze_hash_verification.json",
    "heldout_case_execution_inventory.jsonl", "query_execution_log.jsonl",
    "metadata_inventory.jsonl", "abstract_screening.jsonl", "v22_gate_outputs.jsonl",
    "case_retrieval_metrics.jsonl", "ambiguity_retrieval_metrics.jsonl",
    "fulltext_selection_inventory.jsonl", "fulltext_acquisition_attempts.jsonl",
    "fulltext_manifest.jsonl", "neutral_review_packets.jsonl", "network_usage_audit.json",
    "provider_usage_audit.json", "protocol_leakage_audit.json",
    "scientific_state_safety_audit.json", "validation.json", "manifest.json", "summary.json",
}


def j(name):
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def jl(name):
    return [json.loads(line) for line in (RUN / name).read_text(encoding="utf-8").splitlines() if line]


def frozen_jl(name):
    return [json.loads(line) for line in (FREEZE / name).read_text(encoding="utf-8").splitlines() if line]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class HeldoutV1NetworkRetrievalTests(unittest.TestCase):
    def test_frozen_protocol_and_queries(self):
        protocol = j("protocol_verification.json")
        self.assertTrue(protocol["explicit_user_network_authorization"])
        self.assertTrue(protocol["protocol_hash_match"])
        self.assertEqual(protocol["recomputed_protocol_sha256"], EXPECTED)
        self.assertEqual(protocol["frozen_query_count"], 48)
        hashes = j("freeze_hash_verification.json")
        self.assertTrue(hashes["protocol_hash_match"])
        self.assertTrue(hashes["gate_hash_match"])
        self.assertTrue(all(row["match"] for row in hashes["components"]))
        frozen = {row["query_variant_id"]: row for row in frozen_jl("heldout_frozen_queries.jsonl")}
        logs = jl("query_execution_log.jsonl")
        executed = {row["query_variant_id"] for row in logs if row["execution_status"] == "executed"}
        self.assertEqual(executed, set(frozen))
        for row in logs:
            source = frozen[row["query_variant_id"]]
            self.assertEqual((row["query_text"], row["sort"], row["query_order"]),
                             (source["query_text"], source["sort"], source["query_order"]))
            self.assertFalse(row["query_modified"])

    def test_metadata_depth_and_natural_exhaustion(self):
        metrics = jl("case_retrieval_metrics.jsonl")
        self.assertEqual(len(metrics), 8)
        counts = {row["case_id"]: row["unique_metadata_records"] for row in metrics}
        self.assertEqual(counts, {
            "heldout_v1_001": 180, "heldout_v1_002": 180, "heldout_v1_003": 180,
            "heldout_v1_004": 148, "heldout_v1_005": 11, "heldout_v1_006": 13,
            "heldout_v1_007": 180, "heldout_v1_008": 180,
        })
        self.assertTrue(all(value <= 180 for value in counts.values()))
        exhausted = {row["case_id"] for row in metrics if row["natural_exhaustion"]}
        self.assertEqual(exhausted, {"heldout_v1_004", "heldout_v1_005", "heldout_v1_006"})
        self.assertTrue(all(not row["adaptive_early_stop_used"] for row in metrics))
        metadata = jl("metadata_inventory.jsonl")
        self.assertEqual(len(metadata), 1072)
        for case_id, count in counts.items():
            self.assertEqual([row["metadata_depth"] for row in metadata if row["case_id"] == case_id],
                             list(range(1, count + 1)))
        self.assertTrue(all(row["metadata_resolved"] for row in metadata))

    def test_gate_funnel_is_descriptive_only(self):
        gates = jl("v22_gate_outputs.jsonl")
        self.assertEqual(len(gates), 1072)
        self.assertEqual(Counter(row["state"] for row in gates),
                         {"TIER_A": 142, "TIER_B": 772, "REJECT": 125, None: 33})
        self.assertTrue(all(not row["fulltext_facts_used"] for row in gates))
        self.assertTrue(all(not row["reviewer_labels_used"] for row in gates))
        self.assertTrue(all(not row["previous_calibration_rationale_used"] for row in gates))
        summary = j("summary.json")
        self.assertFalse(summary["relevance_metrics_calculated"])
        self.assertFalse(summary["heldout_relevance_conclusion_created"])
        self.assertFalse(summary["preregistered_heuristic_pass_fail_calculated"])
        self.assertEqual(summary["neutral_review_batch_state"], "GENERATED_PENDING_SEPARATE_FREEZE")

    def test_bounded_oa_acquisition_and_neutral_packets(self):
        selections = jl("fulltext_selection_inventory.jsonl")
        selected = [row for row in selections if row["selected"]]
        attempts = jl("fulltext_acquisition_attempts.jsonl")
        acquired = jl("fulltext_manifest.jsonl")
        packets = jl("neutral_review_packets.jsonl")
        self.assertEqual((len(selected), len(attempts), len(acquired), len(packets)), (70, 70, 70, 70))
        for case_id in {row["case_id"] for row in selected}:
            self.assertLessEqual(sum(row["case_id"] == case_id for row in selected), 10)
        self.assertTrue(all(row["tier_state"] in {"TIER_A", "TIER_B"} for row in selected))
        self.assertTrue(all(row["pmcid_available"] and not row["no_pmcid"] for row in selected))
        self.assertTrue(all(row["acquired"] and not row["retrieval_failure"] for row in attempts))
        for packet in packets:
            adjudication = packet["adjudication"]
            self.assertTrue(all(adjudication[field] is None for field in
                                ("relevance_state", "acquisition_decision", "contaminant_class",
                                 "reviewer_rationale", "confidence")))
            self.assertIsNone(packet["automatic_relevance_prediction"])
            self.assertIsNone(packet["acquisition_quality_prediction"])
            self.assertIsNone(packet["confidence_prediction"])
            self.assertFalse(packet["scientific_extraction_performed"])

    def test_network_prohibitions_validation_and_manifest(self):
        network = j("network_usage_audit.json")
        self.assertTrue(network["authorized"])
        self.assertTrue(network["allowed_services_only"])
        self.assertEqual(network["successful_network_response_count"], 156)
        self.assertEqual(network["request_counts_by_kind"], {
            "pubmed_esearch_heldout_v1": 75,
            "pubmed_efetch_heldout_v1": 11,
            "pmc_fulltext_efetch_heldout_v1": 70,
        })
        self.assertEqual(network["general_web_fallback_calls"], 0)
        self.assertEqual(network["publisher_fallback_calls"], 0)
        provider = j("provider_usage_audit.json")
        for key in ("provider_calls", "llm_calls", "scientific_extraction_calls", "relevance_prediction_calls"):
            self.assertEqual(provider[key], 0)
        leakage = j("protocol_leakage_audit.json")
        self.assertEqual(leakage["status"], "NO_PROTOCOL_LEAKAGE")
        for key in ("query_modifications", "target_modifications", "gate_modifications",
                    "budget_modifications", "case_replacements"):
            self.assertEqual(leakage[key], 0)
        safety = j("scientific_state_safety_audit.json")
        self.assertFalse(safety["historical_assets_modified"])
        self.assertFalse(safety["relevance_labels_created"])
        validation = j("validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        manifest = j("manifest.json")
        self.assertEqual(manifest["required_artifact_count"], 20)
        self.assertEqual(set(manifest["required_artifacts"]), REQUIRED)
        self.assertTrue(all(sha(RUN / row["path"]) == row["sha256"] for row in manifest["files"]))


if __name__ == "__main__":
    unittest.main()
