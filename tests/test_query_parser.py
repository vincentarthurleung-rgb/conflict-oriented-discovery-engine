import unittest
from pathlib import Path

from src.query.parser import parse_research_query


class QueryParserTests(unittest.TestCase):
    def test_chinese_entity_pair(self):
        profile = Path(__file__).parents[1] / "configs/pilots/ketamine.json"
        query = parse_research_query("氯胺酮 - 抑郁症", entity_aliases_path=profile)
        self.assertEqual(query.normalized_subject, "KETAMINE")
        self.assertEqual(query.normalized_object, "DEPRESSION")
        self.assertEqual(query.language, "zh")

    def test_directed_pair(self):
        query = parse_research_query("ketamine -> BDNF")
        self.assertEqual(query.query_type, "directed_relation")
        self.assertEqual(query.normalized_object, "BDNF")

    def test_mechanism_path(self):
        query = parse_research_query("ketamine mTOR depression")
        self.assertEqual(query.query_type, "mechanism_path")
        self.assertEqual(query.relation_raw, "mTOR")

    def test_unknown_input_does_not_raise(self):
        query = parse_research_query("")
        self.assertEqual(query.query_type, "unknown")


if __name__ == "__main__":
    unittest.main()
