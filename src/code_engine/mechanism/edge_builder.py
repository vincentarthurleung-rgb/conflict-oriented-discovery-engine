"""Build paper-grounded mechanism edges from normalized observations."""

from __future__ import annotations

import hashlib
from typing import Any

from code_engine.mechanism.evidence_linker import link_evidence_to_mechanism_edges
from code_engine.mechanism.models import MechanismEdge


PLANNING_SOURCES = {"llm_semantic_intake", "deterministic_degraded_fallback", "user_intent_llm_parser", "user_intent", "semantic_intake_repair"}


def _stable(*parts: Any) -> str:
    return hashlib.sha256("\x1f".join(str(item or "") for item in parts).encode()).hexdigest()[:16]


def _is_planning_record(item: dict[str, Any]) -> bool:
    source = str(item.get("source", "")).casefold()
    purpose = str(item.get("purpose", "")).casefold()
    return bool(item.get("is_evidence") is False or source in PLANNING_SOURCES or "user_intent" in source or "seed" in source or "search" in purpose)


def _is_abstract_screening_record(item: dict[str, Any]) -> bool:
    return (
        str(item.get("source_scope", "")).casefold() == "abstract"
        or str(item.get("evidence_tier", "")).casefold() in {
            "abstract_screening", "abstract_conflict_signal", "coverage_gap",
        }
    )


def _relation(raw: str, sign: int) -> tuple[str, str]:
    text = str(raw or "").casefold().replace("-", "_")
    mappings = (
        (("bind", "affinity"), "binding"), (("expression", "expressed", "upregulat", "downregulat"), "expression_increase" if sign > 0 else "expression_decrease"),
        (("pathway", "signal"), "pathway_activation" if sign > 0 else "pathway_inhibition"),
        (("activat", "increase", "enhanc", "promot"), "activation"), (("inhibit", "decrease", "suppress", "block"), "inhibition"),
        (("modulat", "regulat"), "modulation"), (("clinical", "response", "remission", "effect"), "clinical_effect"),
        (("associat", "correlat", "interact"), "association"),
    )
    for needles, result in mappings:
        if any(needle in text for needle in needles):
            return result, str(raw or result)
    return "unknown_mechanism_relation", str(raw or "unknown")


def _role(relation_type: str) -> str:
    return {
        "binding": "drug_target_binding", "expression_increase": "gene_expression_change", "expression_decrease": "gene_expression_change",
        "pathway_activation": "pathway_change", "pathway_inhibition": "pathway_change", "clinical_effect": "phenotypic_or_clinical_effect",
        "modulation": "receptor_modulation", "activation": "receptor_modulation", "inhibition": "receptor_modulation", "association": "protein_interaction",
    }.get(relation_type, "unknown")


def _sign(observation: dict[str, Any]) -> int:
    raw = observation.get("relation_sign", observation.get("direct_relation_sign", 0))
    if isinstance(raw, (int, float)):
        return 1 if raw > 0 else -1 if raw < 0 else 0
    normalized = str(raw or "").casefold()
    if normalized in {"positive", "+", "+1", "activation", "increase"}:
        return 1
    if normalized in {"negative", "-", "-1", "inhibition", "decrease"}:
        return -1
    return 0


def build_mechanism_edges_from_observations(observations: list[dict], evidence_records: list[dict] | None = None, l1_claims: list[dict] | None = None, domain_profile: dict | None = None, include_low_confidence: bool = False) -> list[MechanismEdge]:
    claims = {str(item.get("claim_id")): item for item in (l1_claims or []) if item.get("claim_id") and not _is_planning_record(item)}
    edges = []
    for observation in observations:
        if _is_planning_record(observation) or _is_abstract_screening_record(observation):
            continue
        generic_status = str(observation.get("normalization_status", "resolved"))
        statuses = {str(observation.get("subject_normalization_status", generic_status)), str(observation.get("object_normalization_status", generic_status))}
        bad_statuses = {"ambiguous", "unresolved", "unresolved_fallback", "empty_or_invalid", "low_confidence"}
        low_quality = str(observation.get("normalization_quality", "")).casefold() in {"low_confidence", "ambiguous", "unresolved"}
        usable = bool(observation.get("allow_high_confidence_graph_use", not observation.get("exclude_from_high_confidence_conflict", False))) and not statuses.intersection(bad_statuses) and not low_quality
        if not usable and not include_low_confidence:
            continue
        paper_id = str(observation.get("paper_id") or observation.get("source_asset") or "").strip()
        if not paper_id:
            continue
        observation_id = str(observation.get("observation_id") or observation.get("triple_id") or _stable(paper_id, observation.get("evidence_sentence"), observation.get("subject"), observation.get("object")))
        subject_id = observation.get("subject_canonical_id")
        object_id = observation.get("object_canonical_id")
        subject_name = observation.get("subject_canonical_name") or observation.get("normalized_subject") or observation.get("subject")
        object_name = observation.get("object_canonical_name") or observation.get("normalized_object") or observation.get("object")
        sign = _sign(observation)
        direction = "positive" if sign > 0 else "negative" if sign < 0 else "neutral"
        relation_type, relation_label = _relation(str(observation.get("relation_type") or observation.get("relation_raw") or ""), sign)
        claim_id = str(observation.get("claim_id") or observation.get("l1_claim_id") or "")
        linked_claim = claims.get(claim_id, {})
        evidence_id = str(observation.get("evidence_id") or linked_claim.get("evidence_id") or "")
        confidence = min(1.0, max(0.0, float(observation.get("belief_weight", observation.get("confidence", 0.0)))))
        warnings = [] if usable else ["low_confidence_observation_included", "not_for_high_confidence_graph_use"]
        if not subject_id or not object_id:
            warnings.append("canonical_id_missing_stable_node_hash_used")
        edge = MechanismEdge(
            edge_id=_stable(observation_id, subject_id or subject_name, object_id or object_name, relation_type, direction),
            source_node_id=str(subject_id or _stable("node", subject_name)), target_node_id=str(object_id or _stable("node", object_name)),
            subject_canonical_id=subject_id, object_canonical_id=object_id, subject_name=str(subject_name or ""), object_name=str(object_name or ""),
            relation_type=relation_type, relation_label=relation_label, direction=direction, mechanism_role=_role(relation_type),
            domain_id=str(observation.get("domain_id") or (domain_profile or {}).get("domain_id") or "") or None,
            subdomain_id=(domain_profile or {}).get("subdomain_id"), evidence_ids=[evidence_id] if evidence_id else [],
            claim_ids=[claim_id] if claim_id else [], observation_ids=[observation_id], paper_ids=[paper_id],
            context=dict(observation.get("context") or {}), context_slots={**{key: [{"observation_id": observation_id, "value": value}] for key, value in dict(observation.get("context") or {}).items()}, **({"evidence_sentence": [{"observation_id": observation_id, "value": observation.get("evidence_sentence")}]} if observation.get("evidence_sentence") else {})},
            support_count=1 if direction == "positive" else 0, contradict_count=1 if direction == "negative" else 0,
            neutral_count=1 if direction == "neutral" else 0, confidence=confidence,
            normalization_quality="low_confidence" if not usable else str(observation.get("normalization_quality") or "resolved_or_acceptable"),
            allow_high_confidence_graph_use=usable, warnings=warnings,
        )
        edges.append(edge)
    return link_evidence_to_mechanism_edges(edges, evidence_records or [], l1_claims)
