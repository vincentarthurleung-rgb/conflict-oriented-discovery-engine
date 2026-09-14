"""Deterministic v2.3-beta Policy A production-candidate disposition logic."""

from __future__ import annotations

from dataclasses import dataclass


ORIGINAL_DISPOSITIONS = ("TIER_A", "TIER_B", "REJECT", "ABSTAIN")


@dataclass(frozen=True)
class SearchPlanV23BetaDispositionDecision:
    original_v22_disposition: str
    final_disposition: str
    blocker_reason_codes: tuple[str, ...]
    tier_a_demoted_to_tier_b: bool
    tier_b_subtier_annotation: str | None
    acquisition_priority_tier: str | None
    within_tier_v22_order_preserved: bool
    hard_rejected_by_v23_beta: bool
    tier_b_to_tier_a_promoted: bool
    policy_version: str
    decision_mode: str = "deterministic"


def decide_search_plan_v23_beta_disposition(
    original_v22_disposition: str,
    *,
    biological_unit_state: str,
    functional_relation_state: str,
    endpoint_state: str,
    tier_b_subtier_annotation: str | None,
    config: dict,
    mode: str = "v2.3-beta",
) -> SearchPlanV23BetaDispositionDecision:
    """Apply Policy A without changing legacy v2.2 behavior or Tier-B order."""
    if original_v22_disposition not in ORIGINAL_DISPOSITIONS:
        raise ValueError(f"unknown frozen v2.2 disposition: {original_v22_disposition}")
    if mode not in {"v2.2", "v2.3-beta"}:
        raise ValueError(f"unsupported search-plan mode: {mode}")
    if mode == "v2.3-beta" and config.get("selected_policy") != "POLICY_A_MINIMAL":
        raise ValueError("v2.3-beta requires frozen POLICY_A_MINIMAL")

    if mode == "v2.2":
        final = original_v22_disposition
        reasons: list[str] = []
    else:
        blockers = config["tier_a_blockers"]
        reasons = []
        if biological_unit_state in blockers["biological_unit_states"]:
            reasons.append("P0_POSITIVE_BIOLOGICAL_UNIT_INCOMPATIBILITY")
        if functional_relation_state in blockers["functional_relation_states"]:
            reasons.append("P1_RELATION_WEAK")
        if endpoint_state in blockers["endpoint_states"]:
            reasons.append("P2_POSITIVE_ENDPOINT_INCOMPATIBILITY")
        final = original_v22_disposition
        if original_v22_disposition == "TIER_A" and reasons:
            final = "TIER_B"

    demoted = original_v22_disposition == "TIER_A" and final == "TIER_B"
    priority = final if final in {"TIER_A", "TIER_B"} else None
    return SearchPlanV23BetaDispositionDecision(
        original_v22_disposition=original_v22_disposition,
        final_disposition=final,
        blocker_reason_codes=tuple(reasons) if original_v22_disposition == "TIER_A" else (),
        tier_a_demoted_to_tier_b=demoted,
        tier_b_subtier_annotation=tier_b_subtier_annotation,
        acquisition_priority_tier=priority,
        within_tier_v22_order_preserved=True,
        hard_rejected_by_v23_beta=False,
        tier_b_to_tier_a_promoted=False,
        policy_version="v2.2-unchanged" if mode == "v2.2" else config["module_versions"]["composite_policy_version"],
    )
