import tempfile
import unittest
from pathlib import Path

from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan
from code_engine.search.search_plan_replay import freeze_search_plan
from code_engine.workflow.steps import run_search_step
from tests.search_intent_helpers import prepare


class ExplodingPlanner:
    def extract_json(self, prompt): raise AssertionError("LLM planner must not be called")


class ReplayNoLLMTests(unittest.TestCase):
    def test_replay_bypasses_all_planners(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"; prepare(run)
            plan = build_literature_search_plan(parse_research_intent("metformin AMPK cancer"))
            frozen = Path(tmp) / "frozen.json"
            freeze_search_plan(plan, frozen, run_id="R", query_text="metformin AMPK cancer", semantic_search_intent={}, query_guard_summary={})
            result = run_search_step(run_dir=run, execute=True, api=True, network=True, max_papers=5,
                                     semantic_llm_client=ExplodingPlanner(), search_plan_file=frozen,
                                     replay_search_plan=True, fail_if_search_plan_drift=True)
            self.assertEqual(result.status, "completed")
            self.assertFalse(result.summary["llm_search_intent_used"])
            self.assertEqual(result.summary["search_intent_mode"], "frozen_replay")


if __name__ == "__main__": unittest.main()
