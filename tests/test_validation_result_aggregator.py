import unittest

from code_engine.schemas.validation import ValidationResult
from code_engine.validation.result_aggregator import ValidationResultAggregator


def result(status, validator):
    return ValidationResult(hypothesis_id="H1", validator_name=validator, validation_status=status)


class ValidationResultAggregatorTests(unittest.TestCase):
    def setUp(self):
        self.aggregator = ValidationResultAggregator()

    def test_status_rules(self):
        cases = (
            ([result("supported", "A"), result("contradicted", "B")], "mixed"),
            ([result("supported", "A")], "supported"),
            ([result("no_coverage", "A")], "no_coverage"),
            ([result("external_index_not_configured", "A")], "no_coverage"),
            ([result("insufficient_quality", "A")], "insufficient_quality"),
        )
        for results, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(self.aggregator.aggregate(results).overall_status, expected)


if __name__ == "__main__":
    unittest.main()
