import tempfile, unittest
from pathlib import Path
from code_engine.reporting.full_abstract_pipeline import generate_full_abstract_pipeline
from tests.full_pipeline_test_support import make_pipeline

class FullReportTests(unittest.TestCase):
 def test_report_has_pipeline_completeness_table(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=make_pipeline(Path(tmp)); generate_full_abstract_pipeline(root); text=(root/"artifacts/whitebox_case_report.md").read_text()
  self.assertIn("Pipeline completeness",text); self.assertIn("L6 Mechanism graph",text); self.assertIn("complete for the abstract-mode",text)
if __name__=="__main__": unittest.main()
