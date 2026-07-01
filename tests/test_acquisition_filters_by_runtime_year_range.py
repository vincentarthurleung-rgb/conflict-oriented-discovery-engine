import unittest
from code_engine.temporal.paper_year_filter import PaperYearFilter, filter_papers_by_year

class AcquisitionYearFilterTests(unittest.TestCase):
    def test_closed_and_upper_bound_ranges(self):
        papers = [{"paper_id": "A", "publication_year": 2014}, {"paper_id": "B", "publication_year": 2016}, {"paper_id": "C", "publication_year": 2018}, {"paper_id": "D", "publication_year": 2021}]
        kept, _ = filter_papers_by_year(papers, PaperYearFilter(None, 2015))
        self.assertEqual([x["paper_id"] for x in kept], ["A"])
        kept, _ = filter_papers_by_year(papers, PaperYearFilter(2016, 2020))
        self.assertEqual([x["paper_id"] for x in kept], ["B", "C"])

if __name__ == "__main__": unittest.main()
