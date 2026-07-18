"""Ontology-backed normalization candidate providers."""

from __future__ import annotations

import re
from typing import Any

from code_engine.normalization.candidates import EntityResolutionRequest
from code_engine.normalization.providers.base import ExternalCandidateProvider


TYPE_ONTOLOGY_ROUTES: dict[str, list[str]] = {
    "biological_process": ["go"],
    "pathway": ["reactome", "go"],
    "disease": ["mondo", "doid"],
    "phenotype": ["hp", "efo", "ncit"],
    "compound": ["chebi"],
    "metabolite": ["chebi"],
    "cell_type": ["cl"],
    "cell_line": ["cellosaurus"],
    "tissue": ["uberon"],
    "organ": ["uberon"],
}

OLS_ONTOLOGIES = {"go", "mondo", "doid", "chebi", "cl", "uberon", "hp", "efo", "ncit"}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _synonyms(doc: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("exact_synonyms", "related_synonyms", "narrow_synonyms", "broad_synonyms"):
        raw = doc.get(key) or []
        if isinstance(raw, str):
            raw = [raw]
        values.extend(str(item) for item in raw if item)
    return values


def _score_doc(surface: str, doc: dict[str, Any]) -> tuple[float, str]:
    needle = _norm(surface)
    label = _norm(doc.get("label"))
    synonyms = [_norm(item) for item in _synonyms(doc)]
    if needle == label:
        return 0.94, "ontology_label_exact"
    if needle in synonyms:
        return 0.91, "ontology_exact_synonym"
    if needle and (needle in label or label in needle) and min(len(needle), len(label)) >= 5:
        return 0.78, "ontology_label_containment"
    return 0.0, "ontology_low_similarity"


class OLSOntologyCandidateProvider(ExternalCandidateProvider):
    name = "OLSOntologyCandidateProvider"
    resource_name = "OLS"
    source_reliability = 0.9
    supported_entity_types = [
        "biological_process",
        "pathway",
        "disease",
        "phenotype",
        "compound",
        "metabolite",
        "cell_type",
        "tissue",
        "organ",
    ]

    def cache_key(self, request: EntityResolutionRequest) -> tuple[str, str, tuple[str, ...]]:
        return (
            request.surface.casefold().strip(),
            str(request.l1_entity_type_hint or ""),
            tuple(self._ontologies_for(request)),
        )

    def _ontologies_for(self, request: EntityResolutionRequest) -> list[str]:
        etype = request.l1_entity_type_hint or "unknown"
        routes = list(TYPE_ONTOLOGY_ROUTES.get(etype, []))
        if etype == "phenotype":
            context = f"{request.context_text or ''} {request.surface}".casefold()
            clinical = any(term in context for term in ("patient", "clinical", "human", "syndrome", "disease"))
            routes = ["hp", "mondo"] if clinical else ["efo", "ncit", "go", "mondo"]
        if etype == "pathway":
            routes = ["go"]
        return [item for item in routes if item in OLS_ONTOLOGIES]

    def propose(self, request: EntityResolutionRequest):
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
        ontologies = self._ontologies_for(request)
        if not ontologies:
            self.last_status = "not_applicable"
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
                lambda: self.client.search(request.surface, request=request, ontologies=ontologies),
            )
            self.last_warnings.extend(warnings)
            if status in {"completed_cache_hit", "negative_cache_hit", "retry_pending"}:
                self.last_network_calls = 0
            elif status == "retryable_failed":
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
            records = self.client.search(request.surface, request=request, ontologies=ontologies)
            self.last_network_calls = int(getattr(self.client, "network_call_cost", 0))
        records = list(records or [])
        items: list[dict[str, Any]] = []
        for doc in records or []:
            score, match_type = _score_doc(request.surface, doc)
            if score < 0.75:
                continue
            ontology = str(doc.get("ontology_name") or "").casefold()
            if ontology not in ontologies:
                continue
            entity_type = request.l1_entity_type_hint or "unknown"
            if entity_type == "pathway" and ontology == "go":
                match_type = f"{match_type}_pathway_supplement"
            obo_id = str(doc.get("obo_id"))
            aliases = _synonyms(doc)
            items.append({
                "provider_record_id": obo_id,
                "canonical_id": obo_id,
                "canonical_name": str(doc.get("label")),
                "normalized_surface": _norm(doc.get("label")),
                "entity_type": entity_type,
                "semantic_level": "ontology_term",
                "external_ids": {str(doc.get("ontology_prefix") or ontology).upper(): obo_id, "OLS_IRI": doc.get("iri")},
                "aliases": aliases[:30],
                "match_type": match_type,
                "match_score": score,
                "type_score": 0.93,
                "source_reliability": self.source_reliability,
                "context_score": 0.55,
                "score": score,
                "supporting_context": {
                    "ontology_name": ontology,
                    "ontology_route": ontologies,
                    "definition": (doc.get("description") or [""])[0] if isinstance(doc.get("description"), list) else "",
                },
            })
        result = []
        for index, item in enumerate(items[:5]):
            record_id = str(item["provider_record_id"] or index)
            result.append(self._candidate_from_record(request, item, record_id))
        self._query_cache[key] = [item.model_copy(deep=True) for item in result]
        self.last_status = "candidates_returned" if result else "no_candidates"
        return result

    def _candidate_from_record(self, request: EntityResolutionRequest, item: dict[str, Any], record_id: str):
        from code_engine.normalization.candidates import EntityCandidate

        return EntityCandidate(
            surface=request.surface,
            normalized_surface=str(item.get("normalized_surface") or request.surface.casefold()),
            candidate_id=f"{self.name}:{record_id}",
            canonical_id=str(item.get("canonical_id")),
            canonical_name=str(item.get("canonical_name")),
            entity_type=str(item.get("entity_type") or request.l1_entity_type_hint or "unknown"),
            semantic_level=str(item.get("semantic_level") or "ontology_term"),
            source="external_ontology_provider",
            provider_name=self.name,
            provider_record_id=record_id,
            external_ids=dict(item.get("external_ids") or {}),
            aliases=list(item.get("aliases") or []),
            match_type=str(item.get("match_type") or "ontology_candidate"),
            match_score=float(item.get("match_score", item.get("score", 0.0))),
            type_score=float(item.get("type_score", 0.9)),
            source_reliability=float(item.get("source_reliability", self.source_reliability)),
            context_score=float(item.get("context_score", 0.5)),
            overall_score=float(item.get("score", 0.0)),
            is_grounded=True,
            supporting_context=dict(item.get("supporting_context") or {}),
        )


class ReactomeCandidateProvider(ExternalCandidateProvider):
    name = "ReactomeCandidateProvider"
    resource_name = "Reactome"
    supported_entity_types = ["pathway"]


class CellosaurusCandidateProvider(ExternalCandidateProvider):
    name = "CellosaurusCandidateProvider"
    resource_name = "Cellosaurus"
    supported_entity_types = ["cell_line"]
