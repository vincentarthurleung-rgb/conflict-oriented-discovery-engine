import unittest

from code_engine.mechanism.conflict_annotator import annotate_mechanism_graph_with_conflicts
from code_engine.mechanism.graph_builder import build_mechanism_graph
from tests.test_mechanism_edge_builder import observation


class MechanismConflictAnnotatorTests(unittest.TestCase):
    def test_pair_annotation_preserves_l3_type(self):
        graph = build_mechanism_graph([observation()])
        annotated = annotate_mechanism_graph_with_conflicts(graph, [{"edge_id": "c1", "subject_canonical_id": "CHEM:A", "object_canonical_id": "GENE:B", "conflict_status": "conflicting", "conflict_type": "Type II", "entropy": 0.75}])
        self.assertTrue(annotated.edges[0].has_conflict)
        self.assertEqual(annotated.edges[0].conflict_types, ["Type II"])
        self.assertIn("pair_level_annotation=true", annotated.edges[0].warnings)
        self.assertEqual(annotated.conflict_annotations[0].entropy, 0.75)


if __name__ == "__main__": unittest.main()
