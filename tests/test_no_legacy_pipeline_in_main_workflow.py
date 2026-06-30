import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class LegacyPipelineIsolationTests(unittest.TestCase):
    def test_main_workflow_does_not_import_legacy_stage6(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_workflow("ketamine BDNF depression",run_dir=Path(tmp),until="hypothesis")
            report=json.loads((Path(tmp)/"artifacts/runtime_provenance_report.json").read_text())
            self.assertNotIn("src.pipelines.stage6_l4_beam_search",report["legacy_modules_imported"])


if __name__ == "__main__": unittest.main()
