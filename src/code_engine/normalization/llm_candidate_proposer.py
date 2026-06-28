"""Deprecated compatibility wrapper for the candidate-only LLM provider."""

from code_engine.normalization.candidates import EntityResolutionRequest
from code_engine.normalization.providers.llm_proposer import LLMCandidateProposerProvider


class LLMCandidateProposer:
    enabled = False

    def __init__(self, client=None):
        self.provider = LLMCandidateProposerProvider(client)

    def propose(self, raw_text: str):
        return self.provider.propose(EntityResolutionRequest(surface=raw_text, execute=self.enabled, api_enabled=self.enabled))
