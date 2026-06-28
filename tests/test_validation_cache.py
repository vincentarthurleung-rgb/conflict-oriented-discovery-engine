import tempfile
import unittest
from pathlib import Path

from code_engine.validation.cache import ValidationQueryCache, build_validation_cache_key


class ValidationCacheTests(unittest.TestCase):
    def test_stable_key_hit_miss_and_fingerprint(self):
        entities=[{"canonical_id":"GENE:MTOR"}]
        key1=build_validation_cache_key("V","identity",entities,config_fingerprint="v1")
        self.assertEqual(key1,build_validation_cache_key("V","identity",entities,config_fingerprint="v1"))
        self.assertNotEqual(key1,build_validation_cache_key("V","identity",entities,config_fingerprint="v2"))
        with tempfile.TemporaryDirectory() as tmp:
            cache=ValidationQueryCache(Path(tmp)/"cache.sqlite")
            self.assertEqual(list(cache.lookup(key1)),[])
            cache.store(key1,[{"evidence_id":"E1"}])
            self.assertEqual(list(cache.lookup(key1))[0]["evidence_id"],"E1")


if __name__ == "__main__": unittest.main()
