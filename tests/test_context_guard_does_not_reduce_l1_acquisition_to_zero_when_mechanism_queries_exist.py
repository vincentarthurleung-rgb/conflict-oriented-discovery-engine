import unittest

from code_engine.search.query_guard import guard_search_queries


class ContextGuardRecallTests(unittest.TestCase):
    def test_mechanism_only_set_survives_context_annotation(self):
        kept, _ = guard_search_queries([{"query": "metformin AMPK signaling pathway", "query_group": "mechanism", "allowed_for_l1_acquisition": True}],
                                       subject_aliases=["metformin"], object_aliases=["AMPK"], context_terms=["cancer"])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["query_scope"], "cross_context_mechanism")


if __name__ == "__main__": unittest.main()
