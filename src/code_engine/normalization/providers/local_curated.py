"""Explicitly configured curated-anchor provider."""

from __future__ import annotations

from pathlib import Path

from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest
from code_engine.normalization.lexical import normalize_lexical_surface
from code_engine.normalization.providers.base import CandidateProvider
from code_engine.normalization.registry import LocalBiomedicalRegistry


class LocalCuratedProvider(CandidateProvider):
    name = "LocalCuratedProvider"

    def __init__(self, registry_path: str | Path | None = None, registry: LocalBiomedicalRegistry | None = None):
        super().__init__()
        self.registry = registry
        if self.registry is None and registry_path is not None:
            self.registry = LocalBiomedicalRegistry(registry_path)

    def propose(self, request: EntityResolutionRequest) -> list[EntityCandidate]:
        self.last_warnings = []
        if self.registry is None:
            self.last_status = "curated_source_not_configured"
            self.last_warnings = [self.last_status]
            return []
        lexical = normalize_lexical_surface(request.surface)
        result = []
        for item in self.registry.lookup(request.surface, lexical.normalized_surface):
            result.append(EntityCandidate(surface=request.surface, normalized_surface=lexical.normalized_surface, candidate_id=f"{self.name}:{item.canonical_id}", canonical_id=item.canonical_id, canonical_name=item.canonical_name, entity_type=item.entity_type, semantic_level=item.semantic_level, source="local_curated_anchor", provider_name=self.name, provider_record_id=item.canonical_id, external_ids=item.external_ids, aliases=item.aliases, match_type=item.match_type, match_score=item.score, type_score=1.0 if not request.l1_entity_type_hint or request.l1_entity_type_hint == item.entity_type else 0.4, source_reliability=0.95, context_score=0.5, overall_score=item.score, is_grounded=True, is_curated=True, supporting_context={"relations": [relation.model_dump() for relation in item.relations]}, warnings=item.warnings))
        self.last_status = "candidates_returned" if result else "no_candidates"
        return result
