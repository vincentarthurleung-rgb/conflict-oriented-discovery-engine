import tempfile
import unittest
from pathlib import Path
from code_engine.corpus.paper_registry import PaperRegistry


class PaperRegistryTests(unittest.TestCase):
    def test_create_dedup_hash_status_and_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp); registry = PaperRegistry.load(directory)
            first = registry.resolve_or_create({"paper_id": "A", "doi": "10.1/X", "title": "Paper", "journal": "J", "abstract": "text"}, "R1", "q1")
            second = registry.resolve_or_create({"paper_id": "B", "doi": "https://doi.org/10.1/x", "title": "Paper"}, "R2", "q2")
            self.assertEqual(first.canonical_paper_id, second.canonical_paper_id)
            self.assertIsNotNone(second.abstract_hash)
            registry.mark_processing_status(first.canonical_paper_id, "abstract_l1", "completed", {"claims": "x"})
            registry.save()
            loaded = PaperRegistry.load(directory)
            self.assertEqual(loaded.get(first.canonical_paper_id).processing_status["abstract_l1"], "completed")
            self.assertTrue((directory / "duplicate_resolution_audit.jsonl").exists())

    def test_no_save_means_no_global_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = PaperRegistry.load(Path(tmp)); registry.resolve_or_create({"pmid": "1"}, "R")
            self.assertFalse((Path(tmp) / "paper_registry.jsonl").exists())


if __name__ == "__main__": unittest.main()
