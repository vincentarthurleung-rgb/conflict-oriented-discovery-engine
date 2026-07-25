from __future__ import annotations

from ...layer_identity import layer_identity


def scientific_pair_identity(payload: dict) -> str:
    return layer_identity(
        "scientific_candidate_pair", "scientific_candidate_pair_identity_v1", payload
    )


def qualification_identity(payload: dict) -> str:
    return layer_identity(
        "conflict_candidate_qualification",
        "conflict_candidate_qualification_identity_v1",
        payload,
    )


def authority_sidecar_identity(payload: dict) -> str:
    return layer_identity(
        "qualified_candidate_authority",
        "qualified_candidate_authority_identity_v1",
        payload,
    )


def difference_binding_identity(payload: dict) -> str:
    return layer_identity(
        "context_difference_qualification_binding",
        "context_difference_qualification_binding_identity_v1",
        payload,
    )

