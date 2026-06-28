import tempfile
import unittest
from pathlib import Path

from code_engine.mechanism.conflict_annotator import annotate_mechanism_graph_with_conflicts
from code_engine.mechanism.graph_builder import build_mechanism_graph
from code_engine.mechanism.io import save_mechanism_graph
from code_engine.storage.mechanism_index import load_mechanism_index, query_conflicted_mechanism_edges, query_evidence_for_mechanism_edge, query_mechanism_edges_for_entity
from tests.test_mechanism_edge_builder import observation


class MechanismIndexTests(unittest.TestCase):
    def test_load_and_queries(self):
        graph = annotate_mechanism_graph_with_conflicts(build_mechanism_graph([observation()]), [{"edge_id": "c", "subject_canonical_id": "CHEM:A", "object_canonical_id": "GENE:B", "conflict_type": "Type I", "conflict_status": "conflicting"}])
        with tempfile.TemporaryDirectory() as tmp:
            path = save_mechanism_graph(graph, Path(tmp) / "graph.json")
            loaded = load_mechanism_index(path)
            edge = query_mechanism_edges_for_entity("CHEM:A", loaded)[0]
            self.assertEqual(len(query_conflicted_mechanism_edges(loaded)), 1)
            self.assertEqual(query_evidence_for_mechanism_edge(edge["edge_id"], loaded), ["EV1"])


if __name__ == "__main__": unittest.main()
