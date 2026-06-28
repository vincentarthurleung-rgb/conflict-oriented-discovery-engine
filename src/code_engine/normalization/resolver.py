"""Deterministic type-aware and relation-aware biomedical resolver cascade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from code_engine.normalization.entity_type import classify_entity_type
from code_engine.normalization.lexical import normalize_lexical_surface
from code_engine.normalization.models import NormalizationCandidate, NormalizationDecision
from code_engine.normalization.registry import DEFAULT_REGISTRY_PATH, LocalBiomedicalRegistry


DANGEROUS_WARNINGS = {
    "receptor_complex_to_gene_merge",
    "metabolite_to_parent_merge",
    "phenotype_to_gene_merge",
    "assay_to_phenotype_merge_without_relation",
}


class ResolverCascade:
    def __init__(
        self,
        registry: LocalBiomedicalRegistry | None = None,
        *,
        registry_path: str | Path = DEFAULT_REGISTRY_PATH,
        allow_fallback: bool = False,
        domain_id: str = "general_biomedical",
        entity_registry_profile: str = "general_biomedical_registry",
        resolver_policy_id: str = "conservative_resolver_v2",
    ):
        self.domain_id = domain_id
        self.entity_registry_profile = entity_registry_profile
        self.resolver_policy_id = resolver_policy_id
        self.domain_resolution_warnings: list[str] = []
        requested = Path(registry_path)
        domain_specific_used = False
        if registry is None and entity_registry_profile != "general_biomedical_registry":
            profile_path = Path("configs/normalization/registries") / f"{entity_registry_profile}.json"
            if profile_path.exists():
                requested = profile_path
                domain_specific_used = True
            else:
                self.domain_resolution_warnings.append("domain_registry_missing_general_registry_used")
        self.registry = registry or LocalBiomedicalRegistry(requested, allow_fallback=allow_fallback)
        self.domain_specific_resolution_used = domain_specific_used

    def _domain_metadata(self) -> dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "entity_registry_profile": self.entity_registry_profile,
            "resolver_policy_id": self.resolver_policy_id,
            "domain_specific_resolution_used": self.domain_specific_resolution_used,
            "domain_resolution_warnings": list(self.domain_resolution_warnings),
        }

    @staticmethod
    def _danger_warnings(surface: str, candidate: NormalizationCandidate) -> list[str]:
        warnings = []
        if "receptor" in surface and candidate.entity_type == "gene":
            warnings.append("receptor_complex_to_gene_merge")
        if surface in {"norketamine", "hydroxynorketamine"} and candidate.canonical_id == "CHEM:KETAMINE":
            warnings.append("metabolite_to_parent_merge")
        if any(term in surface for term in ("response", "behavior", "immobility")) and candidate.entity_type == "gene":
            warnings.append("phenotype_to_gene_merge")
        if "test" in surface and candidate.entity_type == "phenotype":
            warnings.append("assay_to_phenotype_merge_without_relation")
        return warnings

    def resolve_entity(self, raw_text: str, context: dict[str, Any] | None = None, allow_fallback: bool = False) -> NormalizationDecision:
        lexical = normalize_lexical_surface(raw_text)
        if lexical.invalid:
            return NormalizationDecision(
                raw_text=lexical.raw_text,
                normalized_surface=lexical.normalized_surface,
                normalization_status="empty_or_invalid",
                confidence=0.0,
                match_type="uppercase_fallback",
                decision_reason="empty_invalid_or_placeholder_input",
                warnings=lexical.warnings,
                **self._domain_metadata(),
            )
        candidates = self.registry.lookup(lexical.raw_text, lexical.normalized_surface)
        expected_type = str((context or {}).get("expected_entity_type") or "")
        if expected_type:
            typed = [candidate for candidate in candidates if candidate.entity_type == expected_type]
            if typed:
                candidates = typed
        inferred_type = classify_entity_type(raw_text, lexical.normalized_surface, candidates)
        if not candidates:
            fallback_name = lexical.normalized_surface.upper()
            return NormalizationDecision(
                raw_text=lexical.raw_text,
                normalized_surface=lexical.normalized_surface,
                canonical_name=fallback_name,
                entity_type=inferred_type,
                semantic_level="unresolved",
                normalization_status="unresolved_fallback",
                confidence=0.3,
                resolver="resolver_cascade_v1",
                match_type="uppercase_fallback",
                decision_reason="no_registry_candidate_uppercase_retained_for_traceability_only",
                allow_high_confidence_graph_use=False,
                warnings=[*lexical.warnings, *self.registry.warnings, "uppercase_fallback_low_confidence"],
                **self._domain_metadata(),
            )
        top = candidates[0]
        close_candidates = [candidate for candidate in candidates if top.score - candidate.score <= 0.05]
        danger = self._danger_warnings(lexical.normalized_surface, top)
        if len({candidate.canonical_id for candidate in close_candidates}) > 1 or top.match_type == "fuzzy_candidate" or danger:
            return NormalizationDecision(
                raw_text=lexical.raw_text,
                normalized_surface=lexical.normalized_surface,
                entity_type=inferred_type,
                semantic_level="ambiguous_candidate_set",
                normalization_status="ambiguous",
                confidence=min(0.7, top.score),
                resolver="resolver_cascade_v1",
                match_type=top.match_type,
                candidates=candidates,
                decision_reason="multiple_close_candidates_or_non_exact_match_requires_review",
                allow_high_confidence_graph_use=False,
                warnings=list(dict.fromkeys([*lexical.warnings, *self.registry.warnings, *danger, *top.warnings])),
                **self._domain_metadata(),
            )
        return NormalizationDecision(
            raw_text=lexical.raw_text,
            normalized_surface=lexical.normalized_surface,
            canonical_id=top.canonical_id,
            canonical_name=top.canonical_name,
            entity_type=top.entity_type,
            semantic_level=top.semantic_level,
            external_ids=top.external_ids,
            relations=top.relations,
            normalization_status="resolved",
            confidence=max(0.9, top.score),
            resolver="resolver_cascade_v1",
            match_type=top.match_type,
            candidates=candidates,
            decision_reason="unique_exact_local_registry_candidate",
            allow_high_confidence_graph_use=True,
            warnings=list(dict.fromkeys([*lexical.warnings, *self.registry.warnings, *top.warnings])),
            **self._domain_metadata(),
        )


def resolve_entity(raw_text: str, context: dict[str, Any] | None = None, allow_fallback: bool = False, **resolver_kwargs: Any) -> NormalizationDecision:
    return ResolverCascade(allow_fallback=allow_fallback, **resolver_kwargs).resolve_entity(raw_text, context=context, allow_fallback=allow_fallback)
