"""Focused checks for the immutable tail adjudication overlay."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v1/tail_review_packets.jsonl"
PACKAGING = ROOT / "runs/20260907_search_plan_v22_recall_tail_relevance_packaging_v1_offline"
RUN = ROOT / "runs/20260907_search_plan_v22_recall_tail_relevance_adjudication_v1_offline"


def jl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]


def j(name):
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TailAdjudicationTests(unittest.TestCase):
    def test_exact_bijection_and_identity_join(self):
        source, rows = jl(SOURCE), jl(RUN / "adjudications.jsonl")
        self.assertEqual([x["packet_id"] for x in source], [x["packet_id"] for x in rows])
        self.assertEqual(len(rows), 15)
        for packet, row in zip(source, rows):
            self.assertEqual(row["case_id"], packet["adjudication"]["case_id"])
            self.assertEqual(row["publication_id"], packet["adjudication"]["publication_id"])

    def test_submitted_outcomes_and_tail_metrics(self):
        metrics = j("tail_relevance_metrics.json")
        self.assertEqual(metrics["directly_relevant_count"], 10)
        self.assertEqual(metrics["acquisition_acceptable_count"], 10)
        self.assertEqual(metrics["relevance_state_counts"], {
            "DIRECTLY_RELEVANT": 10, "RELATED_BUT_WRONG_PROPOSITION": 4, "WRONG_ENDPOINT": 1})
        self.assertEqual(metrics["tier_direct_relevance"]["TIER_A"], {"numerator": 9, "denominator": 10, "value": .9})
        self.assertEqual(metrics["tier_direct_relevance"]["TIER_B"], {"numerator": 1, "denominator": 5, "value": .2})
        self.assertEqual(metrics["max_depth_with_direct_relevance"], 101)
        self.assertFalse(metrics["scientific_recall_completeness_claimed"])
        self.assertFalse(metrics["search_plan_or_budget_changed"])

    def test_per_case_and_depth_yield(self):
        cases = {x["case_id"]: x for x in jl(RUN / "per_case_metrics.jsonl")}
        self.assertEqual({k: v["directly_relevant"] for k, v in cases.items()},
                         {"spv2_003": 5, "spv2_016": 2, "spv2_017": 3})
        depth = {(x["case_id"], x["depth_bin"]): x for x in jl(RUN / "depth_bin_relevance_yield.jsonl")}
        self.assertEqual(depth[("spv2_017", "91-120")]["directly_relevant"], 1)
        self.assertEqual(depth[("spv2_003", "91-120")]["directly_relevant"], 0)
        self.assertTrue(all(not x["scientific_recall_or_saturation_inferred"] for x in depth.values()))

    def test_submission_provenance_and_immutability(self):
        baseline = j("baseline.json")
        self.assertEqual(baseline["submission_sha256"], sha(RUN / "submitted_adjudications.txt"))
        self.assertEqual(baseline["source_tail_packets_sha256"], sha(SOURCE))
        self.assertEqual(baseline["source_packaging_tree"], tree_hash(PACKAGING))
        validation = j("validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))

    def test_manifest_and_safety(self):
        manifest = j("manifest.json")
        self.assertEqual(manifest["required_artifact_count"], 11)
        self.assertTrue(all(sha(RUN / row["path"]) == row["sha256"] for row in manifest["files"]))
        safety = j("safety_audit.json")
        for key in ["network_calls", "provider_calls", "llm_calls", "downloads", "experimental_extraction_calls"]:
            self.assertEqual(safety[key], 0)
        self.assertFalse(safety["search_plan_tuning_performed"])
        self.assertFalse(safety["case_specific_fix_performed"])


def tree_hash(path):
    rows = [(str(item.relative_to(path)), sha(item)) for item in sorted(path.rglob("*")) if item.is_file()]
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"file_count": len(rows), "sha256": digest}


if __name__ == "__main__":
    unittest.main()
