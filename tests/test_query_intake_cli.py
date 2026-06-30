import contextlib
import io
import json
import tempfile
import unittest

from code_engine.query.cli import main


class QueryIntakeCLITests(unittest.TestCase):
    def test_intake_modes_are_offline_smokes(self):
        for mode in ("intent", "search-plan", "l1-plan", "intake"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    status = main([
                        "--query", "我想了解一下当前氯胺酮在抑郁症的作用",
                        "--mode", mode, "--dry-run", "--no-api", "--repository-root", tmp,
                    ])
                self.assertEqual(status, 0)
                payload = json.loads(output.getvalue())
                if mode == "intake":
                    self.assertEqual(payload["api_calls_made"], 0)
                elif mode == "l1-plan":
                    self.assertEqual(payload["api_calls_made"], 0)


if __name__ == "__main__": unittest.main()
