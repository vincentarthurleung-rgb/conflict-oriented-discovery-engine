"""Resource policy enforcement for external validation query plans."""

from __future__ import annotations

from collections import Counter

from code_engine.schemas.validation import ValidationQueryPlan, ValidationResourcePolicy


def check_validation_query_plan_against_policy(
    plan: ValidationQueryPlan, policy: ValidationResourcePolicy,
) -> ValidationQueryPlan:
    checked = plan.model_copy(deep=True)
    warnings = list(checked.warnings)
    reasons = []
    if checked.estimated_memory_mb is not None and checked.estimated_memory_mb > policy.max_memory_mb:
        reasons.append("estimated_memory_over_budget")
    if checked.execution_mode == "local_index" and checked.query_context.get("requires_full_scan") and not policy.allow_large_local_scan:
        reasons.append("large_local_scan_disallowed")
    record_limit = min(policy.max_records_per_validator, policy.max_records_per_anchor)
    if checked.max_records > record_limit:
        checked.max_records = record_limit
        warnings.append("max_records_truncated_by_resource_policy")
    if checked.estimated_records is not None and checked.estimated_records > record_limit:
        checked.estimated_records = record_limit
        warnings.append("estimated_records_truncated_by_resource_policy")
    if checked.max_signals > policy.max_signals_per_validator:
        checked.max_signals = policy.max_signals_per_validator
        warnings.append("max_signals_truncated_by_resource_policy")
    if checked.max_raw_payload_bytes > policy.max_raw_payload_bytes_per_validator:
        checked.max_raw_payload_bytes = policy.max_raw_payload_bytes_per_validator
        warnings.append("raw_payload_truncated")
    if checked.timeout_seconds > policy.max_query_seconds:
        checked.timeout_seconds = policy.max_query_seconds
        warnings.append("query_timeout_truncated_by_resource_policy")
    if reasons:
        checked.status = "blocked"
        checked.execution_mode = "blocked"
        checked.reason = ";".join(reasons)
    checked.warnings = list(dict.fromkeys(warnings))
    return checked


def enforce_validation_resource_policy(
    plans: list[ValidationQueryPlan], policy: ValidationResourcePolicy,
) -> list[ValidationQueryPlan]:
    if policy.max_concurrent_validator_queries != 1:
        policy = policy.model_copy(update={"max_concurrent_validator_queries": 1})
    return [check_validation_query_plan_against_policy(plan, policy) for plan in plans]


def summarize_validation_resource_usage(plans: list[ValidationQueryPlan]) -> dict:
    statuses = Counter(item.status for item in plans)
    modes = Counter(item.execution_mode for item in plans)
    return {
        "query_plan_count": len(plans),
        "allowed_query_count": statuses["allowed"],
        "blocked_query_count": sum(count for status, count in statuses.items() if status in {"blocked", "no_index", "no_cache", "provider_not_configured", "too_broad", "over_budget"}),
        "execution_mode_counts": dict(modes),
        "estimated_records": sum(int(item.estimated_records or 0) for item in plans),
        "estimated_memory_mb": round(sum(float(item.estimated_memory_mb or 0.0) for item in plans), 4),
        "blocked_reasons": dict(Counter(item.reason for item in plans if item.status != "allowed" and item.reason)),
        "max_concurrent_validator_queries": 1,
    }


__all__ = ["ValidationResourcePolicy", "check_validation_query_plan_against_policy", "enforce_validation_resource_policy", "summarize_validation_resource_usage"]
