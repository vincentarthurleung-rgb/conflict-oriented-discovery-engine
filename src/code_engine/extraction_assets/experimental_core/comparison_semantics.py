"""Conflict-neutral, fail-closed result comparison semantics."""
from __future__ import annotations

from typing import Any

from .identities import core_identity


def classify_comparison(
    result: dict[str, Any], observation: dict[str, Any],
    source_observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observation_type = observation["observation_type"]
    source_observation = source_observation or {}
    source_result = source_observation.get("observation", {})
    relation = " ".join(str(value or "") for value in (
        source_observation.get("candidate_relation", {}).get("relation_raw"),
        source_observation.get("candidate_relation", {}).get("evidence_design_raw"),
        source_result.get("observed_result"),
    )).casefold()
    if source_result.get("comparison_raw") is None and (
        "associated" in relation or "correlation" in relation
    ):
        semantics, required, basis = (
            "association_or_correlation", False,
            "explicit_association_relation_policy_v1",
        )
    elif (
        observation_type == "interventional_experiment"
        and source_result.get("comparison_raw") is None
        and not result.get("comparison_factor_refs")
        and not result.get("baseline_ref")
    ):
        semantics, required, basis = "unresolved", None, "fail_closed_unresolved_policy_v1"
    elif observation_type == "interventional_experiment":
        semantics, required, basis = (
            "intervention_vs_control", True, "observation_type_policy_v1"
        )
    elif observation_type == "observational_comparison":
        semantics, required, basis = (
            "group_vs_group", True, "observation_type_policy_v1"
        )
    elif observation_type == "descriptive_measurement":
        semantics, required, basis = (
            "absolute_descriptive_observation", False,
            "descriptive_measurement_type_policy_v1",
        )
    else:
        semantics, required, basis = "unresolved", None, "fail_closed_unresolved_policy_v1"
    payload = {
        "observed_result_identity": result["identity"],
        "observation_type": observation_type,
        "comparison_semantics": semantics,
        "comparison_required": required,
        "comparison_basis": basis,
        "source_structured_refs": [observation["identity"]],
        "evidence_refs": list(result.get("evidence_anchor_ids", [])),
        "semantic_authority": "type_policy" if required is not None else "unresolved",
        "provenance": result["provenance"],
        "schema_version": "observed_result_comparison_semantics_v1",
    }
    payload["identity"] = core_identity("observed_result_comparison_semantics_v1", payload)
    return payload
