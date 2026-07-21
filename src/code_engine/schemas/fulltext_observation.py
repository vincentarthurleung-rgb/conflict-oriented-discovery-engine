"""Strict Fulltext L1 v2 experimental-observation contract."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceSpan(StrictModel):
    text: str
    span_type: Literal["setup", "intervention", "comparison", "measurement", "observation", "interpretation", "other"] = "other"
    section: str | None = None
    paragraph_id: str | None = None
    sentence_id: str | None = None
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)


class DocumentProvenance(StrictModel):
    paper_id: str
    pmid: str | None = None
    pmcid: str | None = None
    source_document_id: str
    section: str | None = None
    subsection: str | None = None
    paragraph_id: str | None = None
    sentence_ids: list[str] = Field(default_factory=list)
    evidence_spans: list[EvidenceSpan]
    figure_ids: list[str] = Field(default_factory=list)
    table_ids: list[str] = Field(default_factory=list)
    supplementary_reference: str | None = None
    fulltext_source_hash: str


class ExperimentContext(StrictModel):
    experiment_id: str
    evidence_family_id: str
    experimental_design: str | None = None
    design_type: Literal["in_vitro", "in_vivo", "patient_sample", "computational", "review", "unknown"] = "unknown"
    model_system: str | None = None
    species: str | None = None
    species_source: str | None = None
    cell_line: str | None = None
    cell_type: str | None = None
    tissue: str | None = None
    disease_model: str | None = None
    genotype: str | None = None
    localization: str | None = None
    treatment: str | None = None
    dose: str | None = None
    duration_time: str | None = None
    comparison_arm: str | None = None
    control_arm: str | None = None
    replicate_sample_information: str | None = None
    context_source: list[str] = Field(default_factory=list)
    binding_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class InterventionDetail(StrictModel):
    intervention_target_mention: str | None = None
    intervention_type: Literal[
        "knockout", "knockdown", "silencing", "inhibition", "depletion", "mutation",
        "overexpression", "activation", "agonism", "drug_treatment", "rescue",
        "re_expression", "combination_treatment", "observational_no_intervention", "unknown",
    ] = "unknown"
    intervention_sign: Literal[-1, 0, 1] | None = None
    intervention_method: str | None = None
    secondary_intervention: str | None = None
    rescue_intervention: str | None = None
    combination_intervention: list[str] = Field(default_factory=list)
    intervention_span: EvidenceSpan | None = None


class MeasurementDetail(StrictModel):
    outcome_mention: str | None = None
    measured_entity_mention: str | None = None
    measurement_dimension: Literal[
        "abundance_expression", "phosphorylation", "activation_activity", "localization",
        "viability", "proliferation", "migration", "invasion", "apoptosis", "metastasis",
        "drug_response_resistance", "pathway_output", "morphology_marker_panel", "unknown",
    ] = "unknown"
    assay: str | None = None
    measurement_method: str | None = None
    measurement_span: EvidenceSpan | None = None


class ObservationDetail(StrictModel):
    observed_result: str | None = None
    observed_outcome_sign: Literal[-1, 0, 1] | None = None
    effect_size_or_magnitude: str | None = None
    statistical_support: str | None = None
    uncertainty: str | None = None
    negation: bool = False
    comparison_relation: str | None = None
    observation_span: EvidenceSpan | None = None


class AuthorInterpretationDetail(StrictModel):
    author_interpretation: str | None = None
    author_conclusion: str | None = None
    conclusion_scope: str | None = None
    limitation_statements: list[str] = Field(default_factory=list)
    interpretation_span: EvidenceSpan | None = None


class CandidateRelation(StrictModel):
    subject_mention: str | None = None
    object_mention: str | None = None
    relation_raw: str | None = None
    lexical_direction: Literal["positive", "negative", "neutral", "unclear"] = "unclear"
    evidence_design_candidate: str | None = None


class ExperimentalObservationV2(StrictModel):
    schema_version: Literal["fulltext_l1_experimental_observation_schema_v2"] = "fulltext_l1_experimental_observation_schema_v2"
    observation_id: str
    provenance: DocumentProvenance
    experiment: ExperimentContext
    intervention: InterventionDetail
    measurement: MeasurementDetail
    observation: ObservationDetail
    author_interpretation: AuthorInterpretationDetail = Field(default_factory=AuthorInterpretationDetail)
    candidate_relation: CandidateRelation = Field(default_factory=CandidateRelation)
    statement_role: Literal["current_study_experiment", "background", "review", "methods_only", "unknown"] = "unknown"
    extraction_warnings: list[str] = Field(default_factory=list)
    parent_abstract_run_id: str | None = None
    source_abstract_observation_id: str | None = None
    abstract_prior_candidates: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_grounded_observation(self):
        if not self.provenance.evidence_spans:
            raise ValueError("an observation requires at least one supporting evidence span")
        if self.statement_role == "current_study_experiment" and not self.observation.observation_span:
            raise ValueError("current-study observations require observation_span")
        return self


class FulltextL1V2Response(StrictModel):
    schema_version: Literal["fulltext_l1_experimental_observation_schema_v2"]
    experimental_observations: list[ExperimentalObservationV2]

