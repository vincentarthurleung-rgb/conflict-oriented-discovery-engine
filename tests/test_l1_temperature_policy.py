import unittest

from code_engine.extraction.policy import (
    DEFAULT_L1_TEMPERATURE,
    DEFAULT_L1_TOP_P,
    get_l1_sampling_config,
)


class L1TemperaturePolicyTests(unittest.TestCase):
    def test_default_is_fixed_zero(self):
        self.assertEqual(DEFAULT_L1_TEMPERATURE, 0.0)
        self.assertEqual(DEFAULT_L1_TOP_P, 1.0)

    def test_default_does_not_change_by_chunk_index(self):
        self.assertEqual(
            {get_l1_sampling_config(index).temperature for index in range(20)},
            {0.0},
        )

    def test_schedule_requires_explicit_flag(self):
        default = get_l1_sampling_config(3)
        experimental = get_l1_sampling_config(3, experimental_temperature_schedule=True)
        self.assertFalse(default.experimental_temperature_schedule)
        self.assertEqual(default.temperature, 0.0)
        self.assertTrue(experimental.experimental_temperature_schedule)
        self.assertEqual(experimental.temperature, 0.6)


if __name__ == "__main__":
    unittest.main()
