import json
import unittest
from pathlib import Path

from code_engine.query.intent import parse_research_intent


FIXTURE = json.loads((Path(__file__).parent / "fixtures/intake_minimal.json").read_text())


class ResearchIntentParserTests(unittest.TestCase):
    def test_chinese_role_query(self):
        intent = parse_research_intent(FIXTURE["natural_language_queries"][0])
        self.assertEqual((intent.primary_entity, intent.disease_or_condition), ("ketamine", "depression"))
        self.assertEqual(intent.intent_type, "mechanism_overview")

    def test_literature_update_mechanism(self):
        intent = parse_research_intent(FIXTURE["natural_language_queries"][1])
        self.assertEqual(intent.time_scope, "current")
        self.assertTrue(intent.needs_mechanism_summary)

    def test_comparison(self):
        intent = parse_research_intent(FIXTURE["natural_language_queries"][2])
        self.assertEqual(intent.intent_type, "comparative_mechanism_query")
        self.assertEqual(intent.comparison_entities, ["esketamine", "ketamine"])

    def test_structured_query_still_parses(self):
        self.assertEqual(parse_research_intent(FIXTURE["natural_language_queries"][3]).intent_type, "entity_relation_query")

    def test_unknown_does_not_raise(self):
        intent = parse_research_intent(FIXTURE["natural_language_queries"][4])
        self.assertEqual(intent.intent_type, "unknown")
        self.assertTrue(intent.warnings)


if __name__ == "__main__": unittest.main()
