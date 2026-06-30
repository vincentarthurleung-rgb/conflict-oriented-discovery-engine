import unittest

from code_engine.evidence_graph.validators import validate_graph_contract


class ContractTests(unittest.TestCase):
    def test_missing_target_is_reported_not_raised(self):
        result=validate_graph_contract([{"node_id":"a","node_type":"paper","provenance":{}}],[{"edge_id":"e","source":"a","target":"missing"}],[],[])
        self.assertEqual(result["edges_with_missing_target"],["e"])
        self.assertEqual(result["status"],"warnings")


if __name__ == "__main__": unittest.main()
