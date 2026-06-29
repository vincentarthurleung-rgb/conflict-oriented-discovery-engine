import unittest
from pathlib import Path

from code_engine.validation.null import NullValidator
from code_engine.validation.registry import DEFAULT_VALIDATORS


class ValidatorSchemaBindingTests(unittest.TestCase):
    def test_validator_schema_metadata(self):
        for validator in DEFAULT_VALIDATORS:
            if validator is NullValidator:
                self.assertIsNone(validator.schema_name)
                continue
            self.assertIsNotNone(validator.schema_name, validator.__name__)
            self.assertEqual(validator.schema_version, "1.0.0")
            self.assertIsNotNone(validator.source_database)
            self.assertTrue((Path(__file__).parents[1] / "configs/validation/index_schemas" / f"{validator.schema_name}.json").exists() or validator.__name__ == "PathwayValidator")


if __name__ == "__main__": unittest.main()
