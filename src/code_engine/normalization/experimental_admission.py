"""Rejection-only native experimental admission checks.

No independent scientific-review verifier is configured for native V3/Core.
Self-reported flags, reviewer names and file hashes cannot supply that trust
boundary. This module deliberately provides no new authorization mechanism.
"""
from __future__ import annotations

from typing import Any


def is_shadow_artifact(row: dict[str, Any]) -> bool:
    """Recognize explicit shadow provenance, including wrapped/imported payloads.

    This rejects marked artifacts, not arbitrary scientific prose. Removing all
    provenance and fabricating a different record is not a supported promotion.
    """
    pending: list[Any] = [row]
    visited: set[int] = set()
    while pending:
        item = pending.pop()
        if not isinstance(item, (dict, list)) or id(item) in visited:
            continue
        visited.add(id(item))
        if isinstance(item, list):
            pending.extend(item)
            continue
        if (item.get("namespace") == "seen_development_shadow"
                or item.get("execution_path") == "shadow"
                or item.get("shadow_only") is True
                or str(item.get("schema_version") or "").startswith(("ai_scientific_review_shadow_", "shadow_"))
                or any(item.get(k) == "AI_PROVISIONAL_NOT_INDEPENDENTLY_VALIDATED"
                       for k in ("authority_label", "annotation_class", "status"))):
            return True
        pending.extend(item.values())
    return False


def experimental_admission_blocks(row: dict[str, Any]) -> list[str]:
    if is_shadow_artifact(row):
        return ["shadow_artifact_has_no_formal_scientific_authority"]
    native = bool(
        row.get("schema_version") == "fulltext_l1_experimental_observation_schema_v3"
        or row.get("adapter_mode") == "formal_v3_native"
        or any(key in row for key in ("ExperimentalObservationV3", "formal_v3_native_payload", "experimental_core", "ExperimentalCore"))
        or (isinstance(row.get("fulltext_l1_v2_observation"), dict)
            and row["fulltext_l1_v2_observation"].get("schema_version") == "fulltext_l1_experimental_observation_schema_v3")
    )
    if not native:
        return []
    if "scientific_authorization" not in row:
        authorization = "scientific_authorization_missing"
    elif row["scientific_authorization"] is None:
        authorization = "scientific_authorization_null"
    elif type(row["scientific_authorization"]) is not bool:
        authorization = "scientific_authorization_invalid_type"
    elif row["scientific_authorization"] is False:
        authorization = "scientific_authorization_not_granted"
    else:
        authorization = "scientific_authorization_provenance_unverifiable"
    blocks = [authorization]
    # Human Gold is a separate label, never proof of independent review.
    # Even a true flag/reviewer assertion cannot replace a trusted verifier.
    blocks.append("independent_scientific_review_unverified")
    audit = row.get("experimental_core_handoff_audit")
    if not isinstance(audit, dict):
        return blocks + ["experimental_core_audit_missing"]
    if audit.get("structural_integrity") != "structurally_complete":
        blocks.append("experimental_core_integrity_not_complete")
    linkage = audit.get("linkage") or {}
    if linkage.get("full_machine_reuse_linkage") != "complete":
        blocks.append(str(linkage.get("full_machine_reuse_linkage") or "experimental_core_linkage_missing"))
    readiness = audit.get("readiness") or {}
    if readiness.get("status") != "machine_reusable_candidate":
        blocks.append("experimental_core_readiness_not_complete")
    return list(dict.fromkeys(blocks))
