import unittest

from code_engine.mechanism.models import MechanismEdge, MechanismGraph, MechanismNode


class MechanismModelTests(unittest.TestCase):
    def test_models_round_trip(self):
        node = MechanismNode(node_id="CHEM:A", canonical_id="CHEM:A", raw_names=["A"])
        edge = MechanismEdge(edge_id="e1", source_node_id="CHEM:A", target_node_id="GENE:B")
        graph = MechanismGraph(graph_id="g1", nodes=[node], edges=[edge])
        loaded = MechanismGraph.model_validate_json(graph.model_dump_json())
        self.assertEqual(loaded.nodes[0].canonical_id, "CHEM:A")
        self.assertFalse(loaded.edges[0].has_conflict)
        self.assertEqual(loaded.warnings, [])


if __name__ == "__main__": unittest.main()
