"""Immutable first-class assets for experimental observation context.

This layer intentionally contains no conflict comparison or adjudication model.
Scientific validation remains owned by ``context_attribution.observation_context``.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


FORBIDDEN_DERIVED_FIELDS = {
    "comparison_status", "comparability", "comparability_effect",
    "explains_divergence", "divergence_explanation", "conflict_decision",
    "formal_conflict", "formal_conflict_status",
}


def reject_derived_fields(value: Any) -> None:
    if isinstance(value, dict):
        bad = FORBIDDEN_DERIVED_FIELDS.intersection(value)
        if bad:
            raise ValueError(f"derived reasoning fields forbidden in context assets: {sorted(bad)}")
        for item in value.values():
            reject_derived_fields(item)
    elif isinstance(value, list):
        for item in value:
            reject_derived_fields(item)


class StrictContextAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AssetProvenance(StrictContextAsset):
    producer: str
    producer_version: str
    source_artifact_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    offline: Literal[True] = True


class ContextValueState(str, Enum):
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


class ContextValueOrigin(str, Enum):
    direct_local_evidence = "direct_local_evidence"
    direct_shared_experiment_evidence = "direct_shared_experiment_evidence"
    deterministic_scope_inheritance = "deterministic_scope_inheritance"
    historical_validated_context = "historical_validated_context"
    historical_context_consolidation = "historical_context_consolidation"
    parsed_payload_recovery = "parsed_payload_recovery"
    raw_response_recovery = "raw_response_recovery"
    document_metadata_explicit = "document_metadata_explicit"
    human_annotation = "human_annotation"
    unresolved_legacy = "unresolved_legacy"
    unavailable = "unavailable"


class ExperimentalContextCandidateRevision(StrictContextAsset):
    context_candidate_revision_id: str
    observation_candidate_identity: str
    parsed_candidate_revision_identity: str | None = None
    source_snapshot_identity: str | None = None
    experiment_scope_identity: str | None = None
    source_context_envelope_identity: str | None = None
    context_schema_name: str
    context_schema_version: str
    extractor_name: str
    extractor_version: str
    extraction_contract_identity: str
    raw_context_payload: dict[str, Any] | list[Any] | None
    raw_context_payload_sha256: str
    field_record_ids: list[str] = Field(default_factory=list)
    parse_status: Literal["parsed", "parse_failed", "migrated"]
    schema_status: Literal["valid", "invalid", "legacy_unvalidated"]
    extraction_warnings: list[str] = Field(default_factory=list)
    extraction_error_codes: list[str] = Field(default_factory=list)
    supersedes_revision_id: str | None = None
    immutable: Literal[True] = True
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["experimental_context_candidate_revision_v1"] = (
        "experimental_context_candidate_revision_v1"
    )

    @model_validator(mode="after")
    def asset_boundary(self):
        reject_derived_fields(self.raw_context_payload)
        return self


class ExperimentContextScope(StrictContextAsset):
    experiment_scope_id: str
    document_id: str
    source_section_refs: list[str] = Field(default_factory=list)
    source_paragraph_refs: list[str] = Field(default_factory=list)
    source_block_refs: list[str] = Field(default_factory=list)
    experiment_group_identity: str
    scope_detection_method: str
    scope_detection_version: str
    directly_stated_context_field_ids: list[str] = Field(default_factory=list)
    linked_observation_ids: list[str] = Field(default_factory=list)
    scope_start_anchor: str | None = None
    scope_end_anchor: str | None = None
    scope_status: Literal[
        "validated_explicit_scope", "deterministic_scope_candidate",
        "ambiguous_scope", "unavailable", "invalid",
    ]
    authority_status: Literal["authoritative", "candidate_only", "blocked"]
    ambiguity_status: Literal["unambiguous", "ambiguous", "unavailable"]
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["experiment_context_scope_v1"] = "experiment_context_scope_v1"


class SourceContextEnvelope(StrictContextAsset):
    source_context_envelope_id: str
    primary_observation_block: str | None
    section_hierarchy: list[str] = Field(default_factory=list)
    preceding_paragraph_refs: list[str] = Field(default_factory=list)
    following_paragraph_refs: list[str] = Field(default_factory=list)
    methods_paragraph_refs: list[str] = Field(default_factory=list)
    figure_table_caption_refs: list[str] = Field(default_factory=list)
    source_byte_hash_refs: list[str] = Field(default_factory=list)
    envelope_construction_policy: str
    truncation_status: str
    context_window_limits: dict[str, int] = Field(default_factory=dict)
    completeness_status: Literal["complete", "incomplete", "unavailable"]
    authority_status: Literal["authoritative", "non_authoritative"]
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["source_context_envelope_v1"] = "source_context_envelope_v1"

    @model_validator(mode="after")
    def honest_authority(self):
        if self.completeness_status != "complete" and self.authority_status == "authoritative":
            raise ValueError("incomplete envelope cannot be authoritative")
        return self


class ContextFieldRegistryRecord(StrictContextAsset):
    field_id: str
    canonical_field_path: str
    legacy_aliases: list[str] = Field(default_factory=list)
    semantic_category: str
    value_type: str
    cardinality: Literal["one", "many"]
    ordered_or_unordered: Literal["ordered", "unordered", "not_applicable"]
    direct_evidence_required: bool
    scope_propagation_allowed: bool
    scope_propagation_policy_identity: str | None = None
    normalization_contract: str
    currently_supported: bool
    prompt_requested: bool
    schema_representable: bool
    parser_preserved: bool
    active_status: Literal["active", "audit_only", "deprecated"]
    identity: str
    schema_version: Literal["experimental_context_field_registry_v1"] = (
        "experimental_context_field_registry_v1"
    )


class ContextValueStateBasis(StrictContextAsset):
    value_state: ContextValueState
    state_basis_type: str
    source_evidence_refs: list[str] = Field(default_factory=list)
    extraction_evidence_refs: list[str] = Field(default_factory=list)
    scope_basis_refs: list[str] = Field(default_factory=list)
    validation_refs: list[str] = Field(default_factory=list)
    state_authority: Literal["authoritative", "candidate", "legacy_unresolved"]
    limitations: list[str] = Field(default_factory=list)
    schema_version: Literal["context_value_state_basis_v1"] = "context_value_state_basis_v1"

    @model_validator(mode="after")
    def evidence_requirements(self):
        if self.value_state == ContextValueState.not_mentioned and not self.source_evidence_refs:
            raise ValueError("not_mentioned requires sufficient source audit")
        if self.value_state == ContextValueState.not_applicable and not self.scope_basis_refs:
            raise ValueError("not_applicable requires scope basis")
        if self.value_state == ContextValueState.explicitly_absent and not self.source_evidence_refs:
            raise ValueError("explicitly_absent requires direct negative evidence")
        return self


class ContextFieldEvidence(StrictContextAsset):
    context_field_evidence_id: str
    context_candidate_revision_identity: str
    observation_candidate_identity: str
    experiment_scope_identity: str | None = None
    field_id: str
    field_path: str
    original_field_name: str | None = None
    original_value: Any = None
    original_schema: str | None = None
    original_artifact_identity: str | None = None
    raw_text: str | None = None
    provider_value: Any = None
    extracted_value: Any = None
    canonical_value: Any = None
    canonical_identity: str | None = None
    value_state: ContextValueState
    value_origin: ContextValueOrigin
    value_state_basis: ContextValueStateBasis
    evidence_anchor_ids: list[str] = Field(default_factory=list)
    source_sentence_ids: list[str] = Field(default_factory=list)
    source_paragraph_ids: list[str] = Field(default_factory=list)
    source_block_ids: list[str] = Field(default_factory=list)
    evidence_quote: str | None = None
    provider_supplied_offsets: list[tuple[int, int]] = Field(default_factory=list)
    deterministically_resolved_offsets: list[tuple[int, int]] = Field(default_factory=list)
    anchor_precision: Literal["exact", "sentence", "block", "unresolved"]
    anchor_validation_status: str
    context_validation_status: str
    normalization_status: str
    rejection_reason_codes: list[str] = Field(default_factory=list)
    unresolved_reason_codes: list[str] = Field(default_factory=list)
    authority_status: str
    migration_record: bool = False
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["context_field_evidence_v1"] = "context_field_evidence_v1"

    @model_validator(mode="after")
    def value_contract(self):
        if self.value_state == ContextValueState.legacy_null_unresolved and not self.migration_record:
            raise ValueError("legacy_null_unresolved is migration-only")
        if self.deterministically_resolved_offsets and self.anchor_precision != "exact":
            raise ValueError("resolved offsets require exact anchor precision")
        return self


class ObservationContextScopeLink(StrictContextAsset):
    observation_identity: str
    experiment_scope_identity: str
    field_id: str
    source_context_field_identity: str
    link_type: Literal["direct_membership", "deterministic_inheritance"]
    propagation_policy_identity: str
    propagation_validation_status: str
    conflicting_value_check: Literal["clear", "conflict", "not_assessed"]
    authority_status: str
    identity: str
    schema_version: Literal["observation_context_scope_link_v1"] = "observation_context_scope_link_v1"


class ContextScopePropagationPolicy(StrictContextAsset):
    policy_id: str
    version: str
    require_validated_scope: Literal[True] = True
    require_registry_permission: Literal[True] = True
    require_explicit_source_evidence: Literal[True] = True
    require_observation_membership: Literal[True] = True
    reject_local_conflict: Literal[True] = True
    reject_scope_conflict: Literal[True] = True
    cross_document_propagation_allowed: Literal[False] = False
    majority_vote_allowed: Literal[False] = False
    llm_adjudication_allowed: Literal[False] = False
    identity: str
    schema_version: Literal["context_scope_propagation_policy_v1"] = (
        "context_scope_propagation_policy_v1"
    )


class ValidatedObservationContextRevision(StrictContextAsset):
    validated_context_revision_id: str
    context_candidate_revision_identity: str
    observation_identity: str
    experiment_scope_identity: str | None = None
    context_field_record_ids: list[str] = Field(default_factory=list)
    schema_validation_status: str
    field_validation_statuses: dict[str, str] = Field(default_factory=dict)
    anchor_validation_statuses: dict[str, str] = Field(default_factory=dict)
    scope_validation_status: str
    propagation_validation_status: str
    semantic_validation_status: Literal["validated_current", "validated_legacy", "invalid"]
    completeness_status: Literal["complete", "partial", "unknown"]
    validation_contract_identity: str
    validator_version: str
    validation_error_codes: list[str] = Field(default_factory=list)
    validation_warning_codes: list[str] = Field(default_factory=list)
    immutable: Literal[True] = True
    supersedes_revision_id: str | None = None
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["validated_observation_context_revision_v1"] = (
        "validated_observation_context_revision_v1"
    )


class ContextNormalizationRevision(StrictContextAsset):
    normalization_revision_id: str
    validated_context_revision_identity: str
    field_id: str
    raw_text: str | None = None
    extracted_value: Any = None
    canonical_value: Any = None
    canonical_identity: str | None = None
    normalization_status: Literal["resolved", "ambiguous", "unresolved", "not_requested"]
    normalization_contract_identity: str
    registry_identity: str
    ambiguous_candidates: list[Any] = Field(default_factory=list)
    unresolved_reason: str | None = None
    immutable: Literal[True] = True
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["context_normalization_revision_v1"] = "context_normalization_revision_v1"


class ConsolidationFieldResolution(StrictContextAsset):
    field_id: str
    selected_value_record: str | None
    candidate_value_records: list[str] = Field(default_factory=list)
    resolution_method: Literal[
        "validated_direct_local", "validated_same_observation",
        "validated_scope_inheritance", "historical_validated_consolidation", "unresolved",
    ]
    direct_vs_inherited: Literal["direct", "inherited", "unresolved"]
    conflict_status: Literal["clear", "conflict", "unresolved"]
    authority_status: str
    rejection_reasons: list[str] = Field(default_factory=list)


class ContextConsolidationRevision(StrictContextAsset):
    consolidation_revision_id: str
    observation_identity: str
    source_context_candidate_revisions: list[str] = Field(default_factory=list)
    validated_context_revision_ids: list[str] = Field(default_factory=list)
    experiment_scope_ids: list[str] = Field(default_factory=list)
    field_resolution_records: list[ConsolidationFieldResolution] = Field(default_factory=list)
    direct_field_count: int = Field(ge=0)
    inherited_field_count: int = Field(ge=0)
    unresolved_field_count: int = Field(ge=0)
    unavailable_field_count: int = Field(ge=0)
    conflicting_field_count: int = Field(ge=0)
    consolidation_policy_identity: str
    authority_status: str
    immutable: Literal[True] = True
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["context_consolidation_revision_v1"] = "context_consolidation_revision_v1"


class ContextAssetScopedAuthority(StrictContextAsset):
    observation_identity: str
    semantic_authority: Literal[
        "validated_current", "validated_legacy", "candidate_only", "unresolved", "invalid",
    ]
    evidence_authority: Literal[
        "exact_field_anchor", "exact_sentence_anchor", "block_level_only",
        "evidence_unresolved", "source_unavailable",
    ]
    provenance_authority: Literal[
        "end_to_end_direct", "end_to_end_reconstructed",
        "parsed_or_context_artifact_only", "legacy_incomplete", "unavailable",
    ]
    replayability_authority: Literal[
        "fully_replayable", "parser_replayable", "structured_artifact_replayable",
        "partially_replayable", "not_replayable",
    ]
    downstream_use_authority: Literal[
        "allowed_for_observation_display", "allowed_for_exploratory_graph",
        "allowed_for_l4_entry", "diagnostic_only", "blocked",
    ]
    downstream_authority_source: Literal["existing_entry_gate", "asset_display_policy"]
    identity: str
    schema_version: Literal["context_asset_scoped_authority_v1"] = "context_asset_scoped_authority_v1"


class HistoricalContextAssetInventoryRecord(StrictContextAsset):
    artifact_kind: str
    source_run: str
    relative_path: str
    sha256: str
    schema_name: str | None = None
    schema_version_found: str | None = None
    observation_refs: list[str] = Field(default_factory=list)
    experiment_scope_refs: list[str] = Field(default_factory=list)
    context_fields_present: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    validation_refs: list[str] = Field(default_factory=list)
    normalization_refs: list[str] = Field(default_factory=list)
    direct_inherited_status: str
    lineage_completeness: str
    migration_eligibility: str
    migration_blockers: list[str] = Field(default_factory=list)
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["historical_context_asset_inventory_v1"] = (
        "historical_context_asset_inventory_v1"
    )


class HistoricalContextAssetMigration(StrictContextAsset):
    migration_id: str
    original_artifact_identity: str
    original_field_name: str | None = None
    original_value: Any = None
    original_schema: str | None = None
    mapping_status: Literal[
        "exact_same_field", "versioned_alias", "split_required", "merge_required",
        "semantic_mismatch", "unresolved",
    ]
    migrated_asset_identities: list[str] = Field(default_factory=list)
    historical_artifact_modified: Literal[False] = False
    identity: str
    provenance: AssetProvenance
    schema_version: Literal["historical_context_asset_migration_v1"] = (
        "historical_context_asset_migration_v1"
    )


class ContextCoverageRecord(StrictContextAsset):
    coverage_record_id: str
    observation_identity: str
    experiment_scope_identity: str | None = None
    field_id: str
    field_registry_identity: str
    requested_by_observation_prompt: bool
    requested_by_context_prompt: bool
    representable_in_observation_schema: bool
    representable_in_context_schema: bool
    returned_in_observation_payload: bool
    returned_in_context_payload: bool
    preserved_in_parsed_payload: bool
    migrated_from_historical_context: bool
    direct_evidence_available: bool
    shared_scope_evidence_available: bool
    authoritative_anchor_available: bool
    value_state_available: bool
    validated_value_available: bool
    normalized_value_available: bool
    consolidation_value_available: bool
    propagation_available: bool
    provider_reextraction_required: bool
    deterministic_recovery_available: bool
    source_scope_sufficient: bool
    blocking_reason_codes: list[str] = Field(default_factory=list)
    identity: str
    schema_version: Literal["context_asset_coverage_ledger_v1"] = "context_asset_coverage_ledger_v1"


class ContextCompletenessProfile(StrictContextAsset):
    observation_identity: str
    category_counts: dict[str, dict[str, int]]
    evidence_anchor_coverage: float = Field(ge=0, le=1)
    normalization_coverage: float = Field(ge=0, le=1)
    value_state_coverage: float = Field(ge=0, le=1)
    validity_status: str
    completeness_status: str
    identity: str
    schema_version: Literal["context_completeness_profile_v1"] = "context_completeness_profile_v1"


class ContextAssetRemediationRequirement(StrictContextAsset):
    observation_identity: str
    experiment_scope_identity: str | None = None
    field_ids: list[str]
    current_context_asset_status: str
    available_recovery_modes: list[str] = Field(default_factory=list)
    preferred_recovery_mode: str
    historical_artifact_refs: list[str] = Field(default_factory=list)
    source_scope_status: str
    raw_lineage_status: str
    parsed_lineage_status: str
    provider_reextraction_required: bool
    source_reingestion_required: bool
    minimal_source_block_set: list[str] = Field(default_factory=list)
    dedup_group_identity: str
    automatic_execution_authorized: Literal[False] = False
    provider_call_authorized: Literal[False] = False
    network_call_authorized: Literal[False] = False
    budget_authorization_present: Literal[False] = False
    identity: str
    schema_version: Literal["context_asset_remediation_requirement_v2"] = (
        "context_asset_remediation_requirement_v2"
    )


class ContextAssetMultiAxisReadiness(StrictContextAsset):
    observation_identity: str
    semantic_readiness: Literal[
        "validated_current", "validated_legacy", "candidate_only", "invalid", "unavailable",
    ]
    evidence_readiness: Literal[
        "field_level_exact", "sentence_level", "block_level", "partial", "unresolved",
    ]
    provenance_readiness: Literal[
        "end_to_end_direct", "end_to_end_reconstructed", "structured_artifact_only",
        "legacy_incomplete", "unavailable",
    ]
    replayability_readiness: Literal[
        "fully_replayable", "parser_replayable", "structured_artifact_replayable",
        "partially_replayable", "not_replayable",
    ]
    coverage_readiness: Literal["high", "medium", "low", "unknown"]
    downstream_readiness: Literal[
        "observation_display_ready", "exploratory_graph_ready", "l4_entry_eligible",
        "diagnostic_only", "blocked",
    ]
    future_data_reuse_readiness: Literal[
        "research_grade_candidate", "usable_with_limitations", "challenge_record", "unusable",
    ]
    threshold_contract_identity: str
    identity: str
    schema_version: Literal["context_asset_multi_axis_readiness_v1"] = (
        "context_asset_multi_axis_readiness_v1"
    )


class ContextProviderCallPolicy(StrictContextAsset):
    bulk_secondary_context_calls_allowed: Literal[False] = False
    automatic_context_retry_allowed: Literal[False] = False
    provider_call_authorized: Literal[False] = False
    selective_remediation_only: Literal[True] = True
    explicit_budget_authorization_required: Literal[True] = True
    block_level_dedup_required: Literal[True] = True
    cache_first_required: Literal[True] = True
    raw_first_persistence_required: Literal[True] = True
    identity: str
    schema_version: Literal["context_provider_call_policy_v1"] = "context_provider_call_policy_v1"


class ResearchGradeObservationContextExtractionContract(StrictContextAsset):
    contract_status: Literal["Proposed"] = "Proposed"
    validation_status: Literal["pending_smoke_validation"] = "pending_smoke_validation"
    production_status: Literal["not_activated"] = "not_activated"
    atomic_observations_required: Literal[True] = True
    experiment_scopes_required: Literal[True] = True
    local_context_supported: Literal[True] = True
    shared_context_supported: Literal[True] = True
    intervention_order_supported: Literal[True] = True
    evidence_refs_required: Literal[True] = True
    explicit_value_state_candidates_supported: Literal[True] = True
    canonical_identity_requested_from_llm: Literal[False] = False
    conflict_judgment_requested_from_llm: Literal[False] = False
    comparability_judgment_requested_from_llm: Literal[False] = False
    divergence_explanation_requested_from_llm: Literal[False] = False
    output_shape: dict[str, Any]
    prompt_requirements: list[str]
    identity: str
    schema_version: Literal["research_grade_observation_context_extraction_contract_v1"] = (
        "research_grade_observation_context_extraction_contract_v1"
    )

    @model_validator(mode="after")
    def no_derived_output(self):
        reject_derived_fields(self.output_shape)
        return self
