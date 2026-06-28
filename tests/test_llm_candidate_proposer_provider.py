import unittest

from code_engine.normalization.candidates import EntityResolutionRequest
from code_engine.normalization.providers.llm_proposer import LLMCandidateProposerProvider


class FakeLLM:
    def extract_json(self, prompt): return {"candidate_type":"compound","suggested_resources":["PubChem"],"reasoning_summary":"intervention"}


class LLMCandidateProviderTests(unittest.TestCase):
    def test_disabled_and_fake_ungrounded(self):
        provider = LLMCandidateProposerProvider(FakeLLM())
        self.assertEqual(provider.propose(EntityResolutionRequest(surface="sirolimus")), [])
        candidate = provider.propose(EntityResolutionRequest(surface="sirolimus", execute=True, api_enabled=True))[0]
        self.assertTrue(candidate.is_llm_suggested)
        self.assertFalse(candidate.is_grounded)
        self.assertIsNone(candidate.canonical_id)


if __name__ == "__main__": unittest.main()
