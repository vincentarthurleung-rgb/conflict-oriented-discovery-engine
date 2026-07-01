import unittest
from code_engine.temporal.paper_year_filter import PaperYearFilter, filter_papers_by_year

class MissingYearTests(unittest.TestCase):
    def test_missing_year_policy(self):
        papers = [{"paper_id": "P"}]
        self.assertEqual(len(filter_papers_by_year(papers, PaperYearFilter())[0]), 1)
        kept, counts = filter_papers_by_year(papers, PaperYearFilter(None, 2020))
        self.assertEqual(kept, [])
        self.assertEqual(counts["papers_missing_year_excluded"], 1)

if __name__ == "__main__": unittest.main()
