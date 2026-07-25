"""Immutable, conflict-neutral records for reusable experimental observations."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ObservationType = Literal[
    "interventional_experiment",
    "observational_comparison",
    "descriptive_measurement",
    "non_experimental_claim",
    "unresolved",
]
AuthorityStatus = Literal["authoritative", "deterministic", "candidate_only", "unresolved", "blocked"]

FORBIDDEN_DERIVED_FIELDS = {
    "alignment", "claim_alignment", "comparability", "context_difference",
    "contradiction", "divergence_explanation", "formal_conflict",
    "hypothesis_validity",
}


def reject_derived_fields(value: Any) -> None:
    if isinstance(value, dict):
        bad = FORBIDDEN_DERIVED_FIELDS.intersection(value)
        if bad:
            raise ValueError(f"derived scientific fields are forbidden: {sorted(bad)}")
        for item in value.values():
            reject_derived_fields(item)
    elif isinstance(value, list):
        for item in value:
            reject_derived_fields(item)


class StrictCoreAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CoreProvenance(StrictCoreAsset):
    producer: str
    producer_version: str
    source_artifact_refs: list[str] = Field(default_factory=list)
    deterministic_rule_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    offline: Literal[True] = True


class ObservationTypePolicyEntry(StrictCoreAsset):
    observation_type: ObservationType
    factor_requirement: Literal[
        "active_factor_required", "group_or_comparison_required",
        "not_required_by_type_policy", "not_applicable", "unresolved",
    ]
    measurement_minimum: int
    result_minimum: int
    result_measurement_ref_required: bool
    comparator_ref_required_for_comparative_result: bool
    machine_reuse_eligible: bool


class ObservationTypeCardinalityPolicy(StrictCoreAsset):
    policy_id: str
    entries: list[ObservationTypePolicyEntry]
    immutable: Literal[True] = True
    identity: str
    schema_version: Literal["observation_type_cardinality_policy_v1"] = (
        "observation_type_cardinality_policy_v1"
    )

    @model_validator(mode="after")
    def unique_types(self):
        types = [entry.observation_type for entry in self.entries]
        if len(types) != len(set(types)):
            raise ValueError("duplicate observation type policy")
        return self


class ExperimentalFactorRecord(StrictCoreAsset):
    factor_id: str
    observation_revision_identity: str
    local_factor_id: str
    role: Literal[
        "intervention", "treatment", "exposure", "genetic_manipulation",
        "environmental_condition", "disease_condition", "cohort",
        "experimental_group", "control", "comparator", "baseline",
        "sample_condition", "unresolved",
    ]
    raw_text: str | None = None
    extracted_value: Any = None
    canonical_value: Any = None
    canonical_identity: str | None = None
    value_state: str
    order_index: int
    factor_group_id: str | None = None
    control_or_comparator_status: str
    qualifier_refs: list[str] = Field(default_factory=list)
    context_field_refs: list[str] = Field(default_factory=list)
    evidence_anchor_ids: list[str] = Field(default_factory=list)
    validation_status: str
    normalization_status: str
    authority_status: AuthorityStatus
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_factor_record_v1"] = "experimental_factor_record_v1"


class MeasurementRecord(StrictCoreAsset):
    measurement_id: str
    observation_revision_identity: str
    local_measurement_id: str
    measured_entity_raw: str | None = None
    measured_entity_extracted: str | None = None
    measured_entity_canonical: str | None = None
    property_or_endpoint_raw: str | None = None
    property_or_endpoint_extracted: str | None = None
    property_or_endpoint_canonical: str | None = None
    measurement_semantic_level: str
    method_raw: str | None = None
    method_extracted: str | None = None
    method_canonical: str | None = None
    unit_raw: str | None = None
    unit_canonical: str | None = None
    sample_ref: str | None = None
    localization_ref: str | None = None
    assay_context_ref: str | None = None
    evidence_anchor_ids: list[str] = Field(default_factory=list)
    validation_status: str
    normalization_status: str
    authority_status: AuthorityStatus
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["measurement_record_v1"] = "measurement_record_v1"


class ObservedResultRecord(StrictCoreAsset):
    observed_result_id: str
    observation_revision_identity: str
    local_result_id: str
    measurement_ref: str | None = None
    comparison_factor_refs: list[str] = Field(default_factory=list)
    baseline_ref: str | None = None
    qualitative_result: str | None = None
    direction: str | None = None
    sign: str | None = None
    negation: bool = False
    quantitative_value_raw: Any = None
    quantitative_value_canonical: Any = None
    effect_size: Any = None
    confidence_interval: Any = None
    statistical_statement: str | None = None
    significance_status: str
    uncertainty_text: str | None = None
    evidence_anchor_ids: list[str] = Field(default_factory=list)
    validation_status: str
    authority_status: AuthorityStatus
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["observed_result_record_v1"] = "observed_result_record_v1"


class ExperimentalObservationLinkage(StrictCoreAsset):
    linkage_id: str
    observation_revision_identity: str
    relation_type: Literal[
        "factor_applies_to_measurement", "measurement_produces_result",
        "result_compared_against_factor", "result_uses_baseline",
        "factor_precedes_factor", "factor_cooccurs_with_factor",
        "observation_belongs_to_experiment_scope",
    ]
    source_ref: str
    target_ref: str
    order: int | None = None
    evidence_anchor_ids: list[str] = Field(default_factory=list)
    derivation_method: str
    validation_status: str
    authority_status: AuthorityStatus
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_observation_linkage_v1"] = (
        "experimental_observation_linkage_v1"
    )


class StructuredExperimentalObservationRevision(StrictCoreAsset):
    structured_observation_revision_id: str
    source_observation_identity: str
    source_parsed_candidate_identity: str | None = None
    source_validated_observation_identity: str | None = None
    source_fulltext_v3_identity: str | None = None
    source_projection_identity: str | None = None
    observation_type: ObservationType
    observation_type_authority: AuthorityStatus
    experiment_scope_identity: str | None = None
    experimental_factor_ids: list[str] = Field(default_factory=list)
    measurement_ids: list[str] = Field(default_factory=list)
    observed_result_ids: list[str] = Field(default_factory=list)
    linkage_record_ids: list[str] = Field(default_factory=list)
    context_asset_identity: str | None = None
    evidence_chain_identity: str | None = None
    structural_integrity_identity: str | None = None
    extraction_schema_identity: str | None = None
    parser_identity: str | None = None
    validator_identity: str | None = None
    supersedes_revision_id: str | None = None
    immutable: Literal[True] = True
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["structured_experimental_observation_revision_v1"] = (
        "structured_experimental_observation_revision_v1"
    )

    @model_validator(mode="after")
    def enforce_formal_core_cardinality(self):
        formal_types = {
            "interventional_experiment", "observational_comparison",
            "descriptive_measurement",
        }
        if self.observation_type in formal_types and not self.measurement_ids:
            raise ValueError("formal experimental observation requires measurement")
        if self.observation_type in formal_types and not self.observed_result_ids:
            raise ValueError("formal experimental observation requires observed result")
        if self.observation_type in {
            "interventional_experiment", "observational_comparison",
        } and not self.experimental_factor_ids:
            raise ValueError("observation type requires explicit factor records")
        return self


class ExperimentalCoreStageTrace(StrictCoreAsset):
    trace_id: str
    source_observation_identity: str
    stage_number: int
    stage_name: str
    stage_identity: str
    source_artifact_ref: str | None = None
    factor_count: int
    intervention_count: int
    measurement_count: int
    observed_result_count: int
    linkage_count: int
    evidence_count: int
    payload_hash: str | None = None
    field_availability: dict[str, bool]
    field_status: dict[str, str]
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_core_stage_trace_v1"] = (
        "experimental_core_stage_trace_v1"
    )


class ExperimentalCoreFirstLossDiagnosis(StrictCoreAsset):
    diagnosis_id: str
    source_observation_identity: str
    component: Literal["experimental_factors", "interventions", "measurements", "observed_results", "linkages"]
    first_loss_stage_number: int | None = None
    first_loss_stage_name: str | None = None
    loss_origin: Literal[
        "present_all_stages", "absent_from_provider_output", "raw_unavailable",
        "parser_dropped", "response_schema_could_not_represent", "adapter_dropped",
        "schema_validation_rejected", "scientific_validation_rejected",
        "atomization_split_loss", "experiment_merge_loss", "local_id_reference_loss",
        "fulltext_v3_projection_loss", "evidence_projection_loss",
        "asset_migration_omission", "non_experimental_source",
        "legacy_lineage_unavailable", "unknown",
    ]
    stage_trace_ids: list[str]
    evidence_refs: list[str] = Field(default_factory=list)
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_core_first_loss_diagnosis_v1"] = (
        "experimental_core_first_loss_diagnosis_v1"
    )


class ExperimentalObservationAtomicityAudit(StrictCoreAsset):
    source_observation_identity: str
    status: Literal[
        "atomic", "compound_but_explicitly_linked", "merged_recoverable",
        "merged_unrecoverable", "unresolved",
    ]
    issue_codes: list[str] = Field(default_factory=list)
    deterministic_split_allowed: bool = False
    parent_observation_identity: str | None = None
    child_revision_ids: list[str] = Field(default_factory=list)
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_observation_atomicity_audit_v1"] = (
        "experimental_observation_atomicity_audit_v1"
    )


class ExperimentalCoreRecoveryRevision(StrictCoreAsset):
    recovery_revision_id: str
    source_observation_identity: str
    affected_component: str
    source_stage: str
    source_artifact_identity: str
    old_status: str
    recovered_records: list[str] = Field(default_factory=list)
    recovered_links: list[str] = Field(default_factory=list)
    recovery_method: str
    deterministic_rule_identity: str
    authority_status: AuthorityStatus
    unresolved_items: list[str] = Field(default_factory=list)
    supersedes_revision_id: str | None = None
    immutable: Literal[True] = True
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_core_recovery_revision_v1"] = (
        "experimental_core_recovery_revision_v1"
    )


class ExperimentalObservationStructuralIntegrity(StrictCoreAsset):
    source_observation_identity: str
    structured_observation_revision_identity: str
    observation_type: ObservationType
    status: Literal[
        "structurally_complete", "structurally_complete_with_limitations",
        "incomplete_missing_factor", "incomplete_missing_measurement",
        "incomplete_missing_result", "incomplete_missing_linkage",
        "invalid_dangling_reference", "non_experimental_claim", "unresolved",
    ]
    factor_requirement_basis: str
    issue_codes: list[str] = Field(default_factory=list)
    dangling_refs: list[str] = Field(default_factory=list)
    duplicate_local_ids: list[str] = Field(default_factory=list)
    core_evidence_complete: bool
    provenance_traceable: bool
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_observation_structural_integrity_v1"] = (
        "experimental_observation_structural_integrity_v1"
    )


class ExperimentalObservationMachineReuseReadiness(StrictCoreAsset):
    source_observation_identity: str
    structured_observation_revision_identity: str
    structural_integrity_identity: str
    status: Literal[
        "machine_reusable_candidate", "usable_with_major_limitations",
        "text_evidence_only", "non_experimental_claim", "unusable", "unassessed",
    ]
    human_gold: Literal[False] = False
    formal_conflict_authority: Literal[False] = False
    limitation_codes: list[str] = Field(default_factory=list)
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_observation_machine_reuse_readiness_v1"] = (
        "experimental_observation_machine_reuse_readiness_v1"
    )


class ExperimentalCoreRemediationRequirement(StrictCoreAsset):
    observation_identity: str
    source_block_identity: str | None = None
    observation_type: ObservationType
    missing_components: list[str]
    first_loss_stage: str | None = None
    available_offline_recovery_modes: list[str] = Field(default_factory=list)
    preferred_offline_recovery_mode: str | None = None
    raw_lineage_status: str
    parsed_payload_status: str
    evidence_status: str
    provider_reextraction_required: bool
    minimal_source_scope: str
    dedup_group_identity: str
    automatic_execution_authorized: Literal[False] = False
    provider_call_authorized: Literal[False] = False
    network_call_authorized: Literal[False] = False
    budget_authorization_present: Literal[False] = False
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_core_remediation_requirement_v1"] = (
        "experimental_core_remediation_requirement_v1"
    )


class ResearchGradeObservationContextExtractionContractV2(StrictCoreAsset):
    contract_id: str
    output_fields: list[str]
    local_reference_requirements: list[str]
    atomicity_requirements: list[str]
    forbidden_outputs: list[str]
    validation_status: Literal["pending_smoke_validation"]
    production_status: Literal["not_activated"]
    provider_execution_authorized: Literal[False] = False
    identity: str
    schema_version: Literal["research_grade_observation_context_extraction_contract_v2"] = (
        "research_grade_observation_context_extraction_contract_v2"
    )
