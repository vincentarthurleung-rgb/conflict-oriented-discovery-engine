from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict
from ..layer_identity import layer_identity


class GranularityBridgeAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["granularity_bridge_assessment_v1"] = "granularity_bridge_assessment_v1"
    dimension_id: str
    qualifier_a: str | None
    qualifier_b: str | None
    qualifier_a_identity: str | None
    qualifier_b_identity: str | None
    bridge_status: Literal["exact_match", "policy_equivalent", "policy_compatible",
                           "partially_compatible", "incompatible", "unresolved", "not_applicable"]
    bridge_policy_identity: str | None
    assessment_basis: list[str]
    deterministic_authority: bool
    human_review_required: bool
    provenance: dict[str, Any]
    granularity_bridge_identity: str


def assess_granularity_bridge(*, dimension_id: str, qualifier_a: dict[str, Any],
                              qualifier_b: dict[str, Any], policy_identity: str | None = None,
                              policy_mapping: str | None = None) -> GranularityBridgeAssessment:
    a, b = qualifier_a.get("canonical_value"), qualifier_b.get("canonical_value")
    aid, bid = qualifier_a.get("canonical_identity"), qualifier_b.get("canonical_identity")
    if a is None and b is None:
        status, authority, review, basis = "not_applicable", True, False, ["both qualifiers unavailable"]
    elif aid is not None and aid == bid:
        status, authority, review, basis = "exact_match", True, False, ["exact canonical qualifier identity match"]
    elif policy_identity and policy_mapping in {"equivalent", "compatible"}:
        status, authority, review, basis = f"policy_{policy_mapping}", True, False, ["explicit versioned bridge policy"]
    else:
        status, authority, review, basis = "unresolved", False, True, ["nonexact qualifiers have no explicit versioned bridge policy"]
    payload = {"schema_version":"granularity_bridge_assessment_v1", "dimension_id":dimension_id,
               "qualifier_a":a, "qualifier_b":b, "qualifier_a_identity":aid, "qualifier_b_identity":bid,
               "bridge_status":status, "bridge_policy_identity":policy_identity,
               "assessment_basis":basis, "deterministic_authority":authority,
               "human_review_required":review,
               "provenance":{"string_similarity_used":False,"case_specific_rule_used":False}}
    payload["granularity_bridge_identity"] = layer_identity(
        "granularity_bridge", "granularity_bridge_identity_v1",
        {k: payload[k] for k in ("dimension_id","qualifier_a_identity","qualifier_b_identity",
                                 "bridge_status","bridge_policy_identity")})
    return GranularityBridgeAssessment.model_validate(payload)
