import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.steps import run_search_step
from tests.search_intent_helpers import prepare


class BadPlanner:
    def extract_json(self, prompt):
        return {"seed_triple": {"relation": {"name": "activates"}, "object": {"name": "AMPK"}},
                "query_groups": {"direct_relation": ["AMPK"]}}


class UnrepairableRealModeTests(unittest.TestCase):
    def test_missing_subject_blocks_without_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); prepare(run)
            result = run_search_step(run_dir=run, execute=True, api=True, network=True, max_papers=5,
                                     semantic_llm_client=BadPlanner(), query="metformin AMPK cancer",
                                     allow_deterministic_search_fallback=False)
            self.assertEqual(result.status, "blocked")
            self.assertFalse(result.summary["deterministic_search_fallback_used"])
            self.assertFalse(result.summary["search_intent_schema_valid_after_normalization"])
            self.assertFalse((run / "artifacts/search_plan.json").exists())


if __name__ == "__main__": unittest.main()
