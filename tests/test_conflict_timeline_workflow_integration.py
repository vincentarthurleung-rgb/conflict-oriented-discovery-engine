import json
import tempfile
import unittest
from pathlib import Path

from code_engine.temporal.io import run_conflict_timeline
from code_engine.workflow.models import STEP_ORDER


class IntegrationTests(unittest.TestCase):
    def test_step_order_and_artifacts(self):
        self.assertLess(STEP_ORDER.index("hypothesis"), STEP_ORDER.index("conflict_timeline"))
        self.assertLess(STEP_ORDER.index("conflict_timeline"), STEP_ORDER.index("validation"))
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp) / "artifacts"; artifacts.mkdir()
            (artifacts / "abstract_conflict_candidates.jsonl").write_text(json.dumps({"candidate_id":"c","subject_canonical_id":"S","object_canonical_id":"O"})+"\n")
            summary = run_conflict_timeline(tmp)
            self.assertIn(summary["status"], {"completed", "no_input"})
            self.assertTrue((artifacts / "conflict_evidence_timelines.jsonl").exists())


if __name__ == "__main__": unittest.main()
