"""Candidate-only provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from typing import Any

from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest
from code_engine.normalization.entity_type import canonical_entity_type, compatible_entity_types
from code_engine.normalization.providers.patient_execution import L2ProviderExecutionManager, ProviderNegativeTerminal


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
        hinted = canonical_entity_type(request.l1_entity_type_hint)
        compatible = set(compatible_entity_types(hinted))
        type_ok = not self.supported_entity_types or not hinted or hinted == "unknown" or hinted in self.supported_entity_types or bool(compatible & set(self.supported_entity_types))
        domain_ok = not self.supported_domains or not request.domain_id or request.domain_id in self.supported_domains
        return type_ok and domain_ok

    @abstractmethod
    def propose(self, request: EntityResolutionRequest) -> list[EntityCandidate]: ...


class ExternalCandidateProvider(CandidateProvider):
    requires_network = True
    resource_name = "External"
    source_reliability = 0.9

    def __init__(self, client=None, execution_manager: L2ProviderExecutionManager | None = None):
        super().__init__()
        self.client = client
        self.execution_manager = execution_manager
        self._query_cache: dict[tuple[str, str, tuple[str, ...]], list[EntityCandidate]] = {}

    def cache_key(self, request: EntityResolutionRequest) -> tuple[str, str, tuple[str, ...], str, str]:
        return (
            request.surface.casefold().strip(),
            str(request.l1_entity_type_hint or ""),
            tuple(request.allowed_entity_types),
            str(request.species_context or ""),
            str(request.mention_granularity or ""),
        )

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
        key = self.cache_key(request)
        if self.execution_manager is None and key in self._query_cache:
            self.last_status = "cache_hit"
            self.last_warnings = ["provider_query_cache_hit"]
            return [item.model_copy(deep=True) for item in self._query_cache[key]]
        if self.execution_manager is not None:
            status, records, warnings = self.execution_manager.execute(
                self.name,
                request,
                key,
                lambda: self.client.search(request.surface, request=request),
                network_call_cost=int(getattr(self.client, "network_call_cost", 1)),
            )
            self.last_warnings.extend(warnings)
            if status in {"completed_cache_hit", "negative_cache_hit", "retry_pending"}:
                self.last_network_calls = 0
            elif status in {"retryable_failed"}:
                self.last_network_calls = 0
                self.last_status = status
                return []
            else:
                self.last_network_calls = int(getattr(self.client, "network_call_cost", 0))
            if status == "negative_terminal":
                self.last_status = "no_candidates"
                self._query_cache[key] = []
                return []
            if status == "negative_cache_hit":
                self.last_status = "negative_cache_hit"
                self._query_cache[key] = []
                return []
            if status == "retry_pending":
                self.last_status = "retry_pending"
                return []
        else:
            try:
                records = self.client.search(request.surface, request=request)
            except ProviderNegativeTerminal as exc:
                self.last_status = "no_candidates"
                self.last_warnings = [exc.category]
                self._query_cache[key] = []
                return []
            self.last_network_calls = int(getattr(self.client, "network_call_cost", 0))
        records = list(records or [])
        result = []
        for index, item in enumerate(records or []):
            record_id = str(item.get("provider_record_id") or item.get("id") or item.get("canonical_id") or index)
            external_ids = dict(item.get("external_ids") or {})
            external_ids.setdefault(self.resource_name, record_id)
            canonical_name = str(item.get("canonical_name") or item.get("name") or request.surface)
            normalized_surface = str(item.get("normalized_surface") or canonical_name.casefold())
            result.append(EntityCandidate(surface=request.surface, normalized_surface=normalized_surface, candidate_id=f"{self.name}:{record_id}", canonical_id=str(item.get("canonical_id") or f"{self.resource_name}:{record_id}"), canonical_name=canonical_name, entity_type=item.get("entity_type") or (request.l1_entity_type_hint if request.l1_entity_type_hint != "unknown" else None), semantic_level=item.get("semantic_level"), source="external_provider", provider_name=self.name, provider_record_id=record_id, external_ids=external_ids, aliases=list(item.get("aliases") or []), match_type=str(item.get("match_type") or "external_candidate"), match_score=float(item.get("match_score", item.get("score", 0.9))), type_score=float(item.get("type_score", 0.9)), source_reliability=float(item.get("source_reliability", self.source_reliability)), context_score=float(item.get("context_score", 0.5)), overall_score=float(item.get("overall_score", item.get("score", 0.85))), is_grounded=True, supporting_context=dict(item.get("supporting_context") or {}), warnings=list(item.get("warnings") or []), raw_provider_payload_ref=item.get("raw_provider_payload_ref"),
                                  species_context=request.species_context, candidate_species=item.get("species") or item.get("organism") or item.get("taxon"),
                                  mention_granularity=request.mention_granularity, candidate_granularity=item.get("granularity") or item.get("semantic_level")))
        self._query_cache[key] = [item.model_copy(deep=True) for item in result]
        self.last_status = "candidates_returned" if result else "no_candidates"
        return result
