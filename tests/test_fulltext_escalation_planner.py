import unittest

from code_engine.extraction.fulltext_escalation import plan_fulltext_escalation


class FulltextEscalationPlannerTests(unittest.TestCase):
    def test_selects_available_and_records_gaps_and_limits(self):
        candidates=[{"candidate_id":"C1","abstract_entropy":.9,"paper_count":3,"relation_family":"drug_target","paper_ids":["P1","P2","P3"]}]
        records=[{"paper_id":"P1","full_text_status":"available"},{"paper_id":"P2","full_text_status":"parsed"},{"paper_id":"P3","full_text_status":"unavailable"}]
        result=plan_fulltext_escalation(candidates,records,max_papers_per_conflict=1)
        self.assertEqual(result["selected_papers"][0]["paper_id"],"P1")
        self.assertEqual(len(result["selected_papers"]),1)
        self.assertEqual(result["coverage_gaps"][0]["paper_id"],"P3")
        self.assertIn("max_papers_per_conflict_reached",[item["reason"] for item in result["skipped"]])


if __name__ == "__main__": unittest.main()
