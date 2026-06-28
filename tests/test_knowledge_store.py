import json
import tempfile
import unittest
from pathlib import Path

from src.storage.knowledge_store import (
    build_knowledge_store,
    query_conflicts_for_pair,
    query_contexts_for_pair,
    query_exact_pair,
    query_neighbors,
)


class KnowledgeStoreTests(unittest.TestCase):
    def test_queries_over_compatible_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data/processed/l3").mkdir(parents=True)
            (root / "data/processed/l4").mkdir(parents=True)
            graph = [
                {
                    "subject": "KETAMINE",
                    "object": "BDNF",
                    "whitebox_traceability": [{"triple_id": "t1", "relation_sign": 1}],
                },
                {
                    "subject": "BDNF",
                    "object": "MTOR",
                    "whitebox_traceability": [{"triple_id": "t2", "relation_sign": 1}],
                },
            ]
            conflicts = {"conflict_edges": [{"edge_id": "e1", "source": "KETAMINE", "target": "BDNF"}]}
            contexts = {"context_mentions": [{"triple_id": "t1", "axis": "species", "value": "mouse"}]}
            (root / "data/processed/l3/integrated_shannon_graph.json").write_text(json.dumps(graph), encoding="utf-8")
            (root / "data/processed/l3/conflict_edges.json").write_text(json.dumps(conflicts), encoding="utf-8")
            (root / "data/processed/l4/context_mentions.json").write_text(json.dumps(contexts), encoding="utf-8")

            store = build_knowledge_store(root)
            self.assertEqual(len(query_exact_pair("ketamine", "bdnf", store)), 1)
            self.assertEqual(len(query_neighbors("ketamine", max_depth=2, store=store)), 2)
            self.assertEqual(len(query_conflicts_for_pair("ketamine", "bdnf", store)), 1)
            self.assertEqual(len(query_contexts_for_pair("ketamine", "bdnf", store)), 1)


if __name__ == "__main__":
    unittest.main()
