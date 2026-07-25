from __future__ import annotations

from typing import Any

from ..layer_identity import layer_identity
from .identities import proposition_core_identity, result_identity, view_identity
from .models import ObservationSemanticViews


def _dim(dimension_id: str, value: str | None, source_path: str) -> dict[str, Any]:
    status = "resolved" if value and value != "unknown" else "unresolved"
    canonical = value if status == "resolved" else None
    return {
        "dimension_id": dimension_id,
        "canonical_identity": layer_identity("semantic_value", "semantic_value_identity_v1",
                                             {"dimension_id": dimension_id, "value": canonical}) if canonical else None,
        "canonical_value": canonical,
        "status": status,
        "source_paths": [source_path],
    }


def project_observation_semantic_views(
    *, observation_id: str, normalized_claim_identity: str, subject: str | None,
    relation_family: str | None, endpoint: str | None, direction: str | None,
    measurement_level: str | None, compartments: list[str],
    observation_context: dict[str, Any] | None,
) -> ObservationSemanticViews:
    core_dims = [
        _dim("canonical_subject_identity", subject, "legacy_candidate.base_subject"),
        _dim("canonical_relation_family", relation_family, "legacy_candidate.relation_family_match"),
        _dim("canonical_endpoint_identity", endpoint, "legacy_candidate.object_family"),
    ]
    core = {
        "schema_version": "proposition_core_view_v2",
        "normalized_claim_identity": normalized_claim_identity,
        "canonical_subject_identity": subject,
        "canonical_relation_family": relation_family,
        "canonical_endpoint_identity": endpoint,
        "outcome_variable_identity": None,
        "proposition_core_dimensions": core_dims,
        "unresolved_core_dimensions": [x["dimension_id"] for x in core_dims if x["status"] == "unresolved"],
        "normalization_identities": [normalized_claim_identity],
    }
    core["proposition_core_identity"] = proposition_core_identity(core)
    anchors: list[str] = []
    failed: list[str] = []
    unavailable: list[str] = []
    if observation_context:
        for fact in observation_context.get("facts", []):
            anchors.extend(fact.get("evidence_anchor_ids", []))
            if fact.get("status") == "unknown":
                unavailable.append(fact["factor_id"])
    result = {
        "schema_version": "contradiction_result_view_v1",
        "observation_id": observation_id,
        "normalized_result_identity": layer_identity("normalized_result", "normalized_result_identity_v1",
                                                     {"direction": direction}),
        "direction": direction,
        "sign": direction,
        "polarity": direction,
        "qualitative_outcome": direction,
        "quantitative_effect": None,
        "result_category": "signed_directional_outcome" if direction else None,
        "evidence_anchor_ids": sorted(set(anchors)),
    }
    result["contradiction_result_identity"] = result_identity(result)
    context_ref = {
        "schema_version": "context_envelope_ref_v1", "observation_id": observation_id,
        "observation_context_identity": observation_context.get("observation_context_identity") if observation_context else None,
        "context_status": observation_context.get("validation_status", "unavailable") if observation_context else "unavailable",
        "context_readiness": "ready" if observation_context and observation_context.get("validation_status") == "validated" else "unavailable",
        "failed_factor_ids": failed, "unavailable_factor_ids": sorted(unavailable),
    }
    context_ref["context_envelope_ref_identity"] = view_identity("context_envelope_ref", context_ref)
    qualifiers = [_dim("measurement_semantic_level", measurement_level, "legacy_candidate.object_process_type")]
    compartment_value = "|".join(sorted(compartments)) if compartments else None
    qualifiers.append(_dim("endpoint_compartment", compartment_value, "legacy_candidate.object_compartments_left_or_right"))
    unresolved = [x["dimension_id"] for x in qualifiers if x["status"] == "unresolved"]
    qualification = {
        "schema_version": "granularity_qualification_view_v1", "observation_id": observation_id,
        "qualifier_dimensions": qualifiers,
        "bridge_status": "required" if any(x["status"] == "resolved" for x in qualifiers) else "unresolved",
        "unresolved_dimensions": unresolved,
    }
    qualification["granularity_qualification_identity"] = view_identity("granularity_qualification", qualification)
    payload = {
        "schema_version": "observation_semantic_views_v1", "observation_id": observation_id,
        "proposition_core_view": core, "contradiction_result_view": result,
        "context_envelope_ref": context_ref, "granularity_qualification_view": qualification,
        "provenance": {"projection_version": "observation_semantic_projection_v1",
                       "direction_in_proposition_core": False, "source_payload_modified": False},
    }
    payload["observation_semantic_views_identity"] = view_identity(
        "observation_semantic_views",
        {k: payload[k] for k in ("observation_id", "proposition_core_view", "contradiction_result_view",
                                "context_envelope_ref", "granularity_qualification_view")},
    )
    return ObservationSemanticViews.model_validate(payload)
