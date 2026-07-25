"""Referential integrity and conservative deterministic linkage."""
from __future__ import annotations

from typing import Any

from .identities import core_identity


def duplicate_local_ids(*record_groups: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for group in record_groups:
        for row in group:
            local_id = str(
                row.get("local_factor_id") or row.get("local_measurement_id")
                or row.get("local_result_id") or ""
            )
            if not local_id:
                continue
            if local_id in seen:
                duplicates.add(local_id)
            seen.add(local_id)
    return sorted(duplicates)


def resolve_explicit_links(
    observation_revision_identity: str,
    factors: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create only explicit-reference or structurally unique links.

    A unique measurement/result pair is authoritative because the old scalar
    schema can represent only one such relation. Factors are not automatically
    linked merely because they share an observation.
    """
    links: list[dict[str, Any]] = []
    measurement_ids = {
        str(row["local_measurement_id"]): str(row["measurement_id"]) for row in measurements
    }
    factor_ids = {str(row["local_factor_id"]): str(row["factor_id"]) for row in factors}
    for result in results:
        ref = result.get("_explicit_measurement_local_ref")
        method = "explicit_local_reference"
        if not ref and len(measurements) == 1 and len(results) == 1:
            ref = measurements[0]["local_measurement_id"]
            method = "legacy_scalar_one_to_one"
        if ref in measurement_ids:
            payload = {
                "observation_revision_identity": observation_revision_identity,
                "relation_type": "measurement_produces_result",
                "source_ref": measurement_ids[str(ref)],
                "target_ref": result["observed_result_id"],
                "order": None,
                "evidence_anchor_ids": sorted(set(
                    result.get("evidence_anchor_ids", [])
                    + next(row["evidence_anchor_ids"] for row in measurements
                           if row["local_measurement_id"] == ref)
                )),
                "derivation_method": method,
                "validation_status": "valid",
                "authority_status": "deterministic" if method.startswith("legacy") else "authoritative",
            }
            payload["linkage_id"] = core_identity("experimental_observation_linkage_v1", payload)
            links.append(payload)
        for factor_ref in result.get("_comparison_local_refs", []):
            if factor_ref in factor_ids:
                payload = {
                    "observation_revision_identity": observation_revision_identity,
                    "relation_type": "result_compared_against_factor",
                    "source_ref": result["observed_result_id"],
                    "target_ref": factor_ids[factor_ref],
                    "order": None,
                    "evidence_anchor_ids": result.get("evidence_anchor_ids", []),
                    "derivation_method": "explicit_local_reference",
                    "validation_status": "valid",
                    "authority_status": "authoritative",
                }
                payload["linkage_id"] = core_identity("experimental_observation_linkage_v1", payload)
                links.append(payload)
    return sorted(links, key=lambda row: row["linkage_id"])


def reference_audit(
    observation_revision_identity: str,
    factors: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    results: list[dict[str, Any]],
    links: list[dict[str, Any]],
) -> dict[str, Any]:
    ids = {
        *(row["factor_id"] for row in factors),
        *(row["measurement_id"] for row in measurements),
        *(row["observed_result_id"] for row in results),
    }
    dangling = sorted({
        ref for link in links for ref in (link["source_ref"], link["target_ref"])
        if ref not in ids
    })
    measurement_ids = {row["measurement_id"] for row in measurements}
    orphan_results = sorted(
        row["observed_result_id"] for row in results
        if row.get("measurement_ref") not in measurement_ids
    )
    duplicates = duplicate_local_ids(factors, measurements, results)
    return {
        "observation_revision_identity": observation_revision_identity,
        "dangling_refs": dangling,
        "duplicate_local_ids": duplicates,
        "orphan_results": orphan_results,
        "cross_observation_reference_errors": [],
        "valid": not dangling and not duplicates and not orphan_results,
    }

