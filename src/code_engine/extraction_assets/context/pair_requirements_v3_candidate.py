"""Candidate semantic-trigger authority audit for pair Context requirements.

This module is additive to :mod:`pair_requirements_v2`.  It implements the
candidate contract requested by the Pair Semantic Trigger Coverage audit:

* absence of a trigger fact is epistemic uncertainty, not irrelevance;
* irrelevance and structural inapplicability require affirmative authority;
* a semantic fact is separate from the consumer rule that makes it eligible;
* requirement satisfaction is evaluated only for ``comparison_required``;
* ``matched`` and ``different`` are both resolved states.

The frozen scientific definition remains in
``docs/l4b_pair_comparability_semantics_v1.md``.  Nothing in this candidate
sidecar modifies L4a, historical Candidate objects, or Formal Judgments.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .pair_requirements_v2 import (
    ContextDimension,
    L4bUpstreamEligibilityV1,
    SEMANTICS_CONTRACT_ID,
)


CONTEXT_DIMENSIONS: tuple[ContextDimension, ...] = (
    "biological_model",
    "intervention",
    "temporal",
    "genotype",
    "localization",
    "measurement",
    "disease",
    "experimental_design",
)

FactType = Literal[
    "proposition_scope",
    "experimental_factor_scope",
    "arm_contrast",
    "intervention_contrast",
    "genotype_scope",
    "temporal_scope",
    "localization_scope",
    "population_scope",
    "measurement_scope",
    "result_scope",
    "experimental_design_scope",
    "source_grounded_context_difference",
]
FactState = Literal[
    "matched",
    "different",
    "resolved_pair",
    "side_a_only",
    "side_b_only",
    "unresolved",
    "ambiguous",
    "not_applicable",
]
TriggerAuthority = Literal[
    "validated_experimental_core",
    "validated_claim_core",
    "validated_context_direct_value",
    "safe_scope_context_inheritance",
    "authorized_deterministic_derived_value",
    "validated_l4a_difference",
    "validated_experimental_design_linkage",
    "explicit_consumer_contract",
    "structural_inapplicability_rule",
    "unsupported",
]
TriggerType = Literal["comparison_required", "divergence_explanatory"]
CoverageState = Literal[
    "fully_materialized",
    "partially_materialized",
    "present_upstream_but_not_materialized",
    "absent_from_current_structured_assets",
    "ambiguous_structured_evidence",
    "not_applicable_with_authority",
]
ActivationState = Literal[
    "comparison_required",
    "divergence_explanatory",
    "explicit_not_decision_relevant",
    "not_applicable",
    "requirement_unresolved",
]
DimensionStateV3 = Literal[
    "matched",
    "different",
    "unresolved",
    "ambiguous",
    "source_scope_insufficient",
    "not_applicable",
]
SatisfactionStatusV3 = Literal[
    "satisfied_resolved_matched",
    "satisfied_resolved_different",
    "unsatisfied_unresolved",
    "unsatisfied_ambiguous",
    "unsatisfied_source_scope",
    "not_evaluated_not_activated",
    "not_evaluated_upstream_blocked",
]
L4bStateV3 = Literal[
    "comparable_all_required_context_resolved",
    "comparable_with_context_divergence",
    "comparable_no_context_sensitive_requirement",
    "reviewable_requirement_semantics_unresolved",
    "reviewable_required_context_gap",
    "blocked_required_context_ambiguous",
    "blocked_source_scope",
    "blocked_upstream_alignment",
    "blocked_upstream_candidate_qualification",
    "blocked_upstream_entity_integrity",
]

SUPPORTED_FACT_AUTHORITIES = {
    "validated_experimental_core",
    "validated_claim_core",
    "validated_context_direct_value",
    "safe_scope_context_inheritance",
    "authorized_deterministic_derived_value",
    "validated_l4a_difference",
    "validated_experimental_design_linkage",
}
RESOLVED_FACT_STATES = {"matched", "different", "resolved_pair"}


def stable_v3(kind: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{kind}_{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


class StrictCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PairSemanticTriggerFactV1(StrictCandidateModel):
    """Pair-scoped semantic fact projected only from structured authority."""

    schema_version: Literal[
        "pair_semantic_trigger_fact_v1"
    ] = "pair_semantic_trigger_fact_v1"
    trigger_fact_id: str = Field(min_length=1)
    pair_id: str = Field(min_length=1)
    dimension: ContextDimension
    fact_type: FactType
    side_a_object_refs: list[str] = Field(default_factory=list)
    side_b_object_refs: list[str] = Field(default_factory=list)
    source_artifact_refs: list[str] = Field(default_factory=list)
    fact_state: FactState
    authority: TriggerAuthority
    trigger_eligible: bool
    trigger_type: TriggerType | None = None
    structured_values_a: list[Any] = Field(default_factory=list)
    structured_values_b: list[Any] = Field(default_factory=list)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def authority_contract(self):
        if self.trigger_eligible:
            if self.authority not in SUPPORTED_FACT_AUTHORITIES:
                raise ValueError("trigger_eligible_fact_requires_supported_authority")
            if self.trigger_type is None:
                raise ValueError("trigger_eligible_fact_requires_trigger_type")
            if self.fact_state not in RESOLVED_FACT_STATES:
                raise ValueError("trigger_eligible_fact_requires_resolved_pair_semantics")
            if not self.side_a_object_refs or not self.side_b_object_refs:
                raise ValueError("trigger_eligible_fact_requires_two_sided_objects")
            if not self.source_artifact_refs:
                raise ValueError("trigger_eligible_fact_requires_source_artifact")
        elif self.trigger_type is not None:
            raise ValueError("ineligible_fact_cannot_preselect_trigger_type")
        if (
            self.trigger_type == "divergence_explanatory"
            and (
                self.fact_type != "source_grounded_context_difference"
                or self.fact_state != "different"
                or self.authority != "validated_l4a_difference"
            )
        ):
            raise ValueError("explanatory_trigger_requires_validated_l4a_difference")
        return self


def make_trigger_fact_v1(**payload: Any) -> PairSemanticTriggerFactV1:
    identity_payload = dict(payload)
    identity_payload.pop("trigger_fact_id", None)
    return PairSemanticTriggerFactV1(
        **identity_payload,
        trigger_fact_id=stable_v3("pair_semantic_trigger_fact_v1", identity_payload),
    )


class PairRequirementAuthorityV1(StrictCandidateModel):
    """Affirmative contract authority for a non-trigger activation state."""

    schema_version: Literal[
        "pair_requirement_authority_v1"
    ] = "pair_requirement_authority_v1"
    pair_id: str
    consumer: str
    dimension: ContextDimension
    authority_state: Literal["explicit_not_decision_relevant", "not_applicable"]
    authority: Literal["explicit_consumer_contract", "structural_inapplicability_rule"]
    contract_refs: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)
    authority_id: str

    @model_validator(mode="after")
    def authority_matches_state(self):
        if (
            self.authority_state == "explicit_not_decision_relevant"
            and self.authority != "explicit_consumer_contract"
        ):
            raise ValueError("irrelevance_requires_explicit_consumer_contract")
        if (
            self.authority_state == "not_applicable"
            and self.authority != "structural_inapplicability_rule"
        ):
            raise ValueError("not_applicable_requires_structural_rule")
        return self


def make_requirement_authority_v1(**payload: Any) -> PairRequirementAuthorityV1:
    identity_payload = dict(payload)
    identity_payload.pop("authority_id", None)
    return PairRequirementAuthorityV1(
        **identity_payload,
        authority_id=stable_v3("pair_requirement_authority_v1", identity_payload),
    )


class PairSemanticTriggerCoverageV1(StrictCandidateModel):
    schema_version: Literal[
        "pair_semantic_trigger_coverage_v1"
    ] = "pair_semantic_trigger_coverage_v1"
    pair_id: str
    dimension: ContextDimension
    coverage_state: CoverageState
    trigger_fact_ids: list[str] = Field(default_factory=list)
    upstream_object_refs: list[str] = Field(default_factory=list)
    authority_refs: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    coverage_id: str


class UpstreamTriggerProjectionGapV1(StrictCandidateModel):
    schema_version: Literal[
        "upstream_trigger_projection_gap_v1"
    ] = "upstream_trigger_projection_gap_v1"
    pair_id: str
    dimension: ContextDimension
    upstream_object: str
    available_fact: str
    missing_adapter_or_projection: str
    downstream_requirement_consumer: str
    resolved_in_v3_candidate_sidecar: bool
    gap_id: str


def make_projection_gap_v1(**payload: Any) -> UpstreamTriggerProjectionGapV1:
    identity_payload = dict(payload)
    identity_payload.pop("gap_id", None)
    return UpstreamTriggerProjectionGapV1(
        **identity_payload,
        gap_id=stable_v3("upstream_trigger_projection_gap_v1", identity_payload),
    )


def audit_trigger_coverage_v1(
    *,
    pair_id: str,
    dimension: ContextDimension,
    facts: Sequence[PairSemanticTriggerFactV1],
    upstream_object_refs: Sequence[str] = (),
    authorities: Sequence[PairRequirementAuthorityV1] = (),
) -> PairSemanticTriggerCoverageV1:
    """Classify one pair/dimension without collapsing missingness states."""
    relevant = [
        fact for fact in facts if fact.pair_id == pair_id and fact.dimension == dimension
    ]
    relevant_authorities = [
        row for row in authorities if row.pair_id == pair_id and row.dimension == dimension
    ]
    if any(row.authority_state == "not_applicable" for row in relevant_authorities):
        state: CoverageState = "not_applicable_with_authority"
        reason = "structural_inapplicability_is_affirmatively_authorized"
    elif any(fact.fact_state == "ambiguous" for fact in relevant):
        state = "ambiguous_structured_evidence"
        reason = "structured_pair_semantics_are_ambiguous"
    elif any(
        fact.trigger_eligible and fact.fact_state in RESOLVED_FACT_STATES
        for fact in relevant
    ):
        state = "fully_materialized"
        reason = "supported_two_sided_semantic_fact_has_consumer_trigger_projection"
    elif any(
        fact.trigger_eligible
        or fact.fact_state in {"side_a_only", "side_b_only", "unresolved"}
        for fact in relevant
    ):
        state = "partially_materialized"
        reason = "semantic_trigger_information_is_present_but_incomplete"
    elif relevant or upstream_object_refs:
        state = "present_upstream_but_not_materialized"
        reason = "structured_semantics_exist_without_an_eligible_requirement_projection"
    else:
        state = "absent_from_current_structured_assets"
        reason = "no_supported_structured_semantic_fact_or_explicit_authority_is_available"

    payload = {
        "pair_id": pair_id,
        "dimension": dimension,
        "coverage_state": state,
        "trigger_fact_ids": sorted(f.trigger_fact_id for f in relevant),
        "upstream_object_refs": sorted(set(upstream_object_refs)),
        "authority_refs": sorted(row.authority_id for row in relevant_authorities),
        "reason": reason,
    }
    return PairSemanticTriggerCoverageV1(
        **payload,
        coverage_id=stable_v3("pair_semantic_trigger_coverage_v1", payload),
    )


class PairContextRequirementActivationV3Candidate(StrictCandidateModel):
    schema_version: Literal[
        "pair_context_requirement_activation_v3_candidate"
    ] = "pair_context_requirement_activation_v3_candidate"
    pair_id: str
    consumer: str
    consumer_version: Literal["v3_candidate"] = "v3_candidate"
    dimension: ContextDimension
    activation_state: ActivationState
    trigger_fact_ids: list[str] = Field(default_factory=list)
    trigger_type: TriggerType | Literal[
        "explicit_consumer_contract", "structural_inapplicability_rule", "none"
    ]
    authority: list[TriggerAuthority] = Field(default_factory=list)
    authority_refs: list[str] = Field(default_factory=list)
    blocking_semantics: Literal[
        "requires_resolution",
        "explanatory_candidate_only",
        "affirmatively_nonblocking",
        "blocks_no_requirement_comparability",
    ]
    reason: str = Field(min_length=1)
    requirement_identity: str
    candidate_only: Literal[True] = True
    missingness_created_relevance: Literal[False] = False
    llm_output_created_relevance: Literal[False] = False

    @model_validator(mode="after")
    def activation_contract(self):
        if self.activation_state == "requirement_unresolved":
            if self.blocking_semantics != "blocks_no_requirement_comparability":
                raise ValueError("unresolved_requirement_semantics_must_block_no_requirement_state")
        if self.activation_state == "comparison_required":
            if not self.trigger_fact_ids or self.trigger_type != "comparison_required":
                raise ValueError("comparison_requirement_requires_supported_trigger")
        if self.activation_state == "divergence_explanatory":
            if not self.trigger_fact_ids or self.trigger_type != "divergence_explanatory":
                raise ValueError("explanatory_role_requires_supported_difference_trigger")
        if self.activation_state == "explicit_not_decision_relevant":
            if self.trigger_type != "explicit_consumer_contract" or not self.authority_refs:
                raise ValueError("explicit_irrelevance_requires_contract_authority")
        if self.activation_state == "not_applicable":
            if self.trigger_type != "structural_inapplicability_rule" or not self.authority_refs:
                raise ValueError("not_applicable_requires_structural_authority")
        return self


def activate_pair_dimension_v3_candidate(
    *,
    pair_id: str,
    consumer: str,
    dimension: ContextDimension,
    trigger_facts: Sequence[PairSemanticTriggerFactV1],
    requirement_authorities: Sequence[PairRequirementAuthorityV1] = (),
    consumer_eligible_trigger_fact_ids: Sequence[str] | None = None,
) -> PairContextRequirementActivationV3Candidate:
    """Activate from positive authority; fact absence defaults to unresolved."""
    facts = [
        fact
        for fact in trigger_facts
        if fact.pair_id == pair_id and fact.dimension == dimension
    ]
    authorities = [
        row
        for row in requirement_authorities
        if row.pair_id == pair_id
        and row.consumer == consumer
        and row.dimension == dimension
    ]
    authority_states = {row.authority_state for row in authorities}
    if len(authority_states) > 1:
        state: ActivationState = "requirement_unresolved"
        trigger_type: Any = "none"
        blocking = "blocks_no_requirement_comparability"
        reason = "conflicting_affirmative_requirement_authorities"
        used_facts: list[PairSemanticTriggerFactV1] = []
    elif authority_states == {"not_applicable"}:
        state = "not_applicable"
        trigger_type = "structural_inapplicability_rule"
        blocking = "affirmatively_nonblocking"
        reason = "dimension_is_structurally_inapplicable_with_authority"
        used_facts = []
    elif authority_states == {"explicit_not_decision_relevant"}:
        state = "explicit_not_decision_relevant"
        trigger_type = "explicit_consumer_contract"
        blocking = "affirmatively_nonblocking"
        reason = "consumer_contract_affirmatively_proves_dimension_irrelevance"
        used_facts = []
    else:
        permitted_ids = (
            None
            if consumer_eligible_trigger_fact_ids is None
            else set(consumer_eligible_trigger_fact_ids)
        )
        eligible = [
            fact
            for fact in facts
            if fact.trigger_eligible
            and (permitted_ids is None or fact.trigger_fact_id in permitted_ids)
        ]
        comparison = [fact for fact in eligible if fact.trigger_type == "comparison_required"]
        explanatory = [
            fact for fact in eligible if fact.trigger_type == "divergence_explanatory"
        ]
        if comparison:
            state = "comparison_required"
            trigger_type = "comparison_required"
            blocking = "requires_resolution"
            reason = "validated_pair_semantics_require_resolution_for_safe_interpretation"
            used_facts = comparison
        elif explanatory:
            state = "divergence_explanatory"
            trigger_type = "divergence_explanatory"
            blocking = "explanatory_candidate_only"
            reason = "validated_source_grounded_difference_is_permitted_as_candidate_only"
            used_facts = explanatory
        else:
            state = "requirement_unresolved"
            trigger_type = "none"
            blocking = "blocks_no_requirement_comparability"
            used_facts = facts
            reason = (
                "available_structured_facts_do_not_establish_consumer_relevance"
                if facts
                else "absence_of_trigger_evidence_defaults_to_requirement_unresolved"
            )

    payload = {
        "pair_id": pair_id,
        "consumer": consumer,
        "consumer_version": "v3_candidate",
        "dimension": dimension,
        "activation_state": state,
        "trigger_fact_ids": sorted(f.trigger_fact_id for f in used_facts),
        "trigger_type": trigger_type,
        "authority": sorted(
            {f.authority for f in used_facts} | {row.authority for row in authorities}
        ),
        "authority_refs": sorted(row.authority_id for row in authorities),
        "blocking_semantics": blocking,
        "reason": reason,
    }
    return PairContextRequirementActivationV3Candidate(
        **payload,
        requirement_identity=stable_v3("pair_context_requirement_v3_candidate", payload),
    )


class PairContextDimensionEvidenceV3Candidate(StrictCandidateModel):
    schema_version: Literal[
        "pair_context_dimension_evidence_v3_candidate"
    ] = "pair_context_dimension_evidence_v3_candidate"
    pair_id: str
    dimension: ContextDimension
    dimension_state: DimensionStateV3
    value_a: Any = None
    value_b: Any = None
    side_a_object_refs: list[str] = Field(default_factory=list)
    side_b_object_refs: list[str] = Field(default_factory=list)
    authority: list[TriggerAuthority] = Field(default_factory=list)
    authoritative_two_sided_support: bool
    evidence_identity: str

    @model_validator(mode="after")
    def evidence_contract(self):
        if self.dimension_state in {"matched", "different"}:
            if not self.authoritative_two_sided_support:
                raise ValueError("resolved_dimension_requires_authoritative_two_sided_support")
            if self.value_a is None or self.value_b is None:
                raise ValueError("resolved_dimension_requires_two_values")
            if not self.side_a_object_refs or not self.side_b_object_refs:
                raise ValueError("resolved_dimension_requires_two_sided_objects")
            if self.dimension_state == "matched" and self.value_a != self.value_b:
                raise ValueError("matched_values_must_be_equal")
            if self.dimension_state == "different" and self.value_a == self.value_b:
                raise ValueError("different_values_must_differ")
        return self


def evidence_from_trigger_fact_v3_candidate(
    fact: PairSemanticTriggerFactV1,
) -> PairContextDimensionEvidenceV3Candidate:
    if fact.fact_state not in {"matched", "different"}:
        state: DimensionStateV3 = (
            "ambiguous" if fact.fact_state == "ambiguous" else "unresolved"
        )
        value_a = value_b = None
        supported = False
    else:
        state = fact.fact_state
        value_a = fact.structured_values_a
        value_b = fact.structured_values_b
        supported = (
            fact.authority in SUPPORTED_FACT_AUTHORITIES
            and bool(fact.side_a_object_refs)
            and bool(fact.side_b_object_refs)
        )
    payload = {
        "pair_id": fact.pair_id,
        "dimension": fact.dimension,
        "dimension_state": state,
        "value_a": value_a,
        "value_b": value_b,
        "side_a_object_refs": fact.side_a_object_refs,
        "side_b_object_refs": fact.side_b_object_refs,
        "authority": [fact.authority],
        "authoritative_two_sided_support": supported,
    }
    return PairContextDimensionEvidenceV3Candidate(
        **payload,
        evidence_identity=stable_v3("pair_context_dimension_evidence_v3_candidate", payload),
    )


class PairContextRequirementSatisfactionV3Candidate(StrictCandidateModel):
    schema_version: Literal[
        "pair_context_requirement_satisfaction_v3_candidate"
    ] = "pair_context_requirement_satisfaction_v3_candidate"
    pair_id: str
    consumer: str
    dimension: ContextDimension
    requirement_identity: str
    activation_state: ActivationState
    dimension_state: DimensionStateV3
    resolved_for_comparison: bool
    satisfaction_status: SatisfactionStatusV3
    evidence_identity: str | None = None
    candidate_only: Literal[True] = True


def satisfaction_for_pair_v3_candidate(
    activation: PairContextRequirementActivationV3Candidate,
    evidence: PairContextDimensionEvidenceV3Candidate | None,
    *,
    upstream_blocked: bool = False,
) -> PairContextRequirementSatisfactionV3Candidate:
    state: DimensionStateV3 = evidence.dimension_state if evidence else "unresolved"
    if upstream_blocked:
        status: SatisfactionStatusV3 = "not_evaluated_upstream_blocked"
        resolved = False
    elif activation.activation_state != "comparison_required":
        status = "not_evaluated_not_activated"
        resolved = False
    elif evidence and evidence.authoritative_two_sided_support and state == "matched":
        status = "satisfied_resolved_matched"
        resolved = True
    elif evidence and evidence.authoritative_two_sided_support and state == "different":
        status = "satisfied_resolved_different"
        resolved = True
    elif state == "ambiguous":
        status = "unsatisfied_ambiguous"
        resolved = False
    elif state == "source_scope_insufficient":
        status = "unsatisfied_source_scope"
        resolved = False
    else:
        status = "unsatisfied_unresolved"
        resolved = False
    return PairContextRequirementSatisfactionV3Candidate(
        pair_id=activation.pair_id,
        consumer=activation.consumer,
        dimension=activation.dimension,
        requirement_identity=activation.requirement_identity,
        activation_state=activation.activation_state,
        dimension_state=state,
        resolved_for_comparison=resolved,
        satisfaction_status=status,
        evidence_identity=evidence.evidence_identity if evidence else None,
    )


class L4bComparabilityResultV3Candidate(StrictCandidateModel):
    schema_version: Literal[
        "l4b_comparability_result_v3_candidate"
    ] = "l4b_comparability_result_v3_candidate"
    pair_id: str
    semantics_contract_id: Literal[
        "l4b_pair_comparability_semantics_v1"
    ] = SEMANTICS_CONTRACT_ID
    upstream_eligibility: L4bUpstreamEligibilityV1
    comparison_required_dimensions: list[ContextDimension]
    divergence_explanatory_dimensions: list[ContextDimension]
    explicit_not_decision_relevant_dimensions: list[ContextDimension]
    not_applicable_dimensions: list[ContextDimension]
    requirement_unresolved_dimensions: list[ContextDimension]
    matched_required_dimensions: list[ContextDimension]
    different_required_dimensions: list[ContextDimension]
    unresolved_required_dimensions: list[ContextDimension]
    ambiguous_required_dimensions: list[ContextDimension]
    source_scope_blockers: list[ContextDimension]
    l4b_state: L4bStateV3
    comparable: bool | None
    authoritative_l4b_result: bool
    candidate_only: Literal[True] = True
    divergence_explanation_decided: Literal[False] = False
    formal_conflict_generated: Literal[False] = False
    historical_objects_modified: Literal[False] = False
    result_identity: str


def _upstream_block_state_v3(upstream: L4bUpstreamEligibilityV1) -> L4bStateV3 | None:
    if not upstream.entity_integrity_eligible:
        return "blocked_upstream_entity_integrity"
    if not upstream.alignment_eligible:
        return "blocked_upstream_alignment"
    if not upstream.contradiction_signal_valid or not upstream.candidate_qualification_eligible:
        return "blocked_upstream_candidate_qualification"
    return None


def evaluate_l4b_v3_candidate(
    *,
    pair_id: str,
    upstream: L4bUpstreamEligibilityV1,
    activations: Sequence[PairContextRequirementActivationV3Candidate],
    dimension_evidence: Sequence[PairContextDimensionEvidenceV3Candidate],
    expected_dimensions: Sequence[ContextDimension] = CONTEXT_DIMENSIONS,
    consumer: str = "l4b_comparability",
) -> tuple[
    L4bComparabilityResultV3Candidate,
    list[PairContextRequirementSatisfactionV3Candidate],
]:
    """Evaluate the candidate state without using unresolved semantics as no-op."""
    if upstream.pair_id != pair_id:
        raise ValueError("l4b_upstream_pair_identity_mismatch")
    rows = [
        row for row in activations if row.pair_id == pair_id and row.consumer == consumer
    ]
    dimensions = [row.dimension for row in rows]
    if len(dimensions) != len(set(dimensions)):
        raise ValueError("duplicate_l4b_v3_dimension_activation")
    if set(dimensions) != set(expected_dimensions):
        raise ValueError("incomplete_l4b_v3_dimension_activation")
    evidence_by_dimension = {
        row.dimension: row for row in dimension_evidence if row.pair_id == pair_id
    }
    required = [row for row in rows if row.activation_state == "comparison_required"]
    explanatory = [
        row for row in rows if row.activation_state == "divergence_explanatory"
    ]
    irrelevant = [
        row
        for row in rows
        if row.activation_state == "explicit_not_decision_relevant"
    ]
    inapplicable = [row for row in rows if row.activation_state == "not_applicable"]
    unresolved_roles = [
        row for row in rows if row.activation_state == "requirement_unresolved"
    ]
    block_state = _upstream_block_state_v3(upstream)
    satisfactions = [
        satisfaction_for_pair_v3_candidate(
            row,
            evidence_by_dimension.get(row.dimension),
            upstream_blocked=block_state is not None,
        )
        for row in rows
    ]
    required_satisfaction = [
        row for row in satisfactions if row.activation_state == "comparison_required"
    ]
    matched = [
        row.dimension
        for row in required_satisfaction
        if row.satisfaction_status == "satisfied_resolved_matched"
    ]
    different = [
        row.dimension
        for row in required_satisfaction
        if row.satisfaction_status == "satisfied_resolved_different"
    ]
    source_blockers = [
        row.dimension
        for row in required_satisfaction
        if row.satisfaction_status == "unsatisfied_source_scope"
    ]
    ambiguous = [
        row.dimension
        for row in required_satisfaction
        if row.satisfaction_status == "unsatisfied_ambiguous"
    ]
    unresolved_required = [
        row.dimension
        for row in required_satisfaction
        if row.satisfaction_status == "unsatisfied_unresolved"
    ]

    if block_state:
        state = block_state
        comparable: bool | None = None
        authoritative = False
    elif unresolved_roles:
        state = "reviewable_requirement_semantics_unresolved"
        comparable = None
        authoritative = False
    elif source_blockers:
        state = "blocked_source_scope"
        comparable = False
        authoritative = True
    elif ambiguous:
        state = "blocked_required_context_ambiguous"
        comparable = False
        authoritative = True
    elif unresolved_required:
        state = "reviewable_required_context_gap"
        comparable = None
        authoritative = False
    elif different:
        state = "comparable_with_context_divergence"
        comparable = True
        authoritative = True
    elif explanatory and any(
        evidence_by_dimension.get(row.dimension)
        and evidence_by_dimension[row.dimension].dimension_state == "different"
        for row in explanatory
    ):
        state = "comparable_with_context_divergence"
        comparable = True
        authoritative = True
    elif required or explanatory:
        state = "comparable_all_required_context_resolved"
        comparable = True
        authoritative = True
    elif len(irrelevant) + len(inapplicable) == len(expected_dimensions):
        state = "comparable_no_context_sensitive_requirement"
        comparable = True
        authoritative = True
    else:
        # Defensive fail-closed branch: an uncovered state can never silently
        # become "no context-sensitive requirement".
        state = "reviewable_requirement_semantics_unresolved"
        comparable = None
        authoritative = False

    payload = {
        "pair_id": pair_id,
        "upstream": upstream.model_dump(mode="json"),
        "activation_ids": sorted(row.requirement_identity for row in rows),
        "evidence_ids": sorted(row.evidence_identity for row in evidence_by_dimension.values()),
        "l4b_state": state,
    }
    return L4bComparabilityResultV3Candidate(
        pair_id=pair_id,
        upstream_eligibility=upstream,
        comparison_required_dimensions=sorted(row.dimension for row in required),
        divergence_explanatory_dimensions=sorted(row.dimension for row in explanatory),
        explicit_not_decision_relevant_dimensions=sorted(
            row.dimension for row in irrelevant
        ),
        not_applicable_dimensions=sorted(row.dimension for row in inapplicable),
        requirement_unresolved_dimensions=sorted(
            row.dimension for row in unresolved_roles
        ),
        matched_required_dimensions=sorted(matched),
        different_required_dimensions=sorted(different),
        unresolved_required_dimensions=sorted(unresolved_required),
        ambiguous_required_dimensions=sorted(ambiguous),
        source_scope_blockers=sorted(source_blockers),
        l4b_state=state,
        comparable=comparable,
        authoritative_l4b_result=authoritative,
        result_identity=stable_v3("l4b_comparability_result_v3_candidate", payload),
    ), satisfactions


__all__ = [
    "CONTEXT_DIMENSIONS",
    "PairSemanticTriggerFactV1",
    "PairRequirementAuthorityV1",
    "PairSemanticTriggerCoverageV1",
    "UpstreamTriggerProjectionGapV1",
    "PairContextRequirementActivationV3Candidate",
    "PairContextDimensionEvidenceV3Candidate",
    "PairContextRequirementSatisfactionV3Candidate",
    "L4bComparabilityResultV3Candidate",
    "make_trigger_fact_v1",
    "make_requirement_authority_v1",
    "make_projection_gap_v1",
    "audit_trigger_coverage_v1",
    "activate_pair_dimension_v3_candidate",
    "evidence_from_trigger_fact_v3_candidate",
    "satisfaction_for_pair_v3_candidate",
    "evaluate_l4b_v3_candidate",
    "stable_v3",
]
