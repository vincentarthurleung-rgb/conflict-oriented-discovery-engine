import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from code_engine.corpus.l1_task_cache import L1TaskCacheRecord, L1TaskSignature, build_l1_task_cache_key, lookup_l1_task_cache, store_l1_task_cache_record


class L1TaskCacheTests(unittest.TestCase):
    def signature(self, **changes):
        data = {"task_family": "abstract_claim_screening", "source_scope": "abstract", "canonical_paper_id": "P", "content_hash": "H", "schema_version": "v1", "prompt_fingerprint": "A", "domain_id": "bio", "l1_mode": "abstract_screening"}; data.update(changes)
        return L1TaskSignature(**data)

    def test_exact_compatible_and_schema_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            signature = self.signature(); now = datetime.now(timezone.utc).isoformat()
            record = L1TaskCacheRecord(task_cache_key=build_l1_task_cache_key(signature), signature=signature, status="stored", created_at=now, updated_at=now)
            store_l1_task_cache_record(record, Path(tmp))
            self.assertEqual(lookup_l1_task_cache(signature, Path(tmp)).status, "hit")
            self.assertEqual(lookup_l1_task_cache(self.signature(prompt_fingerprint="B"), Path(tmp)).status, "compatible_task_family_hit")
            self.assertEqual(lookup_l1_task_cache(self.signature(schema_version="v2"), Path(tmp)).status, "incompatible_schema")
            self.assertEqual(build_l1_task_cache_key(signature), build_l1_task_cache_key(signature))


if __name__ == "__main__": unittest.main()
