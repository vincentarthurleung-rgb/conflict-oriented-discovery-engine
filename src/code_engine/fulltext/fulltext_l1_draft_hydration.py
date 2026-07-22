"""Deterministic boundary from provider drafts to the strict formal L1 schema."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from code_engine.schemas.fulltext_observation import (
    AuthorInterpretationDetail, CandidateRelation, DocumentProvenance, EvidenceSpan,
    ExperimentContext, ExperimentalObservationV2, FulltextL1V2Response,
    InterventionDetail, MeasurementDetail, ObservationDetail,
)
from code_engine.schemas.fulltext_observation_draft import (
    DRAFT_SCHEMA_VERSION, ExperimentalObservationDraft, FulltextL1DraftResponse,
)


HYDRATOR_VERSION = "fulltext_l1_draft_hydrator_v1"
ENUM_NORMALIZATION_VERSION = "fulltext_l1_draft_enum_normalization_v1"
OBSERVATION_ID_VERSION = "fulltext_l1_draft_observation_id_sha256_v1"


class DraftHydrationError(ValueError):
    def __init__(self, reason: str, detail: str | None = None):
        self.reason = reason
        self.detail = detail or reason
        super().__init__(self.detail)


@dataclass(frozen=True)
class TrustedDraftContext:
    run_id: str
    block_id: str
    parent_block_id: str | None
    child_block_id: str | None
    block_text: str
    source_block_hash: str
    source_document_id: str
    paper_id: str
    pmid: str | None
    pmcid: str | None
    fulltext_source_hash: str
    source_artifact: str
    section: str | None = None
    subsection: str | None = None
    parser_version: str | None = None
    extractor_version: str | None = None


@dataclass
class HydrationBatch:
    formal_response: dict[str, Any]
    audit: list[dict[str, Any]]
    rejected: list[dict[str, Any]]


_DESIGN = {value: value for value in ("in_vitro", "in_vivo", "patient_sample", "computational", "review", "unknown")}
_INTERVENTION = {value: value for value in (
    "knockout", "knockdown", "silencing", "inhibition", "depletion", "mutation",
    "overexpression", "activation", "agonism", "drug_treatment", "rescue",
    "re_expression", "combination_treatment", "observational_no_intervention", "unknown",
)}
_INTERVENTION.update({
    "drug treatment": "drug_treatment", "re-expression": "re_expression",
    "combination treatment": "combination_treatment", "genetic knockout": "knockout",
})
_MEASUREMENT = {value: value for value in (
    "abundance_expression", "phosphorylation", "activation_activity", "localization",
    "viability", "proliferation", "migration", "invasion", "apoptosis", "metastasis",
    "drug_response_resistance", "pathway_output", "morphology_marker_panel", "unknown",
)}
_MEASUREMENT.update({
    "protein_level": "abundance_expression", "protein_expression": "abundance_expression",
    "mrna_expression": "abundance_expression", "gene_expression": "abundance_expression",
    "phosphorylation_level": "phosphorylation", "pathway_activation": "activation_activity",
    "cell_survival": "viability",
})
_LEXICAL = {"positive": "positive", "negative": "negative", "neutral": "neutral", "unclear": "unclear", "unknown": "unclear"}


def _hash(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _key(value: Any) -> str:
    return str(value).strip().casefold()


def normalize_draft_enum(kind: str, raw: Any) -> tuple[str | None, dict[str, Any]]:
    """Apply frozen, auditable mappings; unresolved values never reach Formal."""
    key = _key(raw) if raw is not None else ""
    tables = {"design_type": _DESIGN, "intervention_type": _INTERVENTION,
              "measurement_dimension": _MEASUREMENT, "lexical_direction": _LEXICAL}
    if kind not in tables:
        raise ValueError(f"unknown enum kind: {kind}")
    mapped = tables[kind].get(key)
    reason = "exact_controlled_value" if mapped == key else "frozen_equivalent_mapping" if mapped else "no_safe_mapping"
    audit = {"normalization_version": ENUM_NORMALIZATION_VERSION, "enum_kind": kind,
             "raw_value": raw, "normalized_value": mapped, "status": "mapped" if mapped else "unresolved",
             "reason": reason}
    return mapped, audit


def locate_exact_evidence(text: str, context: TrustedDraftContext, *, span_type: str) -> tuple[EvidenceSpan, dict[str, Any]]:
    if not text:
        raise DraftHydrationError("evidence_span_missing")
    starts: list[int] = []
    offset = 0
    while True:
        found = context.block_text.find(text, offset)
        if found < 0:
            break
        starts.append(found)
        offset = found + 1
    if not starts:
        raise DraftHydrationError("evidence_span_missing", f"evidence_span_missing:{text[:80]}")

    def line_prefix(position: int) -> str:
        start = context.block_text.rfind("\n", 0, position) + 1
        return context.block_text[start:position]

    if span_type == "methods":
        candidates = [x for x in starts if "LINKED_METHODS:" in line_prefix(x)]
    else:
        candidates = [x for x in starts if "LINKED_METHODS:" not in line_prefix(x)]
    if len(candidates) == 1:
        starts = candidates
    elif len(starts) != 1:
        raise DraftHydrationError("evidence_span_ambiguous", f"evidence_span_ambiguous:{text[:80]}")
    start = starts[0]
    if span_type == "observation" and "LINKED_METHODS:" in line_prefix(start):
        raise DraftHydrationError("provenance_binding_failed", "observation evidence occurs only in linked Methods context")
    formal_type = "setup" if span_type == "methods" else span_type
    span = EvidenceSpan(text=text, span_type=formal_type, section=context.section,
                        char_start=start, char_end=start + len(text))
    audit = {"status": "exact", "draft_span_type": span_type, "formal_span_type": formal_type,
             "char_start": start, "char_end": start + len(text), "evidence_text_hash": _hash(text),
             "source_block_hash": context.source_block_hash}
    return span, audit


def deterministic_draft_observation_id(draft: ExperimentalObservationDraft, context: TrustedDraftContext,
                                       evidence_span: EvidenceSpan) -> tuple[str, dict[str, Any]]:
    inputs = {
        "version": OBSERVATION_ID_VERSION,
        "source_document_id": context.source_document_id,
        "parent_block_id": context.parent_block_id,
        "child_block_id": context.child_block_id or context.block_id,
        "experiment_label_raw": draft.experiment.experiment_label_raw,
        "evidence_family_label_raw": draft.experiment.evidence_family_label_raw,
        "species_raw": draft.experiment.species_raw,
        "model_system_raw": draft.experiment.model_system_raw,
        "interventions": [item.model_dump(mode="json", exclude={"evidence_text"}) for item in draft.interventions],
        "comparison": {"arm": draft.experiment.comparison_arm_raw, "control": draft.experiment.control_arm_raw,
                       "observation": draft.observation.comparison_raw},
        "measurement": draft.measurement.model_dump(mode="json", exclude={"evidence_text"}),
        "observed_result": draft.observation.observed_result,
        "evidence_span_hash": _hash({"text": evidence_span.text, "char_start": evidence_span.char_start,
                                     "char_end": evidence_span.char_end}),
    }
    digest = _hash(inputs)
    return f"ftl1draft_{digest[:24]}", {"algorithm_version": OBSERVATION_ID_VERSION, "inputs": inputs, "inputs_hash": digest}


def _require_enum(kind: str, raw: Any, audit: list[dict[str, Any]]) -> str:
    mapped, item = normalize_draft_enum(kind, raw)
    audit.append(item)
    if mapped is None:
        raise DraftHydrationError("enum_unresolved", f"{kind}:{raw!r}")
    return mapped


def hydrate_draft_observation(draft: ExperimentalObservationDraft, context: TrustedDraftContext,
                              *, observation_index: int = 0) -> tuple[dict[str, Any], dict[str, Any]]:
    audit: dict[str, Any] = {
        "hydrator_version": HYDRATOR_VERSION, "enum_normalization_version": ENUM_NORMALIZATION_VERSION,
        "draft_schema_version": DRAFT_SCHEMA_VERSION, "block_id": context.block_id,
        "parent_block_id": context.parent_block_id, "child_block_id": context.child_block_id,
        "observation_index": observation_index, "enum_mappings": [], "evidence_spans": [],
        "trusted_provenance_source": context.source_artifact,
    }
    if len(draft.interventions) != 1:
        audit["multi_intervention_count"] = len(draft.interventions)
        audit["multi_intervention_draft"] = [x.model_dump(mode="json") for x in draft.interventions]
        raise DraftHydrationError("unsupported_multi_intervention", "Formal v2 cannot losslessly represent structured multiple interventions")
    evidence: list[EvidenceSpan] = []
    seen: set[tuple[str, str]] = set()
    for item in [*draft.evidence_texts, draft.observation.evidence_text,
                 draft.measurement.evidence_text, draft.interventions[0].evidence_text,
                 draft.interpretation_evidence_text]:
        if item is None or (item.text, item.span_type) in seen:
            continue
        seen.add((item.text, item.span_type))
        span, span_audit = locate_exact_evidence(item.text, context, span_type=item.span_type)
        evidence.append(span); audit["evidence_spans"].append(span_audit)
    observation_span, observation_span_audit = locate_exact_evidence(
        draft.observation.evidence_text.text, context, span_type="observation")
    if not any(x.text == observation_span.text and x.char_start == observation_span.char_start for x in evidence):
        evidence.append(observation_span); audit["evidence_spans"].append(observation_span_audit)

    enums = audit["enum_mappings"]
    design = _require_enum("design_type", draft.experiment.design_type_raw, enums)
    intervention_type = _require_enum("intervention_type", draft.interventions[0].intervention_type_raw, enums)
    dimension = _require_enum("measurement_dimension", draft.measurement.measurement_dimension_raw, enums)
    lexical = _require_enum("lexical_direction", draft.candidate_relation.lexical_direction_raw, enums)
    observation_id, id_audit = deterministic_draft_observation_id(draft, context, observation_span)
    audit["observation_id_generation"] = id_audit
    experiment_hash = _hash({"block": context.block_id, "label": draft.experiment.experiment_label_raw})[:20]
    family_hash = _hash({"block": context.block_id, "label": draft.experiment.evidence_family_label_raw})[:20]
    intervention = draft.interventions[0]
    measurement_span = next((x for x in evidence if draft.measurement.evidence_text and x.text == draft.measurement.evidence_text.text), None)
    intervention_span = next((x for x in evidence if intervention.evidence_text and x.text == intervention.evidence_text.text), None)
    interpretation_span = next((x for x in evidence if draft.interpretation_evidence_text and x.text == draft.interpretation_evidence_text.text), None)
    formal = ExperimentalObservationV2(
        observation_id=observation_id,
        provenance=DocumentProvenance(
            paper_id=context.paper_id, pmid=context.pmid, pmcid=context.pmcid,
            source_document_id=context.source_document_id, section=context.section,
            subsection=context.subsection, evidence_spans=evidence,
            fulltext_source_hash=context.fulltext_source_hash,
        ),
        experiment=ExperimentContext(
            experiment_id=f"exp_{experiment_hash}", evidence_family_id=f"ef_{family_hash}",
            experimental_design=draft.experiment.experimental_design_raw, design_type=design,
            model_system=draft.experiment.model_system_raw, species=draft.experiment.species_raw,
            cell_line=draft.experiment.cell_line_or_type_raw, tissue=draft.experiment.tissue_raw,
            disease_model=draft.experiment.disease_model_raw, genotype=draft.experiment.genotype_raw,
            comparison_arm=draft.experiment.comparison_arm_raw, control_arm=draft.experiment.control_arm_raw,
            replicate_sample_information=draft.experiment.sample_raw or draft.experiment.cohort_raw,
            context_source=["trusted_block_exact_evidence"], binding_confidence=1.0,
        ),
        intervention=InterventionDetail(
            intervention_target_mention=intervention.intervention_target_mention or intervention.agent_or_drug_mention,
            intervention_type=intervention_type, intervention_method=intervention.intervention_method_raw,
            intervention_span=intervention_span,
        ),
        measurement=MeasurementDetail(
            outcome_mention=draft.measurement.outcome_mention or draft.measurement.endpoint_raw,
            measured_entity_mention=draft.measurement.measured_entity_mention,
            measurement_dimension=dimension, assay=draft.measurement.assay_or_readout_raw,
            measurement_span=measurement_span,
        ),
        observation=ObservationDetail(
            observed_result=draft.observation.observed_result,
            effect_size_or_magnitude=draft.observation.quantitative_result_raw,
            statistical_support=draft.observation.statistical_support_raw,
            uncertainty=draft.observation.uncertainty_raw, negation=draft.observation.negation,
            comparison_relation=draft.observation.comparison_raw, observation_span=observation_span,
        ),
        author_interpretation=AuthorInterpretationDetail(
            author_interpretation=draft.interpretation_raw, interpretation_span=interpretation_span,
        ),
        candidate_relation=CandidateRelation(
            subject_mention=draft.candidate_relation.subject_mention,
            object_mention=draft.candidate_relation.object_mention,
            relation_raw=draft.candidate_relation.relation_wording_raw,
            lexical_direction=lexical,
            evidence_design_candidate=draft.candidate_relation.evidence_design_raw,
        ),
        statement_role=draft.statement_role,
        extraction_warnings=draft.extraction_warnings_raw,
    )
    audit.update({"status": "hydrated_success", "observation_id": observation_id,
                  "trusted_provenance": {"paper_id": context.paper_id, "pmid": context.pmid,
                    "pmcid": context.pmcid, "source_document_id": context.source_document_id,
                    "fulltext_source_hash": context.fulltext_source_hash}})
    return formal.model_dump(mode="json"), audit


def hydrate_draft_response(response: FulltextL1DraftResponse, context: TrustedDraftContext) -> HydrationBatch:
    formal_rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, draft in enumerate(response.experimental_observations):
        try:
            row, item = hydrate_draft_observation(draft, context, observation_index=index)
            formal_rows.append(row); audit.append(item)
        except DraftHydrationError as exc:
            rejected.append({"block_id": context.block_id, "observation_index": index,
                             "status": exc.reason, "reason": exc.detail,
                             "draft": draft.model_dump(mode="json"),
                             "hydrator_version": HYDRATOR_VERSION,
                             "enum_normalization_version": ENUM_NORMALIZATION_VERSION})
        except ValidationError as exc:
            rejected.append({"block_id": context.block_id, "observation_index": index,
                             "status": "formal_schema_failed", "reason": str(exc),
                             "draft": draft.model_dump(mode="json"),
                             "hydrator_version": HYDRATOR_VERSION})
    validated = FulltextL1V2Response(
        schema_version="fulltext_l1_experimental_observation_schema_v2",
        experimental_observations=formal_rows,
    )
    return HydrationBatch(validated.model_dump(mode="json"), audit, rejected)


__all__ = [
    "HYDRATOR_VERSION", "ENUM_NORMALIZATION_VERSION", "OBSERVATION_ID_VERSION",
    "DraftHydrationError", "TrustedDraftContext", "HydrationBatch", "normalize_draft_enum",
    "locate_exact_evidence", "deterministic_draft_observation_id",
    "hydrate_draft_observation", "hydrate_draft_response",
]
