"""Deterministic multi-source candidate adjudication."""

from __future__ import annotations

from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest, EntityResolutionResult


DEFAULT_POLICY = {"high_confidence_threshold": 0.82, "ambiguous_margin": 0.08, "external_grounded_min_score": 0.75, "curated_min_score": 0.70, "llm_ungrounded_max_confidence": 0.45}


def _score(request: EntityResolutionRequest, candidate: EntityCandidate) -> float:
    score = candidate.overall_score or (0.35 * candidate.match_score + 0.2 * candidate.type_score + 0.25 * candidate.source_reliability + 0.2 * candidate.context_score)
    surfaces = {candidate.normalized_surface.casefold(), str(candidate.canonical_name or "").casefold(), *(item.casefold() for item in candidate.aliases)}
    if request.surface.casefold().strip() in surfaces:
        score = min(1.0, score + (0.1 if candidate.is_grounded else 0.03))
    if request.l1_entity_type_hint and candidate.entity_type == request.l1_entity_type_hint:
        score = min(1.0, score + 0.04)
    elif request.allowed_entity_types and candidate.entity_type not in request.allowed_entity_types:
        score *= 0.65
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
