from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, model_validator

class StrictModel(BaseModel):
    model_config=ConfigDict(extra="forbid")

class ObservationContextRemediationNeedV1(StrictModel):
    schema_version: Literal["observation_context_remediation_need_v1"]="observation_context_remediation_need_v1"
    remediation_need_id: str
    observation_id: str
    normalized_claim_identity: str
    endpoint_claim_identity: str
    current_context_status: str
    current_context_identity: str|None
    current_context_schema_version: str|None
    current_context_validator_identity: str|None
    context_source_artifact_identity: str
    context_source_artifact_path: str
    context_source_artifact_sha256: str
    validation_audit_identity: str
    validation_error_codes: list[str]
    failure_class: Literal["context_missing","source_payload_missing","extraction_incomplete","schema_invalid","deterministic_validation_failed","identity_mismatch","endpoint_binding_mismatch","provenance_incomplete","policy_coverage_failure","source_rule_shape_conflict","insufficient_information","unknown_failure"]
    remediation_status: Literal["open","blocked_policy_review","blocked_missing_source","deferred","superseded","resolved","invalid"]
    remediation_scope: Literal["extraction_recovery","deterministic_revalidation","identity_repair_review","provenance_repair_review","endpoint_binding_review","policy_coverage_review","source_artifact_review","insufficient_information_review"]
    remediation_priority: Literal["low","medium","high","critical"]
    active: bool
    supersedes_remediation_need_id: str|None
    replacement_context_identity: str|None
    replacement_remediation_need_identity: str|None
    policy_coverage_review_identity: str|None
    source_candidate_reference_count: int
    source_candidate_ids: list[str]
    automatic_execution_authorized: Literal[False]
    provider_call_authorized: Literal[False]
    network_call_authorized: Literal[False]
    download_authorized: Literal[False]
    historical_payload_mutation_authorized: Literal[False]
    composition_rule_mutation_authorized: Literal[False]
    registry_mutation_authorized: Literal[False]
    requires_human_review: bool
    requires_policy_extension_review: bool
    permitted_future_remediation_modes: list[str]
    validator_version: Literal["observation_context_remediation_need_validator_v1"]="observation_context_remediation_need_validator_v1"
    provenance: dict[str,Any]
    identity: str
    @model_validator(mode="after")
    def invariants(self):
        if self.remediation_status=="resolved" and not self.replacement_context_identity: raise ValueError("resolved_requires_context")
        if self.remediation_status=="superseded" and not self.replacement_remediation_need_identity: raise ValueError("superseded_requires_replacement")
        return self

class ObservationContextPolicyCoverageReviewV1(StrictModel):
    schema_version: Literal["observation_context_policy_coverage_review_v1"]="observation_context_policy_coverage_review_v1"
    policy_review_id: str
    observation_id: str
    normalized_claim_identity: str
    failed_factor_ids: list[str]
    failure_categories: list[str]
    component_shape_signatures: list[str]
    source_rule_signatures: list[str]
    registry_identity: str
    composition_identity: str
    inference_rule_contract_identity: str
    source_document_identity: str
    independent_document_support_count: int
    independent_observation_support_count: int
    candidate_policy_extension_eligible: bool
    policy_extension_gate_results: dict[str,bool]
    review_status: Literal["open","fail_closed","eligible_for_human_review","resolved"]
    automatic_rule_creation_authorized: Literal[False]
    automatic_provider_retry_authorized: Literal[False]
    automatic_payload_mutation_authorized: Literal[False]
    requires_cross_case_evidence: bool
    requires_independent_document_evidence: bool
    requires_fixture_suite: bool
    requires_non_regression_proof: bool
    provenance: dict[str,Any]
    identity: str

class ObservationContextRemediationRegistryV1(StrictModel):
    schema_version: Literal["observation_context_remediation_registry_v1"]="observation_context_remediation_registry_v1"
    registry_version: str
    remediation_need_identities: list[str]
    active_need_identities: list[str]
    resolved_need_identities: list[str]
    superseded_need_identities: list[str]
    observation_to_active_need: dict[str,str]
    duplicate_target_audit: list[dict[str,Any]]
    policy_review_identities: list[str]
    source_snapshot_identity: str
    execution_queue: Literal[False]
    execution_authorized: Literal[False]
    registry_identity: str
    @model_validator(mode="after")
    def unique_active(self):
        if len(self.observation_to_active_need)!=len(set(self.observation_to_active_need)): raise ValueError("duplicate_observation")
        if len(self.active_need_identities)!=len(set(self.active_need_identities)): raise ValueError("duplicate_active_identity")
        return self

class CandidateContextBlockingDependencyV1(StrictModel):
    schema_version: Literal["candidate_context_blocking_dependency_v1"]="candidate_context_blocking_dependency_v1"
    dependency_id: str
    candidate_id: str
    scientific_candidate_pair_identity: str
    candidate_qualification_identity: str
    candidate_qualification_status: str
    entry_authorization_identity: str
    entry_status: str
    endpoint_role: Literal["a","b"]
    observation_id: str
    endpoint_claim_identity: str
    remediation_need_identity: str
    policy_coverage_review_identity: str|None
    dependency_status: Literal["active_block","resolved","deferred_candidate_unqualified","stale","identity_mismatch","invalid"]
    blocks_l4_entry: bool
    blocking_reason_codes: list[str]
    dependency_active: bool
    source_context_status: str
    context_recovery_required: bool
    candidate_qualification_preserved: Literal[True]
    automatic_recovery_authorized: Literal[False]
    provider_recovery_authorized: Literal[False]
    network_recovery_authorized: Literal[False]
    validator_version: Literal["candidate_context_blocking_dependency_validator_v1"]="candidate_context_blocking_dependency_validator_v1"
    provenance: dict[str,Any]
    identity: str
    @model_validator(mode="after")
    def qualified_active(self):
        if self.blocks_l4_entry and (self.candidate_qualification_status!="qualified" or not self.dependency_active): raise ValueError("active_block_requires_qualified")
        return self

class LegacyRecoveryRequirementMigrationV1(StrictModel):
    schema_version: Literal["legacy_recovery_requirement_migration_v1"]="legacy_recovery_requirement_migration_v1"
    legacy_requirement_id: str
    candidate_id: str
    endpoint_role: str
    observation_id: str
    old_recovery_scope: str
    old_identity: str
    new_remediation_need_identity: str
    new_policy_review_identity: str|None
    new_candidate_dependency_identity: str|None
    duplicate_target: bool
    active_l4_dependency: bool
    migration_status: Literal["maps_to_unique_observation_remediation","maps_to_policy_coverage_review","maps_to_candidate_blocking_dependency","duplicate_candidate_reference","inactive_due_candidate_unqualified","invalid_scope","unresolved"]
    migration_notes: list[str]

class ContextEntryRemediationDependencyBindingV1(StrictModel):
    schema_version: Literal["context_entry_remediation_dependency_binding_v1"]="context_entry_remediation_dependency_binding_v1"
    entry_authorization_identity: str
    candidate_id: str
    remediation_need_identities: list[str]
    dependency_identities: list[str]
    policy_review_identities: list[str]
    binding_status: Literal["active_block","no_active_dependency","candidate_unqualified"]
    active_blocking_dependency_count: int
    automatic_execution_authorized: Literal[False]
    binding_identity: str
