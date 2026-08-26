"""Candidate-only semantic authority for the proposition sufficiency frontier."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...normalization.composite_endpoints import decompose_endpoint
from ..claim_alignment.scientific_proposition_v1_candidate import (
    CAUSAL_MODE_FAMILY_V1,
    MEASUREMENT_PROPERTY_FAMILY_V1,
)


BlockerTypeV1 = Literal[
    "semantic_family_unmapped", "projection_missing", "value_absent",
    "ambiguous", "human_scientific_review", "profile_overconstraint",
    "entity_authority_unresolved",
]


class StrictCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PropositionSufficiencyBlockerV1(StrictCandidateModel):
    schema_version: Literal[
        "proposition_sufficiency_blocker_v1"
    ] = "proposition_sufficiency_blocker_v1"
    blocker_id: str
    observation_id: str
    profile: str
    entity_authority: str
    required_field: str
    current_value: object | None = None
    current_semantic_authority: str
    blocker_type: BlockerTypeV1
    component: Literal["measurement", "result", "intervention", "relation", "contrast", "entity", "profile"]
    source_structured_object_refs: list[str] = Field(default_factory=list)
    recoverability: Literal[
        "deterministic_existing_authority", "human_scientific_review",
        "future_extraction_required", "unresolved_no_safe_rule",
    ]
    reason: str
    candidate_only: Literal[True] = True
    free_text_inference_used: Literal[False] = False
    fuzzy_matching_used: Literal[False] = False
    llm_used: Literal[False] = False


class FrontierSemanticRecoveryV1(StrictCandidateModel):
    schema_version: Literal[
        "frontier_semantic_recovery_v1"
    ] = "frontier_semantic_recovery_v1"
    recovery_id: str
    blocker_id: str
    observation_id: str
    required_field: str
    recovery_state: Literal["recovered", "unresolved"]
    recovered_value: object | None = None
    authority_contract: str
    authority_refs: list[str] = Field(default_factory=list)
    deterministic_rule: str
    historical_object_modified: Literal[False] = False
    external_authority_required: Literal[False] = False
    free_text_inference_used: Literal[False] = False
    fuzzy_matching_used: Literal[False] = False
    llm_used: Literal[False] = False
    provider_used: Literal[False] = False

    @model_validator(mode="after")
    def recovered_values_need_authority(self):
        if self.recovery_state == "recovered" and (
            self.recovered_value is None or not self.authority_refs
        ):
            raise ValueError("recovered_frontier_value_requires_existing_authority")
        return self


def deterministic_measurement_property_family_v1(
    measurement_semantic_level: str | None,
    property_or_endpoint: str | None,
) -> tuple[str | None, str]:
    """Resolve only controlled enums or an existing exact endpoint contract."""
    family = MEASUREMENT_PROPERTY_FAMILY_V1.get(measurement_semantic_level or "")
    if family is not None:
        return family, "measurement_property_family_v1"
    if not property_or_endpoint:
        return None, "unresolved"
    endpoint = decompose_endpoint(property_or_endpoint)
    # This is deliberately the only frontier extension: the repository's
    # anchored NON_MOLECULAR_PATTERNS already declares this endpoint type.
    if endpoint.non_molecular_readout and endpoint.endpoint_type == "clinical_outcome":
        return "clinical_outcome", "existing_exact_endpoint_type_contract_v1"
    return None, "unresolved"


def deterministic_result_semantic_family_v1(
    property_family: str | None,
    *,
    has_qualitative: bool,
    has_quantitative: bool,
    direction: object = None,
) -> tuple[str | None, str]:
    """Compose property and representation while excluding direction."""
    del direction
    if property_family is None:
        return None, "unresolved_property_family"
    representation = (
        "mixed_result" if has_qualitative and has_quantitative else
        "qualitative_result" if has_qualitative else
        "quantitative_result" if has_quantitative else None
    )
    if representation is None:
        return None, "unresolved_result_representation"
    return f"{property_family}:{representation}", "result_semantic_family_v1"


def deterministic_relation_effect_family_v1(observation_type: str) -> str | None:
    """Project an existing evidence family without importing polarity."""
    return CAUSAL_MODE_FAMILY_V1.get(observation_type)


def field_is_required_v2_candidate(profile_id: str, field: str) -> bool:
    """Frozen profile necessity result; zero pass count never relaxes a field."""
    common = {
        "subject_identity", "relation_effect_family", "object_target_identity",
        "measurement_target_identity", "measurement_property_semantic_family",
        "result_semantic_family", "causal_evidential_mode",
    }
    if field in common:
        return True
    if field == "intervention_proposition":
        return profile_id == "interventional_effect"
    if field == "experimental_contrast":
        return profile_id in {"interventional_effect", "observational_association"}
    return False
