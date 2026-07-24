from __future__ import annotations

from copy import deepcopy
from typing import Any

from .identities import observation_context_identity
from .models import ObservationContext

LEGACY_EXTRACTION_ADAPTER_VERSION = (
    "observation_context_extraction_v5_v6_v7_to_observation_context_v1_adapter"
)


def adapt_legacy_context_extraction(
    payload: dict[str, Any],
    *,
    claim: dict[str, str],
    evidence_chain_identity: str,
    token_catalog_identity: str,
    anchor_set_identity: str,
    registry_identity: str,
    composition_identity: str,
) -> tuple[ObservationContext, dict[str, Any]]:
    """Read-only, whole-artifact projection; never repairs a failed extraction."""
    source = deepcopy(payload)
    if source.get("validation_status") != "validated":
        raise ValueError("legacy_observation_context_not_validated")
    facts = []
    for factor in source.get("context_factors", []):
        facts.append(
            {
                "factor_id": factor["factor_id"],
                "status": factor["status"],
                "raw_value": factor.get("raw_value"),
                "normalized_value": factor.get("normalized_value"),
                "evidence_anchor_ids": list(factor.get("evidence_anchor_ids") or []),
                "token_span": deepcopy(factor.get("explicit_span")),
                "source_chain_node_ids": list(
                    factor.get("source_chain_node_ids") or []
                ),
                "raw_components": deepcopy(factor.get("raw_components") or []),
                "inference_rule": factor.get("inference_rule"),
                "composition_rule": factor.get("composition_rule"),
                "composition_provenance": deepcopy(
                    factor.get("composition_provenance") or []
                ),
                "normalization_provenance": deepcopy(
                    factor.get("normalization_provenance") or {}
                ),
                "confidence": factor["confidence"],
            }
        )
    projected = {
        "schema_version": "observation_context_v1",
        "observation_id": source["observation_id"],
        **claim,
        "evidence_chain_identity": evidence_chain_identity,
        "token_catalog_identity": token_catalog_identity,
        "anchor_set_identity": anchor_set_identity,
        "registry_identity": registry_identity,
        "composition_identity": composition_identity,
        "facts": facts,
        "provenance": {
            "adapter_version": LEGACY_EXTRACTION_ADAPTER_VERSION,
            "legacy_schema_version": source.get("schema_version"),
            "legacy_extraction_identity": source.get("extraction_identity"),
            "source_payload_modified": False,
            "span_or_component_synthesized": False,
            "value_synthesized": False,
        },
        "validator_version": "observation_context_validator_v1",
        "validation_status": "validated",
    }
    projected["observation_context_identity"] = observation_context_identity(projected)
    context = ObservationContext.model_validate(projected)
    return context, {
        "adapter_version": LEGACY_EXTRACTION_ADAPTER_VERSION,
        "observation_id": context.observation_id,
        "source_payload_modified": False,
        "span_or_component_synthesized": False,
        "value_synthesized": False,
    }
