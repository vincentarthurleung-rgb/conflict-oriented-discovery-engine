import tempfile, unittest
from pathlib import Path
from code_engine.workflow.steps import run_search_step
from tests.search_intent_helpers import FakePlanner, prepare

class RealModePlannerTests(unittest.TestCase):
    def test_real_mode_prefers_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp); prepare(run)
            result=run_search_step(run_dir=run,execute=True,api=True,network=True,max_papers=5,semantic_llm_client=FakePlanner())
            self.assertTrue(result.summary["llm_search_intent_used"]); self.assertFalse(result.summary["deterministic_search_fallback_used"])

if __name__ == "__main__": unittest.main()
