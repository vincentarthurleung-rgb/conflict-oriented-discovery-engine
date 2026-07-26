"""Result/Observation denominator reconciliation for comparator blocker sets."""
from __future__ import annotations

from typing import Any

from .identities import core_identity


def reconcile_comparator_sets(
    *,
    recovery_unresolved_ids: set[str],
    comparative_reference_unresolved_ids: set[str],
    readiness_blocked_comparator_ids: set[str],
    result_to_observation: dict[str, str],
    comparison_semantics: dict[str, dict[str, Any]],
    other_linkage_blockers: dict[str, list[str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Emit exact sets and one explanatory membership row per Result identity."""
    union = sorted(
        recovery_unresolved_ids
        | comparative_reference_unresolved_ids
        | readiness_blocked_comparator_ids
    )
    rows = []
    for result_id in union:
        flags = {
            "recovery_unresolved": result_id in recovery_unresolved_ids,
            "comparative_reference_unresolved": result_id in comparative_reference_unresolved_ids,
            "readiness_blocked_comparator": result_id in readiness_blocked_comparator_ids,
        }
        sem = comparison_semantics.get(result_id, {})
        blockers = sorted(other_linkage_blockers.get(result_id, []))
        if flags["comparative_reference_unresolved"] and not flags["recovery_unresolved"]:
            reason = "added_by_result_level_comparison_semantics_unresolved"
        elif flags["comparative_reference_unresolved"] and not flags["readiness_blocked_comparator"]:
            reason = (
                "other_linkage_blocker_precedence"
                if blockers else "readiness_policy_excludes_comparator_blocker"
            )
        else:
            reason = "shared_unresolved_comparator"
        row = {
            "observation_identity": result_to_observation[result_id],
            "result_identity": result_id,
            "membership_flags": flags,
            "denominator_type": "result",
            "comparison_semantics": sem.get("comparison_semantics", "unresolved"),
            "other_linkage_blockers": blockers,
            "readiness_precedence_rule": (
                "factor_application_before_comparator_v2" if blockers else "comparator_gate_v2"
            ),
            "difference_reason": reason,
        }
        row["identity"] = core_identity("comparator_unresolved_set_membership_v2", row)
        row["schema_version"] = "comparator_unresolved_set_membership_v2"
        rows.append(row)
    r, c, b = recovery_unresolved_ids, comparative_reference_unresolved_ids, readiness_blocked_comparator_ids
    payload = {
        "recovery_unresolved_ids": sorted(r),
        "comparative_reference_unresolved_ids": sorted(c),
        "readiness_blocked_comparator_ids": sorted(b),
        "recovery_only_ids": sorted(r - c - b),
        "comparative_only_ids": sorted(c - r - b),
        "readiness_only_ids": sorted(b - r - c),
        "recovery_and_comparative_not_readiness_ids": sorted((r & c) - b),
        "comparative_and_readiness_not_recovery_ids": sorted((c & b) - r),
        "all_three_ids": sorted(r & c & b),
        "recovery_observation_count": len({result_to_observation[x] for x in r}),
        "comparative_result_count": len(c),
        "readiness_observation_count": len({result_to_observation[x] for x in b}),
        "denominator_explanation": (
            "Recovery is the historical v1 Observation gate projected to Results; "
            "comparative completeness is Result-level; readiness is Observation-level "
            "with factor-application precedence."
        ),
        "schema_version": "comparator_unresolved_set_reconciliation_v2",
    }
    payload["identity"] = core_identity("comparator_unresolved_set_reconciliation_v2", payload)
    return payload, rows
