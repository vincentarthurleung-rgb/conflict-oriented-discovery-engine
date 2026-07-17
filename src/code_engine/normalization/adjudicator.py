"""Deterministic multi-source candidate adjudication."""

from __future__ import annotations

from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest, EntityResolutionResult


def _norm(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


DEFAULT_POLICY = {"high_confidence_threshold": 0.82, "ambiguous_margin": 0.08, "external_grounded_min_score": 0.75, "curated_min_score": 0.70, "llm_ungrounded_max_confidence": 0.45}


SPECIES_ALIASES = {
    "human": {"human", "homo sapiens", "9606", "taxon:9606"},
    "mouse": {"mouse", "mus musculus", "10090", "taxon:10090", "murine"},
    "rat": {"rat", "rattus norvegicus", "10116", "taxon:10116"},
    "bovine": {"bovine", "cow", "bos taurus", "9913", "taxon:9913"},
}


def _canonical_species(value: str | None) -> str | None:
    text = _norm(value or "")
    if not text:
        return None
    for canonical, aliases in SPECIES_ALIASES.items():
        if text in aliases or any(alias in text for alias in aliases if not alias.startswith("taxon:")):
            return canonical
    return text


def _species_score(request: EntityResolutionRequest, candidate: EntityCandidate) -> tuple[float, str]:
    context = _canonical_species(request.species_context)
    candidate_species = _canonical_species(candidate.candidate_species)
    if not context:
        return 0.5, "unknown"
    if not candidate_species:
        return 0.5, "unknown"
    if context == candidate_species:
        return 1.0, "exact"
    return 0.0, "conflicting"


def _granularity_from_text(value: str | None, entity_type: str | None = None) -> str:
    text = _norm(value or "")
    etype = _norm(entity_type or "")
    if etype in {"pathway", "biological_process", "phenotype", "protein_complex", "receptor", "protein_family"}:
        return etype
    if text in {"tgf-β", "tgf-beta", "tgfb", "transforming growth factor beta"}:
        return "protein_family"
    if any(token in text for token in ("family", "superfamily")):
        return "protein_family"
    if "complex" in text:
        return "protein_complex"
    if "receptor" in text:
        return "receptor"
    if etype in {"gene", "protein"}:
        return etype
    return "unknown"


def _granularity_score(request: EntityResolutionRequest, candidate: EntityCandidate) -> tuple[float, str]:
    mention = request.mention_granularity or _granularity_from_text(request.surface, request.l1_entity_type_hint)
    candidate_granularity = candidate.candidate_granularity or _granularity_from_text(candidate.canonical_name or candidate.normalized_surface, candidate.entity_type)
    if mention == "unknown" or candidate_granularity == "unknown":
        return 0.5, "unknown"
    if mention == candidate_granularity:
        return 1.0, "exact"
    if mention == "gene_or_protein" and candidate_granularity in {"gene", "protein"}:
        return 0.85, "compatible"
    if mention == "protein_family" and candidate_granularity in {"gene", "protein", "receptor"}:
        return 0.15, "too_specific"
    if mention in {"gene", "protein"} and candidate_granularity == "protein_family":
        return 0.4, "too_broad"
    if mention == "protein" and candidate_granularity in {"gene", "receptor"}:
        return 0.65, "compatible"
    if mention == "gene" and candidate_granularity == "protein":
        return 0.65, "compatible"
    return 0.0, "conflicting"


def _alias_score(request_surface: str, candidate: EntityCandidate) -> float:
    request_norm = _norm(request_surface)
    aliases = [_norm(item) for item in candidate.aliases]
    return 1.0 if request_norm in aliases else 0.0


def _score(request: EntityResolutionRequest, candidate: EntityCandidate) -> float:
    score = candidate.overall_score or (0.35 * candidate.match_score + 0.2 * candidate.type_score + 0.25 * candidate.source_reliability + 0.2 * candidate.context_score)
    request_surface = _norm(request.surface)
    surfaces = {_norm(candidate.normalized_surface), _norm(str(candidate.canonical_name or "")), *(_norm(item) for item in candidate.aliases)}
    if request_surface in surfaces:
        score = min(1.0, score + (0.1 if candidate.is_grounded else 0.03))
    elif candidate.is_grounded:
        contained = any(request_surface and surface and (request_surface in surface or surface in request_surface) and min(len(request_surface), len(surface)) >= 5 for surface in surfaces)
        if not contained:
            score *= 0.82
    if request.l1_entity_type_hint and candidate.entity_type == request.l1_entity_type_hint:
        score = min(1.0, score + 0.04)
    elif request.l1_entity_type_hint == "gene_or_protein" and candidate.entity_type in {"gene", "protein"}:
        score = min(1.0, score + 0.03)
    elif request.allowed_entity_types and candidate.entity_type not in request.allowed_entity_types:
        score *= 0.65
    species_score, species_status = _species_score(request, candidate)
    granularity_score, granularity_status = _granularity_score(request, candidate)
    candidate.species_context = request.species_context
    candidate.species_match_score = species_score
    candidate.species_match_status = species_status
    candidate.mention_granularity = request.mention_granularity or _granularity_from_text(request.surface, request.l1_entity_type_hint)
    candidate.candidate_granularity = candidate.candidate_granularity or _granularity_from_text(candidate.canonical_name or candidate.normalized_surface, candidate.entity_type)
    candidate.granularity_match_score = granularity_score
    candidate.granularity_status = granularity_status
    candidate.label_match_score = 1.0 if request_surface == _norm(candidate.canonical_name or candidate.normalized_surface) else 0.0
    candidate.alias_match_score = _alias_score(request.surface, candidate)
    candidate.normalized_string_score = candidate.match_score
    candidate.entity_type_score = 1.0 if request.l1_entity_type_hint and candidate.entity_type == request.l1_entity_type_hint else candidate.type_score
    candidate.assay_context_score = 0.8 if request.measurement_dimension and request.l1_entity_type_hint == candidate.entity_type else 0.5
    candidate.source_priority_score = candidate.source_reliability
    candidate.obsolete_penalty = 1.0 if "obsolete" in {w.casefold() for w in candidate.warnings} else 0.0
    if species_status == "exact":
        score = min(1.0, score + 0.05)
    elif species_status == "conflicting":
        score *= 0.45
        if "species_conflict" not in candidate.warnings:
            candidate.warnings.append("species_conflict")
    if granularity_status == "exact":
        score = min(1.0, score + 0.04)
    elif granularity_status == "compatible":
        score = min(1.0, score + 0.01)
    elif granularity_status == "too_specific":
        score *= 0.55
        if "candidate_too_specific_for_mention" not in candidate.warnings:
            candidate.warnings.append("candidate_too_specific_for_mention")
    elif granularity_status == "conflicting":
        score *= 0.5
        if "granularity_conflict" not in candidate.warnings:
            candidate.warnings.append("granularity_conflict")
    if candidate.obsolete_penalty:
        score *= 0.5
    candidate.final_score = round(max(0.0, min(1.0, score)), 6)
    return round(max(0.0, min(1.0, score)), 6)


def adjudicate_entity_candidates(request: EntityResolutionRequest, candidates: list[EntityCandidate], policy: dict | None = None) -> EntityResolutionResult:
    active = {**DEFAULT_POLICY, **(policy or {})}
    if not candidates:
        return EntityResolutionResult(request=request, candidates=[], normalization_status="unresolved", confidence=0.0, decision_reason="no_provider_candidates", requires_manual_review=True, warnings=["entity_unresolved_no_candidates"])
    scored = []
    for candidate in candidates:
        copy = candidate.model_copy(deep=True)
        copy.overall_score = _score(request, copy)
        scored.append(copy)
    scored.sort(key=lambda item: (-item.overall_score, item.provider_name, str(item.canonical_id)))
    top = scored[0]
    if top.species_match_status == "conflicting":
        return EntityResolutionResult(request=request, candidates=scored, selected_candidate=top, normalization_status="manual_review_required", confidence=top.overall_score, decision_reason="top_candidate_species_conflict", requires_manual_review=True, warnings=["candidate_species_conflict"])
    if top.granularity_status in {"too_specific", "conflicting"}:
        return EntityResolutionResult(request=request, candidates=scored, selected_candidate=top, normalization_status="manual_review_required", confidence=top.overall_score, decision_reason=f"top_candidate_granularity_{top.granularity_status}", requires_manual_review=True, warnings=[f"candidate_granularity_{top.granularity_status}"])
    if all(item.is_llm_suggested and not item.is_grounded for item in scored):
        confidence = min(active["llm_ungrounded_max_confidence"], top.overall_score)
        return EntityResolutionResult(request=request, candidates=scored, selected_candidate=top, normalization_status="llm_suggestion_ungrounded", confidence=confidence, decision_reason="only_ungrounded_llm_suggestions_available", requires_manual_review=True, warnings=["external_grounding_required_before_acceptance"])
    second = scored[1] if len(scored) > 1 else None
    margin = top.overall_score - second.overall_score if second else 1.0
    if second and margin < active["ambiguous_margin"] and second.canonical_id != top.canonical_id:
        return EntityResolutionResult(request=request, candidates=scored, normalization_status="ambiguous", confidence=top.overall_score, decision_reason=f"top_candidate_margin_{margin:.3f}_below_{active['ambiguous_margin']}", requires_manual_review=True, warnings=["multiple_close_entity_candidates"])
    if top.provider_name == "LocalCacheProvider" and top.is_grounded and top.overall_score >= active["high_confidence_threshold"]:
        status = "resolved_cache"
    elif top.is_curated and top.overall_score >= max(active["curated_min_score"], active["high_confidence_threshold"]):
        status = "resolved_curated"
    elif top.is_grounded and top.overall_score >= max(active["external_grounded_min_score"], active["high_confidence_threshold"]):
        status = "resolved_external_grounded"
    else:
        return EntityResolutionResult(request=request, candidates=scored, selected_candidate=top, normalization_status="manual_review_required", confidence=top.overall_score, decision_reason="top_candidate_below_high_confidence_acceptance_threshold", requires_manual_review=True, warnings=["candidate_requires_manual_review"])
    return EntityResolutionResult(request=request, candidates=scored, selected_candidate=top, normalization_status=status, confidence=top.overall_score, decision_reason=f"unique_{status}_candidate_above_threshold", allow_high_confidence_graph_use=True, requires_manual_review=False, warnings=[])
