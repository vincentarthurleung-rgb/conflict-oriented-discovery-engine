from __future__ import annotations

from typing import Any

from ...layer_identity import layer_identity


def factor_comparability_identity(payload: dict[str, Any]) -> str:
    return layer_identity(
        "factor_comparability",
        "factor_comparability_identity_v1",
        {
            key: payload[key]
            for key in (
                "context_difference_identity",
                "context_difference_binding_identity",
                "factor_id",
                "factor_registry_identity",
                "assessment_status",
                "effect_assessment_status",
                "comparability_severity",
                "comparability_policy_identity",
                "adjudication_identity",
                "validator_version",
            )
        },
    )
