"""Exact-phrase Measurement Method source audit without scientific guessing."""
from __future__ import annotations

import re
from typing import Any

from .identities import core_identity
from .source_authority import source_not_reported_allowed

SPECIFIC_METHODS = (
    "western blot", "immunoblot", "qPCR", "RT-qPCR", "real-time PCR",
    "immunohistochemistry", "immunofluorescence", "flow cytometry", "ELISA",
    "RNA sequencing", "RNA-seq", "mass spectrometry", "MTT assay",
    "CCK-8 assay", "colony formation assay", "wound healing assay",
    "transwell assay", "luciferase assay",
)
ASSAY_FAMILIES = (
    "protein assay", "gene expression assay", "imaging assay",
    "viability assay", "migration assay",
)


def exact_method_mentions(texts: list[dict[str, str]]) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for source in texts:
        text = source.get("text", "")
        for granularity, methods in (
            ("specific_method", SPECIFIC_METHODS), ("assay_family", ASSAY_FAMILIES)
        ):
            for method in methods:
                match = re.search(rf"(?<!\w){re.escape(method)}(?!\w)", text, re.I)
                if match:
                    mentions.append({
                        "method_text": match.group(0),
                        "canonical_method": method.lower(),
                        "method_resolution_granularity": granularity,
                        "source_kind": source.get("source_kind", "result"),
                        "source_ref": source.get("source_ref"),
                        "char_start": match.start(), "char_end": match.end(),
                    })
    return mentions


def resolve_measurement_method(
    *,
    measurement: dict[str, Any],
    source_texts: list[dict[str, str]],
    context_method_refs: list[dict[str, Any]],
    scope_audit: dict[str, Any],
    core_reuse_blocked_without_method: bool,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    mentions = exact_method_mentions(source_texts)
    direct = measurement.get("method_raw") or measurement.get("method_extracted")
    validated_context = [
        row for row in context_method_refs
        if row.get("field_id") in {"assay", "measurement_method"}
        and row.get("context_validation_status") == "validated"
        and row.get("experiment_scope_validated", False)
    ]
    resolved_text = None
    granularity = "unresolved"
    source_kind = None
    if direct:
        status, resolved_text, granularity, source_kind = (
            "deterministically_resolved", str(direct), "specific_method", "measurement_field"
        )
    elif mentions:
        specific = [m for m in mentions if m["method_resolution_granularity"] == "specific_method"]
        chosen = (specific or mentions)[0]
        status, resolved_text = "deterministically_resolved", chosen["method_text"]
        granularity, source_kind = chosen["method_resolution_granularity"], chosen["source_kind"]
    elif validated_context:
        row = validated_context[0]
        resolved_text = str(row.get("value_raw") or row.get("value") or "")
        granularity = row.get("method_resolution_granularity", "assay_family")
        status, source_kind = "deterministically_resolved", "validated_scope_context"
    elif not core_reuse_blocked_without_method:
        status = "optional_enrichment"
    elif not source_not_reported_allowed(scope_audit):
        status = "source_scope_insufficient"
    elif scope_audit.get("source_not_reported_authorized"):
        status = "source_not_reported"
    else:
        status = "unresolved"
    payload = {
        "measurement_identity": measurement["identity"],
        "resolution_status": status,
        "resolved_method_text": resolved_text,
        "method_resolution_granularity": granularity,
        "method_source_kind": source_kind,
        "exact_method_mentions": mentions,
        "semantic_level_used_as_method": False,
        "endpoint_used_to_infer_method": False,
        "source_scope_identity": scope_audit["identity"],
        "creates_measurement_revision": status == "deterministically_resolved",
        "historical_measurement_unchanged": True,
        "provider_candidate": False,
        "provider_reextraction_required": False,
        "automatic_execution_authorized": False,
        "provider_call_authorized": False,
        "network_call_authorized": False,
        "budget_authorization_present": False,
        "provenance": provenance,
        "schema_version": "source_grounded_measurement_method_resolution_v2",
    }
    payload["identity"] = core_identity(
        "source_grounded_measurement_method_resolution_v2",
        {k: v for k, v in payload.items() if k != "provenance"},
    )
    return payload
