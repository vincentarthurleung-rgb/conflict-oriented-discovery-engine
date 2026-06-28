import unittest

from code_engine.schemas.validation import ValidationQuestion
from code_engine.validation.registry import ValidatorRegistry


def question(relation="drug_target_binding", domain="drug_target_binding"):
    return ValidationQuestion(
        question_id="Q1", hypothesis_id="H1", domain_id=domain,
        validator_profile_id="test", relation_type=relation,
        preferred_validators=["ChEMBLValidator"],
        context={"subject_entity_type": "compound", "object_entity_type": "protein"},
    )


class ValidatorRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = ValidatorRegistry().register_defaults()

    def test_default_registration_and_applicability(self):
        self.assertIn("ChEMBLValidator", self.registry.applicable(question()))
        self.assertNotIn("ChEMBLValidator", self.registry.applicable(question("clinical_outcome", "clinical_outcome")))

    def test_missing_local_index_is_structured(self):
        result = self.registry.validate("ChEMBLValidator", question())
        self.assertEqual(result.validation_status, "external_index_not_configured")


if __name__ == "__main__":
    unittest.main()
