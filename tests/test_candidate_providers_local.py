import json
import tempfile
import unittest
from pathlib import Path

from code_engine.normalization.cache import EntityCache
from code_engine.normalization.candidates import EntityResolutionRequest
from code_engine.normalization.providers.local_cache import LocalCacheProvider
from code_engine.normalization.providers.local_curated import LocalCuratedProvider
from code_engine.normalization.providers.null import NullProvider
from code_engine.normalization.registry import PILOT_REGISTRY_PATH


class LocalProviderTests(unittest.TestCase):
    def test_curated_is_explicit_and_cache_reads_accepted(self):
        request = EntityResolutionRequest(surface="ketamine")
        self.assertEqual(LocalCuratedProvider().propose(request), [])
        self.assertTrue(LocalCuratedProvider(PILOT_REGISTRY_PATH).propose(request)[0].is_curated)
        with tempfile.TemporaryDirectory() as tmp:
            cache = EntityCache(tmp)
            cache.root.mkdir(exist_ok=True)
            cache.accepted_path.write_text(json.dumps({"surface":"x","normalized_surface":"x","canonical_id":"X:1","canonical_name":"X","entity_type":"gene","source":"external","provider_name":"old","is_grounded":True,"overall_score":.9}) + "\n")
            self.assertEqual(LocalCacheProvider(cache).propose(EntityResolutionRequest(surface="x"))[0].canonical_id, "X:1")
        null = NullProvider(); self.assertEqual(null.propose(request), []); self.assertTrue(null.last_warnings)


if __name__ == "__main__": unittest.main()
