import unittest
from code_engine.search.query_guard import guard_search_queries

class ObjectOnlyGuardTests(unittest.TestCase):
    def test_object_only_removed(self):
        _, report = guard_search_queries([{"query": "AMPK", "query_group": "direct_relation", "allowed_for_l1_acquisition": True}], subject_aliases=["metformin"], object_aliases=["AMPK"])
        self.assertEqual(report["off_seed_queries_removed"], 1)

if __name__ == "__main__": unittest.main()
