import unittest

from code_engine.evidence_graph.bundle_builder import build_relation_evidence_bundles
from code_engine.evidence_graph.conflict_reasoning import reason_over_bundle
from code_engine.evidence_graph.models import EvidenceEdge


def make(directions):
    return build_relation_evidence_bundles([EvidenceEdge(f"e{i}","S","O","r","p",d,paper_id=f"p{i}") for i,d in enumerate(directions)])[0]


class ReasoningTests(unittest.TestCase):
    def test_conflict_uncontested_and_insufficient(self):
        self.assertEqual(reason_over_bundle(make(["increase","decrease","no_effect"]))[0].status, "graph_conflict_candidate")
        self.assertEqual(reason_over_bundle(make(["increase","increase","increase"]))[0].status, "graph_uncontested_relation")
        self.assertEqual(reason_over_bundle(make(["increase"]))[0].status, "graph_insufficient_evidence")

    def test_trace_has_formula_inputs(self):
        _, trace = reason_over_bundle(make(["increase","decrease"]))
        self.assertTrue(trace.input_evidence_edge_ids)
        self.assertEqual(trace.thresholds["conflict_entropy_threshold"], .55)


if __name__ == "__main__": unittest.main()
