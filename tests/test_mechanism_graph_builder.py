import unittest

from code_engine.mechanism.graph_builder import build_mechanism_graph
from tests.test_mechanism_edge_builder import observation


class MechanismGraphBuilderTests(unittest.TestCase):
    def test_merge_nodes_edges_and_paths(self):
        observations = [observation(), observation(triple_id="o2", evidence_id="EV2"), observation(triple_id="o3", evidence_id="EV3", subject="B", normalized_subject="B", subject_canonical_id="GENE:B", object="C", normalized_object="C", object_canonical_id="PATH:C")]
        graph = build_mechanism_graph(observations, max_path_length=2)
        self.assertEqual(len(graph.nodes), 3)
        self.assertEqual(len(graph.edges), 2)
        merged = next(edge for edge in graph.edges if edge.subject_canonical_id == "CHEM:A")
        self.assertEqual(merged.support_count, 2)
        self.assertTrue(any(path.path_length == 2 for path in graph.paths))
        self.assertTrue(all(path.path_length <= 2 for path in graph.paths))


if __name__ == "__main__": unittest.main()
