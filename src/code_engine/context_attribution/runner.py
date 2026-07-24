from __future__ import annotations

import json
import hashlib
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.extraction.client_factory import (
    build_l1_client_from_env_or_config, resolve_l1_provider_settings,
)
from code_engine.extraction.deepseek_client import DeepSeekExtractionError, _safe_provider_error_body

from .engine import (
    COMPARABILITY_POLICY_VERSION, PROMPT_VERSION, build_abstract_input,
    build_fulltext_input, extraction_cache_identity, extraction_prompt,
    pair_cache_identity, pair_prompt,
)
from .composition import (
    composition_identity, load_composition_policy, validate_registry_policy_consistency,
)
from .identities import (
    IDENTITY_BUNDLE_VERSION, resolve_policy_identities, validate_policy_identity,
)
from .gate import apply_comparability_gate
from .models import ContextExtraction, EXTRACTION_SCHEMA_VERSION, PAIR_SCHEMA_VERSION
from .planning import (
    complete_selection, observation_id, observation_input_mode,
    representative_smoke_selection, validate_plan,
)
from .readiness import calculate_scientific_status, scientific_readiness
from .registry import RegistryResolution, load_registry, resolve_registry
from .validation import validate_context_extraction, validate_pair_attribution
from .validation import (
    HYDRATOR_VERSION, LOCAL_CHAIN_INFERENCE_POLICY_VERSION, VALIDATOR_VERSION,
)
from .token_spans import (
    ANCHOR_TOKENIZER_VERSION, EXPLICIT_SPAN_VERSION, SPAN_HYDRATOR_VERSION,
    selected_token_catalog_identity, validate_selected_token_catalog_identity,
)

ARTIFACTS = (
    "observation_context_extractions.jsonl", "context_pair_attributions.jsonl",
    "context_attribution_validation_audit.jsonl", "context_attribution_execution_ledger.jsonl",
    "context_attribution_summary.json", "context_attribution_completeness_report.json",
    "context_attribution_provider_calls.jsonl",
)

def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists(): return []
    if path.suffix == ".jsonl":
        return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list): return value
    for key in ("observations", "experimental_observations", "items"):
        if isinstance(value.get(key), list): return value[key]
    return []

def discover_observations(run: Path) -> list[dict[str, Any]]:
    artifacts = run / "artifacts"
    names = (
        "fulltext_experiment_observations.jsonl", "fulltext_l1_formal_observations_v3.jsonl",
        "fulltext_formal_observations_v3.jsonl", "l2_fulltext_observations.jsonl",
        "l2_fulltext_graph_observations.jsonl",
        "l2_graph_observations.jsonl", "core_observations.jsonl",
        "l2_retained_observations.jsonl", "l2_normalized_observations.jsonl",
    )
    combined: dict[str, dict[str, Any]] = {}
    for name in names:
        for index, row in enumerate(_rows(artifacts / name)):
            oid = str(row.get("observation_id") or row.get("claim_id") or f"{name}:{index}")
            combined[oid] = {**combined.get(oid, {}), **row}
    return list(combined.values())

def discover_existing_candidate_pairs(run: Path, observations: list[dict[str, Any]],
                                      allowlist: set[str] | None = None) -> list[dict[str, Any]]:
    """Resolve only pairs already emitted by deterministic conflict screening."""
    artifacts = run / "artifacts"
    by_id = {str(x.get("observation_id") or x.get("claim_id")): x for x in observations}
    records = []
    for name in ("graph_conflict_candidates.jsonl", "abstract_conflict_candidates.jsonl",
                 "weak_conflict_candidates.jsonl"):
        records.extend((name, x) for x in _rows(artifacts / name))
    pairs, seen = [], set()
    for source, record in records:
        candidate_id = str(record.get("candidate_id") or record.get("bundle_id") or "")
        if not candidate_id or (allowlist is not None and candidate_id not in allowlist): continue
        if record.get("eligible_for_weak_conflict") is False or record.get("comparability_label") in {"not_comparable", "non_comparable"}:
            continue
        left_ids = list(record.get("supporting_observation_ids") or record.get("positive_observation_ids") or [])
        right_ids = list(record.get("opposing_or_contextual_observation_ids") or record.get("negative_observation_ids") or [])
        if not left_ids or not right_ids:
            members = list(record.get("observation_ids") or record.get("supporting_evidence_ids") or [])
            positive = [x for x in members if str((by_id.get(str(x)) or {}).get("polarity") or
                                                 (by_id.get(str(x)) or {}).get("direction")).casefold() in {"positive", "increase", "activate"}]
            negative = [x for x in members if str((by_id.get(str(x)) or {}).get("polarity") or
                                                 (by_id.get(str(x)) or {}).get("direction")).casefold() in {"negative", "decrease", "inhibit"}]
            left_ids, right_ids = positive, negative
        for left_id in left_ids:
            for right_id in right_ids:
                left, right = by_id.get(str(left_id)), by_id.get(str(right_id))
                key = (candidate_id, str(left_id), str(right_id))
                if left and right and key not in seen:
                    seen.add(key)
                    pid = candidate_id if len(left_ids) == len(right_ids) == 1 else f"{candidate_id}:{left_id}:{right_id}"
                    pairs.append({"pair_id": pid, "claim_a": left, "claim_b": right,
                                  "source_candidate_id": candidate_id, "source_artifact": source,
                                  "candidate_record": record,
                                  "candidate_policy_version": record.get("candidate_policy_version") or
                                  "existing_deterministic_candidate_artifact_v1"})
    return pairs

def discover_invalid_candidates(run: Path, observations: list[dict[str, Any]],
                                allowlist: set[str] | None = None) -> list[dict[str, Any]]:
    artifacts = run / "artifacts"
    by_id = {observation_id(x) for x in observations}
    invalid = []
    for name in ("graph_conflict_candidates.jsonl", "abstract_conflict_candidates.jsonl",
                 "weak_conflict_candidates.jsonl"):
        for index, record in enumerate(_rows(artifacts / name)):
            candidate_id = str(record.get("candidate_id") or record.get("bundle_id") or f"{name}:{index}")
            if allowlist is not None and candidate_id not in allowlist: continue
            left = list(record.get("supporting_observation_ids") or record.get("positive_observation_ids") or [])
            right = list(record.get("opposing_or_contextual_observation_ids") or record.get("negative_observation_ids") or [])
            members = list(record.get("observation_ids") or record.get("supporting_evidence_ids") or [])
            explicitly_invalid = (record.get("eligible_for_weak_conflict") is False
                                  or record.get("comparability_label") in {"not_comparable", "non_comparable"})
            referenced = [*left, *right] if left and right else members
            unresolved = len(referenced) < 2 or not set(map(str, referenced)) <= by_id
            if explicitly_invalid or unresolved:
                invalid.append({"pair_id": candidate_id, "reason": "invalid_candidate",
                                "source_artifact": name})
    return invalid

def _read_index(path: Path) -> dict[str, Any]:
    if not path.exists(): return {"schema_version": "context_attribution_cache_v2", "entries": {}}
    return json.loads(path.read_text(encoding="utf-8"))

def _write_json(path: Path, value: Any) -> None:
    _atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2))

