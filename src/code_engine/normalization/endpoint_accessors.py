"""Shared graph endpoint accessors for raw and projected observation endpoints."""

from __future__ import annotations

from typing import Any


def _first(item: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = item.get(name)
        if value not in (None, "", []):
            return value
    return None


def resolve_graph_endpoint(observation: dict[str, Any], role: str) -> dict[str, Any]:
    if role not in {"subject", "object"}:
        raise ValueError(f"unsupported endpoint role: {role}")
    endpoint = observation.get(f"{role}_endpoint")
    endpoint = endpoint if isinstance(endpoint, dict) else {}
    is_composite = endpoint.get("endpoint_decomposition_status") == "decomposed"
    canonical_id = _first(observation, f"{role}_canonical_id", f"{role}_id", f"normalized_{role}_id")
    canonical_name = _first(observation, f"{role}_canonical_name", f"normalized_{role}", role)
    entity_type = _first(observation, f"{role}_entity_type", f"{role}_type")
    resolution_status = _first(
        observation,
        f"{role}_normalization_status",
        f"{role}_resolution_status",
        f"{role}_entity_resolution_status",
    )
    measured_id = endpoint.get("measured_entity_canonical_id")
    measured_name = endpoint.get("measured_entity_canonical_name")
    measured_type = endpoint.get("measured_entity_type")
    projection_status = endpoint.get("core_projection_status") or observation.get("core_projection_status")
    projection_relation = endpoint.get("core_projection_relation") or observation.get("core_projection_relation")
    exclusion_reason = endpoint.get("core_projection_reason") or observation.get("core_projection_reason")
    effective_id = canonical_id
    effective_name = canonical_name
    effective_type = entity_type
    if is_composite and projection_status in {"eligible", "projected"} and measured_id and projection_relation:
        effective_id = measured_id
        effective_name = measured_name or canonical_name
        effective_type = measured_type or entity_type
        exclusion_reason = None
    return {
        "raw_name": _first(observation, f"{role}_raw", f"{role}_raw_name", role),
        "canonical_id": canonical_id,
        "canonical_name": canonical_name,
        "entity_type": entity_type,
        "resolution_status": resolution_status,
        "is_composite": is_composite,
        "measured_entity_canonical_id": measured_id,
        "measurement_dimension": endpoint.get("measurement_dimension"),
        "effective_canonical_id": effective_id,
        "effective_canonical_name": effective_name,
        "effective_entity_type": effective_type,
        "projection_status": projection_status,
        "projection_relation": projection_relation,
        "exclusion_reason": exclusion_reason,
    }


__all__ = ["resolve_graph_endpoint"]
