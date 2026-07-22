"""Formal v3 eligibility and explicit compatibility boundaries."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from code_engine.fulltext.experimental_semantics_registry import REGISTRY_VERSION, normalize_semantics
from code_engine.schemas.fulltext_observation import (
    CandidateRelationV3, DocumentProvenanceV3, ExperimentalObservationV2,
    ExperimentalObservationV3, ExperimentContextV3, FormalEligibilityV3,
    FormalEvidenceSpanV3, FormalIntervention, MeasurementDetailV3, ObservationDetailV3,
)


V2_TO_V3_ADAPTER_VERSION = "experimental_observation_v2_to_v3_adapter_v1"
LEGACY_LOSSY_PROJECTION_VERSION = "experimental_observation_v3_legacy_lossy_projection_v1"
ELIGIBILITY_POLICY_VERSION = "formal_observation_v3_eligibility_v1"


def _hash(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def calculate_eligibility(*, interventions: list[FormalIntervention], design_status: str,
                          measurement_status: str, direction: str, direction_status: str,
                          combination_mode: str, combination_status: str,
                          comparison_raw: str | None, evidence_exact: bool) -> FormalEligibilityV3:
    reasons: list[str] = []
    if not evidence_exact: reasons.append("evidence_not_exact")
    if design_status != "resolved": reasons.append("design_reviewable_or_unresolved")
    if measurement_status != "resolved": reasons.append("measurement_reviewable_or_unresolved")
    if direction_status != "resolved" or direction in {"mixed", "unclear"}: reasons.append("direction_not_strict")
    if not comparison_raw: reasons.append("comparison_unclear")
    if any(item.normalization_status != "resolved" for item in interventions): reasons.append("intervention_semantics_unresolved")
    if len(interventions) > 1 and (combination_status != "resolved" or combination_mode == "unknown"):
        reasons.append("multi_intervention_attribution_unresolved")
    if not interventions: reasons.append("no_assigned_intervention")
    strict = not reasons
    conflict = strict and direction in {"positive", "negative"}
    return FormalEligibilityV3(
        formal_validity="valid", graph_eligible=evidence_exact,
        strict_core_eligible=strict, conflict_eligible=conflict,
        hypothesis_eligible=strict, exclusion_reasons=reasons,
    )


def adapt_v2_observation_to_v3(row: ExperimentalObservationV2) -> ExperimentalObservationV3:
    spans: list[FormalEvidenceSpanV3] = []
    for index, span in enumerate(row.provenance.evidence_spans):
        if span.char_start is None or span.char_end is None:
            raise ValueError("v2_to_v3_requires_exact_evidence_offsets")
        span_id = f"span_{_hash({'observation': row.observation_id, 'index': index, 'text': span.text})[:20]}"
        spans.append(FormalEvidenceSpanV3(
            evidence_span_id=span_id, block_id=row.provenance.source_document_id,
            anchor_version="legacy_v2_exact_span_adapter_v1",
            source_document_id=row.provenance.source_document_id,
            text=span.text, text_hash=_hash(span.text), source_role="current",
            span_type=span.span_type, section=span.section,
            char_start=span.char_start, char_end=span.char_end,
        ))
    primary_norm = normalize_semantics("intervention_type", row.intervention.intervention_type)
    primary_span_ids = [x.evidence_span_id for x in spans if row.intervention.intervention_span and x.text == row.intervention.intervention_span.text]
    interventions = [FormalIntervention(
        intervention_id=f"int_{_hash({'observation': row.observation_id, 'index': 0})[:20]}",
        role="primary", intervention_type=primary_norm.normalized_value,
        intervention_type_raw=row.intervention.intervention_type,
        target_mention=row.intervention.intervention_target_mention,
        method_raw=row.intervention.intervention_method,
        evidence_span_ids=primary_span_ids, normalization_status=primary_norm.status,
        normalization_rule_id=primary_norm.rule_id, review_reasons=list(primary_norm.review_reasons),
    )]
    lossy_fields: list[str] = []
    review_reasons: list[str] = []
    if row.intervention.secondary_intervention:
        lossy_fields.append("intervention.secondary_intervention")
        review_reasons.append("v2_secondary_intervention_string_has_no_structured_semantics")
        interventions.append(FormalIntervention(
            intervention_id=f"int_{_hash({'observation': row.observation_id, 'index': 1})[:20]}",
            role="secondary", intervention_type="unknown",
            intervention_type_raw=row.intervention.secondary_intervention,
            condition_raw=row.intervention.secondary_intervention,
            normalization_status="reviewable_unknown", normalization_rule_id=V2_TO_V3_ADAPTER_VERSION,
            review_reasons=["unstructured_v2_secondary_intervention"],
        ))
    for value in row.intervention.combination_intervention:
        lossy_fields.append("intervention.combination_intervention")
        interventions.append(FormalIntervention(
            intervention_id=f"int_{_hash({'observation': row.observation_id, 'combination': value})[:20]}",
            role="co_treatment", intervention_type="unknown", intervention_type_raw=value,
            condition_raw=value, normalization_status="reviewable_unknown",
            normalization_rule_id=V2_TO_V3_ADAPTER_VERSION,
            review_reasons=["unstructured_v2_combination_intervention"],
        ))
    design = normalize_semantics("design_type", row.experiment.design_type)
    measurement = normalize_semantics("measurement_dimension", row.measurement.measurement_dimension)
    direction = normalize_semantics("lexical_direction", row.candidate_relation.lexical_direction)
    combination_mode = "unknown" if len(interventions) > 1 else "unknown"
    combination_status = "reviewable_unknown" if len(interventions) > 1 else "resolved"
    eligibility = calculate_eligibility(
        interventions=interventions, design_status=design.status, measurement_status=measurement.status,
        direction=direction.normalized_value, direction_status=direction.status,
        combination_mode=combination_mode, combination_status=combination_status,
        comparison_raw=row.observation.comparison_relation or row.experiment.comparison_arm,
        evidence_exact=True,
    )
    review_reasons = sorted(set(review_reasons) | set(eligibility.exclusion_reasons)
                            | {reason for item in interventions for reason in item.review_reasons})
    normalization_status = ("ambiguous" if direction.status == "ambiguous"
                            else "reviewable_unknown" if review_reasons else "resolved")
    return ExperimentalObservationV3(
        observation_id=row.observation_id,
        provenance=DocumentProvenanceV3(
            paper_id=row.provenance.paper_id, pmid=row.provenance.pmid, pmcid=row.provenance.pmcid,
            source_document_id=row.provenance.source_document_id,
            fulltext_source_hash=row.provenance.fulltext_source_hash, section=row.provenance.section,
            subsection=row.provenance.subsection, child_block_id=row.provenance.source_document_id,
            evidence_spans=spans,
        ),
        evidence_span_ids=[x.evidence_span_id for x in spans],
        normalization_status=normalization_status,
        normalization_rule_id=f"{V2_TO_V3_ADAPTER_VERSION}:aggregate_v1",
        experiment=ExperimentContextV3(
            experiment_id=row.experiment.experiment_id, evidence_family_id=row.experiment.evidence_family_id,
            experiment_label_raw=row.experiment.experiment_id,
            evidence_family_label_raw=row.experiment.evidence_family_id,
            experimental_design_raw=row.experiment.experimental_design,
            design_type=design.normalized_value, design_type_raw=row.experiment.design_type,
            design_normalization_status=design.status, design_normalization_rule_id=design.rule_id,
            design_review_reasons=list(design.review_reasons), species_raw=row.experiment.species,
            model_system_raw=row.experiment.model_system,
            experimental_unit_raw=row.experiment.cell_line or row.experiment.cell_type,
            tissue_raw=row.experiment.tissue, disease_model_raw=row.experiment.disease_model,
            genotype_raw=row.experiment.genotype, sample_raw=row.experiment.replicate_sample_information,
            comparison_arm_raw=row.experiment.comparison_arm, control_arm_raw=row.experiment.control_arm,
        ),
        interventions=interventions, combination_mode=combination_mode,
        combination_normalization_status=combination_status,
        combination_normalization_rule_id=V2_TO_V3_ADAPTER_VERSION,
        combination_review_reasons=["combination_mode_not_structured_in_v2"] if len(interventions) > 1 else [],
        measurement=MeasurementDetailV3(
            measurement_dimension=measurement.normalized_value,
            measurement_dimension_raw=row.measurement.measurement_dimension,
            measured_entity_mention=row.measurement.measured_entity_mention,
            outcome_mention=row.measurement.outcome_mention,
            assay_or_readout_raw=row.measurement.assay or row.measurement.measurement_method,
            endpoint_raw=row.measurement.outcome_mention,
            evidence_span_ids=[x.evidence_span_id for x in spans if row.measurement.measurement_span and x.text == row.measurement.measurement_span.text],
            normalization_status=measurement.status, normalization_rule_id=measurement.rule_id,
            review_reasons=list(measurement.review_reasons),
        ),
        observation=ObservationDetailV3(
            observed_result=row.observation.observed_result or "unknown result",
            quantitative_result_raw=row.observation.effect_size_or_magnitude,
            statistical_support_raw=row.observation.statistical_support,
            uncertainty_raw=row.observation.uncertainty,
            comparison_raw=row.observation.comparison_relation,
            negation=row.observation.negation,
            evidence_span_ids=[x.evidence_span_id for x in spans if row.observation.observation_span and x.text == row.observation.observation_span.text] or [spans[0].evidence_span_id],
        ),
        interpretation_raw=row.author_interpretation.author_interpretation or row.author_interpretation.author_conclusion,
        candidate_relation=CandidateRelationV3(
            subject_mention=row.candidate_relation.subject_mention,
            object_mention=row.candidate_relation.object_mention,
            relation_raw=row.candidate_relation.relation_raw,
            lexical_direction=direction.normalized_value,
            lexical_direction_raw=row.candidate_relation.lexical_direction,
            normalization_status=direction.status, normalization_rule_id=direction.rule_id,
            review_reasons=list(direction.review_reasons),
            evidence_design_raw=row.candidate_relation.evidence_design_candidate,
        ),
        statement_role=row.statement_role, eligibility=eligibility,
        extraction_warnings=row.extraction_warnings,
        source_schema_version=row.schema_version, adapter_version=V2_TO_V3_ADAPTER_VERSION,
        lossy_fields=sorted(set(lossy_fields)), review_reasons=review_reasons,
    )


def legacy_lossy_projection(row: ExperimentalObservationV3) -> dict[str, Any]:
    primary = row.interventions[0] if row.interventions else None
    return {
        "projection_version": LEGACY_LOSSY_PROJECTION_VERSION,
        "source_schema_version": row.schema_version,
        "observation_id": row.observation_id,
        "intervention": None if primary is None else primary.model_dump(mode="json"),
        "discarded_intervention_ids": [x.intervention_id for x in row.interventions[1:]],
        "lossy_fields": ["interventions[1:]", "combination_mode"] if len(row.interventions) > 1 else [],
        "review_reasons": ["legacy_consumer_cannot_represent_multi_intervention"] if len(row.interventions) > 1 else [],
    }


__all__ = ["V2_TO_V3_ADAPTER_VERSION", "LEGACY_LOSSY_PROJECTION_VERSION", "ELIGIBILITY_POLICY_VERSION",
           "calculate_eligibility", "adapt_v2_observation_to_v3", "legacy_lossy_projection"]
