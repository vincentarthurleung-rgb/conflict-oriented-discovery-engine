import unittest
from code_engine.search.semantic_search_intent import plan_semantic_search_intent
from tests.search_intent_helpers import FakePlanner

class PlannerSchemaTests(unittest.TestCase):
    def test_schema_aliases_groups_and_prompt_metadata(self):
        value = plan_semantic_search_intent("metformin AMPK cancer", domain_id="general_biomedical", seed_triple={}, llm_client=FakePlanner())
        self.assertEqual(value.seed_triple.subject.name, "metformin")
        self.assertIn("AMP-activated protein kinase", value.seed_triple.object.aliases)
        self.assertTrue(value.planner_prompt_hash)

if __name__ == "__main__": unittest.main()
