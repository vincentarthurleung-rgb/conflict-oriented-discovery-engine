from __future__ import annotations

from typing import Any

from ..layer_identity import layer_identity

CONFLICT_COMPARABILITY_IDENTITY_VERSION = "conflict_comparability_identity_v1"


def conflict_comparability_identity(payload: dict[str, Any]) -> str:
    fields = {
        key: payload[key]
        for key in (
            "candidate_id",
            "conflict_candidate_identity",
            "context_difference_identity",
            "source_difference_validation_status",
            "comparability_policy_identity",
            "adjudication_identity",
            "assessment_status",
            "comparability_class",
            "validator_version",
        )
    }
    return layer_identity(
        "conflict_comparability",
        CONFLICT_COMPARABILITY_IDENTITY_VERSION,
        fields,
    )
