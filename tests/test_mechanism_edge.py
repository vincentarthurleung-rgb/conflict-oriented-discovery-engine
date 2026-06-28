import json
import unittest
from pathlib import Path

from code_engine.schemas.mechanism_edge import MechanismEdge


FIXTURE = json.loads((Path(__file__).parent / "fixtures/v42_minimal.json").read_text())


class MechanismEdgeTests(unittest.TestCase):
    def test_legacy_pair_adapter(self):
        edge = MechanismEdge.from_legacy_pair(FIXTURE["conflict_edge"])
        self.assertEqual(edge.source, "KETAMINE")
        self.assertNotEqual(edge.source, edge.target)

    def test_biological_distinctions_are_typed_relations(self):
        subunit = MechanismEdge(edge_id="e1", source="GRIA1", source_type="gene", target="AMPAR", target_type="receptor_complex", edge_type="subunit_of")
        metabolite = MechanismEdge(edge_id="e2", source="NORKETAMINE", source_type="metabolite", target="KETAMINE", target_type="compound", edge_type="metabolite_of")
        self.assertNotEqual(subunit.source, subunit.target)
        self.assertEqual(metabolite.edge_type, "metabolite_of")


if __name__ == "__main__": unittest.main()
