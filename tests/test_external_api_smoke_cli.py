import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_engine.cli.external_api_smoke_test import main


class ExternalAPISmokeCLITests(unittest.TestCase):
    def test_no_network_cli_writes_all_reports(self):
        with tempfile.TemporaryDirectory() as td, patch("urllib.request.urlopen", side_effect=AssertionError("network call")):
            status = main(["--registry", "configs/external_apis/external_api_registry.json", "--output-root", td, "--no-network", "--validators", "reactome,enrichr"])
            self.assertEqual(status, 0)
            root = Path(td)
            summary = json.loads((root / "external_api_smoke_summary.json").read_text())
            self.assertEqual(summary["skipped_count"], 2)
            for name in ("external_api_smoke_summary.md", "external_api_smoke_results.jsonl", "external_api_smoke_registry_overlay.json"):
                self.assertTrue((root / name).is_file())


if __name__ == "__main__": unittest.main()
