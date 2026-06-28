import unittest

from code_engine.extraction.evidence_tiers import PaperProcessingRecord, is_high_confidence_mechanism_evidence
from code_engine.mechanism.edge_builder import build_mechanism_edges_from_observations


class EvidenceTierTests(unittest.TestCase):
    def test_unavailable_fulltext_is_coverage_gap(self):
        record = PaperProcessingRecord(paper_id="P1", abstract_available=True, full_text_status="unavailable")
        payload = record.model_dump(mode="json")
        self.assertEqual(payload["evidence_tier"], "coverage_gap")
        self.assertFalse(record.high_confidence_mechanism_eligible)

    def test_abstract_scope_is_not_mechanism_evidence(self):
        self.assertFalse(is_high_confidence_mechanism_evidence({"source_scope": "abstract", "evidence_tier": "abstract_screening"}))
        observation = {"paper_id":"P1", "source_scope":"abstract", "evidence_tier":"abstract_screening", "subject":"A", "object":"B", "subject_canonical_id":"A", "object_canonical_id":"B", "allow_high_confidence_graph_use":True}
        self.assertEqual(build_mechanism_edges_from_observations([observation]), [])


if __name__ == "__main__": unittest.main()
