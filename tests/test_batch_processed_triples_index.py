import json
import tempfile
import unittest
from pathlib import Path

from code_engine.batch.triple_runner import run_triple_batch


TRIPLES = [
    {"query_text": "metformin AMPK cancer", "papers": [{"canonical_paper_id": "shared"}]},
    {"query_text": "aspirin COX inflammation", "papers": [{"canonical_paper_id": "shared"}]},
    {"query_text": "ketamine BDNF depression", "papers": [{"canonical_paper_id": "other"}]},
]


class BatchProcessedTriplesIndexTests(unittest.TestCase):
    def test_isolation_cache_savings_catalog_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kwargs = {"until": "report", "l1_mode": "abstract_screening", "merge_knowledge_store": False}
            result = run_triple_batch(
                TRIPLES, root / "batch", batch_id="b1",
                paper_artifact_cache_index=root / "cache.jsonl", workflow_kwargs=kwargs,
            )
            self.assertEqual(result["paper_artifact_cache_hits"], 1)
            self.assertEqual(result["paper_artifact_build_count"], 2)
            self.assertFalse(result["aggregate_feedback_to_triples"])
            self.assertFalse(result["reasoning_artifacts_reused_from_other_batch"])
            rows = [json.loads(line) for line in Path(result["processed_triples_index"]).read_text().splitlines()]
            self.assertEqual(len(rows), 3)
            self.assertEqual(len({row["run_dir"] for row in rows}), 3)
            for row in rows:
                self.assertIn("/per_triple/", row["run_dir"])
                manifest = json.loads((Path(row["run_dir"]) / "triple_run_manifest.json").read_text())
                self.assertNotIn("processed_triples_index", json.dumps(manifest))
            resumed = run_triple_batch(
                TRIPLES, root / "batch", batch_id="b1", resume=True,
                paper_artifact_cache_index=root / "cache.jsonl", workflow_kwargs=kwargs,
            )
            self.assertEqual(resumed["resumed_triple_count"], 3)

    def test_existing_directory_requires_explicit_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "batch"
            root.mkdir()
            (root / "unexpected").write_text("x")
            with self.assertRaises(FileExistsError):
                run_triple_batch(TRIPLES[:1], root)
            report = json.loads((root / "batch_contamination_preflight_report.json").read_text())
            self.assertEqual(report["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
