import unittest

from code_engine.normalization.candidates import EntityResolutionRequest
from code_engine.normalization.hub import EntityResolutionHub
from code_engine.normalization.providers.local_curated import LocalCuratedProvider
from code_engine.normalization.registry import PILOT_REGISTRY_PATH
from code_engine.normalization.resolver import ResolverCascade


class ResolverHubIntegrationTests(unittest.TestCase):
    def test_old_and_new_fields_are_preserved(self):
        hub = EntityResolutionHub([LocalCuratedProvider(PILOT_REGISTRY_PATH)])
        decision = ResolverCascade(hub=hub).resolve_entity("BDNF")
        self.assertEqual(decision.canonical_id, "GENE:BDNF")
        self.assertEqual(decision.normalization_status, "resolved")
        self.assertEqual(decision.entity_resolution_status, "resolved_curated")
        self.assertEqual(decision.candidate_count, 1)
        self.assertTrue(decision.candidate_provider_names)
        unresolved = ResolverCascade(hub=EntityResolutionHub([])).resolve_entity("novel x")
        self.assertFalse(unresolved.allow_high_confidence_graph_use)
        self.assertTrue(unresolved.requires_manual_review)


if __name__ == "__main__": unittest.main()
