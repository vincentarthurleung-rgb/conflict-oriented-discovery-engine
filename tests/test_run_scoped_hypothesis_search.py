import json
import tempfile
import unittest
from pathlib import Path

from code_engine.hypothesis.search import run_hypothesis_search_for_run


class RunScopedSearchTests(unittest.TestCase):
    def test_no_input_and_artifact_grounded_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_hypothesis_search_for_run(None, None, None, Path(tmp))
            self.assertEqual((result["status"], result["hypothesis_count"]), ("no_input", 0))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); artifacts = root / "artifacts"; artifacts.mkdir()
            candidate = {"candidate_id": "C1", "subject_canonical_id": "S", "object_canonical_id": "O", "abstract_entropy": 1.0}
            (artifacts / "abstract_conflict_candidates.jsonl").write_text(json.dumps(candidate) + "\n")
            result = run_hypothesis_search_for_run(None, None, None, root)
            self.assertEqual(result["hypothesis_abstract_only_count"], 1)
            for name in ("hypothesis_candidates.jsonl", "hypothesis_hyperedges.jsonl", "hypothesis_reasoning_records.jsonl", "hypothesis_validation_requirements.jsonl", "hypothesis_summary.json"):
                self.assertTrue((artifacts / name).exists())

    def test_repository_fixture_mechanism_conflict_smoke(self):
        source = Path(__file__).parent / "fixtures/runs/hypothesis_mechanism_conflict_fixture/artifacts"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); artifacts = root / "artifacts"; artifacts.mkdir()
            for path in source.iterdir():
                (artifacts / path.name).write_bytes(path.read_bytes())
            result = run_hypothesis_search_for_run(None, None, None, root)
            self.assertGreater(result["hypothesis_count"], 0)
            self.assertGreater(result["hypothesis_mechanism_grounded_count"], 0)


if __name__ == "__main__": unittest.main()
