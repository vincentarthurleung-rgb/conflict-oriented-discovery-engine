from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from pydantic import ValidationError

from .composition import composition_identity
from .engine import build_abstract_input, build_fulltext_input
from .identities import (
    PROVIDER_EXECUTION_IDENTITY_VERSION, ProviderExecutionIdentity,
    resolve_provider_execution_identity,
)
from .models import (
    ContextExtraction, PAIR_SCHEMA_VERSION,
    ProviderContextExtractionV6,
)
from .planning import observation_id, observation_input_mode
from .registry import load_registry
from .runner import discover_observations
from .validation import validate_context_extraction_v5

RECOVERY_CLASSIFICATION_VERSION = "context_attribution_recovery_classification_v1"
RECOVERY_PLAN_VERSION = "context_attribution_recovery_plan_v2"
LEGACY_RECOVERY_PLAN_VERSION = "context_attribution_recovery_plan_v1"
EXECUTION_PLAN_VERSION = "context_attribution_execution_plan_v4"
PROMPT_VERSION_V6 = "context_attribution_prompts_v6"
EXTRACTION_SCHEMA_VERSION_V6 = "observation_context_extraction_v6"
VALIDATOR_VERSION_V5 = "context_attribution_validator_v5"
FACTOR_ANCHOR_DERIVER_VERSION = "context_attribution_factor_anchor_deriver_v1"
OFFLINE_ADAPTER_VERSION = "context_attribution_v5_to_v6_redundant_anchor_adapter_v1"
RETRY_QUEUE_VERSION = "context_attribution_retry_queue_v2"
CACHE_VERSION_V3 = "context_attribution_cache_v3"
PROVIDER_CALL_VERSION_V3 = "context_attribution_provider_call_v3"
RECOVERY_EXECUTION_VERSION = "context_attribution_targeted_recovery_execution_v1"

RECOVERY_ACTIONS = {
    "reuse_validated_cache",
    "offline_revalidate",
    "provider_regeneration_required",
    "provider_regeneration_explicit_opt_in",
    "blocked_identity_incomplete",
    "blocked_manual_review",
    "no_action",
}

VALIDATED_IDS = {
    "ftl1v3_5f3214a32e567d0b2d9b6e89",
    "ftl1v3_7ac0b7ee4873b288530caf95",
    "ftl1v3_8a6dafe08d3c36201f191e09",
    "ftl1v3_e105a9b7b3c5372b46877ff0",
}
OFFLINE_IDS = {"ftl1v3_71023211dcfb3d430a918e17"}
SCHEMA_REJECTED_IDS = {"ftl1v3_f530298f2b2955bfe9988710"}
TRUNCATED_IDS = {
    "ftl1v3_17b7314297cabac677007b35",
    "ftl1v3_41f0090d726e6e8591a58574",
}


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write(path: Path, value: Any, *, jsonl: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in value)
        if jsonl
        else json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _sha(value: Any) -> str:
    encoded = (
        value.encode("utf-8") if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    )
    return hashlib.sha256(encoded).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_artifact_hashes(source_run: Path) -> dict[str, str]:
    artifacts = source_run / "artifacts"
    required = (
        "context_attribution_plan.json",
        "context_attribution_cache.json",
        "context_attribution_execution_ledger.jsonl",
        "context_attribution_provider_calls.jsonl",
        "context_attribution_validation_audit.jsonl",
    )
    return {name: _file_sha(artifacts / name) for name in required}


def provider_execution_identity_errors(
    value: dict[str, Any] | ProviderExecutionIdentity | None,
) -> list[str]:
    if not isinstance(value, (dict, ProviderExecutionIdentity)):
        return ["provider_execution_identity_missing"]
    try:
        identity = (
            value if isinstance(value, ProviderExecutionIdentity)
            else ProviderExecutionIdentity.model_validate(value)
        )
    except (ValidationError, ValueError, TypeError):
        return ["provider_execution_identity_invalid"]
    errors = []
    if not identity.provider:
        errors.append("provider_missing")
    if not identity.model:
        errors.append("model_missing")
    if identity.thinking_mode not in {
        "enabled", "disabled", "provider_default",
    }:
        errors.append("thinking_mode_invalid")
    if identity.configured_max_tokens <= 0:
        errors.append("configured_max_tokens_invalid")
    if not identity.prompt_version:
        errors.append("prompt_version_missing")
    if not identity.extraction_schema_version:
        errors.append("extraction_schema_version_missing")
    if not identity.comparison_schema_version:
        errors.append("comparison_schema_version_missing")
    if not identity.verify():
        errors.append("provider_execution_identity_hash_mismatch")
    return errors


