import copy
import json
import unittest
from pathlib import Path

from code_engine.query.intent import parse_research_intent
from code_engine.query.l1_batch_planner import plan_l1_batch_for_intent
from code_engine.query.prompt_compatibility import build_required_fingerprint_for_intent
from code_engine.query.search_planner import build_literature_search_plan


FIXTURE = json.loads((Path(__file__).parent / "fixtures/intake_minimal.json").read_text())


class L1BatchPlannerTests(unittest.TestCase):
    def setUp(self):
        self.intent = parse_research_intent("domain: neuropharmacology ketamine depression mechanism")
        self.search = build_literature_search_plan(self.intent, candidate_papers=FIXTURE["candidate_papers"])
        self.required = build_required_fingerprint_for_intent(self.intent)

    def test_reuse_reextract_payload_and_download_classification(self):
        plan = plan_l1_batch_for_intent(self.intent, self.search, FIXTURE["inventory"], self.required)
        self.assertEqual([item["chunk_id"] for item in plan.chunks_reused], ["c1"])
        self.assertEqual([item["chunk_id"] for item in plan.chunks_need_reextraction_due_to_prompt], ["c2"])
        self.assertEqual([item["chunk_id"] for item in plan.chunks_need_reextraction_due_to_schema], ["c3"])
        self.assertEqual([item["chunk_id"] for item in plan.chunks_need_reextraction_due_to_chunk_hash], ["c4"])
        self.assertEqual(plan.papers_need_payload_build[0]["paper_id"], "P2")
        self.assertEqual(plan.papers_need_download[0]["paper_id"], "P3")
        self.assertEqual(plan.api_calls_made, 0)

    def test_missing_l1_chunk_enters_l1_batch(self):
        inventory = copy.deepcopy(FIXTURE["inventory"])
        inventory["papers"][0]["l1_extracted"] = False
        inventory["papers"][0]["chunks"] = [{"chunk_id": "new", "chunk_hash": "new"}]
        plan = plan_l1_batch_for_intent(self.intent, self.search, inventory, self.required)
        self.assertEqual(plan.chunks_need_l1[0]["chunk_id"], "new")

    def test_budget_limit_requests_user_budget(self):
        plan = plan_l1_batch_for_intent(self.intent, self.search, FIXTURE["inventory"], self.required, budget={"max_api_calls": 1})
        self.assertEqual(plan.budget_status, "over_budget")
        self.assertEqual(plan.recommended_action, "request_user_budget")


if __name__ == "__main__": unittest.main()
