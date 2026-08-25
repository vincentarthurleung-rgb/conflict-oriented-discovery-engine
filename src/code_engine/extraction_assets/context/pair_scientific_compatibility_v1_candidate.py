"""Candidate scientific-role and compatibility boundary for pair comparison.

This additive module separates three questions that the V3 trigger sidecar did
not distinguish:

* whether two observations assert the same proposition (Alignment authority),
* whether non-identical designs or measurements are scientifically compatible,
* whether a resolved Context value is available for interpretation.

The implementation is deterministic and fail closed.  In particular, a raw
``different`` state satisfies only ``resolution_only`` Context.  It never
establishes proposition alignment or scientific compatibility.  The module
does not mutate or re-adjudicate historical Alignment, Candidate, L4a, or
Formal objects.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .pair_requirements_v2 import L4bUpstreamEligibilityV1
from .pair_requirements_v3_candidate import (
    PairSemanticTriggerCoverageV1,
    PairSemanticTriggerFactV1,
    SUPPORTED_FACT_AUTHORITIES,
)


SCIENTIFIC_COMPATIBILITY_CONTRACT_ID = "pair_scientific_compatibility_boundary_v1"
SCIENTIFIC_COMPATIBILITY_CONTRACT_PATH = (
    "docs/pair_scientific_compatibility_boundary_v1.md"
)

ScientificRole = Literal[
    "proposition_alignment_critical",
    "comparison_compatibility_critical",
    "context_explanatory",
    "explicitly_not_decision_relevant",
    "semantic_role_unresolved",
]
SatisfactionPolicy = Literal[
    "resolution_only",
    "compatibility_required",
    "upstream_alignment_required",
    "not_decision_relevant",
    "semantic_role_unresolved",
]
SemanticEvidenceState = Literal[
    "matched",
    "different",
    "compatible",
    "incompatible",
    "upstream_alignment_supported",
    "upstream_alignment_partial_but_reviewable",
    "alignment_semantic_coverage_gap",
    "unresolved",
    "ambiguous",
    "missing",
    "not_applicable",
]
SatisfactionState = Literal[
    "satisfied_resolved_matched",
    "satisfied_resolved_different",
    "satisfied_deterministically_compatible",
    "satisfied_upstream_alignment",
    "not_evaluated_not_decision_relevant",
    "unsatisfied_compatibility_unresolved",
    "unsatisfied_upstream_alignment_unresolved",
    "unsatisfied_semantic_role_unresolved",
    "unsatisfied_missing_structured_authority",
    "unsatisfied_ambiguous_source",
    "blocked_scientific_incompatibility",
]
AlignmentCompatibilityOutcome = Literal[
    "upstream_alignment_supported",
    "upstream_alignment_partial_but_reviewable",
    "alignment_semantic_coverage_gap",
    "measurement_compatibility_unresolved",
    "experimental_contrast_compatibility_unresolved",
    "scientifically_incompatible_under_current_contract",
]
ProjectionGapState = Literal[
    "repaired_by_deterministic_projection",
    "cannot_project_missing_structured_authority",
    "cannot_project_semantic_role_unresolved",
    "cannot_project_ambiguous_source",
    "not_required_after_role_audit",
]
L4bStateV4 = Literal[
    "comparable_all_required_context_resolved",
    "comparable_with_context_divergence",
    "reviewable_context_requirement_unresolved",
    "reviewable_scientific_compatibility_unresolved",
    "blocked_scientific_incompatibility",
    "blocked_upstream_alignment",
    "blocked_upstream_candidate_qualification",
    "blocked_upstream_entity_integrity",
]


ROLE_POLICY: dict[ScientificRole, SatisfactionPolicy] = {
    "proposition_alignment_critical": "upstream_alignment_required",
    "comparison_compatibility_critical": "compatibility_required",
    "context_explanatory": "resolution_only",
    "explicitly_not_decision_relevant": "not_decision_relevant",
    "semantic_role_unresolved": "semantic_role_unresolved",
}


def stable_scientific_v1(kind: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{kind}_{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


class StrictScientificModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScientificDimensionSatisfactionPolicyV1(StrictScientificModel):
    """One role-specific rule for when a semantic unit is satisfied."""

    schema_version: Literal[
        "scientific_dimension_satisfaction_policy_v1"
    ] = "scientific_dimension_satisfaction_policy_v1"
    policy: SatisfactionPolicy
    permitted_satisfying_states: list[SemanticEvidenceState] = Field(default_factory=list)
    l4b_authority_boundary: str = Field(min_length=1)
    different_is_sufficient: bool
    requires_deterministic_compatibility_authority: bool
    policy_identity: str

    @model_validator(mode="after")
    def policy_invariants(self):
        states = set(self.permitted_satisfying_states)
        if self.policy == "resolution_only":
            if states != {"matched", "different"} or not self.different_is_sufficient:
                raise ValueError("resolution_only_requires_matched_and_different")
        elif self.different_is_sufficient:
            raise ValueError("raw_difference_only_satisfies_resolution_only")
        if self.policy == "compatibility_required":
            if states != {"compatible"} or not self.requires_deterministic_compatibility_authority:
                raise ValueError("compatibility_policy_requires_compatible_authority")
        elif self.requires_deterministic_compatibility_authority:
            raise ValueError("compatibility_authority_flag_only_valid_for_compatibility_policy")
        if self.policy == "upstream_alignment_required" and states != {
            "upstream_alignment_supported"
        }:
            raise ValueError("upstream_policy_requires_supported_alignment")
        if self.policy in {"not_decision_relevant", "semantic_role_unresolved"} and states:
            raise ValueError("non_evaluated_policy_cannot_define_satisfying_evidence")
        return self


def make_satisfaction_policy_v1(
    *,
    policy: SatisfactionPolicy,
    permitted_satisfying_states: Sequence[SemanticEvidenceState],
    l4b_authority_boundary: str,
    different_is_sufficient: bool = False,
    requires_deterministic_compatibility_authority: bool = False,
) -> ScientificDimensionSatisfactionPolicyV1:
    payload = {
        "policy": policy,
        "permitted_satisfying_states": list(permitted_satisfying_states),
        "l4b_authority_boundary": l4b_authority_boundary,
        "different_is_sufficient": different_is_sufficient,
        "requires_deterministic_compatibility_authority": (
            requires_deterministic_compatibility_authority
        ),
    }
    return ScientificDimensionSatisfactionPolicyV1(
        **payload,
        policy_identity=stable_scientific_v1(
            "scientific_dimension_satisfaction_policy_v1", payload
        ),
    )


def default_satisfaction_policies_v1() -> tuple[
    ScientificDimensionSatisfactionPolicyV1, ...
]:
    return (
        make_satisfaction_policy_v1(
            policy="resolution_only",
            permitted_satisfying_states=("matched", "different"),
            l4b_authority_boundary=(
                "Resolved explanatory Context may be matched or different; neither state "
                "decides proposition identity or scientific compatibility."
            ),
            different_is_sufficient=True,
        ),
        make_satisfaction_policy_v1(
            policy="compatibility_required",
            permitted_satisfying_states=("compatible",),
            l4b_authority_boundary=(
                "L4b consumes a deterministic compatibility result and cannot derive it "
                "from raw equality, difference, or free text."
            ),
            requires_deterministic_compatibility_authority=True,
        ),
        make_satisfaction_policy_v1(
            policy="upstream_alignment_required",
            permitted_satisfying_states=("upstream_alignment_supported",),
            l4b_authority_boundary=(
                "Claim Alignment or Qualification owns proposition semantics; L4b may "
                "consume but never repair or re-adjudicate them."
            ),
        ),
        make_satisfaction_policy_v1(
            policy="not_decision_relevant",
            permitted_satisfying_states=(),
            l4b_authority_boundary=(
                "An explicit versioned contract makes the unit non-blocking."
            ),
        ),
        make_satisfaction_policy_v1(
            policy="semantic_role_unresolved",
            permitted_satisfying_states=(),
            l4b_authority_boundary=(
                "No positive comparability decision is permitted until the semantic role "
                "is established by a versioned contract."
            ),
        ),
    )


class ScientificSemanticRoleInventoryV1(StrictScientificModel):
    """Pair-scoped role assignment backed by structured contract authority."""

    schema_version: Literal[
        "scientific_semantic_role_inventory_v1"
    ] = "scientific_semantic_role_inventory_v1"
    pair_id: str = Field(min_length=1)
    dimension_or_semantic: str = Field(min_length=1)
    scientific_role: ScientificRole
    satisfaction_policy: SatisfactionPolicy
    authority: str = Field(min_length=1)
    authority_status: Literal[
        "supported", "partial", "alignment_semantic_coverage_gap", "unresolved"
    ]
    source_refs: list[str] = Field(min_length=1)
    structured_values_a: list[Any] = Field(default_factory=list)
    structured_values_b: list[Any] = Field(default_factory=list)
    semantic_state: SemanticEvidenceState
    reason: str = Field(min_length=1)
    inventory_identity: str

    @model_validator(mode="after")
    def role_policy_agree(self):
        if ROLE_POLICY[self.scientific_role] != self.satisfaction_policy:
            raise ValueError("scientific_role_policy_mismatch")
        if self.authority_status == "alignment_semantic_coverage_gap" and (
            self.satisfaction_policy != "upstream_alignment_required"
        ):
            raise ValueError("alignment_gap_must_remain_upstream_owned")
        return self


def make_semantic_role_inventory_v1(**payload: Any) -> ScientificSemanticRoleInventoryV1:
    identity_payload = dict(payload)
    identity_payload.pop("inventory_identity", None)
    return ScientificSemanticRoleInventoryV1(
        **identity_payload,
        inventory_identity=stable_scientific_v1(
            "scientific_semantic_role_inventory_v1", identity_payload
        ),
    )


class ScientificDimensionSatisfactionV1(StrictScientificModel):
    schema_version: Literal[
        "scientific_dimension_satisfaction_v1"
    ] = "scientific_dimension_satisfaction_v1"
    pair_id: str
    dimension_or_semantic: str
    scientific_role: ScientificRole
    satisfaction_policy: SatisfactionPolicy
    evidence_state: SemanticEvidenceState
    compatibility_authority_refs: list[str] = Field(default_factory=list)
    satisfaction_state: SatisfactionState
    satisfied: bool
    reason: str
    satisfaction_identity: str


def evaluate_scientific_dimension_satisfaction_v1(
    inventory: ScientificSemanticRoleInventoryV1,
    *,
    evidence_state: SemanticEvidenceState | None = None,
    compatibility_authority_refs: Sequence[str] = (),
) -> ScientificDimensionSatisfactionV1:
    """Apply the unit's policy without comparing or interpreting raw strings."""
    state = evidence_state or inventory.semantic_state
    refs = sorted(set(compatibility_authority_refs))
    policy = inventory.satisfaction_policy
    if policy == "not_decision_relevant":
        result: SatisfactionState = "not_evaluated_not_decision_relevant"
        satisfied = True
        reason = "explicit_contract_marks_unit_non_decision_relevant"
    elif policy == "semantic_role_unresolved":
        result = "unsatisfied_semantic_role_unresolved"
        satisfied = False
        reason = "semantic_role_requires_versioned_authority"
    elif state == "ambiguous":
        result = "unsatisfied_ambiguous_source"
        satisfied = False
        reason = "ambiguous_structured_source_cannot_satisfy_policy"
    elif state in {"missing", "unresolved", "not_applicable"}:
        result = "unsatisfied_missing_structured_authority"
        satisfied = False
        reason = "required_structured_authority_is_unavailable"
    elif policy == "resolution_only" and state == "matched":
        result = "satisfied_resolved_matched"
        satisfied = True
        reason = "explanatory_context_is_resolved_matched"
    elif policy == "resolution_only" and state == "different":
        result = "satisfied_resolved_different"
        satisfied = True
        reason = "explanatory_context_is_resolved_different"
    elif policy == "compatibility_required" and state == "compatible" and refs:
        result = "satisfied_deterministically_compatible"
        satisfied = True
        reason = "versioned_deterministic_compatibility_authority_is_present"
    elif policy == "compatibility_required" and state == "incompatible" and refs:
        result = "blocked_scientific_incompatibility"
        satisfied = False
        reason = "versioned_deterministic_authority_establishes_incompatibility"
    elif policy == "compatibility_required":
        result = "unsatisfied_compatibility_unresolved"
        satisfied = False
        reason = "raw_resolution_does_not_establish_scientific_compatibility"
    elif policy == "upstream_alignment_required" and (
        state == "upstream_alignment_supported"
    ):
        result = "satisfied_upstream_alignment"
        satisfied = True
        reason = "validated_upstream_alignment_semantics_are_consumed_read_only"
    elif policy == "upstream_alignment_required" and (
        state == "incompatible" and refs
    ):
        result = "blocked_scientific_incompatibility"
        satisfied = False
        reason = "upstream_authority_establishes_scientific_incompatibility"
    else:
        result = "unsatisfied_upstream_alignment_unresolved"
        satisfied = False
        reason = "l4b_cannot_repair_or_re_adjudicate_upstream_proposition_semantics"
    payload = {
        "pair_id": inventory.pair_id,
        "dimension_or_semantic": inventory.dimension_or_semantic,
        "scientific_role": inventory.scientific_role,
        "satisfaction_policy": policy,
        "evidence_state": state,
        "compatibility_authority_refs": refs,
        "satisfaction_state": result,
        "satisfied": satisfied,
        "reason": reason,
    }
    return ScientificDimensionSatisfactionV1(
        **payload,
        satisfaction_identity=stable_scientific_v1(
            "scientific_dimension_satisfaction_v1", payload
        ),
    )


