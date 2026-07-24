from __future__ import annotations

from typing import Any

from ..layer_identity import layer_identity

CONFLICT_CANDIDATE_IDENTITY_VERSION = "conflict_candidate_identity_v1"


def conflict_candidate_identity(payload: dict[str, Any]) -> str:
    fields = {
        key: payload[key]
        for key in (
            "candidate_id",
            "canonical_edge_identity",
            "observation_a_id",
            "observation_b_id",
            "claim_a_identity",
            "claim_b_identity",
            "disagreement_signal",
            "candidate_reason",
            "candidate_generation_version",
        )
    }
    return layer_identity(
        "conflict_candidate", CONFLICT_CANDIDATE_IDENTITY_VERSION, fields
    )
