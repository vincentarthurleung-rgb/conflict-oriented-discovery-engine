import unittest

from code_engine.evidence_graph.bundle_builder import build_relation_evidence_bundles
from code_engine.evidence_graph.conflict_reasoning import reason_over_bundle
from code_engine.evidence_graph.models import EvidenceEdge


def edge(identifier, paper, direction):
    return EvidenceEdge(identifier, "S", "O", "regulation", "effect", direction,
                        paper_id=paper, canonical_paper_id=paper, observation_id=identifier)


class TrueGraphConflictSemanticsTests(unittest.TestCase):
    def status(self, directions):
        bundle = build_relation_evidence_bundles([edge(str(i), f"P{i}", value) for i, value in enumerate(directions)])[0]
        return reason_over_bundle(bundle)[0].status

    def test_only_opposing_polarity_is_conflict(self):
        self.assertEqual(self.status(["activate"]), "graph_insufficient_evidence")
        self.assertEqual(self.status(["decrease", "inhibit"]), "graph_uncontested_relation")
        self.assertEqual(self.status(["activate", "increase"]), "graph_uncontested_relation")
        self.assertEqual(self.status(["activate", "inhibit"]), "graph_conflict_candidate")


if __name__ == "__main__": unittest.main()
