import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.steps import run_search_step
from tests.search_intent_helpers import prepare


class Planner:
    def extract_json(self, prompt):
        return {"mode": "llm", "confidence": .8,
                "seed_triple": {"subject": {"name": "metformin"}, "relation": {"name": "activates", "directional": True},
                                "object": {"name": "AMPK"}, "context": {"terms": ["cancer"]}},
                "query_groups": {"direct_relation": [
                    {"query": "metformin AND AMPK AND cancer", "allowed_for_l1_acquisition": True},
                    {"query": "metformin activates AMPK", "allowed_for_l1_acquisition": True}]}}


class SearchPlanProvenanceTests(unittest.TestCase):
    def test_final_plan_contains_only_guarded_actual_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); prepare(run)
            result = run_search_step(run_dir=run, execute=True, api=True, network=True, max_papers=5,
                                     semantic_llm_client=Planner(), query="metformin AMPK cancer",
                                     paper_year_filter={"enabled": True, "paper_year_to": 2020, "temporal_role": "discovery"})
            self.assertEqual(result.status, "completed")
            plan = json.loads((run / "artifacts/search_plan.json").read_text())
            self.assertEqual(plan["query_generation_mode"], "llm")
            self.assertEqual(len(plan["pubmed_queries"]), 2)
            self.assertTrue(all(q["search_intent_mode"] == "llm" and q["passed_query_guard"] for q in plan["pubmed_queries"]))
            self.assertTrue(all(q["paper_year_filter_enabled"] and q["temporal_role"] == "discovery" for q in plan["pubmed_queries"]))
            self.assertTrue(plan["pubmed_queries"][0]["context_strict"])
            self.assertFalse(plan["pubmed_queries"][1]["allowed_for_context_specific_core"])


if __name__ == "__main__": unittest.main()
