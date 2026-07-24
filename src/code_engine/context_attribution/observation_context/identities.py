from __future__ import annotations

from typing import Any

from ..layer_identity import layer_identity

OBSERVATION_CONTEXT_IDENTITY_VERSION = "observation_context_identity_v1"


def observation_context_identity(payload: dict[str, Any]) -> str:
    fields = {
        key: payload[key]
        for key in (
            "observation_id",
            "normalized_claim_identity",
            "canonical_subject",
            "canonical_relation",
            "canonical_object",
            "normalized_polarity",
            "evidence_chain_identity",
            "token_catalog_identity",
            "anchor_set_identity",
            "registry_identity",
            "composition_identity",
            "facts",
            "validator_version",
        )
    }
    return layer_identity(
        "observation_context", OBSERVATION_CONTEXT_IDENTITY_VERSION, fields
    )
