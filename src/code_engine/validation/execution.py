"""Sequential streaming execution for resource-guarded validation plans."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from itertools import chain
from pathlib import Path
from typing import Any

from code_engine.schemas.validation import (
    ExternalEvidenceRecord, ValidationExecutionContext, ValidationExecutionResult,
    ValidationQueryPlan, ValidationResourcePolicy, ValidationSignal,
)
from code_engine.validation.cache import ValidationQueryCache


def _signal(plan: ValidationQueryPlan, signal_type: str, warning: str) -> ValidationSignal:
    stable = f"{plan.query_plan_id}|{signal_type}"
    return ValidationSignal(
        signal_id=hashlib.sha256(stable.encode()).hexdigest()[:16],
        validator_name=plan.validator_name, source_database=plan.index_name or plan.validator_name,
        query_plan_id=plan.query_plan_id, anchor_id=plan.anchor_id,
        signal_type=signal_type, confidence=0.0, quality=0.0,
        interpretation_limits=["External evidence and validation signals are not proof."],
        warnings=[warning],
    )


def execute_validation_query_plans(
    query_plans: list[ValidationQueryPlan], registry,
    resource_policy: ValidationResourcePolicy, execute: bool = False,
    network_enabled: bool = False, cache_enabled: bool = True,
    auth_config: dict | None = None, run_dir: Path | None = None,
    *, provider_clients: dict[str, Any] | None = None,
) -> ValidationExecutionResult:
    output = Path(run_dir) if run_dir is not None else None
    evidence_path = output / "external_validation_evidence.jsonl" if output else None
    signal_path = output / "external_validation_signals.jsonl" if output else None
    summary_path = output / "external_validation_execution_summary.json" if output else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    evidence_handle = evidence_path.open("w", encoding="utf-8") if evidence_path else None
    signal_handle = signal_path.open("w", encoding="utf-8") if signal_path else None
    context = ValidationExecutionContext(
        execute=execute, network_enabled=network_enabled,
        external_validation_enabled=resource_policy.external_validation_enabled,
        cache_enabled=cache_enabled, index_dir=resource_policy.index_dir,
        cache_dir=resource_policy.cache_dir, auth_config=auth_config or {},
        provider_clients=provider_clients or {}, resource_policy=resource_policy,
    )
    cache_path = None
    if resource_policy.cache_dir:
        candidate = Path(resource_policy.cache_dir)
        cache_path = candidate if candidate.suffix in {".sqlite", ".db"} else candidate / "validation_query_cache.sqlite"
    cache = ValidationQueryCache(cache_path) if cache_enabled and cache_path else None
    counts = Counter()
    evidence_count = signal_count = executed = blocked = cache_hits = cache_misses = network_calls = 0
    max_records_seen = 0
    warnings = []
    try:
        if not execute:
            status = "planned"
            blocked = sum(item.status != "allowed" for item in query_plans)
            counts.update(item.status for item in query_plans)
        else:
            status = "completed"
            for plan in query_plans:
                if plan.status != "allowed":
                    blocked += 1
                    counts[plan.status] += 1
                    if plan.status == "no_cache":
                        cache_misses += 1
                    continue
                if plan.execution_mode == "disabled":
                    blocked += 1
                    counts["no_coverage"] += 1
                    if signal_handle:
                        signal = _signal(plan, "no_coverage_signal", "Null validator route; no external coverage.")
                        signal_handle.write(signal.model_dump_json() + "\n")
                        signal_count += 1
                    continue
                if plan.execution_mode == "remote_api" and not (network_enabled and resource_policy.external_validation_enabled):
                    blocked += 1
                    counts["blocked_remote"] += 1
                    continue
                validator = registry.create(plan.validator_name)
                if plan.validator_name in context.provider_clients:
                    validator.provider_client = context.provider_clients[plan.validator_name]
                if plan.execution_mode == "remote_api" and getattr(validator, "provider_client", None) is None:
                    blocked += 1
                    counts["external_index_not_configured"] += 1
                    signal = _signal(plan, "external_index_not_configured_signal", "Remote provider client is not configured.")
                    if signal_handle:
                        signal_handle.write(signal.model_dump_json() + "\n")
                        signal_count += 1
                    continue
                cached_iterator = cache.lookup(plan.cache_key, plan.max_records) if cache and plan.cache_key else iter(())
                first_cached = next(cached_iterator, None)
                if first_cached is not None:
                    source = chain(
                        (ExternalEvidenceRecord.model_validate(first_cached),),
                        (ExternalEvidenceRecord.model_validate(item) for item in cached_iterator),
                    )
                    cache_hits += 1
                    counts["cache_hit"] += 1
                elif plan.execution_mode == "cache_only":
                    cache_misses += 1
                    counts["cache_miss_no_conclusion"] += 1
                    continue
                else:
                    if cache:
                        cache_misses += 1
                    try:
                        source = validator.stream_evidence(plan, context)
                    except Exception as exc:
                        source = iter(())
                        warnings.append(f"{plan.validator_name}:{type(exc).__name__}:{exc}")
                executed += 1
                if plan.execution_mode == "remote_api":
                    network_calls += 1
                plan_records = 0
                plan_signals = 0
                try:
                    for evidence in source:
                        if plan_records >= plan.max_records:
                            break
                        plan_records += 1
                        evidence_count += 1
                        if evidence_handle:
                            evidence_handle.write(evidence.model_dump_json() + "\n")
                        if cache and plan.cache_key and first_cached is None:
                            cache.store_record(plan.cache_key, plan_records - 1, evidence, reset=plan_records == 1)
                        for signal in validator.build_signals((evidence,), context):
                            if plan_signals >= plan.max_signals or signal_count >= resource_policy.max_signals_per_run:
                                break
                            if signal_handle:
                                signal_handle.write(signal.model_dump_json() + "\n")
                            plan_signals += 1
                            signal_count += 1
                    max_records_seen = max(max_records_seen, plan_records)
                    if plan_records == 0:
                        counts["no_coverage"] += 1
                        signal = _signal(plan, "no_coverage_signal", "Successful query returned no records; this is not contradiction.")
                        if signal_handle and signal_count < resource_policy.max_signals_per_run:
                            signal_handle.write(signal.model_dump_json() + "\n")
                            signal_count += 1
                    else:
                        counts["evidence_streamed"] += 1
                except Exception as exc:
                    counts["error"] += 1
                    warning = f"{plan.validator_name}:{type(exc).__name__}:{exc}"
                    warnings.append(warning)
                    signal = _signal(plan, "error_signal", warning)
                    if signal_handle:
                        signal_handle.write(signal.model_dump_json() + "\n")
                        signal_count += 1
    finally:
        if evidence_handle:
            evidence_handle.close()
        if signal_handle:
            signal_handle.close()
    result = ValidationExecutionResult(
        result_id=hashlib.sha256("|".join(item.query_plan_id for item in query_plans).encode()).hexdigest()[:16],
        status=status, query_plan_count=len(query_plans), executed_query_count=executed,
        blocked_query_count=blocked, validator_status_counts=dict(counts),
        evidence_count=evidence_count, signal_count=signal_count,
        cache_hit_count=cache_hits, cache_miss_count=cache_misses,
        estimated_memory_mb=sum(float(item.estimated_memory_mb or 0.0) for item in query_plans),
        actual_max_records_seen=max_records_seen, network_calls_made=network_calls,
        warnings=warnings,
        artifact_refs={
            "evidence": str(evidence_path) if evidence_path else "",
            "signals": str(signal_path) if signal_path else "",
            "summary": str(summary_path) if summary_path else "",
        },
    )
    if summary_path:
        summary_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


__all__ = ["execute_validation_query_plans"]
