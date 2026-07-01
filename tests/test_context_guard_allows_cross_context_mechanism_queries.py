import unittest

from code_engine.search.query_guard import guard_search_queries


class ContextGuardMechanismTests(unittest.TestCase):
    def test_background_query_remains_acquirable(self):
        kept, report = guard_search_queries([{"query": "metformin activates AMPK", "query_group": "direct_relation", "allowed_for_l1_acquisition": True}],
                                            subject_aliases=["metformin"], object_aliases=["AMPK"], context_terms=["cancer"])
        self.assertEqual(len(kept), 1)
        self.assertFalse(kept[0]["context_strict"])
        self.assertFalse(kept[0]["allowed_for_context_specific_core"])
        self.assertEqual(kept[0]["query_scope"], "cross_context_mechanism")
        self.assertEqual(report["cross_context_mechanism_query_count"], 1)


if __name__ == "__main__": unittest.main()
