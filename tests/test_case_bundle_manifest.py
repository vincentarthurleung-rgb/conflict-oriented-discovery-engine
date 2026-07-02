import json
import unittest
from pathlib import Path


class CaseBundleManifestContractTests(unittest.TestCase):
    def test_metformin_profile_declares_bundle_routing_inputs(self):
        profile = json.loads(Path("configs/case_profiles/metformin_ampk_cancer.case_profile.json").read_text())
        self.assertIn("lincs_l1000", profile["expected_validators"])
        self.assertIn("post_cutoff_literature", profile["validation_needs"])


if __name__ == "__main__":
    unittest.main()
