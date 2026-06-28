"""Grounded L1 v2 claim contract for evidence and mechanism processing."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import Field, model_validator

from code_engine.schemas.models import CODEBaseModel
from code_engine.schemas.evidence import EvidenceType, StatementType


DirectRelationSign = Literal["positive", "negative", "neutral_or_association", "unknown"]
class L1ExtractedClaim(CODEBaseModel):
    claim_id: str
    paper_id: str
    chunk_id: str
    chunk_hash: str
    domain_id: str
    subdomain_id: str = ""
    domain_profile_id: str = "general_biomedical"
    prompt_profile_id: str
    prompt_version: str
    output_schema_version: str
    extraction_policy_version: str
    model_name: str
    model_family: str = "unknown"
    validator_profile_id: str = "general_validation"
    required_context_slots: list[str] = Field(default_factory=list)
    missing_required_context_slots: list[str] = Field(default_factory=list)
    domain_specific_warnings: list[str] = Field(default_factory=list)
    compiled_prompt_hash: str
    prompt_fingerprint: dict[str, Any] = Field(default_factory=dict)

    subject_raw: str
    subject_type: str = "unknown"
    relation_raw: str = ""
    relation_family: str = "unknown"
    direct_relation_sign: DirectRelationSign = "unknown"
    therapeutic_direction: Literal["beneficial", "adverse", "mixed", "not_applicable", "unknown"] = "unknown"
    object_raw: str
    object_type: str = "unknown"

    evidence_sentence: str = ""
    evidence_quote: str = ""
    section: str = ""
    statement_type: StatementType = "unknown"
    evidence_type: EvidenceType = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    negated: bool = False
    speculative: bool = False

    subject_span: str = ""
    relation_span: str = ""
    object_span: str = ""
    context_spans: dict[str, Any] = Field(default_factory=dict)

    species: str = ""
    sex: str = ""
    age: str = ""
    disease_model: str = ""
    brain_region: str = ""
    cell_type: str = ""
    treatment: str = ""
    dose: str = ""
    route: str = ""
    treatment_duration: str = ""
    time_after_treatment: str = ""
    assay_or_readout: str = ""
    behavioral_assay: str = ""
    clinical_outcome: str = ""
    genotype: str = ""
    oxygen_condition: str = ""
    localization: str = ""
    drug: str = ""
    target: str = ""
    binding_affinity: str = ""
    assay_type: str = ""
    experimental_system: str = ""
    population: str = ""
    intervention: str = ""
    comparator: str = ""
    trial_phase: str = ""
    sample_size: str = ""
    response_rate: str = ""
    remission_rate: str = ""
    adverse_events: str = ""
    timepoint: str = ""
    extraction_warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_grounding_rules(self):
        if not self.evidence_sentence.strip() and self.confidence > 0.6:
            self.confidence = 0.6
            if "confidence_capped_missing_evidence_sentence" not in self.extraction_warnings:
                self.extraction_warnings.append("confidence_capped_missing_evidence_sentence")
        if self.speculative and self.statement_type == "direct_experimental_result":
            self.statement_type = "speculation"
            if "speculative_claim_reclassified" not in self.extraction_warnings:
                self.extraction_warnings.append("speculative_claim_reclassified")
        fingerprint_values = {
            "paper_id": self.paper_id,
            "chunk_id": self.chunk_id,
            "chunk_hash": self.chunk_hash,
            "domain_id": self.domain_id,
            "subdomain_id": self.subdomain_id,
            "prompt_profile_id": self.prompt_profile_id,
            "prompt_version": self.prompt_version,
            "output_schema_version": self.output_schema_version,
            "extraction_policy_version": self.extraction_policy_version,
            "model_name": self.model_name,
            "model_family": self.model_family,
            "compiled_prompt_hash": self.compiled_prompt_hash,
        }
        fingerprint_values["fingerprint_hash"] = hashlib.sha256(
            json.dumps(fingerprint_values, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.prompt_fingerprint = fingerprint_values
        missing = [slot for slot in self.required_context_slots if not str(getattr(self, slot, "") or "").strip()]
        self.missing_required_context_slots = missing
        if missing and "missing_required_domain_context" not in self.domain_specific_warnings:
            self.domain_specific_warnings.append("missing_required_domain_context")
        return self


L1_CONTEXT_FIELDS = (
    "species", "sex", "age", "disease_model", "brain_region", "cell_type",
    "treatment", "dose", "route", "treatment_duration", "time_after_treatment",
    "assay_or_readout", "behavioral_assay", "clinical_outcome", "genotype",
    "oxygen_condition", "localization",
    "drug", "target", "binding_affinity", "assay_type", "experimental_system",
    "population", "intervention", "comparator", "trial_phase", "sample_size",
    "response_rate", "remission_rate", "adverse_events", "timepoint",
)
