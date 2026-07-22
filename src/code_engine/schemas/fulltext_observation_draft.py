"""Strict provider-owned draft contract for Fulltext L1 experimental observations."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DRAFT_SCHEMA_VERSION = "fulltext_l1_experimental_observation_draft_schema_v3_anchor_id_authoritative"


class DraftStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceAnchorReferenceDraft(DraftStrictModel):
    """Provider-owned anchor selection; source text is never provider-owned."""

    evidence_anchor_ids: list[str] = Field(min_length=1)
    span_type: Literal[
        "setup", "methods", "intervention", "comparison", "measurement",
        "observation", "interpretation", "other",
    ]
    model_selected_excerpt_raw: str | None = None


# Import compatibility only. The v3 JSON contract uses the explicit class name
# and contains no authoritative-looking ``text`` member.
EvidenceTextDraft = EvidenceAnchorReferenceDraft


class ExperimentDraft(DraftStrictModel):
    experiment_label_raw: str = Field(min_length=1)
    evidence_family_label_raw: str = Field(min_length=1)
    experimental_design_raw: str | None = None
    design_type_raw: str = Field(min_length=1)
    species_raw: str | None = None
    model_system_raw: str | None = None
    cell_line_or_type_raw: str | None = None
    tissue_raw: str | None = None
    disease_model_raw: str | None = None
    genotype_raw: str | None = None
    cohort_raw: str | None = None
    sample_raw: str | None = None
    comparison_arm_raw: str | None = None
    control_arm_raw: str | None = None


class InterventionDraft(DraftStrictModel):
    role_raw: str = Field(min_length=1)
    intervention_type_raw: str | None
    intervention_target_mention: str | None = None
    agent_or_drug_mention: str | None = None
    intervention_method_raw: str | None = None
    dose_raw: str | None = None
    duration_raw: str | None = None
    route_raw: str | None = None
    condition_raw: str | None = None
    evidence: EvidenceAnchorReferenceDraft | None = None


class MeasurementDraft(DraftStrictModel):
    measurement_dimension_raw: str = Field(min_length=1)
    measured_entity_mention: str | None = None
    outcome_mention: str | None = None
    assay_or_readout_raw: str | None = None
    endpoint_raw: str | None = None
    evidence: EvidenceAnchorReferenceDraft | None = None


class ObservationDraft(DraftStrictModel):
    observed_result: str = Field(min_length=1)
    lexical_direction_raw: str | None = None
    quantitative_result_raw: str | None = None
    statistical_support_raw: str | None = None
    uncertainty_raw: str | None = None
    comparison_raw: str | None = None
    negation: bool = False
    evidence: EvidenceAnchorReferenceDraft


class CandidateRelationDraft(DraftStrictModel):
    subject_mention: str | None = None
    object_mention: str | None = None
    relation_wording_raw: str | None = None
    lexical_direction_raw: str | None = None
    evidence_design_raw: str | None = None
    confidence_or_qualification_raw: str | None = None


class ExperimentalObservationDraft(DraftStrictModel):
    experiment: ExperimentDraft
    interventions: list[InterventionDraft]
    combination_mode_raw: str = Field(min_length=1)
    measurement: MeasurementDraft
    observation: ObservationDraft
    interpretation_raw: str | None = None
    interpretation_evidence: EvidenceAnchorReferenceDraft | None = None
    candidate_relation: CandidateRelationDraft
    statement_role: Literal[
        "current_study_experiment", "background", "review", "methods_only", "unknown",
    ]
    evidence_references: list[EvidenceAnchorReferenceDraft] = Field(min_length=1)
    extraction_warnings_raw: list[str] = Field(default_factory=list)


class FulltextL1DraftResponse(DraftStrictModel):
    schema_version: Literal[DRAFT_SCHEMA_VERSION]
    experimental_observations: list[ExperimentalObservationDraft]


def fulltext_l1_draft_prompt_examples() -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = EvidenceAnchorReferenceDraft(
        evidence_anchor_ids=["example_block:S0001"],
        span_type="observation",
        model_selected_excerpt_raw="HIF1A knockdown decreased target-gene expression versus control.",
    )
    row = ExperimentalObservationDraft(
        experiment=ExperimentDraft(
            experiment_label_raw="HIF1A knockdown experiment",
            evidence_family_label_raw="HIF1A perturbation",
            experimental_design_raw="Target knockdown compared with non-targeting control",
            design_type_raw="in_vitro",
            species_raw="Homo sapiens",
            model_system_raw="cultured cells",
            cell_line_or_type_raw="cultured cells",
            comparison_arm_raw="HIF1A knockdown",
            control_arm_raw="non-targeting control",
        ),
        interventions=[InterventionDraft(
            role_raw="primary",
            intervention_type_raw="knockdown",
            intervention_target_mention="HIF1A",
            intervention_method_raw="knockdown",
            evidence=evidence.model_copy(update={"span_type": "intervention"}),
        )],
        combination_mode_raw="unknown",
        measurement=MeasurementDraft(
            measurement_dimension_raw="abundance_expression",
            measured_entity_mention="target gene",
            outcome_mention="target-gene expression",
            endpoint_raw="target-gene expression",
            evidence=evidence.model_copy(update={"span_type": "measurement"}),
        ),
        observation=ObservationDraft(
            observed_result="decreased versus control",
            lexical_direction_raw="negative",
            comparison_raw="versus non-targeting control",
            evidence=evidence,
        ),
        candidate_relation=CandidateRelationDraft(
            subject_mention="HIF1A",
            object_mention="target-gene expression",
            relation_wording_raw="decreased",
            lexical_direction_raw="negative",
            evidence_design_raw="knockdown comparison",
        ),
        statement_role="current_study_experiment",
        evidence_references=[evidence],
    )
    empty = FulltextL1DraftResponse(schema_version=DRAFT_SCHEMA_VERSION, experimental_observations=[])
    nonempty = FulltextL1DraftResponse(schema_version=DRAFT_SCHEMA_VERSION, experimental_observations=[row])
    return empty.model_dump(mode="json"), nonempty.model_dump(mode="json")


__all__ = [
    "DRAFT_SCHEMA_VERSION", "EvidenceAnchorReferenceDraft", "EvidenceTextDraft", "ExperimentDraft", "InterventionDraft",
    "MeasurementDraft", "ObservationDraft", "CandidateRelationDraft",
    "ExperimentalObservationDraft", "FulltextL1DraftResponse",
    "fulltext_l1_draft_prompt_examples",
]
