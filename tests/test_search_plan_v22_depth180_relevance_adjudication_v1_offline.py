"""Focused invariants for depth-180 adjudication import and supplement planning."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260908_search_plan_v22_depth180_relevance_adjudication_v1_offline"
SOURCE = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v2_depth180/tail_review_packets.jsonl"


def jl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]
def j(name): return json.loads((RUN/name).read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Depth180AdjudicationTests(unittest.TestCase):
    def test_exact_bijection_order_and_reviewer_representation(self):
        source, rows = jl(SOURCE), jl(RUN/"adjudications.jsonl")
        self.assertEqual([x["packet_id"] for x in source], [x["packet_id"] for x in rows])
        self.assertEqual(len(rows), len({x["packet_id"] for x in rows}))
        self.assertEqual(len(rows), 17)
        self.assertTrue(all(x["reviewer_type"] == "model_retrieval_adjudicator" for x in rows))
        self.assertTrue(all(x["confidence"] in {"high", "moderate-high"} for x in rows))
        self.assertTrue(all(x["reviewer_id_or_label"] is None and x["timestamp"] is None for x in rows))

    def test_expected_tier_and_depth_metrics(self):
        tiers = j("tier_metrics.json")
        self.assertEqual((tiers["overall"]["count"], tiers["overall"]["directly_relevant_count"]), (17, 9))
        self.assertEqual((tiers["TIER_A"]["count"], tiers["TIER_A"]["directly_relevant_count"]), (9, 8))
        self.assertEqual((tiers["TIER_B"]["count"], tiers["TIER_B"]["directly_relevant_count"]), (8, 1))
        depth = {x["depth_bin"]: x for x in jl(RUN/"depth_bin_metrics.jsonl")}
        self.assertEqual((depth["121-150"]["count"], depth["121-150"]["directly_relevant_count"]), (15, 8))
        self.assertEqual((depth["151-180"]["count"], depth["151-180"]["directly_relevant_count"]), (2, 1))
        self.assertFalse(depth["151-180"]["stable_precision_estimate_claimed"])
        self.assertEqual(j("summary.json")["deepest_adjudicated_direct_relevance_depth"], 151)

    def test_contaminant_counts(self):
        contaminants = j("contaminant_summary.json")
        self.assertEqual(contaminants["class_counts"], {"association_vs_functional_relation": 6,
                                                        "wrong_biological_unit": 2})
        self.assertEqual(contaminants["per_case"]["spv2_016"], {"association_vs_functional_relation": 6})
        self.assertEqual(contaminants["per_case"]["spv2_017"], {"wrong_biological_unit": 2})

    def test_count_trigger_and_label_blind_selection(self):
        balance = j("supplemental_151_180_balance_summary.json")
        self.assertEqual(balance["trigger_inputs"], {"current_depth_151_180_sample_count": 2, "minimum_count": 6})
        self.assertTrue(balance["supplemental_sampling_required"])
        self.assertFalse(balance["trigger_uses_relevance_labels"])
        self.assertEqual(balance["eligible_candidate_count"], 58)
        self.assertEqual(balance["eligible_with_preserved_pmcid_count"], 31)
        self.assertEqual(balance["supplemental_plan_selected_count"], 7)
        self.assertEqual([x["supplemental_selected_count"] for x in balance["per_case"]], [3, 2, 2])
        self.assertTrue(all(x["shortage_to_ideal"] == 0 for x in balance["per_case"]))
        selected = jl(RUN/"supplemental_151_180_selection_plan.jsonl")
        self.assertTrue(all(x["preserved_pmcid_available"] and not x["label_fields_used"] for x in selected))
        forbidden = {"relevance_state", "acquisition_decision", "reviewer_rationale", "contaminant_class", "confidence", "title"}
        self.assertTrue(all(not (forbidden & set(x)) for x in selected))

    def test_safety_validation_and_manifest(self):
        safety = j("scientific_state_safety_audit.json")
        for key in ["network_calls", "provider_calls", "llm_calls", "downloads", "extraction_calls"]:
            self.assertEqual(safety[key], 0)
        self.assertFalse(safety["human_gold_claimed"])
        self.assertFalse(safety["historical_assets_modified"])
        validation = j("validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        manifest = j("manifest.json")
        self.assertEqual(manifest["required_artifact_count"], 17)
        self.assertTrue(all(sha(RUN/x["path"]) == x["sha256"] for x in manifest["files"]))


if __name__ == "__main__": unittest.main()
