"""Focused integrity tests for the authorized v2.2 recall-tail probe."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v1"
SOURCE = ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1"
CASES = {"spv2_017", "spv2_016", "spv2_003"}
REQUIRED = {
    "baseline.json", "probe_case_inventory.json", "original_retrieval_state.jsonl",
    "continued_query_executions.jsonl", "tail_metadata_inventory.jsonl",
    "tail_abstract_screening.jsonl", "tail_v22_gate_outputs.jsonl",
    "tail_fulltext_acquisition_attempts.jsonl", "tail_fulltext_manifest.jsonl",
    "tail_review_packets.jsonl", "depth_bin_metrics.jsonl", "query_tail_contribution.jsonl",
    "tail_saturation_audit.jsonl", "budget_recommendation.json", "network_usage_audit.json",
    "provider_usage_audit.json", "scientific_state_safety_audit.json", "final_validation.json",
    "manifest.json", "summary.json",
}


def j(name): return json.loads((RUN / name).read_text(encoding="utf-8"))
def jl(name): return [json.loads(x) for x in (RUN / name).read_text(encoding="utf-8").splitlines() if x]
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RecallTailProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (RUN / "manifest.json").exists(): raise unittest.SkipTest("tail probe not generated")

    def test_required_artifacts_and_manifest(self):
        self.assertFalse(REQUIRED - {p.name for p in RUN.iterdir() if p.is_file()})
        manifest = j("manifest.json")
        self.assertEqual(manifest["required_artifact_count"], len(REQUIRED))
        for row in manifest["files"]: self.assertEqual(digest(RUN / row["path"]), row["sha256"])
        for row in manifest["retrieval_assets"]: self.assertEqual(digest(ROOT / row["path"]), row["sha256"])
        self.assertEqual(j("final_validation.json")["status"], "PASS")
        self.assertTrue(all(j("final_validation.json")["checks"].values()))

    def test_exact_cases_and_depth(self):
        metadata = jl("tail_metadata_inventory.jsonl")
        self.assertEqual({x["case_id"] for x in metadata}, CASES)
        for case in CASES:
            rows = [x for x in metadata if x["case_id"] == case]
            self.assertEqual(len(rows), 60)
            self.assertEqual([x["metadata_depth"] for x in rows], list(range(61, 121)))
            self.assertEqual(len({x["pmid"] for x in rows}), 60)
        self.assertEqual(j("summary.json")["new_case_publication_count"], 180)

    def test_only_frozen_query_continuations(self):
        original = {x["query_variant_id"]: x for x in
                    [json.loads(s) for s in (SOURCE / "executed_queries.jsonl").read_text().splitlines()]}
        rows = jl("continued_query_executions.jsonl")
        for row in rows:
            prior = original[row["query_variant_id"]]
            self.assertEqual(row["query_string"], prior["query_string"])
            self.assertEqual(row["retmax"], 20)
            if prior["execution_status"] == "executed": self.assertGreaterEqual(row["retstart"], 20)
            else: self.assertEqual(row["continuation_reason"], "budget_stopped_before_first_page")
            self.assertFalse(row["original_records_retrieved_again"])
        self.assertTrue(all(x["query_text_or_order_modified"] is False for x in jl("query_tail_contribution.jsonl")))

    def test_abstract_and_gate_bijection_and_exact_evidence(self):
        metadata = jl("tail_metadata_inventory.jsonl"); screens = jl("tail_abstract_screening.jsonl")
        outputs = jl("tail_v22_gate_outputs.jsonl")
        keys = lambda rows: {(x["case_id"], x["pmid"]) for x in rows}
        self.assertEqual(keys(metadata), keys(screens)); self.assertEqual(keys(metadata), keys(outputs))
        inputs = {(x["case_id"], x["pmid"]): json.loads((ROOT / x["pre_acquisition_evidence_refs"]["abstract"]["path"]).read_text()) for x in outputs}
        for row in outputs:
            pub = inputs[(row["case_id"], row["pmid"])]
            for gate in row["gates"].values():
                for evidence in gate["evidence"]:
                    if evidence["field"] in {"title", "abstract"}:
                        self.assertEqual(pub[evidence["field"]][evidence["start"]:evidence["end"]], evidence["quote"])
                    elif evidence["field"] == "publication_types":
                        self.assertEqual(pub["publication_types"][evidence["index"]], evidence["quote"])
            if row["state"] == "TIER_B":
                self.assertTrue(row["known_plausible_fields"])
                self.assertTrue(row["unresolved_fields_requiring_fulltext"])
                self.assertTrue(row["why_fulltext_can_resolve"])
            if row["state"] == "REJECT": self.assertTrue(row["reject_gate_names"])

    def test_fulltext_budget_identity_hash_and_neutral_packets(self):
        attempts = jl("tail_fulltext_acquisition_attempts.jsonl"); acquired = jl("tail_fulltext_manifest.jsonl")
        for case in CASES: self.assertLessEqual(sum(x["case_id"] == case for x in attempts), 10)
        acquired_keys = {(x["case_id"], x["pmid"]) for x in acquired}
        self.assertEqual(acquired_keys, {(x["case_id"], x["publication_identity"]["pmid"]) for x in jl("tail_review_packets.jsonl")})
        for row in acquired:
            self.assertEqual(digest(ROOT / row["snapshot_ref"]), row["content_hash"])
            self.assertEqual(row["status"], "fulltext_acquired")
        for packet in jl("tail_review_packets.jsonl"):
            self.assertIsNone(packet["automatic_relevance_prediction"])
            self.assertIsNone(packet["adjudication"]["relevance_state"])
            self.assertIsNone(packet["adjudication"]["acquisition_decision"])
            self.assertFalse(packet["fulltext_evidence_packet"]["excerpts"])
            self.assertFalse(packet["fulltext_evidence_packet"]["experimental_extraction_performed"])

    def test_metrics_recompute(self):
        screens = jl("tail_abstract_screening.jsonl"); outputs = jl("tail_v22_gate_outputs.jsonl")
        acquired = jl("tail_fulltext_manifest.jsonl"); summary = j("summary.json")
        self.assertEqual(summary["new_abstract_plausible_count"], sum(x["screen_state"] in {"abstract_high_plausibility", "abstract_possible"} for x in screens))
        self.assertEqual(summary["new_tier_a_count"], sum(x["state"] == "TIER_A" for x in outputs))
        self.assertEqual(summary["new_tier_b_count"], sum(x["state"] == "TIER_B" for x in outputs))
        self.assertEqual(summary["new_fulltext_count"], len(acquired))
        bins = jl("depth_bin_metrics.jsonl")
        self.assertEqual(Counter((x["case_id"], x["depth_bin"]) for x in bins), Counter({(c, b): 1 for c in CASES for b in ["1-30", "31-60", "61-90", "91-120"]}))
        self.assertTrue(all(x["abstract_plausible_publications"] is None for x in bins if x["depth_bin"] == "31-60"))

    def test_network_and_scientific_boundaries(self):
        network = j("network_usage_audit.json"); provider = j("provider_usage_audit.json")
        self.assertTrue(network["authorized"]); self.assertTrue(network["allowed_services_only"])
        self.assertFalse(network["original_depth_1_60_retrieval_repeated"])
        self.assertEqual(provider["provider_calls"], 0); self.assertEqual(provider["llm_calls"], 0)
        self.assertFalse(provider["experimental_extraction_invoked"])
        safety = j("scientific_state_safety_audit.json")
        self.assertFalse(safety["historical_assets_modified"]); self.assertTrue(safety["frozen_sources_unchanged"])
        self.assertFalse(safety["search_plan_tuning_performed"]); self.assertFalse(safety["case_specific_fix_performed"])
        self.assertFalse(j("summary.json")["heldout_v22_validation"])


if __name__ == "__main__": unittest.main()
