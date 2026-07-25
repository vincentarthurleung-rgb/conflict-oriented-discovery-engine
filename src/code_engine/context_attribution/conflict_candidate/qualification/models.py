from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

QualificationStatus = Literal[
    "qualified", "legacy_preserved", "blocked_alignment", "blocked_signal",
    "insufficient_information", "rejected",
]


class ScientificCandidatePairIdentityV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["scientific_candidate_pair_identity_v1"] = "scientific_candidate_pair_identity_v1"
    endpoint_claim_identity_a: str
    endpoint_claim_identity_b: str
    proposition_core_identity_a: str
    proposition_core_identity_b: str
    observation_pair_ordering_policy: str
    contradiction_signal_type: str
    candidate_scientific_pair_contract_identity: str
    scientific_candidate_pair_identity: str


class ConflictCandidateQualificationV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["conflict_candidate_qualification_v1"] = "conflict_candidate_qualification_v1"
    candidate_id: str
    legacy_candidate_identity: str
    observation_a_id: str
    observation_b_id: str
    endpoint_claim_identity_a: str
    endpoint_claim_identity_b: str
    proposition_core_identity_a: str
    proposition_core_identity_b: str
    claim_alignment_v2_identity: str
    claim_alignment_status: str
    contradiction_signal_v2_identity: str
    contradiction_signal_status: str
    contradiction_signal_structure_valid: bool
    contradiction_signal_schema_valid: bool
    contradiction_signal_validator_valid: bool
    contradiction_signal_provenance_complete: bool
    candidate_generation_policy_identity: str
    qualification_contract_identity: str
    qualification_validator_identity: str
    scientific_candidate_pair_identity: str
    source_lineage: dict[str, Any]
    provenance: dict[str, Any]
    observation_context_readiness_a: str | None = None
    observation_context_readiness_b: str | None = None
    qualification_status: QualificationStatus
    qualification_error_codes: list[str]
    qualified_for_l4: bool
    qualification_identity: str

    @model_validator(mode="after")
    def status_invariants(self):
        if self.qualified_for_l4 != (self.qualification_status == "qualified"):
            raise ValueError("qualified_for_l4_status_mismatch")
        if self.qualification_status == "blocked_alignment" and self.claim_alignment_status == "aligned":
            raise ValueError("blocked_alignment_requires_non_aligned")
        if self.qualification_status == "blocked_signal" and self.claim_alignment_status != "aligned":
            raise ValueError("blocked_signal_requires_aligned")
        if self.qualification_status == "rejected" and not self.qualification_error_codes:
            raise ValueError("rejected_requires_error_codes")
        return self


class QualifiedCandidateAuthoritySidecarV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["qualified_candidate_authority_v1"] = "qualified_candidate_authority_v1"
    candidate_id: str
    legacy_candidate_identity: str
    qualification_identity: str
    authority_status: QualificationStatus
    authority_scope: Literal["future_standard", "legacy_only", "diagnostic_only"]
    lineage_status: Literal["complete", "incomplete", "mismatch"]
    qualified_for_l4: bool
    source_pair_set_unchanged: Literal[True]
    legacy_identity_preserved: Literal[True]
    scientific_pair_identity: str
    identity: str

    @model_validator(mode="after")
    def authority_invariants(self):
        expected = self.authority_status == "qualified"
        if self.qualified_for_l4 != expected:
            raise ValueError("authority_qualification_mismatch")
        if self.authority_scope != ("future_standard" if expected else "legacy_only"):
            raise ValueError("authority_scope_status_mismatch")
        return self


class ContextDifferenceQualificationBindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["context_difference_candidate_qualification_binding_v1"] = (
        "context_difference_candidate_qualification_binding_v1"
    )
    context_difference_identity: str
    candidate_id: str
    candidate_qualification_identity: str
    qualification_status: QualificationStatus
    artifact_valid: bool
    authoritative_for_new_l4: bool
    legacy_diagnostic_only: bool
    binding_identity: str

