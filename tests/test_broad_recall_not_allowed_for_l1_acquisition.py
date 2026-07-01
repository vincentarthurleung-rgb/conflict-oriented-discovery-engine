import unittest
from code_engine.search.query_guard import guard_search_queries

class BroadRecallTests(unittest.TestCase):
    def test_broad_recall_removed(self):
        kept, report=guard_search_queries([{"query":"metformin cancer","query_group":"broad_recall","allowed_for_l1_acquisition":True}],subject_aliases=["metformin"],object_aliases=["AMPK"])
        self.assertFalse(kept); self.assertEqual(report["broad_recall_queries_removed"],1)

if __name__ == "__main__": unittest.main()
