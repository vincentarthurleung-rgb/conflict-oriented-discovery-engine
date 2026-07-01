import unittest
from pathlib import Path

class NoHardcodedCutoffTests(unittest.TestCase):
    def test_production_code_has_no_experiment_year_literals(self):
        source = "\n".join(path.read_text() for path in Path("src/code_engine").rglob("*.py"))
        for year in ("2015", "2016", "2020"):
            self.assertNotIn(year, source)

if __name__ == "__main__": unittest.main()
