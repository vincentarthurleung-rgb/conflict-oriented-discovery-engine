import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.steps import run_search_step
from tests.search_intent_helpers import prepare


class FakePlanner:
    def extract_json(self, prompt):
        return {"seed_triple": {"subject": {"name": "metformin"},
                "relation": {"name": "activates", "directional": "subject>object"},
                "object": {"name": "AMPK"}},
                "query_groups": {"direct_relation": [
                    {"query": "AMPK AND cancer", "purpose": "find evidence", "allowed_for_l1_acquisition": True},
                    {"query": "metformin AND AMPK AND cancer", "purpose": "find evidence", "allowed_for_l1_acquisition": True}]}}


class GuardAfterNormalizationTests(unittest.TestCase):
    def test_guard_removes_off_seed_and_plan_survives(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); prepare(run)
            result = run_search_step(run_dir=run, execute=True, api=True, network=True, max_papers=5,
                                     semantic_llm_client=FakePlanner(), query="metformin AMPK cancer")
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.summary["query_guard"]["off_seed_queries_removed"], 1)
            self.assertTrue((run / "artifacts/search_plan.json").exists())
            self.assertEqual(result.api_calls_made, 1)


if __name__ == "__main__": unittest.main()
