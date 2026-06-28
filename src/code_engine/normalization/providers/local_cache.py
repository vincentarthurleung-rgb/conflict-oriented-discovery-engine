"""Provider for previously accepted audited mappings."""

from code_engine.normalization.cache import EntityCache
from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest
from code_engine.normalization.lexical import normalize_lexical_surface
from code_engine.normalization.providers.base import CandidateProvider


class LocalCacheProvider(CandidateProvider):
    name = "LocalCacheProvider"

    def __init__(self, cache: EntityCache | None = None):
        super().__init__()
        self.cache = cache or EntityCache()

    def propose(self, request: EntityResolutionRequest) -> list[EntityCandidate]:
        lexical = normalize_lexical_surface(request.surface)
        records = self.cache.lookup(lexical.normalized_surface)
        result = []
        for index, item in enumerate(records):
            payload = dict(item)
            payload.update({"surface": request.surface, "normalized_surface": lexical.normalized_surface, "candidate_id": payload.get("candidate_id") or f"cache:{index}:{lexical.normalized_surface}", "source": "accepted_mapping_cache", "provider_name": self.name, "match_type": "cache_exact", "match_score": float(payload.get("match_score", 1.0)), "source_reliability": float(payload.get("source_reliability", 0.9)), "overall_score": float(payload.get("overall_score", payload.get("confidence", 0.9))), "is_grounded": True, "is_curated": bool(payload.get("is_curated", False)), "is_llm_suggested": False})
            for extra in ("normalization_status", "confidence"):
                payload.pop(extra, None)
            result.append(EntityCandidate.model_validate(payload))
        self.last_status = "candidates_returned" if result else "cache_miss"
        self.last_warnings = ["entity_candidate_cache_used"] if result else []
        return result
