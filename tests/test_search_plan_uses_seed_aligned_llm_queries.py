import tempfile, unittest
from pathlib import Path
from code_engine.workflow.steps import run_search_step
from tests.search_intent_helpers import FakePlanner, prepare

class AlignedPlanTests(unittest.TestCase):
    def test_llm_query_kept_and_unsafe_groups_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp); prepare(run)
            result=run_search_step(run_dir=run, execute=True, api=True, network=True, max_papers=5, semantic_llm_client=FakePlanner(), query="metformin AMPK cancer")
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.summary["query_count"], 1)
            self.assertTrue(result.summary["llm_search_intent_used"])

if __name__ == "__main__": unittest.main()
