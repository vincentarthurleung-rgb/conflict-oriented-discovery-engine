"""Deterministic shadow-only composition of frozen P0/P1/P2 states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


EvidenceClass = Literal[
    "CLASS_0_POSITIVE_INCOMPATIBILITY", "CLASS_1_RELATION_WEAK",
    "CLASS_2_REVIEWABLE_UNRESOLVED", "CLASS_3_POSITIVELY_SUPPORTED",
]
CompositeDisposition = Literal[
    "B1_SUPPORTED_OR_SINGLE_UNCERTAINTY", "B2_MULTI_UNRESOLVED", "B3_RELATION_WEAK",
    "INCOMPATIBLE_DIAGNOSTIC", "ORIGINAL_REJECT_PRESERVED", "ORIGINAL_ABSTAIN_PRESERVED",
]

EVIDENCE_CLASSES = (
    "CLASS_0_POSITIVE_INCOMPATIBILITY", "CLASS_1_RELATION_WEAK",
    "CLASS_2_REVIEWABLE_UNRESOLVED", "CLASS_3_POSITIVELY_SUPPORTED",
)
B_SUBTIERS = (
    "B1_SUPPORTED_OR_SINGLE_UNCERTAINTY", "B2_MULTI_UNRESOLVED",
    "B3_RELATION_WEAK", "INCOMPATIBLE_DIAGNOSTIC",
)


@dataclass(frozen=True)
class CompositePreAcquisitionProfileV1:
    packet_or_candidate_id: str
    case_id: str
    original_v22_disposition: str
    biological_unit_state: str
    biological_unit_reason_codes: tuple[str, ...]
    functional_relation_state: str
    functional_relation_reason_codes: tuple[str, ...]
    endpoint_state: str
    endpoint_reason_codes: tuple[str, ...]
    positive_incompatibility_flags: tuple[str, ...]
    relation_weak_flags: tuple[str, ...]
    uncertainty_flags: tuple[str, ...]
    evidence_class: EvidenceClass
    tier_b_subtier: str | None
    passes_tier_a_blocker_rule_shadow: bool
    tier_a_eligible_shadow: bool
    alpha4_original_eligible: bool
    fulltext_eligibility_by_policy: dict[str, bool]
    fulltext_priority_class_by_policy: dict[str, str]
    composite_disposition: CompositeDisposition
    disposition_reason_codes: tuple[str, ...]
    policy_version: str
    tier_b_policy_version: str
    decision_mode: str = "deterministic"
    preacquisition_only: bool = True
    numeric_scientific_score: None = None
    modifies_production_tier: bool = False
    modifies_production_acquisition: bool = False
    modifies_production_rejection: bool = False


def _classify(unit_state: str, relation_state: str, endpoint_state: str, policy):
    positive = []
    if unit_state in policy["positive_unit_incompatibility_states"]:
        positive.append("POSITIVE_UNIT_INCOMPATIBILITY")
    if endpoint_state in policy["positive_endpoint_incompatibility_states"]:
        positive.append("POSITIVE_ENDPOINT_INCOMPATIBILITY")
    weak = ["RELATION_WEAK_" + relation_state] if relation_state in policy["relation_weak_states"] else []
    uncertainty = []
    if unit_state in policy["unit_uncertainty_states"]:
        uncertainty.append("UNIT_UNRESOLVED")
    if relation_state in policy["relation_uncertainty_states"]:
        uncertainty.append("RELATION_UNRESOLVED")
    if endpoint_state == "PARTIAL":
        uncertainty.append("ENDPOINT_PARTIAL_NONBLOCKING")
    elif endpoint_state == "UNRESOLVED":
        uncertainty.append("ENDPOINT_UNRESOLVED_NONBLOCKING")

    if positive:
        evidence_class = "CLASS_0_POSITIVE_INCOMPATIBILITY"
    elif weak:
        evidence_class = "CLASS_1_RELATION_WEAK"
    elif uncertainty and (unit_state == "UNRESOLVED" or relation_state == "UNRESOLVED"):
        evidence_class = "CLASS_2_REVIEWABLE_UNRESOLVED"
    elif (unit_state in policy["compatible_unit_states"]
          and relation_state in policy["strong_relation_states"]):
        evidence_class = "CLASS_3_POSITIVELY_SUPPORTED"
    else:
        raise ValueError(f"uncovered P0/P1/P2 state combination: {unit_state}/{relation_state}/{endpoint_state}")
    return positive, weak, uncertainty, evidence_class


def _subtier(unit_state, relation_state, positive, weak, policy):
    if positive:
        return "INCOMPATIBLE_DIAGNOSTIC"
    if weak:
        return "B3_RELATION_WEAK"
    if unit_state == "UNRESOLVED" and relation_state == "UNRESOLVED":
        return "B2_MULTI_UNRESOLVED"
    unit_positive = unit_state in policy["compatible_unit_states"]
    relation_positive = relation_state in policy["strong_relation_states"]
    if unit_positive or relation_positive:
        return "B1_SUPPORTED_OR_SINGLE_UNCERTAINTY"
    raise ValueError(f"uncovered Tier-B subtier combination: {unit_state}/{relation_state}")


def decide_composite_preacquisition_profile_v1(
    packet_or_candidate_id: str,
    case_id: str,
    original_v22_disposition: str,
    *,
    biological_unit_state: str,
    biological_unit_reason_codes,
    functional_relation_state: str,
    functional_relation_reason_codes,
    endpoint_state: str,
    endpoint_reason_codes,
    policy: dict,
    tier_b_policy: dict,
) -> CompositePreAcquisitionProfileV1:
    """Compose raw scientific states without scoring or production mutation."""
    if not policy.get("enabled") or not policy.get("shadow_only") or not tier_b_policy.get("shadow_only"):
        raise ValueError("alpha4 composite policy must be enabled in shadow mode")
    positive, weak, uncertainty, evidence_class = _classify(
        biological_unit_state, functional_relation_state, endpoint_state, policy
    )
    original_eligible = original_v22_disposition in policy["original_eligible_dispositions"]
    never_resurrect = original_v22_disposition in policy["never_resurrect_dispositions"]
    if not original_eligible and not never_resurrect:
        raise ValueError(f"unknown original v2.2 disposition: {original_v22_disposition}")
    subtier = _subtier(biological_unit_state, functional_relation_state, positive, weak, policy)
    passes_tier_a_blocker_rule = original_eligible and not positive and not weak
    # Alpha4 constrains the frozen Tier-A pool; it does not promote historical
    # Tier-B candidates into Tier A.  Eligible Tier-B candidates retain their
    # diagnostic subtier and recall-tail acquisition path.
    tier_a_eligible = original_v22_disposition == "TIER_A" and passes_tier_a_blocker_rule
    reasons = []
    if positive:
        reasons.extend(positive)
    if weak:
        reasons.extend(weak)
    if uncertainty:
        reasons.extend(uncertainty)
    if original_v22_disposition == "TIER_A":
        reasons.append("TIER_A_ELIGIBILITY_NOT_BLOCKED" if tier_a_eligible
                       else "TIER_A_ELIGIBILITY_BLOCKED")
    elif original_v22_disposition == "TIER_B":
        reasons.append("ORIGINAL_TIER_B_RETAINED")
        reasons.append("TIER_A_BLOCKER_RULE_PASSED" if passes_tier_a_blocker_rule
                       else "TIER_A_BLOCKER_RULE_NOT_PASSED")
    if never_resurrect:
        disposition = ("ORIGINAL_REJECT_PRESERVED" if original_v22_disposition == "REJECT"
                       else "ORIGINAL_ABSTAIN_PRESERVED")
        reasons.append("ORIGINAL_V22_DISPOSITION_NOT_RESURRECTED")
        exposed_subtier = None
    else:
        disposition = subtier
        exposed_subtier = subtier

    policy_a = original_eligible
    policy_b = original_eligible
    policy_c = original_eligible and subtier in {
        "B1_SUPPORTED_OR_SINGLE_UNCERTAINTY", "B2_MULTI_UNRESOLVED"
    }
    eligibility = {
        "POLICY_A_MINIMAL": policy_a,
        "POLICY_B_CONSERVATIVE_PRIORITY": policy_b,
        "POLICY_C_STRICT_FULLTEXT_ELIGIBILITY": policy_c,
    }
    priorities = {
        "POLICY_A_MINIMAL": "HISTORICAL_ORDER_UNCHANGED",
        "POLICY_B_CONSERVATIVE_PRIORITY": "TIER_A_ELIGIBLE" if tier_a_eligible else subtier,
        "POLICY_C_STRICT_FULLTEXT_ELIGIBILITY": subtier if policy_c else "METADATA_ONLY_DIAGNOSTIC",
    }
    return CompositePreAcquisitionProfileV1(
        packet_or_candidate_id=packet_or_candidate_id, case_id=case_id,
        original_v22_disposition=original_v22_disposition,
        biological_unit_state=biological_unit_state,
        biological_unit_reason_codes=tuple(biological_unit_reason_codes),
        functional_relation_state=functional_relation_state,
        functional_relation_reason_codes=tuple(functional_relation_reason_codes),
        endpoint_state=endpoint_state, endpoint_reason_codes=tuple(endpoint_reason_codes),
        positive_incompatibility_flags=tuple(positive), relation_weak_flags=tuple(weak),
        uncertainty_flags=tuple(uncertainty), evidence_class=evidence_class,
        tier_b_subtier=exposed_subtier,
        passes_tier_a_blocker_rule_shadow=passes_tier_a_blocker_rule,
        tier_a_eligible_shadow=tier_a_eligible,
        alpha4_original_eligible=original_eligible,
        fulltext_eligibility_by_policy=eligibility,
        fulltext_priority_class_by_policy=priorities,
        composite_disposition=disposition, disposition_reason_codes=tuple(reasons),
        policy_version=policy["policy_version"],
        tier_b_policy_version=tier_b_policy["tier_b_policy_version"],
    )
