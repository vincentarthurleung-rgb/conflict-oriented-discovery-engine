import tempfile
import unittest
from pathlib import Path

from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan
from code_engine.search.search_plan_replay import executable_query_hash, freeze_search_plan, load_frozen_search_plan


class ReplayProvenanceTests(unittest.TestCase):
    def test_replay_records_hashes_and_planner_bypass(self):
        plan = build_literature_search_plan(parse_research_intent("metformin AMPK cancer"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frozen.json"
            freeze_search_plan(plan, path, run_id="R", query_text="q", semantic_search_intent={}, query_guard_summary={})
            replayed, provenance = load_frozen_search_plan(path, fail_if_drift=True)
        self.assertTrue(provenance["enabled"])
        self.assertTrue(provenance["fail_if_search_plan_drift"])
        self.assertFalse(provenance["planner_called"])
        self.assertFalse(provenance["deterministic_fallback_called"])
        self.assertFalse(provenance["search_plan_drift_detected"])
        self.assertEqual(provenance["frozen_executable_query_hash"], executable_query_hash(replayed))
        self.assertEqual(provenance["replayed_executable_query_hash"], executable_query_hash(replayed))


if __name__ == "__main__": unittest.main()
