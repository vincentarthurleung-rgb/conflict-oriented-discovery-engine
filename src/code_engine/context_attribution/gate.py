from __future__ import annotations
from typing import Any
from .models import ContextPairAttribution
from .registry import resolve_factors

def apply_comparability_gate(attribution: ContextPairAttribution | dict[str, Any], profiles: list[str],
                             *, existing_formal_eligibility: bool) -> dict[str, Any]:
    value = attribution if isinstance(attribution, ContextPairAttribution) else ContextPairAttribution.model_validate(attribution)
    factors = resolve_factors(profiles)
    validated = value.validation_status == "validated"
    blocking = [x.factor_id for x in value.factor_comparisons
                if x.comparability_effect == "blocking"
                and factors.get(x.factor_id, {}).get("whether_difference_can_block_comparability")]
    if not validated:
        status, eligible, reason = "reviewable", False, "context_attribution_not_validated"
    elif value.comparability == "non_comparable" and blocking:
        status, eligible, reason = "blocked", False, "validated_blocking_context_difference"
    elif value.comparability == "insufficient_information":
        status, eligible, reason = "reviewable", False, "insufficient_context_information"
    elif value.comparability == "conditionally_comparable":
        eligible = bool(existing_formal_eligibility)
        status, reason = "candidate" if eligible else "blocked_by_existing_formal_gate", "conditional_context_with_explanatory_factors"
    else:
        eligible = bool(existing_formal_eligibility)
        status, reason = "pass" if eligible else "blocked_by_existing_formal_gate", "context_comparable"
    return {"schema_version": "deterministic_comparability_gate_v1", "pair_id": value.pair_id,
            "comparability_status": value.comparability, "gate_status": status,
            "formal_conflict_eligible": eligible, "validated_blocking_factors": blocking,
            "primary_explanatory_factors": value.primary_explanatory_factors,
            "reason": reason, "does_not_modify_polarity_or_canonical_state": True}