class PairSemanticTriggerProjectionV1(StrictScientificModel):
    """Outcome of projecting one existing V3 gap from structured authority."""

    schema_version: Literal[
        "pair_semantic_trigger_projection_v1"
    ] = "pair_semantic_trigger_projection_v1"
    pair_id: str
    dimension: str
    before_coverage_state: str
    scientific_role: ScientificRole
    satisfaction_policy: SatisfactionPolicy
    gap_resolution_state: ProjectionGapState
    after_projection_state: Literal[
        "materialized_context_explanatory",
        "not_materialized",
        "not_required_for_l4b_projection",
    ]
    source_fact_ids: list[str] = Field(default_factory=list)
    projected_fact_state: Literal["matched", "different"] | None = None
    authority_refs: list[str] = Field(default_factory=list)
    reason: str
    free_text_inference_used: Literal[False] = False
    fuzzy_scientific_inference_used: Literal[False] = False
    llm_used: Literal[False] = False
    projection_identity: str

    @model_validator(mode="after")
    def projection_invariants(self):
        if self.gap_resolution_state == "repaired_by_deterministic_projection":
            if self.after_projection_state != "materialized_context_explanatory":
                raise ValueError("repaired_projection_requires_materialized_state")
            if self.scientific_role != "context_explanatory":
                raise ValueError("adapter_only_projects_explanatory_context")
            if not self.source_fact_ids or self.projected_fact_state is None:
                raise ValueError("repaired_projection_requires_structured_fact")
        elif self.projected_fact_state is not None:
            raise ValueError("unrepaired_projection_cannot_claim_projected_fact")
        return self


