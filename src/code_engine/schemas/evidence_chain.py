"""Schemas for claim-linked experimental evidence chains."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from code_engine.schemas.models import CODEBaseModel


ComparatorType = Literal["vehicle", "untreated", "wild_type", "negative_control", "positive_control", "other"]
ResultDirection = Literal["increase", "decrease", "no_change", "mixed", "unknown"]
AuthorCertainty = Literal["asserted", "suggested", "speculative", "not_stated"]
CausalEvidenceType = Literal[
    "association",
    "temporal_observation",
    "intervention",
    "dose_response",
    "pharmacological_blockade",
    "knockdown",
    "knockout",
    "overexpression",
    "rescue",
    "other",
]
CausalStrength = Literal[
    "association",
    "intervention_support",
    "necessity_support",
    "sufficiency_support",
    "rescue_support",
    "mechanistic_support",
    "unclear",
]
ValidationStatus = Literal["valid", "partial", "invalid"]
LinkRelation = Literal["supports", "weakens", "qualifies", "contextualizes", "unclear"]
LinkMethod = Literal["explicit_reference", "shared_result_anchor", "section_proximity", "structured_matching", "llm_assisted"]
ContextSourceType = Literal["explicit_claim_context", "evidence_chain_context"]
AgreementStatus = Literal["consistent", "mixed", "conflicting", "single_source"]
ParameterType = Literal[
    "dose",
    "concentration",
    "duration",
    "timepoint",
    "wavelength",
    "temperature",
    "centrifugation_speed",
    "rotation_speed",
    "volume",
    "mass",
    "frequency",
    "pH",
    "assay_readout",
    "statistical_value",
    "unknown_parameter",
]


class ExperimentalSystem(CODEBaseModel):
    species: str | None = None
    strain: str | None = None
    sex: str | None = None
    age: str | None = None
    disease_model: str | None = None
    tissue: str | None = None
    organ: str | None = None
    cell_type: str | None = None
    cell_line: str | None = None
    genotype: str | None = None
    localization: str | None = None


class Intervention(CODEBaseModel):
    agent_raw: str = ""
    canonical_id: str | None = None
    dose: str | None = None
    concentration: str | None = None
    route: str | None = None
    duration: str | None = None
    timing: str | None = None
    pretreatment: str | None = None
    combination: str | None = None
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    resolution_status: Literal["resolved", "ambiguous", "unresolved_fallback"] = "unresolved_fallback"


class Comparator(CODEBaseModel):
    comparator_type: ComparatorType = "other"
    description: str = ""


class Measurement(CODEBaseModel):
    assay: str | None = None
    endpoint: str | None = None
    measurement_time: str | None = None
    unit: str | None = None
    parameters: list[dict[str, Any]] = Field(default_factory=list)


class ObservedResult(CODEBaseModel):
    endpoint: str = ""
    direction: ResultDirection = "unknown"
    effect_description: str = ""
    effect_size: str | None = None
    statistical_support: str | None = None


class AuthorInterpretation(CODEBaseModel):
    text: str | None = None
    certainty: AuthorCertainty = "not_stated"


class CausalDesign(CODEBaseModel):
    evidence_type: CausalEvidenceType = "other"
    causal_strength: CausalStrength = "unclear"
    classification_basis: list[str] = Field(default_factory=list)


class EvidenceAnchor(CODEBaseModel):
    anchor_id: str | None = None
    section: str | None = None
    paragraph_id: str | None = None
    sentence_id: str | None = None
    sentence_text: str | None = None
    figure: str | None = None
    table: str | None = None
    supplement: str | None = None


class ExperimentalEvidenceChain(CODEBaseModel):
    schema_version: Literal["experimental_evidence_chain_v1"] = "experimental_evidence_chain_v1"
    chain_id: str
    paper_id: str = ""
    source_document_id: str = ""
    experimental_system: ExperimentalSystem = Field(default_factory=ExperimentalSystem)
    interventions: list[Intervention] = Field(default_factory=list)
    comparators: list[Comparator] = Field(default_factory=list)
    measurements: list[Measurement] = Field(default_factory=list)
    observed_results: list[ObservedResult] = Field(default_factory=list)
    author_interpretation: AuthorInterpretation = Field(default_factory=AuthorInterpretation)
    causal_design: CausalDesign = Field(default_factory=CausalDesign)
    evidence_anchors: list[EvidenceAnchor] = Field(default_factory=list)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    validation_status: ValidationStatus = "partial"

    @model_validator(mode="after")
    def validate_anchor_and_strength(self):
        if self.extraction_confidence > 0.6 and not self.evidence_anchors:
            raise ValueError("high-confidence evidence chains require at least one evidence anchor")
        if self.validation_status == "valid" and not self.evidence_anchors:
            raise ValueError("valid evidence chains require evidence anchors")
        return self


class ClaimEvidenceLink(CODEBaseModel):
    schema_version: Literal["claim_evidence_link_v1"] = "claim_evidence_link_v1"
    link_id: str
    claim_id: str
    chain_id: str
    paper_id: str = ""
    relation: LinkRelation = "unclear"
    link_method: LinkMethod = "structured_matching"
    link_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    link_basis: list[str] = Field(default_factory=list)
    score_components: dict[str, float] = Field(default_factory=dict)
    evidence_anchor_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def low_confidence_is_unclear(self):
        if self.link_confidence < 0.5 and self.relation != "unclear":
            raise ValueError("links below 0.5 confidence must use relation='unclear'")
        return self


class ConsolidatedContextValue(CODEBaseModel):
    value: Any
    source_type: ContextSourceType
    source_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    agreement_status: AgreementStatus = "single_source"


class UnlinkedClaimReason(CODEBaseModel):
    claim_id: str
    status: Literal["unlinked"] = "unlinked"
    primary_reason: Literal[
        "background_claim",
        "interpretive_claim",
        "review_or_prior_work_claim",
        "no_experimental_anchor",
        "no_compatible_chain",
        "insufficient_matching_evidence",
        "conflicting_candidate_links",
        "fulltext_experiment_not_reconstructed",
        "unsupported_claim_type",
    ]
    reason_details: list[str] = Field(default_factory=list)
    candidate_chain_count: int = 0
    highest_candidate_score: float | None = None


def validate_claim_evidence_references(
    links: list[ClaimEvidenceLink],
    *,
    claim_ids: set[str],
    chain_ids: set[str],
) -> None:
    missing_claims = sorted({link.claim_id for link in links if link.claim_id not in claim_ids})
    missing_chains = sorted({link.chain_id for link in links if link.chain_id not in chain_ids})
    if missing_claims or missing_chains:
        raise ValueError(f"claim-chain link references missing ids: claims={missing_claims}, chains={missing_chains}")
