import unittest
from code_engine.cli.run import build_parser

class PaperYearFilterCLITests(unittest.TestCase):
    def test_cli_values_and_defaults(self):
        default = build_parser().parse_args(["--query", "x"])
        self.assertEqual((default.paper_year_from, default.paper_year_to, default.temporal_role), (None, None, "unrestricted"))
        value = build_parser().parse_args(["--query", "x", "--paper-year-from", "2016", "--paper-year-to", "2020", "--temporal-role", "discovery"])
        self.assertEqual((value.paper_year_from, value.paper_year_to, value.temporal_role), (2016, 2020, "discovery"))

if __name__ == "__main__": unittest.main()
