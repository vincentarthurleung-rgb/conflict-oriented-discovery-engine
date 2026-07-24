from __future__ import annotations

from typing import Any

from ..layer_identity import layer_identity

CLAIM_ALIGNMENT_IDENTITY_VERSION = "claim_alignment_identity_v1"


def claim_alignment_identity(payload: dict[str, Any]) -> str:
    return layer_identity(
        "claim_alignment",
        CLAIM_ALIGNMENT_IDENTITY_VERSION,
        {
            key: payload[key]
            for key in (
                "member_claim_identities",
                "l2_normalization_identities",
                "canonical_proposition_signature",
                "alignment_status",
                "alignment_dimensions",
                "unresolved_alignment_dimensions",
                "validator_version",
            )
        },
    )
