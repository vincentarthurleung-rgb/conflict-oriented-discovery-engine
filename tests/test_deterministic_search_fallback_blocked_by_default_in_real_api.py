import tempfile, unittest
from pathlib import Path
from code_engine.workflow.steps import run_search_step
from tests.search_intent_helpers import FakePlanner, prepare

class FallbackBlockedTests(unittest.TestCase):
    def test_real_mode_planner_failure_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp); prepare(run)
            result=run_search_step(run_dir=run,execute=True,api=True,network=True,max_papers=5,semantic_llm_client=FakePlanner(fail=True),allow_deterministic_search_fallback=False)
            self.assertEqual(result.status,"blocked"); self.assertEqual(result.summary["blocked_reason"],"llm_search_intent_failed")

if __name__ == "__main__": unittest.main()
