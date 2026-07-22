"""Draft-to-Formal-v3 hydration with anchors, registry normalization, and eligibility."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from code_engine.fulltext.evidence_anchors import (
    EVIDENCE_ANCHOR_VERSION, EvidenceAnchor, generate_evidence_anchors, resolve_anchor,
)
from code_engine.fulltext.experimental_semantics_registry import REGISTRY_VERSION, normalize_semantics
from code_engine.fulltext.fulltext_observation_v3 import ELIGIBILITY_POLICY_VERSION, calculate_eligibility
from code_engine.schemas.fulltext_observation import (
    CandidateRelationV3, DocumentProvenanceV3, ExperimentalObservationV3,
    ExperimentContextV3, FormalEvidenceSpanV3, FormalIntervention,
    FulltextL1V3Response, MeasurementDetailV3, ObservationDetailV3,
)
from code_engine.schemas.fulltext_observation_draft import (
    DRAFT_SCHEMA_VERSION, EvidenceTextDraft, ExperimentalObservationDraft, FulltextL1DraftResponse,
)


HYDRATOR_VERSION = "fulltext_l1_draft_hydrator_v3_formal_v3_authoritative_anchors"
COMPLETENESS_POLICY_VERSION = "fulltext_l1_formal_block_completeness_v2"
OBSERVATION_ID_VERSION = "fulltext_l1_draft_observation_id_sha256_v2_anchor_stable"


class DraftHydrationV3Error(ValueError):
    def __init__(self, reason: str, detail: str | None = None):
        self.reason = reason; self.detail = detail or reason
        super().__init__(self.detail)


@dataclass(frozen=True)
class TrustedDraftContextV3:
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
    domain_profile: str = "generic_experimental"


@dataclass
class HydrationBatchV3:
    formal_response: dict[str, Any]
    audit: list[dict[str, Any]]
    rejected: list[dict[str, Any]]


def _hash(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _span_from_anchor(anchor: EvidenceAnchor, span_type: str) -> FormalEvidenceSpanV3:
    formal_type = "setup" if span_type == "methods" else span_type
    return FormalEvidenceSpanV3(
        evidence_span_id=f"span_{_hash({'anchor': anchor.anchor_id, 'type': formal_type})[:20]}",
        anchor_id=anchor.anchor_id, anchor_version=EVIDENCE_ANCHOR_VERSION,
        source_document_id=anchor.source_document_id, block_id=anchor.block_id, text=anchor.text,
        text_hash=anchor.text_hash, source_role=anchor.source_role, span_type=formal_type,
        section=anchor.section, char_start=anchor.char_start, char_end=anchor.char_end,
    )


def resolve_draft_evidence(evidence: EvidenceTextDraft, context: TrustedDraftContextV3,
                           anchors: list[EvidenceAnchor]) -> tuple[list[FormalEvidenceSpanV3], str]:
    spans = []; seen: set[str] = set()
    for anchor_id in evidence.evidence_anchor_ids:
        if anchor_id in seen:
            continue
        seen.add(anchor_id)
        anchor = resolve_anchor(
            anchor_id, anchors, expected_block_id=context.block_id,
            source_text=context.block_text, expected_source_document_id=context.source_document_id,
        )
        if evidence.span_type == "observation" and anchor.source_role == "methods":
            raise DraftHydrationV3Error("evidence_unresolved", "results_observation_cannot_bind_methods_only_anchor")
        spans.append(_span_from_anchor(anchor, evidence.span_type))
    return spans, "authoritative_anchor"


def iter_draft_evidence_references(draft: FulltextL1DraftResponse | ExperimentalObservationDraft):
    observations = (draft.experimental_observations if isinstance(draft, FulltextL1DraftResponse) else [draft])
    for oi, observation in enumerate(observations):
        for ei, evidence in enumerate(observation.evidence_references):
            yield f"experimental_observations.{oi}.evidence_references.{ei}", evidence
        yield f"experimental_observations.{oi}.observation.evidence", observation.observation.evidence
        if observation.measurement.evidence:
            yield f"experimental_observations.{oi}.measurement.evidence", observation.measurement.evidence
        if observation.interpretation_evidence:
            yield f"experimental_observations.{oi}.interpretation_evidence", observation.interpretation_evidence
        for ii, intervention in enumerate(observation.interventions):
            if intervention.evidence:
                yield f"experimental_observations.{oi}.interventions.{ii}.evidence", intervention.evidence


def audit_draft_anchor_bindings(draft: FulltextL1DraftResponse | ExperimentalObservationDraft,
                                context: TrustedDraftContextV3,
                                anchors: list[EvidenceAnchor] | None = None) -> dict[str, Any]:
    """Audit identity failures separately from non-authoritative excerpt differences."""
    anchors = anchors or generate_evidence_anchors(
        block_id=context.block_id, source_document_id=context.source_document_id,
        block_text=context.block_text, section=context.section,
    )
    counts = Counter(); unique_ids: set[str] = set(); errors = []; warnings = []
    for path, evidence in iter_draft_evidence_references(draft):
        resolved: list[EvidenceAnchor] = []
        for anchor_id in evidence.evidence_anchor_ids:
            counts["anchor_reference_count"] += 1; unique_ids.add(anchor_id)
            if not str(anchor_id).startswith(f"{context.block_id}:"):
                counts["anchor_id_cross_block_count"] += 1
                counts["formal_evidence_binding_failure_count"] += 1
                errors.append({"path": path, "anchor_id": anchor_id, "reason": "evidence_anchor_cross_block"})
                continue
            try:
                anchor = resolve_anchor(
                    anchor_id, anchors, expected_block_id=context.block_id,
                    source_text=context.block_text, expected_source_document_id=context.source_document_id,
                )
            except ValueError as exc:
                reason = str(exc)
                key = ("anchor_id_missing_count" if "not_found" in reason else
                       "anchor_registry_integrity_failure_count")
                counts[key] += 1; counts["formal_evidence_binding_failure_count"] += 1
                errors.append({"path": path, "anchor_id": anchor_id, "reason": reason})
                continue
            if evidence.span_type == "observation" and anchor.source_role == "methods":
                counts["anchor_role_violation_count"] += 1
                counts["formal_evidence_binding_failure_count"] += 1
                errors.append({"path": path, "anchor_id": anchor_id,
                               "reason": "results_observation_cannot_bind_methods_only_anchor"})
                continue
            resolved.append(anchor)
            counts["anchor_id_valid_reference_count"] += 1
            counts["formal_evidence_binding_success_count"] += 1
        excerpt = evidence.model_selected_excerpt_raw
        if excerpt is None:
            counts["anchor_excerpt_missing_count"] += 1
        elif resolved and " ".join(item.text for item in resolved) == excerpt:
            counts["anchor_excerpt_match_count"] += 1
        elif resolved:
            counts["anchor_excerpt_mismatch_count"] += 1
            warnings.append({"path": path, "reason": "anchor_excerpt_mismatch_warning"})
    metric_keys = (
        "anchor_reference_count", "anchor_id_valid_reference_count", "anchor_id_missing_count",
        "anchor_id_cross_block_count", "anchor_registry_integrity_failure_count",
        "anchor_role_violation_count", "anchor_excerpt_match_count",
        "anchor_excerpt_mismatch_count", "anchor_excerpt_missing_count",
        "formal_evidence_binding_success_count", "formal_evidence_binding_failure_count",
    )
    return {**{key: counts[key] for key in metric_keys}, "unique_anchor_id_count": len(unique_ids),
            "valid": not errors, "errors": errors, "warnings": warnings}


def _observation_id(draft: ExperimentalObservationDraft, context: TrustedDraftContextV3,
                    evidence_ids: list[str]) -> str:
    payload = {
        "version": OBSERVATION_ID_VERSION, "source_document_id": context.source_document_id,
        "parent_block_id": context.parent_block_id, "child_block_id": context.child_block_id or context.block_id,
        "experiment": draft.experiment.model_dump(mode="json"),
        "interventions": [x.model_dump(mode="json", exclude={"evidence"}) for x in draft.interventions],
        "combination_mode_raw": draft.combination_mode_raw,
        "measurement": draft.measurement.model_dump(mode="json", exclude={"evidence"}),
        "comparison": draft.observation.comparison_raw, "observed_result": draft.observation.observed_result,
        "evidence_span_ids": evidence_ids,
    }
    return f"ftl1v3_{_hash(payload)[:24]}"


def hydrate_draft_observation_v3(draft: ExperimentalObservationDraft, context: TrustedDraftContextV3,
                                 *, observation_index: int = 0) -> tuple[dict[str, Any], dict[str, Any]]:
    anchors = generate_evidence_anchors(block_id=context.block_id, source_document_id=context.source_document_id,
                                        block_text=context.block_text, section=context.section)
    anchor_audit = audit_draft_anchor_bindings(draft, context, anchors)
    if not anchor_audit["valid"]:
        first = anchor_audit["errors"][0]
        raise DraftHydrationV3Error("evidence_unresolved", str(first["reason"]))
    evidence_items = [*draft.evidence_references, draft.observation.evidence,
                      draft.measurement.evidence, draft.interpretation_evidence,
                      *(x.evidence for x in draft.interventions)]
    spans: list[FormalEvidenceSpanV3] = []; evidence_modes: list[str] = []
    purpose_ids: dict[int, list[str]] = {}
    for item in evidence_items:
        if item is None: continue
        resolved, mode = resolve_draft_evidence(item, context, anchors)
        evidence_modes.append(mode)
        purpose_ids[id(item)] = [x.evidence_span_id for x in resolved]
        for span in resolved:
            if span.evidence_span_id not in {x.evidence_span_id for x in spans}: spans.append(span)
    observation_ids = purpose_ids.get(id(draft.observation.evidence), [])
    if not observation_ids:
        raise DraftHydrationV3Error("evidence_unresolved", "observation_evidence_missing")
    design = normalize_semantics("design_type", draft.experiment.design_type_raw, domain_profile=context.domain_profile)
    measurement = normalize_semantics("measurement_dimension", draft.measurement.measurement_dimension_raw, domain_profile=context.domain_profile)
    direction = normalize_semantics("lexical_direction", draft.candidate_relation.lexical_direction_raw, domain_profile=context.domain_profile)
    combination = normalize_semantics("combination_mode", draft.combination_mode_raw, domain_profile=context.domain_profile)
    combination_status = "resolved" if len(draft.interventions) <= 1 else combination.status
    combination_reasons = () if len(draft.interventions) <= 1 else combination.review_reasons
    interventions: list[FormalIntervention] = []
    combination_audit = {**combination.__dict__, "status": combination_status,
                         "review_reasons": combination_reasons,
                         "effective_single_intervention_not_applicable": len(draft.interventions) <= 1}
    normalization_audit = [design.__dict__, measurement.__dict__, direction.__dict__, combination_audit]
    for index, item in enumerate(draft.interventions):
        category = normalize_semantics("intervention_type", item.intervention_type_raw, domain_profile=context.domain_profile)
        role = normalize_semantics("intervention_role", item.role_raw, domain_profile=context.domain_profile)
        normalization_audit.extend([category.__dict__, role.__dict__])
        status = category.status if role.status == "resolved" else role.status
        reasons = [*category.review_reasons, *role.review_reasons]
        interventions.append(FormalIntervention(
            intervention_id=f"int_{_hash({'block': context.block_id, 'observation': observation_index, 'index': index, 'raw': item.model_dump(mode='json')})[:20]}",
            role=role.normalized_value, intervention_type=category.normalized_value,
            intervention_type_raw=item.intervention_type_raw,
            target_mention=item.intervention_target_mention, agent_mention=item.agent_or_drug_mention,
            method_raw=item.intervention_method_raw, dose_raw=item.dose_raw,
            duration_raw=item.duration_raw, route_raw=item.route_raw, condition_raw=item.condition_raw,
            evidence_span_ids=purpose_ids.get(id(item.evidence), []) if item.evidence else [],
            normalization_status=status, normalization_rule_id=f"{REGISTRY_VERSION}:{category.rule_id}",
            review_reasons=reasons,
        ))
    experiment_id = f"exp_{_hash({'block': context.block_id, 'raw': draft.experiment.experiment_label_raw})[:20]}"
    family_id = f"ef_{_hash({'block': context.block_id, 'raw': draft.experiment.evidence_family_label_raw})[:20]}"
    observation_id = _observation_id(draft, context, observation_ids)
    eligibility = calculate_eligibility(
        interventions=interventions, design_status=design.status, measurement_status=measurement.status,
        direction=direction.normalized_value, direction_status=direction.status,
        combination_mode=combination.normalized_value, combination_status=combination_status,
        comparison_raw=draft.observation.comparison_raw or draft.experiment.comparison_arm_raw,
        evidence_exact=bool(spans),
    )
    review_reasons = sorted({reason for norm in (design, measurement, direction) for reason in norm.review_reasons}
                            | set(combination_reasons)
                            | {reason for item in interventions for reason in item.review_reasons}
                            | set(eligibility.exclusion_reasons))
    normalization_status = ("ambiguous" if any(x.status == "ambiguous" for x in (design, measurement, direction, combination))
                            else "reviewable_unknown" if review_reasons else "resolved")
    formal = ExperimentalObservationV3(
        observation_id=observation_id,
        provenance=DocumentProvenanceV3(
            paper_id=context.paper_id, pmid=context.pmid, pmcid=context.pmcid,
            source_document_id=context.source_document_id, fulltext_source_hash=context.fulltext_source_hash,
            section=context.section, subsection=context.subsection, parent_block_id=context.parent_block_id,
            child_block_id=context.child_block_id or context.block_id, evidence_spans=spans,
        ),
        evidence_span_ids=[x.evidence_span_id for x in spans],
        normalization_status=normalization_status,
        normalization_rule_id=f"{REGISTRY_VERSION}:aggregate_v1",
        experiment=ExperimentContextV3(
            experiment_id=experiment_id, evidence_family_id=family_id,
            experiment_label_raw=draft.experiment.experiment_label_raw,
            evidence_family_label_raw=draft.experiment.evidence_family_label_raw,
            experimental_design_raw=draft.experiment.experimental_design_raw,
            design_type=design.normalized_value, design_type_raw=draft.experiment.design_type_raw,
            design_normalization_status=design.status,
            design_normalization_rule_id=f"{REGISTRY_VERSION}:{design.rule_id}",
            design_review_reasons=list(design.review_reasons), species_raw=draft.experiment.species_raw,
            model_system_raw=draft.experiment.model_system_raw,
            experimental_unit_raw=draft.experiment.cell_line_or_type_raw,
            tissue_raw=draft.experiment.tissue_raw, disease_model_raw=draft.experiment.disease_model_raw,
            genotype_raw=draft.experiment.genotype_raw, cohort_raw=draft.experiment.cohort_raw,
            sample_raw=draft.experiment.sample_raw, comparison_arm_raw=draft.experiment.comparison_arm_raw,
            control_arm_raw=draft.experiment.control_arm_raw,
        ),
        interventions=interventions, combination_mode=combination.normalized_value,
        combination_mode_raw=draft.combination_mode_raw,
        combination_normalization_status=combination_status,
        combination_normalization_rule_id=f"{REGISTRY_VERSION}:{combination.rule_id}",
        combination_review_reasons=list(combination_reasons),
        measurement=MeasurementDetailV3(
            measurement_dimension=measurement.normalized_value,
            measurement_dimension_raw=draft.measurement.measurement_dimension_raw,
            measured_entity_mention=draft.measurement.measured_entity_mention,
            outcome_mention=draft.measurement.outcome_mention,
            assay_or_readout_raw=draft.measurement.assay_or_readout_raw,
            endpoint_raw=draft.measurement.endpoint_raw,
            evidence_span_ids=purpose_ids.get(id(draft.measurement.evidence), []) if draft.measurement.evidence else [],
            normalization_status=measurement.status,
            normalization_rule_id=f"{REGISTRY_VERSION}:{measurement.rule_id}",
            review_reasons=list(measurement.review_reasons),
        ),
        observation=ObservationDetailV3(
            observed_result=draft.observation.observed_result,
            quantitative_result_raw=draft.observation.quantitative_result_raw,
            statistical_support_raw=draft.observation.statistical_support_raw,
            uncertainty_raw=draft.observation.uncertainty_raw,
            comparison_raw=draft.observation.comparison_raw, negation=draft.observation.negation,
            evidence_span_ids=observation_ids,
        ),
        interpretation_raw=draft.interpretation_raw,
        interpretation_evidence_span_ids=purpose_ids.get(id(draft.interpretation_evidence), []) if draft.interpretation_evidence else [],
        candidate_relation=CandidateRelationV3(
            subject_mention=draft.candidate_relation.subject_mention,
            object_mention=draft.candidate_relation.object_mention,
            relation_raw=draft.candidate_relation.relation_wording_raw,
            lexical_direction=direction.normalized_value,
            lexical_direction_raw=draft.candidate_relation.lexical_direction_raw,
            normalization_status=direction.status,
            normalization_rule_id=f"{REGISTRY_VERSION}:{direction.rule_id}",
            review_reasons=list(direction.review_reasons),
            evidence_design_raw=draft.candidate_relation.evidence_design_raw,
        ),
        statement_role=draft.statement_role, eligibility=eligibility,
        extraction_warnings=draft.extraction_warnings_raw, review_reasons=review_reasons,
    )
    audit = {
        "status": "formal_valid", "observation_id": observation_id,
        "hydrator_version": HYDRATOR_VERSION, "registry_version": REGISTRY_VERSION,
        "evidence_anchor_version": EVIDENCE_ANCHOR_VERSION,
        "eligibility_policy_version": ELIGIBILITY_POLICY_VERSION,
        "block_id": context.block_id, "observation_index": observation_index,
        "evidence_binding_modes": evidence_modes,
        "evidence_anchor_resolved_count": sum(mode == "authoritative_anchor" for mode in evidence_modes),
        "evidence_text_exact_count": 0,
        "normalization_audit": normalization_audit,
        "formal_status": "resolved" if not review_reasons and direction.status == "resolved" else "reviewable",
        "eligibility": eligibility.model_dump(mode="json"),
        "anchor_binding_audit": anchor_audit,
    }
    return formal.model_dump(mode="json"), audit


def hydrate_draft_response_v3(response: FulltextL1DraftResponse, context: TrustedDraftContextV3) -> HydrationBatchV3:
    rows: list[dict[str, Any]] = []; audit: list[dict[str, Any]] = []; rejected: list[dict[str, Any]] = []
    for index, draft in enumerate(response.experimental_observations):
        try:
            row, item = hydrate_draft_observation_v3(draft, context, observation_index=index)
            rows.append(row); audit.append(item)
        except (DraftHydrationV3Error, ValueError) as exc:
            rejected.append({"block_id": context.block_id, "observation_index": index,
                             "status": getattr(exc, "reason", "evidence_unresolved"), "reason": str(exc),
                             "draft": draft.model_dump(mode="json"), "hydrator_version": HYDRATOR_VERSION})
        except ValidationError as exc:
            rejected.append({"block_id": context.block_id, "observation_index": index,
                             "status": "formal_schema_failed", "reason": str(exc),
                             "draft": draft.model_dump(mode="json"), "hydrator_version": HYDRATOR_VERSION})
    response_v3 = FulltextL1V3Response(schema_version="fulltext_l1_experimental_observation_schema_v3",
                                       experimental_observations=rows)
    return HydrationBatchV3(response_v3.model_dump(mode="json"), audit, rejected)


__all__ = ["HYDRATOR_VERSION", "COMPLETENESS_POLICY_VERSION", "OBSERVATION_ID_VERSION",
           "DraftHydrationV3Error", "TrustedDraftContextV3", "HydrationBatchV3",
           "resolve_draft_evidence", "iter_draft_evidence_references", "audit_draft_anchor_bindings",
           "hydrate_draft_observation_v3", "hydrate_draft_response_v3"]
