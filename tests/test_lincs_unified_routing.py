import tempfile
import unittest
from pathlib import Path

from code_engine.validation.case_routing import CaseDomainProfile, route_case_validators


class LincsUnifiedRoutingTests(unittest.TestCase):
    def test_router_and_cli_override_are_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); index = root / "lincs_l1000/index/GSE70138"; index.mkdir(parents=True)
            (index / "drug_index_summary.json").write_text("{}")
            (index / "drug_top_genes.jsonl").write_text("")
            profile = CaseDomainProfile(case_id="case", query="drug disease", case_type="drug_perturbation", entity_types=["drug"], validation_needs=["transcriptomic_perturbation"])
            report = route_case_validators(profile, external_data_root=root, manual_cli_validators=["lincs_l1000"])
            self.assertEqual(report["selected_validators"].count("lincs_l1000"), 1)
            self.assertTrue(report["deduplicated"])


if __name__ == "__main__":
    unittest.main()
