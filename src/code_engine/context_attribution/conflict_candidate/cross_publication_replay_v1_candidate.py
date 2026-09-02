"""Offline, candidate-only gates for cross-publication contradiction replay.

The helpers are domain-neutral.  They require structured direction and explicit
contrast authority; free-text tokens never establish a contradiction here.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..layer_identity import layer_identity
from .contradiction_v2 import compare_result_directions_v2


EvidenceUnitState = Literal[
    "resolved_distinct_unit", "same_unit", "partially_resolved_unit",
    "unit_identity_unresolved",
]
ContrastOrientationState = Literal[
    "contrast_orientation_exact", "contrast_orientation_normalized_deterministically",
    "contrast_orientation_unresolved", "contrast_semantics_incompatible",
]
OutcomeDirection = Literal[
    "supports_higher_outcome", "supports_lower_outcome",
    "no_supported_difference", "direction_unresolved",
]
QualificationState = Literal[
    "qualified_scientific_candidate", "reviewable_result_orientation",
    "reviewable_evidence_unit_independence", "blocked_not_contradictory",
    "blocked_proposition", "blocked_contrast_orientation",
    "blocked_result_semantics", "blocked_duplicate_or_same_unit",
]


class StrictCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScientificEvidenceUnitV1(StrictCandidateModel):
    schema_version: Literal["scientific_evidence_unit_v1"] = "scientific_evidence_unit_v1"
    evidence_unit_id: str
    publication_id: str
    study_id: str | None = None
    cohort_id: str | None = None
    experiment_or_analysis_unit_id: str
    observation_id: str
    measurement_result_unit_id: str
    evidence_span_ids: list[str]
    unit_identity_state: EvidenceUnitState
    identity_basis: list[str]
    source_refs: list[str]
    candidate_only: Literal[True] = True
    historical_object_modified: Literal[False] = False


class ObservationalContrastOrientationV1(StrictCandidateModel):
    schema_version: Literal["observational_contrast_orientation_v1"] = "observational_contrast_orientation_v1"
    observation_id: str
    raw_group_a: str | None
    raw_group_b: str | None
    normalized_group_a: str | None
    normalized_group_b: str | None
    canonical_orientation: Literal["higher_trib3_vs_lower_trib3"] | None
    source_order_reversed_for_canonical_orientation: bool = False
    orientation_state: ContrastOrientationState
    explicit_authority_refs: list[str] = Field(default_factory=list)
    raw_arm_order_used_as_result_direction: Literal[False] = False
    free_text_result_inference_used: Literal[False] = False


class ObservationalOutcomeOrientationV1(StrictCandidateModel):
    schema_version: Literal["observational_outcome_orientation_v1"] = "observational_outcome_orientation_v1"
    observation_id: str
    endpoint_family: str
    result_representation: Literal["survival", "hazard_or_risk", "other", "unresolved"]
    structured_direction_raw: str | None
    canonical_contrast_orientation: str | None
    result_orientation: OutcomeDirection
    orientation_state: Literal["result_orientation_resolved", "result_orientation_unresolved", "result_semantics_incompatible"]
    deterministic_authority_refs: list[str] = Field(default_factory=list)
    hazard_survival_inverse_applied: bool = False
    raw_string_only_decision: Literal[False] = False
    evidence_span_ids: list[str] = Field(default_factory=list)


class ScientificCandidateQualificationV2Candidate(StrictCandidateModel):
    schema_version: Literal["scientific_candidate_qualification_v2_candidate"] = "scientific_candidate_qualification_v2_candidate"
    pair_id: str
    observation_a_id: str
    observation_b_id: str
    evidence_unit_a_id: str
    evidence_unit_b_id: str
    proposition_compatible: bool
    entity_integrity_eligible: bool
    publication_independent: bool
    evidence_unit_independence_state: EvidenceUnitState
    contrast_orientation_state: str
    result_orientation_state_a: str
    result_orientation_state_b: str
    contradiction_state: str
    qualification_state: QualificationState
    qualification_error_codes: list[str] = Field(default_factory=list)
    qualified_for_l4_entry: bool
    qualification_identity: str
    candidate_only: Literal[True] = True
    historical_candidate_modified: Literal[False] = False
    l4_executed: Literal[False] = False

    @model_validator(mode="after")
    def qualified_state_matches_l4_entry(self):
        if self.qualified_for_l4_entry != (self.qualification_state == "qualified_scientific_candidate"):
            raise ValueError("qualified_l4_entry_state_mismatch")
        return self


def normalize_observational_contrast_v1(
    *, observation_id: str, group_a: str | None, group_b: str | None,
    structured_group_a_state: Literal["higher", "lower", "unknown"] | None,
    structured_group_b_state: Literal["higher", "lower", "unknown"] | None,
    explicit_authority_refs: list[str],
) -> ObservationalContrastOrientationV1:
    """Orient a comparison only from explicit structured group-state authority."""
    if structured_group_a_state == "higher" and structured_group_b_state == "lower" and explicit_authority_refs:
        state: ContrastOrientationState = (
            "contrast_orientation_exact"
            if group_a and group_b and "high" in group_a.casefold() and "low" in group_b.casefold()
            else "contrast_orientation_normalized_deterministically"
        )
        normalized_a, normalized_b, orientation, reversed_order = "higher TRIB3", "lower TRIB3", "higher_trib3_vs_lower_trib3", False
    elif structured_group_a_state == "lower" and structured_group_b_state == "higher" and explicit_authority_refs:
        state = "contrast_orientation_normalized_deterministically"
        normalized_a, normalized_b, orientation, reversed_order = "higher TRIB3", "lower TRIB3", "higher_trib3_vs_lower_trib3", True
    elif {structured_group_a_state, structured_group_b_state} == {"higher", "lower"}:
        state = "contrast_orientation_unresolved"
        normalized_a = normalized_b = orientation = None; reversed_order = False
    elif structured_group_a_state == structured_group_b_state and structured_group_a_state in {"higher", "lower"}:
        state = "contrast_semantics_incompatible"
        normalized_a = normalized_b = orientation = None; reversed_order = False
    else:
        state = "contrast_orientation_unresolved"
        normalized_a = normalized_b = orientation = None; reversed_order = False
    return ObservationalContrastOrientationV1(
        observation_id=observation_id, raw_group_a=group_a, raw_group_b=group_b,
        normalized_group_a=normalized_a, normalized_group_b=normalized_b,
        canonical_orientation=orientation, source_order_reversed_for_canonical_orientation=reversed_order,
        orientation_state=state,
        explicit_authority_refs=explicit_authority_refs,
    )


def orient_observational_outcome_v1(
    *, observation_id: str, endpoint_family: str, result_representation: str,
    structured_direction: str | None, contrast: ObservationalContrastOrientationV1,
    evidence_span_ids: list[str], hazard_survival_inverse_authority: str | None = None,
) -> ObservationalOutcomeOrientationV1:
    """Project direction after contrast orientation, with hazard inversion fail-closed."""
    resolved_contrast = contrast.orientation_state in {
        "contrast_orientation_exact", "contrast_orientation_normalized_deterministically"
    }
    direction = structured_direction
    if contrast.source_order_reversed_for_canonical_orientation:
        direction = {"positive": "negative", "negative": "positive", "neutral": "neutral"}.get(direction)
    inverse = False
    authority = [*contrast.explicit_authority_refs, "contradiction_signal_v2:structured_direction_policy"]
    if not resolved_contrast or endpoint_family != "clinical_outcome":
        result, state = "direction_unresolved", "result_orientation_unresolved"
    elif result_representation == "hazard_or_risk":
        if not hazard_survival_inverse_authority:
            result, state = "direction_unresolved", "result_orientation_unresolved"
        else:
            inverse = True
            authority.append(hazard_survival_inverse_authority)
            result = {"positive": "supports_lower_outcome", "negative": "supports_higher_outcome"}.get(direction, "direction_unresolved")
            state = "result_orientation_resolved" if result != "direction_unresolved" else "result_orientation_unresolved"
    elif result_representation != "survival":
        result, state = "direction_unresolved", "result_semantics_incompatible"
    else:
        result = {"positive": "supports_higher_outcome", "negative": "supports_lower_outcome",
                  "neutral": "no_supported_difference"}.get(direction, "direction_unresolved")
        state = "result_orientation_resolved" if result != "direction_unresolved" else "result_orientation_unresolved"
    return ObservationalOutcomeOrientationV1(
        observation_id=observation_id, endpoint_family=endpoint_family,
        result_representation=result_representation, structured_direction_raw=structured_direction,
        canonical_contrast_orientation=contrast.canonical_orientation,
        result_orientation=result, orientation_state=state,
        deterministic_authority_refs=authority, hazard_survival_inverse_applied=inverse,
        evidence_span_ids=evidence_span_ids,
    )


def compare_observational_outcomes_v1(
    a: ObservationalOutcomeOrientationV1, b: ObservationalOutcomeOrientationV1,
) -> Literal["same_direction", "opposing_direction", "result_relation_unresolved", "result_semantics_incompatible"]:
    if "result_semantics_incompatible" in {a.orientation_state, b.orientation_state}:
        return "result_semantics_incompatible"
    if "result_orientation_unresolved" in {a.orientation_state, b.orientation_state}:
        return "result_relation_unresolved"
    mapped = {
        "supports_higher_outcome": "positive", "supports_lower_outcome": "negative",
        "no_supported_difference": "neutral", "direction_unresolved": None,
    }
    relation = compare_result_directions_v2(mapped[a.result_orientation], mapped[b.result_orientation])
    return "opposing_direction" if relation == "opposed" else "same_direction" if relation == "same" else "result_relation_unresolved"


def qualify_scientific_candidate_v2(
    *, pair_id: str, observation_a_id: str, observation_b_id: str,
    evidence_unit_a_id: str, evidence_unit_b_id: str,
    proposition_compatible: bool, entity_integrity_eligible: bool,
    publication_independent: bool, evidence_unit_independence_state: EvidenceUnitState,
    contrast_orientation_state: str, result_orientation_state_a: str,
    result_orientation_state_b: str, contradiction_state: str,
    representative_evidence_pair: bool,
) -> ScientificCandidateQualificationV2Candidate:
    errors: list[str] = []
    if not proposition_compatible or not entity_integrity_eligible:
        state: QualificationState = "blocked_proposition"; errors.append("upstream_proposition_or_entity_gate_failed")
    elif not publication_independent or evidence_unit_independence_state in {"partially_resolved_unit", "unit_identity_unresolved"}:
        state = "reviewable_evidence_unit_independence"; errors.append("evidence_unit_independence_unresolved")
    elif evidence_unit_independence_state == "same_unit" or not representative_evidence_pair:
        state = "blocked_duplicate_or_same_unit"; errors.append("duplicate_evidence_unit_pair")
    elif contrast_orientation_state not in {"contrast_orientation_exact", "contrast_orientation_normalized_deterministically"}:
        state = "blocked_contrast_orientation"; errors.append("contrast_orientation_not_resolved")
    elif "result_semantics_incompatible" in {result_orientation_state_a, result_orientation_state_b}:
        state = "blocked_result_semantics"; errors.append("result_semantics_incompatible")
    elif contradiction_state == "result_relation_unresolved":
        state = "reviewable_result_orientation"; errors.append("existing_contradiction_direction_contract_unresolved")
    elif contradiction_state != "opposing_direction":
        state = "blocked_not_contradictory"; errors.append("resolved_results_not_opposed")
    else:
        state = "qualified_scientific_candidate"
    basis = {
        "pair_id": pair_id, "observation_a_id": observation_a_id, "observation_b_id": observation_b_id,
        "evidence_unit_a_id": evidence_unit_a_id, "evidence_unit_b_id": evidence_unit_b_id,
        "proposition_compatible": proposition_compatible, "entity_integrity_eligible": entity_integrity_eligible,
        "publication_independent": publication_independent,
        "evidence_unit_independence_state": evidence_unit_independence_state,
        "contrast_orientation_state": contrast_orientation_state,
        "result_orientation_state_a": result_orientation_state_a,
        "result_orientation_state_b": result_orientation_state_b,
        "contradiction_state": contradiction_state, "qualification_state": state,
        "qualification_error_codes": errors, "qualified_for_l4_entry": state == "qualified_scientific_candidate",
    }
    return ScientificCandidateQualificationV2Candidate(
        **basis,
        qualification_identity=layer_identity(
            "scientific_candidate_qualification", "scientific_candidate_qualification_v2_candidate_identity_v1", basis
        ),
    )


__all__ = [
    "ScientificEvidenceUnitV1", "ObservationalContrastOrientationV1",
    "ObservationalOutcomeOrientationV1", "ScientificCandidateQualificationV2Candidate",
    "normalize_observational_contrast_v1", "orient_observational_outcome_v1",
    "compare_observational_outcomes_v1", "qualify_scientific_candidate_v2",
]
