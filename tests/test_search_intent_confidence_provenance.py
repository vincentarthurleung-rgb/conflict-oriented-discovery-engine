import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.steps import run_search_step
from tests.search_intent_helpers import prepare


class NoConfidencePlanner:
    def extract_json(self, prompt):
        return {"seed_triple": {"subject": {"name": "metformin"},
                "relation": {"name": "activates", "directional": True}, "object": {"name": "AMPK"},
                "context": {"terms": ["cancer"]}}, "query_groups": {"direct_relation": [
                {"query": "metformin AND AMPK AND cancer", "allowed_for_l1_acquisition": True}]}}


class SearchIntentConfidenceProvenanceTests(unittest.TestCase):
    def test_successful_planner_populates_intent_and_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); prepare(run)
            result = run_search_step(run_dir=run, execute=True, api=True, network=True, max_papers=5,
                                     semantic_llm_client=NoConfidencePlanner(), query="metformin AMPK cancer")
            self.assertEqual(result.status, "completed")
            intent = json.loads((run / "artifacts/semantic_search_intent.json").read_text())
            plan = json.loads((run / "artifacts/search_plan.json").read_text())
            self.assertGreater(intent["confidence"], 0)
            self.assertEqual(intent["confidence_source"], "semantic_intake_confidence")
            self.assertTrue(all(q["search_intent_confidence"] == intent["confidence"] for q in plan["pubmed_queries"]))


if __name__ == "__main__": unittest.main()
