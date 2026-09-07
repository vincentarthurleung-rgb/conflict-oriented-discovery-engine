"""Focused invariants for the authorized depth-120-to-180 tail probe."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v2_depth180"
V1 = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v1"


def jl(name): return [json.loads(x) for x in (RUN / name).read_text(encoding="utf-8").splitlines() if x]
def j(name): return json.loads((RUN / name).read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TailProbeV2Tests(unittest.TestCase):
    def test_exact_depth_and_aggregate_counts(self):
        metadata = jl("tail_metadata_121_180.jsonl")
        summary = j("summary.json")
        self.assertEqual(len(metadata), 180)
        for case_id in ["spv2_017", "spv2_016", "spv2_003"]:
            self.assertEqual([x["metadata_depth"] for x in metadata if x["case_id"] == case_id], list(range(121, 181)))
        self.assertEqual(summary["new_tier_a_count"], 17)
        self.assertEqual(summary["new_tier_b_count"], 90)
        self.assertEqual(summary["new_reject_count"], 52)
        self.assertEqual(summary["new_not_admitted_insufficient_plausibility_count"], 21)

    def test_frozen_queries_and_continuation_offsets(self):
        state = {(x["case_id"], x["query_variant_id"]): x for x in jl("continuation_state.jsonl")}
        executions = jl("continued_query_executions.jsonl")
        v1 = jl_from(V1 / "continued_query_executions.jsonl")
        for row in executions:
            prior = [x for x in v1 if x["case_id"] == row["case_id"] and x["query_variant_id"] == row["query_variant_id"] and x["execution_status"] == "executed"]
            if prior:
                last = max(prior, key=lambda x: x["retstart"])
                self.assertGreaterEqual(row["retstart"], last["retstart"] + last["returned_id_count"])
            self.assertEqual(row["query_string"], state[(row["case_id"], row["query_variant_id"])]["query_string"])
            self.assertFalse(row["prior_pages_repeated"])

    def test_gate_selection_and_neutral_packets(self):
        gates = jl("tail_v22_gate_outputs_121_180.jsonl")
        candidates = jl("tail_acquisition_candidate_inventory.jsonl")
        attempts = jl("tail_fulltext_acquisition_attempts.jsonl")
        packets = jl("tail_review_packets.jsonl")
        self.assertEqual(sum(x["state"] in {"TIER_A", "TIER_B"} for x in gates), len(candidates))
        self.assertEqual(len(attempts), 30)
        self.assertEqual(len(packets), 17)
        for case_id in {x["case_id"] for x in attempts}:
            self.assertLessEqual(sum(x["case_id"] == case_id for x in attempts), 10)
        self.assertTrue(all(not x["predicted_relevance_used"] for x in candidates))
        self.assertTrue(all(x["adjudication"]["relevance_state"] is None and
                            x["adjudication"]["acquisition_decision"] is None and
                            x["automatic_relevance_prediction"] is None and
                            x["manual_relevance_status"] == "pending" for x in packets))

    def test_candidate_states_and_previous_context_only(self):
        saturation = jl("tail_candidate_saturation_audit.jsonl")
        self.assertEqual({x["tail_candidate_state"] for x in saturation}, {"TAIL_CANDIDATE_YIELD_ACTIVE"})
        self.assertTrue(all(not x["scientific_relevance_saturation_inferred"] for x in saturation))
        linkage = j("previous_tail_adjudication_linkage.json")
        self.assertEqual(linkage["deepest_adjudicated_direct_relevance_depth"], 101)
        self.assertFalse(linkage["used_as_retrieval_or_gate_input"])
        self.assertEqual(j("budget_recommendation_pre_adjudication.json")["candidate_future_budget_policy"],
                         "TAIL_CALIBRATION_STILL_INSUFFICIENT")

    def test_network_safety_validation_and_manifest(self):
        network = j("network_usage_audit.json")
        self.assertEqual(network["network_request_count"], 31)
        self.assertEqual(network["failed_network_attempt_count"], 0)
        self.assertTrue(network["allowed_services_only"])
        summary = j("summary.json")
        self.assertEqual((summary["provider_calls"], summary["llm_calls"], summary["extraction_calls"]), (0, 0, 0))
        self.assertFalse(summary["historical_assets_modified"])
        validation = j("final_validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        manifest = j("manifest.json")
        self.assertEqual(manifest["required_artifact_count"], 23)
        self.assertTrue(all(sha(RUN / x["path"]) == x["sha256"] for x in manifest["files"]))


def jl_from(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]


if __name__ == "__main__": unittest.main()
