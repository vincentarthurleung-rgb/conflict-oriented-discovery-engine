import json
import tempfile
import unittest
from pathlib import Path

from code_engine.schemas.triples import build_seed_triple
from code_engine.workflow.orchestrator import run_workflow


class TripleCardGenerationTests(unittest.TestCase):
    def test_stable_id_and_run_metadata(self):
        first = build_seed_triple("metformin AMPK cancer")
        second = build_seed_triple("  METFORMIN   ampk CANCER ")
        self.assertEqual(first.triple_id, second.triple_id)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            run_workflow(first.query_text, run_dir=directory, until="report", l1_mode="abstract_screening", merge_knowledge_store=False)
            card = json.loads((directory / "triple_card.json").read_text())
            manifest = json.loads((directory / "triple_run_manifest.json").read_text())
            provenance = json.loads((directory / "artifacts/runtime_provenance_report.json").read_text())
            self.assertEqual(card["triple_id"], first.triple_id)
            self.assertEqual(manifest["triple_id"], first.triple_id)
            self.assertEqual(provenance["query_hash"], first.query_hash)
            self.assertIn("seed_triple", provenance)


if __name__ == "__main__":
    unittest.main()
