import tempfile
import unittest
from pathlib import Path

from code_engine.system_b import SystemBBatchIngestor


class ValidatorCoverageMatrixTests(unittest.TestCase):
    def test_executed_and_unavailable_are_infrastructure_statuses(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = SystemBBatchIngestor().run(["case_bundles"], root, root / "registry.json", case_glob="metformin_ampk_cancer")
            row = result["matrix"]["cases"][0]
            self.assertEqual(row["lincs_l1000"], "executed")
            for validator in ("reactome", "enrichr", "chembl", "opentargets", "pubmed_post_cutoff"):
                self.assertEqual(row[validator], "recommended_unavailable")
            self.assertNotIn("failed", row.values())


if __name__ == "__main__":
    unittest.main()
