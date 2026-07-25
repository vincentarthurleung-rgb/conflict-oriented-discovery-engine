"""Machine-reuse readiness v2; never Human Gold or formal authority."""
from __future__ import annotations

from typing import Any

from .identities import core_identity


def evaluate_readiness_v2(
    observation: dict[str, Any], linkage: dict[str, Any],
    method_recoveries: list[dict[str, Any]], *, context_available: bool,
) -> dict[str, Any]:
    has_core = bool(
        observation["experimental_factor_ids"] or observation["observation_type"] == "descriptive_measurement"
    ) and bool(observation["measurement_ids"]) and bool(observation["observed_result_ids"])
    full = linkage["full_machine_reuse_linkage"]
    method_limited = any(not row["method_present_after"] for row in method_recoveries)
    context_limited = not context_available
    if observation["observation_type"] == "non_experimental_claim":
        status = "non_experimental_claim"
    elif not has_core:
        status = "text_evidence_only"
    elif full == "blocked_missing_comparator":
        status = "structured_core_blocked_comparative_linkage"
    elif full.startswith("blocked_") or full in {"unresolved", "invalid"}:
        status = "structured_core_blocked_other_linkage"
    elif method_limited and context_limited:
        status = "machine_reusable_with_method_and_context_limitations"
    elif method_limited:
        status = "machine_reusable_with_method_limitations"
    elif context_limited:
        status = "machine_reusable_with_context_limitations"
    else:
        status = "machine_reusable_candidate"
    payload = {
        "observation_identity": observation["source_observation_identity"],
        "structured_observation_revision_identity": observation["identity"],
        "linkage_completeness_ref": linkage["identity"],
        "status": status,
        "limitation_codes": [
            *(["measurement_method_unresolved"] if method_limited else []),
            *(["context_unavailable"] if context_limited else []),
        ],
        "human_gold": False,
        "formal_authority": False,
        "downstream_recomputation_candidate": status.startswith("machine_reusable"),
        "provenance": observation["provenance"],
        "schema_version": "experimental_observation_machine_reuse_readiness_v2",
    }
    payload["identity"] = core_identity(
        "experimental_observation_machine_reuse_readiness_v2", payload
    )
    return payload
