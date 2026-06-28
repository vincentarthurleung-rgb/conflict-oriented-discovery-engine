import json
import unittest
from pathlib import Path

from code_engine.loop.dry_lab_loop import plan_dry_lab_loop


FIXTURE = json.loads((Path(__file__).parent / "fixtures/v42_minimal.json").read_text())


class DryLabLoopTests(unittest.TestCase):
    def test_sufficient_local_graph_answers_without_api(self):
        state = plan_dry_lab_loop("ketamine -> BDNF", inventory=FIXTURE["inventory"], knowledge_store=FIXTURE["knowledge_store"])
        self.assertEqual(state.next_action, "answer_from_existing_graph")
        self.assertEqual(state.api_calls_made, 0)
        self.assertTrue(state.hypotheses)

    def test_insufficient_graph_does_not_create_hypothesis(self):
        empty_store = {"pairs": {}, "triples": [], "conflict_edges": [], "context_mentions": [], "validation_results": [], "hypotheses": [], "hypothesis_pairs": {}, "warnings": []}
        state = plan_dry_lab_loop("ketamine -> unknown", inventory={"papers": [], "duplicate_groups": []}, knowledge_store=empty_store)
        self.assertEqual(state.hypotheses, [])
        self.assertEqual(state.api_calls_made, 0)


if __name__ == "__main__": unittest.main()
