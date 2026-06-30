import unittest

from code_engine.evidence_graph.models import EvidenceEdge, EvidenceGraphNode, NODE_TYPES, Serializable


class EvidenceGraphModelTests(unittest.TestCase):
    def test_export_contract_and_node_types(self):
        node = EvidenceGraphNode("n", "paper", "paper")
        self.assertIn("relation_bundle", NODE_TYPES)
        self.assertEqual(node.to_dict()["artifact_schema_version"], "evidence_graph.v1")
        edge = EvidenceEdge("e", "S", "O", "r", "p", "increase")
        self.assertIn("export_ready", edge.to_dict())

    def test_non_dataclass_serializable_has_clear_error(self):
        with self.assertRaisesRegex(TypeError, "must be a dataclass"):
            Serializable().to_dict()


if __name__ == "__main__": unittest.main()