def project_pair_semantic_trigger_v1(
    *,
    coverage: PairSemanticTriggerCoverageV1,
    inventory: ScientificSemanticRoleInventoryV1,
    facts: Sequence[PairSemanticTriggerFactV1],
) -> PairSemanticTriggerProjectionV1:
    """Project resolved Context only; never manufacture compatibility authority."""
    if coverage.pair_id != inventory.pair_id or coverage.dimension != inventory.dimension_or_semantic:
        raise ValueError("projection_pair_dimension_mismatch")
    relevant = sorted(
        (
            fact
            for fact in facts
            if fact.pair_id == coverage.pair_id and fact.dimension == coverage.dimension
        ),
        key=lambda row: row.trigger_fact_id,
    )
    if inventory.scientific_role in {
        "proposition_alignment_critical",
        "explicitly_not_decision_relevant",
    }:
        gap_state: ProjectionGapState = "not_required_after_role_audit"
        after = "not_required_for_l4b_projection"
        projected = None
        used: list[PairSemanticTriggerFactV1] = []
        reason = "semantic_unit_is_owned_upstream_or_explicitly_non_decision_relevant"
    elif inventory.scientific_role == "semantic_role_unresolved":
        gap_state = "cannot_project_semantic_role_unresolved"
        after = "not_materialized"
        projected = None
        used = []
        reason = "semantic_role_contract_does_not_authorize_projection"
    elif any(fact.fact_state == "ambiguous" for fact in relevant):
        gap_state = "cannot_project_ambiguous_source"
        after = "not_materialized"
        projected = None
        used = []
        reason = "ambiguous_structured_fact_cannot_be_projected"
    elif inventory.scientific_role == "comparison_compatibility_critical":
        gap_state = "cannot_project_missing_structured_authority"
        after = "not_materialized"
        projected = None
        used = []
        reason = "raw_structured_values_do_not_establish_compatibility"
    else:
        supported = [
            fact
            for fact in relevant
            if fact.fact_state in {"matched", "different"}
            and fact.authority in SUPPORTED_FACT_AUTHORITIES
            and fact.side_a_object_refs
            and fact.side_b_object_refs
            and fact.structured_values_a
            and fact.structured_values_b
        ]
        if supported:
            gap_state = "repaired_by_deterministic_projection"
            after = "materialized_context_explanatory"
            projected = (
                "matched"
                if all(fact.fact_state == "matched" for fact in supported)
                else "different"
            )
            used = supported
            reason = "validated_two_sided_context_fact_projected_without_semantic_inference"
        else:
            gap_state = "cannot_project_missing_structured_authority"
            after = "not_materialized"
            projected = None
            used = []
            reason = "two_sided_validated_context_authority_is_unavailable"
    payload = {
        "pair_id": coverage.pair_id,
        "dimension": coverage.dimension,
        "before_coverage_state": coverage.coverage_state,
        "scientific_role": inventory.scientific_role,
        "satisfaction_policy": inventory.satisfaction_policy,
        "gap_resolution_state": gap_state,
        "after_projection_state": after,
        "source_fact_ids": [row.trigger_fact_id for row in used],
        "projected_fact_state": projected,
        "authority_refs": sorted({ref for row in used for ref in row.source_artifact_refs}),
        "reason": reason,
    }
    return PairSemanticTriggerProjectionV1(
        **payload,
        projection_identity=stable_scientific_v1(
            "pair_semantic_trigger_projection_v1", payload
        ),
    )


