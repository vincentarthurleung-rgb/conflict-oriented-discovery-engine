import unittest

from code_engine.search.query_guard import guard_search_queries


class ContextGuardStrictTests(unittest.TestCase):
    def test_context_specific_query_is_annotated_not_filtered(self):
        kept, report = guard_search_queries([{"query": "metformin AND AMPK AND cancer", "query_group": "direct_relation", "allowed_for_l1_acquisition": True}],
                                            subject_aliases=["metformin"], object_aliases=["AMPK"], context_terms=["cancer"])
        self.assertEqual(len(kept), 1)
        self.assertTrue(kept[0]["context_strict"])
        self.assertTrue(kept[0]["allowed_for_context_specific_core"])
        self.assertEqual(report["context_strict_query_count"], 1)


if __name__ == "__main__": unittest.main()
