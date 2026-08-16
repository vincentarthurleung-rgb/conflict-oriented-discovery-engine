"""Scope-safe Experimental Context closure contracts.

The gate is deliberately conservative.  It never treats document proximity,
wording similarity, or a missing child value as proof of inheritance.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from .identities import context_asset_identity
from .models import AssetProvenance, StrictContextAsset


ScopeType = Literal["document", "experiment", "arm", "observation", "measurement", "result"]
ValueStateV2 = Literal[
    "present", "explicit_unknown", "not_reported", "unavailable",
    "ambiguous", "unresolved", "not_applicable",
]
ContextAuthorityV2 = Literal[
    "direct_explicit", "direct_structured", "scope_inherited",
    "deterministically_derived", "candidate_only", "unresolved",
]
Compatibility = Literal["same", "compatible", "not_applicable", "unknown", "conflict"]


def stable(kind: str, payload: dict[str, Any]) -> str:
    return context_asset_identity(kind, {k: v for k, v in payload.items() if k not in {"identity", "provenance"}})


class ContextScopeRefV1(StrictContextAsset):
    scope_type: ScopeType
    scope_id: str
    parent_scope_type: ScopeType | None = None
    parent_scope_id: str | None = None
    source_document_id: str
    source_evidence_refs: list[str] = Field(default_factory=list)
    value_state: ValueStateV2
    authority: ContextAuthorityV2
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["context_scope_ref_v1"] = "context_scope_ref_v1"

    @model_validator(mode="after")
    def parent_pair(self):
        if (self.parent_scope_type is None) != (self.parent_scope_id is None):
            raise ValueError("parent scope type/id must be supplied together")
        return self


class ContextFieldValueV2(StrictContextAsset):
    field_name: str
    semantic_category: str
    value_raw: Any = None
    value_normalized: Any = None
    value_state: ValueStateV2
    scope_type: ScopeType
    scope_id: str
    authority: ContextAuthorityV2
    source_evidence_refs: list[str] = Field(default_factory=list)
    source_document_id: str
    inheritance_path: list[str] = Field(default_factory=list)
    derivation_rule_id: str | None = None
    normalization_rule_id: str | None = None
    normalization_status: Literal["resolved", "unresolved", "not_requested"]
    validation_status: Literal["validated", "candidate", "blocked", "unresolved"]
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["context_field_value_v2"] = "context_field_value_v2"

    @model_validator(mode="after")
    def authority_evidence(self):
        if self.authority in {"direct_explicit", "direct_structured"} and not self.source_evidence_refs:
            raise ValueError("direct context requires source evidence refs")
        if self.authority == "scope_inherited" and len(self.inheritance_path) < 2:
            raise ValueError("inherited context requires a parent-to-child path")
        if self.authority == "deterministically_derived" and not self.derivation_rule_id:
            raise ValueError("derived context requires a rule identity")
        if self.normalization_status == "unresolved" and self.value_normalized is not None:
            raise ValueError("unresolved normalization cannot assert a normalized value")
        if self.value_state != "present" and self.value_normalized is not None:
            raise ValueError("non-present state cannot assert a normalized value")
        return self


class ContextScopeCompatibilityProofV1(StrictContextAsset):
    same_document: bool
    experiment_scope: Compatibility
    arm_identity: Compatibility
    cohort: Compatibility
    genotype: Compatibility
    treatment: Compatibility
    dose: Compatibility
    timepoint: Compatibility
    tissue_or_model: Compatibility
    measurement_scope: Compatibility
    contradictory_sibling_scope: bool = False
    competing_arm: bool = False
    multiple_cohorts: bool = False
    multiple_timepoints: bool = False
    multiple_doses: bool = False
    multiple_treatments: bool = False
    ambiguous_group_definition: bool = False
    wording_similarity_only: bool = False
    proximity_only: bool = False
    schema_version: Literal["context_scope_compatibility_proof_v1"] = (
        "context_scope_compatibility_proof_v1"
    )


class ContextInheritanceCandidateV1(StrictContextAsset):
    field_value_identity: str
    field_name: str
    parent_scope_type: ScopeType
    parent_scope_id: str
    child_scope_type: ScopeType
    child_scope_id: str
    field_scope_sensitive: bool
    proof: ContextScopeCompatibilityProofV1
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["context_inheritance_candidate_v1"] = "context_inheritance_candidate_v1"


class ContextScopeClosureDecisionV1(StrictContextAsset):
    candidate_identity: str
    status: Literal["accepted", "rejected"]
    reason_codes: list[str]
    inheritance_path: list[str]
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["experimental_context_scope_closure_gate_v1"] = (
        "experimental_context_scope_closure_gate_v1"
    )


def scope_closure_gate(candidate: ContextInheritanceCandidateV1) -> ContextScopeClosureDecisionV1:
    proof = candidate.proof
    reasons: list[str] = []
    if not proof.same_document:
        reasons.append("cross_document_blocked")
    if proof.experiment_scope not in {"same", "compatible"}:
        reasons.append("experiment_scope_not_closed")
    if candidate.field_scope_sensitive and proof.arm_identity not in {"same", "compatible"}:
        reasons.append("arm_scope_not_closed")
    for name in ("cohort", "genotype", "treatment", "dose", "timepoint", "tissue_or_model", "measurement_scope"):
        state = getattr(proof, name)
        if state in {"unknown", "conflict"}:
            reasons.append(f"{name}_not_compatible")
    flags = {
        "contradictory_sibling_scope": proof.contradictory_sibling_scope,
        "competing_arm": proof.competing_arm,
        "multiple_cohorts": proof.multiple_cohorts,
        "multiple_timepoints": proof.multiple_timepoints,
        "multiple_doses": proof.multiple_doses,
        "multiple_treatments": proof.multiple_treatments,
        "ambiguous_group_definition": proof.ambiguous_group_definition,
        "wording_similarity_only": proof.wording_similarity_only,
        "proximity_only": proof.proximity_only,
    }
    reasons.extend(f"{name}_blocked" for name, enabled in flags.items() if enabled)
    payload = {
        "candidate_identity": candidate.identity,
        "status": "rejected" if reasons else "accepted",
        "reason_codes": reasons,
        "inheritance_path": [candidate.parent_scope_id, candidate.child_scope_id],
        "provenance": candidate.provenance,
    }
    payload["identity"] = stable("experimental_context_scope_closure_gate_v1", payload)
    return ContextScopeClosureDecisionV1.model_validate(payload)


class ExperimentalContextCompositionV2(StrictContextAsset):
    observation_identity: str
    direct_context: list[str] = Field(default_factory=list)
    inherited_context: list[str] = Field(default_factory=list)
    derived_context: list[str] = Field(default_factory=list)
    unresolved_context: list[str] = Field(default_factory=list)
    blocked_inheritance: list[str] = Field(default_factory=list)
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["experimental_context_composition_v2"] = "experimental_context_composition_v2"


class ExperimentalContextReadinessV2Candidate(StrictContextAsset):
    observation_identity: str
    status: Literal[
        "ready_direct", "ready_with_safe_inheritance", "ready_with_derived_context",
        "reviewable_context_gap", "blocked_ambiguous_context", "blocked_source_scope",
        "blocked_required_context_missing", "provider_candidate_nonexecuted", "not_required",
    ]
    direct_field_count: int = Field(ge=0)
    inherited_field_count: int = Field(ge=0)
    derived_field_count: int = Field(ge=0)
    unresolved_field_count: int = Field(ge=0)
    candidate_only: Literal[True] = True
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["experimental_context_readiness_v2_candidate"] = (
        "experimental_context_readiness_v2_candidate"
    )


def readiness_v2(
    *, observation_identity: str, direct: int, inherited: int, derived: int,
    unresolved: int, ambiguous: int = 0, source_scope_blocked: bool = False,
    required_missing: bool = False, provider_candidate: bool = False,
    provenance: AssetProvenance,
) -> ExperimentalContextReadinessV2Candidate:
    if ambiguous:
        status = "blocked_ambiguous_context"
    elif source_scope_blocked:
        status = "blocked_source_scope"
    elif required_missing:
        status = "blocked_required_context_missing"
    elif provider_candidate:
        status = "provider_candidate_nonexecuted"
    elif inherited:
        status = "ready_with_safe_inheritance"
    elif derived:
        status = "ready_with_derived_context"
    elif direct:
        status = "ready_direct"
    else:
        status = "reviewable_context_gap"
    payload = {
        "observation_identity": observation_identity, "status": status,
        "direct_field_count": direct, "inherited_field_count": inherited,
        "derived_field_count": derived, "unresolved_field_count": unresolved,
        "candidate_only": True, "provenance": provenance,
    }
    payload["identity"] = stable("experimental_context_readiness_v2_candidate", payload)
    return ExperimentalContextReadinessV2Candidate.model_validate(payload)


CONTEXT_CLOSURE_MODELS = {
    "context_scope_ref_v1": ContextScopeRefV1,
    "context_field_value_v2": ContextFieldValueV2,
    "context_inheritance_candidate_v1": ContextInheritanceCandidateV1,
    "experimental_context_scope_closure_gate_v1": ContextScopeClosureDecisionV1,
    "experimental_context_composition_v2": ExperimentalContextCompositionV2,
    "experimental_context_readiness_v2_candidate": ExperimentalContextReadinessV2Candidate,
}
