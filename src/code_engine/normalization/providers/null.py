"""Empty terminal provider."""

from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest
from code_engine.normalization.providers.base import CandidateProvider


class NullProvider(CandidateProvider):
    name = "NullProvider"

    def propose(self, request: EntityResolutionRequest) -> list[EntityCandidate]:
        self.last_status = "no_provider_candidates"
        self.last_warnings = [self.last_status]
        return []
