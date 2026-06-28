"""Ungrounded type/resource suggestions; never canonical decisions."""

from __future__ import annotations

from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest
from code_engine.normalization.providers.base import CandidateProvider


class LLMCandidateProposerProvider(CandidateProvider):
    name = "LLMCandidateProposerProvider"
    requires_api = True

    def __init__(self, client=None):
        super().__init__()
        self.client = client

    def propose(self, request: EntityResolutionRequest) -> list[EntityCandidate]:
        self.last_api_calls = 0
        if not (request.execute and request.api_enabled):
            self.last_status = "llm_candidate_proposer_not_enabled"
            self.last_warnings = [self.last_status]
            return []
        if self.client is None:
            self.last_status = "llm_candidate_proposer_not_configured"
            self.last_warnings = [self.last_status]
            return []
        payload = self.client.extract_json("Propose entity type and grounding resources only; do not emit an accepted canonical ID.\nMention: " + request.surface)
        self.last_api_calls = int(getattr(self.client, "api_call_cost", 0))
        items = payload.get("candidates") or [payload]
        result = []
        for index, item in enumerate(items):
            entity_type = item.get("candidate_type") or item.get("entity_type") or "unknown"
            result.append(EntityCandidate(surface=request.surface, normalized_surface=request.surface.casefold(), candidate_id=f"llm:{index}:{request.surface.casefold()}", canonical_id=None, canonical_name=None, entity_type=entity_type, semantic_level=None, source="llm_candidate_proposer", provider_name=self.name, aliases=[], match_type="llm_type_suggestion", match_score=0.4, type_score=0.5, source_reliability=0.2, context_score=0.4, overall_score=0.4, requires_external_grounding=True, is_grounded=False, is_curated=False, is_llm_suggested=True, supporting_context={"suggested_resources": item.get("suggested_resources", []), "reasoning_summary": item.get("reasoning_summary", "")}))
        self.last_status = "candidates_returned" if result else "no_candidates"
        self.last_warnings = ["llm_candidates_are_ungrounded"] if result else []
        return result
