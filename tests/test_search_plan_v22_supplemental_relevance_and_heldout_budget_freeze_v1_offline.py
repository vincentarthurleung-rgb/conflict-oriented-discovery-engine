"""Focused checks for supplemental adjudication and held-out budget freeze."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260909_search_plan_v22_depth180_supplemental_relevance_adjudication_v1_offline"
SOURCE = ROOT / "runs/20260908_search_plan_v22_depth180_supplemental_relevance_packaging_v1_offline/supplemental_review_packets.jsonl"


def jl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]
def j(name): return json.loads((RUN/name).read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SupplementalRelevanceFreezeTests(unittest.TestCase):
    def test_exact_order_labels_and_reviewer(self):
        source, rows = jl(SOURCE), jl(RUN/"supplemental_adjudications.jsonl")
        self.assertEqual([x["packet_id"] for x in source], [x["packet_id"] for x in rows])
        self.assertEqual(len(rows), len({x["packet_id"] for x in rows}))
        self.assertEqual(len(rows), 7)
        self.assertEqual(sum(x["relevance_state"] == "DIRECTLY_RELEVANT" for x in rows), 5)
        self.assertEqual(sum(x["relevance_state"] == "RELATED_BUT_WRONG_PROPOSITION" for x in rows), 2)
        self.assertTrue(all(x["reviewer_type"] == "model_retrieval_adjudicator" for x in rows))
        self.assertTrue(all(x["confidence"] in {"high","moderate-high"} for x in rows))

    def test_balanced_depth_sample(self):
        rows = jl(RUN/"balanced_depth_151_180_adjudications.jsonl")
        self.assertEqual(len(rows), 9)
        self.assertEqual(sum(x["relevance_state"] == "DIRECTLY_RELEVANT" for x in rows), 6)
        expected = {"spv2_017": (3,2), "spv2_016": (3,1), "spv2_003": (3,3)}
        for cid, pair in expected.items():
            case = [x for x in rows if x["case_id"] == cid]
            self.assertEqual((len(case), sum(x["relevance_state"] == "DIRECTLY_RELEVANT" for x in case)), pair)
        self.assertEqual(max(x["metadata_depth"] for x in rows if x["relevance_state"] == "DIRECTLY_RELEVANT"), 171)
        self.assertEqual(sum(x["tier_state"] == "TIER_A" for x in rows), 2)
        self.assertEqual(sum(x["tier_state"] == "TIER_B" for x in rows), 7)

    def test_depth_calibration_limits_claims(self):
        depth = j("depth_calibration_summary.json")
        windows = {x["depth_window"]: (x["count"],x["directly_relevant_count"]) for x in depth["observed_adjudicated_windows"]}
        self.assertEqual(windows, {"61-120":(15,10), "121-150":(15,8), "151-180":(9,6)})
        self.assertIsNone(depth["historically_unadjudicated_depth_31_60"]["result"])
        self.assertFalse(depth["monotonicity_claimed"])
        self.assertFalse(depth["true_precision_or_recall_claimed"])
        self.assertFalse(depth["scientific_saturation_at_180_established"])

    def test_heldout_budget_protocol_and_freeze(self):
        protocol = j("heldout_retrieval_budget_protocol_v1.json")
        self.assertEqual(protocol["metadata_soft_checkpoint"], 120)
        self.assertEqual(protocol["metadata_hard_safety_ceiling"], 180)
        self.assertFalse(protocol["retrieval_beyond_180_allowed"])
        self.assertEqual(protocol["adaptive_early_stop_state"], "deferred")
        self.assertTrue(protocol["heldout_budget_frozen"])
        self.assertFalse(protocol["heldout_validation_started"])
        self.assertIn("spv2_017", protocol["excluded_calibration_case_ids"])
        self.assertEqual(protocol["deferred_not_heldout_case_ids"], ["spv2_019"])
        audit = j("calibration_to_heldout_freeze_audit.json")
        self.assertEqual(audit["status"], "PASS")
        self.assertTrue(audit["no_adaptive_threshold_fitted_to_three_case_yields"])
        self.assertTrue(audit["future_heldout_cases_require_unseen_propositions"])

    def test_safety_validation_and_manifest(self):
        summary = j("summary.json")
        self.assertFalse(summary["scientific_saturation_at_180_established"])
        self.assertFalse(summary["true_tail_precision_or_recall_claimed"])
        self.assertEqual(summary["search_plan_v22_activation_state"], "candidate_not_activated")
        for key in ["network_calls","provider_calls","llm_calls","downloads","extraction_calls"]:
            self.assertEqual(summary[key], 0)
        self.assertFalse(summary["historical_assets_modified"])
        validation = j("validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        manifest = j("manifest.json")
        self.assertEqual(manifest["required_artifact_count"], 16)
        self.assertTrue(all(sha(RUN/x["path"]) == x["sha256"] for x in manifest["files"]))


if __name__ == "__main__": unittest.main()
