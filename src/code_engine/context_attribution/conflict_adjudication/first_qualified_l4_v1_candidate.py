"""Fail-closed, candidate-only L4 aggregation helpers.

These helpers contain no disease-, entity-, or source-specific rules.  They
separate a validated difference, its explanatory authority, and a formal
candidate decision.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..layer_identity import layer_identity


class StrictCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DivergenceExplanatoryPowerResultV1Candidate(StrictCandidateModel):
    schema_version: Literal["divergence_explanatory_power_result_v1_candidate"] = "divergence_explanatory_power_result_v1_candidate"
    pair_id: str
    context_dimension: str
    context_difference_identity: str
    difference_validated: bool
    two_sided_context_resolved: bool
    explanation_eligibility: Literal["eligible_explanation_candidate", "difference_not_explanatory_under_contract", "insufficient_authority"]
    explanation_state: Literal["supported_explanatory_difference", "explanatory_power_unresolved", "difference_not_explanatory_under_contract", "insufficient_authority"]
    explanation_policy_identity: str | None = None
    human_adjudication_identity: str | None = None
    sufficient_to_explain_divergence: bool | None = None
    rationale: str
    source_refs: list[str] = Field(default_factory=list)
    llm_authority_used: Literal[False] = False
    biomedical_common_knowledge_used: Literal[False] = False
    candidate_only: Literal[True] = True
    identity: str

    @model_validator(mode="after")
    def supported_explanation_requires_authority(self):
        if self.explanation_state == "supported_explanatory_difference":
            if not (self.explanation_policy_identity or self.human_adjudication_identity):
                raise ValueError("supported_explanation_requires_authority")
            if self.sufficient_to_explain_divergence is not True:
                raise ValueError("supported_explanation_requires_sufficiency")
        elif self.sufficient_to_explain_divergence is not None:
            raise ValueError("unresolved_explanation_cannot_assert_sufficiency")
        return self


class FormalJudgmentCandidateV1(StrictCandidateModel):
    schema_version: Literal["formal_judgment_candidate_v1"] = "formal_judgment_candidate_v1"
    pair_id: str
    upstream_valid: bool
    evidence_independence_valid: bool
    provenance_adequate: bool
    l4b_state: str
    l4b_comparable: bool | None
    divergence_explanation_assessed: bool
    supported_sufficient_context_explanation: bool
    unresolved_explanatory_power_count: int
    formal_candidate_state: Literal[
        "formal_conflict_candidate_confirmed", "not_confirmed_context_explained",
        "reviewable_divergence_explanation_unresolved", "reviewable_context_authority_gap",
        "blocked_comparability", "blocked_upstream_regression",
    ]
    historical_formal_created: Literal[False] = False
    candidate_only: Literal[True] = True
    rationale: str
    identity: str


def assess_divergence_explanatory_power_v1(
    *, pair_id: str, context_dimension: str, context_difference_identity: str,
    difference_validated: bool, two_sided_context_resolved: bool,
    explanation_eligible: bool, source_refs: list[str],
    explanation_policy_identity: str | None = None,
    human_adjudication_identity: str | None = None,
    authoritative_sufficiency: bool | None = None,
) -> DivergenceExplanatoryPowerResultV1Candidate:
    if not difference_validated or not two_sided_context_resolved:
        eligibility = "insufficient_authority"
        state = "insufficient_authority"
        sufficient = None
        rationale = "A validated, two-sided resolved Context difference is required."
    elif not explanation_eligible:
        eligibility = "difference_not_explanatory_under_contract"
        state = "difference_not_explanatory_under_contract"
        sufficient = None
        rationale = "The Context difference is not eligible under the explanation contract."
    elif authoritative_sufficiency is True and (explanation_policy_identity or human_adjudication_identity):
        eligibility = "eligible_explanation_candidate"
        state = "supported_explanatory_difference"
        sufficient = True
        rationale = "Versioned policy or completed adjudication establishes sufficient explanatory power."
    elif authoritative_sufficiency is False and (explanation_policy_identity or human_adjudication_identity):
        eligibility = "eligible_explanation_candidate"
        state = "difference_not_explanatory_under_contract"
        sufficient = None
        rationale = "Versioned policy or completed adjudication found the difference insufficient to explain divergence."
    else:
        eligibility = "eligible_explanation_candidate"
        state = "explanatory_power_unresolved"
        sufficient = None
        rationale = "Difference is eligible for consideration, but no authority establishes explanatory sufficiency."
    payload = {
        "pair_id": pair_id, "context_dimension": context_dimension,
        "context_difference_identity": context_difference_identity,
        "difference_validated": difference_validated,
        "two_sided_context_resolved": two_sided_context_resolved,
        "explanation_eligibility": eligibility, "explanation_state": state,
        "explanation_policy_identity": explanation_policy_identity,
        "human_adjudication_identity": human_adjudication_identity,
        "sufficient_to_explain_divergence": sufficient,
        "rationale": rationale, "source_refs": source_refs,
    }
    return DivergenceExplanatoryPowerResultV1Candidate(
        **payload,
        identity=layer_identity("divergence_explanatory_power", "divergence_explanatory_power_result_v1_candidate_identity", payload),
    )


def make_formal_judgment_candidate_v1(
    *, pair_id: str, upstream_valid: bool, evidence_independence_valid: bool,
    provenance_adequate: bool, l4b_state: str, l4b_comparable: bool | None,
    explanation_results: list[DivergenceExplanatoryPowerResultV1Candidate],
) -> FormalJudgmentCandidateV1:
    supported = any(x.sufficient_to_explain_divergence is True for x in explanation_results)
    unresolved = sum(x.explanation_state == "explanatory_power_unresolved" for x in explanation_results)
    assessed = bool(explanation_results) and not unresolved
    if not upstream_valid:
        state = "blocked_upstream_regression"; rationale = "A previously validated upstream gate regressed."
    elif not evidence_independence_valid or not provenance_adequate:
        state = "reviewable_context_authority_gap"; rationale = "Evidence independence or provenance is insufficient."
    elif l4b_comparable is False:
        state = "blocked_comparability"; rationale = "Authoritative L4b found the pair non-comparable."
    elif l4b_comparable is None:
        state = "reviewable_context_authority_gap"; rationale = "L4b comparability is not authoritative."
    elif not explanation_results:
        state = "reviewable_divergence_explanation_unresolved"; rationale = "No authoritative divergence-explanation assessment is available."
    elif supported:
        state = "not_confirmed_context_explained"; rationale = "A sufficient authoritative Context explanation prevents confirmation."
    elif unresolved:
        state = "reviewable_divergence_explanation_unresolved"; rationale = "Eligible Context differences lack explanatory-power authority."
    else:
        state = "formal_conflict_candidate_confirmed"; rationale = "All formal gates passed and explanation assessment found no sufficient explanation."
    payload = {
        "pair_id": pair_id, "upstream_valid": upstream_valid,
        "evidence_independence_valid": evidence_independence_valid,
        "provenance_adequate": provenance_adequate, "l4b_state": l4b_state,
        "l4b_comparable": l4b_comparable, "divergence_explanation_assessed": assessed,
        "supported_sufficient_context_explanation": supported,
        "unresolved_explanatory_power_count": unresolved,
        "formal_candidate_state": state, "rationale": rationale,
    }
    return FormalJudgmentCandidateV1(
        **payload,
        identity=layer_identity("formal_judgment_candidate", "formal_judgment_candidate_v1_identity", payload),
    )


__all__ = [
    "DivergenceExplanatoryPowerResultV1Candidate", "FormalJudgmentCandidateV1",
    "assess_divergence_explanatory_power_v1", "make_formal_judgment_candidate_v1",
]
