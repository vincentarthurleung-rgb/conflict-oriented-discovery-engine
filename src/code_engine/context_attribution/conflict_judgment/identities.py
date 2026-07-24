from __future__ import annotations

from typing import Any

from ..layer_identity import layer_identity

FORMAL_CONFLICT_DECISION_IDENTITY_VERSION = "formal_conflict_decision_identity_v1"


def formal_conflict_decision_identity(payload: dict[str, Any]) -> str:
    fields = {
        key: payload[key]
        for key in (
            "authority_scope",
            "candidate_id",
            "conflict_candidate_identity",
            "context_difference_identity",
            "conflict_comparability_identity",
            "decision_status",
            "formal_conflict_confirmed",
            "formal_gate_policy_identity",
            "scientific_decision_version",
            "validator_version",
        )
    }
    return layer_identity(
        "formal_conflict_decision",
        FORMAL_CONFLICT_DECISION_IDENTITY_VERSION,
        fields,
    )
