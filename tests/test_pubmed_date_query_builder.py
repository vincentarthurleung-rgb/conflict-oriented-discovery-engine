import unittest

from code_engine.temporal.paper_year_filter import build_pubmed_date_filter


class PubMedDateBuilderTests(unittest.TestCase):
    def test_pdat_ranges(self):
        self.assertEqual(build_pubmed_date_filter(2010, 2020), '("2010/01/01"[PDAT] : "2020/12/31"[PDAT])')
        self.assertEqual(build_pubmed_date_filter(2000, 2020), '("2000/01/01"[PDAT] : "2020/12/31"[PDAT])')
        self.assertEqual(build_pubmed_date_filter(None, 2020), '("1900/01/01"[PDAT] : "2020/12/31"[PDAT])')
        self.assertEqual(build_pubmed_date_filter(2010, None), '("2010/01/01"[PDAT] : "3000/12/31"[PDAT])')


if __name__ == "__main__": unittest.main()
