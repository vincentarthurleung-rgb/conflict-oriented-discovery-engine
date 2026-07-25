"""Planning-only post-linkage remediation compression."""
from __future__ import annotations

from typing import Any

from .identities import core_identity
from .remediation import authorization_fields, dedup_group


def plan_remediation_v2(
    observation: dict[str, Any], linkage: dict[str, Any],
    method_recoveries: list[dict[str, Any]], source_block_identity: str | None,
) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    full = linkage["full_machine_reuse_linkage"]
    if full.startswith("blocked_"):
        requirements.append(("core_blocking", full))
    if any(not row["method_present_after"] for row in method_recoveries):
        requirements.append(("enrichment", "measurement_method_unresolved"))
    rows: list[dict[str, Any]] = []
    for category, reason in requirements:
        payload = {
            "observation_identity": observation["source_observation_identity"],
            "structured_observation_revision_identity": observation["identity"],
            "remediation_category": category,
            "reason": reason,
            "provider_reextraction_required": category == "core_blocking",
            "provider_reextraction_candidate": category == "enrichment",
            "source_block_identity": source_block_identity,
            "dedup_group_identity": dedup_group(source_block_identity, reason),
            **authorization_fields(),
            "historical_requirement_unchanged": True,
            "provenance": observation["provenance"],
            "schema_version": "experimental_core_remediation_requirement_v2",
        }
        payload["identity"] = core_identity("experimental_core_remediation_requirement_v2", payload)
        rows.append(payload)
    return rows
