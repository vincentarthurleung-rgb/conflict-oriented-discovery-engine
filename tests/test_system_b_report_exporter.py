import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_engine.cli.system_b_ingest import ingest


class ReportExporterTests(unittest.TestCase):
    def test_ingestion_writes_json_and_markdown_without_network_calls(self):
        with tempfile.TemporaryDirectory() as td, patch("urllib.request.urlopen", side_effect=AssertionError("network call")):
            card, quality = ingest("tests/fixtures/system_b_case_bundles/metformin_ampk_cancer", td)
            output = Path(td) / "metformin_ampk_cancer"
            expected = {
                "system_b_case_card.json", "system_b_case_card.md", "system_b_quality_report.json",
                "system_b_quality_report.md", "system_b_ingestion_summary.json",
            }
            self.assertEqual({path.name for path in output.iterdir()}, expected)
            summary = json.loads((output / "system_b_ingestion_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["quality_class"], "CASE_READY_FOR_ARCHIVE")
            self.assertEqual(card["validation_summary"]["lincs_interpretation"], "mixed")
            self.assertEqual(quality["comparison_readiness"], "READY_AS_POSITIVE_CONTROL")


if __name__ == "__main__":
    unittest.main()
