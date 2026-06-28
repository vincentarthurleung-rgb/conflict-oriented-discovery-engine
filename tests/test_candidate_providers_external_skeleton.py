import unittest

from code_engine.normalization.candidates import EntityResolutionRequest
from code_engine.normalization.providers.chembl import ChEMBLCandidateProvider
from code_engine.normalization.providers.mygene import MyGeneCandidateProvider
from code_engine.normalization.providers.pubchem import PubChemCandidateProvider
from code_engine.normalization.providers.uniprot import UniProtCandidateProvider


class FakeClient:
    def search(self, surface, request=None): return [{"id":"1","canonical_name":surface,"entity_type":request.l1_entity_type_hint,"score":.9}]


class ExternalProviderTests(unittest.TestCase):
    def test_guards_and_fake_grounding(self):
        classes = (PubChemCandidateProvider, ChEMBLCandidateProvider, MyGeneCandidateProvider, UniProtCandidateProvider)
        for cls in classes:
            provider = cls(FakeClient())
            self.assertEqual(provider.propose(EntityResolutionRequest(surface="x")), [])
            self.assertEqual(provider.last_status, "external_lookup_not_enabled")
            hint = provider.supported_entity_types[0]
            candidates = provider.propose(EntityResolutionRequest(surface="x", l1_entity_type_hint=hint, execute=True, network_enabled=True))
            self.assertTrue(candidates[0].is_grounded)
            self.assertTrue(candidates[0].external_ids)


if __name__ == "__main__": unittest.main()
