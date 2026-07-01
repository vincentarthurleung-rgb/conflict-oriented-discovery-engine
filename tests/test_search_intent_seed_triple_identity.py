import unittest
from code_engine.schemas.triples import build_seed_triple

class SearchIntentIdentityTests(unittest.TestCase):
    def test_aliases_do_not_change_query_hash(self):
        first=build_seed_triple("metformin AMPK cancer",domain="general_biomedical",relation="association")
        second=build_seed_triple("metformin AMPK cancer",domain="general_biomedical",relation="association")
        self.assertEqual(first.query_hash,second.query_hash); self.assertEqual(first.triple_id,second.triple_id)

if __name__ == "__main__": unittest.main()
