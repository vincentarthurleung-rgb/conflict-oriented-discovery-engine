import csv
import json
import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.review_queue import discover_bundles, generate


class SystemBReviewQueueTests(unittest.TestCase):
    def make_bundle(self, root: Path) -> Path:
        bundle = root / "nested" / "case_one"; bundle.mkdir(parents=True)
        (bundle / "case_bundle_manifest.json").write_text(json.dumps({
            "case_id": "case_one", "pipeline_complete": True, "ready_for_system_b": True,
            "raw_l1_claim_count": 9, "reviewable_graph_observation_count": 2,
            "fulltext_l1_claim_count": 3, "weak_conflict_candidate_count": 0,
            "non_comparable_direction_pair_count": 1,
        }))
        claims = [{"pmid": str(i), "claim_text": f"claim {i}"} for i in range(5)]
        (bundle / "l35_fulltext_discovery_l1_claims.jsonl").write_text("".join(json.dumps(x) + "\n" for x in claims))
        observations = [{"subject": "A", "predicate": "increases", "object": "B", "score": score} for score in (1, 3, 2)]
        (bundle / "l2_reviewable_graph_observations.jsonl").write_text("".join(json.dumps(x) + "\n" for x in observations))
        (bundle / "weak_conflict_candidates.jsonl").write_text("")
        (bundle / "non_comparable_direction_pairs.jsonl").write_text(json.dumps({"observation_a": {"id": 1}, "observation_b": {"id": 2}, "rejection_reason": "context"}) + "\n")
        return bundle

    def test_nested_discovery_missing_files_outputs_metrics_and_stability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); bundle = self.make_bundle(root)
            self.assertEqual(discover_bundles([root]), [bundle.resolve()])
            out1, out2 = root / "out1", root / "out2"
            first = generate([root / "nested"], out1, random_fulltext_claims=3)
            second = generate([root / "nested"], out2, random_fulltext_claims=3)
            q1 = [json.loads(x) for x in (out1 / "manual_review_queue.jsonl").read_text().splitlines()]
            q2 = [json.loads(x) for x in (out2 / "manual_review_queue.jsonl").read_text().splitlines()]
            self.assertEqual([x["review_item_id"] for x in q1], [x["review_item_id"] for x in q2])
            self.assertEqual([x["pmid"] for x in q1 if x["item_type"] == "fulltext_l1_claim"], [x["pmid"] for x in q2 if x["item_type"] == "fulltext_l1_claim"])
            self.assertEqual(first["items_by_type"]["non_comparable_direction_pair"], 1)
            self.assertNotIn("weak_candidate", first["items_by_type"])
            for name in ("manual_review_queue.csv", "manual_review_annotations_template.csv", "case_level_metrics.csv", "case_level_metrics.json"):
                self.assertTrue((out1 / name).is_file())
            metrics = json.loads((out1 / "case_level_metrics.json").read_text())[0]
            self.assertEqual(metrics["raw_l1_claim_count"], 9)
            self.assertEqual(metrics["abstract_reviewable_count"], 2)
            summary = json.loads((out1 / "review_sampling_summary.json").read_text())["cases"][0]
            self.assertIn("l35_fulltext_discovery_observations.jsonl", summary["missing_files"])
            with (out1 / "manual_review_annotations_template.csv").open() as handle:
                row = next(csv.DictReader(handle)); self.assertEqual(row["final_label"], "")


if __name__ == "__main__":
    unittest.main()
