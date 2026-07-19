"""Central formal/core graph eligibility gate."""

from __future__ import annotations

from typing import Any

from .endpoint_accessors import resolve_graph_endpoint
from .formal_relations import normalize_formal_relation
from .intervention_semantics import STRICT_CAUSAL_CORE, interpret_evidence_semantics


def _endpoint_reason(endpoint: dict[str, Any], role: str) -> str | None:
    if not endpoint["effective_canonical_id"]:
        status = str(endpoint.get("resolution_status") or "").casefold()
        if "ambiguous" in status:
            return f"{role}_ambiguous"
        if endpoint["is_composite"] and endpoint.get("measured_entity_canonical_id") is None:
            return "measured_entity_unresolved"
        return f"{role}_unresolved"
    if str(endpoint["effective_canonical_id"]).startswith("RUN:"):
        return "endpoint_unresolved_fallback"
    if str(endpoint["effective_canonical_id"]).startswith("LOCAL:"):
        return f"{role}_ambiguous"
    status = str(endpoint.get("resolution_status") or "").casefold()
    if status and status not in {"resolved", "accepted", "resolved_runtime_hint"}:
        return f"{role}_resolution_not_accepted"
    if endpoint["is_composite"]:
        if endpoint.get("projection_status") not in {"eligible", "projected"}:
            return endpoint.get("exclusion_reason") or "composite_endpoint_not_decomposed"
        if not endpoint.get("projection_relation"):
            return "projection_relation_missing"
    return None


def core_graph_eligibility(observation: dict[str, Any]) -> dict[str, Any]:
    subject = resolve_graph_endpoint(observation, "subject")
    obj = resolve_graph_endpoint(observation, "object")
    sem_payload = observation.get("evidence_semantics")
    sem = sem_payload if isinstance(sem_payload, dict) else interpret_evidence_semantics(observation).to_dict()
    relation = normalize_formal_relation(observation)
    reasons = []
    for role, endpoint in (("subject", subject), ("object", obj)):
        reason = _endpoint_reason(endpoint, role)
        if reason:
            reasons.append(reason)
    if relation is None:
        reasons.append("projection_relation_not_registered" if observation.get("core_projection_relation") else "relation_not_formal_graph_eligible")
    elif not relation.formal_graph_eligible:
        reasons.append("relation_not_formal_graph_eligible")
    elif relation.semantic_kind != "causal":
        reasons.append("non_causal_evidence_design")
    if observation.get("query_context_only") is True or observation.get("context_compatibility_status") == "context_query_only":
        reasons.append("query_context_only")
    derived_sign = sem.get("derived_causal_sign")
    if derived_sign not in {-1, 1}:
        reasons.append("missing_polarity")
    if sem.get("retained_layer") != STRICT_CAUSAL_CORE:
        reasons.append((sem.get("semantic_hard_exclusions") or ["non_strict_scientific_edge_layer"])[0])
    if not sem.get("endpoint_semantics_eligible"):
        reasons.append("endpoint_semantics_not_eligible")
    if not sem.get("relation_semantics_eligible"):
        reasons.append("relation_semantics_not_eligible")
    if not sem.get("causal_direction_eligible"):
        reasons.append("intervention_semantics_unresolved" if str(sem.get("evidence_design")).endswith("function") else "missing_direction_provenance")
    if sem.get("causal_direction_eligible") and not sem.get("direction_provenance_consistent"):
        reasons.append("direction_provenance_inconsistent")
    if not sem.get("evidence_design_eligible"):
        reasons.append("non_causal_evidence_design")
    if not sem.get("species_projection_valid"):
        reasons.append("species_projection_unverified")
    if not sem.get("granularity_projection_valid"):
        reasons.append("unsupported_isoform_projection")
    if not sem.get("measurement_projection_valid"):
        reasons.append("measurement_projection_missing")
    for reason in sem.get("semantic_hard_exclusions") or []:
        reasons.append(reason)
    if relation and derived_sign in {-1, 1} and relation.sign in {-1, 1} and relation.sign != derived_sign:
        reasons.append("direction_provenance_inconsistent")
    if observation.get("relation_family") == "association_only" and relation and relation.family in {"positive_regulation", "negative_regulation", "regulation"}:
        reasons.append("association_projected_as_regulation")
    if observation.get("graph_observation_eligible") is False:
        reasons.append("observation_to_graph_failure")
    eligible = not list(dict.fromkeys(reasons))
    relation_status = "registered" if relation else "not_registered"
    conflict_eligible = bool(eligible and relation and relation.conflict_eligible and sem.get("conflict_eligible"))
    reason = "eligible_and_emitted" if eligible else reasons[0]
    return {
        "eligible": eligible,
        "reason": reason,
        "reasons": list(dict.fromkeys(reasons)),
        "subject_endpoint_status": subject.get("resolution_status"),
        "object_endpoint_status": obj.get("resolution_status"),
        "relation_status": relation_status,
        "confidence_status": "accepted",
        "projection_status": observation.get("core_projection_status"),
        "conflict_eligible": conflict_eligible,
        "formal_relation": relation.relation if relation else None,
        "relation_family": relation.family if relation else observation.get("relation_family"),
        "sign": int(derived_sign) if derived_sign in {-1, 1} else (relation.sign if relation else None),
        "direction_provenance": sem.get("causal_direction_provenance"),
        "evidence_design": sem.get("evidence_design"),
        "inference_type": sem.get("inference_type"),
        "scientific_edge_layer": sem.get("retained_layer"),
        "core_exclusion_reasons": list(dict.fromkeys(reasons)),
        "measurement_dimension": (subject.get("measurement_dimension") if subject["is_composite"] else None) or (obj.get("measurement_dimension") if obj["is_composite"] else None),
        "subject_effective_canonical_id": subject.get("effective_canonical_id"),
        "subject_effective_canonical_name": subject.get("effective_canonical_name"),
        "object_effective_canonical_id": obj.get("effective_canonical_id"),
        "object_effective_canonical_name": obj.get("effective_canonical_name"),
    }


__all__ = ["core_graph_eligibility"]
