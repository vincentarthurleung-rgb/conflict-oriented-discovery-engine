import unittest
from code_engine.temporal.paper_year_filter import PaperYearFilter

class PaperYearFilterDefaultsTests(unittest.TestCase):
    def test_default_is_unrestricted(self):
        value = PaperYearFilter()
        self.assertFalse(value.enabled)
        self.assertTrue(value.includes(None))
        self.assertFalse(value.to_dict()["hardcoded_cutoff_used"])
    def test_invalid_range_rejected(self):
        with self.assertRaises(ValueError): PaperYearFilter(2021, 2020)

if __name__ == "__main__": unittest.main()
