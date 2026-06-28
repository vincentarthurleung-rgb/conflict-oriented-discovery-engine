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
    hypothesis_id: str
    domain_id: str
    validator_profile_id: str
    relation_type: str = "unknown"
    evidence_modality: str = "unknown"
    subject_entity: str = ""
    object_entity: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
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


__all__ = ["ValidationQuestion", "ValidationPlan", "ValidationResult", "ValidationCoverageReport", "FinalReportItem", "validate_json_list"]
