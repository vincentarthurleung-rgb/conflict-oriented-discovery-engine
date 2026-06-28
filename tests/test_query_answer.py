import unittest

from src.query.answer import assemble_query_answer
from src.query.models import CoverageReport
from src.query.parser import parse_research_query


class QueryAnswerTests(unittest.TestCase):
    def test_insufficient_coverage_does_not_emit_hypotheses(self):
        query = parse_research_query("unknown compound -> unknown outcome")
        coverage = CoverageReport(
            query_id=query.query_id,
            normalized_subject=query.normalized_subject,
            normalized_object=query.normalized_object,
            hypotheses=[{"hypothesis_id": "must-not-leak"}],
            missing_dimensions=["no_exact_pair"],
            verdict="Insufficient_Run_New_Corpus_Search",
        )
        answer = assemble_query_answer(query, coverage, write_outputs=False)
        self.assertEqual(answer.hypotheses, [])
        self.assertEqual(answer.api_calls_made, 0)
        self.assertTrue(answer.used_existing_graph_only)


if __name__ == "__main__":
    unittest.main()