class L4bComparabilityResultV4Candidate(StrictScientificModel):
    schema_version: Literal[
        "l4b_comparability_result_v4_candidate"
    ] = "l4b_comparability_result_v4_candidate"
    pair_id: str
    semantics_contract_id: Literal[
        "pair_scientific_compatibility_boundary_v1"
    ] = SCIENTIFIC_COMPATIBILITY_CONTRACT_ID
    upstream_eligibility: L4bUpstreamEligibilityV1
    upstream_alignment_compatibility_outcome: AlignmentCompatibilityOutcome
    proposition_critical_semantics: list[str]
    compatibility_critical_semantics: list[str]
    context_explanatory_semantics: list[str]
    unresolved_semantic_roles: list[str]
    satisfied_semantics: list[str]
    unresolved_compatibility_semantics: list[str]
    unresolved_context_semantics: list[str]
    incompatible_semantics: list[str]
    different_explanatory_context: list[str]
    l4b_state: L4bStateV4
    comparable: bool | None
    authoritative_l4b_result: bool
    candidate_only: Literal[True] = True
    upstream_alignment_re_adjudicated: Literal[False] = False
    scientific_compatibility_inferred_from_difference: Literal[False] = False
    formal_conflict_generated: Literal[False] = False
    historical_objects_modified: Literal[False] = False
    result_identity: str


