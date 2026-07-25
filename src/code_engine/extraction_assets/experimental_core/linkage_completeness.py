"""Orthogonal experimental-linkage completeness metrics."""
from __future__ import annotations

from typing import Any

from .identities import core_identity


def assess_linkage_v2(
    observation: dict[str, Any], factors: list[dict[str, Any]],
    measurements: list[dict[str, Any]], results: list[dict[str, Any]],
    links: list[dict[str, Any]], semantics: list[dict[str, Any]],
    recoveries: list[dict[str, Any]],
) -> dict[str, Any]:
    measurement_ids = {row["identity"] for row in measurements}
    mr_valid = sum(row.get("measurement_ref") in measurement_ids for row in results)
    measurement_result = (
        "complete" if mr_valid == len(results) and results
        else "partial" if mr_valid else "missing"
    )
    factor_application_links = [
        row for row in links if row["relation_type"] == "factor_applies_to_measurement"
    ]
    if observation["observation_type"] == "descriptive_measurement":
        factor_application = "not_required_by_type"
    elif factor_application_links:
        factor_application = "complete"
    else:
        factor_application = "unresolved"
    required = [row for row in semantics if row["comparison_required"] is True]
    not_required = semantics and all(row["comparison_required"] is False for row in semantics)
    recovered_by_result = {row["result_identity"]: row for row in recoveries}
    comparative_complete = all(
        recovered_by_result[row["observed_result_identity"]]["recovered_comparator_factor_ref"]
        for row in required
    )
    if not_required:
        comparative = "not_required_by_result_semantics"
    elif required and comparative_complete:
        comparative = "complete"
    elif required:
        comparative = "unresolved"
    else:
        comparative = "unresolved"
    evidence_rows = [
        *[row for row in factors if row.get("role") not in {"control", "comparator", "baseline"}],
        *measurements, *results,
    ]
    evidence_total = len(evidence_rows)
    evidence_present = sum(bool(row.get("evidence_anchor_ids")) for row in evidence_rows)
    evidence = (
        "complete" if evidence_present == evidence_total and evidence_total
        else "partial" if evidence_present else "missing"
    )
    if measurement_result != "complete":
        full = "blocked_missing_measurement_result_link"
    elif factor_application in {"missing", "unresolved", "invalid"}:
        full = "blocked_missing_factor_application"
    elif comparative in {"missing", "unresolved", "invalid", "partial"}:
        full = "blocked_missing_comparator"
    elif evidence == "partial":
        full = "complete_with_limitations"
    elif evidence != "complete":
        full = "blocked_missing_evidence"
    else:
        full = "complete"
    payload = {
        "observation_identity": observation["source_observation_identity"],
        "structured_observation_revision_identity": observation["identity"],
        "measurement_result_linkage": measurement_result,
        "factor_measurement_application_linkage": factor_application,
        "comparative_reference_linkage": comparative,
        "evidence_linkage": evidence,
        "full_machine_reuse_linkage": full,
        "limitations": [],
        "provenance": observation["provenance"],
        "schema_version": "experimental_linkage_completeness_v2",
    }
    payload["identity"] = core_identity("experimental_linkage_completeness_v2", payload)
    return payload


def reconcile_metric(
    *, name: str, count: int, semantics: str, replacement: str,
    replacement_count: int, reason: str,
) -> dict[str, Any]:
    payload = {
        "v1_metric_name": name,
        "v1_count": count,
        "v1_semantics": semantics,
        "v2_replacement_metric": replacement,
        "v2_count": replacement_count,
        "discrepancy_reason": reason,
        "backward_compatibility_note": "v1 remains immutable; v2 is the explicit replacement.",
        "schema_version": "experimental_linkage_metric_reconciliation_v1",
    }
    payload["identity"] = core_identity("experimental_linkage_metric_reconciliation_v1", payload)
    return payload
