from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ALIGNMENT_SCHEMA_VERSION = "aligned_claim_group_v1"
ALIGNMENT_VALIDATOR_VERSION = "claim_alignment_validator_v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PropositionDimension(StrictModel):
    dimension: str
    canonical_value: str | None
    resolution_status: Literal["resolved", "unresolved", "not_applicable"]
    basis: str

    @model_validator(mode="after")
    def resolution_contract(self):
        if self.resolution_status == "resolved" and not self.canonical_value:
            raise ValueError("resolved_proposition_dimension_requires_value")
        if self.resolution_status != "resolved" and self.canonical_value is not None:
            raise ValueError("unresolved_proposition_dimension_value_forbidden")
        return self


class CanonicalPropositionSignature(StrictModel):
    """ID-free semantic signature; unresolved dimensions remain explicit."""

    canonical_subject_identity: PropositionDimension
    canonical_relation_identity: PropositionDimension
    canonical_object_endpoint_identity: PropositionDimension
    observation_result_semantic_level: PropositionDimension
    measurement_endpoint_type: PropositionDimension
    outcome_category: PropositionDimension
    intervention_target_identity: PropositionDimension
    direction_interpretation: PropositionDimension
    temporal_interpretation: PropositionDimension
    quantity_unit_compatibility: PropositionDimension


class AlignmentDimension(StrictModel):
    dimension: str
    status: Literal["aligned", "partially_aligned", "unaligned", "unresolved"]
    basis: str


class AlignedClaimGroup(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        title="Aligned Claim Group v1",
        json_schema_extra={
            "$id": "https://conflict-oriented-discovery-engine.local/schemas/aligned_claim_group_v1"
        },
    )

    schema_version: Literal["aligned_claim_group_v1"] = ALIGNMENT_SCHEMA_VERSION
    alignment_id: str
    member_observation_ids: list[str] = Field(min_length=2, max_length=2)
    member_claim_identities: list[str] = Field(min_length=2, max_length=2)
    l2_normalization_identities: list[str] = Field(min_length=2, max_length=2)
    canonical_proposition_signature: CanonicalPropositionSignature
    alignment_status: Literal[
        "aligned", "partially_aligned", "unaligned", "insufficient_information"
    ]
    alignment_basis: list[str] = Field(min_length=1)
    alignment_dimensions: list[AlignmentDimension] = Field(min_length=1)
    unresolved_alignment_dimensions: list[str]
    context_readiness_by_member: dict[str, str]
    provenance: dict[str, Any]
    claim_alignment_identity: str
    validator_version: Literal[
        "claim_alignment_validator_v1"
    ] = ALIGNMENT_VALIDATOR_VERSION
    validation_status: Literal["validated", "rejected"]

    @model_validator(mode="after")
    def unresolved_cannot_be_aligned(self):
        blocking = {
            item.dimension
            for item in self.alignment_dimensions
            if item.status in {"unaligned", "unresolved", "partially_aligned"}
            and item.dimension
            in {
                "canonical_subject_identity",
                "canonical_relation_identity",
                "canonical_object_endpoint_identity",
                "observation_result_semantic_level",
                "measurement_endpoint_type",
            }
        }
        if self.alignment_status == "aligned" and blocking:
            raise ValueError("unresolved_or_partial_critical_dimension_cannot_align")
        return self
