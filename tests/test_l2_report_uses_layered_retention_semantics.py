import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class L2ReportSemanticsTests(unittest.TestCase):
    def test_report_explains_non_core_is_not_discarded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            run_workflow("metformin AMPK cancer", run_dir=root, until="report",
                         allow_uncertain_intake=True, execute=False, api=False, network=False,
                         merge_knowledge_store=False, global_corpus_dir=Path(tmp) / "corpus")
            report = (root / "run_report.md").read_text()
            self.assertIn("## L2 layered retention", report)
            self.assertIn("Non-core does not mean discarded", report)
            self.assertNotIn("excluded_low_confidence_count =", report)


if __name__ == "__main__": unittest.main()
