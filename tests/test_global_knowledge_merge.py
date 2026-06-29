import json
import tempfile
import unittest
from pathlib import Path
from code_engine.corpus.knowledge_merge import merge_run_artifacts_into_knowledge_store


class GlobalKnowledgeMergeTests(unittest.TestCase):
    def test_plan_update_and_duplicate_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / "run"; artifacts = run / "artifacts"; artifacts.mkdir(parents=True)
            (artifacts / "run_paper_manifest.jsonl").write_text(json.dumps({"canonical_paper_id": "P", "doi": "10/x"}) + "\n")
            (artifacts / "abstract_l1_claims.jsonl").write_text(json.dumps({"claim_id": "C", "canonical_paper_id": "P", "source_scope": "abstract", "subject_raw": "a", "object_raw": "b"}) + "\n")
            (artifacts / "l2_abstract_observations.json").write_text(json.dumps([{"observation_id": "O", "canonical_paper_id": "P"}]))
            (artifacts / "abstract_conflict_candidates.jsonl").write_text(json.dumps({"candidate_id": "X"}) + "\n")
            (artifacts / "mechanism_graph.json").write_text(json.dumps({"nodes": [{"node_id": "N"}], "edges": [{"edge_id": "E"}], "paths": [{"path_id": "MP"}]}))
            (artifacts / "hypothesis_hyperedges.jsonl").write_text(json.dumps({"hypothesis_id": "H", "hypothesis_text": "x"}) + "\n")
            planned = merge_run_artifacts_into_knowledge_store(run, root / "corpus")
            self.assertEqual(planned.status, "planned")
            self.assertFalse((root / "corpus/knowledge_store/papers.jsonl").exists())
            updated = merge_run_artifacts_into_knowledge_store(run, root / "corpus", update_global=True, dry_run=False)
            self.assertGreater(updated.inserted_count, 5)
            again = merge_run_artifacts_into_knowledge_store(run, root / "corpus", update_global=True, dry_run=False)
            self.assertGreater(again.skipped_count, 5)
            paper = json.loads((root / "corpus/knowledge_store/papers.jsonl").read_text().splitlines()[0])
            self.assertIn("source_run_ids", paper)


if __name__ == "__main__": unittest.main()
