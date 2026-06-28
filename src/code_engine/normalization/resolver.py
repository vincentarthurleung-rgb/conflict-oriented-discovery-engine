"""ResolverCascade compatibility facade over EntityResolutionHub."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from code_engine.normalization.audit import EntityResolutionAuditWriter
from code_engine.normalization.cache import EntityCache
from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest
from code_engine.normalization.hub import EntityResolutionHub
from code_engine.normalization.lexical import normalize_lexical_surface
from code_engine.normalization.models import EntityRelation, NormalizationCandidate, NormalizationDecision
from code_engine.normalization.providers.chembl import ChEMBLCandidateProvider
from code_engine.normalization.providers.llm_proposer import LLMCandidateProposerProvider
from code_engine.normalization.providers.local_cache import LocalCacheProvider
from code_engine.normalization.providers.local_curated import LocalCuratedProvider
from code_engine.normalization.providers.mygene import MyGeneCandidateProvider
from code_engine.normalization.providers.null import NullProvider
from code_engine.normalization.providers.pubchem import PubChemCandidateProvider
from code_engine.normalization.providers.uniprot import UniProtCandidateProvider
from code_engine.normalization.registry import DEFAULT_REGISTRY_PATH, LocalBiomedicalRegistry


DANGEROUS_WARNINGS = {"receptor_complex_to_gene_merge", "metabolite_to_parent_merge", "phenotype_to_gene_merge", "assay_to_phenotype_merge_without_relation"}


def _legacy_candidate(candidate: EntityCandidate) -> NormalizationCandidate | None:
    if not candidate.canonical_id or not candidate.canonical_name:
        return None
    return NormalizationCandidate(canonical_id=candidate.canonical_id, canonical_name=candidate.canonical_name, entity_type=candidate.entity_type or "unknown", semantic_level=candidate.semantic_level or "unknown", aliases=candidate.aliases, external_ids=candidate.external_ids, relations=[EntityRelation.model_validate(item) for item in candidate.supporting_context.get("relations", [])], score=candidate.overall_score, source=candidate.source, match_type=candidate.match_type, warnings=candidate.warnings)


class ResolverCascade:
    def __init__(self, registry: LocalBiomedicalRegistry | None = None, *, registry_path: str | Path | None = None, allow_fallback: bool = False, domain_id: str = "general_biomedical", entity_registry_profile: str = "general_entity_resolution_hub", resolver_policy_id: str = "conservative_resolver_v2", hub: EntityResolutionHub | None = None, run_dir: str | Path | None = None, execute: bool = False, network_enabled: bool = False, api_enabled: bool = False, entity_network_lookup: bool = False, entity_llm_proposer: bool = False, external_clients: dict[str, Any] | None = None, llm_client: Any | None = None, adjudicator_policy: dict | None = None):
        self.domain_id = domain_id
        self.entity_registry_profile = entity_registry_profile
        self.resolver_policy_id = resolver_policy_id
        self.domain_specific_resolution_used = False
        self.domain_resolution_warnings: list[str] = []
        self.execute, self.network_enabled, self.api_enabled = execute, network_enabled, api_enabled
        self.entity_network_lookup, self.entity_llm_proposer = entity_network_lookup, entity_llm_proposer
        if hub is not None:
            self.hub = hub
            self.registry = registry
            return
        clients = external_clients or {}
        providers = []
        if registry is not None:
            providers.append(LocalCuratedProvider(registry=registry))
        elif registry_path is not None and Path(registry_path) != DEFAULT_REGISTRY_PATH:
            providers.append(LocalCuratedProvider(registry_path=registry_path))
        providers.append(LocalCacheProvider(EntityCache()))
        providers.extend([PubChemCandidateProvider(clients.get("pubchem")), ChEMBLCandidateProvider(clients.get("chembl")), MyGeneCandidateProvider(clients.get("mygene")), UniProtCandidateProvider(clients.get("uniprot"))])
        if entity_llm_proposer:
            providers.append(LLMCandidateProposerProvider(llm_client))
        providers.append(NullProvider())
        audit = EntityResolutionAuditWriter(run_dir) if run_dir else None
        cache = EntityCache(accepted_writes_enabled=bool(execute)) if execute else None
        self.hub = EntityResolutionHub(providers, adjudicator_policy, audit, entity_cache=cache)
        self.registry = registry

    def _domain_metadata(self) -> dict[str, Any]:
        return {"domain_id": self.domain_id, "entity_registry_profile": self.entity_registry_profile, "resolver_policy_id": self.resolver_policy_id, "domain_specific_resolution_used": self.domain_specific_resolution_used, "domain_resolution_warnings": list(self.domain_resolution_warnings)}

    def resolve_entity(self, raw_text: str, context: dict[str, Any] | None = None, allow_fallback: bool = False) -> NormalizationDecision:
        lexical = normalize_lexical_surface(raw_text)
        if lexical.invalid:
            return NormalizationDecision(raw_text=lexical.raw_text, normalized_surface=lexical.normalized_surface, normalization_status="empty_or_invalid", confidence=0.0, decision_reason="empty_invalid_or_placeholder_input", warnings=lexical.warnings, entity_resolution_status="unresolved", requires_manual_review=True, **self._domain_metadata())
        context = context or {}
        request = EntityResolutionRequest(surface=lexical.raw_text, context_text=context.get("context_text"), domain_id=self.domain_id, entity_registry_profile=self.entity_registry_profile, resolver_policy_id=self.resolver_policy_id, allowed_entity_types=list(context.get("allowed_entity_types") or []), l1_entity_type_hint=context.get("expected_entity_type") or context.get("l1_entity_type_hint"), paper_id=context.get("paper_id"), claim_id=context.get("claim_id"), observation_id=context.get("observation_id"), network_enabled=bool(self.execute and self.network_enabled and self.entity_network_lookup), api_enabled=bool(self.execute and self.api_enabled and self.entity_llm_proposer), execute=self.execute)
        result = self.hub.resolve(request)
        selected = result.selected_candidate
        legacy_candidates = [item for item in (_legacy_candidate(candidate) for candidate in result.candidates) if item]
        if result.normalization_status in {"resolved_curated", "resolved_external_grounded", "resolved_cache"} and selected:
            legacy_status = "resolved"
        elif result.normalization_status == "ambiguous" or (result.normalization_status == "manual_review_required" and result.candidates):
            legacy_status = "ambiguous"
        else:
            legacy_status = "unresolved_fallback"
        canonical_name = str(selected.canonical_name or "") if selected else (lexical.normalized_surface.upper() if legacy_status == "unresolved_fallback" else "")
        selected_legacy = _legacy_candidate(selected) if selected else None
        return NormalizationDecision(raw_text=lexical.raw_text, normalized_surface=lexical.normalized_surface, canonical_id=str(selected.canonical_id or "") if selected and result.allow_high_confidence_graph_use else "", canonical_name=canonical_name, entity_type=str(selected.entity_type or "unknown") if selected else "unknown", semantic_level=str(selected.semantic_level or "unknown") if selected else "unresolved", external_ids=dict(selected.external_ids) if selected else {}, relations=selected_legacy.relations if selected_legacy else [], normalization_status=legacy_status, confidence=result.confidence, resolver="entity_resolution_hub_v1", match_type=selected.match_type if selected else "unresolved", candidates=legacy_candidates, decision_reason=result.decision_reason, allow_high_confidence_graph_use=result.allow_high_confidence_graph_use, warnings=list(dict.fromkeys(lexical.warnings + result.warnings + (["uppercase_fallback_low_confidence"] if legacy_status == "unresolved_fallback" else []))), candidate_count=len(result.candidates), candidate_provider_names=list(dict.fromkeys(item.provider_name for item in result.candidates)), selected_candidate_id=selected.candidate_id if selected else None, entity_resolution_status=result.normalization_status, requires_manual_review=result.requires_manual_review, audit_ref=result.audit_ref, **self._domain_metadata())


def resolve_entity(raw_text: str, context: dict[str, Any] | None = None, allow_fallback: bool = False, **resolver_kwargs: Any) -> NormalizationDecision:
    return ResolverCascade(allow_fallback=allow_fallback, **resolver_kwargs).resolve_entity(raw_text, context=context, allow_fallback=allow_fallback)
