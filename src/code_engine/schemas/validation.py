"""Domain-adaptive validation contracts with legacy result compatibility."""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import Field, model_validator

from code_engine.schemas.models import CODEBaseModel, FinalReportItem, validate_json_list


ValidationStatus = Literal["supported", "contradicted", "mixed", "no_coverage", "not_applicable", "external_index_not_configured", "insufficient_quality", "error"]
NORMALIZED_STATUSES = {
    "supported", "contradicted", "mixed", "no_coverage", "not_applicable",
    "external_index_not_configured", "insufficient_quality", "error",
}
LEGACY_STATUS_MAP = {
    "Sign_Consistent_Under_Curated_Index": "supported",
    "Sign_Inconsistent_Under_Curated_Index": "contradicted",
    "Unresolved_No_Coverage": "no_coverage",
    "External_Index_Not_Configured": "external_index_not_configured",
    "No_Local_Index": "external_index_not_configured",
    "No_Coverage": "no_coverage",
    "Not_Applicable": "not_applicable",
}


class ValidationQuestion(CODEBaseModel):
    question_id: str
    hypothesis_id: str = "UNKNOWN"
    anchor_id: str = ""
    validator_intent: str = "unknown"
    domain_id: str | None = None
    validator_profile_id: str = "general_validation"
    relation_type: str = "unknown"
    relation_family: str | None = None
    polarity_type: str | None = None
    direction: str | None = None
    evidence_modality: str = "unknown"
    subject_entity: str = ""
    object_entity: str = ""
    entities: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    contexts: dict[str, Any] = Field(default_factory=dict)
    expected_direction: str | None = None
    quality_requirements: dict[str, Any] = Field(default_factory=dict)
    question_text: str = ""
    required_resources: list[str] = Field(default_factory=list)
    preferred_validators: list[str] = Field(default_factory=list)
    fallback_validators: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValidationPlan(CODEBaseModel):
    plan_id: str
    hypothesis_id: str
    domain_id: str
    validator_profile_id: str
    questions: list[ValidationQuestion] = Field(default_factory=list)
    selected_validators: list[str] = Field(default_factory=list)
    fallback_validators: list[str] = Field(default_factory=list)
    coverage_expectation: str = "unknown"
    warnings: list[str] = Field(default_factory=list)


class ValidationResult(CODEBaseModel):
    validation_id: str = ""
    hypothesis_id: str
    validator_name: str = ""
    domain_id: str = "general_biomedical"
    validator_profile_id: str = "general_validation"
    evidence_modality: str = "unknown"
    validation_status: ValidationStatus = "no_coverage"
    coverage_status: str = "none"
    matched_entities: list[str] = Field(default_factory=list)
    matched_context: dict[str, Any] = Field(default_factory=dict)
    direction_consistency: str = "unknown"
    effect_size: float | None = None
    quality_score: float | None = None
    limitations: list[str] = Field(default_factory=list)
    raw_evidence_refs: list[Any] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validator: str = ""
    status: str = ""
    coverage: str = "none"
    score: float | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    quality: float = Field(default=0.0, ge=0.0, le=1.0)
    coverage_score: float = Field(default=0.0, ge=0.0, le=1.0)
    anchor_ids: list[str] = Field(default_factory=list)
    query_plan_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    signal_ids: list[str] = Field(default_factory=list)
    summary: str = ""
    interpretation_limits: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def map_legacy_fields(self):
        self.validator_name = self.validator_name or self.validator
        self.validator = self.validator or self.validator_name
        if self.status and self.validation_status == "no_coverage":
            self.validation_status = LEGACY_STATUS_MAP.get(
                self.status,
                self.status if self.status in NORMALIZED_STATUSES else self.validation_status,
            )
        self.status = self.status or self.validation_status
        self.coverage_status = self.coverage_status if self.coverage_status != "none" else self.coverage
        self.coverage = self.coverage if self.coverage != "none" else self.coverage_status
        if not self.validation_id:
            self.validation_id = hashlib.sha256(f"{self.hypothesis_id}|{self.validator_name}".encode()).hexdigest()[:16]
        return self


class ValidationCoverageReport(CODEBaseModel):
    hypothesis_id: str
    overall_status: str
    validator_results: list[ValidationResult] = Field(default_factory=list)
    covered_validators: list[str] = Field(default_factory=list)
    uncovered_validators: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValidationAnchor(CODEBaseModel):
    anchor_id: str
    anchor_type: str
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relations: list[dict[str, Any]] = Field(default_factory=list)
    contexts: dict[str, Any] = Field(default_factory=dict)
    domain_id: str | None = None
    relation_family: str | None = None
    polarity_type: str | None = None
    direction: str | None = None
    linked_hypothesis_ids: list[str] = Field(default_factory=list)
    linked_conflict_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    linked_mechanism_edge_ids: list[str] = Field(default_factory=list)
    linked_mechanism_path_ids: list[str] = Field(default_factory=list)
    validation_intent: str = "identity_lookup"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    priority: int = 0
    warnings: list[str] = Field(default_factory=list)


