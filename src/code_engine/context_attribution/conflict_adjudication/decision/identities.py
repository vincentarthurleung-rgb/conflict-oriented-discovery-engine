from __future__ import annotations

from typing import Any

from ...layer_identity import layer_identity


def conflict_adjudication_decision_identity(payload: dict[str, Any]) -> str:
    return layer_identity(
        "conflict_adjudication_decision",
        "conflict_adjudication_decision_identity_v1",
        {
            key: payload[key]
            for key in (
                "authority_scope",
                "pair_id",
                "claim_alignment_identity",
                "contradiction_signal_identity",
                "conflict_candidate_identity",
                "context_difference_identity",
                "context_difference_binding_identity",
                "comparability_assessment_bundle_identity",
                "divergence_explanation_bundle_identity",
                "factor_attribution_bundle_identity",
                "formal_gate_policy_identity",
                "adjudication_status",
                "formal_conflict_confirmed",
                "validator_version",
            )
        },
    )