def evaluate_l4b_v4_candidate(
    *,
    pair_id: str,
    upstream: L4bUpstreamEligibilityV1,
    upstream_alignment_compatibility_outcome: AlignmentCompatibilityOutcome,
    satisfactions: Sequence[ScientificDimensionSatisfactionV1],
) -> L4bComparabilityResultV4Candidate:
    """Consume upstream/compatibility decisions; do not derive them in L4b."""
    if upstream.pair_id != pair_id:
        raise ValueError("l4b_v4_upstream_pair_identity_mismatch")
    rows = [row for row in satisfactions if row.pair_id == pair_id]
    names = [row.dimension_or_semantic for row in rows]
    if len(names) != len(set(names)):
        raise ValueError("duplicate_l4b_v4_semantic_satisfaction")
    proposition = sorted(
        row.dimension_or_semantic
        for row in rows
        if row.scientific_role == "proposition_alignment_critical"
    )
    compatibility = sorted(
        row.dimension_or_semantic
        for row in rows
        if row.scientific_role == "comparison_compatibility_critical"
    )
    context = sorted(
        row.dimension_or_semantic
        for row in rows
        if row.scientific_role == "context_explanatory"
    )
    unresolved_roles = sorted(
        row.dimension_or_semantic
        for row in rows
        if row.scientific_role == "semantic_role_unresolved"
    )
    unresolved_compatibility = sorted(
        row.dimension_or_semantic
        for row in rows
        if row.satisfaction_state in {
            "unsatisfied_compatibility_unresolved",
            "unsatisfied_upstream_alignment_unresolved",
        }
    )
    unresolved_context = sorted(
        row.dimension_or_semantic
        for row in rows
        if row.scientific_role == "context_explanatory" and not row.satisfied
    )
    incompatible = sorted(
        row.dimension_or_semantic
        for row in rows
        if row.satisfaction_state == "blocked_scientific_incompatibility"
    )
    different_context = sorted(
        row.dimension_or_semantic
        for row in rows
        if row.scientific_role == "context_explanatory"
        and row.satisfaction_state == "satisfied_resolved_different"
    )
    if not upstream.entity_integrity_eligible:
        state: L4bStateV4 = "blocked_upstream_entity_integrity"
        comparable: bool | None = None
        authoritative = False
    elif not upstream.alignment_eligible:
        state = "blocked_upstream_alignment"
        comparable = None
        authoritative = False
    elif not upstream.contradiction_signal_valid or not upstream.candidate_qualification_eligible:
        state = "blocked_upstream_candidate_qualification"
        comparable = None
        authoritative = False
    elif (
        upstream_alignment_compatibility_outcome
        == "scientifically_incompatible_under_current_contract"
        or incompatible
    ):
        state = "blocked_scientific_incompatibility"
        comparable = False
        authoritative = True
    elif upstream_alignment_compatibility_outcome != "upstream_alignment_supported":
        state = "reviewable_scientific_compatibility_unresolved"
        comparable = None
        authoritative = False
    elif unresolved_compatibility:
        state = "reviewable_scientific_compatibility_unresolved"
        comparable = None
        authoritative = False
    elif unresolved_roles or unresolved_context:
        state = "reviewable_context_requirement_unresolved"
        comparable = None
        authoritative = False
    elif different_context:
        state = "comparable_with_context_divergence"
        comparable = True
        authoritative = True
    else:
        state = "comparable_all_required_context_resolved"
        comparable = True
        authoritative = True
    payload = {
        "pair_id": pair_id,
        "upstream": upstream.model_dump(mode="json"),
        "upstream_alignment_compatibility_outcome": (
            upstream_alignment_compatibility_outcome
        ),
        "satisfaction_ids": sorted(row.satisfaction_identity for row in rows),
        "l4b_state": state,
    }
    return L4bComparabilityResultV4Candidate(
        pair_id=pair_id,
        upstream_eligibility=upstream,
        upstream_alignment_compatibility_outcome=(
            upstream_alignment_compatibility_outcome
        ),
        proposition_critical_semantics=proposition,
        compatibility_critical_semantics=compatibility,
        context_explanatory_semantics=context,
        unresolved_semantic_roles=unresolved_roles,
        satisfied_semantics=sorted(
            row.dimension_or_semantic for row in rows if row.satisfied
        ),
        unresolved_compatibility_semantics=unresolved_compatibility,
        unresolved_context_semantics=unresolved_context,
        incompatible_semantics=incompatible,
        different_explanatory_context=different_context,
        l4b_state=state,
        comparable=comparable,
        authoritative_l4b_result=authoritative,
        result_identity=stable_scientific_v1(
            "l4b_comparability_result_v4_candidate", payload
        ),
    )


__all__ = [
    "SCIENTIFIC_COMPATIBILITY_CONTRACT_ID",
    "SCIENTIFIC_COMPATIBILITY_CONTRACT_PATH",
    "ScientificDimensionSatisfactionPolicyV1",
    "ScientificSemanticRoleInventoryV1",
    "ScientificDimensionSatisfactionV1",
    "PairSemanticTriggerProjectionV1",
    "L4bComparabilityResultV4Candidate",
    "default_satisfaction_policies_v1",
    "make_semantic_role_inventory_v1",
    "evaluate_scientific_dimension_satisfaction_v1",
    "project_pair_semantic_trigger_v1",
    "evaluate_l4b_v4_candidate",
    "stable_scientific_v1",
]
