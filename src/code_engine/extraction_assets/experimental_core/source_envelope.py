"""Build task-specific, immutable source resolution envelopes."""
from __future__ import annotations

from typing import Any

from .identities import core_identity


def build_resolution_envelope(
    *,
    task_type: str,
    observation: dict[str, Any],
    result: dict[str, Any] | None,
    measurements: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    source_context: dict[str, Any],
    scope_audit: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Return a complete context envelope; never upgrades historical lineage."""
    spans = source_context.get("spans", [])
    primary = source_context.get("primary_result_sentence")
    payload = {
        "envelope_id": "",
        "task_type": task_type,
        "observation_identity": observation.get("source_observation_identity", observation.get("identity")),
        "source_document_identity": source_context.get("source_document_identity"),
        "source_block_identity": source_context.get("source_block_identity"),
        "source_section_identity": source_context.get("source_section_identity"),
        "experiment_scope_identity": observation.get("experiment_scope_identity"),
        "result_identity": result.get("identity") if result else None,
        "measurement_identities": sorted(m["identity"] for m in measurements),
        "factor_identities": sorted(f["identity"] for f in factors),
        "context_asset_identities": sorted(filter(None, [
            observation.get("context_asset_identity"),
            *source_context.get("context_asset_identities", []),
        ])),
        "primary_result_sentence": primary,
        "preceding_sentence_refs": sorted(source_context.get("preceding_sentence_refs", [])),
        "following_sentence_refs": sorted(source_context.get("following_sentence_refs", [])),
        "paragraph_text": source_context.get("paragraph_text"),
        "section_heading": source_context.get("section_heading"),
        "methods_text_refs": sorted(source_context.get("methods_text_refs", [])),
        "figure_caption_refs": sorted(source_context.get("figure_caption_refs", [])),
        "table_caption_refs": sorted(source_context.get("table_caption_refs", [])),
        "group_definition_refs": sorted(source_context.get("group_definition_refs", [])),
        "evidence_chain_refs": sorted(filter(None, [
            observation.get("evidence_chain_identity"),
            *source_context.get("evidence_chain_refs", []),
        ])),
        "context_field_evidence_refs": sorted(source_context.get("context_field_evidence_refs", [])),
        "source_text_authority": source_context.get("source_text_authority", "unavailable"),
        "source_scope_completeness": scope_audit["completeness"],
        "source_scope_policy_identity": scope_audit["identity"],
        "historical_provider_input_authority": source_context.get(
            "historical_provider_input_authority", "unavailable"
        ),
        "truncation_status": "detected" if scope_audit.get("truncation_detected") else (
            "not_detected" if spans or primary else "unknown"
        ),
        "ambiguity_status": source_context.get("ambiguity_status", "unknown"),
        "provenance": provenance,
    }
    identity_payload = {k: v for k, v in payload.items() if k not in {"envelope_id", "provenance"}}
    identity = core_identity("source_grounded_resolution_envelope_v1", identity_payload)
    payload["envelope_id"] = identity
    payload["identity"] = identity
    payload["schema_version"] = "source_grounded_experimental_resolution_envelope_v1"
    return payload
