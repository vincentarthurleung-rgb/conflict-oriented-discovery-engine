import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_engine.system_b import SystemBBatchIngestor


class SystemBBatchIngestTests(unittest.TestCase):
    def test_one_bundle_and_missing_optional_files_without_network(self):
        with tempfile.TemporaryDirectory() as td, patch("urllib.request.urlopen", side_effect=AssertionError("network call")):
            root = Path(td)
            result = SystemBBatchIngestor().run(
                ["case_bundles"], root, root / "case_registry.json",
                write_markdown=True, write_csv=True,
            )
            self.assertEqual(result["summary"]["case_count"], 1)
            self.assertEqual(result["summary"]["ready_count"], 1)
            self.assertTrue((root / "case_comparison_table.csv").is_file())


if __name__ == "__main__":
    unittest.main()
