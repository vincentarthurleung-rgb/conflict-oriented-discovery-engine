import json
import unittest
from pathlib import Path

from code_engine.search.search_plan_replay import load_frozen_search_plan


class Case002SearchPlanTests(unittest.TestCase):
    def setUp(self):
        self.path = Path("configs/search_plans/autophagy_cancer_chemoresistance_2000_2020.llm_v1.frozen.json")
        self.payload = json.loads(self.path.read_text(encoding="utf-8"))

    def test_frozen_plan_metadata_and_window(self):
        self.assertTrue(self.path.is_file()); self.assertTrue(self.payload["frozen"])
        self.assertEqual(self.payload["artifact_schema_version"], "frozen_search_plan.v1")
        self.assertEqual(self.payload["case_id"], "autophagy_cancer_chemoresistance")
        self.assertEqual((self.payload["paper_year_from"], self.payload["paper_year_to"]), (2000, 2020))
        self.assertEqual(self.payload["planner_mode"], "llm_semantic")
        self.assertGreaterEqual(self.payload["query_count"], 4)
        plan, replay = load_frozen_search_plan(self.path, fail_if_drift=True)
        self.assertEqual(len(plan.pubmed_queries), self.payload["query_count"])
        self.assertFalse(replay["search_plan_drift_detected"])

    def test_plan_covers_both_sides_without_being_placeholder(self):
        groups = {item["query_group"] for item in self.payload["pubmed_queries"]}
        self.assertIn("pro_survival_chemoresistance", groups)
        self.assertIn("pro_death_sensitization", groups)
        self.assertIn("tumor_suppressive", groups)
        self.assertNotEqual(self.payload.get("plan_status"), "placeholder")
        self.assertTrue(self.payload["semantic_search_intent"]["llm_search_intent_used"])


if __name__ == "__main__": unittest.main()
