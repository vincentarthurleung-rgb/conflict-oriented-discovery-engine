"""Strict Fulltext L1 v2 experimental-observation contract."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


MEASUREMENT_DIMENSIONS = (
    "abundance_expression", "phosphorylation", "activation_activity", "localization",
    "viability", "proliferation", "migration", "invasion", "apoptosis", "metastasis",
    "drug_response_resistance", "pathway_output", "morphology_marker_panel", "unknown",
)


def measurement_dimension_values() -> tuple[str, ...]:
    """Single runtime/prompt source for the controlled measurement vocabulary."""
    return MEASUREMENT_DIMENSIONS


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


# v2 remains frozen above for historical reads. v3 is an additive, domain-portable
# Formal contract and deliberately does not inherit the v2 single-intervention shape.
NormalizationStatus = Literal["resolved", "reviewable_unknown", "ambiguous", "unsupported", "rejected"]
InterventionRole = Literal[
    "primary", "secondary", "co_treatment", "rescue", "background_condition",
    "genetic_context", "environmental_context", "unknown",
]
CombinationMode = Literal["concurrent", "sequential", "rescue_design", "factorial", "conditioned_on", "unknown"]
InterventionTypeV3 = Literal[
    "knockout", "knockdown", "silencing", "inhibition", "depletion", "mutation",
    "overexpression", "activation", "agonism", "drug_treatment", "rescue",
    "re_expression", "combination_treatment", "observational_no_intervention", "unknown",
]
DesignTypeV3 = Literal["in_vitro", "in_vivo", "patient_sample", "computational", "review", "unknown"]
LexicalDirectionV3 = Literal["positive", "negative", "neutral", "unclear", "mixed"]


class FormalEvidenceSpanV3(StrictModel):
    evidence_span_id: str
    anchor_id: str | None = None
    block_id: str
    text: str
    text_hash: str
    source_role: Literal["current", "setup", "methods", "other"]
    span_type: Literal["setup", "intervention", "comparison", "measurement", "observation", "interpretation", "other"]
    section: str | None = None
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)


class DocumentProvenanceV3(StrictModel):
    paper_id: str
    pmid: str | None = None
    pmcid: str | None = None
    source_document_id: str
    fulltext_source_hash: str
    section: str | None = None
    subsection: str | None = None
    parent_block_id: str | None = None
    child_block_id: str
    evidence_spans: list[FormalEvidenceSpanV3] = Field(min_length=1)


class FormalIntervention(StrictModel):
    intervention_id: str
    role: InterventionRole
    intervention_type: InterventionTypeV3
    intervention_type_raw: str | None = None
    target_mention: str | None = None
    agent_mention: str | None = None
    method_raw: str | None = None
    dose_raw: str | None = None
    duration_raw: str | None = None
    route_raw: str | None = None
    condition_raw: str | None = None
    evidence_span_ids: list[str] = Field(default_factory=list)
    normalization_status: NormalizationStatus
    normalization_rule_id: str | None = None
    review_reasons: list[str] = Field(default_factory=list)


class ExperimentContextV3(StrictModel):
    experiment_id: str
    evidence_family_id: str
    experiment_label_raw: str
    evidence_family_label_raw: str
    experimental_design_raw: str | None = None
    design_type: DesignTypeV3
    design_type_raw: str | None = None
    design_normalization_status: NormalizationStatus
    design_normalization_rule_id: str | None = None
    design_review_reasons: list[str] = Field(default_factory=list)
    species_raw: str | None = None
    model_system_raw: str | None = None
    experimental_unit_raw: str | None = None
    tissue_raw: str | None = None
    disease_model_raw: str | None = None
    genotype_raw: str | None = None
    cohort_raw: str | None = None
    sample_raw: str | None = None
    comparison_arm_raw: str | None = None
    control_arm_raw: str | None = None


class MeasurementDetailV3(StrictModel):
    measurement_dimension: Literal[
        "abundance_expression", "phosphorylation", "activation_activity", "localization",
        "viability", "proliferation", "migration", "invasion", "apoptosis", "metastasis",
        "drug_response_resistance", "pathway_output", "morphology_marker_panel", "unknown",
    ]
    measurement_dimension_raw: str
    measured_entity_mention: str | None = None
    outcome_mention: str | None = None
    assay_or_readout_raw: str | None = None
    endpoint_raw: str | None = None
    evidence_span_ids: list[str] = Field(default_factory=list)
    normalization_status: NormalizationStatus
    normalization_rule_id: str | None = None
    review_reasons: list[str] = Field(default_factory=list)


class ObservationDetailV3(StrictModel):
    observed_result: str
    quantitative_result_raw: str | None = None
    statistical_support_raw: str | None = None
    uncertainty_raw: str | None = None
    comparison_raw: str | None = None
    negation: bool = False
    evidence_span_ids: list[str] = Field(min_length=1)


class CandidateRelationV3(StrictModel):
    subject_mention: str | None = None
    object_mention: str | None = None
    relation_raw: str | None = None
    lexical_direction: LexicalDirectionV3
    lexical_direction_raw: str | None = None
    normalization_status: NormalizationStatus
    normalization_rule_id: str | None = None
    review_reasons: list[str] = Field(default_factory=list)
    evidence_design_raw: str | None = None


class FormalEligibilityV3(StrictModel):
    formal_validity: Literal["valid", "rejected"]
    graph_eligible: bool
    strict_core_eligible: bool
    conflict_eligible: bool
    hypothesis_eligible: bool
    exclusion_reasons: list[str] = Field(default_factory=list)


class ExperimentalObservationV3(StrictModel):
    schema_version: Literal["fulltext_l1_experimental_observation_schema_v3"] = "fulltext_l1_experimental_observation_schema_v3"
    observation_id: str
    provenance: DocumentProvenanceV3
    evidence_span_ids: list[str] = Field(min_length=1)
    normalization_status: NormalizationStatus
    normalization_rule_id: str | None = None
    experiment: ExperimentContextV3
    interventions: list[FormalIntervention]
    combination_mode: CombinationMode = "unknown"
    combination_mode_raw: str | None = None
    combination_normalization_status: NormalizationStatus = "resolved"
    combination_normalization_rule_id: str | None = None
    combination_review_reasons: list[str] = Field(default_factory=list)
    measurement: MeasurementDetailV3
    observation: ObservationDetailV3
    interpretation_raw: str | None = None
    interpretation_evidence_span_ids: list[str] = Field(default_factory=list)
    candidate_relation: CandidateRelationV3
    statement_role: Literal["current_study_experiment", "background", "review", "methods_only", "unknown"]
    eligibility: FormalEligibilityV3
    extraction_warnings: list[str] = Field(default_factory=list)
    source_schema_version: str | None = None
    adapter_version: str | None = None
    lossy_fields: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)


class FulltextL1V3Response(StrictModel):
    schema_version: Literal["fulltext_l1_experimental_observation_schema_v3"]
    experimental_observations: list[ExperimentalObservationV3]


def fulltext_l1_v2_prompt_examples() -> tuple[dict[str, Any], dict[str, Any]]:
    """Return schema-validated empty and non-empty prompt examples.

    Constructing the example with the models themselves makes field renames,
    required-field changes, and Literal changes fail here instead of silently
    leaving a stale hand-written JSON contract in the provider prompt.
    """
    span = EvidenceSpan(
        text="HIF1A knockdown decreased target-gene expression versus control.",
        span_type="observation",
        section="Results",
        paragraph_id="p1",
        sentence_id="s1",
        char_start=0,
        char_end=64,
    )
    observation = ExperimentalObservationV2(
        observation_id="obs_example_001",
        provenance=DocumentProvenance(
            paper_id="paper_example",
            pmid=None,
            pmcid=None,
            source_document_id="source_document_example",
            section="Results",
            evidence_spans=[span],
            fulltext_source_hash="sha256_example_source_text",
        ),
        experiment=ExperimentContext(
            experiment_id="experiment_example_001",
            evidence_family_id="evidence_family_example_001",
            experimental_design="Target knockdown compared with control",
            design_type="in_vitro",
            model_system="cultured cells",
            species="Homo sapiens",
            comparison_arm="HIF1A knockdown",
            control_arm="non-targeting control",
        ),
        intervention=InterventionDetail(
            intervention_target_mention="HIF1A",
            intervention_type="knockdown",
            intervention_sign=None,
            intervention_span=span,
        ),
        measurement=MeasurementDetail(
            outcome_mention="target-gene expression",
            measured_entity_mention="target gene",
            measurement_dimension="abundance_expression",
            measurement_span=span,
        ),
        observation=ObservationDetail(
            observed_result="decreased versus control",
            observed_outcome_sign=None,
            comparison_relation="versus non-targeting control",
            observation_span=span,
        ),
        author_interpretation=AuthorInterpretationDetail(
            author_interpretation=None,
            interpretation_span=None,
        ),
        candidate_relation=CandidateRelation(
            subject_mention="HIF1A",
            object_mention="target-gene expression",
            relation_raw="decreased",
            lexical_direction="negative",
            evidence_design_candidate="knockdown comparison",
        ),
        statement_role="current_study_experiment",
    )
    empty = FulltextL1V2Response(
        schema_version="fulltext_l1_experimental_observation_schema_v2",
        experimental_observations=[],
    )
    nonempty = FulltextL1V2Response(
        schema_version="fulltext_l1_experimental_observation_schema_v2",
        experimental_observations=[observation],
    )
    return empty.model_dump(mode="json"), nonempty.model_dump(mode="json")
