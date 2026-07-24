from __future__ import annotations

from typing import Any

from ...layer_identity import layer_identity


def factor_divergence_explanation_identity(payload: dict[str, Any]) -> str:
    return layer_identity(
        "factor_divergence_explanation",
        "factor_divergence_explanation_identity_v1",
        {
            key: payload[key]
            for key in (
                "context_difference_identity",
                "context_difference_binding_identity",
                "contradiction_signal_identity",
                "factor_id",
                "assessment_status",
                "explanatory_effect",
                "explanation_policy_identity",
                "adjudication_identity",
                "validator_version",
            )
        },
    )
