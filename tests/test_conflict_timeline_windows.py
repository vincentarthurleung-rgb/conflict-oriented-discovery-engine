import unittest

from code_engine.temporal.windows import TimelineConfig, detect_temporal_windows


class TimelineWindowTests(unittest.TestCase):
    def test_detects_early_and_later_windows(self):
        records = [{"paper_id": f"p{y}", "publication_year": y, "direction": d} for y, d in [(2010,"increase"),(2011,"decrease"),(2012,"increase"),(2013,"decrease"),(2017,"increase")]]
        result = detect_temporal_windows(records, TimelineConfig(window_size=5, min_conflict_source_papers=3))
        self.assertIsNotNone(result["conflict_source_window"])
        self.assertEqual(result["later_evidence_window"]["start_year"], 2017)

    def test_cutoff_excludes_future_year(self):
        records = [{"paper_id": str(y), "publication_year": y, "direction": "increase" if y % 2 else "decrease"} for y in (2018, 2019, 2020, 2021)]
        result = detect_temporal_windows(records, TimelineConfig(cutoff_year=2020, min_conflict_source_papers=2))
        self.assertNotIn("2021", result["paper_count_by_year"])


if __name__ == "__main__": unittest.main()
