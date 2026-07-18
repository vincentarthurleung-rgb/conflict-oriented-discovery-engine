"""Central formal/core graph eligibility gate."""

from __future__ import annotations

from typing import Any

from .endpoint_accessors import resolve_graph_endpoint
from .formal_relations import normalize_formal_relation


def _endpoint_reason(endpoint: dict[str, Any], role: str) -> str | None:
    if not endpoint["effective_canonical_id"]:
        status = str(endpoint.get("resolution_status") or "").casefold()
        if "ambiguous" in status:
            return f"{role}_ambiguous"
        if endpoint["is_composite"] and endpoint.get("measured_entity_canonical_id") is None:
            return "measured_entity_unresolved"
        return f"{role}_unresolved"
    if str(endpoint["effective_canonical_id"]).startswith("LOCAL:"):
        return f"{role}_ambiguous"
    if endpoint["is_composite"]:
        if endpoint.get("projection_status") not in {"eligible", "projected"}:
            return endpoint.get("exclusion_reason") or "composite_endpoint_not_decomposed"
        if not endpoint.get("projection_relation"):
            return "projection_relation_missing"
    return None


def core_graph_eligibility(observation: dict[str, Any]) -> dict[str, Any]:
    subject = resolve_graph_endpoint(observation, "subject")
    obj = resolve_graph_endpoint(observation, "object")
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
    if observation.get("query_context_only") is True or observation.get("context_compatibility_status") == "context_query_only":
        reasons.append("query_context_only")
    direction = str(observation.get("direction") or "").casefold()
    if direction not in {"positive", "negative", "increase", "decrease", "activate", "inhibit"}:
        reasons.append("missing_polarity")
    if observation.get("graph_observation_eligible") is False:
        reasons.append("observation_to_graph_failure")
    eligible = not reasons
    relation_status = "registered" if relation else "not_registered"
    conflict_eligible = bool(eligible and relation and relation.conflict_eligible)
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
        "sign": relation.sign if relation else None,
        "measurement_dimension": (subject.get("measurement_dimension") if subject["is_composite"] else None) or (obj.get("measurement_dimension") if obj["is_composite"] else None),
        "subject_effective_canonical_id": subject.get("effective_canonical_id"),
        "subject_effective_canonical_name": subject.get("effective_canonical_name"),
        "object_effective_canonical_id": obj.get("effective_canonical_id"),
        "object_effective_canonical_name": obj.get("effective_canonical_name"),
    }


__all__ = ["core_graph_eligibility"]