def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write_text(path, "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))

def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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

def _load_fixture(path: Path | None) -> dict[str, Any]:
    return {} if path is None else json.loads(path.read_text(encoding="utf-8"))

def _valid_cache_entry(cache: dict[str, Any], identity: str, kind: str) -> bool:
    entry = (cache.get("entries") or {}).get(identity)
    payload = entry.get("payload") if isinstance(entry, dict) else None
    return bool(isinstance(entry, dict) and entry.get("kind") == kind
                and isinstance(payload, dict) and payload.get("validation_status") == "validated")

def _ledger_id(call_type: str, record_id: str, identity: str) -> str:
    digest = hashlib.sha256(f"{call_type}\x1f{record_id}\x1f{identity}".encode()).hexdigest()[:20]
    return f"ctx-ledger-{digest}"


def _validation_audit_id(record_type: str, record_id: str, identity: str) -> str:
    digest = hashlib.sha256(
        f"validation\x1f{record_type}\x1f{record_id}\x1f{identity}".encode()
    ).hexdigest()[:20]
    return f"ctx-validation-{digest}"


def _retry_queue_v2_rows(
    audits: list[dict[str, Any]], ledger: list[dict[str, Any]],
    provider_audits: list[dict[str, Any]], source_run: Path,
) -> list[dict[str, Any]]:
    ledger_by_id = {
        row.get("record_id"): row for row in ledger if row.get("call_type") == "extraction"
    }
    provider_by_id = {
        row.get("record_id"): row for row in provider_audits
        if row.get("call_type") == "extraction"
    }
    output = []
    for audit in audits:
        if audit.get("record_type") != "extraction" or audit.get("valid"):
            continue
        oid = audit["record_id"]
        entry, provider = ledger_by_id.get(oid, {}), provider_by_id.get(oid, {})
        status = str(entry.get("status") or "")
        diagnostic = entry.get("provider_diagnostic") or {}
        complete = not _provider_artifact_integrity_errors(provider)
        if status == "rejected_validation" and complete:
            layer, action, automatic = "deterministic_validation", "offline_revalidate", False
        elif status == "rejected_schema" and complete:
            layer, action, automatic = (
                "schema", "provider_regeneration_explicit_opt_in", False
            )
        elif status.startswith("failed_provider") and diagnostic.get("error_kind") == "output_truncated":
            layer, action, automatic = "provider", "provider_regeneration_required", True
        else:
            layer, action, automatic = "execution_internal", "blocked_manual_review", False
        attempt_count = int(entry.get("attempt_count") or 0)
        output.append({
            "retry_record_schema_version": "context_attribution_retry_queue_v2",
            "record_type": "extraction",
            "record_id": oid,
            "observation_id": oid,
            "source_run": str(source_run),
            "source_status": status,
            "failure_layer": layer,
            "failure_code": (audit.get("errors") or ["unknown_failure"])[0],
            "errors": audit.get("errors") or [],
            "provider_artifact_complete": complete,
            "identity_complete": len(str(entry.get("identity") or "")) == 64,
            "recovery_action": action,
            "automatic_provider_recall_allowed": automatic,
            "provider_regeneration_requires_explicit_opt_in":
                action == "provider_regeneration_explicit_opt_in",
            "offline_revalidation_possible": action == "offline_revalidate",
            "new_provider_call_required": action in {
                "provider_regeneration_required", "provider_regeneration_explicit_opt_in",
            },
            "new_provider_call_required_reason": (
                "complete_payload_unavailable" if action == "provider_regeneration_required"
                else "explicit_provider_regeneration_opt_in_required"
                if action == "provider_regeneration_explicit_opt_in" else None
            ),
            "source_provider_call_id": entry.get("ledger_entry_id"),
            "source_request_identity": entry.get("identity"),
            "attempt_count": attempt_count,
            "max_attempts": attempt_count + 1 if automatic else attempt_count,
            "next_attempt_allowed": automatic,
            "blocked_reason": None if automatic else (
                "offline_revalidation_only" if action == "offline_revalidate"
                else "explicit_provider_regeneration_opt_in_required"
                if action == "provider_regeneration_explicit_opt_in"
                else "manual_review_required"
            ),
        })
    return output


def _ensure_validation_audit_ids(
    audits: list[dict[str, Any]],
    extraction_identities: dict[str, str],
    comparison_identities: dict[str, str],
) -> None:
    for row in audits:
        identities = (
            extraction_identities if row.get("record_type") == "extraction"
            else comparison_identities
        )
        identity = identities.get(str(row.get("record_id") or ""))
        if identity:
            row.setdefault(
                "validation_audit_id",
                _validation_audit_id(
                    str(row.get("record_type")), str(row.get("record_id")), identity
                ),
            )

def _upsert_ledger(ledger: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    index = next((i for i, row in enumerate(ledger)
                  if row.get("ledger_entry_id") == entry.get("ledger_entry_id")), None)
    if index is None:
        ledger.append({
            **entry,
            "state_history": [entry["status"]] if entry.get("status") else [],
        })
    else:
        previous = ledger[index]
        history = list(previous.get("state_history") or
                       ([previous["status"]] if previous.get("status") else []))
        if entry.get("status") and (not history or history[-1] != entry["status"]):
            history.append(entry["status"])
        ledger[index] = {**previous, **entry, "state_history": history}

def _ensure_ledger(ledger: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    if not any(row.get("ledger_entry_id") == entry.get("ledger_entry_id") for row in ledger):
        _upsert_ledger(ledger, entry)

def _upsert_provider_audit(rows: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    key = (entry.get("call_type"), entry.get("request_identity"))
    index = next((i for i, row in enumerate(rows)
                  if (row.get("call_type"), row.get("request_identity")) == key), None)
    if index is None:
        rows.append(entry)
    else:
        rows[index] = {**rows[index], **entry}

def _safe_audit_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if any(token in str(key).casefold().replace("-", "_")
                                     for token in ("authorization", "api_key", "apikey"))
                  else _safe_audit_value(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe_audit_value(item) for item in value]
    if isinstance(value, str):
        return _safe_provider_error_body(value)
    return value

def _safe_prompt_snapshot(prompt: str) -> str:
    try:
        return json.dumps(_safe_audit_value(json.loads(prompt)), ensure_ascii=False, sort_keys=True)
    except (json.JSONDecodeError, TypeError):
        return _safe_provider_error_body(prompt)

def _successful_provider_audit(rows: list[dict[str, Any]], call_type: str,
                               identity: str) -> dict[str, Any] | None:
    return next((row for row in rows
                 if row.get("call_type") == call_type
                 and row.get("request_identity") == identity
                 and row.get("status") in {
                     "provider_completed", "validated", "rejected_validation", "rejected_schema",
                 }
                 and not _provider_artifact_integrity_errors(row)), None)


def _provider_artifact_integrity_errors(row: dict[str, Any]) -> list[str]:
    errors = []
    if not isinstance(row.get("request_identity"), str): errors.append("request_identity_missing")
    if not isinstance(row.get("parsed_payload"), dict): errors.append("parsed_payload_missing")
    if not isinstance(row.get("raw_response_body"), str) or not row.get("raw_response_body"):
        errors.append("raw_response_missing")
    else:
        try:
            if not isinstance(json.loads(row["raw_response_body"]), dict):
                errors.append("raw_response_not_json_object")
        except json.JSONDecodeError:
            errors.append("raw_response_not_parseable_after_redaction")
    if not isinstance(row.get("prompt_snapshot"), str) or not row.get("prompt_snapshot"):
        errors.append("prompt_snapshot_missing")
    if row.get("http_status") is None: errors.append("http_status_unknown")
    elif not 200 <= int(row["http_status"]) < 300: errors.append("http_not_successful")
    if row.get("credential_values_logged") or row.get("authorization_logged"):
        errors.append("credential_redaction_failed")
    if row.get("identity_bundle_version") != IDENTITY_BUNDLE_VERSION:
        errors.append("identity_bundle_incomplete")
    if not isinstance(row.get("normalization_policy_identity"), dict):
        errors.append("normalization_policy_identity_missing")
    if not isinstance(row.get("comparator_normalization_policy_identity"), dict):
        errors.append("comparator_normalization_policy_identity_missing")
    if row.get("call_type") == "extraction":
        if not isinstance(row.get("observation_token_catalog_identity"), dict):
            errors.append("observation_token_catalog_identity_missing")
        if not isinstance(row.get("observation_anchor_text_identity"), dict):
            errors.append("observation_anchor_text_identity_missing")
    return errors


def _plan_identity_errors(
    plan: dict[str, Any], contracts: dict[str, dict[str, Any]],
    selected_observation_ids: list[str],
) -> list[str]:
    errors: list[str] = []
    for field in (
        "normalization_policy_content_sha256",
        "normalization_policy_identity_sha256",
        "comparator_normalization_policy_content_sha256",
        "comparator_normalization_policy_identity_sha256",
        "selected_token_catalog_identity_sha256",
        "selected_anchor_text_identity_sha256",
    ):
        value = plan.get(field)
        if not isinstance(value, str) or len(value) != 64:
            errors.append(f"plan_identity_missing:{field}")
    if plan.get("comparator_normalization_policy_active") is True and not plan.get(
        "comparator_normalization_policy_content_sha256"
    ):
        errors.append("active_comparator_policy_content_identity_missing")
    if plan.get("token_catalog_identity_version") != (
        "context_attribution_token_catalog_identity_v1"
    ):
        errors.append("token_catalog_identity_version_mismatch")
    errors.extend(validate_selected_token_catalog_identity(
        {
            key: plan.get(key)
            for key in (
                "token_catalog_identity_version",
                "selected_token_catalog_identity_sha256",
                "selected_anchor_text_identity_sha256",
                "selected_observation_token_catalog_identities",
            )
        },
        contracts,
        selected_observation_ids,
    ))
    return errors

def _provider_audit_entry(*, call_type: str, record_id: str, ledger_entry_id: str,
                          identity: str, provider: str, model: str, thinking_mode: str,
                          schema_version: str, prompt_snapshot: str, response: Any,
                          contract_identity: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(getattr(response, "provider_metadata", {}) or {})
    entry = {
        "artifact_schema_version": "context_attribution_provider_call_v2",
        "status": "provider_completed",
        "call_type": call_type,
        "record_id": record_id,
        "observation_id": record_id if call_type == "extraction" else None,
        "pair_id": record_id if call_type == "comparison" else None,
        "ledger_entry_id": ledger_entry_id,
        "provider": provider,
        "model": model,
        "thinking_mode": thinking_mode,
        "prompt_version": PROMPT_VERSION,
        "schema_version": schema_version,
        **contract_identity,
        "request_identity": identity,
        "prompt_snapshot": _safe_prompt_snapshot(prompt_snapshot),
        "raw_response_body": _safe_provider_error_body(getattr(response, "raw_response", None)),
        "parsed_payload": _safe_audit_value(getattr(response, "payload", None)),
        "finish_reason": getattr(response, "finish_reason", None),
        "usage": dict(getattr(response, "usage", {}) or {}),
        "http_status": metadata.get("http_status"),
        "attempt_count": int(getattr(response, "attempt_count", 1) or 1),
        "provider_metadata": _safe_audit_value(metadata),
        "authorization_logged": False,
        "credential_values_logged": False,
        "credential_redaction_status": "redacted_safe",
        "validation_result": None,
    }
    errors = _provider_artifact_integrity_errors(entry)
    entry["provider_artifact_integrity_errors"] = errors
    entry["provider_artifact_complete"] = not errors
    return entry

def _provider_error_audit_entry(*, call_type: str, record_id: str, ledger_entry_id: str,
                                identity: str, provider: str, model: str,
                                thinking_mode: str, schema_version: str,
                                prompt_snapshot: str, exc: Exception,
                                contract_identity: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(getattr(exc, "provider_metadata", {}) or {})
    return {
        "artifact_schema_version": "context_attribution_provider_call_v2",
        "status": "failed_provider",
        "call_type": call_type,
        "record_id": record_id,
        "observation_id": record_id if call_type == "extraction" else None,
        "pair_id": record_id if call_type == "comparison" else None,
        "ledger_entry_id": ledger_entry_id,
        "provider": provider,
        "model": model,
        "thinking_mode": thinking_mode,
        "prompt_version": PROMPT_VERSION,
        "schema_version": schema_version,
        **contract_identity,
        "request_identity": identity,
        "prompt_snapshot": _safe_prompt_snapshot(prompt_snapshot),
        "raw_response_body": _safe_provider_error_body(getattr(exc, "raw_response", None)),
        "parsed_payload": None,
        "finish_reason": getattr(exc, "finish_reason", None),
        "usage": dict(getattr(exc, "usage", {}) or {}),
        "http_status": getattr(exc, "status_code", None),
        "attempt_count": int(getattr(exc, "attempts", 1) or 1),
        "provider_metadata": _safe_audit_value(metadata),
        "authorization_logged": False,
        "credential_values_logged": False,
        "credential_redaction_status": "redacted_safe",
        "validation_result": None,
        "provider_artifact_complete": False,
        "provider_artifact_integrity_errors": ["provider_call_failed"],
    }

def _provider_failure(exc: Exception, *, call_type: str, record_id: str,
                      ledger_entry_id: str, provider: str, model: str,
                      thinking_mode: str, max_tokens: int) -> dict[str, Any]:
    metadata = dict(getattr(exc, "provider_metadata", {}) or {})
    raw = getattr(exc, "raw_response", None)
    return {
        "error_type": getattr(exc, "error_type", type(exc).__name__),
        "error_kind": getattr(exc, "error_kind", "unknown"),
        "status_code": getattr(exc, "status_code", None),
        "provider_error_response_body": _safe_provider_error_body(raw),
        "request_endpoint": metadata.get("request_endpoint") or
                            ("https://api.deepseek.com/v1/chat/completions" if provider == "deepseek" else None),
        "provider": provider, "model": model, "thinking_mode": thinking_mode,
        "max_tokens": max_tokens,
        "response_format_enabled": bool(metadata.get("json_output_enabled", True)),
        "response_format": metadata.get("response_format") or {"type": "json_object"},
        "prompt_version": PROMPT_VERSION,
        "schema_version": EXTRACTION_SCHEMA_VERSION if call_type == "extraction" else PAIR_SCHEMA_VERSION,
        "call_type": call_type, "record_id": record_id, "ledger_entry_id": ledger_entry_id,
        "authorization_logged": False, "credential_values_logged": False,
    }

def run_context_attribution(*, input_run: Path, output_run: Path, mode: str,
                            profiles: list[str], provider: str | None = None, model: str | None = None,
                            execute: bool = False, api: bool = False, cached_only: bool = False,
                            resume: bool = False, extraction_limit: int = 50, comparison_limit: int = 50,
                            allowlist: set[str] | None = None, fixture_responses: Path | None = None,
                            purpose: str = "smoke", smoke_pair_count: int = 5,
                            thinking_mode: str | None = None,
                            registry_version: str | None = None,
                            registry_path: Path | None = None,
                            registry_content_sha256: str | None = None) -> dict[str, Any]:
    if api and not execute: raise ValueError("--api requires --execute")
    if purpose not in {"smoke", "complete"}: raise ValueError("purpose must be smoke or complete")
    if provider == "offline":
        settings = {
            "provider": "offline", "model": model or "offline-fixture",
            "thinking_mode": thinking_mode or "disabled", "max_tokens": 32_768,
            "provider_source": "offline_fixture_override",
            "model_source": "override" if model else "offline_fixture_default",
            "thinking_mode_source": "override" if thinking_mode else "offline_fixture_default",
            "max_tokens_source": "fulltext_l1_default", "credential_values_read": False,
        }
    else:
        settings = resolve_l1_provider_settings(
            provider=provider, model_name=model, thinking_mode=thinking_mode,
        )
    provider, model = settings["provider"], settings["model"]
    thinking_mode, max_tokens = settings["thinking_mode"], int(settings["max_tokens"])
    registry_resolution = resolve_registry(
        requested_registry_version=registry_version,
        prompt_version=PROMPT_VERSION,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
        explicit_path=registry_path,
        expected_content_sha256=registry_content_sha256,
    )
    registry = load_registry(resolution=registry_resolution)
    composition_policy, _ = load_composition_policy()
    composition = composition_identity()
    normalization_policy_identity, comparator_policy_identity = resolve_policy_identities(
        registry=registry,
        registry_path=registry_resolution.registry_path,
        registry_sha256=registry_resolution.registry_content_sha256,
        composition_policy=composition_policy,
        composition_path=composition["composition_policy_path"],
        composition_sha256=composition["composition_policy_content_sha256"],
    )
    configuration_errors = validate_registry_policy_consistency(registry, composition_policy)
    configuration_errors.extend(validate_policy_identity(normalization_policy_identity))
    configuration_errors.extend(validate_policy_identity(comparator_policy_identity))
    registry_identity = registry_resolution.to_dict()
    contract_identity = {
        "identity_bundle_version": IDENTITY_BUNDLE_VERSION,
        **registry_identity,
        "validator_version": VALIDATOR_VERSION,
        "hydrator_version": HYDRATOR_VERSION,
        "anchor_tokenizer_version": ANCHOR_TOKENIZER_VERSION,
        "explicit_span_version": EXPLICIT_SPAN_VERSION,
        "explicit_span_hydrator_version": SPAN_HYDRATOR_VERSION,
        "normalization_policy_version": registry["normalization_registry_version"],
        "local_chain_policy_version": LOCAL_CHAIN_INFERENCE_POLICY_VERSION,
        **composition,
        **normalization_policy_identity.prefixed("normalization_policy"),
        **comparator_policy_identity.prefixed("comparator_normalization_policy"),
        "normalization_policy_identity": normalization_policy_identity.to_dict(),
        "comparator_normalization_policy_identity": comparator_policy_identity.to_dict(),
        "legacy_normalization_version_alias": True,
    }
    output = output_run / "artifacts"; output.mkdir(parents=True, exist_ok=True)
    observations = discover_observations(input_run)
    eligible_observations = []
    for row in observations:
        fulltext = observation_input_mode(row) == "fulltext"
        if mode == "abstract-only" and fulltext: continue
        if mode == "fulltext-only" and not fulltext: continue
        eligible_observations.append(row)
    pairs = discover_existing_candidate_pairs(input_run, eligible_observations, allowlist)
    invalid_candidates = discover_invalid_candidates(input_run, eligible_observations, allowlist)
    selection = (representative_smoke_selection(pairs, smoke_pair_count)
                 if purpose == "smoke" else complete_selection(pairs))
    pair_by_id = {x["pair_id"]: x for x in pairs}
    selected_pairs = [pair_by_id[x] for x in selection["selected_pair_ids"]]
    selected_observation_ids = list(selection["selected_observations"])
    all_candidate_ids = sorted({observation_id(p[side]) for p in pairs for side in ("claim_a", "claim_b")})
    by_id = {observation_id(x): x for x in eligible_observations}
    all_contracts = {
        oid: (build_fulltext_input(by_id[oid], profiles)
              if observation_input_mode(by_id[oid]) == "fulltext" else build_abstract_input(by_id[oid], profiles))
        for oid in all_candidate_ids
    }
    selected_identity = selected_token_catalog_identity(
        all_contracts, selected_observation_ids
    )
    configuration_errors.extend(validate_selected_token_catalog_identity(
        selected_identity, all_contracts, selected_observation_ids
    ))
    contract_identity.update(selected_identity)
    identities = {
        oid: extraction_cache_identity(contract, profiles=profiles, provider=provider, model=model,
                                       thinking_mode=thinking_mode, max_tokens=max_tokens,
                                       registry=registry,
                                       registry_resolution=registry_resolution)
        for oid, contract in all_contracts.items()
    }
    cache_path = output / "context_attribution_cache.json"
    cache = _read_index(cache_path) if resume or cached_only else {"schema_version": "context_attribution_cache_v2", "entries": {}}
    fixtures = _load_fixture(fixture_responses)
    comparison_identities: dict[str, str] = {}
    for pair in pairs:
        a, b = observation_id(pair["claim_a"]), observation_id(pair["claim_b"])
        comparison_identities[pair["pair_id"]] = pair_cache_identity(
            identities[a], identities[b], profiles, pair_id=pair["pair_id"],
            provider=provider, model=model, thinking_mode=thinking_mode,
            registry_resolution=registry_resolution,
        )
    cached_extraction_ids = [oid for oid in selected_observation_ids
                             if _valid_cache_entry(cache, identities[oid], "extraction")]
    extraction_misses = [oid for oid in selected_observation_ids if oid not in cached_extraction_ids]
    planned_extraction_ids = extraction_misses[:extraction_limit]
    covered_extraction_ids = set(cached_extraction_ids) | set(planned_extraction_ids)
    cached_pair_ids = [pid for pid in selection["selected_pair_ids"]
                       if _valid_cache_entry(cache, comparison_identities[pid], "pair")]
    comparison_candidates = [
        pid for pid in selection["selected_pair_ids"]
        if pid not in cached_pair_ids
        and {observation_id(pair_by_id[pid]["claim_a"]), observation_id(pair_by_id[pid]["claim_b"])}
        <= covered_extraction_ids
    ]
    planned_comparison_ids = comparison_candidates[:comparison_limit]
    covered_pair_ids = set(cached_pair_ids) | set(planned_comparison_ids)
    cap_blocked = (len(planned_extraction_ids) < len(extraction_misses)
                   or len(planned_comparison_ids) < len(comparison_candidates))
    complete_covered = (
        purpose == "complete"
        and set(all_candidate_ids) == covered_extraction_ids
        and set(selection["selected_pair_ids"]) == covered_pair_ids
        and not cap_blocked
    )
    coverage_complete = bool(complete_covered)
    plan_status = "blocked_by_call_bound" if cap_blocked else "ready_complete" if coverage_complete else "ready_smoke"
    unprocessed_pairs = [*selection["unselected_pairs"], *invalid_candidates]
    for pid in selection["selected_pair_ids"]:
        if pid in covered_pair_ids: continue
        pair = pair_by_id[pid]
        endpoints = {observation_id(pair["claim_a"]), observation_id(pair["claim_b"])}
        reason = "missing_extraction" if not endpoints <= covered_extraction_ids else "call_bound"
        unprocessed_pairs.append({"pair_id": pid, "reason": reason})
    all_candidate_pair_ids = sorted(pair_by_id)
    unprocessed_observations = []
    for oid in all_candidate_ids:
        if oid in covered_extraction_ids: continue
        reason = "call_bound" if oid in selected_observation_ids else "smoke_not_selected"
        unprocessed_observations.append({"observation_id": oid, "reason": reason})
    selected_observation_rows = [
        {"observation_id": oid, "input_mode": observation_input_mode(by_id[oid]),
         "cache_hit": oid in cached_extraction_ids, "planned_extraction": oid in planned_extraction_ids}
        for oid in selected_observation_ids
    ]
    plan = {
        "schema_version": "context_attribution_execution_plan_v3", "plan_only": not execute,
        "input_run": str(input_run), "output_run": str(output_run), "input_mode": mode,
        "context_attribution_mode": "llm_evidence_grounded", "domain_profiles": profiles,
        "purpose": purpose, "smoke_pair_count": smoke_pair_count,
        "coverage_complete": coverage_complete, "plan_status": plan_status,
        "selection_policy_version": selection["selection_policy_version"],
        "observation_count": len(all_candidate_ids), "candidate_pair_count": len(pairs),
        "selected_pair_count": len(selected_pairs), "selected_observation_count": len(selected_observation_ids),
        "selected_pairs": selection["selected_pairs"], "selected_observation_ids": selected_observation_ids,
        "selected_observations": selected_observation_rows,
        "unprocessed_pairs": unprocessed_pairs, "unprocessed_pair_count": len(unprocessed_pairs),
        "unprocessed_observations": unprocessed_observations,
        "unprocessed_observation_count": len(unprocessed_observations),
        "category_coverage": selection["category_coverage"],
        "all_candidate_pair_ids": all_candidate_pair_ids, "all_candidate_observation_ids": all_candidate_ids,
        "cached_extraction_observation_ids": cached_extraction_ids,
        "planned_extraction_observation_ids": planned_extraction_ids,
        "cached_comparison_pair_ids": cached_pair_ids,
        "planned_comparison_pair_ids": planned_comparison_ids,
        "extraction_cache_hits": len(cached_extraction_ids),
        "extraction_calls_planned": len(planned_extraction_ids),
        "comparison_cache_hits": len(cached_pair_ids),
        "comparison_calls_planned": len(planned_comparison_ids),
        "provider": provider, "model": model, "thinking_mode": thinking_mode,
        "configured_max_tokens": max_tokens,
        "provider_metadata_valid": provider == "offline" or (provider in {"deepseek", "openai"} and bool(model)),
        "provider_configuration_source": {
            "provider": settings["provider_source"], "model": settings["model_source"],
            "thinking_mode": settings["thinking_mode_source"], "max_tokens": settings["max_tokens_source"],
        },
        "credential_values_read": settings["credential_values_read"], "api_enabled": bool(api and execute),
        "network_calls": 0, "provider_calls": 0, "downloads": 0,
        "prompt_version": PROMPT_VERSION, "extraction_schema_version": EXTRACTION_SCHEMA_VERSION,
        "comparison_schema_version": PAIR_SCHEMA_VERSION,
        **registry_identity,
        "profile_version": registry["registry_version"],
        "normalization_registry_version": registry["normalization_registry_version"],
        "normalization_policy_version": registry["normalization_registry_version"],
        "validator_version": VALIDATOR_VERSION, "hydrator_version": HYDRATOR_VERSION,
        "anchor_tokenizer_version": ANCHOR_TOKENIZER_VERSION,
        "explicit_span_version": EXPLICIT_SPAN_VERSION,
        "explicit_span_hydrator_version": SPAN_HYDRATOR_VERSION,
        "local_chain_policy_version": LOCAL_CHAIN_INFERENCE_POLICY_VERSION,
        "local_chain_inference_policy_version": LOCAL_CHAIN_INFERENCE_POLICY_VERSION,
        **composition,
        **normalization_policy_identity.prefixed("normalization_policy"),
        **comparator_policy_identity.prefixed("comparator_normalization_policy"),
        "normalization_policy_identity": normalization_policy_identity.to_dict(),
        "comparator_normalization_policy_identity": comparator_policy_identity.to_dict(),
        "identity_bundle_version": IDENTITY_BUNDLE_VERSION,
        "legacy_normalization_version_alias": True,
        **selected_identity,
        "provider_calls_hard_bound": len(planned_extraction_ids) + len(planned_comparison_ids),
        "activation": False, "active_pointer_unchanged": True,
        "legacy_variational_em_called": False,
    }
    plan_errors = [
        *configuration_errors,
        *_plan_identity_errors(plan, all_contracts, selected_observation_ids),
        *validate_plan(plan),
    ]
    if plan_errors:
        plan["plan_status"] = "invalid"
        plan["coverage_complete"] = False
    plan["plan_validation"] = {"valid": not plan_errors, "errors": plan_errors}
    selection_artifact = {**selection, "purpose": purpose,
                          "selected_observations": selected_observation_rows,
                          "unselected_pairs": unprocessed_pairs}
    _write_json(output / "context_attribution_smoke_selection.json", selection_artifact)
    _write_json(output / "context_attribution_plan.json", plan)
    if not execute:
        _write_json(output / "context_attribution_summary.json", {**plan, "status": "planned", "api_calls": 0})
        _write_json(output / "context_attribution_completeness_report.json",
                    {"status": "plan_only", "purpose": purpose, "candidate_pairs_attributed": 0,
                     "complete": coverage_complete, "plan_status": plan["plan_status"],
                     "reason": "execution_not_requested", "api_calls": 0, "network_calls": 0,
                     "downloads": 0, "activation": False, **contract_identity,
                     "prompt_version": PROMPT_VERSION,
                     "extraction_schema_version": EXTRACTION_SCHEMA_VERSION,
                     "comparison_schema_version": PAIR_SCHEMA_VERSION})
        for name in ARTIFACTS[:4]:
            (output / name).touch(exist_ok=True)
        return plan
    if plan["plan_status"] in {"invalid", "blocked_by_call_bound"}:
        raise RuntimeError(f"context attribution execution blocked: {plan['plan_status']}")
    contracts = {oid: all_contracts[oid] for oid in selected_observation_ids}
    client = build_l1_client_from_env_or_config(provider, model, max_retries=0) if api else None
    if api and client is None: raise RuntimeError("requested_provider_not_configured")
    ledger_path = output / ARTIFACTS[3]
    ledger = _rows(ledger_path) if resume else []
    provider_audit_path = output / ARTIFACTS[-1]
    provider_audits = _rows(provider_audit_path) if resume else []
    audits, extractions, attributions = [], [], []
    calls = {"extraction": 0, "comparison": 0}
    for oid in selected_observation_ids:
        identity = identities[oid]
        _ensure_ledger(ledger, {
            "ledger_entry_id": _ledger_id("extraction", oid, identity),
            "call_type": "extraction", "record_id": oid, "identity": identity,
            "status": "pending", "provider_call": False, "provider": provider, "model": model,
        })
    for pid in selection["selected_pair_ids"]:
        identity = comparison_identities[pid]
        _ensure_ledger(ledger, {
            "ledger_entry_id": _ledger_id("comparison", pid, identity),
            "call_type": "comparison", "record_id": pid, "identity": identity,
            "status": "pending", "provider_call": False, "provider": provider, "model": model,
        })
    _write_jsonl(ledger_path, ledger)
    extraction_by_id: dict[str, ContextExtraction] = {}
    systemic_failure: dict[str, Any] | None = None
    for oid, contract in contracts.items():
        identity = identities[oid]
        raw: dict[str, Any] | None = None
        observation_contract_identity = {
            **contract_identity,
            "token_catalog_identity": contract.get("token_catalog_identity"),
            "observation_token_catalog_identity":
                contract.get("observation_token_catalog_identity"),
            "observation_anchor_text_identity": {
                "observation_id": oid,
                "observation_anchor_text_identity_sha256":
                    (contract.get("observation_token_catalog_identity") or {}).get(
                        "observation_anchor_text_identity_sha256"
                    ),
            },
            "authoritative_anchor_text_sha256": [
                {
                    "anchor_id": anchor.get("anchor_id"),
                    "text_sha256": anchor.get("text_sha256"),
                }
                for anchor in contract.get("evidence_anchors") or []
            ],
        }
        ledger_entry_id = _ledger_id("extraction", oid, identity)
        cached = cache["entries"].get(identity) if _valid_cache_entry(cache, identity, "extraction") else None
        replayed_provider = _successful_provider_audit(provider_audits, "extraction", identity) if resume else None
        source = ("cache" if cached else "fixture" if oid in fixtures.get("extractions", {})
                  else "provider_replay" if replayed_provider else "provider")
        prompt_snapshot = ""
        try:
            if cached:
                raw = cached["payload"]
            elif oid in fixtures.get("extractions", {}):
                raw = fixtures["extractions"][oid]
            elif replayed_provider:
                raw = replayed_provider["parsed_payload"]
            elif cached_only or calls["extraction"] >= extraction_limit or client is None:
                continue
            else:
                prompt_snapshot = extraction_prompt(contract, profiles, registry)
                _upsert_ledger(ledger, {
                    "ledger_entry_id": ledger_entry_id, "status": "in_progress",
                    "source": "provider", "provider_call": True, "attempt_count": 1,
                })
                _write_jsonl(ledger_path, ledger)
                calls["extraction"] += 1
                method = getattr(client, "extract_json_result", None) or getattr(client, "extract_json")
                response = method(
                    prompt_snapshot, model=model, temperature=0, top_p=1,
                    max_tokens=max_tokens, retry_on_length=False, thinking_mode=thinking_mode,
                )
                raw = response.payload if hasattr(response, "payload") else response
                provider_entry = _provider_audit_entry(
                    call_type="extraction", record_id=oid, ledger_entry_id=ledger_entry_id,
                    identity=identity, provider=provider, model=model, thinking_mode=thinking_mode,
                    schema_version=EXTRACTION_SCHEMA_VERSION, prompt_snapshot=prompt_snapshot,
                    response=response, contract_identity=observation_contract_identity,
                )
                _upsert_provider_audit(provider_audits, provider_entry)
                _upsert_ledger(ledger, {
                    "ledger_entry_id": ledger_entry_id, "status": "provider_completed",
                    "source": "provider", "provider_call": True,
                    "attempt_count": provider_entry["attempt_count"],
                })
                _write_jsonl(provider_audit_path, provider_audits)
                _write_jsonl(ledger_path, ledger)
            validated, errors = validate_context_extraction(
                raw, contract, profiles, registry=registry
            )
            validated.extraction_identity = identity
            dumped = validated.model_dump(mode="json")
            if not errors:
                cache["entries"][identity] = {
                    "kind": "extraction", "request_identity": identity,
                    "identity_contract": {
                        **observation_contract_identity,
                        "prompt_version": PROMPT_VERSION,
                        "extraction_schema_version": EXTRACTION_SCHEMA_VERSION,
                        "observation_id": oid,
                    },
                    "payload": dumped,
                }
                extraction_by_id[oid] = validated
                extractions.append(dumped)
            audits.append({
                "record_type": "extraction", "record_id": oid, "valid": not errors,
                "errors": errors,
                "schema_result": {"valid": True, "schema_version": EXTRACTION_SCHEMA_VERSION},
                "provider_parsed_payload": _safe_audit_value(raw),
                "post_hydration_composition_resolver_candidate": _safe_audit_value(dumped),
                "normalization_policy_identity": normalization_policy_identity.to_dict(),
                "comparator_normalization_policy_identity":
                    comparator_policy_identity.to_dict(),
                "observation_token_catalog_identity":
                    contract.get("observation_token_catalog_identity"),
                "observation_anchor_text_identity": {
                    "observation_id": oid,
                    "observation_anchor_text_identity_sha256":
                        (contract.get("observation_token_catalog_identity") or {}).get(
                            "observation_anchor_text_identity_sha256"
                        ),
                },
                "deterministic_validation": validated.provenance.get("deterministic_validation"),
            })
            _upsert_ledger(ledger, {
                "ledger_entry_id": ledger_entry_id, "source": source,
                "status": "rejected_validation" if errors else "validated",
                "validation_status": "rejected" if errors else "validated",
                **({"provider_call_this_execution": False,
                    "resumed_from_complete_provider_artifact": True}
                   if source == "provider_replay" else {"provider_call": source == "provider"}),
            })
            if source in {"provider", "provider_replay"}:
                _upsert_provider_audit(provider_audits, {
                    "call_type": "extraction", "request_identity": identity,
                    "status": "rejected_validation" if errors else "validated",
                    "validation_result": {"valid": not errors, "errors": errors,
                                          "validator_version": VALIDATOR_VERSION,
                                          "hydrator_version": HYDRATOR_VERSION},
                })
        except DeepSeekExtractionError as exc:
            _upsert_provider_audit(provider_audits, _provider_error_audit_entry(
                call_type="extraction", record_id=oid, ledger_entry_id=ledger_entry_id,
                identity=identity, provider=provider, model=model, thinking_mode=thinking_mode,
                schema_version=EXTRACTION_SCHEMA_VERSION, prompt_snapshot=prompt_snapshot, exc=exc,
                contract_identity=observation_contract_identity,
            ))
            diagnostic = _provider_failure(
                exc, call_type="extraction", record_id=oid, ledger_entry_id=ledger_entry_id,
                provider=provider, model=model, thinking_mode=thinking_mode, max_tokens=max_tokens,
            )
            systemic = diagnostic["status_code"] == 400
            status = "failed_systemic_provider_400" if systemic else "failed_provider"
            audits.append({"record_type": "extraction", "record_id": oid, "valid": False,
                           "errors": [status], "provider_diagnostic": diagnostic})
            _upsert_ledger(ledger, {
                "ledger_entry_id": ledger_entry_id, "source": "provider", "provider_call": True,
                "status": status, "attempt_count": int(getattr(exc, "attempts", 1) or 1),
                "provider_diagnostic": diagnostic,
            })
            systemic_failure = diagnostic if systemic else None
        except Exception as exc:
            audits.append({
                "record_type": "extraction", "record_id": oid, "valid": False,
                "errors": [str(exc)],
                "schema_result": {
                    "valid": False, "schema_version": EXTRACTION_SCHEMA_VERSION,
                    "safe_error_type": type(exc).__name__,
                },
                "provider_parsed_payload": _safe_audit_value(raw),
                "normalization_policy_identity": normalization_policy_identity.to_dict(),
                "comparator_normalization_policy_identity":
                    comparator_policy_identity.to_dict(),
                "observation_token_catalog_identity":
                    contract.get("observation_token_catalog_identity"),
                "observation_anchor_text_identity": {
                    "observation_id": oid,
                    "observation_anchor_text_identity_sha256":
                        (contract.get("observation_token_catalog_identity") or {}).get(
                            "observation_anchor_text_identity_sha256"
                        ),
                },
            })
            _upsert_ledger(ledger, {
                "ledger_entry_id": ledger_entry_id, "source": source,
                "provider_call": source == "provider", "status": "rejected_schema",
                "safe_error_type": type(exc).__name__,
            })
            if source in {"provider", "provider_replay"}:
                _upsert_provider_audit(provider_audits, {
                    "call_type": "extraction", "request_identity": identity,
                    "status": "rejected_schema",
                    "validation_result": {"valid": False, "stage": "schema",
                                          "safe_error_type": type(exc).__name__},
                })
        _ensure_validation_audit_ids(audits, identities, comparison_identities)
        _write_jsonl(output / ARTIFACTS[2], audits)
        _write_jsonl(ledger_path, ledger)
        _write_jsonl(provider_audit_path, provider_audits)
        _write_json(cache_path, cache)
        if systemic_failure is not None:
            break
    gates = []
    for pair in selected_pairs:
        pid = pair["pair_id"]; identity = comparison_identities[pid]
        ledger_entry_id = _ledger_id("comparison", pid, identity)
        a, b = str(pair["claim_a"].get("observation_id") or pair["claim_a"].get("claim_id")), str(pair["claim_b"].get("observation_id") or pair["claim_b"].get("claim_id"))
        blocked_observations = [oid for oid in (a, b) if oid not in extraction_by_id]
        if systemic_failure is not None or blocked_observations:
            extraction_statuses = {
                oid: next((row.get("status") for row in ledger
                           if row.get("call_type") == "extraction" and row.get("record_id") == oid),
                          "not_selected")
                for oid in (a, b)
            }
            _upsert_ledger(ledger, {
                "ledger_entry_id": ledger_entry_id,
                "status": "blocked_dependency_validation",
                "provider_call": False,
                "blocked_observation_ids": blocked_observations or [a, b],
                "blocked_by_observation_ids": blocked_observations or [a, b],
                "dependency_extraction_statuses": extraction_statuses,
                "upstream_statuses": extraction_statuses,
                "upstream_validation_audit_ids": [
                    _validation_audit_id("extraction", oid, identities[oid])
                    for oid in (a, b)
                ],
                "blocked_reason": "one_or_more_extractions_not_deterministically_validated",
                "resume_semantics": "reopen_when_all_dependency_extractions_are_validated",
            })
            continue
        cached = cache["entries"].get(identity) if _valid_cache_entry(cache, identity, "pair") else None
        replayed_provider = _successful_provider_audit(provider_audits, "comparison", identity) if resume else None
        source = ("cache" if cached else "fixture" if pid in fixtures.get("pairs", {})
                  else "provider_replay" if replayed_provider else "provider")
        prompt_snapshot = ""
        try:
            if cached:
                raw = cached["payload"]
            elif pid in fixtures.get("pairs", {}):
                raw = fixtures["pairs"][pid]
            elif replayed_provider:
                raw = replayed_provider["parsed_payload"]
            elif cached_only or calls["comparison"] >= comparison_limit or client is None:
                continue
            else:
                payload = {"pair_id": pid, "claim_a_extraction": extraction_by_id[a].model_dump(mode="json"),
                           "claim_b_extraction": extraction_by_id[b].model_dump(mode="json"),
                           "claim_a_evidence": contracts[a], "claim_b_evidence": contracts[b]}
                prompt_snapshot = pair_prompt(payload, profiles, registry)
                _upsert_ledger(ledger, {
                    "ledger_entry_id": ledger_entry_id, "status": "in_progress",
                    "source": "provider", "provider_call": True, "attempt_count": 1,
                })
                _write_jsonl(ledger_path, ledger)
                calls["comparison"] += 1
                method = getattr(client, "extract_json_result", None) or getattr(client, "extract_json")
                response = method(
                    prompt_snapshot, model=model, temperature=0, top_p=1,
                    max_tokens=max_tokens, retry_on_length=False, thinking_mode=thinking_mode,
                )
                raw = response.payload if hasattr(response, "payload") else response
                provider_entry = _provider_audit_entry(
                    call_type="comparison", record_id=pid, ledger_entry_id=ledger_entry_id,
                    identity=identity, provider=provider, model=model, thinking_mode=thinking_mode,
                    schema_version=PAIR_SCHEMA_VERSION, prompt_snapshot=prompt_snapshot,
                    response=response, contract_identity=contract_identity,
                )
                _upsert_provider_audit(provider_audits, provider_entry)
                _upsert_ledger(ledger, {
                    "ledger_entry_id": ledger_entry_id, "status": "provider_completed",
                    "source": "provider", "provider_call": True,
                    "attempt_count": provider_entry["attempt_count"],
                })
                _write_jsonl(provider_audit_path, provider_audits)
                _write_jsonl(ledger_path, ledger)
            validated, errors = validate_pair_attribution(raw, pair_id=pid, extraction_a=extraction_by_id[a],
                                                          extraction_b=extraction_by_id[b], profiles=profiles,
                                                          registry=registry)
            validated.comparison_identity = identity
            dumped = validated.model_dump(mode="json")
            if not errors:
                cache["entries"][identity] = {
                    "kind": "pair", "request_identity": identity,
                    "identity_contract": {
                        **contract_identity,
                        "prompt_version": PROMPT_VERSION,
                        "comparison_schema_version": PAIR_SCHEMA_VERSION,
                        "comparability_policy_version": COMPARABILITY_POLICY_VERSION,
                        "pair_id": pid,
                        "validated_extraction_identities": [identities[a], identities[b]],
                        "claim_a_validated_extraction_identity": identities[a],
                        "claim_b_validated_extraction_identity": identities[b],
                    },
                    "payload": dumped,
                }
                attributions.append(dumped)
                existing = all(bool((x.get("eligibility") or {}).get("conflict_eligible", x.get("conflict_eligible", False)))
                               for x in (pair["claim_a"], pair["claim_b"]))
                gates.append(apply_comparability_gate(
                    validated, profiles, existing_formal_eligibility=existing,
                    registry=registry,
                ))
            audits.append({"record_type": "pair", "record_id": pid, "valid": not errors, "errors": errors})
            _upsert_ledger(ledger, {
                "ledger_entry_id": ledger_entry_id, "source": source,
                "status": "rejected_validation" if errors else "completed",
                "validation_status": "rejected" if errors else "validated",
                **({"provider_call_this_execution": False,
                    "resumed_from_complete_provider_artifact": True}
                   if source == "provider_replay" else {"provider_call": source == "provider"}),
            })
            if source in {"provider", "provider_replay"}:
                _upsert_provider_audit(provider_audits, {
                    "call_type": "comparison", "request_identity": identity,
                    "status": "rejected_validation" if errors else "validated",
                    "validation_result": {"valid": not errors, "errors": errors,
                                          "validator_version": VALIDATOR_VERSION},
                })
        except DeepSeekExtractionError as exc:
            _upsert_provider_audit(provider_audits, _provider_error_audit_entry(
                call_type="comparison", record_id=pid, ledger_entry_id=ledger_entry_id,
                identity=identity, provider=provider, model=model, thinking_mode=thinking_mode,
                schema_version=PAIR_SCHEMA_VERSION, prompt_snapshot=prompt_snapshot, exc=exc,
                contract_identity=contract_identity,
            ))
            diagnostic = _provider_failure(
                exc, call_type="comparison", record_id=pid, ledger_entry_id=ledger_entry_id,
                provider=provider, model=model, thinking_mode=thinking_mode, max_tokens=max_tokens,
            )
            systemic = diagnostic["status_code"] == 400
            status = "failed_systemic_provider_400" if systemic else "failed_provider"
            audits.append({"record_type": "pair", "record_id": pid, "valid": False,
                           "errors": [status], "provider_diagnostic": diagnostic})
            _upsert_ledger(ledger, {
                "ledger_entry_id": ledger_entry_id, "source": "provider", "provider_call": True,
                "status": status, "attempt_count": int(getattr(exc, "attempts", 1) or 1),
                "provider_diagnostic": diagnostic,
            })
            systemic_failure = diagnostic if systemic else None
        except Exception as exc:
            audits.append({"record_type": "pair", "record_id": pid, "valid": False, "errors": [str(exc)]})
            _upsert_ledger(ledger, {
                "ledger_entry_id": ledger_entry_id, "source": source,
                "provider_call": source == "provider", "status": "rejected_schema",
                "safe_error_type": type(exc).__name__,
            })
            if source in {"provider", "provider_replay"}:
                _upsert_provider_audit(provider_audits, {
                    "call_type": "comparison", "request_identity": identity,
                    "status": "rejected_schema",
                    "validation_result": {"valid": False, "stage": "schema",
                                          "safe_error_type": type(exc).__name__},
                })
        _ensure_validation_audit_ids(audits, identities, comparison_identities)
        _write_jsonl(output / ARTIFACTS[2], audits)
        _write_jsonl(ledger_path, ledger)
        _write_jsonl(provider_audit_path, provider_audits)
        _write_json(cache_path, cache)
        if systemic_failure is not None:
            break
    cache["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(cache_path, cache)
    _write_jsonl(output / ARTIFACTS[0], extractions); _write_jsonl(output / ARTIFACTS[1], attributions)
    _ensure_validation_audit_ids(audits, identities, comparison_identities)
    _write_jsonl(output / ARTIFACTS[2], audits); _write_jsonl(output / ARTIFACTS[3], ledger)
    _write_jsonl(provider_audit_path, provider_audits)
    _write_jsonl(output / "context_comparability_gate.jsonl", gates)
    gate_by_pair = {x["pair_id"]: x for x in gates}
    retry_queue = _retry_queue_v2_rows(audits, ledger, provider_audits, output_run)
    _write_jsonl(output / "context_attribution_retry_queue.jsonl", retry_queue)
    distribution = Counter(x.get("comparability") for x in attributions)
    execution_status = "failed_systemic_provider_error" if systemic_failure is not None else "completed"
    validated_extraction_count = len(extraction_by_id)
    rejected_extraction_count = sum(
        row["record_type"] == "extraction" and not row["valid"] for row in audits
    )
    current_extraction_ledger = [
        row for row in ledger
        if row.get("call_type") == "extraction"
        and row.get("record_id") in selected_observation_ids
    ]
    provider_failed_observation_count = sum(
        str(row.get("status") or "").startswith("failed_provider")
        or row.get("status") == "failed_systemic_provider_400"
        for row in current_extraction_ledger
    )
    schema_rejected_observation_count = sum(
        row.get("status") == "rejected_schema" for row in current_extraction_ledger
    )
    deterministic_rejected_observation_count = sum(
        row.get("status") == "rejected_validation" for row in current_extraction_ledger
    )
    execution_internal_failure_count = sum(
        row.get("status") in {"failed_internal", "failed_execution"}
        for row in current_extraction_ledger
    )
    nonvalidated_observation_count = (
        len(selected_observation_ids) - validated_extraction_count
    )
    current_pair_ledger_ids = {
        _ledger_id("comparison", pid, comparison_identities[pid])
        for pid in selection["selected_pair_ids"]
    }
    current_pair_ledger = [
        row for row in ledger if row.get("ledger_entry_id") in current_pair_ledger_ids
    ]
    validated_pair_count = len(attributions)
    blocked_pair_count = sum(
        row.get("status") == "blocked_dependency_validation" for row in current_pair_ledger
    )
    pending_pair_count = sum(
        row.get("status") in {"pending", "in_progress", "provider_completed"}
        for row in current_pair_ledger
    )
    scientific_status = calculate_scientific_status(
        purpose=purpose,
        selected_extraction_count=len(selected_observation_ids),
        validated_extraction_count=validated_extraction_count,
        rejected_extraction_count=rejected_extraction_count,
        selected_pair_count=len(selected_pairs),
        validated_pair_count=validated_pair_count,
        blocked_pair_count=blocked_pair_count,
        pending_pair_count=pending_pair_count,
        transport_complete=systemic_failure is None,
        planned_coverage_complete=coverage_complete,
    )
    actual_coverage_complete = (
        purpose == "complete" and scientific_status == "validated_complete"
    )
    completeness_status = (
        "complete" if actual_coverage_complete
        else "smoke_partial" if scientific_status == "validated_partial"
        else "incomplete"
    )
    summary = {**plan, "status": execution_status, "execution_status": execution_status,
               "scientific_status": scientific_status, "validation_status": scientific_status,
               "legacy_transport_status": execution_status,
               "legacy_status_semantics": "transport_execution_status_only",
               "coverage_complete": actual_coverage_complete,
               "completeness_status": completeness_status,
               "plan_only": False, "extraction_count": len(extractions),
               "pair_attribution_count": len(attributions), "comparability_distribution": dict(distribution),
               "validation_failure_count": sum(not x["valid"] for x in audits),
               "validation_failure_count_semantics":
                   "legacy_mixed_provider_schema_deterministic_and_pair_failures",
               "validated_extraction_count": validated_extraction_count,
               "rejected_extraction_count": rejected_extraction_count,
               "legacy_rejected_extraction_count_semantics":
                   "all_nonvalidated_selected_observations",
               "provider_failed_observation_count": provider_failed_observation_count,
               "schema_rejected_observation_count": schema_rejected_observation_count,
               "deterministic_rejected_observation_count":
                   deterministic_rejected_observation_count,
               "execution_internal_failure_count": execution_internal_failure_count,
               "nonvalidated_observation_count": nonvalidated_observation_count,
               "retry_queue_entry_count": len(retry_queue),
               "provider_recall_required_count": sum(
                   row["recovery_action"] == "provider_regeneration_required"
                   for row in retry_queue
               ),
               "provider_regeneration_opt_in_count": sum(
                   row["recovery_action"] == "provider_regeneration_explicit_opt_in"
                   for row in retry_queue
               ),
               "offline_revalidation_candidate_count": sum(
                   row["recovery_action"] == "offline_revalidate"
                   for row in retry_queue
               ),
               "detailed_scientific_status": (
                   "validated_partial_mixed_failure"
                   if validated_extraction_count and rejected_extraction_count
                   else "fully_validated_smoke"
                   if validated_extraction_count == len(selected_observation_ids)
                   else "all_extractions_rejected"
               ),
               "validated_pair_count": validated_pair_count,
               "blocked_pair_count": blocked_pair_count,
               "pending_pair_count": pending_pair_count,
               "provider_completed_call_count": sum(
                   row.get("status") in {"provider_completed", "validated", "rejected_validation", "rejected_schema"}
                   for row in provider_audits
               ),
               "api_calls": sum(calls.values()), "provider_calls": sum(calls.values()),
               "network_calls": sum(calls.values()), "downloads": 0, "activation": False,
               "systemic_provider_failure": systemic_failure,
               "pending_ledger_entry_count": sum(x.get("status") == "pending" for x in ledger),
               "failed_ledger_entry_count": sum(str(x.get("status", "")).startswith("failed") for x in ledger),
               "blocked_dependency_ledger_entry_count": sum(
                   x.get("status") == "blocked_dependency_validation" for x in ledger
               )}
    readiness = scientific_readiness(summary)
    readiness["identity_bundle"] = {
        "identity_bundle_version": IDENTITY_BUNDLE_VERSION,
        "normalization_policy_identity_sha256":
            normalization_policy_identity.identity_sha256,
        "comparator_normalization_policy_identity_sha256":
            comparator_policy_identity.identity_sha256,
        "selected_token_catalog_identity_sha256":
            selected_identity["selected_token_catalog_identity_sha256"],
        "selected_anchor_text_identity_sha256":
            selected_identity["selected_anchor_text_identity_sha256"],
    }
    handoff_rows = [{
        "schema_version": "context_attribution_handoff_v2",
        "pair_id": item["pair_id"],
        "extracted_context": {
            "claim_a_extraction_identity": identities.get(item["claim_a_observation_id"]),
            "claim_b_extraction_identity": identities.get(item["claim_b_observation_id"]),
        },
        "validated_context": True,
        "pair_attribution": item,
        "comparability_status": (gate_by_pair.get(item["pair_id"]) or {}).get("comparability_status"),
        "formal_conflict_eligibility": (gate_by_pair.get(item["pair_id"]) or {}).get("formal_conflict_eligible", False),
        "scientific_status": scientific_status,
        "handoff_provenance": {
            **contract_identity,
            "prompt_version": PROMPT_VERSION,
            "extraction_schema_version": EXTRACTION_SCHEMA_VERSION,
            "comparison_schema_version": PAIR_SCHEMA_VERSION,
            "comparison_identity": item.get("comparison_identity"),
        },
        "natural_language_is_not_canonical_fact": True,
        "atlas_activation_requested": False,
    } for item in attributions if item.get("validation_status") == "validated"]
    _write_jsonl(output / "context_attribution_handoff.jsonl", handoff_rows)
    summary["handoff_created"] = bool(handoff_rows)
    summary["scientific_readiness"] = readiness
    completeness = {"status": "failed_systemic_provider_error" if systemic_failure is not None else
                              "complete" if scientific_status == "validated_complete" else
                              "smoke_partial" if scientific_status == "validated_partial" else "incomplete",
                    "completeness_status": "complete" if actual_coverage_complete else "partial_or_incomplete",
                    "purpose": purpose, "coverage_complete": actual_coverage_complete,
                    "candidate_pairs": len(pairs), "selected_pairs": len(selected_pairs),
                    "candidate_pairs_attributed": len(attributions),
                    "execution_status": execution_status, "scientific_status": scientific_status,
                    "validated_extraction_count": validated_extraction_count,
                    "rejected_extraction_count": rejected_extraction_count,
                    "validated_pair_count": validated_pair_count,
                    "blocked_pair_count": blocked_pair_count,
                    "pending_pair_count": pending_pair_count,
                    "validation_failure_count": summary["validation_failure_count"],
                    **contract_identity,
                    "prompt_version": PROMPT_VERSION,
                    "extraction_schema_version": EXTRACTION_SCHEMA_VERSION,
                    "comparison_schema_version": PAIR_SCHEMA_VERSION,
                    "scientific_readiness": readiness,
                    "validated_extractions": validated_extraction_count,
                    "formal_conflict_eligible_count": sum(x["formal_conflict_eligible"] for x in gates),
                    "reviewable_count": sum(x["gate_status"] == "reviewable" for x in gates),
                    "api_calls": sum(calls.values()), "network_calls": sum(calls.values()),
                    "downloads": 0, "activation": False}
    _write_json(output / ARTIFACTS[4], summary); _write_json(output / ARTIFACTS[5], completeness)
    legacy = {}
    legacy_path = input_run / "artifacts" / "l4_context_mining_summary.json"
    if legacy_path.exists(): legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    _write_json(output / "context_attribution_legacy_comparison.json", {
        "schema_version": "legacy_l4_vs_evidence_grounded_v1",
        "legacy_candidate_pair_count": legacy.get("candidate_pair_count"),
        "new_candidate_pair_count": len(pairs),
        "extracted_factor_coverage": sum(len(x.get("context_factors", [])) for x in extractions),
        "unknown_rate": (sum(f.get("status") == "unknown" for x in extractions for f in x.get("context_factors", []))
                         / max(1, sum(len(x.get("context_factors", [])) for x in extractions))),
        "comparability_distribution": dict(distribution),
        "evidence_binding_success_count": sum(x["valid"] for x in audits if x["record_type"] == "extraction"),
        "invalid_or_hallucinated_factor_count": sum(not x["valid"] for x in audits if x["record_type"] == "extraction"),
        "conflict_candidate_changes": "review_required_no_automatic_promotion",
        "provider_calls": sum(calls.values()),
        "cache_reuse_count": len(cached_extraction_ids) + len(cached_pair_ids),
    })
    return summary

def revalidate_context_attribution_offline(*, input_run: Path, source_run: Path,
                                           output_run: Path, mode: str,
                                           profiles: list[str]) -> dict[str, Any]:
    """Revalidate previously parsed extractions without constructing a provider client."""
    if output_run.resolve() in {input_run.resolve(), source_run.resolve()}:
        raise ValueError("offline revalidation output must be an isolated run")
    if output_run.exists() and any(output_run.iterdir()):
        raise FileExistsError(f"offline revalidation output is not empty: {output_run}")
    output = output_run / "artifacts"
    output.mkdir(parents=True, exist_ok=True)
    source_payload_path = source_run / "artifacts" / "observation_context_extractions.jsonl"
    source_payloads = _rows(source_payload_path)
    source_summary_path = source_run / "artifacts" / "context_attribution_summary.json"
    source_summary = (json.loads(source_summary_path.read_text(encoding="utf-8"))
                      if source_summary_path.exists() else {})
    source_registry_version = (
        source_summary.get("registry_version") or source_summary.get("profile_version")
    )
    source_registry_path = source_summary.get("registry_path")
    source_registry_hash = source_summary.get("registry_content_sha256")
    source_registry_hash_known = bool(source_registry_hash)
    source_provider_audits = _rows(
        source_run / "artifacts" / "context_attribution_provider_calls.jsonl"
    )
    source_payload_locations = {
        str(row.get("observation_id") or ""): f"{source_payload_path}:{row.get('observation_id')}"
        for row in source_payloads
    }
    seen_payload_ids = set(source_payload_locations)
    for provider_row in source_provider_audits:
        parsed = provider_row.get("parsed_payload")
        oid = str(
            provider_row.get("record_id")
            or (parsed or {}).get("observation_id")
            or ""
        )
        if (
            provider_row.get("call_type") == "extraction"
            and oid
            and oid not in seen_payload_ids
            and isinstance(parsed, dict)
        ):
            source_payloads.append(parsed)
            seen_payload_ids.add(oid)
            source_payload_locations[oid] = (
                f"{source_run / 'artifacts' / 'context_attribution_provider_calls.jsonl'}:"
                f"{oid}:parsed_payload"
            )
    registry_resolution = resolve_registry(
        prompt_version=PROMPT_VERSION,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
    )
    registry = load_registry(resolution=registry_resolution)
    new_registry_identity = registry_resolution.to_dict()
    composition_policy, _ = load_composition_policy()
    composition = composition_identity()
    normalization_policy_identity, comparator_policy_identity = resolve_policy_identities(
        registry=registry,
        registry_path=registry_resolution.registry_path,
        registry_sha256=registry_resolution.registry_content_sha256,
        composition_policy=composition_policy,
        composition_path=composition["composition_policy_path"],
        composition_sha256=composition["composition_policy_content_sha256"],
    )
    observations = discover_observations(input_run)
    eligible = {
        observation_id(row): row for row in observations
        if not (mode == "abstract-only" and observation_input_mode(row) == "fulltext")
        and not (mode == "fulltext-only" and observation_input_mode(row) != "fulltext")
    }
    contracts = {
        oid: (build_fulltext_input(row, profiles)
              if observation_input_mode(row) == "fulltext" else build_abstract_input(row, profiles))
        for oid, row in eligible.items()
    }
    revalidation_observation_ids = sorted({
        str(row.get("observation_id") or "") for row in source_payloads
        if str(row.get("observation_id") or "") in contracts
    })
    revalidation_token_identity = selected_token_catalog_identity(
        contracts, revalidation_observation_ids
    )
    source_identity = {
        "normalization_policy_identity":
            source_summary.get("normalization_policy_identity"),
        "comparator_normalization_policy_identity":
            source_summary.get("comparator_normalization_policy_identity"),
        "selected_token_catalog_identity_sha256":
            source_summary.get("selected_token_catalog_identity_sha256"),
        "selected_anchor_text_identity_sha256":
            source_summary.get("selected_anchor_text_identity_sha256"),
    }
    source_identity_known = all(source_identity.values())
    revalidation_identity = {
        "identity_bundle_version": IDENTITY_BUNDLE_VERSION,
        "normalization_policy_identity": normalization_policy_identity.to_dict(),
        "comparator_normalization_policy_identity": comparator_policy_identity.to_dict(),
        **revalidation_token_identity,
    }
    settings = resolve_l1_provider_settings()
    identities = {
        oid: extraction_cache_identity(
            contract, profiles=profiles, provider=settings["provider"], model=settings["model"],
            thinking_mode=settings["thinking_mode"], max_tokens=int(settings["max_tokens"]),
            registry=registry, registry_resolution=registry_resolution,
        )
        for oid, contract in contracts.items()
    }
    validated_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    validated_by_id: dict[str, ContextExtraction] = {}
    original_prompt_version = source_summary.get("prompt_version")
    for raw in source_payloads:
        oid = str(raw.get("observation_id") or "")
        source_payload_location = source_payload_locations.get(
            oid, f"{source_payload_path}:{oid}"
        )
        source_provider_audit = next((
            row for row in source_provider_audits
            if row.get("call_type") == "extraction"
            and str(row.get("record_id") or row.get("observation_id") or "") == oid
        ), None)
        raw_provider_response_available = bool(
            source_provider_audit
            and isinstance(source_provider_audit.get("raw_response_body"), str)
            and source_provider_audit.get("raw_response_body")
        )
        identity = identities.get(oid, hashlib.sha256(f"offline:{oid}".encode()).hexdigest())
        ledger_entry_id = _ledger_id("extraction", oid, identity)
        provenance = {
            **dict(raw.get("provenance") or {}),
            "offline_revalidation": {
                "source_run": str(source_run),
                "source_payload": source_payload_location,
                "original_prompt_version": original_prompt_version,
                "source_contract_version": source_summary.get("extraction_schema_version"),
                "source_validator_version": source_summary.get("validator_version"),
                "source_registry_version": source_registry_version,
                "source_registry_path": source_registry_path,
                "source_registry_content_sha256": source_registry_hash,
                "source_registry_hash_known": source_registry_hash_known,
                "source_identity": source_identity,
                "source_identity_known": source_identity_known,
                "revalidation_identity": revalidation_identity,
                "revalidation_policy_version": VALIDATOR_VERSION,
                "new_validator_version": VALIDATOR_VERSION,
                "new_hydrator_version": HYDRATOR_VERSION,
                **{f"new_{key}": value for key, value in new_registry_identity.items()},
                "raw_provider_response_available": raw_provider_response_available,
                "raw_provider_response_unavailable": not raw_provider_response_available,
                "finish_reason_unavailable": not bool(
                    source_provider_audit and source_provider_audit.get("finish_reason") is not None
                ),
                "usage_unavailable": not bool(
                    source_provider_audit and source_provider_audit.get("usage") is not None
                ),
            },
        }
        candidate = {**raw, "provenance": provenance}
        try:
            if oid not in contracts:
                raise ValueError("observation_contract_unavailable")
            validated, errors = validate_context_extraction(
                candidate, contracts[oid], profiles, registry=registry
            )
            validated.extraction_identity = identity
            dumped = validated.model_dump(mode="json")
            if not errors:
                validated_rows.append(dumped)
                validated_by_id[oid] = validated
            status = "validated" if not errors else "rejected_validation"
            audits.append({
                "record_type": "extraction", "record_id": oid, "valid": not errors,
                "errors": errors, "source": "offline_revalidation",
                "deterministic_validation": validated.provenance.get("deterministic_validation"),
                "source_identity": source_identity,
                "source_identity_known": source_identity_known,
                "revalidation_identity": revalidation_identity,
                "observation_token_catalog_identity":
                    contracts[oid].get("observation_token_catalog_identity"),
            })
        except Exception as exc:
            dumped = candidate
            errors = [str(exc)]
            status = "rejected_schema"
            audits.append({
                "record_type": "extraction", "record_id": oid, "valid": False,
                "errors": errors, "source": "offline_revalidation",
                "safe_error_type": type(exc).__name__,
                "source_identity": source_identity,
                "source_identity_known": source_identity_known,
                "revalidation_identity": revalidation_identity,
            })
        replay_rows.append({
            "artifact_schema_version": "context_attribution_offline_revalidation_payload_v2",
            "record_id": oid,
            "source_run": str(source_run),
            "source_payload": source_payload_location,
            "original_prompt_version": original_prompt_version,
            "source_contract_version": source_summary.get("extraction_schema_version"),
            "source_validator_version": source_summary.get("validator_version"),
            "source_registry_version": source_registry_version,
            "source_registry_path": source_registry_path,
            "source_registry_content_sha256": source_registry_hash,
            "source_registry_hash_known": source_registry_hash_known,
            "source_identity": source_identity,
            "source_identity_known": source_identity_known,
            "revalidation_identity": revalidation_identity,
            "new_prompt_version": PROMPT_VERSION,
            "new_validator_version": VALIDATOR_VERSION,
            "new_hydrator_version": HYDRATOR_VERSION,
            "revalidation_policy_version": VALIDATOR_VERSION,
            **{f"new_{key}": value for key, value in new_registry_identity.items()},
            "raw_provider_response_available": raw_provider_response_available,
            "raw_provider_response_unavailable": not raw_provider_response_available,
            "finish_reason": (
                source_provider_audit.get("finish_reason") if source_provider_audit else None
            ),
            "usage": source_provider_audit.get("usage") if source_provider_audit else None,
            "revalidated_payload": dumped,
            "validation_result": {"valid": not errors, "errors": errors},
        })
        ledger.append({
            "ledger_entry_id": ledger_entry_id,
            "call_type": "extraction", "record_id": oid, "identity": identity,
            "status": status, "source": "offline_revalidation", "provider_call": False,
            "state_history": ["pending", status],
            "source_run": str(source_run),
        })
    pairs = discover_existing_candidate_pairs(input_run, list(eligible.values()))
    comparison_identities: dict[str, str] = {}
    source_selected_ids = set(source_summary.get("planned_comparison_pair_ids") or
                              source_summary.get("selected_pair_ids") or [])
    if source_selected_ids:
        pairs = [pair for pair in pairs if pair["pair_id"] in source_selected_ids]
    for pair in pairs:
        pid = pair["pair_id"]
        a, b = observation_id(pair["claim_a"]), observation_id(pair["claim_b"])
        identity = pair_cache_identity(
            identities[a], identities[b], profiles, pair_id=pid,
            provider=settings["provider"], model=settings["model"],
            thinking_mode=settings["thinking_mode"],
            registry_resolution=registry_resolution,
        )
        comparison_identities[pid] = identity
        blocked = [oid for oid in (a, b) if oid not in validated_by_id]
        ledger.append({
            "ledger_entry_id": _ledger_id("comparison", pid, identity),
            "call_type": "comparison", "record_id": pid, "identity": identity,
            "status": "blocked_dependency_validation" if blocked else "pending",
            "state_history": (["pending", "blocked_dependency_validation"] if blocked else ["pending"]),
            "provider_call": False,
            "blocked_observation_ids": blocked,
            "blocked_by_observation_ids": blocked,
            "upstream_statuses": {
                oid: ("validated" if oid in validated_by_id else "rejected_or_unavailable")
                for oid in (a, b)
            },
            "upstream_validation_audit_ids": [
                _validation_audit_id("extraction", oid, identities[oid])
                for oid in (a, b)
            ],
            "blocked_reason": (
                "one_or_more_extractions_not_deterministically_validated"
                if blocked else None
            ),
            "resume_semantics": "reopen_when_all_dependency_extractions_are_validated",
            "offline_revalidation_does_not_create_pair_payload": True,
        })
    rejected_count = sum(not row["valid"] for row in audits)
    blocked_pair_count = sum(
        row["status"] == "blocked_dependency_validation" for row in ledger
        if row.get("call_type") == "comparison"
    )
    pending_pair_count = sum(
        row["status"] == "pending" for row in ledger
        if row.get("call_type") == "comparison"
    )
    source_purpose = source_summary.get("purpose") or "smoke"
    scientific_status = calculate_scientific_status(
        purpose=source_purpose,
        selected_extraction_count=len(source_payloads),
        validated_extraction_count=len(validated_rows),
        rejected_extraction_count=rejected_count,
        selected_pair_count=len(pairs),
        validated_pair_count=0,
        blocked_pair_count=blocked_pair_count,
        pending_pair_count=pending_pair_count,
        transport_complete=True,
        planned_coverage_complete=False,
    )
    summary = {
        "schema_version": "context_attribution_offline_revalidation_summary_v1",
        "execution_status": "completed",
        "status": "completed",
        "legacy_status_semantics": "transport_execution_status_only",
        "scientific_status": scientific_status,
        "validation_status": scientific_status,
        "offline_revalidation": True,
        "source_run": str(source_run),
        "source_payload": str(source_payload_path),
        "input_run": str(input_run),
        "output_run": str(output_run),
        "input_mode": mode,
        "domain_profiles": profiles,
        "original_prompt_version": original_prompt_version,
        "source_contract_version": source_summary.get("extraction_schema_version"),
        "source_validator_version": source_summary.get("validator_version"),
        "source_registry_version": source_registry_version,
        "source_registry_path": source_registry_path,
        "source_registry_content_sha256": source_registry_hash,
        "source_registry_hash_known": source_registry_hash_known,
        "source_identity": source_identity,
        "source_identity_known": source_identity_known,
        "source_identity_incomplete": not source_identity_known,
        "revalidation_identity": revalidation_identity,
        "new_prompt_version": PROMPT_VERSION,
        "new_validator_version": VALIDATOR_VERSION,
        "new_hydrator_version": HYDRATOR_VERSION,
        "revalidation_policy_version": VALIDATOR_VERSION,
        **new_registry_identity,
        "prompt_version": PROMPT_VERSION,
        "extraction_schema_version": EXTRACTION_SCHEMA_VERSION,
        "comparison_schema_version": PAIR_SCHEMA_VERSION,
        "validator_version": VALIDATOR_VERSION,
        "hydrator_version": HYDRATOR_VERSION,
        "normalization_policy_version": registry["normalization_registry_version"],
        "local_chain_policy_version": LOCAL_CHAIN_INFERENCE_POLICY_VERSION,
        **composition,
        **normalization_policy_identity.prefixed("normalization_policy"),
        **comparator_policy_identity.prefixed("comparator_normalization_policy"),
        "identity_bundle_version": IDENTITY_BUNDLE_VERSION,
        **revalidation_token_identity,
        **{f"new_{key}": value for key, value in new_registry_identity.items()},
        "raw_provider_response_available": any(
            row.get("raw_provider_response_available") for row in replay_rows
        ),
        "raw_provider_response_unavailable": not any(
            row.get("raw_provider_response_available") for row in replay_rows
        ),
        "finish_reason_unavailable": not any(
            row.get("finish_reason") is not None for row in replay_rows
        ),
        "usage_unavailable": not any(
            row.get("usage") is not None for row in replay_rows
        ),
        "source_parsed_extraction_count": len(source_payloads),
        "validated_extraction_count": len(validated_rows),
        "rejected_extraction_count": rejected_count,
        "validation_failure_count": rejected_count,
        "coverage_complete": False,
        "completeness_status": "incomplete",
        "pair_attribution_count": 0,
        "validated_pair_count": 0,
        "blocked_pair_count": blocked_pair_count,
        "pending_pair_count": pending_pair_count,
        "blocked_dependency_ledger_entry_count": sum(
            row["status"] == "blocked_dependency_validation" for row in ledger
        ),
        "api_calls": 0, "provider_calls": 0, "network_calls": 0, "downloads": 0,
        "cache_hits": 0, "handoff_created": False,
        "activation": False, "active_pointer_unchanged": True,
        "legacy_variational_em_called": False,
    }
    _write_jsonl(output / ARTIFACTS[0], validated_rows)
    _write_jsonl(output / ARTIFACTS[1], [])
    _ensure_validation_audit_ids(audits, identities, comparison_identities)
    _write_jsonl(output / ARTIFACTS[2], audits)
    _write_jsonl(output / ARTIFACTS[3], ledger)
    _write_json(output / ARTIFACTS[4], summary)
    _write_json(output / ARTIFACTS[5], {
        "status": "offline_revalidation",
        "completeness_status": "incomplete",
        "scientific_status": scientific_status,
        "complete": False,
        "reason": "offline_revalidation_never_creates_handoff",
        **new_registry_identity,
        "prompt_version": PROMPT_VERSION,
        "extraction_schema_version": EXTRACTION_SCHEMA_VERSION,
        "comparison_schema_version": PAIR_SCHEMA_VERSION,
        "validator_version": VALIDATOR_VERSION,
        "hydrator_version": HYDRATOR_VERSION,
        "normalization_policy_version": registry["normalization_registry_version"],
        "local_chain_policy_version": LOCAL_CHAIN_INFERENCE_POLICY_VERSION,
        **composition,
        **normalization_policy_identity.prefixed("normalization_policy"),
        **comparator_policy_identity.prefixed("comparator_normalization_policy"),
        "identity_bundle_version": IDENTITY_BUNDLE_VERSION,
        **revalidation_token_identity,
        "api_calls": 0, "network_calls": 0, "downloads": 0, "activation": False,
    })
    _write_jsonl(output / "context_attribution_offline_revalidation_payloads.jsonl", replay_rows)
    _write_jsonl(output / ARTIFACTS[-1], [])
    _write_jsonl(output / "context_attribution_handoff.jsonl", [])
    _write_jsonl(output / "context_pair_attributions.jsonl", [])
    return summary