def _source_maps(source_run: Path) -> tuple[dict[str, Any], ...]:
    artifacts = source_run / "artifacts"
    ledger = {
        row["record_id"]: row for row in _rows(artifacts / "context_attribution_execution_ledger.jsonl")
        if row.get("call_type") == "extraction"
    }
    providers = {
        row["record_id"]: row for row in _rows(artifacts / "context_attribution_provider_calls.jsonl")
        if row.get("call_type") == "extraction"
    }
    audits = {
        row["record_id"]: row for row in _rows(artifacts / "context_attribution_validation_audit.jsonl")
        if row.get("record_type") == "extraction"
    }
    cache = _json(artifacts / "context_attribution_cache.json")
    cache_by_oid = {
        entry["payload"]["observation_id"]: entry
        for entry in (cache.get("entries") or {}).values()
        if isinstance(entry, dict) and isinstance(entry.get("payload"), dict)
    }
    return ledger, providers, audits, cache_by_oid


def classify_recovery(source_run: Path) -> list[dict[str, Any]]:
    """Classify every selected observation exactly once from persisted facts."""
    artifacts = source_run / "artifacts"
    summary = _json(artifacts / "context_attribution_summary.json")
    ledger, providers, audits, cache = _source_maps(source_run)
    rows: list[dict[str, Any]] = []
    for oid in summary.get("selected_observation_ids") or []:
        source_ledger = ledger.get(oid, {})
        diagnostic = source_ledger.get("provider_diagnostic") or {}
        provider = providers.get(oid, {})
        audit = audits.get(oid, {})
        cached = cache.get(oid)
        parsed = provider.get("parsed_payload")
        complete = bool(
            provider.get("provider_artifact_complete")
            and isinstance(provider.get("raw_response_body"), str)
            and isinstance(parsed, dict)
        )
        schema_valid = bool(
            complete and (provider.get("validation_result") or {}).get("stage") != "schema"
        )
        deterministic_valid = bool(audit.get("valid"))
        identity = str(source_ledger.get("identity") or provider.get("request_identity") or "")
        identity_complete = len(identity) == 64
        if cached and deterministic_valid:
            classification, action = "validated_cached", "reuse_validated_cache"
            reasons = ["validated_cache_entry_exists"]
        elif complete and schema_valid:
            classification, action = (
                "complete_provider_artifact_schema_valid_deterministic_rejected",
                "offline_revalidate",
            )
            reasons = ["complete_schema_valid_payload", "deterministic_validation_rejected"]
        elif complete:
            classification, action = (
                "complete_provider_artifact_schema_rejected",
                "provider_regeneration_explicit_opt_in",
            )
            reasons = ["complete_payload", "schema_rejected", "automatic_repair_forbidden"]
        elif provider and (
            provider.get("error_kind") == "output_truncated"
            or diagnostic.get("error_kind") == "output_truncated"
        ):
            classification, action = (
                "incomplete_provider_artifact_provider_recall_required",
                "provider_regeneration_required",
            )
            reasons = ["output_truncated", "parsed_payload_absent"]
        elif source_ledger.get("status") in {"failed_internal", "failed_execution"}:
            classification, action = "execution_internal_failure", "blocked_manual_review"
            reasons = ["execution_internal_failure"]
        elif not identity_complete:
            classification, action = "identity_incomplete_nonreusable", "blocked_identity_incomplete"
            reasons = ["source_request_identity_incomplete"]
        else:
            classification, action = "unknown_unclassified", "blocked_manual_review"
            reasons = ["no_safe_recovery_classification"]
        if action not in RECOVERY_ACTIONS:
            raise AssertionError(action)
        raw = provider.get("raw_response_body")
        row = {
            "recovery_classification_version": RECOVERY_CLASSIFICATION_VERSION,
            "observation_id": oid,
            "source_run": str(source_run),
            "classification": classification,
            "source_ledger_status": source_ledger.get("status"),
            "source_provider_status": (
                "complete" if complete else
                provider.get("error_kind") or diagnostic.get("error_kind") or "unavailable"
            ),
            "provider_artifact_exists": bool(provider),
            "provider_artifact_complete": complete,
            "raw_body_complete": complete,
            "parsed_payload_exists": isinstance(parsed, dict),
            "schema_valid": schema_valid,
            "deterministic_valid": deterministic_valid,
            "validated_cache_exists": bool(cached),
            "identity_complete": identity_complete,
            "offline_reparse_possible": complete,
            "offline_schema_revalidation_possible": complete,
            "offline_deterministic_revalidation_possible": complete and schema_valid,
            "provider_recall_required": classification == "incomplete_provider_artifact_provider_recall_required",
            "provider_regeneration_optional": classification == "complete_provider_artifact_schema_rejected",
            "automatic_provider_recall_allowed": classification == "incomplete_provider_artifact_provider_recall_required",
            "recovery_action": action,
            "reason_codes": reasons,
            "source_request_identity": identity or None,
            "source_provider_call_id": source_ledger.get("ledger_entry_id"),
            "source_validation_audit_id": audit.get("validation_audit_id"),
            "raw_response_byte_count": len(raw.encode("utf-8")) if isinstance(raw, str) else 0,
        }
        rows.append(row)
    if len(rows) != len({row["observation_id"] for row in rows}):
        raise ValueError("recovery_classification_not_mutually_exclusive")
    return rows


