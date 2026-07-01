import tempfile, unittest
from pathlib import Path
from code_engine.workflow.steps import run_search_step
from tests.search_intent_helpers import FakePlanner, prepare

class ExplicitFallbackTests(unittest.TestCase):
    def test_explicit_flag_allows_real_mode_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp); prepare(run)
            result=run_search_step(run_dir=run,execute=True,api=True,network=True,max_papers=5,semantic_llm_client=FakePlanner(fail=True),allow_deterministic_search_fallback=True)
            self.assertNotEqual(result.status,"blocked"); self.assertTrue(result.summary["deterministic_search_fallback_used"])

if __name__ == "__main__": unittest.main()
