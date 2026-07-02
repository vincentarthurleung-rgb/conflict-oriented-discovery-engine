import tempfile, unittest
from pathlib import Path
from tests.whitebox_test_support import make_whitebox

class WhiteboxReportTests(unittest.TestCase):
    def test_report_explains_positive_control_without_false_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); make_whitebox(root); text=(root/"artifacts/whitebox_case_report.md").read_text()
        for phrase in ("Positive-control style evidence extraction case", "5 strong-context core observations",
                       "No true graph conflict", "No high-confidence or graph-conflict hypothesis", "avoiding false conflict inflation"):
            self.assertIn(phrase, text)

if __name__ == "__main__": unittest.main()
