"""Candidate-only provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest


class CandidateProvider(ABC):
    name = "CandidateProvider"
    supported_entity_types: list[str] = []
    supported_domains: list[str] = []
    requires_network = False
    requires_api = False

    def __init__(self):
        self.last_warnings: list[str] = []
        self.last_status: str = "ready"
        self.last_network_calls: int = 0
        self.last_api_calls: int = 0

    def can_handle(self, request: EntityResolutionRequest) -> bool:
        hinted = request.l1_entity_type_hint
        type_ok = not self.supported_entity_types or not hinted or hinted == "unknown" or hinted in self.supported_entity_types
        domain_ok = not self.supported_domains or not request.domain_id or request.domain_id in self.supported_domains
        return type_ok and domain_ok

    @abstractmethod
    def propose(self, request: EntityResolutionRequest) -> list[EntityCandidate]: ...


class ExternalCandidateProvider(CandidateProvider):
    requires_network = True
    resource_name = "External"
    source_reliability = 0.9

    def __init__(self, client=None):
        super().__init__()
        self.client = client

    def propose(self, request: EntityResolutionRequest) -> list[EntityCandidate]:
        self.last_warnings = []
        self.last_network_calls = 0
        if not (request.execute and request.network_enabled):
            self.last_status = "external_lookup_not_enabled"
            self.last_warnings = [self.last_status]
            return []
        if self.client is None:
            self.last_status = "external_provider_not_configured"
            self.last_warnings = [self.last_status]
            return []
        records = self.client.search(request.surface, request=request)
        self.last_network_calls = int(getattr(self.client, "network_call_cost", 0))
        result = []
        for index, item in enumerate(records or []):
            record_id = str(item.get("provider_record_id") or item.get("id") or item.get("canonical_id") or index)
            external_ids = dict(item.get("external_ids") or {})
            external_ids.setdefault(self.resource_name, record_id)
            result.append(EntityCandidate(surface=request.surface, normalized_surface=str(item.get("normalized_surface") or request.surface.casefold()), candidate_id=f"{self.name}:{record_id}", canonical_id=str(item.get("canonical_id") or f"{self.resource_name}:{record_id}"), canonical_name=str(item.get("canonical_name") or item.get("name") or request.surface), entity_type=item.get("entity_type") or (request.l1_entity_type_hint if request.l1_entity_type_hint != "unknown" else None), semantic_level=item.get("semantic_level"), source="external_provider", provider_name=self.name, provider_record_id=record_id, external_ids=external_ids, aliases=list(item.get("aliases") or []), match_type=str(item.get("match_type") or "external_candidate"), match_score=float(item.get("match_score", item.get("score", 0.9))), type_score=float(item.get("type_score", 0.9)), source_reliability=float(item.get("source_reliability", self.source_reliability)), context_score=float(item.get("context_score", 0.5)), overall_score=float(item.get("overall_score", item.get("score", 0.85))), is_grounded=True, raw_provider_payload_ref=item.get("raw_provider_payload_ref")))
        self.last_status = "candidates_returned" if result else "no_candidates"
        return result
