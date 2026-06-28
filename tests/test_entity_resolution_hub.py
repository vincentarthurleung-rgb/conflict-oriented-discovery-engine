import tempfile
import unittest
from pathlib import Path

from code_engine.normalization.audit import EntityResolutionAuditWriter
from code_engine.normalization.cache import EntityCache
from code_engine.normalization.candidates import EntityResolutionRequest
from code_engine.normalization.hub import EntityResolutionHub
from code_engine.normalization.providers.base import CandidateProvider
from code_engine.normalization.providers.local_curated import LocalCuratedProvider
from code_engine.normalization.registry import PILOT_REGISTRY_PATH


class FailingProvider(CandidateProvider):
    name = "FailingProvider"
    def propose(self, request): raise RuntimeError("fixture")


class HubTests(unittest.TestCase):
    def test_order_failure_audit_batch_and_accepted_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = EntityCache(Path(tmp) / "cache", accepted_writes_enabled=True)
            audit = EntityResolutionAuditWriter(Path(tmp) / "run")
            hub = EntityResolutionHub([FailingProvider(), LocalCuratedProvider(PILOT_REGISTRY_PATH)], audit_writer=audit, entity_cache=cache)
            result = hub.resolve(EntityResolutionRequest(surface="ketamine", execute=True))
            self.assertEqual(result.normalization_status, "resolved_curated")
            self.assertTrue(any("provider_failure" in item for item in result.warnings))
            self.assertTrue(Path(result.audit_ref).exists())
            self.assertTrue(cache.accepted_path.exists())
            self.assertEqual(len(hub.resolve_many([EntityResolutionRequest(surface="BDNF")])), 1)


if __name__ == "__main__": unittest.main()
