import json
import unittest
from pathlib import Path

from code_engine.validation.case_routing import load_case_domain_profile


class Case002ProfileTests(unittest.TestCase):
    def test_profile_loads_with_oa_fulltext_policy(self):
        path = "configs/case_profiles/autophagy_cancer_chemoresistance.case_profile.json"
        profile = load_case_domain_profile(path)
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(profile.case_id, "autophagy_cancer_chemoresistance")
        self.assertEqual(profile.case_type, "conflict_enriched")
        self.assertTrue(profile.fulltext_policy["enabled"])
        self.assertTrue(profile.fulltext_policy["require_oa"])
        self.assertTrue(profile.fulltext_policy["skip_non_oa"])
        self.assertEqual(profile.expected_validators, ["pubmed_post_cutoff", "reactome", "enrichr"])
        self.assertEqual(raw["optional_validators"], ["chembl", "opentargets", "pmc_oa"])


if __name__ == "__main__": unittest.main()
