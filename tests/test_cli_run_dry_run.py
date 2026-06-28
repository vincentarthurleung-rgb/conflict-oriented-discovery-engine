import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CLIRunDryRunTests(unittest.TestCase):
    def test_cli_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, "-m", "code_engine.cli.run", "--query", "ketamine depression", "--run-dir", tmp, "--dry-run", "--no-api", "--no-network", "--until", "search"], check=True, capture_output=True, text=True)
            state = json.loads((Path(tmp) / "run_state.json").read_text(encoding="utf-8"))
            self.assertIn("Run dir:", result.stdout)
            self.assertEqual(state["api_calls_made"], 0)
            self.assertEqual(state["network_calls_made"], 0)


if __name__ == "__main__":
    unittest.main()
