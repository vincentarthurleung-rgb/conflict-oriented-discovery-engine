from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, model_validator

EntryStatus = Literal[
    "ready", "blocked_candidate_unqualified", "blocked_context_a_unavailable",
    "blocked_context_b_unavailable", "blocked_context_both_unavailable",
    "blocked_context_a_unvalidated", "blocked_context_b_unvalidated",
    "blocked_context_both_unvalidated", "blocked_context_identity_mismatch",
    "blocked_endpoint_context_binding_mismatch", "insufficient_information", "rejected",
]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class ContextEndpointAuthority(StrictModel):
    endpoint_role: Literal["a", "b"]
    observation_id: str
    endpoint_claim_identity: str
    context_present: bool
    context_schema_valid: bool
    context_validator_valid: bool
    context_identity_valid: bool
    context_provenance_complete: bool
    endpoint_binding_valid: bool
    context_authority_valid: bool
    observation_context_identity: str | None
    observation_context_status: str
    observation_context_validator_identity: str | None
    observation_context_source_identity: str | None
    source_artifact_path: str
    source_artifact_sha256: str
    validation_audit_valid: bool
    error_codes: list[str]

class ContextDifferenceEntryAuthorizationV1(StrictModel):
    schema_version: Literal["context_difference_entry_authorization_v1"] = "context_difference_entry_authorization_v1"
    candidate_id: str
    scientific_candidate_pair_identity: str
    candidate_qualification_identity: str
    candidate_qualification_status: str
    qualified_candidate_authority_identity: str
    qualified_for_l4_entry_evaluation: bool
    observation_a_id: str
    observation_b_id: str
    endpoint_claim_identity_a: str
    endpoint_claim_identity_b: str
    observation_context_identity_a: str | None
    observation_context_identity_b: str | None
    observation_context_status_a: str
    observation_context_status_b: str
    observation_context_validator_identity_a: str | None
    observation_context_validator_identity_b: str | None
    observation_context_source_identity_a: str | None
    observation_context_source_identity_b: str | None
    endpoint_context_binding_status_a: str
    endpoint_context_binding_status_b: str
    context_gate_policy_identity: str
    entry_status: EntryStatus
    primary_block_reason: str | None
    secondary_block_reasons: list[str]
    ready_for_authoritative_context_difference: bool
    validator_version: Literal["context_difference_entry_authorization_validator_v1"] = "context_difference_entry_authorization_validator_v1"
    provenance: dict[str, Any]
    identity: str

    @model_validator(mode="after")
    def invariants(self):
        if self.ready_for_authoritative_context_difference != (self.entry_status == "ready"):
            raise ValueError("entry_ready_flag_mismatch")
        if self.entry_status == "ready" and (
            self.candidate_qualification_status != "qualified"
            or not self.observation_context_identity_a or not self.observation_context_identity_b
            or self.observation_context_status_a != "validated"
            or self.observation_context_status_b != "validated"
        ):
            raise ValueError("ready_requires_qualified_and_validated_contexts")
        return self

class ObservationContextRecoveryRequirementV1(StrictModel):
    schema_version: Literal["observation_context_recovery_requirement_v1"] = "observation_context_recovery_requirement_v1"
    recovery_requirement_id: str
    candidate_id: str
    candidate_qualification_identity: str
    entry_authorization_identity: str
    endpoint_role: Literal["a", "b"]
    observation_id: str
    endpoint_claim_identity: str
    current_context_status: str
    current_context_identity: str | None
    blocking_reason_codes: list[str]
    recovery_required: Literal[True]
    recovery_scope: Literal["context_missing", "context_unvalidated", "identity_mismatch", "endpoint_binding_mismatch", "policy_coverage_failure", "insufficient_information"]
    permitted_future_recovery_modes: list[str]
    provider_call_authorized: Literal[False]
    network_call_authorized: Literal[False]
    automatic_execution_authorized: Literal[False]
    historical_payload_mutation_authorized: Literal[False]
    requires_policy_extension_review: bool
    automatic_retry_recommended: Literal[False]
    source_artifact_refs: list[dict[str, str]]
    provenance: dict[str, Any]
    identity: str

class ContextDifferenceAuthorityV1(StrictModel):
    schema_version: Literal["context_difference_authority_v1"] = "context_difference_authority_v1"
    context_difference_authority_id: str
    candidate_id: str
    scientific_candidate_pair_identity: str
    candidate_qualification_identity: str
    entry_authorization_identity: str
    entry_status: EntryStatus
    source_context_difference_identity: str | None
    source_context_difference_schema_version: str | None
    source_context_difference_validation_status: str | None
    source_context_difference_validator_identity: str | None
    source_kind: Literal["newly_materialized", "deterministic_projection", "legacy_pair_projection", "historical_artifact", "unavailable"]
    source_lineage: dict[str, Any]
    difference_artifact_valid: bool
    authoritative_for_new_l4: bool
    authority_status: Literal["authoritative", "diagnostic_only", "ready_not_materialized", "blocked_entry", "unvalidated", "identity_mismatch", "rejected"]
    authority_scope: Literal["new_l4", "legacy_diagnostic", "none"]
    diagnostic_use_allowed: bool
    formal_use_allowed: bool
    legacy_artifact_preserved: bool
    source_payload_modified: Literal[False]
    validator_version: Literal["context_difference_authority_validator_v1"] = "context_difference_authority_validator_v1"
    identity: str
    provenance: dict[str, Any]

    @model_validator(mode="after")
    def invariants(self):
        if self.authority_status == "authoritative" and (self.entry_status != "ready" or not self.authoritative_for_new_l4):
            raise ValueError("authoritative_requires_ready_entry")
        if self.authority_status == "diagnostic_only" and self.formal_use_allowed:
            raise ValueError("diagnostic_cannot_be_formal")
        if self.authority_status == "ready_not_materialized" and self.source_context_difference_identity is not None:
            raise ValueError("not_materialized_has_source")
        if self.authority_status == "blocked_entry" and self.authoritative_for_new_l4:
            raise ValueError("blocked_entry_cannot_be_authoritative")
        return self

class ContextDifferenceEntryAuthorityBindingV1(StrictModel):
    schema_version: Literal["context_difference_entry_authority_binding_v1"] = "context_difference_entry_authority_binding_v1"
    context_difference_identity: str | None
    candidate_id: str
    candidate_qualification_identity: str
    entry_authorization_identity: str
    entry_status: EntryStatus
    difference_authority_identity: str
    artifact_valid: bool
    entry_ready: bool
    authoritative_for_new_l4: bool
    diagnostic_only: bool
    formal_use_allowed: bool
    binding_identity: str

class ConflictAdjudicationInputAuthorityV1(StrictModel):
    schema_version: Literal["conflict_adjudication_input_authority_v1"] = "conflict_adjudication_input_authority_v1"
    candidate_id: str
    candidate_qualification_identity: str
    candidate_qualification_status: str
    context_entry_authorization_identity: str
    context_entry_status: EntryStatus
    context_difference_authority_identity: str
    context_difference_authority_status: str
    comparability_bundle_identity: str | None
    divergence_explanation_bundle_identity: str | None
    authority_complete: bool
    blocking_layer: str
    primary_block_reason: str
    secondary_block_reasons: list[str]
    identity: str
