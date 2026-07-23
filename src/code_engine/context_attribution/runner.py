from __future__ import annotations

import json
import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.extraction.client_factory import (
    build_l1_client_from_env_or_config, resolve_l1_provider_settings,
)
from code_engine.extraction.deepseek_client import DeepSeekExtractionError, _safe_provider_error_body

from .engine import (
    PROMPT_VERSION, build_abstract_input, build_fulltext_input, extraction_cache_identity,
    extraction_prompt, pair_cache_identity, pair_prompt,
)
from .gate import apply_comparability_gate
from .models import ContextExtraction, EXTRACTION_SCHEMA_VERSION, PAIR_SCHEMA_VERSION
from .planning import (
    complete_selection, observation_id, observation_input_mode,
    representative_smoke_selection, validate_plan,
)
from .registry import load_registry
from .validation import validate_context_extraction, validate_pair_attribution

ARTIFACTS = (
    "observation_context_extractions.jsonl", "context_pair_attributions.jsonl",
    "context_attribution_validation_audit.jsonl", "context_attribution_execution_ledger.jsonl",
    "context_attribution_summary.json", "context_attribution_completeness_report.json",
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
    if not path.exists(): return {"schema_version": "context_attribution_cache_v1", "entries": {}}
    return json.loads(path.read_text(encoding="utf-8"))

def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")

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

def _upsert_ledger(ledger: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    index = next((i for i, row in enumerate(ledger)
                  if row.get("ledger_entry_id") == entry.get("ledger_entry_id")), None)
    if index is None: ledger.append(entry)
    else: ledger[index] = {**ledger[index], **entry}

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
                            thinking_mode: str | None = None) -> dict[str, Any]:
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
    all_candidate_ids = sorted({observation_id(p[side]) for p in pairs for side in ("claim_a", "claim_b")})
    by_id = {observation_id(x): x for x in eligible_observations}
    all_contracts = {
        oid: (build_fulltext_input(by_id[oid], profiles)
              if observation_input_mode(by_id[oid]) == "fulltext" else build_abstract_input(by_id[oid], profiles))
        for oid in all_candidate_ids
    }
    identities = {
        oid: extraction_cache_identity(contract, profiles=profiles, provider=provider, model=model,
                                       thinking_mode=thinking_mode, max_tokens=max_tokens)
        for oid, contract in all_contracts.items()
    }
    cache_path = output / "context_attribution_cache.json"
    cache = _read_index(cache_path) if resume or cached_only else {"schema_version": "context_attribution_cache_v1", "entries": {}}
    fixtures = _load_fixture(fixture_responses)
    comparison_identities: dict[str, str] = {}
    for pair in pairs:
        a, b = observation_id(pair["claim_a"]), observation_id(pair["claim_b"])
        comparison_identities[pair["pair_id"]] = pair_cache_identity(identities[a], identities[b], profiles)
    selected_observation_ids = list(selection["selected_observations"])
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
    registry = load_registry()
    selected_observation_rows = [
        {"observation_id": oid, "input_mode": observation_input_mode(by_id[oid]),
         "cache_hit": oid in cached_extraction_ids, "planned_extraction": oid in planned_extraction_ids}
        for oid in selected_observation_ids
    ]
    plan = {
        "schema_version": "context_attribution_execution_plan_v2", "plan_only": not execute,
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
        "profile_version": registry["registry_version"],
        "provider_calls_hard_bound": len(planned_extraction_ids) + len(planned_comparison_ids),
        "activation": False, "active_pointer_unchanged": True,
        "legacy_variational_em_called": False,
    }
    plan_errors = validate_plan(plan)
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
                     "downloads": 0, "activation": False})
        for name in ARTIFACTS[:4]: (output / name).touch(exist_ok=True)
        return plan
    if plan["plan_status"] in {"invalid", "blocked_by_call_bound"}:
        raise RuntimeError(f"context attribution execution blocked: {plan['plan_status']}")
    contracts = {oid: all_contracts[oid] for oid in selected_observation_ids}
    client = build_l1_client_from_env_or_config(provider, model, max_retries=0) if api else None
    if api and client is None: raise RuntimeError("requested_provider_not_configured")
    ledger_path = output / ARTIFACTS[3]
    ledger = _rows(ledger_path) if resume else []
    audits, extractions, attributions = [], [], []
    calls = {"extraction": 0, "comparison": 0}
    for oid in selected_observation_ids:
        identity = identities[oid]
        _upsert_ledger(ledger, {
            "ledger_entry_id": _ledger_id("extraction", oid, identity),
            "call_type": "extraction", "record_id": oid, "identity": identity,
            "status": "pending", "provider_call": False, "provider": provider, "model": model,
        })
    for pid in selection["selected_pair_ids"]:
        identity = comparison_identities[pid]
        _upsert_ledger(ledger, {
            "ledger_entry_id": _ledger_id("comparison", pid, identity),
            "call_type": "comparison", "record_id": pid, "identity": identity,
            "status": "pending", "provider_call": False, "provider": provider, "model": model,
        })
    _write_jsonl(ledger_path, ledger)
    extraction_by_id: dict[str, ContextExtraction] = {}
    systemic_failure: dict[str, Any] | None = None
    for oid, contract in contracts.items():
        identity = identities[oid]
        ledger_entry_id = _ledger_id("extraction", oid, identity)
        cached = cache["entries"].get(identity) if _valid_cache_entry(cache, identity, "extraction") else None
        source = "cache" if cached else "fixture" if oid in fixtures.get("extractions", {}) else "provider"
        try:
            if cached:
                raw = cached["payload"]
            elif oid in fixtures.get("extractions", {}):
                raw = fixtures["extractions"][oid]
            elif cached_only or calls["extraction"] >= extraction_limit or client is None:
                continue
            else:
                _upsert_ledger(ledger, {
                    "ledger_entry_id": ledger_entry_id, "status": "in_progress",
                    "source": "provider", "provider_call": True, "attempt_count": 1,
                })
                _write_jsonl(ledger_path, ledger)
                calls["extraction"] += 1
                method = getattr(client, "extract_json_result", None) or getattr(client, "extract_json")
                response = method(
                    extraction_prompt(contract, profiles), model=model, temperature=0, top_p=1,
                    max_tokens=max_tokens, retry_on_length=False, thinking_mode=thinking_mode,
                )
                raw = response.payload if hasattr(response, "payload") else response
            validated, errors = validate_context_extraction(raw, contract, profiles)
            validated.extraction_identity = identity
            dumped = validated.model_dump(mode="json")
            if not errors:
                cache["entries"][identity] = {"kind": "extraction", "payload": dumped}
                extraction_by_id[oid] = validated
            extractions.append(dumped); audits.append({"record_type": "extraction", "record_id": oid, "valid": not errors, "errors": errors})
            _upsert_ledger(ledger, {
                "ledger_entry_id": ledger_entry_id, "source": source,
                "provider_call": source == "provider", "status": "rejected_validation" if errors else "completed",
            })
        except DeepSeekExtractionError as exc:
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
            audits.append({"record_type": "extraction", "record_id": oid, "valid": False, "errors": [str(exc)]})
            _upsert_ledger(ledger, {
                "ledger_entry_id": ledger_entry_id, "source": source,
                "provider_call": source == "provider", "status": "rejected_schema",
                "safe_error_type": type(exc).__name__,
            })
        _write_jsonl(output / ARTIFACTS[2], audits)
        _write_jsonl(ledger_path, ledger)
        _write_json(cache_path, cache)
        if systemic_failure is not None:
            break
    gates = []
    for pair in ([] if systemic_failure is not None else selected_pairs):
        pid = pair["pair_id"]; identity = comparison_identities[pid]
        ledger_entry_id = _ledger_id("comparison", pid, identity)
        a, b = str(pair["claim_a"].get("observation_id") or pair["claim_a"].get("claim_id")), str(pair["claim_b"].get("observation_id") or pair["claim_b"].get("claim_id"))
        if a not in extraction_by_id or b not in extraction_by_id: continue
        cached = cache["entries"].get(identity) if _valid_cache_entry(cache, identity, "pair") else None
        source = "cache" if cached else "fixture" if pid in fixtures.get("pairs", {}) else "provider"
        try:
            if cached:
                raw = cached["payload"]
            elif pid in fixtures.get("pairs", {}):
                raw = fixtures["pairs"][pid]
            elif cached_only or calls["comparison"] >= comparison_limit or client is None:
                continue
            else:
                payload = {"pair_id": pid, "claim_a_extraction": extraction_by_id[a].model_dump(mode="json"),
                           "claim_b_extraction": extraction_by_id[b].model_dump(mode="json"),
                           "claim_a_evidence": contracts[a], "claim_b_evidence": contracts[b]}
                _upsert_ledger(ledger, {
                    "ledger_entry_id": ledger_entry_id, "status": "in_progress",
                    "source": "provider", "provider_call": True, "attempt_count": 1,
                })
                _write_jsonl(ledger_path, ledger)
                calls["comparison"] += 1
                method = getattr(client, "extract_json_result", None) or getattr(client, "extract_json")
                response = method(
                    pair_prompt(payload, profiles), model=model, temperature=0, top_p=1,
                    max_tokens=max_tokens, retry_on_length=False, thinking_mode=thinking_mode,
                )
                raw = response.payload if hasattr(response, "payload") else response
            validated, errors = validate_pair_attribution(raw, pair_id=pid, extraction_a=extraction_by_id[a],
                                                          extraction_b=extraction_by_id[b], profiles=profiles)
            validated.comparison_identity = identity
            dumped = validated.model_dump(mode="json")
            if not errors: cache["entries"][identity] = {"kind": "pair", "payload": dumped}
            attributions.append(dumped); audits.append({"record_type": "pair", "record_id": pid, "valid": not errors, "errors": errors})
            existing = all(bool((x.get("eligibility") or {}).get("conflict_eligible", x.get("conflict_eligible", False)))
                           for x in (pair["claim_a"], pair["claim_b"]))
            gates.append(apply_comparability_gate(validated, profiles, existing_formal_eligibility=existing))
            _upsert_ledger(ledger, {
                "ledger_entry_id": ledger_entry_id, "source": source,
                "provider_call": source == "provider", "status": "rejected_validation" if errors else "completed",
            })
        except DeepSeekExtractionError as exc:
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
        _write_jsonl(output / ARTIFACTS[2], audits)
        _write_jsonl(ledger_path, ledger)
        _write_json(cache_path, cache)
        if systemic_failure is not None:
            break
    cache["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(cache_path, cache)
    _write_jsonl(output / ARTIFACTS[0], extractions); _write_jsonl(output / ARTIFACTS[1], attributions)
    _write_jsonl(output / ARTIFACTS[2], audits); _write_jsonl(output / ARTIFACTS[3], ledger)
    _write_jsonl(output / "context_comparability_gate.jsonl", gates)
    gate_by_pair = {x["pair_id"]: x for x in gates}
    _write_jsonl(output / "context_attribution_handoff.jsonl", [{
        "schema_version": "context_attribution_handoff_v1",
        "pair_id": item["pair_id"],
        "extracted_context": {
            "claim_a_extraction_identity": identities.get(item["claim_a_observation_id"]),
            "claim_b_extraction_identity": identities.get(item["claim_b_observation_id"]),
        },
        "validated_context": item.get("validation_status") == "validated",
        "pair_attribution": item,
        "comparability_status": (gate_by_pair.get(item["pair_id"]) or {}).get("comparability_status"),
        "formal_conflict_eligibility": (gate_by_pair.get(item["pair_id"]) or {}).get("formal_conflict_eligible", False),
        "natural_language_is_not_canonical_fact": True,
    } for item in attributions])
    retry_queue = [{"record_type": x["record_type"], "record_id": x["record_id"], "errors": x["errors"]}
                   for x in audits if not x["valid"]]
    _write_jsonl(output / "context_attribution_retry_queue.jsonl", retry_queue)
    distribution = Counter(x.get("comparability") for x in attributions)
    execution_status = "failed_systemic_provider_error" if systemic_failure is not None else "completed"
    summary = {**plan, "status": execution_status, "plan_only": False, "extraction_count": len(extractions),
               "pair_attribution_count": len(attributions), "comparability_distribution": dict(distribution),
               "validation_failure_count": sum(not x["valid"] for x in audits),
               "api_calls": sum(calls.values()), "provider_calls": sum(calls.values()),
               "network_calls": sum(calls.values()), "downloads": 0, "activation": False,
               "systemic_provider_failure": systemic_failure,
               "pending_ledger_entry_count": sum(x.get("status") == "pending" for x in ledger),
               "failed_ledger_entry_count": sum(str(x.get("status", "")).startswith("failed") for x in ledger)}
    execution_complete = len(attributions) == len(selected_pairs)
    completeness = {"status": "failed_systemic_provider_error" if systemic_failure is not None else
                              "complete" if purpose == "complete" and execution_complete else
                              "smoke_complete" if purpose == "smoke" and execution_complete else "incomplete",
                    "purpose": purpose, "coverage_complete": purpose == "complete" and execution_complete,
                    "candidate_pairs": len(pairs), "selected_pairs": len(selected_pairs),
                    "candidate_pairs_attributed": len(attributions),
                    "validated_extractions": sum(x.validation_status == "validated" for x in extraction_by_id.values()),
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
