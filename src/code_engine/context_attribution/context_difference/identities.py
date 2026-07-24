from __future__ import annotations

from typing import Any

from ..layer_identity import layer_identity

CONTEXT_DIFFERENCE_IDENTITY_VERSION = "context_difference_identity_v1"


def context_difference_identity(payload: dict[str, Any]) -> str:
    fields = {
        key: payload[key]
        for key in (
            "candidate_id",
            "conflict_candidate_identity",
            "observation_a_id",
            "observation_b_id",
            "claim_a_identity",
            "claim_b_identity",
            "observation_context_a_identity",
            "observation_context_b_identity",
            "factor_registry_identity",
            "prompt_identity",
            "factor_differences",
            "validator_version",
        )
    }
    return layer_identity(
        "context_difference", CONTEXT_DIFFERENCE_IDENTITY_VERSION, fields
    )
