"""Deterministic pair Context requirement and L4b comparability semantics.

The authoritative scientific contract is
``docs/l4b_pair_comparability_semantics_v1.md``.  In particular, an activated
requirement must be *resolved*, not equal: both ``matched`` and ``different``
can satisfy comparison-required Context.

This module is a backward-compatible sidecar implementation.  It neither
modifies the v1 requirement artifacts nor materializes L4a, explanation, or
Formal Judgment objects.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SEMANTICS_CONTRACT_ID = "l4b_pair_comparability_semantics_v1"
SEMANTICS_CONTRACT_PATH = "docs/l4b_pair_comparability_semantics_v1.md"

ContextDimension = Literal[
    "biological_model",
    "intervention",
    "temporal",
    "genotype",
    "localization",
    "measurement",
    "disease",
    "experimental_design",
]
RequirementRole = Literal[
    "comparison_required",
    "divergence_explanatory",
    "not_decision_relevant",
    "requirement_unresolved",
]
ActivatingRole = Literal["comparison_required", "divergence_explanatory"]
TriggerFamily = Literal[
    "proposition_scope",
    "experimental_factor_scope",
    "measurement_result_scope",
    "evidence_family_scope",
    "source_grounded_pair_difference",
    "comparison_structure",
]
DimensionState = Literal[
    "matched",
    "different",
    "unresolved_a",
    "unresolved_b",
    "unresolved_both",
    "ambiguous_a",
    "ambiguous_b",
    "ambiguous_both",
    "source_scope_insufficient_a",
    "source_scope_insufficient_b",
    "source_scope_insufficient_both",
    "not_reported_a",
    "not_reported_b",
    "not_reported_both",
    "not_applicable",
    "no_supported_value",
]
ContextValueStateV1 = Literal[
    "present",
    "explicitly_absent",
    "not_mentioned",
    "not_extracted",
    "unknown",
    "ambiguous",
    "not_applicable",
    "invalid",
    "unavailable",
    "legacy_null_unresolved",
]
SourceAuthority = Literal[
    "validated_source_grounded",
    "safe_scope_inherited",
    "authorized_deterministic_derived",
    "unsupported",
]
ScopeAdequacy = Literal["adequate", "insufficient", "unresolved", "not_applicable"]
SatisfactionStatusV2 = Literal[
    "satisfied_resolved_matched",
    "satisfied_resolved_different",
    "unsatisfied_unresolved",
    "unsatisfied_ambiguous",
    "unsatisfied_source_scope",
    "unsatisfied_not_reported",
    "not_applicable",
]
L4bState = Literal[
    "comparable_all_required_context_resolved",
    "comparable_with_context_divergence",
    "comparable_no_context_sensitive_requirement",
    "reviewable_requirement_semantics_unresolved",
    "reviewable_required_context_gap",
    "blocked_required_context_ambiguous",
    "blocked_source_scope",
    "blocked_upstream_alignment",
    "blocked_upstream_contradiction_signal",
    "blocked_upstream_candidate_qualification",
    "blocked_upstream_entity_integrity",
    "not_applicable",
]

SUPPORTED_SOURCE_AUTHORITIES = {
    "validated_source_grounded",
    "safe_scope_inherited",
    "authorized_deterministic_derived",
}
SOURCE_GROUNDED_HANDOFF_AUTHORITIES = {
    "validated_source_grounded",
    "safe_scope_inherited",
}
AMBIGUOUS_DIMENSION_STATES = {"ambiguous_a", "ambiguous_b", "ambiguous_both"}
SOURCE_SCOPE_DIMENSION_STATES = {
    "source_scope_insufficient_a",
    "source_scope_insufficient_b",
    "source_scope_insufficient_both",
}
NOT_REPORTED_DIMENSION_STATES = {
    "not_reported_a",
    "not_reported_b",
    "not_reported_both",
}
UNRESOLVED_DIMENSION_STATES = {
    "unresolved_a",
    "unresolved_b",
    "unresolved_both",
    "not_applicable",
    "no_supported_value",
}


def stable(kind: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{kind}_{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PairContextTriggerFactV2(StrictModel):
    """One structured fact permitted to activate a pair/consumer role."""

    schema_version: Literal["pair_context_trigger_fact_v2"] = "pair_context_trigger_fact_v2"
    pair_id: str = Field(min_length=1)
    consumer: str = Field(min_length=1)
    dimension: ContextDimension
    trigger_family: TriggerFamily
    structurally_established: bool
    decision_role: ActivatingRole | None = None
    role_determinable: bool = True
    trigger_evidence: dict[str, Any]
    source_contract_ref: str = Field(min_length=1)
    source_code_ref: str = Field(min_length=1)
    missingness_used_as_trigger: Literal[False] = False
    llm_output_used_as_trigger: Literal[False] = False
    proposition_identity_contract: bool = False
    explicit_formal_contract: bool = False
    trigger_fact_identity: str | None = None

    @model_validator(mode="after")
    def validate_authority_boundary(self):
        if self.structurally_established and self.role_determinable and self.decision_role is None:
            raise ValueError("established_determinable_trigger_requires_decision_role")
        if not self.role_determinable and self.decision_role is not None:
            raise ValueError("indeterminate_trigger_cannot_preselect_role")
        if (
            self.structurally_established
            and self.consumer == "l4a_context_difference"
            and self.decision_role is not None
        ):
            raise ValueError("l4a_cannot_activate_comparability_or_explanation_role")
        if (
            self.structurally_established
            and self.consumer == "claim_qualification"
            and not self.proposition_identity_contract
        ):
            raise ValueError("claim_qualification_requires_proposition_identity_contract")
        if (
            self.structurally_established
            and self.consumer == "formal_judgment"
            and not self.explicit_formal_contract
        ):
            raise ValueError("formal_judgment_requires_explicit_formal_contract")
        return self


class PairContextRequirementActivationV2(StrictModel):
    schema_version: Literal[
        "pair_context_requirement_activation_v2"
    ] = "pair_context_requirement_activation_v2"
    pair_id: str
    consumer: str
    consumer_version: str
    dimension: ContextDimension
    primary_role: RequirementRole
    secondary_roles: list[ActivatingRole] = Field(default_factory=list)
    trigger_families: list[TriggerFamily] = Field(default_factory=list)
    trigger_fact_ids: list[str] = Field(default_factory=list)
    trigger_evidence: list[dict[str, Any]] = Field(default_factory=list)
    source_contract_refs: list[str] = Field(default_factory=list)
    source_code_refs: list[str] = Field(default_factory=list)
    activation_reason: str = Field(min_length=1)
    missingness_created_relevance: Literal[False] = False
    llm_output_created_relevance: Literal[False] = False
    requirement_identity: str

    @model_validator(mode="after")
    def validate_roles(self):
        if len(self.secondary_roles) != len(set(self.secondary_roles)):
            raise ValueError("duplicate_secondary_role")
        if self.primary_role in {"not_decision_relevant", "requirement_unresolved"}:
            if self.secondary_roles:
                raise ValueError("inactive_or_unresolved_primary_cannot_have_secondary_role")
        if self.primary_role == "divergence_explanatory" and self.secondary_roles:
            raise ValueError("divergence_primary_has_no_distinct_secondary_role")
        if self.primary_role == "comparison_required" and "comparison_required" in self.secondary_roles:
            raise ValueError("primary_role_cannot_repeat_as_secondary")
        return self


class PairContextRequirementProfileV2(StrictModel):
    schema_version: Literal[
        "pair_context_requirement_profile_v2"
    ] = "pair_context_requirement_profile_v2"
    pair_id: str
    consumer: str
    consumer_version: str
    semantics_contract_id: Literal[
        "l4b_pair_comparability_semantics_v1"
    ] = SEMANTICS_CONTRACT_ID
    validated_trigger_inputs: dict[str, Any]
    contract_ids: list[str]
    requirement_identity: str
    upstream_preconditions_evaluated_first: Literal[True] = True
    task_identity_read: Literal[False] = False
    reference_answer_read: Literal[False] = False
    llm_output_read_for_activation: Literal[False] = False

    @model_validator(mode="after")
    def no_evaluation_leakage(self):
        forbidden = {
            "task_id",
            "task_ids",
            "case_name",
            "pmid",
            "reference_answer",
            "human_adjudication",
            "reference_factor_id",
            "llm_output",
        }
        if forbidden.intersection(self.validated_trigger_inputs):
            raise ValueError("pair_requirement_trigger_contains_forbidden_input")
        return self


class ContextSideValueV2(StrictModel):
    value_state: ContextValueStateV1
    value: Any = None
    source_authority: SourceAuthority = "unsupported"
    source_scope_adequacy: ScopeAdequacy = "unresolved"
    provenance: list[str] = Field(default_factory=list)
    inheritance_scope_validated: bool = False
    deterministic_rule_identity: str | None = None

    @model_validator(mode="after")
    def validate_source_semantics(self):
        if self.value_state == "present" and self.value is None:
            raise ValueError("present_context_value_cannot_be_null")
        if self.value_state != "present" and self.value is not None:
            raise ValueError("non_present_context_state_cannot_carry_single_resolved_value")
        if self.value_state == "not_mentioned":
            if self.source_scope_adequacy != "adequate" or not self.provenance:
                raise ValueError("not_mentioned_requires_adequately_inspected_source_scope")
        if self.source_authority in SUPPORTED_SOURCE_AUTHORITIES and not self.provenance:
            raise ValueError("supported_context_value_requires_provenance")
        if self.source_authority == "safe_scope_inherited" and not self.inheritance_scope_validated:
            raise ValueError("inherited_context_requires_validated_scope")
        if (
            self.source_authority == "authorized_deterministic_derived"
            and not self.deterministic_rule_identity
        ):
            raise ValueError("derived_context_requires_authorized_rule_identity")
        return self


class PairContextDimensionEvidenceV2(StrictModel):
    schema_version: Literal[
        "pair_context_dimension_evidence_v2"
    ] = "pair_context_dimension_evidence_v2"
    pair_id: str
    dimension: ContextDimension
    dimension_state: DimensionState
    value_a: Any = None
    value_b: Any = None
    provenance_a: list[str] = Field(default_factory=list)
    provenance_b: list[str] = Field(default_factory=list)
    source_authority_a: SourceAuthority = "unsupported"
    source_authority_b: SourceAuthority = "unsupported"
    source_scope_adequacy_a: ScopeAdequacy = "unresolved"
    source_scope_adequacy_b: ScopeAdequacy = "unresolved"
    inheritance_scope_validated_a: bool = False
    inheritance_scope_validated_b: bool = False
    deterministic_rule_identity_a: str | None = None
    deterministic_rule_identity_b: str | None = None
    evidence_identity: str

    @model_validator(mode="after")
    def validate_dimension_state(self):
        if self.dimension_state in {"matched", "different"}:
            if self.value_a is None or self.value_b is None:
                raise ValueError("resolved_dimension_requires_two_values")
            if self.source_authority_a not in SUPPORTED_SOURCE_AUTHORITIES:
                raise ValueError("resolved_dimension_requires_authoritative_side_a")
            if self.source_authority_b not in SUPPORTED_SOURCE_AUTHORITIES:
                raise ValueError("resolved_dimension_requires_authoritative_side_b")
            if self.source_scope_adequacy_a != "adequate" or self.source_scope_adequacy_b != "adequate":
                raise ValueError("resolved_dimension_requires_adequate_source_scope")
            if not self.provenance_a or not self.provenance_b:
                raise ValueError("resolved_dimension_requires_two_sided_provenance")
            if self.source_authority_a == "safe_scope_inherited" and not self.inheritance_scope_validated_a:
                raise ValueError("side_a_inheritance_scope_not_validated")
            if self.source_authority_b == "safe_scope_inherited" and not self.inheritance_scope_validated_b:
                raise ValueError("side_b_inheritance_scope_not_validated")
            if self.source_authority_a == "authorized_deterministic_derived" and not self.deterministic_rule_identity_a:
                raise ValueError("side_a_derived_value_missing_rule_identity")
            if self.source_authority_b == "authorized_deterministic_derived" and not self.deterministic_rule_identity_b:
                raise ValueError("side_b_derived_value_missing_rule_identity")
            if self.dimension_state == "matched" and self.value_a != self.value_b:
                raise ValueError("matched_dimension_values_must_be_equal")
            if self.dimension_state == "different" and self.value_a == self.value_b:
                raise ValueError("different_dimension_values_must_differ")
        if self.dimension_state in NOT_REPORTED_DIMENSION_STATES:
            affected = {
                "not_reported_a": (True, False),
                "not_reported_b": (False, True),
                "not_reported_both": (True, True),
            }[self.dimension_state]
            if affected[0] and self.source_scope_adequacy_a != "adequate":
                raise ValueError("not_reported_a_requires_adequate_source_scope")
            if affected[1] and self.source_scope_adequacy_b != "adequate":
                raise ValueError("not_reported_b_requires_adequate_source_scope")
        return self


class PairContextRequirementSatisfactionV2(StrictModel):
    schema_version: Literal[
        "pair_context_requirement_satisfaction_v2"
    ] = "pair_context_requirement_satisfaction_v2"
    pair_id: str
    consumer: str
    dimension: ContextDimension
    requirement_identity: str
    primary_role: RequirementRole
    dimension_state: DimensionState
    resolved_for_comparison: bool
    satisfaction_status: SatisfactionStatusV2
    evidence_identity: str | None = None


class L4bUpstreamEligibilityV1(StrictModel):
    schema_version: Literal["l4b_upstream_eligibility_v1"] = "l4b_upstream_eligibility_v1"
    pair_id: str
    entity_integrity_eligible: bool
    alignment_eligible: bool
    contradiction_signal_valid: bool
    candidate_qualification_eligible: bool
    entity_integrity_state: str
    alignment_state: str
    contradiction_signal_state: str
    candidate_qualification_state: str
    upstream_refs: list[str] = Field(default_factory=list)
    explicitly_not_applicable: bool = False


class ResolvedContextDifferenceCandidateV1(StrictModel):
    schema_version: Literal[
        "resolved_context_difference_candidate_v1"
    ] = "resolved_context_difference_candidate_v1"
    pair_id: str
    dimension: ContextDimension
    value_a: Any
    value_b: Any
    provenance_a: list[str]
    provenance_b: list[str]
    difference_status: Literal["resolved_different"] = "resolved_different"
    requirement_role: RequirementRole
    eligibility_for_divergence_explanation: Literal[
        "eligible_candidate_only"
    ] = "eligible_candidate_only"
    causal_explanation_asserted: Literal[False] = False
    candidate_identity: str


class L4bComparabilityResultV1(StrictModel):
    schema_version: Literal[
        "l4b_comparability_result_v1"
    ] = "l4b_comparability_result_v1"
    pair_id: str
    semantics_contract_id: Literal[
        "l4b_pair_comparability_semantics_v1"
    ] = SEMANTICS_CONTRACT_ID
    upstream_eligibility: L4bUpstreamEligibilityV1
    activated_comparison_required_dimensions: list[ContextDimension]
    activated_divergence_explanatory_dimensions: list[ContextDimension]
    requirement_unresolved_dimensions: list[ContextDimension]
    matched_required_dimensions: list[ContextDimension]
    different_required_dimensions: list[ContextDimension]
    unresolved_required_dimensions: list[ContextDimension]
    ambiguous_required_dimensions: list[ContextDimension]
    source_scope_blockers: list[ContextDimension]
    l4b_state: L4bState
    comparable: bool | None
    authoritative_l4b_result: bool
    resolved_context_difference_candidates: list[ResolvedContextDifferenceCandidateV1]
    l4a_descriptive_input_consumed: bool
    divergence_explanation_decided: Literal[False] = False
    formal_conflict_generated: Literal[False] = False
    historical_objects_modified: Literal[False] = False
    result_identity: str


def _fact_identity(fact: PairContextTriggerFactV2) -> str:
    if fact.trigger_fact_identity:
        return fact.trigger_fact_identity
    return stable(
        "pair_context_trigger_fact_v2",
        fact.model_dump(exclude={"trigger_fact_identity"}),
    )


def activate_pair_dimension_v2(
    *,
    pair_id: str,
    consumer: str,
    consumer_version: str,
    dimension: ContextDimension,
    trigger_facts: list[PairContextTriggerFactV2],
) -> PairContextRequirementActivationV2:
    """Assign one role using established facts; absence and missingness do not activate."""
    relevant = [
        fact
        for fact in trigger_facts
        if fact.pair_id == pair_id
        and fact.consumer == consumer
        and fact.dimension == dimension
        and fact.structurally_established
    ]
    indeterminate = any(not fact.role_determinable for fact in relevant)
    roles = {fact.decision_role for fact in relevant if fact.decision_role is not None}
    if indeterminate:
        primary_role: RequirementRole = "requirement_unresolved"
        secondary_roles: list[ActivatingRole] = []
        reason = "established_pair_semantics_have_unresolved_decision_role"
    elif "comparison_required" in roles:
        primary_role = "comparison_required"
        secondary_roles = (
            ["divergence_explanatory"] if "divergence_explanatory" in roles else []
        )
        reason = "validated_pair_semantics_activate_comparison_resolution_requirement"
    elif roles == {"divergence_explanatory"}:
        primary_role = "divergence_explanatory"
        secondary_roles = []
        reason = "validated_pair_semantics_allow_explanatory_candidate_handoff"
    else:
        primary_role = "not_decision_relevant"
        secondary_roles = []
        reason = "no_structurally_established_pair_specific_trigger"

    fact_ids = sorted(_fact_identity(fact) for fact in relevant)
    payload = {
        "pair_id": pair_id,
        "consumer": consumer,
        "consumer_version": consumer_version,
        "dimension": dimension,
        "primary_role": primary_role,
        "secondary_roles": secondary_roles,
        "trigger_fact_ids": fact_ids,
        "semantics_contract_id": SEMANTICS_CONTRACT_ID,
    }
    return PairContextRequirementActivationV2(
        pair_id=pair_id,
        consumer=consumer,
        consumer_version=consumer_version,
        dimension=dimension,
        primary_role=primary_role,
        secondary_roles=secondary_roles,
        trigger_families=sorted({fact.trigger_family for fact in relevant}),
        trigger_fact_ids=fact_ids,
        trigger_evidence=[fact.trigger_evidence for fact in relevant],
        source_contract_refs=sorted({fact.source_contract_ref for fact in relevant}),
        source_code_refs=sorted({fact.source_code_ref for fact in relevant}),
        activation_reason=reason,
        requirement_identity=stable("pair_context_requirement_v2", payload),
    )


def _side_is_supported(side: ContextSideValueV2) -> bool:
    if side.value_state != "present":
        return False
    if side.source_authority not in SUPPORTED_SOURCE_AUTHORITIES:
        return False
    if side.source_scope_adequacy != "adequate":
        return False
    if side.source_authority == "safe_scope_inherited" and not side.inheritance_scope_validated:
        return False
    if side.source_authority == "authorized_deterministic_derived" and not side.deterministic_rule_identity:
        return False
    return True


def classify_pair_dimension_state_v2(
    side_a: ContextSideValueV2,
    side_b: ContextSideValueV2,
) -> DimensionState:
    """Map existing Context value states into the L4b pair-state vocabulary."""
    if side_a.value_state == side_b.value_state == "not_applicable":
        return "not_applicable"

    scope_a = side_a.source_scope_adequacy == "insufficient"
    scope_b = side_b.source_scope_adequacy == "insufficient"
    if scope_a and scope_b:
        return "source_scope_insufficient_both"
    if scope_a:
        return "source_scope_insufficient_a"
    if scope_b:
        return "source_scope_insufficient_b"

    ambiguous_a = side_a.value_state == "ambiguous"
    ambiguous_b = side_b.value_state == "ambiguous"
    if ambiguous_a and ambiguous_b:
        return "ambiguous_both"
    if ambiguous_a:
        return "ambiguous_a"
    if ambiguous_b:
        return "ambiguous_b"

    not_reported_a = side_a.value_state == "not_mentioned"
    not_reported_b = side_b.value_state == "not_mentioned"
    if not_reported_a and not_reported_b:
        return "not_reported_both"
    if not_reported_a:
        return "not_reported_a"
    if not_reported_b:
        return "not_reported_b"

    supported_a = _side_is_supported(side_a)
    supported_b = _side_is_supported(side_b)
    if supported_a and supported_b:
        return "matched" if side_a.value == side_b.value else "different"
    if supported_a:
        return "unresolved_b"
    if supported_b:
        return "unresolved_a"
    if not side_a.provenance and not side_b.provenance:
        return "no_supported_value"
    return "unresolved_both"


def build_dimension_evidence_v2(
    *,
    pair_id: str,
    dimension: ContextDimension,
    side_a: ContextSideValueV2,
    side_b: ContextSideValueV2,
) -> PairContextDimensionEvidenceV2:
    state = classify_pair_dimension_state_v2(side_a, side_b)
    payload = {
        "pair_id": pair_id,
        "dimension": dimension,
        "dimension_state": state,
        "value_a": side_a.value,
        "value_b": side_b.value,
        "provenance_a": side_a.provenance,
        "provenance_b": side_b.provenance,
        "source_authority_a": side_a.source_authority,
        "source_authority_b": side_b.source_authority,
        "source_scope_adequacy_a": side_a.source_scope_adequacy,
        "source_scope_adequacy_b": side_b.source_scope_adequacy,
        "inheritance_scope_validated_a": side_a.inheritance_scope_validated,
        "inheritance_scope_validated_b": side_b.inheritance_scope_validated,
        "deterministic_rule_identity_a": side_a.deterministic_rule_identity,
        "deterministic_rule_identity_b": side_b.deterministic_rule_identity,
    }
    return PairContextDimensionEvidenceV2(
        **payload,
        evidence_identity=stable("pair_context_dimension_evidence_v2", payload),
    )


def resolved_for_comparison_v2(evidence: PairContextDimensionEvidenceV2) -> bool:
    """True for authoritative matched *or different* two-sided evidence."""
    return evidence.dimension_state in {"matched", "different"}


def satisfaction_for_pair_v2(
    activation: PairContextRequirementActivationV2,
    evidence: PairContextDimensionEvidenceV2 | None,
) -> PairContextRequirementSatisfactionV2:
    if activation.primary_role != "comparison_required":
        state: DimensionState = evidence.dimension_state if evidence else "no_supported_value"
        return PairContextRequirementSatisfactionV2(
            pair_id=activation.pair_id,
            consumer=activation.consumer,
            dimension=activation.dimension,
            requirement_identity=activation.requirement_identity,
            primary_role=activation.primary_role,
            dimension_state=state,
            resolved_for_comparison=False,
            satisfaction_status="not_applicable",
            evidence_identity=evidence.evidence_identity if evidence else None,
        )

    state = evidence.dimension_state if evidence else "no_supported_value"
    resolved = bool(evidence and resolved_for_comparison_v2(evidence))
    if state == "matched" and resolved:
        status: SatisfactionStatusV2 = "satisfied_resolved_matched"
    elif state == "different" and resolved:
        status = "satisfied_resolved_different"
    elif state in SOURCE_SCOPE_DIMENSION_STATES:
        status = "unsatisfied_source_scope"
    elif state in AMBIGUOUS_DIMENSION_STATES:
        status = "unsatisfied_ambiguous"
    elif state in NOT_REPORTED_DIMENSION_STATES:
        status = "unsatisfied_not_reported"
    else:
        status = "unsatisfied_unresolved"
    return PairContextRequirementSatisfactionV2(
        pair_id=activation.pair_id,
        consumer=activation.consumer,
        dimension=activation.dimension,
        requirement_identity=activation.requirement_identity,
        primary_role=activation.primary_role,
        dimension_state=state,
        resolved_for_comparison=resolved,
        satisfaction_status=status,
        evidence_identity=evidence.evidence_identity if evidence else None,
    )


def l4a_descriptive_state_v1(evidence: PairContextDimensionEvidenceV2) -> Literal[
    "matched", "different", "unresolved", "ambiguous"
]:
    """L4a projection is descriptive and deliberately has no blocking state."""
    if evidence.dimension_state == "matched":
        return "matched"
    if evidence.dimension_state == "different":
        return "different"
    if evidence.dimension_state in AMBIGUOUS_DIMENSION_STATES:
        return "ambiguous"
    return "unresolved"


def upstream_block_state_v1(upstream: L4bUpstreamEligibilityV1) -> L4bState | None:
    if upstream.explicitly_not_applicable:
        return "not_applicable"
    if not upstream.entity_integrity_eligible:
        return "blocked_upstream_entity_integrity"
    if not upstream.alignment_eligible:
        return "blocked_upstream_alignment"
    if not upstream.contradiction_signal_valid:
        return "blocked_upstream_contradiction_signal"
    if not upstream.candidate_qualification_eligible:
        return "blocked_upstream_candidate_qualification"
    return None


def _handoff_candidate(
    *,
    activation: PairContextRequirementActivationV2,
    evidence: PairContextDimensionEvidenceV2,
) -> ResolvedContextDifferenceCandidateV1 | None:
    permits_explanation = (
        activation.primary_role == "divergence_explanatory"
        or "divergence_explanatory" in activation.secondary_roles
    )
    if not permits_explanation or evidence.dimension_state != "different":
        return None
    if evidence.source_authority_a not in SOURCE_GROUNDED_HANDOFF_AUTHORITIES:
        return None
    if evidence.source_authority_b not in SOURCE_GROUNDED_HANDOFF_AUTHORITIES:
        return None
    payload = {
        "pair_id": activation.pair_id,
        "dimension": activation.dimension,
        "value_a": evidence.value_a,
        "value_b": evidence.value_b,
        "provenance_a": evidence.provenance_a,
        "provenance_b": evidence.provenance_b,
        "requirement_role": activation.primary_role,
        "evidence_identity": evidence.evidence_identity,
    }
    return ResolvedContextDifferenceCandidateV1(
        pair_id=activation.pair_id,
        dimension=activation.dimension,
        value_a=evidence.value_a,
        value_b=evidence.value_b,
        provenance_a=evidence.provenance_a,
        provenance_b=evidence.provenance_b,
        requirement_role=activation.primary_role,
        candidate_identity=stable("resolved_context_difference_candidate_v1", payload),
    )


def evaluate_l4b_comparability_v1(
    *,
    pair_id: str,
    upstream: L4bUpstreamEligibilityV1,
    activations: list[PairContextRequirementActivationV2],
    dimension_evidence: list[PairContextDimensionEvidenceV2],
    consumer: str = "l4b_comparability",
) -> tuple[L4bComparabilityResultV1, list[PairContextRequirementSatisfactionV2]]:
    """Evaluate L4b after enforcing upstream scientific preconditions."""
    if upstream.pair_id != pair_id:
        raise ValueError("l4b_upstream_pair_identity_mismatch")
    rows = [row for row in activations if row.pair_id == pair_id and row.consumer == consumer]
    if len(rows) != len({row.dimension for row in rows}):
        raise ValueError("duplicate_l4b_dimension_activation")
    evidence_by_dimension = {
        row.dimension: row for row in dimension_evidence if row.pair_id == pair_id
    }
    if len(evidence_by_dimension) != len(
        [row for row in dimension_evidence if row.pair_id == pair_id]
    ):
        raise ValueError("duplicate_l4b_dimension_evidence")

    required = [row for row in rows if row.primary_role == "comparison_required"]
    explanatory = [
        row
        for row in rows
        if row.primary_role == "divergence_explanatory"
        or "divergence_explanatory" in row.secondary_roles
    ]
    unresolved_roles = [row for row in rows if row.primary_role == "requirement_unresolved"]

    # Preconditions are a true gate, not merely a final-state override.  Keep
    # the audited activations visible, but do not inspect dimension satisfaction
    # or consume L4a evidence for an ineligible upstream pair.
    block_state = upstream_block_state_v1(upstream)
    if block_state is not None:
        payload = {
            "pair_id": pair_id,
            "semantics_contract_id": SEMANTICS_CONTRACT_ID,
            "upstream": upstream.model_dump(),
            "activation_ids": [row.requirement_identity for row in rows],
            "evidence_ids": [],
            "l4b_state": block_state,
            "handoff_ids": [],
        }
        return L4bComparabilityResultV1(
            pair_id=pair_id,
            upstream_eligibility=upstream,
            activated_comparison_required_dimensions=sorted(
                row.dimension for row in required
            ),
            activated_divergence_explanatory_dimensions=sorted(
                row.dimension for row in explanatory
            ),
            requirement_unresolved_dimensions=sorted(
                row.dimension for row in unresolved_roles
            ),
            matched_required_dimensions=[],
            different_required_dimensions=[],
            unresolved_required_dimensions=[],
            ambiguous_required_dimensions=[],
            source_scope_blockers=[],
            l4b_state=block_state,
            comparable=None,
            authoritative_l4b_result=False,
            resolved_context_difference_candidates=[],
            l4a_descriptive_input_consumed=False,
            result_identity=stable("l4b_comparability_result_v1", payload),
        ), []

    satisfactions = [
        satisfaction_for_pair_v2(row, evidence_by_dimension.get(row.dimension)) for row in rows
    ]
    required_satisfactions = [
        row for row in satisfactions if row.primary_role == "comparison_required"
    ]

    matched = [
        row.dimension
        for row in required_satisfactions
        if row.satisfaction_status == "satisfied_resolved_matched"
    ]
    different = [
        row.dimension
        for row in required_satisfactions
        if row.satisfaction_status == "satisfied_resolved_different"
    ]
    source_blockers = [
        row.dimension
        for row in required_satisfactions
        if row.satisfaction_status == "unsatisfied_source_scope"
    ]
    ambiguous = [
        row.dimension
        for row in required_satisfactions
        if row.satisfaction_status == "unsatisfied_ambiguous"
    ]
    unresolved = [
        row.dimension
        for row in required_satisfactions
        if row.satisfaction_status in {"unsatisfied_unresolved", "unsatisfied_not_reported"}
    ]
    handoffs = [
        candidate
        for row in explanatory
        if (evidence := evidence_by_dimension.get(row.dimension)) is not None
        if (candidate := _handoff_candidate(activation=row, evidence=evidence)) is not None
    ]

    if unresolved_roles:
        state = "reviewable_requirement_semantics_unresolved"
        comparable: bool | None = None
        authoritative = False
        handoffs = []
    elif source_blockers:
        state = "blocked_source_scope"
        comparable = False
        authoritative = True
        handoffs = []
    elif ambiguous:
        state = "blocked_required_context_ambiguous"
        comparable = False
        authoritative = True
        handoffs = []
    elif unresolved:
        state = "reviewable_required_context_gap"
        comparable = None
        authoritative = False
        handoffs = []
    else:
        decision_relevant_differences = set(different)
        decision_relevant_differences.update(
            row.dimension
            for row in explanatory
            if (
                (evidence := evidence_by_dimension.get(row.dimension)) is not None
                and resolved_for_comparison_v2(evidence)
                and evidence.dimension_state == "different"
            )
        )
        if decision_relevant_differences:
            state = "comparable_with_context_divergence"
        elif not required and not explanatory:
            state = "comparable_no_context_sensitive_requirement"
        else:
            state = "comparable_all_required_context_resolved"
        comparable = True
        authoritative = True

    payload = {
        "pair_id": pair_id,
        "semantics_contract_id": SEMANTICS_CONTRACT_ID,
        "upstream": upstream.model_dump(),
        "activation_ids": [row.requirement_identity for row in rows],
        "evidence_ids": sorted(row.evidence_identity for row in evidence_by_dimension.values()),
        "l4b_state": state,
        "handoff_ids": [row.candidate_identity for row in handoffs],
    }
    result = L4bComparabilityResultV1(
        pair_id=pair_id,
        upstream_eligibility=upstream,
        activated_comparison_required_dimensions=sorted(row.dimension for row in required),
        activated_divergence_explanatory_dimensions=sorted(
            row.dimension for row in explanatory
        ),
        requirement_unresolved_dimensions=sorted(row.dimension for row in unresolved_roles),
        matched_required_dimensions=sorted(matched),
        different_required_dimensions=sorted(different),
        unresolved_required_dimensions=sorted(unresolved),
        ambiguous_required_dimensions=sorted(ambiguous),
        source_scope_blockers=sorted(source_blockers),
        l4b_state=state,
        comparable=comparable,
        authoritative_l4b_result=authoritative,
        resolved_context_difference_candidates=handoffs,
        l4a_descriptive_input_consumed=bool(evidence_by_dimension),
        result_identity=stable("l4b_comparability_result_v1", payload),
    )
    return result, satisfactions


__all__ = [
    "SEMANTICS_CONTRACT_ID",
    "SEMANTICS_CONTRACT_PATH",
    "PairContextTriggerFactV2",
    "PairContextRequirementActivationV2",
    "PairContextRequirementProfileV2",
    "ContextSideValueV2",
    "PairContextDimensionEvidenceV2",
    "PairContextRequirementSatisfactionV2",
    "L4bUpstreamEligibilityV1",
    "ResolvedContextDifferenceCandidateV1",
    "L4bComparabilityResultV1",
    "activate_pair_dimension_v2",
    "classify_pair_dimension_state_v2",
    "build_dimension_evidence_v2",
    "resolved_for_comparison_v2",
    "satisfaction_for_pair_v2",
    "l4a_descriptive_state_v1",
    "upstream_block_state_v1",
    "evaluate_l4b_comparability_v1",
]
