import tempfile, unittest
from pathlib import Path
from tests.whitebox_test_support import make_whitebox

class HypothesisDisplayTests(unittest.TestCase):
    def test_abstract_followups_are_not_formal_hypotheses(self):
        with tempfile.TemporaryDirectory() as tmp: value = make_whitebox(Path(tmp))["hypothesis_summary"]
        self.assertEqual(value["formal_hypothesis_count"], 0)
        self.assertEqual(value["main_hypothesis_count"], 0)
        self.assertEqual(value["manual_review_followup_count"], 4)
        self.assertEqual(value["display_hypothesis_count"], 0)
        self.assertEqual(value["display_followup_count"], 4)

if __name__ == "__main__": unittest.main()
