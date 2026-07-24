from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..conflict_candidate.models import ConflictCandidate
from ..observation_context.models import ObservationContext
from .identities import context_difference_identity
from .models import ContextDifference

LEGACY_PAIR_TO_DIFFERENCE_ADAPTER_VERSION = (
    "context_pair_attribution_v3_to_context_difference_v1_adapter"
)


def adapt_legacy_pair_to_context_difference(
    payload: dict[str, Any],
    *,
    candidate: ConflictCandidate,
    context_a: ObservationContext,
    context_b: ObservationContext,
    factor_registry_identity: str,
    legacy_prompt_identity: str | None,
) -> tuple[ContextDifference, dict[str, Any]]:
    """Project factual fields only; no repair, effect interpretation, or salvage."""
    source = deepcopy(payload)
    if source.get("schema_version") not in {
        "context_pair_attribution_v2",
        "context_pair_attribution_v3",
    }:
        raise ValueError("unsupported_legacy_pair_schema")
    differences = []
    discarded_factors = []
    for factor in source.get("factor_comparisons") or []:
        differences.append(
            {
                "factor_id": factor["factor_id"],
                "status": factor["status"],
                "claim_a_value": factor.get("claim_a_value"),
                "claim_b_value": factor.get("claim_b_value"),
                "claim_a_anchor_ids": list(factor.get("claim_a_anchor_ids") or []),
                "claim_b_anchor_ids": list(factor.get("claim_b_anchor_ids") or []),
                "comparison_rationale": factor["reason"],
                "provenance": {
                    "legacy_pair_id": source.get("pair_id"),
                    "adapter_version": LEGACY_PAIR_TO_DIFFERENCE_ADAPTER_VERSION,
                },
                "difference_confidence_suggestion": None,
                "missing_information_description": None,
            }
        )
        discarded_factors.append(
            {
                "factor_id": factor.get("factor_id"),
                "comparability_effect": deepcopy(
                    factor.get("comparability_effect")
                ),
                "explanatory_strength": deepcopy(
                    factor.get("explanatory_strength")
                ),
            }
        )
    projected = {
        "schema_version": "context_difference_v1",
        "candidate_id": candidate.candidate_id,
        "conflict_candidate_identity": candidate.conflict_candidate_identity,
        "observation_a_id": context_a.observation_id,
        "observation_b_id": context_b.observation_id,
        "claim_a_identity": candidate.claim_a_identity,
        "claim_b_identity": candidate.claim_b_identity,
        "observation_context_a_identity": (
            context_a.observation_context_identity
        ),
        "observation_context_b_identity": (
            context_b.observation_context_identity
        ),
        "factor_registry_identity": factor_registry_identity,
        "prompt_identity": legacy_prompt_identity,
        "factor_differences": differences,
        "provenance": {
            "adapter_version": LEGACY_PAIR_TO_DIFFERENCE_ADAPTER_VERSION,
            "legacy_schema_version": source.get("schema_version"),
            "legacy_pair_validation_status": source.get("validation_status"),
            "projection_is_not_factor_salvage": True,
            "source_payload_modified": False,
            "status_or_value_modified": False,
            "anchor_modified_or_created": False,
        },
        "validator_version": "context_difference_validator_v1",
        "validation_status": "validated",
    }
    projected["context_difference_identity"] = context_difference_identity(projected)
    difference = ContextDifference.model_validate(projected)
    audit = {
        "adapter_version": LEGACY_PAIR_TO_DIFFERENCE_ADAPTER_VERSION,
        "candidate_id": candidate.candidate_id,
        "legacy_non_authoritative_comparability_fields": {
            "comparability": deepcopy(source.get("comparability")),
            "confidence": deepcopy(source.get("confidence")),
            "primary_explanatory_factors": deepcopy(
                source.get("primary_explanatory_factors")
            ),
            "reasoning_summary": deepcopy(source.get("reasoning_summary")),
            "factor_fields": discarded_factors,
        },
        "source_payload_modified": False,
        "status_or_value_modified": False,
        "anchor_modified_or_created": False,
        "new_comparability_created": False,
    }
    return difference, audit
