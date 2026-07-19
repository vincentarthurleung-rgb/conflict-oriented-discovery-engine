"""Evidence-aware deterministic external candidate adjudication."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any

from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest, EntityResolutionResult


DEFAULT_POLICY = {
    "accept_threshold": 0.82,
    "ambiguous_threshold": 0.55,
    "ambiguous_margin": 0.08,
    "curated_accept_threshold": 0.78,
    "cache_accept_threshold": 0.82,
    "llm_ungrounded_max_confidence": 0.45,
    # Legacy names remain accepted config inputs.
    "high_confidence_threshold": 0.82,
    "external_grounded_min_score": 0.75,
    "curated_min_score": 0.70,
}

SPECIES_ALIASES = {
    "human": {"human", "homo sapiens", "9606", "taxon:9606", "hsapiens", "human human"},
    "mouse": {"mouse", "mus musculus", "10090", "taxon:10090", "murine"},
    "rat": {"rat", "rattus norvegicus", "10116", "taxon:10116"},
    "bovine": {"bovine", "cow", "bos taurus", "9913", "taxon:9913"},
}

MEASUREMENT_TOKENS = {
    "phosphorylation": {"phospho", "phosphorylation", "phosphorylated", "p-"},
    "expression": {"expression", "mrna", "transcript", "rna"},
    "activity": {"activity", "activation"},
}

MEASUREMENT_ONLY_RE = re.compile(
    r"^\s*(?:p\s*[<=>]\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:nm|um|µm|μm|mm|mg|ug|µg|μg|ml|ul|µl|μl|%|rpm|x\s*g|×\s*g)|od\s*\d{3,4})\s*$",
    re.I,
)

TYPE_GROUPS = {
    "gene_or_protein": {"gene", "protein", "gene_or_protein", "transcript"},
    "chemical": {"chemical", "compound", "drug", "metabolite"},
    "process": {"phenotype", "biological_process", "pathway", "disease"},
    "complex": {"protein_complex", "complex", "receptor", "protein_family"},
}

RELATION_TYPE_COMPATIBILITY = {
    "expression": {"strong": {"gene", "protein", "gene_or_protein", "transcript"}, "weak": {"protein_family", "pathway"}},
    "phosphorylation": {"strong": {"protein", "gene_or_protein", "protein_family", "protein_complex", "complex"}, "weak": {"gene", "receptor"}},
    "proliferation": {"strong": {"phenotype", "biological_process"}, "weak": {"pathway", "disease"}},
    "activation": {"strong": {"protein", "gene_or_protein", "protein_complex", "pathway", "receptor"}, "weak": {"gene", "protein_family"}},
}


def _norm(value: str | None) -> str:
    return " ".join(str(value or "").casefold().replace("_", " ").split())


def _canonical_species(value: str | None) -> str | None:
    text = _norm(value)
    if not text:
        return None
    for canonical, aliases in SPECIES_ALIASES.items():
        if text in aliases or any(alias and alias in text for alias in aliases if not alias.startswith("taxon:")):
            return canonical
    return text


def _infer_species_from_candidate(candidate: EntityCandidate) -> str | None:
    if candidate.candidate_species:
        return candidate.candidate_species
    text = "_".join(str(item or "") for item in (candidate.normalized_surface, candidate.canonical_name, *candidate.aliases)).casefold()
    suffixes = {"human": ("_human", " homo sapiens"), "mouse": ("_mouse", "_mus", " murine"), "rat": ("_rat",), "bovine": ("_bovin", "_cow")}
    for species, markers in suffixes.items():
        if any(marker in text for marker in markers):
            return species
    return None


def _species_compatibility(request: EntityResolutionRequest, candidate: EntityCandidate) -> tuple[float, str, str | None]:
    source_species = _canonical_species(request.species_context)
    candidate_species = _canonical_species(_infer_species_from_candidate(candidate))
    candidate.candidate_species = candidate_species or candidate.candidate_species
    if not source_species:
        return 0.0, "unspecified", None
    if not candidate_species:
        return -0.02, "unspecified", None
    if source_species == candidate_species:
        return 0.08, "exact", None
    ortholog = candidate.supporting_context.get("ortholog_provenance") if isinstance(candidate.supporting_context, dict) else None
    if ortholog:
        candidate.ortholog_provenance = dict(ortholog)
        return 0.04, "ortholog_supported", None
    return -1.0, "incompatible", "rejected_species_incompatible"


def _measurement_dimension(surface: str, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    text = _norm(surface)
    for dimension, tokens in MEASUREMENT_TOKENS.items():
        if any(token in text for token in tokens):
            return dimension
    return None


def _granularity_from_text(value: str | None, entity_type: str | None = None) -> str:
    text = _norm(value)
    etype = _norm(entity_type)
    if etype in {"pathway", "biological process", "phenotype", "protein complex", "receptor", "protein family", "gene", "protein", "transcript"}:
        return etype.replace(" ", "_")
    if "pathway" in text:
        return "pathway"
    if any(token in text for token in ("family", "akt", "tgf beta", "tgfb")) and not re.search(r"\b(?:akt1|akt2|akt3|tgfbr1|tgfbr2)\b", text):
        return "protein_family"
    if "complex" in text:
        return "protein_complex"
    if "receptor" in text:
        return "receptor"
    return "unknown"


def _granularity_compatibility(request: EntityResolutionRequest, candidate: EntityCandidate) -> tuple[float, str, str | None]:
    mention = request.mention_granularity or _granularity_from_text(request.surface, request.l1_entity_type_hint)
    candidate_granularity = candidate.candidate_granularity or _granularity_from_text(candidate.canonical_name or candidate.normalized_surface, candidate.entity_type)
    candidate.mention_granularity = mention
    candidate.candidate_granularity = candidate_granularity
    if MEASUREMENT_ONLY_RE.match(request.surface or ""):
        return -1.0, "incompatible", "rejected_measurement_only"
    if mention == "unknown" or candidate_granularity == "unknown":
        return 0.0, "unknown", None
    if mention == candidate_granularity:
        return 0.06, "exact", None
    if mention == "gene_or_protein" and candidate_granularity in {"gene", "protein", "transcript"}:
        return 0.04, "projectable", None
    if mention == "protein_family" and candidate_granularity in {"gene", "protein", "receptor"}:
        return -0.02, "narrower", None
    if mention in {"gene", "protein"} and candidate_granularity == "protein_family":
        return -0.03, "broader", None
    if mention == "pathway" and candidate_granularity in {"gene", "protein"}:
        return -1.0, "incompatible", "rejected_granularity_incompatible"
    if mention in {"gene", "protein"} and candidate_granularity == "pathway":
        return -1.0, "incompatible", "rejected_granularity_incompatible"
    if mention == "protein" and candidate_granularity in {"gene", "receptor"}:
        return 0.02, "projectable", None
    return -0.04, "broader" if candidate_granularity in {"pathway", "protein_family"} else "narrower", None


def _type_compatibility(request: EntityResolutionRequest, candidate: EntityCandidate) -> tuple[float, str, str | None]:
    expected = _norm(request.l1_entity_type_hint)
    actual = _norm(candidate.entity_type)
    if not expected or expected == "unknown" or not actual:
        return 0.0, "unknown", None
    if expected == actual or (expected == "gene_or_protein" and actual in TYPE_GROUPS["gene_or_protein"]):
        return 0.08, "compatible", None
    if expected in TYPE_GROUPS["chemical"] and actual in TYPE_GROUPS["gene_or_protein"]:
        return -1.0, "incompatible", "rejected_type_incompatible"
    if expected in TYPE_GROUPS["gene_or_protein"] and actual in TYPE_GROUPS["chemical"]:
        return -1.0, "incompatible", "rejected_type_incompatible"
    if expected in TYPE_GROUPS["process"] and actual in TYPE_GROUPS["gene_or_protein"]:
        return -0.12, "partially_compatible", None
    return -0.04, "partially_compatible", None


def _relation_family(relation: str | None, measurement_dimension: str | None) -> str | None:
    text = _norm(relation)
    if measurement_dimension == "phosphorylation" or "phosphorylation" in text or "phosphorylat" in text:
        return "phosphorylation"
    if measurement_dimension == "expression" or "expression" in text or "transcription" in text:
        return "expression"
    if "proliferation" in text:
        return "proliferation"
    if "activat" in text or "inhibit" in text:
        return "activation"
    return None


def _relation_compatibility(request: EntityResolutionRequest, candidate: EntityCandidate, measurement_dimension: str | None) -> tuple[float, str, str | None]:
    family = _relation_family(request.relation, measurement_dimension)
    if not family:
        return 0.0, "unknown", None
    actual = _norm(candidate.entity_type).replace(" ", "_")
    rules = RELATION_TYPE_COMPATIBILITY.get(family, {})
    if actual in rules.get("strong", set()):
        return 0.04, "compatible", None
    if actual in rules.get("weak", set()):
        return -0.04, "weak", None
    return -1.0, "incompatible", "rejected_relation_type_incompatible"


def _provider_agreement(candidates: list[EntityCandidate]) -> dict[str, tuple[int, bool]]:
    providers_by_id: dict[str, set[str]] = defaultdict(set)
    curated_by_id: dict[str, bool] = defaultdict(bool)
    for candidate in candidates:
        if candidate.canonical_id:
            providers_by_id[str(candidate.canonical_id)].add(candidate.provider_name)
            curated_by_id[str(candidate.canonical_id)] = curated_by_id[str(candidate.canonical_id)] or candidate.is_curated
    return {cid: (len(providers), curated_by_id[cid]) for cid, providers in providers_by_id.items()}


def _base_score(request: EntityResolutionRequest, candidate: EntityCandidate) -> float:
    if candidate.overall_score:
        score = candidate.overall_score
    else:
        score = 0.35 * candidate.match_score + 0.2 * candidate.type_score + 0.25 * candidate.source_reliability + 0.2 * candidate.context_score
    request_surface = _norm(request.surface)
    surfaces = {_norm(candidate.normalized_surface), _norm(candidate.canonical_name), *(_norm(item) for item in candidate.aliases)}
    candidate.provider_exact_match = request_surface in surfaces
    if candidate.provider_exact_match:
        score = min(1.0, score + 0.08)
    elif candidate.is_grounded and not any(request_surface and surface and (request_surface in surface or surface in request_surface) and min(len(request_surface), len(surface)) >= 5 for surface in surfaces):
        score *= 0.82
    if "obsolete" in {warning.casefold() for warning in candidate.warnings}:
        score *= 0.5
    return score


def _entropy(scores: list[float]) -> float:
    total = sum(max(score, 0.0) for score in scores)
    if total <= 0:
        return 0.0
    return round(-sum((score / total) * math.log2(score / total) for score in scores if score > 0), 6)


def _reasons(candidate: EntityCandidate, decision: str, *, margin: float, active: dict[str, Any]) -> list[str]:
    reasons = list(candidate.decision_reasons)
    if decision == "accepted":
        if candidate.provider_exact_match:
            reasons.append("accepted_exact_label")
        if candidate.alias_match_score >= 1.0:
            reasons.append("accepted_exact_synonym")
        if candidate.provider_agreement_count > 1:
            reasons.append("accepted_multi_provider_agreement")
        if candidate.species_compatibility == "exact":
            reasons.append("accepted_species_exact")
        if candidate.species_compatibility == "ortholog_supported":
            reasons.append("accepted_ortholog_supported")
    elif decision == "ambiguous":
        if candidate.overall_score < active["accept_threshold"]:
            reasons.append("ambiguous_low_score")
        if margin < active["ambiguous_margin"]:
            reasons.append("ambiguous_small_top_margin")
        if candidate.species_compatibility == "unspecified":
            reasons.append("ambiguous_species_unspecified")
        if candidate.granularity_compatibility == "broader":
            reasons.append("ambiguous_granularity_broader")
        if candidate.granularity_compatibility == "narrower":
            reasons.append("ambiguous_granularity_narrower")
        if candidate.provider_agreement_count <= 1 and not candidate.is_curated:
            reasons.append("ambiguous_single_provider_fuzzy")
        if candidate.relation_type_compatibility == "weak":
            reasons.append("ambiguous_relation_type_weak")
    else:
        if not reasons:
            reasons.append("rejected_below_candidate_floor")
    return list(dict.fromkeys(reasons))


def adjudicate_external_candidate(
    request: EntityResolutionRequest,
    candidate: EntityCandidate,
    *,
    all_candidates: list[EntityCandidate] | None = None,
    provider_rank: int | None = None,
    policy: dict | None = None,
) -> EntityCandidate:
    """Score a candidate and attach auditable evidence fields."""

    active = {**DEFAULT_POLICY, **(policy or {})}
    active["accept_threshold"] = max(active.get("accept_threshold", 0.0), active.get("high_confidence_threshold", 0.0), active.get("external_grounded_min_score", 0.0))
    copy = candidate.model_copy(deep=True)
    copy.provider_rank = provider_rank
    copy.provider_score = copy.overall_score or copy.match_score
    copy.curated_registry_support = bool(copy.is_curated)
    agreement = _provider_agreement(all_candidates or [copy])
    copy.provider_agreement_count, curated_support = agreement.get(str(copy.canonical_id), (1, copy.is_curated))
    copy.curated_registry_support = copy.curated_registry_support or curated_support

    measurement_dimension = _measurement_dimension(request.surface, request.measurement_dimension)
    base = _base_score(request, copy)
    type_delta, type_status, type_hard = _type_compatibility(request, copy)
    species_delta, species_status, species_hard = _species_compatibility(request, copy)
    granularity_delta, granularity_status, granularity_hard = _granularity_compatibility(request, copy)
    relation_delta, relation_status, relation_hard = _relation_compatibility(request, copy, measurement_dimension)
    agreement_delta = min(0.08, 0.04 * max(0, copy.provider_agreement_count - 1))
    curated_delta = 0.08 if copy.curated_registry_support else 0.0
    hard_exclusions = [item for item in (type_hard, species_hard, granularity_hard, relation_hard) if item]
    if not copy.canonical_id and not copy.is_llm_suggested:
        hard_exclusions.append("rejected_invalid_candidate")
    if copy.is_llm_suggested and not copy.is_grounded:
        hard_exclusions.append("external_grounding_required_before_acceptance")
    if MEASUREMENT_ONLY_RE.match(request.surface or ""):
        hard_exclusions.append("rejected_measurement_only")

    final = max(0.0, min(1.0, base + type_delta + species_delta + granularity_delta + relation_delta + agreement_delta + curated_delta))
    if hard_exclusions:
        final = min(final, 0.49)
    copy.overall_score = round(final, 6)
    copy.final_score = copy.overall_score
    copy.type_compatibility = type_status
    copy.species_compatibility = species_status
    copy.species_match_status = species_status
    copy.species_match_score = {"exact": 1.0, "ortholog_supported": 0.75, "unspecified": 0.5, "incompatible": 0.0}.get(species_status, 0.5)
    copy.granularity_compatibility = granularity_status
    copy.granularity_status = granularity_status
    copy.granularity_match_score = {"exact": 1.0, "projectable": 0.85, "broader": 0.45, "narrower": 0.45, "incompatible": 0.0}.get(granularity_status, 0.5)
    copy.relation_type_compatibility = relation_status
    copy.entity_type_score = 1.0 if type_status == "compatible" else 0.65 if type_status == "partially_compatible" else 0.0
    copy.label_match_score = 1.0 if copy.provider_exact_match and _norm(request.surface) == _norm(copy.canonical_name) else 0.0
    copy.alias_match_score = 1.0 if _norm(request.surface) in {_norm(item) for item in copy.aliases} else 0.0
    copy.normalized_string_score = copy.match_score
    copy.assay_context_score = 0.8 if measurement_dimension else 0.5
    copy.source_priority_score = copy.source_reliability
    copy.obsolete_penalty = 1.0 if "obsolete" in {warning.casefold() for warning in copy.warnings} else 0.0
    copy.hard_exclusions = list(dict.fromkeys(hard_exclusions))
    copy.evidence_components = {
        "base_score": round(base, 6),
        "type_delta": round(type_delta, 6),
        "species_delta": round(species_delta, 6),
        "granularity_delta": round(granularity_delta, 6),
        "relation_delta": round(relation_delta, 6),
        "provider_agreement_delta": round(agreement_delta, 6),
        "curated_registry_delta": round(curated_delta, 6),
        "measurement_dimension": measurement_dimension,
        "mention_entity_type": request.l1_entity_type_hint,
        "candidate_entity_type": copy.entity_type,
        "species_context": request.species_context,
        "candidate_species": copy.candidate_species,
        "mention_granularity": copy.mention_granularity,
        "candidate_granularity": copy.candidate_granularity,
        "relation": request.relation,
        "endpoint_role": request.endpoint_role,
    }
    return copy


def _status_for_accept(top: EntityCandidate, active: dict[str, Any]) -> str:
    if top.provider_name == "LocalCacheProvider" and top.overall_score >= active["cache_accept_threshold"]:
        return "resolved_cache"
    if top.is_curated and top.overall_score >= max(active["curated_min_score"], active["curated_accept_threshold"]):
        return "resolved_curated"
    return "accepted_external_grounded"


def _result(
    request: EntityResolutionRequest,
    candidates: list[EntityCandidate],
    *,
    selected: EntityCandidate | None,
    status: str,
    decision: str,
    confidence: float,
    reason: str,
    reasons: list[str],
    hard_exclusions: list[str],
    top_score: float = 0.0,
    second_score: float = 0.0,
    margin: float = 0.0,
) -> EntityResolutionResult:
    accepted = decision == "accepted"
    reviewable = decision in {"accepted", "ambiguous"}
    return EntityResolutionResult(
        request=request,
        candidates=candidates,
        selected_candidate=selected,
        normalization_status=status,
        confidence=round(confidence, 6),
        decision_reason=reason,
        allow_high_confidence_graph_use=accepted,
        requires_manual_review=not accepted,
        warnings=[] if accepted else reasons,
        decision=decision,
        score_components=(selected.evidence_components if selected else {}),
        hard_exclusions=hard_exclusions,
        decision_reasons=reasons,
        alternative_candidates=[item for item in candidates[:5] if selected is None or item.candidate_id != selected.candidate_id],
        accepted_for_formal_graph=accepted,
        accepted_for_reviewable_graph=reviewable,
        accepted_for_conflict=accepted,
        available_for_review=reviewable,
        available_for_exploratory_graph=False,
        conflict_reasoning_eligible=accepted,
        formal_hypothesis_eligible=accepted,
        top_candidate_score=round(top_score, 6),
        second_candidate_score=round(second_score, 6),
        score_margin=round(margin, 6),
        candidate_entropy=_entropy([item.overall_score for item in candidates]),
    )


def adjudicate_entity_candidates(request: EntityResolutionRequest, candidates: list[EntityCandidate], policy: dict | None = None) -> EntityResolutionResult:
    active = {**DEFAULT_POLICY, **(policy or {})}
    active["accept_threshold"] = max(active.get("accept_threshold", 0.0), active.get("high_confidence_threshold", 0.0), active.get("external_grounded_min_score", 0.0))
    if not candidates:
        return _result(
            request, [], selected=None, status="unresolved", decision="rejected", confidence=0.0,
            reason="no_provider_candidates", reasons=["rejected_below_candidate_floor"], hard_exclusions=[],
        )

    scored = [adjudicate_external_candidate(request, candidate, all_candidates=candidates, provider_rank=index + 1, policy=active) for index, candidate in enumerate(candidates)]
    scored.sort(key=lambda item: (-item.overall_score, item.provider_name, str(item.canonical_id)))
    for candidate in scored:
        candidate.decision = "rejected" if candidate.hard_exclusions else ""
        candidate.decision_reasons = list(candidate.hard_exclusions)

    if all(item.is_llm_suggested and not item.is_grounded for item in scored):
        top = scored[0]
        top.decision = "rejected"
        top.decision_reasons = ["external_grounding_required_before_acceptance"]
        confidence = min(active["llm_ungrounded_max_confidence"], top.overall_score)
        return _result(
            request, scored, selected=top, status="llm_suggestion_ungrounded", decision="rejected", confidence=confidence,
            reason="only_ungrounded_llm_suggestions_available", reasons=top.decision_reasons,
            hard_exclusions=top.hard_exclusions, top_score=top.overall_score,
        )

    top = scored[0]
    second = scored[1] if len(scored) > 1 else None
    second_score = second.overall_score if second else 0.0
    margin = top.overall_score - second_score if second else 1.0
    provider_disagreement = bool(second and second.canonical_id != top.canonical_id and margin < active["ambiguous_margin"])

    if top.hard_exclusions:
        top.decision = "rejected"
        top.decision_reasons = _reasons(top, "rejected", margin=margin, active=active)
        return _result(
            request, scored, selected=top, status="rejected_external_candidate", decision="rejected",
            confidence=top.overall_score, reason="top_candidate_hard_excluded",
            reasons=top.decision_reasons, hard_exclusions=top.hard_exclusions,
            top_score=top.overall_score, second_score=second_score, margin=margin,
        )

    if provider_disagreement:
        top.decision = "ambiguous"
        top.decision_reasons = _reasons(top, "ambiguous", margin=margin, active=active) + ["ambiguous_provider_disagreement"]
        return _result(
            request, scored, selected=None, status="ambiguous_external_candidate", decision="ambiguous",
            confidence=top.overall_score, reason=f"top_candidate_margin_{margin:.3f}_below_{active['ambiguous_margin']}",
            reasons=list(dict.fromkeys(top.decision_reasons)), hard_exclusions=[],
            top_score=top.overall_score, second_score=second_score, margin=margin,
        )

    projection_uncertain = top.relation_type_compatibility == "weak" or top.granularity_compatibility in {"broader", "narrower"}

    if top.overall_score >= active["accept_threshold"] and top.is_grounded and not projection_uncertain:
        top.decision = "accepted"
        top.decision_reasons = _reasons(top, "accepted", margin=margin, active=active)
        return _result(
            request, scored, selected=top, status=_status_for_accept(top, active), decision="accepted",
            confidence=top.overall_score, reason="top_candidate_above_accept_threshold",
            reasons=top.decision_reasons, hard_exclusions=[],
            top_score=top.overall_score, second_score=second_score, margin=margin,
        )

    if top.overall_score >= active["ambiguous_threshold"] and top.is_grounded:
        top.decision = "ambiguous"
        top.decision_reasons = _reasons(top, "ambiguous", margin=margin, active=active)
        return _result(
            request, scored, selected=top, status="ambiguous_external_candidate", decision="ambiguous",
            confidence=top.overall_score, reason="top_candidate_between_ambiguous_and_accept_threshold",
            reasons=top.decision_reasons, hard_exclusions=[],
            top_score=top.overall_score, second_score=second_score, margin=margin,
        )

    top.decision = "rejected"
    top.decision_reasons = _reasons(top, "rejected", margin=margin, active=active)
    return _result(
        request, scored, selected=top, status="rejected_external_candidate", decision="rejected",
        confidence=top.overall_score, reason="top_candidate_below_ambiguous_threshold",
        reasons=top.decision_reasons, hard_exclusions=top.hard_exclusions,
        top_score=top.overall_score, second_score=second_score, margin=margin,
    )


def reason_distribution(results: list[EntityResolutionResult]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for result in results:
        counter.update(result.decision_reasons)
    return dict(counter)
