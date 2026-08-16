"""Candidate-only, blocker-closure semantics for Experimental Context readiness.

The module deliberately does not invent field requirements.  Callers must
provide a versioned requirement assignment backed by an actual consumer
contract; an unknown requirement blocks a ready classification.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from .closure_v2 import ContextAuthorityV2, ValueStateV2, stable
from .models import AssetProvenance, StrictContextAsset


RequirementLevel = Literal[
    "required", "conditionally_required", "optional", "not_applicable",
    "unknown_requirement",
]
ReadinessV3Status = Literal[
    "ready_direct", "ready_with_safe_inheritance", "ready_with_derived_context",
    "ready_with_optional_unresolved", "reviewable_required_context_gap",
    "blocked_required_context_missing", "blocked_required_context_ambiguous",
    "blocked_source_scope", "requirement_profile_unresolved", "not_context_sensitive",
]


class ExperimentalContextRequirementProfileV1(StrictContextAsset):
    profile_id: str
    downstream_consumer: str
    consumer_contract_identity: str
    evidence_family: str | None = None
    observation_type: str | None = None
    comparison_type: str | None = None
    experimental_design: str | None = None
    measurement_type: str | None = None
    arm_structure: str | None = None
    field_requirements: dict[str, RequirementLevel]
    requirement_basis_refs: list[str] = Field(min_length=1)
    candidate_only: Literal[True] = True
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["experimental_context_requirement_profile_v1"] = (
        "experimental_context_requirement_profile_v1"
    )


class ContextFieldRequirementAssignmentV1(StrictContextAsset):
    observation_identity: str
    profile_id: str
    field_name: str
    requirement: RequirementLevel
    requirement_basis_refs: list[str] = Field(min_length=1)
    value_state: ValueStateV2
    authority: ContextAuthorityV2
    inheritance_path: list[str] = Field(default_factory=list)
    source_scope_sufficient: bool | None = None
    competing_source_supported_value_count: int = Field(default=0, ge=0)
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["context_field_requirement_assignment_v1"] = (
        "context_field_requirement_assignment_v1"
    )

    @model_validator(mode="after")
    def inherited_requires_path(self):
        if self.authority == "scope_inherited" and len(self.inheritance_path) < 2:
            raise ValueError("inherited_requirement_assignment_requires_path")
        return self


class ExperimentalContextReadinessV3Candidate(StrictContextAsset):
    observation_identity: str
    requirement_profile_ids: list[str] = Field(min_length=1)
    status: ReadinessV3Status
    required_field_count: int = Field(ge=0)
    optional_field_count: int = Field(ge=0)
    unknown_requirement_count: int = Field(ge=0)
    required_blocker_fields: list[str] = Field(default_factory=list)
    ambiguous_blocker_fields: list[str] = Field(default_factory=list)
    source_scope_blocker_fields: list[str] = Field(default_factory=list)
    optional_unresolved_fields: list[str] = Field(default_factory=list)
    candidate_only: Literal[True] = True
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["experimental_context_readiness_v3_candidate"] = (
        "experimental_context_readiness_v3_candidate"
    )


def build_readiness_v3(
    *, observation_identity: str,
    assignments: list[ContextFieldRequirementAssignmentV1],
    provenance: AssetProvenance,
) -> ExperimentalContextReadinessV3Candidate:
    if not assignments:
        raise ValueError("readiness_v3_requires_field_assignments")
    unknown = [x.field_name for x in assignments if x.requirement == "unknown_requirement"]
    required = [x for x in assignments if x.requirement in {"required", "conditionally_required"}]
    optional = [x for x in assignments if x.requirement == "optional"]
    ambiguous = [x.field_name for x in required if x.value_state == "ambiguous"]
    source_blocked = [
        x.field_name for x in required
        if x.source_scope_sufficient is False and x.value_state != "present"
    ]
    missing = [
        x.field_name for x in required
        if x.value_state in {"explicit_unknown", "not_reported", "unavailable", "unresolved"}
    ]
    optional_unresolved = [x.field_name for x in optional if x.value_state != "present"]
    applicable = [x for x in assignments if x.requirement != "not_applicable"]
    if unknown:
        status: ReadinessV3Status = "requirement_profile_unresolved"
    elif ambiguous:
        status = "blocked_required_context_ambiguous"
    elif source_blocked:
        status = "blocked_source_scope"
    elif missing:
        status = "blocked_required_context_missing"
    elif not applicable:
        status = "not_context_sensitive"
    elif optional_unresolved:
        status = "ready_with_optional_unresolved"
    elif any(x.authority == "scope_inherited" for x in applicable):
        status = "ready_with_safe_inheritance"
    elif any(x.authority == "deterministically_derived" for x in applicable):
        status = "ready_with_derived_context"
    else:
        status = "ready_direct"
    payload: dict[str, Any] = {
        "observation_identity": observation_identity,
        "requirement_profile_ids": sorted({x.profile_id for x in assignments}),
        "status": status,
        "required_field_count": len(required),
        "optional_field_count": len(optional),
        "unknown_requirement_count": len(unknown),
        "required_blocker_fields": sorted(set(missing)),
        "ambiguous_blocker_fields": sorted(set(ambiguous)),
        "source_scope_blocker_fields": sorted(set(source_blocked)),
        "optional_unresolved_fields": sorted(set(optional_unresolved)),
        "candidate_only": True,
        "identity": "",
        "provenance": provenance,
    }
    payload["identity"] = stable("experimental_context_readiness_v3_candidate", payload)
    return ExperimentalContextReadinessV3Candidate.model_validate(payload)


def classify_unresolved(
    assignment: ContextFieldRequirementAssignmentV1,
) -> Literal[
    "required_unresolved", "optional_unresolved", "not_applicable",
    "source_not_reported", "source_scope_insufficient",
    "ambiguous_competing_context", "normalization_unresolved", "unknown_requirement",
]:
    if assignment.requirement == "unknown_requirement":
        return "unknown_requirement"
    if assignment.requirement == "not_applicable":
        return "not_applicable"
    if assignment.value_state == "ambiguous" and assignment.competing_source_supported_value_count >= 2:
        return "ambiguous_competing_context"
    if assignment.source_scope_sufficient is False:
        return "source_scope_insufficient"
    if assignment.value_state == "not_reported" and assignment.source_scope_sufficient is True:
        return "source_not_reported"
    if assignment.requirement in {"required", "conditionally_required"}:
        return "required_unresolved"
    return "optional_unresolved"
