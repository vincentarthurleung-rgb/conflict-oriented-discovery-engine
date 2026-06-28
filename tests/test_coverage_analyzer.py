import unittest

from src.query.coverage import analyze_coverage
from src.query.parser import parse_research_query


def inventory():
    return {"papers": [{"paper_id": "p1", "l1_extracted": True, "l1_5_refined": True, "year": 2024}]}


def store(include_exact=True, include_conflict=False, include_context=False):
    triple = {"triple_id": "t1", "subject": "KETAMINE", "object": "BDNF", "relation_sign": 1}
    pair = {"subject": "KETAMINE", "object": "BDNF", "triple_ids": ["t1"]}
    return {
        "pairs": {"KETAMINE␟BDNF": pair} if include_exact else {},
        "triples": [triple] if include_exact else [],
        "conflict_edges": ([{"pair_key": "KETAMINE␟BDNF"}] if include_conflict else []),
        "context_mentions": ([{"triple_id": "t1"}] if include_context else []),
        "validation_results": [],
        "hypotheses": [],
        "hypothesis_pairs": {},
    }


class CoverageAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.query = parse_research_query("ketamine -> BDNF")

    def test_sufficient_verdict(self):
        report = analyze_coverage(
            self.query, inventory=inventory(), knowledge_store=store(True, True, True), write_outputs=False
        )
        self.assertEqual(report.coverage_score, 0.7)
        self.assertEqual(report.verdict, "Sufficient_No_Update_Needed")

    def test_partial_verdict(self):
        report = analyze_coverage(
            self.query, inventory=inventory(), knowledge_store=store(True), write_outputs=False
        )
        self.assertEqual(report.verdict, "Partial_Coverage_Delta_Update_Recommended")

    def test_insufficient_verdict(self):
        report = analyze_coverage(
            self.query, inventory=inventory(), knowledge_store=store(False), write_outputs=False
        )
        self.assertEqual(report.verdict, "Insufficient_Run_New_Corpus_Search")


if __name__ == "__main__":
    unittest.main()
