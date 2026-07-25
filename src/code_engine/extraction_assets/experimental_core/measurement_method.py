"""Measurement-method recovery from explicit existing assets only."""
from __future__ import annotations

from typing import Any

from .identities import core_identity

METHOD_FIELDS = {"assay", "measurement_method"}


def recover_method(
    measurement: dict[str, Any], context_fields: list[dict[str, Any]],
    *, experiment_scope_validated: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    links: list[dict[str, Any]] = []
    before = any(measurement.get(key) for key in ("method_raw", "method_extracted", "method_canonical"))
    authority = "direct_measurement_field" if before else "unresolved"
    raw = measurement.get("method_raw")
    extracted = measurement.get("method_extracted")
    canonical = measurement.get("method_canonical")
    context_ref = None
    valid_fields = [
        row for row in context_fields
        if row.get("field_id") in METHOD_FIELDS
        and (row.get("validation_status") or row.get("context_validation_status"))
        in {"validated", "validated_legacy", "valid"}
        and row.get("value_state") == "present"
    ]
    if not before and len(valid_fields) == 1:
        field = valid_fields[0]
        direct = (field.get("observation_identity") or field.get("observation_candidate_identity")) in {
            measurement.get("_source_observation_identity"),
            measurement["observation_revision_identity"],
        }
        authoritative = direct or experiment_scope_validated
        authority = (
            "validated_local_context_reference" if direct
            else "validated_scope_context_reference" if authoritative
            else "candidate_non_authoritative"
        )
        context_ref = field["identity"]
        link = {
            "link_id": "",
            "measurement_identity": measurement["identity"],
            "context_field_evidence_identity": field["identity"],
            "context_field_id": field["field_id"],
            "experiment_scope_identity": measurement.get("_experiment_scope_identity"),
            "link_method": "explicit_context_field_identity",
            "direct_vs_shared": "direct" if direct else "shared",
            "evidence_consistency": "consistent",
            "scope_consistency": "validated" if authoritative else "unvalidated",
            "validation_status": "valid" if authoritative else "candidate_only",
            "authority_status": authority,
            "provenance": measurement["provenance"],
            "schema_version": "measurement_method_context_link_v1",
        }
        link["identity"] = link["link_id"] = core_identity(
            "measurement_method_context_link_v1", link
        )
        links.append(link)
    recovery = {
        "measurement_identity": measurement["identity"],
        "method_present_before": before,
        "method_raw": raw,
        "method_extracted": extracted,
        "method_canonical": canonical,
        "method_context_ref": context_ref,
        "method_evidence_refs": list(measurement.get("evidence_anchor_ids", [])),
        "method_recovery_authority": authority,
        "method_present_after": before or authority.startswith("validated_"),
        "historical_measurement_unchanged": True,
        "provenance": measurement["provenance"],
        "schema_version": "measurement_method_recovery_v1",
    }
    recovery["identity"] = core_identity("measurement_method_recovery_v1", recovery)
    return recovery, links


def missing_reason(recovery: dict[str, Any]) -> dict[str, Any]:
    reason = (
        "method_present" if recovery["method_present_after"]
        else "context_link_missing" if recovery["method_recovery_authority"] == "candidate_non_authoritative"
        else "legacy_lineage_incomplete"
    )
    payload = {
        "measurement_identity": recovery["measurement_identity"],
        "missing_reason": reason,
        "source_scope_completely_audited": False,
        "source_not_reported_authorized": False,
        "evidence_refs": recovery["method_evidence_refs"],
        "provenance": recovery["provenance"],
        "schema_version": "measurement_method_missing_reason_v1",
    }
    payload["identity"] = core_identity("measurement_method_missing_reason_v1", payload)
    return payload
