"""Stage-count tracing helpers."""
from __future__ import annotations

from typing import Any

from ..identities import sha256_json
from .factors import explicit_factor_candidates
from .measurements import explicit_measurement_candidates
from .results import explicit_result_candidates

STAGES = (
    (0, "raw_provider_response"),
    (1, "parsed_extraction_candidate"),
    (2, "schema_valid_l1_observation"),
    (3, "deterministically_validated_observation"),
    (4, "fulltext_v3_observation"),
    (5, "evidence_projection"),
    (6, "extraction_asset_revision"),
    (7, "context_downstream_consumer_view"),
)


def component_counts(payload: dict[str, Any] | None) -> dict[str, int]:
    if not payload:
        return {
            "factor_count": 0, "intervention_count": 0, "measurement_count": 0,
            "observed_result_count": 0, "linkage_count": 0, "evidence_count": 0,
        }
    factors = explicit_factor_candidates(payload)
    evidence = payload.get("evidence_span_ids") or payload.get("authoritative_evidence_spans") or []
    return {
        "factor_count": len(factors),
        "intervention_count": len(payload.get("interventions") or []),
        "measurement_count": len(explicit_measurement_candidates(payload)),
        "observed_result_count": len(explicit_result_candidates(payload)),
        "linkage_count": len(payload.get("linkages") or payload.get("experimental_observation_linkages") or []),
        "evidence_count": len(evidence),
    }


def trace_payload(payload: dict[str, Any] | None) -> tuple[dict[str, int], str | None]:
    return component_counts(payload), sha256_json(payload) if payload else None

