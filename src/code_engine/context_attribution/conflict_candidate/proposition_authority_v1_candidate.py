"""Candidate-only proposition authority profiles and deterministic recovery.

This module is deliberately narrower than conflict generation.  It evaluates
minimum authority for evidence-family-specific propositions and records exact,
offline recovery sidecars without modifying the source signature, Experimental
Core records, Entity Integrity decisions, or historical candidates.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..claim_alignment.scientific_proposition_v1_candidate import (
    MEASUREMENT_PROPERTY_FAMILY_V1,
)


PropositionFieldV1 = Literal[
    "subject_identity",
    "relation_effect_family",
    "object_target_identity",
    "measurement_target_identity",
    "measurement_property_semantic_family",
    "result_semantic_family",
    "intervention_proposition",
    "causal_evidential_mode",
    "experimental_contrast",
    "assay_method",
    "unit_representation",
    "granularity_qualifiers",
]
AuthorityFieldStateV1 = Literal["resolved", "unresolved", "not_applicable"]
EntityRoleStateV1 = Literal[
    "valid",
    "unresolved",
    "invalid",
    "historical_cleaner_integrity_block",
    "noncritical_warning",
]


class StrictCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MinimumScientificPropositionProfileV1(StrictCandidateModel):
    """Minimum proposition identity contract for one repository evidence family."""

    schema_version: Literal[
        "minimum_scientific_proposition_profile_v1"
    ] = "minimum_scientific_proposition_profile_v1"
    profile_id: Literal[
        "interventional_effect",
        "observational_association",
        "descriptive_observation",
    ]
    observation_types: list[str]
    required_fields: list[PropositionFieldV1]
    compatibility_qualifiers: list[PropositionFieldV1] = Field(default_factory=list)
    optional_fields: list[PropositionFieldV1] = Field(default_factory=list)
    not_applicable_fields: list[PropositionFieldV1] = Field(default_factory=list)
    required_entity_roles: list[Literal[
        "subject", "object_target", "measurement_target", "intervention_target"
    ]]
    required_measurement_semantics: list[str]
    required_result_semantics: list[str]
    required_intervention_semantics: list[str] = Field(default_factory=list)
    required_causal_evidential_mode: str
    required_contrast_semantics: list[str] = Field(default_factory=list)
    profile_basis: list[str]
    direction_required_for_identity: Literal[False] = False
    candidate_only: Literal[True] = True

    @model_validator(mode="after")
    def field_roles_are_disjoint(self):
        groups = (
            self.required_fields,
            self.compatibility_qualifiers,
            self.optional_fields,
            self.not_applicable_fields,
        )
        flattened = [field for group in groups for field in group]
        if len(flattened) != len(set(flattened)):
            raise ValueError("proposition_profile_field_roles_overlap")
        if "causal_evidential_mode" not in self.required_fields:
            raise ValueError("causal_evidential_mode_must_be_required")
        if self.profile_id == "interventional_effect" and (
            "intervention_proposition" not in self.required_fields
        ):
            raise ValueError("interventional_profile_requires_intervention")
        return self


class PropositionSufficiencyAssessmentV1(StrictCandidateModel):
    schema_version: Literal[
        "proposition_sufficiency_assessment_v1"
    ] = "proposition_sufficiency_assessment_v1"
    observation_id: str
    profile_id: str
    field_states: dict[str, AuthorityFieldStateV1]
    unresolved_required_fields: list[str] = Field(default_factory=list)
    qualifier_warnings: list[str] = Field(default_factory=list)
    blocking_entity_roles: list[str] = Field(default_factory=list)
    noncritical_entity_warnings: list[str] = Field(default_factory=list)
    minimum_profile_satisfied: bool
    proposition_readiness_state: Literal[
        "minimum_sufficient", "reviewable", "blocked", "not_applicable"
    ]
    direction_used_for_identity: Literal[False] = False
    universal_signature_modified: Literal[False] = False
    entity_gate_modified: Literal[False] = False


class PropositionAuthorityRecoveryV1(StrictCandidateModel):
    """Traceable recovery result for one prior missing-authority record."""

    schema_version: Literal[
        "proposition_authority_recovery_v1"
    ] = "proposition_authority_recovery_v1"
    recovery_id: str
    observation_id: str
    prior_authority_category: str
    missing_fields: list[str]
    source_fields: list[str] = Field(default_factory=list)
    existing_authority_refs: list[str] = Field(default_factory=list)
    deterministic_transformation: str
    recovered_values: dict[str, Any] = Field(default_factory=dict)
    authority_class: Literal[
        "validated_structured_linkage",
        "exact_local_alias",
        "existing_semantic_contract",
        "profile_not_applicable",
        "unresolved_existing_authority",
    ]
    recovery_state: Literal[
        "recovered", "partially_recovered", "unresolved", "not_applicable"
    ]
    unresolved_after_recovery: Literal[
        "source_value_absent",
        "source_scope_insufficient",
        "canonical_identity_unresolved",
        "semantic_family_unresolved",
        "ambiguous",
        "requires_future_extraction",
        "requires_human_review",
        "not_applicable",
        "none",
    ]
    confidence: Literal["deterministic_exact", "not_scored"]
    counted_as_recovery_candidate: bool
    candidate_only: Literal[True] = True
    historical_object_modified: Literal[False] = False
    fuzzy_matching_used: Literal[False] = False
    llm_used: Literal[False] = False
    provider_used: Literal[False] = False

    @model_validator(mode="after")
    def recovery_has_traceable_authority(self):
        if self.recovery_state in {"recovered", "partially_recovered"}:
            if not self.recovered_values or not self.existing_authority_refs:
                raise ValueError("recovery_requires_value_and_authority_reference")
            if self.confidence != "deterministic_exact":
                raise ValueError("recovery_requires_deterministic_exact_confidence")
        if self.recovery_state == "not_applicable" and self.counted_as_recovery_candidate:
            raise ValueError("not_applicable_is_not_a_recovery_candidate")
        return self


class ObservationScientificReadinessAxesV1(StrictCandidateModel):
    schema_version: Literal[
        "observation_scientific_readiness_axes_v1"
    ] = "observation_scientific_readiness_axes_v1"
    observation_id: str
    experimental_core_reuse_state: str
    proposition_readiness_state: Literal[
        "minimum_sufficient", "reviewable", "blocked", "not_applicable"
    ]
    entity_integrity_state: str
    provenance_state: str
    axes_independent: Literal[True] = True
    candidate_only: Literal[True] = True


def repository_proposition_profiles_v1() -> tuple[MinimumScientificPropositionProfileV1, ...]:
    """Return only profiles justified by current Experimental Core types."""
    common_required: list[PropositionFieldV1] = [
        "subject_identity",
        "relation_effect_family",
        "object_target_identity",
        "measurement_target_identity",
        "measurement_property_semantic_family",
        "result_semantic_family",
        "causal_evidential_mode",
    ]
    qualifiers: list[PropositionFieldV1] = [
        "assay_method", "unit_representation", "granularity_qualifiers",
    ]
    basis = [
        "StructuredExperimentalObservationRevision.observation_type",
        "CAUSAL_MODE_FAMILY_V1",
        "ExperimentalFactorRecord/MeasurementRecord/ObservedResultRecord linkage",
    ]
    return (
        MinimumScientificPropositionProfileV1(
            profile_id="interventional_effect",
            observation_types=["interventional_experiment"],
            required_fields=[
                *common_required, "intervention_proposition", "experimental_contrast",
            ],
            compatibility_qualifiers=qualifiers,
            required_entity_roles=[
                "subject", "object_target", "measurement_target", "intervention_target",
            ],
            required_measurement_semantics=[
                "canonical measurement target", "controlled measured-property family",
            ],
            required_result_semantics=["controlled result representation family"],
            required_intervention_semantics=[
                "intervention mode", "factor family", "canonical intervention target",
            ],
            required_causal_evidential_mode="interventional_effect",
            required_contrast_semantics=["experimental_vs_reference"],
            profile_basis=basis,
        ),
        MinimumScientificPropositionProfileV1(
            profile_id="observational_association",
            observation_types=["observational_comparison"],
            required_fields=[*common_required, "experimental_contrast"],
            compatibility_qualifiers=qualifiers,
            not_applicable_fields=["intervention_proposition"],
            required_entity_roles=["subject", "object_target", "measurement_target"],
            required_measurement_semantics=[
                "canonical measurement target", "controlled measured-property family",
            ],
            required_result_semantics=["controlled result representation family"],
            required_causal_evidential_mode="observational_association",
            required_contrast_semantics=["observational_group_vs_reference"],
            profile_basis=basis,
        ),
        MinimumScientificPropositionProfileV1(
            profile_id="descriptive_observation",
            observation_types=["descriptive_measurement"],
            required_fields=common_required,
            compatibility_qualifiers=qualifiers,
            not_applicable_fields=["intervention_proposition", "experimental_contrast"],
            required_entity_roles=["subject", "object_target", "measurement_target"],
            required_measurement_semantics=[
                "canonical measurement target", "controlled measured-property family",
            ],
            required_result_semantics=["controlled result representation family"],
            required_causal_evidential_mode="descriptive_observation",
            profile_basis=basis,
        ),
    )


def profile_for_observation_type_v1(
    observation_type: str,
) -> MinimumScientificPropositionProfileV1 | None:
    return next(
        (
            profile for profile in repository_proposition_profiles_v1()
            if observation_type in profile.observation_types
        ),
        None,
    )


def measurement_semantic_family_v1(measurement_semantic_level: str) -> str | None:
    """Map only an exact existing controlled value; lexical similarity is forbidden."""
    return MEASUREMENT_PROPERTY_FAMILY_V1.get(measurement_semantic_level)


def normalize_exact_local_alias_v1(value: Any) -> str | None:
    """Apply equality-preserving case/whitespace normalization only."""
    if value is None:
        return None
    normalized = " ".join(str(value).casefold().split())
    return normalized or None


def recover_exact_local_alias_v1(
    value: Any,
    aliases: Mapping[str, str],
) -> tuple[Literal["recovered", "unresolved", "ambiguous"], str | None]:
    """Resolve an exact local alias only when it identifies one canonical value."""
    normalized = normalize_exact_local_alias_v1(value)
    if normalized is None:
        return "unresolved", None
    matches = {
        canonical_identity
        for alias, canonical_identity in aliases.items()
        if normalize_exact_local_alias_v1(alias) == normalized
    }
    if len(matches) == 1:
        return "recovered", next(iter(matches))
    if len(matches) > 1:
        return "ambiguous", None
    return "unresolved", None


def evaluate_minimum_proposition_sufficiency_v1(
    *,
    observation_id: str,
    profile: MinimumScientificPropositionProfileV1,
    field_states: Mapping[str, AuthorityFieldStateV1],
    entity_role_states: Mapping[str, EntityRoleStateV1],
) -> PropositionSufficiencyAssessmentV1:
    """Evaluate a profile without interpreting contradiction direction."""
    normalized_states = {
        field: field_states.get(field, "unresolved") for field in profile.required_fields
    }
    normalized_states.update({
        field: "not_applicable" for field in profile.not_applicable_fields
    })
    unresolved = sorted(
        field for field in profile.required_fields
        if normalized_states[field] != "resolved"
    )
    qualifier_warnings = sorted(
        field for field in profile.compatibility_qualifiers
        if field_states.get(field, "unresolved") == "unresolved"
    )
    blocking_entity_roles = sorted(
        role for role in profile.required_entity_roles
        if entity_role_states.get(role, "unresolved") in {
            "unresolved", "invalid", "historical_cleaner_integrity_block",
        }
    )
    noncritical_warnings = sorted(
        role for role, state in entity_role_states.items()
        if role not in profile.required_entity_roles and state == "noncritical_warning"
    )
    satisfied = not unresolved and not blocking_entity_roles
    readiness = (
        "minimum_sufficient" if satisfied else
        "blocked" if blocking_entity_roles else
        "reviewable"
    )
    return PropositionSufficiencyAssessmentV1(
        observation_id=observation_id,
        profile_id=profile.profile_id,
        field_states=normalized_states,
        unresolved_required_fields=unresolved,
        qualifier_warnings=qualifier_warnings,
        blocking_entity_roles=blocking_entity_roles,
        noncritical_entity_warnings=noncritical_warnings,
        minimum_profile_satisfied=satisfied,
        proposition_readiness_state=readiness,
    )
