import contextlib
import io
import tempfile
import unittest

from src.query.cli import main


class QueryCLISmokeTests(unittest.TestCase):
    def test_parse_coverage_and_plan_are_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ("parse", "coverage", "plan"):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    status = main([
                        "--query", "ketamine -> BDNF",
                        "--mode", mode,
                        "--repository-root", tmp,
                        "--no-api",
                    ])
                self.assertEqual(status, 0)
                self.assertTrue(output.getvalue().strip())

    def test_update_is_plan_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = main([
                    "--query", "esketamine -> depression",
                    "--mode", "update",
                    "--dry-run",
                    "--max-api-calls", "50",
                    "--repository-root", tmp,
                ])
            self.assertEqual(status, 0)
            self.assertIn("not implemented", output.getvalue())


if __name__ == "__main__":
    unittest.main()
