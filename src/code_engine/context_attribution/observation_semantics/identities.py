from __future__ import annotations

from typing import Any

from ..layer_identity import layer_identity


def proposition_core_identity(payload: dict[str, Any]) -> str:
    allowed = {
        key: payload[key]
        for key in (
            "canonical_subject_identity",
            "canonical_relation_family",
            "canonical_endpoint_identity",
            "outcome_variable_identity",
            "proposition_core_dimensions",
            "unresolved_core_dimensions",
            "normalization_identities",
        )
    }
    return layer_identity("proposition_core", "proposition_core_identity_v2", allowed)


def result_identity(payload: dict[str, Any]) -> str:
    return layer_identity(
        "contradiction_result",
        "contradiction_result_identity_v1",
        {k: payload[k] for k in ("direction", "sign", "polarity", "qualitative_outcome",
                                "quantitative_effect", "result_category", "evidence_anchor_ids")},
    )


def view_identity(name: str, payload: dict[str, Any]) -> str:
    return layer_identity(name, f"{name}_identity_v1", payload)