def adapt_v5_payload_to_v6(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Remove redundant authority only; never search, infer, or synthesize evidence."""
    if payload.get("schema_version") != "observation_context_extraction_v5":
        raise ValueError("adapter_requires_schema_v5")
    before = deepcopy(payload)
    factors: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for index, source in enumerate(payload.get("context_factors") or []):
        status = source.get("status")
        if status == "explicit" and not isinstance(source.get("explicit_span"), dict):
            raise ValueError(f"adapter_missing_explicit_span:{source.get('factor_id')}")
        if status == "inferred_from_local_chain" and not source.get("raw_components"):
            raise ValueError(f"adapter_missing_raw_components:{source.get('factor_id')}")
        allowed = {
            key: deepcopy(source[key])
            for key in (
                "factor_id", "status", "explicit_span", "source_chain_node_ids",
                "inference_rule", "raw_components", "normalized_candidate", "confidence",
            )
            if key in source
        }
        if status == "unknown":
            allowed.update({
                "explicit_span": None, "source_chain_node_ids": [], "inference_rule": None,
                "raw_components": [], "normalized_candidate": None,
            })
        if "evidence_anchor_ids" in source:
            removed.append({
                "factor_index": index,
                "factor_id": source.get("factor_id"),
                "field": "evidence_anchor_ids",
                "value": deepcopy(source["evidence_anchor_ids"]),
            })
        factors.append(allowed)
    adapted = {
        "schema_version": EXTRACTION_SCHEMA_VERSION_V6,
        "observation_id": payload.get("observation_id"),
        "domain_profiles": deepcopy(payload.get("domain_profiles")),
        "input_mode": payload.get("input_mode"),
        "context_factors": factors,
        "missing_critical_information": deepcopy(payload.get("missing_critical_information") or []),
        "warnings": deepcopy(payload.get("warnings") or []),
    }
    ProviderContextExtractionV6.model_validate(adapted)
    audit = {
        "adapter_version": OFFLINE_ADAPTER_VERSION,
        "source_payload_sha256": _sha(before),
        "adapted_provider_payload_sha256": _sha(adapted),
        "removed_redundant_provider_fields": removed,
        "before_after_diff": [
            {"op": "remove", "path": f"/context_factors/{item['factor_index']}/evidence_anchor_ids",
             "value": item["value"]}
            for item in removed
        ] + [{"op": "replace", "path": "/schema_version",
              "from": "observation_context_extraction_v5", "value": EXTRACTION_SCHEMA_VERSION_V6}],
        "new_scientific_information_added": False,
        "text_search_performed": False,
        "span_inference_performed": False,
        "component_synthesis_performed": False,
        "source_payload_modified": payload != before,
    }
    return adapted, audit


def derive_factor_anchors(payload: ProviderContextExtractionV6 | dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    value = (
        payload if isinstance(payload, ProviderContextExtractionV6)
        else ProviderContextExtractionV6.model_validate(payload)
    )
    internal_factors: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for index, factor in enumerate(value.context_factors):
        if factor.status == "explicit":
            anchors = [factor.explicit_span.evidence_anchor_id] if factor.explicit_span else []
            source = "explicit_span"
        elif factor.status == "inferred_from_local_chain":
            anchors = list(dict.fromkeys(
                anchor
                for component in factor.raw_components
                for anchor in component.evidence_anchor_ids
            ))
            source = "ordered_unique_union_of_canonical_components"
        else:
            anchors, source = [], "unknown_empty"
        dumped = factor.model_dump(mode="json")
        dumped["evidence_anchor_ids"] = anchors
        internal_factors.append(dumped)
        provenance.append({
            "factor_index": index, "factor_id": factor.factor_id,
            "derivation_source": source, "derived_evidence_anchor_ids": anchors,
            "component_order_preserved": True,
        })
    internal = {
        "schema_version": "observation_context_extraction_v5",
        "observation_id": value.observation_id,
        "domain_profiles": value.domain_profiles,
        "input_mode": value.input_mode,
        "context_factors": internal_factors,
        "missing_critical_information": value.missing_critical_information,
        "warnings": value.warnings,
        "provenance": {
            "factor_anchor_derivation": {
                "deriver_version": FACTOR_ANCHOR_DERIVER_VERSION,
                "provider_factor_level_anchor_authority": False,
                "factors": provenance,
            }
        },
        "validation_status": "unvalidated",
    }
    return internal, internal["provenance"]["factor_anchor_derivation"]


def _contracts(input_run: Path, profiles: list[str]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in discover_observations(input_run):
        oid = observation_id(row)
        output[oid] = (
            build_fulltext_input(row, profiles)
            if observation_input_mode(row) == "fulltext"
            else build_abstract_input(row, profiles)
        )
    return output


def offline_revalidate_payload(
    *, payload: dict[str, Any], contract: dict[str, Any], profiles: list[str],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    adapted, adapter_audit = adapt_v5_payload_to_v6(payload)
    internal, derivation_audit = derive_factor_anchors(adapted)
    registry = load_registry()
    validated, errors = validate_context_extraction_v5(
        internal, contract, profiles, registry=registry
    )
    dumped = validated.model_dump(mode="json")
    dumped["schema_version"] = EXTRACTION_SCHEMA_VERSION_V6
    dumped["provenance"] = {
        **dumped.get("provenance", {}),
        "source_kind": "offline_adapted_from_v5",
        "offline_adapter": adapter_audit,
        "factor_anchor_derivation": derivation_audit,
        "validator_version": VALIDATOR_VERSION_V5,
    }
    source_identity = _sha({
        "prompt_version": PROMPT_VERSION_V6,
        "schema_version": EXTRACTION_SCHEMA_VERSION_V6,
        "validator_version": VALIDATOR_VERSION_V5,
        "factor_anchor_deriver_version": FACTOR_ANCHOR_DERIVER_VERSION,
        "adapter_version": OFFLINE_ADAPTER_VERSION,
        "source_provider_artifact_hash": adapter_audit["source_payload_sha256"],
        "token_catalog_identity": contract.get("token_catalog_identity"),
        "observation_token_catalog_identity": contract.get("observation_token_catalog_identity"),
        "registry_version": "context_factor_registry_v3",
        "composition_version": "context_local_chain_composition_v3",
        "normalization_version": "context_normalization_policy_v3",
        "comparator_normalization_version": "context_comparator_normalization_v1",
        "provenance": "offline_adapted_from_v5",
    })
    dumped["extraction_identity"] = source_identity
    return (dumped if not errors else None), {
        "valid": not errors,
        "errors": errors,
        "adapter": adapter_audit,
        "factor_anchor_derivation": derivation_audit,
        "full_validation_stages": [
            "schema_v6", "token_span", "component_ownership", "composition",
            "normalization_resolver", "deterministic_validator_v5",
        ],
        "provider_calls": 0, "network_calls": 0,
    }


def retry_queue_v2(classifications: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    layer_by_class = {
        "incomplete_provider_artifact_provider_recall_required": "provider",
        "complete_provider_artifact_schema_valid_deterministic_rejected": "deterministic_validation",
        "complete_provider_artifact_schema_rejected": "schema",
        "execution_internal_failure": "execution_internal",
    }
    for item in classifications:
        if item["classification"] == "validated_cached":
            continue
        action = item["recovery_action"]
        needs_call = action in {
            "provider_regeneration_required", "provider_regeneration_explicit_opt_in",
        }
        automatic = bool(item["automatic_provider_recall_allowed"])
        output.append({
            "retry_record_schema_version": RETRY_QUEUE_VERSION,
            "observation_id": item["observation_id"],
            "source_run": item["source_run"],
            "source_status": item["source_ledger_status"],
            "failure_layer": layer_by_class.get(item["classification"], "unknown"),
            "failure_code": item["reason_codes"][0],
            "provider_artifact_complete": item["provider_artifact_complete"],
            "identity_complete": item["identity_complete"],
            "recovery_action": action,
            "automatic_provider_recall_allowed": automatic,
            "provider_regeneration_requires_explicit_opt_in":
                action == "provider_regeneration_explicit_opt_in",
            "offline_revalidation_possible": item["offline_deterministic_revalidation_possible"],
            "new_provider_call_required": needs_call,
            "new_provider_call_required_reason": (
                "complete_payload_unavailable" if action == "provider_regeneration_required"
                else "schema_rejected_regeneration_only" if needs_call else None
            ),
            "source_provider_call_id": item["source_provider_call_id"],
            "source_request_identity": item["source_request_identity"],
            "attempt_count": 1 if item["provider_artifact_exists"] else 0,
            "max_attempts": 2 if automatic else 1,
            "next_attempt_allowed": automatic,
            "blocked_reason": (
                None if automatic else
                "offline_revalidation_only" if action == "offline_revalidate"
                else "explicit_provider_regeneration_opt_in_required"
                if action == "provider_regeneration_explicit_opt_in"
                else "manual_review_required"
            ),
        })
    return output


def recovery_counts(classifications: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(classifications)
    count = lambda name: sum(row["classification"] == name for row in rows)
    validated = count("validated_cached")
    provider_failed = count("incomplete_provider_artifact_provider_recall_required")
    schema_rejected = count("complete_provider_artifact_schema_rejected")
    deterministic_rejected = count(
        "complete_provider_artifact_schema_valid_deterministic_rejected"
    )
    internal = count("execution_internal_failure")
    nonvalidated = len(rows) - validated
    if provider_failed and (schema_rejected or deterministic_rejected or internal):
        scientific_status = "validated_partial_mixed_failure"
    elif provider_failed:
        scientific_status = "validated_partial_provider_incomplete"
    elif schema_rejected:
        scientific_status = "validated_partial_schema_rejection"
    elif deterministic_rejected:
        scientific_status = "validated_partial_deterministic_rejection"
    elif validated == len(rows):
        scientific_status = "fully_validated_smoke"
    elif validated == 0 and rows:
        scientific_status = "all_extractions_rejected"
    else:
        scientific_status = "validated_partial_mixed_failure"
    return {
        "validated_extraction_count": validated,
        "provider_failed_observation_count": provider_failed,
        "schema_rejected_observation_count": schema_rejected,
        "deterministic_rejected_observation_count": deterministic_rejected,
        "execution_internal_failure_count": internal,
        "nonvalidated_observation_count": nonvalidated,
        "retry_queue_entry_count": len(retry_queue_v2(rows)),
        "provider_recall_required_count": sum(row["provider_recall_required"] for row in rows),
        "provider_regeneration_opt_in_count": sum(
            row["recovery_action"] == "provider_regeneration_explicit_opt_in" for row in rows
        ),
        "offline_revalidation_candidate_count": sum(
            row["recovery_action"] == "offline_revalidate" for row in rows
        ),
        "legacy_rejected_extraction_count": nonvalidated,
        "legacy_rejected_extraction_count_semantics":
            "all_nonvalidated_selected_observations",
        "validation_failure_count": nonvalidated,
        "validation_failure_count_semantics":
            "legacy_mixed_provider_schema_and_deterministic_failures",
        "scientific_status": scientific_status,
    }


def _pair_state(selected_pairs: list[dict[str, Any]], available: set[str]) -> tuple[list[str], list[dict[str, Any]]]:
    ready, blocked = [], []
    for pair in selected_pairs:
        endpoints = {pair["claim_a_id"], pair["claim_b_id"]}
        missing = sorted(endpoints - available)
        if missing:
            blocked.append({"pair_id": pair["pair_id"], "blocked_observation_ids": missing})
        else:
            ready.append(pair["pair_id"])
    return ready, blocked


def build_recovery_plan(
    *, input_run: Path, source_run: Path, target_run: Path,
    mode: str, include_schema_regeneration: bool = False,
    provider: str | None = None, model: str | None = None,
    thinking_mode: str | None = None, configured_max_tokens: int | None = None,
    provider_execution_identity: ProviderExecutionIdentity | None = None,
    fake_test_configuration: bool = False,
) -> dict[str, Any]:
    if mode not in {"offline_only", "targeted_provider"}:
        raise ValueError("invalid_recovery_mode")
    classifications = classify_recovery(source_run)
    by_action: dict[str, list[str]] = {}
    for row in classifications:
        by_action.setdefault(row["recovery_action"], []).append(row["observation_id"])
    source_plan = _json(source_run / "artifacts" / "context_attribution_plan.json")
    runtime_config = _json(
        Path(__file__).parents[3] / "configs/context_attribution/production.json"
    )
    execution_identity = provider_execution_identity or resolve_provider_execution_identity(
        provider=provider, model=model, thinking_mode=thinking_mode,
        configured_max_tokens=configured_max_tokens,
        prompt_version=PROMPT_VERSION_V6,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION_V6,
        comparison_schema_version=PAIR_SCHEMA_VERSION,
        production_config=runtime_config, fake_test=fake_test_configuration,
    )
    selected_pairs = source_plan["selected_pairs"]
    ready_before, blocked_before = _pair_state(selected_pairs, set(by_action.get("reuse_validated_cache", [])))
    offline_ids = by_action.get("offline_revalidate", [])
    recall_ids = by_action.get("provider_regeneration_required", [])
    opt_in_ids = by_action.get("provider_regeneration_explicit_opt_in", [])
    if mode == "offline_only":
        planned_recall: list[str] = []
        offline_candidates = offline_ids
    else:
        planned_recall = list(recall_ids)
        if include_schema_regeneration:
            planned_recall.extend(opt_in_ids)
        offline_candidates = offline_ids
    available_after_offline = set(VALIDATED_IDS) | set(offline_candidates)
    ready_after_offline, _ = _pair_state(selected_pairs, available_after_offline)
    conditional_available = available_after_offline | set(planned_recall)
    ready_after_provider, blocked_after_provider = _pair_state(selected_pairs, conditional_available)
    comparison_calls = 0 if mode == "offline_only" else len(
        [pid for pid in ready_after_provider if pid not in ready_before]
    )
    extraction_calls = len(planned_recall)
    errors: list[str] = []
    if set(planned_recall) & VALIDATED_IDS:
        errors.append("validated_observation_in_provider_allowlist")
    if set(planned_recall) & OFFLINE_IDS:
        errors.append("offline_revalidation_observation_in_provider_allowlist")
    if set(planned_recall) & SCHEMA_REJECTED_IDS and not include_schema_regeneration:
        errors.append("schema_rejected_observation_requires_explicit_opt_in")
    errors.extend(provider_execution_identity_errors(execution_identity))
    expected_bound = extraction_calls + comparison_calls
    plan = {
        "schema_version": RECOVERY_PLAN_VERSION,
        "execution_plan_version": EXECUTION_PLAN_VERSION,
        "source_run": str(source_run),
        "input_run": str(input_run),
        "target_run": str(target_run),
        "recovery_plan_version": RECOVERY_PLAN_VERSION,
        "recovery_mode": mode,
        "plan_only": True,
        "provider": execution_identity.provider,
        "model": execution_identity.model,
        "thinking_mode": execution_identity.thinking_mode,
        "configured_max_tokens": execution_identity.configured_max_tokens,
        "comparison_schema_version": PAIR_SCHEMA_VERSION,
        "provider_configuration_source": execution_identity.configuration_source,
        "provider_execution_identity_version": PROVIDER_EXECUTION_IDENTITY_VERSION,
        "provider_execution_identity_sha256": execution_identity.identity_sha256,
        "provider_execution_identity": execution_identity.model_dump(mode="json"),
        "provider_execution_identity_required": True,
        "provider_execution_identity_verified": execution_identity.verify(),
        "recovery_execution_supported": mode == "targeted_provider",
        "recovery_execution_version": RECOVERY_EXECUTION_VERSION,
        "provider_allowlist_enforced": True,
        "dynamic_pair_execution": True,
        "source_run_immutable": True,
        "resume_checkpoint_enabled": True,
        "per_observation_attempt_bound": 1,
        "extraction_provider_calls_hard_bound": extraction_calls,
        "comparison_provider_calls_hard_bound": comparison_calls,
        "comparison_calls_are_conditional": mode == "targeted_provider",
        "source_artifact_sha256": _source_artifact_hashes(source_run),
        "source_plan_identity_bundle_version": source_plan.get("identity_bundle_version"),
        "source_plan_selected_token_catalog_identity_sha256":
            source_plan.get("selected_token_catalog_identity_sha256"),
        "source_plan_selected_anchor_text_identity_sha256":
            source_plan.get("selected_anchor_text_identity_sha256"),
        "scientific_contract_versions": {
            "prompt": PROMPT_VERSION_V6,
            "extraction_schema": EXTRACTION_SCHEMA_VERSION_V6,
            "validator": VALIDATOR_VERSION_V5,
            "factor_anchor_deriver": FACTOR_ANCHOR_DERIVER_VERSION,
            "offline_adapter": OFFLINE_ADAPTER_VERSION,
            "registry": "context_factor_registry_v3",
            "composition": "context_local_chain_composition_v3",
            "normalization": "context_normalization_policy_v3",
            "comparator_normalization": "context_comparator_normalization_v1",
            "cache": CACHE_VERSION_V3,
            "provider_audit": PROVIDER_CALL_VERSION_V3,
            "retry_queue": RETRY_QUEUE_VERSION,
        },
        "identity_bundle": {
            "identity_bundle_version": "context_attribution_identity_bundle_v2",
            "source_provider_artifact_hash_required": True,
            "source_request_identity_required": True,
            "token_catalog_identity_required": True,
            "anchor_text_identity_required": True,
            "provenance_values": ["fresh_provider_v6", "offline_adapted_from_v5"],
        },
        "selected_observation_count": len(classifications),
        "validated_cache_reuse_observation_ids": sorted(by_action.get("reuse_validated_cache", [])),
        "validated_cache_reuse_count": len(by_action.get("reuse_validated_cache", [])),
        "offline_revalidation_observation_ids": sorted(offline_candidates),
        "offline_revalidation_candidate_count": len(offline_candidates),
        "provider_recall_required_observation_ids": sorted(planned_recall),
        "provider_recall_required_count": len(planned_recall),
        "provider_regeneration_opt_in_observation_ids": sorted(
            opt_in_ids if include_schema_regeneration else []
        ),
        "provider_regeneration_opt_in_count": len(
            opt_in_ids if include_schema_regeneration else []
        ),
        "blocked_observation_ids": sorted(
            set(opt_in_ids) - set(planned_recall)
        ),
        "ready_pair_ids_before_recovery": ready_before,
        "pairs_blocked_before_recovery": blocked_before,
        "expected_ready_pair_ids_after_offline_revalidation": ready_after_offline,
        "expected_ready_pair_ids_after_provider_recovery": ready_after_provider,
        "expected_pair_readiness_is_conditional_on_successful_validation": True,
        "pairs_blocked_after_planned_recovery": blocked_after_provider,
        "extraction_provider_calls_planned": extraction_calls,
        "comparison_provider_calls_planned": comparison_calls,
        "provider_calls_hard_bound": expected_bound,
        "provider_calls": 0,
        "api_calls": 0,
        "network_calls": 0,
        "downloads": 0,
        "credential_values_read": False,
        "provider_client_created": False,
        "provider_call_artifact_created": False,
        "activation": False,
        "active_pointer_unchanged": True,
        "atlas_activated": False,
        "variational_em_called": False,
        "plan_validation": {"valid": not errors, "errors": errors},
    }
    return plan


def create_recovery_run(
    *, input_run: Path, source_run: Path, output_run: Path,
    mode: str, profiles: list[str], include_schema_regeneration: bool = False,
    provider: str | None = None, model: str | None = None,
    thinking_mode: str | None = None, configured_max_tokens: int | None = None,
    provider_execution_identity: ProviderExecutionIdentity | None = None,
    fake_test_configuration: bool = False,
) -> dict[str, Any]:
    """Create a new immutable plan/revalidation run without touching credentials."""
    if output_run.resolve() in {input_run.resolve(), source_run.resolve()}:
        raise ValueError("recovery_output_must_be_new")
    if output_run.exists() and any(output_run.iterdir()):
        raise FileExistsError(f"recovery output is not empty: {output_run}")
    plan = build_recovery_plan(
        input_run=input_run, source_run=source_run, target_run=output_run,
        mode=mode, include_schema_regeneration=include_schema_regeneration,
        provider=provider, model=model, thinking_mode=thinking_mode,
        configured_max_tokens=configured_max_tokens,
        provider_execution_identity=provider_execution_identity,
        fake_test_configuration=fake_test_configuration,
    )
    if not plan["plan_validation"]["valid"]:
        raise ValueError("invalid_recovery_plan")
    output = output_run / "artifacts"
    output.mkdir(parents=True, exist_ok=True)
    classifications = classify_recovery(source_run)
    _atomic_write(output / "context_attribution_recovery_classification.jsonl",
                  classifications, jsonl=True)
    _atomic_write(output / "context_attribution_retry_queue.jsonl",
                  retry_queue_v2(classifications), jsonl=True)
    offline_results: list[dict[str, Any]] = []
    validated_rows: list[dict[str, Any]] = []
    if mode == "offline_only":
        _, providers, _, _ = _source_maps(source_run)
        contracts = _contracts(input_run, profiles)
        for oid in plan["offline_revalidation_observation_ids"]:
            provider = providers.get(oid) or {}
            payload = provider.get("parsed_payload")
            if not isinstance(payload, dict) or oid not in contracts:
                result = {"valid": False, "errors": ["complete_source_payload_or_contract_unavailable"]}
                validated = None
            else:
                try:
                    validated, result = offline_revalidate_payload(
                        payload=payload, contract=contracts[oid], profiles=profiles,
                    )
                except (ValueError, ValidationError) as exc:
                    validated = None
                    result = {"valid": False, "errors": [str(exc)], "provider_calls": 0, "network_calls": 0}
            offline_results.append({"observation_id": oid, **result})
            if validated is not None:
                validated_rows.append(validated)
        _atomic_write(output / "observation_context_extractions.jsonl", validated_rows, jsonl=True)
    plan["offline_revalidation_results"] = offline_results
    plan["offline_revalidation_validated_count"] = len(validated_rows)
    plan["api_calls"] = 0
    _atomic_write(output / "context_attribution_recovery_plan.json", plan)
    initial_counts = recovery_counts(classifications)
    summary = {
        **plan,
        "schema_version": "context_attribution_recovery_summary_v1",
        **initial_counts,
        "validated_extraction_count":
            initial_counts["validated_extraction_count"] + len(validated_rows),
        "deterministic_rejected_observation_count":
            max(0, initial_counts["deterministic_rejected_observation_count"] - len(validated_rows)),
        "nonvalidated_observation_count":
            initial_counts["nonvalidated_observation_count"] - len(validated_rows),
        "scientific_status": "validated_partial_mixed_failure",
    }
    _atomic_write(output / "context_attribution_summary.json", summary)
    return plan


def truncation_audit(source_run: Path) -> list[dict[str, Any]]:
    ledger, providers, _, _ = _source_maps(source_run)
    output = []
    for oid in sorted(TRUNCATED_IDS):
        row = providers[oid]
        diagnostic = (ledger.get(oid) or {}).get("provider_diagnostic") or {}
        raw = row.get("raw_response_body") or ""
        usage = row.get("usage") or {}
        configured = (row.get("provider_metadata") or {}).get("max_tokens") or row.get("max_tokens")
        output.append({
            "observation_id": oid,
            "raw_response_byte_count": len(raw.encode("utf-8")),
            "completion_usage_present": bool(usage),
            "completion_tokens": usage.get("completion_tokens"),
            "finish_reason": row.get("finish_reason"),
            "error_type": row.get("error_type") or diagnostic.get("error_type"),
            "error_kind": row.get("error_kind") or diagnostic.get("error_kind"),
            "configured_max_tokens": configured,
            "recorded_token_limit_reached": (
                isinstance(configured, int)
                and usage.get("completion_tokens") == configured
                and row.get("finish_reason") == "length"
            ),
            "http_status": row.get("http_status"),
            "http_status_evidence": "unknown_not_recorded" if row.get("http_status") is None else "recorded",
            "truncation_location": (
                "context_factors[].normalization_field"
                if oid == "ftl1v3_17b7314297cabac677007b35"
                else "context_factors[].inference_rule_field"
            ),
            "parsed_payload_exists": isinstance(row.get("parsed_payload"), dict),
            "safe_conclusion": "recorded_output_limit_reached",
        })
    return output


__all__ = [
    "CACHE_VERSION_V3", "EXECUTION_PLAN_VERSION", "EXTRACTION_SCHEMA_VERSION_V6",
    "FACTOR_ANCHOR_DERIVER_VERSION", "OFFLINE_ADAPTER_VERSION",
    "PROMPT_VERSION_V6", "PROVIDER_CALL_VERSION_V3", "RECOVERY_EXECUTION_VERSION",
    "LEGACY_RECOVERY_PLAN_VERSION", "RECOVERY_CLASSIFICATION_VERSION",
    "RECOVERY_PLAN_VERSION",
    "RETRY_QUEUE_VERSION", "VALIDATOR_VERSION_V5", "adapt_v5_payload_to_v6",
    "build_recovery_plan", "classify_recovery", "create_recovery_run",
    "derive_factor_anchors", "offline_revalidate_payload", "recovery_counts",
    "provider_execution_identity_errors", "retry_queue_v2",
    "truncation_audit",
]
