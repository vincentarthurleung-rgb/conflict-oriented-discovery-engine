import json
import tempfile
import unittest
from pathlib import Path
from code_engine.workflow.steps import run_hypothesis_step


class WorkflowHypothesisGenerationTests(unittest.TestCase):
    def test_step_writes_artifacts_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); artifacts = root / "artifacts"; artifacts.mkdir()
            (artifacts / "abstract_conflict_candidates.jsonl").write_text(json.dumps({"candidate_id": "C", "subject_canonical_id": "S", "object_canonical_id": "O"}) + "\n")
            result = run_hypothesis_step(run_dir=root, execute=False)
            self.assertEqual(result.counts["hypothesis_count"], 1)
            self.assertEqual(len(result.artifacts), 5)
            self.assertTrue(all(Path(path).exists() for path in result.artifacts.values()))
            self.assertTrue(any("missing_optional" in warning for warning in result.warnings))


if __name__ == "__main__": unittest.main()
