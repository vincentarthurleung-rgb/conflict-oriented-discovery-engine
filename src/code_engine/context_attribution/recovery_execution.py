from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from .engine import extraction_prompt_v6, pair_prompt
from .identities import ProviderExecutionIdentity
from .models import ContextExtraction, ContextPairAttribution, ProviderContextExtractionV6
from .recovery import (
    CACHE_VERSION_V3, EXTRACTION_SCHEMA_VERSION_V6, OFFLINE_IDS,
    PROMPT_VERSION_V6, PROVIDER_CALL_VERSION_V3, RECOVERY_EXECUTION_VERSION,
    RECOVERY_PLAN_VERSION, RETRY_QUEUE_VERSION, TRUNCATED_IDS, VALIDATED_IDS,
    VALIDATOR_VERSION_V5, _atomic_write, _contracts, _file_sha, _json, _rows,
    _sha, _source_artifact_hashes, _source_maps, derive_factor_anchors,
    offline_revalidate_payload, provider_execution_identity_errors,
)
from .registry import load_registry
from .validation import validate_context_extraction_v5, validate_pair_attribution

EXPECTED_ALLOWLIST = {
    "ftl1v3_17b7314297cabac677007b35",
    "ftl1v3_41f0090d726e6e8591a58574",
}
BLOCKED_DEFAULT = {"ftl1v3_f530298f2b2955bfe9988710"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entry_id(call_type: str, record_id: str, identity: str) -> str:
    return f"ctx-recovery-{call_type}-{_sha([record_id, identity])[:24]}"


def validate_targeted_recovery_execution_plan(
    plan: dict[str, Any], *, input_run: Path, source_run: Path, target_run: Path,
    actual_provider_execution_identity: ProviderExecutionIdentity | None = None,
    test_only: bool = False,
) -> list[str]:
    """Pure, credential-free fail-closed gate. It must run before client creation."""
    errors: list[str] = []
    check = lambda condition, code: errors.append(code) if not condition else None
    check(plan.get("schema_version") == RECOVERY_PLAN_VERSION, "recovery_plan_schema_mismatch")
    check(plan.get("recovery_plan_version") == RECOVERY_PLAN_VERSION, "recovery_plan_version_mismatch")
    identity_value = plan.get("provider_execution_identity")
    errors.extend(provider_execution_identity_errors(identity_value))
    try:
        planned_identity = ProviderExecutionIdentity.model_validate(identity_value)
    except (ValidationError, ValueError, TypeError):
        planned_identity = None
    if planned_identity is not None:
        check(plan.get("provider") == planned_identity.provider, "plan_provider_identity_mismatch")
        check(plan.get("model") == planned_identity.model, "plan_model_identity_mismatch")
        check(plan.get("thinking_mode") == planned_identity.thinking_mode,
              "plan_thinking_mode_identity_mismatch")
        check(plan.get("configured_max_tokens") == planned_identity.configured_max_tokens,
              "plan_max_tokens_identity_mismatch")
        check(plan.get("provider_execution_identity_sha256") ==
              planned_identity.identity_sha256, "plan_provider_identity_hash_mismatch")
        check(plan.get("provider_execution_identity_verified") is True,
              "provider_execution_identity_not_verified")
        check(plan.get("provider_execution_identity_required") is True,
              "provider_execution_identity_not_required")
        versions = plan.get("scientific_contract_versions") or {}
        check(versions.get("prompt") == planned_identity.prompt_version,
              "plan_prompt_identity_mismatch")
        check(versions.get("extraction_schema") ==
              planned_identity.extraction_schema_version,
              "plan_extraction_schema_identity_mismatch")
        check(plan.get("comparison_schema_version", "context_pair_attribution_v2") ==
              planned_identity.comparison_schema_version,
              "plan_comparison_schema_identity_mismatch")
        if actual_provider_execution_identity is not None:
            check(actual_provider_execution_identity.verify(),
                  "actual_provider_execution_identity_invalid")
            check(actual_provider_execution_identity.identity_sha256 ==
                  planned_identity.identity_sha256,
                  "actual_provider_execution_identity_mismatch")
        check(test_only or planned_identity.provider != "fake",
              "fake_provider_identity_for_production_execution")
    check(plan.get("recovery_execution_version") == RECOVERY_EXECUTION_VERSION,
          "recovery_execution_version_mismatch")
    check(plan.get("recovery_execution_supported") is True, "recovery_execution_not_supported")
    check(plan.get("recovery_mode") == "targeted_provider", "recovery_mode_not_targeted")
    check(Path(plan.get("source_run", "")).resolve() == source_run.resolve(), "source_run_mismatch")
    check(Path(plan.get("input_run", "")).resolve() == input_run.resolve(), "input_run_mismatch")
    check(Path(plan.get("target_run", "")).resolve() == target_run.resolve(), "target_run_mismatch")
    check(target_run.resolve() != source_run.resolve(), "target_run_equals_source_run")
    check(target_run.resolve() != input_run.resolve(), "target_run_equals_input_run")
    check((plan.get("plan_validation") or {}).get("valid") is True, "plan_validation_invalid")
    allowlist = set(plan.get("provider_recall_required_observation_ids") or [])
    check(allowlist == EXPECTED_ALLOWLIST, "provider_allowlist_not_exact")
    check(not allowlist & OFFLINE_IDS, "offline_observation_in_provider_allowlist")
    check(not allowlist & BLOCKED_DEFAULT, "f530_in_default_provider_allowlist")
    check(not allowlist & VALIDATED_IDS, "validated_observation_in_provider_allowlist")
    check(plan.get("provider_allowlist_enforced") is True, "provider_allowlist_not_enforced")
    check(int(plan.get("per_observation_attempt_bound", -1)) == 1,
          "per_observation_attempt_bound_mismatch")
    check(int(plan.get("extraction_provider_calls_hard_bound", -1)) == 2,
          "extraction_provider_bound_mismatch")
    comparison_bound = int(plan.get("comparison_provider_calls_hard_bound", -1))
    check(0 <= comparison_bound <= 3, "comparison_provider_bound_mismatch")
    check(int(plan.get("provider_calls_hard_bound", -1)) <= 5, "provider_bound_exceeds_five")
    check(plan.get("dynamic_pair_execution") is True, "dynamic_pair_execution_disabled")
    check(plan.get("source_run_immutable") is True, "source_run_immutable_disabled")
    check(plan.get("resume_checkpoint_enabled") is True, "resume_checkpoint_disabled")
    check(plan.get("activation") is False, "activation_not_false")
    check(plan.get("active_pointer_unchanged") is True, "active_pointer_changed")
    check(plan.get("atlas_activated") is False, "atlas_activated")
    check(plan.get("variational_em_called") is False, "variational_em_called")
    source_plan = _json(source_run / "artifacts/context_attribution_plan.json")
    check(plan.get("source_plan_identity_bundle_version") == source_plan.get("identity_bundle_version"),
          "source_identity_bundle_mismatch")
    check(plan.get("source_plan_selected_token_catalog_identity_sha256") ==
          source_plan.get("selected_token_catalog_identity_sha256"),
          "source_token_catalog_identity_mismatch")
    check(plan.get("source_plan_selected_anchor_text_identity_sha256") ==
          source_plan.get("selected_anchor_text_identity_sha256"),
          "source_anchor_text_identity_mismatch")
    try:
        actual_hashes = _source_artifact_hashes(source_run)
    except (FileNotFoundError, OSError):
        actual_hashes = {}
    check(plan.get("source_artifact_sha256") == actual_hashes, "source_artifact_hash_drift")
    return errors


def _call(client: Any, *, call_type: str, record_id: str, request_identity: str,
          prompt: str, attempt_number: int) -> dict[str, Any]:
    if hasattr(client, "call"):
        result = client.call(
            call_type=call_type, record_id=record_id, request_identity=request_identity,
            prompt=prompt, attempt_number=attempt_number,
        )
    else:
        method = getattr(client, "extract_json_result", None) or client.extract_json
        result = method(
            prompt, temperature=0, top_p=1, max_tokens=32768,
            retry_on_length=False, thinking_mode="provider_default",
        )
    return result.payload if hasattr(result, "payload") else result


def _upsert(rows: list[dict[str, Any]], row: dict[str, Any], keys: tuple[str, ...]) -> None:
    index = next((i for i, old in enumerate(rows)
                  if all(old.get(k) == row.get(k) for k in keys)), None)
    if index is None:
        rows.append(row)
    else:
        old = rows[index]
        history = list(old.get("state_history") or [])
        if old.get("status") != row.get("status"):
            history.append({"status": old.get("status"), "at": _now()})
        rows[index] = {**old, **row, "state_history": history}


def _fresh_validate(payload: dict[str, Any], contract: dict[str, Any],
                    profiles: list[str]) -> tuple[dict[str, Any] | None, list[str], str]:
    try:
        provider_value = ProviderContextExtractionV6.model_validate(payload)
    except ValidationError as exc:
        return None, [str(exc)], "schema"
    internal, derivation = derive_factor_anchors(provider_value)
    validated, errors = validate_context_extraction_v5(
        internal, contract, profiles, registry=load_registry()
    )
    if errors:
        return None, errors, "deterministic_validation"
    result = validated.model_dump(mode="json")
    result["schema_version"] = EXTRACTION_SCHEMA_VERSION_V6
    result["provenance"] = {
        **result.get("provenance", {}), "source_kind": "fresh_provider_v6",
        "factor_anchor_derivation": derivation, "validator_version": VALIDATOR_VERSION_V5,
    }
    return result, [], "validated"


def execute_targeted_recovery(
    *, plan: dict[str, Any], input_run: Path, source_run: Path, target_run: Path,
    profiles: list[str], client_factory: Callable[[], Any], resume: bool = False,
    provider_mode: str = "injected", test_only: bool = False,
    interrupt_after_persist: tuple[str, str] | None = None,
    actual_provider_execution_identity: ProviderExecutionIdentity | None = None,
) -> dict[str, Any]:
    errors = validate_targeted_recovery_execution_plan(
        plan, input_run=input_run, source_run=source_run, target_run=target_run,
        actual_provider_execution_identity=actual_provider_execution_identity,
        test_only=test_only,
    )
    if errors:
        raise RuntimeError("targeted_recovery_execution_blocked:" + ",".join(errors))
    artifacts = target_run / "artifacts"
    if target_run.exists() and not resume and any(target_run.iterdir()):
        raise FileExistsError(f"recovery output is not empty: {target_run}")
    artifacts.mkdir(parents=True, exist_ok=True)
    _atomic_write(artifacts / "context_attribution_recovery_plan.json", plan)
    execution_identity = ProviderExecutionIdentity.model_validate(
        plan["provider_execution_identity"]
    )
    # The factory is intentionally invoked only after every immutable-plan check above.
    client = client_factory()
    contracts = _contracts(input_run, profiles)
    source_ledger, source_providers, _, source_cache = _source_maps(source_run)
    source_plan = _json(source_run / "artifacts/context_attribution_plan.json")
    pairs = source_plan["selected_pairs"]
    cache_path = artifacts / "context_attribution_cache.json"
    ledger_path = artifacts / "context_attribution_execution_ledger.jsonl"
    provider_path = artifacts / "context_attribution_provider_calls.jsonl"
    audit_path = artifacts / "context_attribution_validation_audit.jsonl"
    retry_path = artifacts / "context_attribution_retry_queue.jsonl"
    cache = _json(cache_path) if resume and cache_path.exists() else {
        "schema_version": CACHE_VERSION_V3, "entries": {}
    }
    ledger = _rows(ledger_path) if resume else []
    provider_audits = _rows(provider_path) if resume else []
    audits = _rows(audit_path) if resume else []
    retry = _rows(retry_path) if resume else []
    validated_by_id: dict[str, dict[str, Any]] = {}
    calls = {"extraction": 0, "comparison": 0}

    def persist() -> None:
        cache["updated_at"] = _now()
        _atomic_write(cache_path, cache)
        _atomic_write(ledger_path, ledger, jsonl=True)
        _atomic_write(provider_path, provider_audits, jsonl=True)
        _atomic_write(audit_path, audits, jsonl=True)
        _atomic_write(retry_path, retry, jsonl=True)

    # Phase 1: provenance-preserving source cache reuse.
    for oid in sorted(VALIDATED_IDS):
        source = source_cache[oid]
        identity = source["request_identity"]
        target_identity = _sha({"source_run": str(source_run), "source_identity": identity,
                                "provenance": "source_validated_reuse"})
        payload = deepcopy(source["payload"])
        payload["provenance"] = {
            **payload.get("provenance", {}), "source_kind": "source_validated_reuse",
            "source_run": str(source_run), "source_extraction_identity": identity,
            "provider_execution_identity_source": "source_artifact_identity_or_unknown",
        }
        cache["entries"][target_identity] = {
            "kind": "extraction", "request_identity": target_identity,
            "source_extraction_identity": identity, "source_run": str(source_run),
            "provenance": "source_validated_reuse", "payload": payload,
        }
        validated_by_id[oid] = payload
        _upsert(ledger, {
            "ledger_entry_id": _entry_id("extraction", oid, target_identity),
            "call_type": "extraction", "record_id": oid, "identity": target_identity,
            "status": "validated", "source": "source_validated_reuse",
            "provider_call": False, "source_run": str(source_run),
            "source_extraction_identity": identity,
        }, ("call_type", "record_id"))

    # Phase 2: 710 is always attempted offline before any provider call.
    offline_oid = next(iter(OFFLINE_IDS))
    existing_offline = next((e for e in cache["entries"].values()
                             if (e.get("payload") or {}).get("observation_id") == offline_oid), None)
    if existing_offline:
        validated_by_id[offline_oid] = existing_offline["payload"]
    else:
        source_payload = (source_providers.get(offline_oid) or {}).get("parsed_payload")
        validated, result = offline_revalidate_payload(
            payload=source_payload, contract=contracts[offline_oid], profiles=profiles,
        )
        identity = (validated or {}).get("extraction_identity") or _sha(result)
        _upsert(audits, {
            "record_type": "extraction", "record_id": offline_oid,
            "validation_audit_id": _entry_id("validation", offline_oid, identity),
            "valid": validated is not None, "errors": result["errors"],
            "failure_layer": None if validated else "deterministic_validation",
            "source": "offline_adapted_from_v5",
        }, ("record_type", "record_id"))
        _upsert(ledger, {
            "ledger_entry_id": _entry_id("extraction", offline_oid, identity),
            "call_type": "extraction", "record_id": offline_oid, "identity": identity,
            "status": "validated" if validated else "rejected_validation",
            "source": "offline_adapted_from_v5", "provider_call": False,
        }, ("call_type", "record_id"))
        if validated:
            cache["entries"][identity] = {
                "kind": "extraction", "request_identity": identity,
                "provenance": "offline_adapted_from_v5",
                "provider_execution_identity_source":
                    "source_artifact_identity_or_unknown",
                "current_offline_validation_provider_calls": 0,
                "payload": validated,
            }
            validated_by_id[offline_oid] = validated
    persist()

    # Phase 3: exact two-observation recall; resume replays only an exact completed artifact.
    for oid in sorted(EXPECTED_ALLOWLIST):
        source_row = source_ledger[oid]
        identity_bundle = {
            "prompt_version": PROMPT_VERSION_V6,
            "extraction_schema": EXTRACTION_SCHEMA_VERSION_V6,
            "validator": VALIDATOR_VERSION_V5,
            "observation_id": oid,
            "parent_provider_call_id": source_row.get("ledger_entry_id"),
            "parent_request_identity": source_row.get("identity"),
            "token_catalog_identity": contracts[oid].get("token_catalog_identity"),
            "anchor_text_identity":
                (contracts[oid].get("observation_token_catalog_identity") or {}).get(
                    "observation_anchor_text_identity_sha256"),
            "provider_execution_identity_sha256":
                execution_identity.identity_sha256,
        }
        identity = _sha(identity_bundle)
        cached = cache["entries"].get(identity)
        if cached:
            validated_by_id[oid] = cached["payload"]
            continue
        same_record = [r for r in provider_audits
                       if r.get("call_type") == "extraction" and r.get("record_id") == oid]
        mismatched = [r for r in same_record if r.get("request_identity") != identity
                      and r.get("status") == "provider_completed"]
        mismatched.extend(
            r for r in same_record
            if r.get("provider_execution_identity_sha256") !=
            execution_identity.identity_sha256
        )
        if mismatched:
            raise RuntimeError(f"resume_provider_identity_mismatch:{oid}")
        replay = next((r for r in same_record if r.get("request_identity") == identity
                       and r.get("status") == "provider_completed"
                       and isinstance(r.get("parsed_payload"), dict)), None)
        if replay:
            raw = replay["parsed_payload"]
        else:
            if oid not in EXPECTED_ALLOWLIST:
                raise RuntimeError(f"provider_allowlist_violation:{oid}")
            previous_attempts = sum(
                r.get("call_type") == "extraction" and r.get("record_id") == oid
                for r in provider_audits
            )
            if previous_attempts >= 1:
                raise RuntimeError(f"per_observation_attempt_bound_exceeded:{oid}")
            if calls["extraction"] >= 2 or sum(calls.values()) >= 5:
                raise RuntimeError("provider_call_hard_bound_exceeded_before_call")
            started = _now()
            calls["extraction"] += 1
            try:
                raw = _call(
                    client, call_type="extraction", record_id=oid,
                    request_identity=identity,
                    prompt=extraction_prompt_v6(contracts[oid], profiles),
                    attempt_number=2,
                )
                status, error = "provider_completed", None
            except Exception as exc:
                raw, status, error = None, "failed_provider", str(exc)
            provider_row = {
                "artifact_schema_version": PROVIDER_CALL_VERSION_V3,
                "call_type": "extraction", "record_id": oid, "observation_id": oid,
                "request_identity": identity, "recovery_attempt_id": _entry_id(
                    "attempt", oid, identity),
                "parent_provider_call_id": source_row.get("ledger_entry_id"),
                "parent_request_identity": source_row.get("identity"),
                "parent_error_kind": "output_truncated", "attempt_number": 2,
                "max_new_attempts": 1, "prompt_version": PROMPT_VERSION_V6,
                "extraction_schema": EXTRACTION_SCHEMA_VERSION_V6,
                "validator": VALIDATOR_VERSION_V5, "prompt_schema_changed": True,
                "new_request_identity": identity, "identity_bundle": identity_bundle,
                "token_catalog_identity": identity_bundle["token_catalog_identity"],
                "anchor_text_identity": identity_bundle["anchor_text_identity"],
                "provider_execution_identity": execution_identity.model_dump(mode="json"),
                "provider_execution_identity_sha256":
                    execution_identity.identity_sha256,
                "effective_provider": execution_identity.provider,
                "effective_model": execution_identity.model,
                "effective_thinking_mode": execution_identity.thinking_mode,
                "effective_configured_max_tokens":
                    execution_identity.configured_max_tokens,
                "started_at": started, "ended_at": _now(), "status": status,
                "parsed_payload": raw, "error": error,
            }
            _upsert(provider_audits, provider_row, ("call_type", "record_id"))
            _upsert(ledger, {
                "ledger_entry_id": _entry_id("extraction", oid, identity),
                "call_type": "extraction", "record_id": oid, "identity": identity,
                "status": status, "provider_call": True, "attempt_number": 2,
                "checkpoint_status": "provider_artifact_persisted",
                "planned_provider_execution_identity_sha256":
                    execution_identity.identity_sha256,
                "actual_provider_execution_identity_sha256":
                    execution_identity.identity_sha256,
                "identity_match": True,
            }, ("call_type", "record_id"))
            persist()
            if interrupt_after_persist == ("extraction", oid):
                raise InterruptedError(f"simulated_after_persist:{oid}")
            if raw is None:
                _upsert(retry, {
                    "retry_record_schema_version": RETRY_QUEUE_VERSION,
                    "observation_id": oid, "failure_layer": "provider",
                    "failure_code": "provider_failure", "next_attempt_allowed": False,
                    "provider_execution_identity_sha256":
                        execution_identity.identity_sha256,
                }, ("observation_id",))
                continue
        validated, validation_errors, layer = _fresh_validate(raw, contracts[oid], profiles)
        _upsert(audits, {
            "record_type": "extraction", "record_id": oid,
            "validation_audit_id": _entry_id("validation", oid, identity),
            "valid": validated is not None, "errors": validation_errors,
            "failure_layer": None if validated else layer, "source": "fresh_provider_v6",
        }, ("record_type", "record_id"))
        if validated:
            validated["extraction_identity"] = identity
            cache["entries"][identity] = {
                "kind": "extraction", "request_identity": identity,
                "identity_bundle": identity_bundle, "provenance": "fresh_provider_v6",
                "provider_execution_identity":
                    execution_identity.model_dump(mode="json"),
                "provider_execution_identity_sha256":
                    execution_identity.identity_sha256,
                "payload": validated,
            }
            validated_by_id[oid] = validated
            status = "validated"
        else:
            status = "rejected_schema" if layer == "schema" else "rejected_validation"
            _upsert(retry, {
                "retry_record_schema_version": RETRY_QUEUE_VERSION,
                "observation_id": oid, "failure_layer": layer,
                "failure_code": validation_errors[0], "next_attempt_allowed": False,
                "provider_execution_identity_sha256":
                    execution_identity.identity_sha256,
            }, ("observation_id",))
        _upsert(ledger, {
            "ledger_entry_id": _entry_id("extraction", oid, identity),
            "call_type": "extraction", "record_id": oid, "identity": identity,
            "status": status, "provider_call": replay is None,
            "checkpoint_status": "validation_persisted",
        }, ("call_type", "record_id"))
        persist()

    # Phase 4: recompute readiness from actual validated endpoints after recalls.
    comparisons: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for pair in pairs:
        pid = pair["pair_id"]
        a, b = pair["claim_a_id"], pair["claim_b_id"]
        missing = sorted({a, b} - set(validated_by_id))
        if missing:
            blocked.append({"pair_id": pid, "blocked_observation_ids": missing})
            continue
        identity = _sha({
            "pair_id": pid,
            "extraction_a_identity": validated_by_id[a].get("extraction_identity"),
            "extraction_b_identity": validated_by_id[b].get("extraction_identity"),
            "schema": "context_pair_attribution_v2",
            "provider_execution_identity_sha256":
                execution_identity.identity_sha256,
        })
        cached = cache["entries"].get(identity)
        if cached:
            comparisons.append(cached["payload"])
            continue
        same_record = [r for r in provider_audits
                       if r.get("call_type") == "comparison" and r.get("record_id") == pid]
        if any(r.get("request_identity") != identity and
               r.get("status") == "provider_completed" for r in same_record):
            raise RuntimeError(f"resume_provider_identity_mismatch:{pid}")
        if any(r.get("provider_execution_identity_sha256") !=
               execution_identity.identity_sha256 for r in same_record):
            raise RuntimeError(f"resume_provider_identity_mismatch:{pid}")
        replay = next((r for r in same_record if r.get("request_identity") == identity
                       and r.get("status") == "provider_completed"
                       and isinstance(r.get("parsed_payload"), dict)), None)
        if replay:
            raw = replay["parsed_payload"]
        else:
            if calls["comparison"] >= 3 or sum(calls.values()) >= 5:
                raise RuntimeError("provider_call_hard_bound_exceeded_before_call")
            calls["comparison"] += 1
            started = _now()
            try:
                raw = _call(
                    client, call_type="comparison", record_id=pid,
                    request_identity=identity,
                    prompt=pair_prompt({
                        "pair_id": pid, "claim_a": validated_by_id[a],
                        "claim_b": validated_by_id[b],
                    }, profiles),
                    attempt_number=1,
                )
                provider_status, provider_error = "provider_completed", None
            except Exception as exc:
                raw, provider_status, provider_error = None, "failed_provider", str(exc)
            _upsert(provider_audits, {
                "artifact_schema_version": PROVIDER_CALL_VERSION_V3,
                "call_type": "comparison", "record_id": pid, "pair_id": pid,
                "request_identity": identity, "attempt_number": 1,
                "started_at": started, "ended_at": _now(),
                "status": provider_status, "parsed_payload": raw,
                "error": provider_error,
                "provider_execution_identity": execution_identity.model_dump(mode="json"),
                "provider_execution_identity_sha256":
                    execution_identity.identity_sha256,
                "effective_provider": execution_identity.provider,
                "effective_model": execution_identity.model,
                "effective_thinking_mode": execution_identity.thinking_mode,
                "effective_configured_max_tokens":
                    execution_identity.configured_max_tokens,
            }, ("call_type", "record_id"))
            _upsert(ledger, {
                "ledger_entry_id": _entry_id("comparison", pid, identity),
                "call_type": "comparison", "record_id": pid, "identity": identity,
                "status": provider_status, "provider_call": True,
                "checkpoint_status": "provider_artifact_persisted",
                "planned_provider_execution_identity_sha256":
                    execution_identity.identity_sha256,
                "actual_provider_execution_identity_sha256":
                    execution_identity.identity_sha256,
                "identity_match": True,
            }, ("call_type", "record_id"))
            persist()
            if interrupt_after_persist == ("comparison", pid):
                raise InterruptedError(f"simulated_after_persist:{pid}")
            if raw is None:
                continue
        try:
            validated_pair, pair_errors = validate_pair_attribution(
                raw, pair_id=pid,
                extraction_a=ContextExtraction.model_validate({
                    **validated_by_id[a], "schema_version": "observation_context_extraction_v5"}),
                extraction_b=ContextExtraction.model_validate({
                    **validated_by_id[b], "schema_version": "observation_context_extraction_v5"}),
                profiles=profiles, registry=load_registry(),
            )
        except ValidationError as exc:
            validated_pair, pair_errors = None, [str(exc)]
        if validated_pair is not None and not pair_errors:
            payload = validated_pair.model_dump(mode="json")
            payload["comparison_identity"] = identity
            cache["entries"][identity] = {
                "kind": "pair", "request_identity": identity,
                "provider_execution_identity":
                    execution_identity.model_dump(mode="json"),
                "provider_execution_identity_sha256":
                    execution_identity.identity_sha256,
                "payload": payload,
            }
            comparisons.append(payload)
            status = "validated"
        else:
            status = "rejected_schema" if validated_pair is None else "rejected_validation"
        _upsert(ledger, {
            "ledger_entry_id": _entry_id("comparison", pid, identity),
            "call_type": "comparison", "record_id": pid, "identity": identity,
            "status": status, "provider_call": replay is None,
            "checkpoint_status": "validation_persisted", "errors": pair_errors,
        }, ("call_type", "record_id"))
        persist()

    extraction_rows = list(validated_by_id.values())
    _atomic_write(artifacts / "observation_context_extractions.jsonl",
                  extraction_rows, jsonl=True)
    _atomic_write(artifacts / "context_pair_attributions.jsonl", comparisons, jsonl=True)
    total_calls = calls["extraction"] + calls["comparison"]
    summary = {
        **plan, "schema_version": "context_attribution_recovery_execution_summary_v1",
        "plan_only": False, "status": "completed",
        "source_reused_count": sum(
            (e.get("provenance") == "source_validated_reuse")
            for e in cache["entries"].values()),
        "offline_validated_count": int(offline_oid in validated_by_id),
        "fresh_provider_validated_count": sum(oid in validated_by_id for oid in EXPECTED_ALLOWLIST),
        "provider_failed_count": sum(r.get("failure_layer") == "provider" for r in retry),
        "schema_rejected_count": sum(r.get("failure_layer") == "schema" for r in retry),
        "deterministic_rejected_count":
            sum(r.get("failure_layer") == "deterministic_validation" for r in retry),
        "comparison_executed_count": sum(
            row.get("call_type") == "comparison"
            and row.get("status") in {
                "provider_completed", "validated", "rejected_schema",
                "rejected_validation", "failed_provider",
            }
            for row in ledger
        ),
        "comparison_blocked_count": len(blocked),
        "blocked_pairs": blocked, "provider_calls": total_calls,
        "extraction_provider_calls": calls["extraction"],
        "comparison_provider_calls": calls["comparison"],
        "network_calls": 0 if test_only else total_calls,
        "real_api_calls": 0 if test_only else total_calls,
        "downloads": 0, "credential_values_read": False if test_only else None,
        "provider_client_created": True, "provider_mode": provider_mode,
        "provider": execution_identity.provider,
        "model": execution_identity.model,
        "thinking_mode": execution_identity.thinking_mode,
        "configured_max_tokens": execution_identity.configured_max_tokens,
        "provider_configuration_source":
            execution_identity.configuration_source,
        "provider_execution_identity_sha256":
            execution_identity.identity_sha256,
        "provider_execution_identity":
            execution_identity.model_dump(mode="json"),
        "scientific_result_test_only": test_only,
        "not_reusable_as_production_scientific_artifact": test_only,
        "handoff_created": False, "activation": False,
        "active_pointer_unchanged": True, "atlas_activated": False,
        "variational_em_called": False,
    }
    _atomic_write(artifacts / "context_attribution_summary.json", summary)
    _atomic_write(artifacts / "context_attribution_recovery_plan.json", plan)
    return summary


__all__ = [
    "BLOCKED_DEFAULT", "EXPECTED_ALLOWLIST", "execute_targeted_recovery",
    "validate_targeted_recovery_execution_plan",
]
