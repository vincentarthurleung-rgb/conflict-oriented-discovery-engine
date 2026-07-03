import json
import unittest
from pathlib import Path


class Case002SearchPlanReviewTests(unittest.TestCase):
    def test_review_and_diagnostics_are_complete(self):
        root = Path("search_plan_reviews")
        review = json.loads((root / "autophagy_cancer_chemoresistance_search_plan_review.json").read_text(encoding="utf-8"))
        self.assertTrue(review["both_sides_represented"])
        self.assertIn(review["final_review_decision"], {"SEARCH_PLAN_READY", "SEARCH_PLAN_READY_WITH_WARNINGS"})
        self.assertGreaterEqual(len(review["query_families"]), 4)
        diagnostics = [json.loads(line) for line in (root / "autophagy_cancer_chemoresistance_query_diagnostics.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(diagnostics), review["query_count"])
        self.assertTrue(all(item["status"] in {"ok", "zero_hits", "error", "skipped"} for item in diagnostics))


if __name__ == "__main__": unittest.main()
