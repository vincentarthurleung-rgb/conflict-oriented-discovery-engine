import unittest

from code_engine.extraction.evidence_span_selector import select_evidence_spans


class EvidenceSpanSelectorTests(unittest.TestCase):
    def test_selects_bounded_traceable_spans(self):
        sections=[{"paper_id":"P1","section_id":"R1","section_title":"Results","section_type":"results","rank_score":8,"text":"Sirolimus inhibited mTOR in mouse cortical cells. Unrelated sentence."},
                  {"paper_id":"P1","section_id":"REF","section_title":"References","section_type":"references","rank_score":9,"text":"Sirolimus inhibited mTOR."}]
        spans=select_evidence_spans(sections,{"candidate_id":"C1","subject_name":"sirolimus","object_name":"mTOR"},max_spans_per_paper=1)
        self.assertEqual(len(spans),1)
        self.assertEqual(spans[0]["section_id"],"R1")
        self.assertEqual(spans[0]["source_scope"],"full_text")
        self.assertEqual(spans[0]["conflict_candidate_ids"],["C1"])
        self.assertIn("mouse",spans[0]["matched_context_terms"])


if __name__ == "__main__": unittest.main()