class ValidatorRoute(CODEBaseModel):
    route_id: str
    question_id: str
    anchor_id: str
    validator_name: str
    reason: str
    priority: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class ValidatorCapability(CODEBaseModel):
    validator_name: str
    supported_anchor_types: list[str] = Field(default_factory=list)
    supported_validation_intents: list[str] = Field(default_factory=list)
    supported_domains: list[str] = Field(default_factory=list)
    supported_relation_families: list[str] = Field(default_factory=list)
    supported_polarity_types: list[str] = Field(default_factory=list)
    supported_entity_types: list[str] = Field(default_factory=list)
    supports_local_index: bool = False
    supports_remote_api: bool = False
    supports_cache_only: bool = True
    requires_auth: bool = False
    default_max_records: int = 100
    default_max_signals: int = 30
    index_name: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ValidationQueryPlan(CODEBaseModel):
    query_plan_id: str
    anchor_id: str
    question_id: str = ""
    validator_name: str
    query_type: str
    query_entities: list[dict[str, Any]] = Field(default_factory=list)
    query_context: dict[str, Any] = Field(default_factory=dict)
    execution_mode: str = "planned"
    index_name: str | None = None
    cache_key: str | None = None
    estimated_records: int | None = None
    estimated_memory_mb: float | None = None
    estimated_output_bytes: int | None = None
    estimated_query_seconds: float | None = None
    max_records: int = 100
    max_signals: int = 30
    max_raw_payload_bytes: int = 5_000_000
    timeout_seconds: int = 30
    status: str = "planned"
    reason: str = ""
    warnings: list[str] = Field(default_factory=list)


class ExternalEvidenceRecord(CODEBaseModel):
    evidence_id: str
    validator_name: str
    source_database: str
    query_plan_id: str
    anchor_id: str
    evidence_type: str
    source_entity: dict[str, Any] | None = None
    target_entity: dict[str, Any] | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    record_id: str | None = None
    external_ids: dict[str, Any] = Field(default_factory=dict)
    direction: str | None = None
    score: float | None = None
    strength: float | None = None
    p_value: float | None = None
    effect_size: float | None = None
    raw_payload_ref: str | None = None
    retrieved_at: str | None = None
    interpretation_limits: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValidationSignal(CODEBaseModel):
    signal_id: str
    validator_name: str
    source_database: str
    query_plan_id: str
    anchor_id: str
    signal_type: str
    linked_external_evidence_ids: list[str] = Field(default_factory=list)
    supports_hypothesis: bool | None = None
    contradicts_hypothesis: bool | None = None
    direction: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    quality: float = Field(default=0.0, ge=0.0, le=1.0)
    interpretation_limits: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValidationResourcePolicy(CODEBaseModel):
    max_memory_mb: int = 4096
    max_disk_cache_mb: int = 20480
    max_records_per_validator: int = 100
    max_records_per_anchor: int = 200
    max_signals_per_validator: int = 30
    max_signals_per_run: int = 200
    max_raw_payload_bytes_per_validator: int = 5_000_000
    max_query_seconds: int = 30
    max_total_query_seconds: int = 300
    max_concurrent_validator_queries: int = 1
    allow_large_local_scan: bool = False
    external_validation_enabled: bool = False
    network_enabled: bool = False
    cache_enabled: bool = True
    execution_enabled: bool = True
    index_dir: str | None = None
    cache_dir: str | None = None


class ValidationExecutionContext(CODEBaseModel):
    execute: bool = False
    network_enabled: bool = False
    external_validation_enabled: bool = False
    cache_enabled: bool = True
    index_dir: str | None = None
    cache_dir: str | None = None
    auth_config: dict[str, Any] = Field(default_factory=dict)
    provider_clients: dict[str, Any] = Field(default_factory=dict)
    resource_policy: ValidationResourcePolicy = Field(default_factory=ValidationResourcePolicy)


class ValidationExecutionResult(CODEBaseModel):
    result_id: str
    status: str
    query_plan_count: int = 0
    executed_query_count: int = 0
    blocked_query_count: int = 0
    validator_status_counts: dict[str, int] = Field(default_factory=dict)
    evidence_count: int = 0
    signal_count: int = 0
    cache_hit_count: int = 0
    cache_miss_count: int = 0
    estimated_memory_mb: float | None = None
    actual_max_records_seen: int = 0
    network_calls_made: int = 0
    warnings: list[str] = Field(default_factory=list)
    artifact_refs: dict[str, str] = Field(default_factory=dict)


class AggregatedValidationResult(CODEBaseModel):
    aggregate_status: str
    result_count: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    results: list[ValidationResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifact_refs: dict[str, str] = Field(default_factory=dict)


__all__ = [
    "ValidationQuestion", "ValidationPlan", "ValidationResult", "ValidationCoverageReport",
    "ValidationAnchor", "ValidatorRoute", "ValidatorCapability", "ValidationQueryPlan",
    "ExternalEvidenceRecord", "ValidationSignal", "ValidationResourcePolicy",
    "ValidationExecutionContext", "ValidationExecutionResult", "AggregatedValidationResult",
    "FinalReportItem", "validate_json_list",
]
