"""Strict immutable records for lossless extraction assets."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .identities import SECRET_KEYS, assert_secret_free


class StrictAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IdentityProvenance(StrictAsset):
    producer: str
    producer_version: str
    source_artifact_refs: list[str] = Field(default_factory=list)
    offline: bool = True


class SourceSnapshot(StrictAsset):
    source_snapshot_id: str
    document_id: str
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    source_kind: str
    section_id: str | None = None
    paragraph_id: str | None = None
    sentence_ids: list[str] = Field(default_factory=list)
    block_id: str
    block_sequence: int | None = None
    input_text: str | None
    input_text_sha256: str | None
    source_file_identity: str | None = None
    source_file_sha256: str | None = None
    source_manifest_identity: str | None = None
    source_access_metadata: dict[str, Any] = Field(default_factory=dict)
    extraction_scope: str
    text_truncation_status: str = "not_truncated"
    text_window_start: int | None = None
    text_window_end: int | None = None
    preceding_context_ref: str | None = None
    following_context_ref: str | None = None
    source_snapshot_completeness: Literal["complete", "incomplete"]
    schema_version: Literal["source_snapshot_v1"] = "source_snapshot_v1"
    identity: str
    provenance: IdentityProvenance

    @model_validator(mode="after")
    def completeness_is_honest(self) -> "SourceSnapshot":
        if self.source_snapshot_completeness == "complete" and (
            self.input_text is None or self.input_text_sha256 is None
        ):
            raise ValueError("complete snapshot requires input_text and its sha256")
        return self


class ProviderCallSpecification(StrictAsset):
    provider_call_spec_id: str
    source_snapshot_identity: str
    prompt_identity: str
    prompt_template_identity: str
    rendered_prompt_sha256: str
    response_schema_identity: str
    model_provider: str
    model_name: str
    model_version_if_known: str | None = None
    non_secret_parameters: dict[str, Any] = Field(default_factory=dict)
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    response_format: str | None = None
    tool_schema_identity: str | None = None
    parser_contract_identity: str
    call_dedup_identity: str
    credential_source_name: str | None = None
    credential_present_boolean: bool | None = None
    schema_version: Literal["provider_call_specification_v1"] = "provider_call_specification_v1"
    identity: str

    @model_validator(mode="after")
    def no_secrets(self) -> "ProviderCallSpecification":
        assert_secret_free(self.model_dump())
        return self


class AttemptStatus(str, Enum):
    prepared = "prepared"
    cache_hit = "cache_hit"
    provider_in_flight = "provider_in_flight"
    provider_transport_failed = "provider_transport_failed"
    provider_http_failed = "provider_http_failed"
    raw_response_received = "raw_response_received"
    raw_response_persistence_failed = "raw_response_persistence_failed"
    raw_response_persisted = "raw_response_persisted"
    parse_pending = "parse_pending"
    parsed = "parsed"
    parse_failed = "parse_failed"
    validation_pending = "validation_pending"
    schema_validation_failed = "schema_validation_failed"
    scientific_validation_failed = "scientific_validation_failed"
    completed = "completed"
    abandoned = "abandoned"
    superseded = "superseded"


class ProviderCallAttempt(StrictAsset):
    provider_call_attempt_id: str
    provider_call_spec_identity: str
    call_dedup_identity: str
    attempt_sequence: int
    status: AttemptStatus
    raw_response_identity: str | None = None
    failure_kind: str | None = None
    provider_request_id: str | None = None
    provider_response_id: str | None = None
    real_api_call: bool = False
    paid_retry_automatic: bool = False
    state_history: list[str] = Field(default_factory=list)
    schema_version: Literal["provider_call_attempt_v1"] = "provider_call_attempt_v1"
    identity: str
    provenance: IdentityProvenance


class RawProviderResponse(StrictAsset):
    raw_response_id: str
    provider_call_attempt_identity: str
    provider_call_spec_identity: str
    call_dedup_identity: str
    provider_request_id: str | None = None
    provider_response_id: str | None = None
    response_received_at: str
    raw_response_path: str
    raw_response_sha256: str
    raw_response_byte_count: int
    raw_response_content_type: str = "application/octet-stream"
    raw_response_encoding: str | None = None
    provider_finish_reason: str | None = None
    usage_metadata: dict[str, Any] = Field(default_factory=dict)
    provider_error_metadata: dict[str, Any] = Field(default_factory=dict)
    response_complete: bool
    truncation_detected: bool
    secret_redaction_applied: bool
    immutable: Literal[True] = True
    schema_version: Literal["raw_provider_response_v1"] = "raw_provider_response_v1"
    identity: str
    provenance: IdentityProvenance


FORBIDDEN_DERIVED_FIELDS = {
    "formal_conflict", "formal_conflict_status", "comparability",
    "divergence_explanation", "hypothesis_validity", "claim_alignment",
    "candidate_qualification", "contradiction_validity",
}


class ParsedExtractionCandidateRevision(StrictAsset):
    parsed_candidate_revision_id: str
    raw_response_identity: str
    source_snapshot_identity: str
    provider_call_spec_identity: str
    parser_name: str
    parser_version: str
    parser_contract_identity: str
    extraction_schema_name: str
    extraction_schema_version: str
    parsed_payload: dict[str, Any] | list[Any] | None
    parsed_payload_sha256: str | None
    parse_status: Literal["parsed", "parse_failed"]
    parser_error_codes: list[str] = Field(default_factory=list)
    parser_warnings: list[str] = Field(default_factory=list)
    response_fragment_refs: list[str] = Field(default_factory=list)
    supersedes_parsed_revision_id: str | None = None
    immutable: Literal[True] = True
    schema_version: Literal["parsed_extraction_candidate_revision_v1"] = "parsed_extraction_candidate_revision_v1"
    identity: str
    provenance: IdentityProvenance

    @model_validator(mode="after")
    def no_derived_science(self) -> "ParsedExtractionCandidateRevision":
        def walk(value: Any) -> None:
            if isinstance(value, dict):
                bad = FORBIDDEN_DERIVED_FIELDS.intersection(value)
                if bad:
                    raise ValueError(f"derived science fields forbidden: {sorted(bad)}")
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(self.parsed_payload)
        return self


class ValueState(str, Enum):
    present = "present"
    explicitly_absent = "explicitly_absent"
    not_mentioned = "not_mentioned"
    not_extracted = "not_extracted"
    unknown = "unknown"
    ambiguous = "ambiguous"
    not_applicable = "not_applicable"
    invalid = "invalid"
    unavailable = "unavailable"
    legacy_null_unresolved = "legacy_null_unresolved"


class ExtractionFieldEvidence(StrictAsset):
    field_evidence_id: str
    parsed_candidate_revision_identity: str
    observation_candidate_id: str
    field_path: str
    field_role: str
    raw_text: str | None = None
    extracted_value: Any = None
    provider_value: Any = None
    value_state: ValueState
    provider_uncertainty: str | None = None
    evidence_anchor_ids: list[str] = Field(default_factory=list)
    source_snapshot_identity: str
    source_block_id: str
    sentence_id: str | None = None
    paragraph_id: str | None = None
    character_spans: list[tuple[int, int]] = Field(default_factory=list)
    token_spans: list[tuple[int, int]] = Field(default_factory=list)
    anchor_status: Literal["exact", "sentence_only", "ambiguous", "unresolved", "not_supplied"]
    anchor_validation_status: str
    field_schema_status: str
    field_validation_status: str
    normalization_status: str
    canonical_value: Any = None
    canonical_identity: str | None = None
    rejection_reason_codes: list[str] = Field(default_factory=list)
    unresolved_reason_codes: list[str] = Field(default_factory=list)
    scope_basis: str | None = None
    migration_record: bool = False
    schema_version: Literal["extraction_field_evidence_v1"] = "extraction_field_evidence_v1"
    identity: str
    provenance: IdentityProvenance

    @model_validator(mode="after")
    def state_rules(self) -> "ExtractionFieldEvidence":
        if self.value_state == ValueState.legacy_null_unresolved and not self.migration_record:
            raise ValueError("legacy_null_unresolved is migration-only")
        if self.value_state == ValueState.not_applicable and not self.scope_basis:
            raise ValueError("not_applicable requires scope_basis")
        if self.value_state == ValueState.not_mentioned and "source_audited" not in self.anchor_validation_status:
            raise ValueError("not_mentioned requires source audit evidence")
        return self


class SourcePresence(str, Enum):
    confirmed_present = "confirmed_present"
    confirmed_absent = "confirmed_absent"
    unknown = "unknown"
    not_assessed = "not_assessed"


class ExtractionCoverageRecord(StrictAsset):
    coverage_record_id: str
    source_snapshot_identity: str
    raw_response_identity: str | None = None
    parsed_candidate_revision_identity: str | None = None
    observation_candidate_id: str
    field_path: str
    capture_profile_identity: str
    requested_by_prompt: bool
    representable_in_response_schema: bool
    returned_by_provider: bool
    preserved_in_raw_response: bool
    preserved_in_parsed_payload: bool
    field_evidence_record_present: bool
    anchor_supplied: bool
    anchor_validated: bool
    value_state_available: bool
    raw_text_available: bool
    extracted_value_available: bool
    canonical_value_available: bool
    deterministic_validation_available: bool
    normalization_available: bool
    source_presence_status: SourcePresence = SourcePresence.unknown
    source_text_scope_sufficient: bool | None = None
    parser_replay_possible: bool
    validation_replay_possible: bool
    normalization_replay_possible: bool
    zero_api_schema_migration_possible: bool
    provider_reextraction_required: bool
    source_reingestion_required: bool
    blocking_reason_codes: list[str] = Field(default_factory=list)
    schema_version: Literal["extraction_coverage_ledger_v1"] = "extraction_coverage_ledger_v1"
    identity: str


class ReplayabilityStatus(str, Enum):
    fully_replayable_zero_api = "fully_replayable_zero_api"
    replayable_from_raw_response = "replayable_from_raw_response"
    replayable_from_parsed_candidate_only = "replayable_from_parsed_candidate_only"
    partially_replayable = "partially_replayable"
    provider_reextraction_required = "provider_reextraction_required"
    source_reingestion_required = "source_reingestion_required"
    invalid = "invalid"


class ReplayabilityAssessment(StrictAsset):
    assessment_id: str
    source_snapshot_identity: str | None = None
    provider_call_spec_identity: str | None = None
    parsed_candidate_revision_identity: str | None = None
    source_snapshot_available: bool
    source_snapshot_complete: bool
    prompt_available: bool
    rendered_prompt_available: bool
    prompt_identity_valid: bool
    model_metadata_available: bool
    non_secret_parameters_available: bool
    raw_response_available: bool
    raw_response_hash_valid: bool
    parsed_candidate_available: bool
    parser_identity_available: bool
    field_evidence_available: bool
    anchors_available: bool
    source_hash_valid: bool
    parser_replay_possible: bool
    schema_revalidation_possible: bool
    anchor_revalidation_possible: bool
    normalization_replay_possible: bool
    derived_artifact_recompute_possible: bool
    provider_reextraction_required: bool
    source_reingestion_required: bool
    replayability_status: ReplayabilityStatus
    blocking_reasons: list[str] = Field(default_factory=list)
    schema_version: Literal["extraction_replayability_assessment_v1"] = "extraction_replayability_assessment_v1"
    identity: str


class SelectiveReextractionRequirement(StrictAsset):
    reextraction_requirement_id: str
    source_snapshot_identity: str
    document_id: str
    block_id: str
    observation_candidate_ids: list[str]
    missing_capture_profile_fields: list[str]
    current_prompt_identity: str | None = None
    current_raw_response_identity: str | None = None
    current_parsed_revision_identities: list[str] = Field(default_factory=list)
    reextraction_reason: str
    minimal_text_scope: str
    minimal_block_set: list[str]
    dedup_group_identity: str
    estimated_call_count: int = 1
    priority: str
    requirement_status: str
    automatic_execution_authorized: Literal[False] = False
    provider_call_authorized: Literal[False] = False
    network_call_authorized: Literal[False] = False
    budget_authorization_present: Literal[False] = False
    historical_payload_mutation_authorized: Literal[False] = False
    schema_version: Literal["selective_reextraction_requirement_v1"] = "selective_reextraction_requirement_v1"
    identity: str
    provenance: IdentityProvenance


class ExtractionRunReadinessGate(StrictAsset):
    source_snapshot_persisted: bool
    rendered_prompt_persisted: bool
    prompt_identity_recomputable: bool
    call_dedup_enabled: bool
    raw_before_parser: bool
    parser_failure_paid_retry_disabled: bool
    parsed_revision_immutable: bool
    field_evidence_contract_available: bool
    value_state_contract_available: bool
    coverage_ledger_available: bool
    secrets_persisted: bool
    selective_reextraction_planner_available: bool
    cache_resume_tests_passed: bool
    real_smoke_evidence_available: bool = False
    status: Literal[
        "ready_for_smoke", "blocked_archive_incomplete", "blocked_dedup_missing",
        "blocked_raw_persistence_missing", "blocked_secret_redaction",
        "blocked_parser_retry_risk", "blocked_schema_gap", "rejected",
    ]
    schema_version: Literal["extraction_run_readiness_gate_v1"] = "extraction_run_readiness_gate_v1"
    identity: str
