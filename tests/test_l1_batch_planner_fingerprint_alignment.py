import copy
import json
import unittest
from pathlib import Path

from code_engine.query.intent import parse_research_intent
from code_engine.query.l1_batch_planner import plan_l1_batch_for_intent
from code_engine.query.prompt_compatibility import build_required_fingerprint_for_intent
from code_engine.query.search_planner import build_literature_search_plan
from code_engine.extraction.l1_extractor import build_l1_dry_run_plan


FIXTURE = json.loads((Path(__file__).parent / "fixtures/intake_minimal.json").read_text())


class L1BatchPlannerFingerprintAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.intent = parse_research_intent(FIXTURE["natural_language_queries"][0])
        self.search = build_literature_search_plan(self.intent, candidate_papers=FIXTURE["candidate_papers"])
        self.required = build_required_fingerprint_for_intent(self.intent)

    def plan(self, inventory, **kwargs):
        return plan_l1_batch_for_intent(
            self.intent, self.search, inventory, self.required, **kwargs
        )

    def test_matching_fingerprint_reuses(self):
        plan = self.plan(FIXTURE["inventory"])
        self.assertIn("c1", [item["chunk_id"] for item in plan.chunks_reused])

    def test_intent_required_profile_matches_extractor_profile(self):
        extraction = build_l1_dry_run_plan(
            "Ketamine affects depression.", auto_domain=True, cache_path="missing.json"
        )
        self.assertEqual(self.required.domain_id, extraction["domain_id"])
        self.assertEqual(self.required.prompt_profile_id, extraction["prompt_profile_id"])
        self.assertEqual(self.required.output_schema_version, extraction["output_schema_version"])
        self.assertEqual(
            self.required.extraction_policy_version,
            extraction["extraction_policy_version"],
        )

    def test_missing_fingerprint_rejected_by_default_and_explicitly_allowed(self):
        inventory = copy.deepcopy(FIXTURE["inventory"])
        inventory["papers"][0]["chunks"] = [{"chunk_id": "legacy", "chunk_hash": "h"}]
        denied = self.plan(inventory)
        allowed = self.plan(inventory, allow_legacy_l1_reuse=True)
        self.assertEqual(denied.chunks_need_reextraction_due_to_prompt[0]["reason"], "missing_prompt_fingerprint")
        self.assertEqual(allowed.chunks_reused[0]["reason"], "legacy_l1_reuse_explicitly_allowed")

    def test_prompt_schema_and_policy_mismatches_are_separate(self):
        inventory = copy.deepcopy(FIXTURE["inventory"])
        chunks = inventory["papers"][0]["chunks"]
        chunks[0]["l1_record"]["prompt_version"] = "old"
        chunks[1]["l1_record"]["prompt_version"] = self.required.prompt_version
        chunks[1]["l1_record"]["output_schema_version"] = "old"
        chunks[2]["l1_record"]["output_schema_version"] = self.required.output_schema_version
        chunks[2]["l1_record"]["extraction_policy_version"] = "old"
        inventory["papers"][0]["chunks"] = chunks[:3]
        plan = self.plan(inventory)
        self.assertEqual([item["chunk_id"] for item in plan.chunks_need_reextraction_due_to_prompt], ["c1"])
        self.assertEqual([item["chunk_id"] for item in plan.chunks_need_reextraction_due_to_schema], ["c2"])
        self.assertEqual([item["chunk_id"] for item in plan.chunks_need_reextraction_due_to_policy], ["c3"])


if __name__ == "__main__":
    unittest.main()
