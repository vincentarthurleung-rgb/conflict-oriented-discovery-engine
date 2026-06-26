import unittest

from src.reporting.blueprint import build_report_blueprints, resolve_anchor_gene
from src.reporting.markdown import render_markdown_report


class L6LegacyFieldTests(unittest.TestCase):
    def test_legacy_target_gene_is_read_as_anchor_gene(self):
        resolved = resolve_anchor_gene({"target_gene": "GRIA1"})
        self.assertEqual(resolved["anchor_gene"], "GRIA1")
        self.assertEqual(resolved["anchor_gene_semantics"], "legacy")

    def test_markdown_uses_anchor_gene_label(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            items = build_report_blueprints(
                [
                    {
                        "hypothesis_id": "H1",
                        "seed_pair": "A -> B",
                        "target_gene": "GRIA1",
                        "global_ranking_score": 0.5,
                        "validation_status": "Verified_By_Hardened_Omics_Sign_Locked",
                    }
                ]
            )
            output = Path(tmp) / "report.md"
            render_markdown_report(items, str(output))
            text = output.read_text(encoding="utf-8")
            self.assertIn("Anchor gene", text)
            self.assertNotIn("target_gene", text)
            self.assertNotIn("Verified_By_Hardened_Omics_Sign_Locked", text)


if __name__ == "__main__":
    unittest.main()
