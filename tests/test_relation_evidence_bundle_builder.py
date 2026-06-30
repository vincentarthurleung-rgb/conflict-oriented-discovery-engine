import unittest

from code_engine.evidence_graph.bundle_builder import build_relation_evidence_bundles
from code_engine.evidence_graph.models import EvidenceEdge


def edge(identity, paper, direction):
    return EvidenceEdge(identity, "ketamine", "BDNF", "affects", "effect", direction, paper_id=paper, canonical_paper_id=paper)


class BundleBuilderTests(unittest.TestCase):
    def test_cross_paper_merge_and_dedup(self):
        bundle = build_relation_evidence_bundles([edge("e1","A","increase"), edge("e2","A","increase"), edge("e3","B","decrease")])[0]
        self.assertEqual(bundle.paper_count, 2)
        self.assertEqual(bundle.evidence_count, 3)
        self.assertEqual(bundle.paper_level_direction_distribution, {"decrease": 1, "increase": 1})

    def test_mixed_same_paper_warning(self):
        bundle = build_relation_evidence_bundles([edge("e1","A","increase"), edge("e2","A","decrease")])[0]
        self.assertIn("mixed_direction_within_same_paper", bundle.warnings)


if __name__ == "__main__": unittest.main()
