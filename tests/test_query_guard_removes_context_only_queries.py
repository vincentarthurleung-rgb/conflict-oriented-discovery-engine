import unittest
from code_engine.search.query_guard import guard_search_queries

class ContextGuardTests(unittest.TestCase):
    def test_context_only_removed_even_if_marked_allowed(self):
        kept, report = guard_search_queries([{"query": "cancer", "query_group": "context_only", "allowed_for_l1_acquisition": True}], subject_aliases=["metformin"], object_aliases=["AMPK"])
        self.assertEqual(kept, []); self.assertEqual(report["context_only_queries_removed"], 1)

if __name__ == "__main__": unittest.main()
