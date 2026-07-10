import json
import unittest
from pathlib import Path


EXPECTED_CASES = {
    "wnt_beta_catenin_cancer_stemness_immunity_discovery_v1",
    "emt_metastasis_drug_resistance_discovery_v1",
    "ferroptosis_cancer_therapy_response_discovery_v1",
    "hif1a_hypoxia_cancer_response_discovery_v1",
    "il6_stat3_cancer_response_discovery_v1",
    "pi3k_akt_mtor_cancer_resistance_discovery_v1",
    "nfkb_inflammation_cancer_response_discovery_v1",
    "pdl1_immune_checkpoint_cancer_response_discovery_v1",
    "ros_oxidative_stress_cancer_response_discovery_v1",
    "senescence_sasp_cancer_therapy_response_discovery_v1",
    "tp53_apoptosis_cancer_therapy_response_discovery_v1",
}


class AtlasElevenCaseInventoryTests(unittest.TestCase):
    def test_curated_inventory_has_exactly_formal_eleven_cases(self):
        root = Path("system_b_inputs/eleven_case_atlas_bundle_20260710")
        inventory = json.loads((root / "atlas_source_inventory.json").read_text(encoding="utf-8"))
        cases = inventory["cases"]
        self.assertEqual(inventory["case_count"], 11)
        self.assertEqual({x["case_id"] for x in cases}, EXPECTED_CASES)
        self.assertEqual(len({x["case_id"] for x in cases}), 11)
        for record in cases:
            self.assertIn("case_bundle_manifest.json", record["included_files"])
            self.assertTrue(Path(record["curated_bundle_path"]).is_dir())
            self.assertIn("___l2_cleaner_fulltext_replay", record["curated_bundle_path"])
            self.assertNotIn("experimental", record["curated_bundle_path"].lower())
            self.assertFalse(record["overlay_applied"])


if __name__ == "__main__":
    unittest.main()
