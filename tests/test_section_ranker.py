import unittest

from code_engine.extraction.section_ranker import rank_fulltext_sections_for_conflict


class SectionRankerTests(unittest.TestCase):
    def test_results_and_entity_direction_mentions_rank_high(self):
        document={"paper_id":"P1","sections":[
            {"section_id":"r","title":"Results","text":"Sirolimus inhibited mTOR in mouse cells."},
            {"section_id":"d","title":"Discussion","text":"Sirolimus and mTOR may explain the result."},
            {"section_id":"i","title":"Introduction","text":"General background."},
            {"section_id":"x","title":"References","text":"Sirolimus inhibited mTOR."},
            {"section_id":"f","title":"Funding","text":"Funding statement."}]}
        candidate={"subject_name":"sirolimus","object_name":"mTOR"}
        ranked=rank_fulltext_sections_for_conflict(document,candidate,max_sections=5)
        self.assertEqual(ranked[0]["section_id"],"r")
        self.assertNotIn("x",[item["section_id"] for item in ranked])
        self.assertNotIn("f",[item["section_id"] for item in ranked])
        self.assertIn("inhibit",ranked[0]["matched_direction_terms"])


if __name__ == "__main__": unittest.main()
