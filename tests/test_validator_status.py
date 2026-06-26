import unittest

from src.validators.curated_omics_validator import CuratedOmicsValidator
from src.validators.null_validator import NullValidator


class ValidatorStatusTests(unittest.TestCase):
    def test_null_validator_is_unresolved_not_passed(self):
        result = NullValidator().validate({"hypothesis_id": "H1"})
        self.assertEqual(result["status"], "Unresolved_No_Coverage")
        self.assertEqual(result["coverage"], "none")

    def test_curated_validator_uncovered_is_unresolved(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            index = Path(tmp) / "index.json"
            index.write_text('{"perturbation_registry": {}}', encoding="utf-8")
            validator = CuratedOmicsValidator(lincs_index_path=str(index), cell_mask_path="missing.json")
            result = validator.validate({"hypothesis_id": "H1", "seed_pair": "A -> UNKNOWN_TARGET"})
            self.assertEqual(result["status"], "Unresolved_No_Coverage")
            self.assertNotEqual(result["status"], "Passed_By_General_Fallback")

    def test_curated_validator_consistent_and_inconsistent(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            index = Path(tmp) / "index.json"
            index.write_text(
                json_dump(
                    {
                        "perturbation_registry": {
                            "BDNF": {
                                "registry_anchor_gene": "BDNF",
                                "omics_anchor_gene": "BDNF",
                                "cell_lines": {"NEURON_CL": {"z_score": 2.0}},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            validator = CuratedOmicsValidator(lincs_index_path=str(index), cell_mask_path="missing.json")
            consistent = validator.validate({"hypothesis_id": "H1", "seed_pair": "A -> BDNF", "whitebox_traceability": [{"relation_sign": 1}]})
            inconsistent = validator.validate({"hypothesis_id": "H2", "seed_pair": "A -> BDNF", "whitebox_traceability": [{"relation_sign": -1}]})
            self.assertEqual(consistent["status"], "Sign_Consistent_Under_Curated_Index")
            self.assertEqual(inconsistent["status"], "Sign_Inconsistent_Under_Curated_Index")
            self.assertEqual(consistent["registry_anchor_gene"], "BDNF")
            self.assertEqual(consistent["anchor_gene"], "BDNF")

    def test_curated_validator_legacy_target_gene_still_works(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            index = Path(tmp) / "index.json"
            index.write_text(
                json_dump(
                    {
                        "perturbation_registry": {
                            "BDNF": {
                                "target_gene": "BDNF",
                                "cell_lines": {"NEURON_CL": {"z_score": 2.0}},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            validator = CuratedOmicsValidator(lincs_index_path=str(index), cell_mask_path="missing.json")
            result = validator.validate({"hypothesis_id": "H1", "seed_pair": "A -> BDNF", "whitebox_traceability": [{"relation_sign": 1}]})
            self.assertEqual(result["registry_anchor_gene"], "BDNF")
            self.assertEqual(result["anchor_gene"], "BDNF")


def json_dump(payload):
    import json

    return json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
