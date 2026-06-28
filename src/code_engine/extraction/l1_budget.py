"""Cost estimation and deny-by-default budget enforcement for progressive L1."""

from __future__ import annotations

from typing import Any, Iterable


PRICING_PROFILES = {
    "deepseek_default": {"input_usd_per_million_tokens": 0.28},
    "conservative_default": {"input_usd_per_million_tokens": 1.0},
    "test": {"input_usd_per_million_tokens": 1.0},
}

DEFAULT_BUDGET_POLICY = {
    "max_papers_per_prompt": 100,
    "max_fulltext_papers_per_prompt": 20,
    "max_sections_per_paper": 5,
    "max_spans_per_paper": 8,
    "max_l1_calls_per_prompt": 100,
    "max_l1_input_tokens_per_prompt": 200000,
    "max_l1_total_calls": 1000,
    "max_l1_total_input_tokens": 2000000,
    "budget_usd": None,
    "model_pricing_profile": "deepseek_default",
}


def estimate_tokens(text: str) -> int:
    return max(1, (len(str(text or "")) + 3) // 4)


def estimate_l1_cost(
    inputs: Iterable[str] | None = None,
    *,
    input_tokens: int | None = None,
    call_count: int | None = None,
    model_pricing_profile: str = "deepseek_default",
) -> dict[str, Any]:
    texts = list(inputs or [])
    tokens = int(input_tokens if input_tokens is not None else sum(estimate_tokens(item) for item in texts))
    calls = int(call_count if call_count is not None else len(texts))
    pricing = PRICING_PROFILES.get(model_pricing_profile, PRICING_PROFILES["conservative_default"])
    cost = tokens / 1_000_000 * float(pricing["input_usd_per_million_tokens"])
    return {
        "estimated_calls": calls,
        "estimated_input_tokens": tokens,
        "estimated_cost_usd": round(cost, 6),
        "model_pricing_profile": model_pricing_profile,
        "pricing": pricing,
    }


def enforce_l1_budget(
    estimate: dict[str, Any],
    budget_policy: dict[str, Any] | None = None,
    *,
    execute: bool = False,
    allow_budget_overrun: bool = False,
) -> dict[str, Any]:
    policy = {**DEFAULT_BUDGET_POLICY, **(budget_policy or {})}
    reasons = []
    checks = (
        ("max_l1_calls_per_prompt", estimate.get("estimated_calls", 0)),
        ("max_l1_total_calls", estimate.get("estimated_calls", 0)),
        ("max_l1_input_tokens_per_prompt", estimate.get("estimated_input_tokens", 0)),
        ("max_l1_total_input_tokens", estimate.get("estimated_input_tokens", 0)),
        ("budget_usd", estimate.get("estimated_cost_usd", 0.0)),
    )
    for key, actual in checks:
        limit = policy.get(key)
        if limit is not None and actual > limit:
            reasons.append(f"{key}_exceeded:{actual}>{limit}")
    over_budget = bool(reasons)
    blocked = bool(execute and over_budget and not allow_budget_overrun)
    return {
        "over_budget": over_budget,
        "blocked": blocked,
        "allow_budget_overrun": bool(allow_budget_overrun),
        "reasons": reasons,
        "policy": policy,
    }


def build_l1_budget_report(
    estimate: dict[str, Any], decision: dict[str, Any], *, actual_calls: int = 0,
    actual_input_tokens: int = 0, actual_cost_usd: float | None = None,
) -> dict[str, Any]:
    return {
        **estimate,
        "budget_status": "blocked" if decision.get("blocked") else ("overrun_allowed" if decision.get("over_budget") else "within_budget"),
        "budget_reasons": list(decision.get("reasons", [])),
        "budget_policy": dict(decision.get("policy", {})),
        "actual_calls": int(actual_calls),
        "actual_input_tokens": int(actual_input_tokens),
        "actual_cost_usd": actual_cost_usd,
    }


__all__ = ["estimate_l1_cost", "enforce_l1_budget", "build_l1_budget_report", "estimate_tokens", "DEFAULT_BUDGET_POLICY"]
