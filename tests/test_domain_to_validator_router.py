import json
import tempfile
import unittest
from pathlib import Path

from code_engine.validation.case_routing import CaseDomainProfile, route_case_validators


class DomainToValidatorRouterTests(unittest.TestCase):
    def _index(self, root: Path, perturbagen: str = "genericdrug"):
        index = root / "lincs_l1000/index/GSE70138"
        index.mkdir(parents=True)
        (index / f"{perturbagen}_index_summary.json").write_text("{}")
        (index / f"{perturbagen}_top_genes.jsonl").write_text("")

    def test_generic_drug_transcriptomic_profile_selects_lincs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self._index(root)
            profile = CaseDomainProfile(case_id="generic", query="genericdrug pathway disease", case_type="drug_perturbation", entity_types=["drug"], validation_needs=["transcriptomic_perturbation"])
            report = route_case_validators(profile, external_data_root=root)
            self.assertIn("lincs_l1000", report["selected_validators"])

    def test_unavailable_recommendations_are_explicit(self):
        profile = CaseDomainProfile(case_id="generic", query="pathway question", case_type="pathway_context", validation_needs=["pathway_membership"])
        report = route_case_validators(profile, external_data_root="missing")
        self.assertIn("reactome", report["recommended_but_unavailable"])
        self.assertTrue(any(item["decision"] == "recommended_but_unavailable" for item in report["decisions"]))


if __name__ == "__main__":
    unittest.main()
