"""Versioned cardinality policy and conservative type assessment."""
from __future__ import annotations

from typing import Any

from .identities import core_identity
from .models import ObservationTypeCardinalityPolicy, ObservationTypePolicyEntry

ACTIVE_ROLES = {"intervention", "treatment", "exposure", "genetic_manipulation"}
GROUP_ROLES = {"cohort", "experimental_group", "control", "comparator", "baseline"}


def build_policy() -> ObservationTypeCardinalityPolicy:
    entries = [
        ObservationTypePolicyEntry(
            observation_type="interventional_experiment",
            factor_requirement="active_factor_required", measurement_minimum=1,
            result_minimum=1, result_measurement_ref_required=True,
            comparator_ref_required_for_comparative_result=True,
            machine_reuse_eligible=True,
        ),
        ObservationTypePolicyEntry(
            observation_type="observational_comparison",
            factor_requirement="group_or_comparison_required", measurement_minimum=1,
            result_minimum=1, result_measurement_ref_required=True,
            comparator_ref_required_for_comparative_result=True,
            machine_reuse_eligible=True,
        ),
        ObservationTypePolicyEntry(
            observation_type="descriptive_measurement",
            factor_requirement="not_required_by_type_policy", measurement_minimum=1,
            result_minimum=1, result_measurement_ref_required=True,
            comparator_ref_required_for_comparative_result=False,
            machine_reuse_eligible=True,
        ),
        ObservationTypePolicyEntry(
            observation_type="non_experimental_claim",
            factor_requirement="not_applicable", measurement_minimum=0,
            result_minimum=0, result_measurement_ref_required=False,
            comparator_ref_required_for_comparative_result=False,
            machine_reuse_eligible=False,
        ),
        ObservationTypePolicyEntry(
            observation_type="unresolved",
            factor_requirement="unresolved", measurement_minimum=1,
            result_minimum=1, result_measurement_ref_required=True,
            comparator_ref_required_for_comparative_result=True,
            machine_reuse_eligible=False,
        ),
    ]
    payload = {"policy_id": "observation_type_cardinality_policy_v1", "entries": [
        entry.model_dump(mode="json") for entry in entries
    ], "immutable": True}
    return ObservationTypeCardinalityPolicy(
        **payload, identity=core_identity("observation_type_cardinality_policy_v1", payload)
    )


def assess_observation_type(
    *, source: dict[str, Any], factor_roles: set[str],
    measurement_count: int, result_count: int,
) -> tuple[str, str]:
    """Use explicit structure/status only; never classify from free claim keywords."""
    explicit = source.get("observation_type") or source.get("observation_type_candidate")
    allowed = {entry.observation_type for entry in build_policy().entries}
    if explicit in allowed:
        return str(explicit), "explicit_source_type"
    statement_role = source.get("statement_role")
    if statement_role in {"background_claim", "discussion_claim", "mechanistic_hypothesis", "review_statement"}:
        return "non_experimental_claim", "explicit_statement_role"
    if factor_roles & ACTIVE_ROLES and measurement_count and result_count:
        return "interventional_experiment", "deterministic_structural_policy"
    if len(factor_roles & GROUP_ROLES) >= 2 and measurement_count and result_count:
        return "observational_comparison", "deterministic_structural_policy"
    if measurement_count and result_count and source.get("experiment"):
        return "descriptive_measurement", "deterministic_structural_policy"
    return "unresolved", "insufficient_explicit_structure"

