"""Observation-type-aware structural integrity gate."""
from __future__ import annotations

from typing import Any

from .type_policy import ACTIVE_ROLES, GROUP_ROLES


def evaluate_integrity(
    *, observation_type: str, factors: list[dict[str, Any]],
    measurements: list[dict[str, Any]], results: list[dict[str, Any]],
    links: list[dict[str, Any]], reference_audit: dict[str, Any],
    provenance_traceable: bool = True,
) -> tuple[str, list[str], str]:
    if observation_type == "non_experimental_claim":
        return "non_experimental_claim", [], "not_applicable"
    if observation_type == "unresolved":
        return "unresolved", ["observation_type_unresolved"], "unresolved"
    roles = {row["role"] for row in factors}
    if observation_type == "interventional_experiment" and not roles & ACTIVE_ROLES:
        return "incomplete_missing_factor", ["active_factor_missing"], "active_factor_required"
    if observation_type == "observational_comparison" and len(roles & GROUP_ROLES) < 2:
        return "incomplete_missing_factor", ["group_comparison_missing"], "group_or_comparison_required"
    factor_basis = (
        "not_required_by_type_policy" if observation_type == "descriptive_measurement"
        else "type_requirement_satisfied"
    )
    if not measurements:
        return "incomplete_missing_measurement", ["measurement_missing"], factor_basis
    if not results:
        return "incomplete_missing_result", ["observed_result_missing"], factor_basis
    if reference_audit["dangling_refs"] or reference_audit["duplicate_local_ids"]:
        return "invalid_dangling_reference", ["referential_integrity_failure"], factor_basis
    measurement_ids = {row["measurement_id"] for row in measurements}
    if any(row.get("measurement_ref") not in measurement_ids for row in results):
        return "incomplete_missing_linkage", ["result_measurement_ref_missing"], factor_basis
    comparative_missing = any(
        (row.get("_comparative") and not row.get("comparison_factor_refs") and not row.get("baseline_ref"))
        for row in results
    )
    if comparative_missing:
        return "incomplete_missing_linkage", ["comparative_result_comparator_missing"], factor_basis
    if not provenance_traceable:
        return "structurally_complete_with_limitations", ["provenance_incomplete"], factor_basis
    core_evidence = all(row.get("evidence_anchor_ids") for row in factors + measurements + results)
    if not core_evidence:
        return "structurally_complete_with_limitations", ["core_evidence_incomplete"], factor_basis
    return "structurally_complete", [], factor_basis

