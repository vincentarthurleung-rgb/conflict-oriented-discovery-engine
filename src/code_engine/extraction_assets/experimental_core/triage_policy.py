"""Provider-candidate and Gold-candidate planning policies."""
from __future__ import annotations

from typing import Any

from .identities import core_identity


def provider_candidate_audit(
    target_identity: str, *, source_text_exists: bool, envelope_sufficient: bool,
    information_likely_present: bool, deterministic_resolution_failed: bool,
    joint_prompt_suitable: bool, annotation_cost_exceeds_batch_extraction: bool,
    prompt_v2_expressible: bool, provenance: dict[str, Any],
) -> dict[str, Any]:
    gates = (
        source_text_exists, envelope_sufficient, information_likely_present,
        deterministic_resolution_failed, joint_prompt_suitable,
        annotation_cost_exceeds_batch_extraction, prompt_v2_expressible,
    )
    payload = {
        "target_identity": target_identity,
        "source_text_exists": source_text_exists,
        "source_envelope_sufficient": envelope_sufficient,
        "information_likely_present": information_likely_present,
        "deterministic_resolution_failed": deterministic_resolution_failed,
        "joint_prompt_suitable": joint_prompt_suitable,
        "annotation_cost_exceeds_batch_extraction": annotation_cost_exceeds_batch_extraction,
        "prompt_v2_expressible": prompt_v2_expressible,
        "paid_smoke_still_required": True,
        "provider_candidate": all(gates),
        "provider_reextraction_required": False,
        "automatic_execution_authorized": False,
        "provider_call_authorized": False,
        "network_call_authorized": False,
        "budget_authorization_present": False,
        "provenance": provenance,
        "schema_version": "experimental_source_resolution_provider_candidate_policy_v1",
    }
    payload["identity"] = core_identity(
        "experimental_source_resolution_provider_candidate_policy_v1",
        {k: v for k, v in payload.items() if k != "provenance"},
    )
    return payload


def gold_candidate_audit(target: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    status = target["gold_eligibility_status"]
    payload = {
        "annotation_target_identity": target["identity"],
        "eligibility_status": status,
        "double_annotation_required": status == "eligible_for_double_annotation",
        "adjudication_required": True,
        "schema_validation_required": True,
        "evidence_anchor_validation_required": True,
        "human_gold": False,
        "provenance": provenance,
        "schema_version": "experimental_annotation_gold_candidate_policy_v1",
    }
    payload["identity"] = core_identity(
        "experimental_annotation_gold_candidate_policy_v1",
        {k: v for k, v in payload.items() if k != "provenance"},
    )
    return payload
