import tempfile
import unittest
from pathlib import Path

from src.storage.llm_cache_index import (
    compute_chunk_hash,
    compute_llm_cache_key,
    has_cached_extraction,
    record_cached_extraction,
)


class LLMCacheIndexTests(unittest.TestCase):
    def test_hash_and_key_are_stable_and_versioned(self):
        chunk_hash = compute_chunk_hash("same chunk")
        self.assertEqual(chunk_hash, compute_chunk_hash("same chunk"))
        first = compute_llm_cache_key("p1", chunk_hash, "v1", "deepseek", "s1")
        repeated = compute_llm_cache_key("p1", chunk_hash, "v1", "deepseek", "s1")
        changed = compute_llm_cache_key("p1", chunk_hash, "v2", "deepseek", "s1")
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, changed)

    def test_recorded_key_is_a_cache_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            record_cached_extraction("key", "output.json", {"prompt_version": "v1"}, path=path)
            self.assertTrue(has_cached_extraction("key", path))


if __name__ == "__main__":
    unittest.main()
