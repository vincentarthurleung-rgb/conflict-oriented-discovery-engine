import json
import tempfile
import unittest
from pathlib import Path

from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan
from code_engine.search.search_plan_replay import executable_query_hash, freeze_search_plan, load_frozen_search_plan


class SearchPlanFreezeReplayTests(unittest.TestCase):
    def test_round_trip_and_drift_detection(self):
        plan = build_literature_search_plan(parse_research_intent("metformin AMPK cancer"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            freeze_search_plan(plan, path, run_id="R", query_text="metformin AMPK cancer", semantic_search_intent={}, query_guard_summary={})
            replayed, provenance = load_frozen_search_plan(path, fail_if_drift=True)
            self.assertEqual(executable_query_hash(plan), executable_query_hash(replayed))
            self.assertFalse(provenance["planner_called"])
            payload = json.loads(path.read_text()); payload["search_plan"]["pubmed_queries"][0]["query_string"] += " drift"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "drift"):
                load_frozen_search_plan(path, fail_if_drift=True)


if __name__ == "__main__": unittest.main()
