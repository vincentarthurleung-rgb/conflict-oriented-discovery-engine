import json
import unittest
from pathlib import Path

from code_engine.validation.validator_input_builder import (
    build_validator_input, enrichr_input, pubmed_post_cutoff_input, reactome_input,
)


class ValidatorInputBuilderTests(unittest.TestCase):
    def test_three_profiles_are_data_driven(self):
        paths = list(Path("configs/case_profiles").glob("*.json")) + [Path("tests/fixtures/case_profiles/tgf_beta_fibrosis_context.case_profile.json")]
        outputs = [build_validator_input(path) for path in paths]
        self.assertEqual(3, len(outputs))
        self.assertEqual({json.loads(path.read_text())["case_id"] for path in paths}, {item["case_id"] for item in outputs})
        synthetic = next(item for item in outputs if item["case_id"] == "tgf_beta_fibrosis_context")
        self.assertEqual(["SMAD2", "SMAD3"], synthetic["genes"])
        self.assertEqual("ready", enrichr_input(synthetic)["status"])
        self.assertIn("SMAD2", reactome_input(synthetic)["terms"])
        self.assertIn("2020:3000[dp]", pubmed_post_cutoff_input(synthetic)["query"])

    def test_no_gene_fallback(self):
        value = build_validator_input({"case_id": "empty", "case_type": "exploratory"})
        self.assertEqual({"status": "skipped_no_gene_set", "genes": []}, enrichr_input(value))

    def test_observation_and_graph_entity_types(self):
        value = build_validator_input(
            {"case_id": "synthetic", "case_type": "conflict_enriched"},
            core_observations=[{"subject_raw": "Drug X", "subject_entity_type": "drug", "object_raw": "GENE9", "object_entity_type": "gene"}],
            kg_nodes=[{"label": "Pathway Q", "type": "pathway"}],
        )
        self.assertEqual(["GENE9"], value["genes"])
        self.assertEqual(["Drug X"], value["drugs"])
        self.assertEqual(["Pathway Q"], value["pathways"])


if __name__ == "__main__":
    unittest.main()
