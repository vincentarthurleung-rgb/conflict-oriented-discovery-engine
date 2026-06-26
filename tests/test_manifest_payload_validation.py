import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.pipelines.manifest_validation import validate_manifest, validate_payload_dir


class ManifestPayloadValidationTests(unittest.TestCase):
    def test_manifest_audit_warns_without_paths(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "global_manifest.json"
            path.write_text(
                json.dumps({"metadata": {"query": "q", "timestamp": "t"}, "papers": {"PMC1": {"source": "pmc"}}}),
                encoding="utf-8",
            )
            audit = validate_manifest(str(path))
            self.assertEqual(audit.total_papers, 1)
            codes = {warning["code"] for warning in audit.warnings}
            self.assertIn("raw_path_missing", codes)
            self.assertIn("payload_path_missing", codes)

    def test_payload_audit_warns_missing_belief_weight(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "P1_payload.json").write_text(
                json.dumps({"pmcid": "P1", "paragraphs": [{"section": "Abstract", "text": "Text"}]}),
                encoding="utf-8",
            )
            audit = validate_payload_dir(str(root))
            self.assertEqual(audit.total_payloads, 1)
            self.assertFalse(audit.errors)
            self.assertIn("belief_weight_missing", {warning["code"] for warning in audit.warnings})


if __name__ == "__main__":
    unittest.main()
