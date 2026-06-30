import unittest

from code_engine.validation.base import AbstractValidator
from code_engine.validation.null import NullValidator


class NullValidatorContractTests(unittest.TestCase):
    def test_can_validate_accepts_abstract_validator_signature(self):
        validator: AbstractValidator = NullValidator()
        self.assertTrue(validator.can_validate({}, context={}))


if __name__ == "__main__":
    unittest.main()
