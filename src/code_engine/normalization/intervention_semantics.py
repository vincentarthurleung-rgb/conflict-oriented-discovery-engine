"""Deterministic intervention-aware evidence semantics.

This module separates lexical outcome polarity from inferred natural-state
causal direction.  It is intentionally rule based and provenance preserving:
L1 relation fields are read as inputs, not rewritten.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


STRICT_CAUSAL_CORE = "strict_causal_core"
CAUSAL_REVIEWABLE = "causal_reviewable"
INTERVENTION_OBSERVATION = "intervention_observation"
RESCUE_SUPPORTED = "rescue_supported"
ASSOCIATION = "association"
DIFFERENTIAL_EXPRESSION = "differential_expression"
CONTEXT_ONLY = "context_only"
AUDIT_REJECTED = "audit_rejected"

LOSS_OF_FUNCTION_TYPES = {"knockdown", "knockout", "silencing", "ablation", "depletion"}
GAIN_OF_FUNCTION_TYPES = {"overexpression", "activation"}
STRICT_ELIGIBLE_DESIGNS = {"direct_intervention", "loss_of_function", "gain_of_function"}
CAUSAL_FAMILIES = {
    "activation",
    "activates",
    "increases",
    "increase",
    "positive_regulation",
    "phenotype_regulation",
    "causal_mediation",
    "inhibition",
    "inhibits",
    "decreases",
    "decrease",
    "negative_regulation",
    "regulation",
}
NON_CAUSAL_RELATIONS = {
    "association_only",
    "association",
    "associated_with",
    "higher_expression_in",
    "lower_expression_in",
    "differentially_expressed_in",
}
SAMPLE_TERMS = (
    "biopsy",
    "biopsies",
    "sample",
    "samples",
    "control",
    "controls",
    "tumor tissues",
    "tumour tissues",
)
CONDITION_TERMS = (
    "silenced",
    "knockdown",
    "knockout",
    "treated",
    "transfected",
    "overexpressed",
    "depleted",
    "ablated",
)


@dataclass
class EvidenceSemantics:
    evidence_design: str = "unknown"
    lexical_relation: str = ""
    lexical_direction: str = "unknown"
    observed_outcome_sign: int = 0
    intervention_target: str | None = None
    intervention_type: str = "unknown"
    intervention_sign: int | None = None
    secondary_intervention: dict[str, Any] | None = None
    comparison_arm: str | None = None
    derived_causal_sign: int | None = None
    causal_direction_provenance: str = "unresolved"
    causal_direction_eligible: bool = False
    inference_type: str = "unknown"
    sample_context: str | None = None
    species_context: str | None = None
    measured_entity: str | None = None
    measurement_dimension: str | None = None
    semantic_warnings: list[str] = field(default_factory=list)
    semantic_hard_exclusions: list[str] = field(default_factory=list)
    retained_layer: str = CAUSAL_REVIEWABLE
    retention_reason: str = "semantics_review_required"
    available_for_review: bool = True
    available_for_display: bool = True
    conflict_eligible: bool = False
    hypothesis_eligible: bool = False
    direction_provenance_consistent: bool = False
    relation_semantics_eligible: bool = False
    evidence_design_eligible: bool = False
    endpoint_semantics_eligible: bool = True
    measurement_projection_valid: bool = True
    granularity_projection_valid: bool = True
    species_projection_valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(*values: Any) -> str:
    return " ".join(str(value or "") for value in values if value not in (None, "")).strip()


def _fold(value: Any) -> str:
    return str(value or "").casefold()


def _sign_from_direction(value: Any) -> int:
    text = _fold(value).replace("_", " ")
    if text in {"positive", "increase", "increases", "increased", "activate", "activates", "activated", "promote", "promotes", "improve", "enhance"}:
        return 1
    if text in {"negative", "decrease", "decreases", "decreased", "inhibit", "inhibits", "inhibited", "suppress", "suppresses", "reduce", "reduces", "worsen"}:
        return -1
    if any(term in text for term in ("increase", "activat", "promot", "enhanc", "upregulat", "higher")):
        return 1
    if any(term in text for term in ("decrease", "reduc", "inhibit", "suppress", "downregulat", "lower")):
        return -1
    return 0


def _legacy_sign(value: Any) -> int:
    if value in (1, "+1", "1", "positive"):
        return 1
    if value in (-1, "-1", "negative"):
        return -1
    return 0


def _direction_from_sign(sign: int | None) -> str:
    if sign == 1:
        return "positive"
    if sign == -1:
        return "negative"
    return "unknown"


def _clean_target(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" .,:;()[]")
    return cleaned or None


def _targets_match(target: str | None, subject: str | None) -> bool:
    if not target or not subject:
        return False
    left = re.sub(r"[^a-z0-9]+", "", target.casefold())
    right = re.sub(r"[^a-z0-9]+", "", subject.casefold())
    return bool(left and (left == right or left in right or right in left))


def _condition_subject(raw: str) -> tuple[str | None, str | None, str | None]:
    patterns = (
        (r"\b(?P<target>[A-Za-z0-9-]+)\s*-\s*silenced\s+(?P<context>.+?cells?)\b", "silencing"),
        (r"\b(?P<target>[A-Za-z0-9-]+)\s+silenced\s+(?P<context>.+?cells?)\b", "silencing"),
        (r"\b(?P<target>[A-Za-z0-9-]+)\s+knockdown\s+(?P<context>.+?cells?)\b", "knockdown"),
        (r"\boverexpressed\s+(?P<target>[A-Za-z0-9-]+)\b", "overexpression"),
    )
    for pattern, intervention_type in patterns:
        match = re.search(pattern, raw, re.I)
        if match:
            return _clean_target(match.group("target")), intervention_type, _clean_target(match.groupdict().get("context"))
    return None, None, None


def _sentence_intervention(sentence: str) -> tuple[str | None, str | None]:
    patterns = (
        (r"RNAi-mediated\s+ablation\s+of\s+(?P<target>[A-Za-z0-9-]+)", "ablation"),
        (r"\bablation\s+of\s+(?P<target>[A-Za-z0-9-]+)", "ablation"),
        (r"\bknockdown\s+of\s+(?P<target>[A-Za-z0-9-]+)", "knockdown"),
        (r"\bknockout\s+of\s+(?P<target>[A-Za-z0-9-]+)", "knockout"),
        (r"\bsilencing\s+of\s+(?P<target>[A-Za-z0-9-]+)", "silencing"),
        (r"\bdepletion\s+of\s+(?P<target>[A-Za-z0-9-]+)", "depletion"),
        (r"\boverexpression\s+of\s+(?P<target>[A-Za-z0-9-]+)", "overexpression"),
        (r"\boverexpressed\s+(?P<target>[A-Za-z0-9-]+)", "overexpression"),
        (r"\bactivation\s+of\s+(?P<target>[A-Za-z0-9-]+)", "activation"),
    )
    for pattern, intervention_type in patterns:
        match = re.search(pattern, sentence, re.I)
        if match:
            return _clean_target(match.group("target")), intervention_type
    return None, None


def _intervention_sign(intervention_type: str | None) -> int | None:
    if intervention_type in LOSS_OF_FUNCTION_TYPES:
        return -1
    if intervention_type in GAIN_OF_FUNCTION_TYPES:
        return 1
    return None


def _sample_context(raw: str, sentence: str) -> str | None:
    subject_target, subject_type, context = _condition_subject(raw)
    if subject_target and subject_type and context:
        return context
    for pattern in (
        r"\bin\s+([^.;,]*?(?:biopsies|biopsy|samples|controls|tumou?r tissues))\b",
        r"\bcompared\s+to\s+([^.;,]*?controls)\b",
    ):
        match = re.search(pattern, sentence, re.I)
        if match:
            return _clean_target(match.group(1))
    return None


def _is_sample_endpoint(raw: str, entity_type: Any = None) -> bool:
    text = _fold(raw)
    etype = _fold(entity_type)
    return any(term in text for term in SAMPLE_TERMS) or etype in {"sample", "disease_sample", "experimental_context", "model_system"}


def _is_intervention_condition_endpoint(raw: str) -> bool:
    text = _fold(raw)
    return " cells" in text and any(term in text for term in CONDITION_TERMS)


def _measurement_from_endpoint(endpoint: dict[str, Any], raw: str) -> tuple[str | None, str | None]:
    dimension = endpoint.get("measurement_dimension")
    measured = endpoint.get("measured_entity_canonical_name") or endpoint.get("measured_entity_cleaned") or endpoint.get("measured_entity_raw")
    if dimension:
        return str(measured) if measured else None, str(dimension)
    match = re.match(r"^\s*p[-\s]?(.+?)\s*$", str(raw or ""), re.I)
    if match:
        return _clean_target(match.group(1)), "phosphorylation"
    return None, None


def _is_differential_expression(observation: dict[str, Any], sentence: str) -> bool:
    relation = _fold(_text(observation.get("relation_family"), observation.get("relation_raw")))
    if "association_only" in relation:
        return False
    return bool(
        re.search(r"\b(increased|decreased|higher|lower)\s+expression\s+of\b", sentence, re.I)
        and re.search(r"\b(in|detected in|compared to|compared with)\b", sentence, re.I)
    )


def _rescue_semantics(observation: dict[str, Any], sem: EvidenceSemantics, sentence: str) -> bool:
    if not re.search(r"\b(rescue|restore|restored|reverse|reversed|attenuate|attenuated)\b", sentence, re.I):
        return False
    rescue_target, rescue_type = _sentence_intervention(sentence)
    if not rescue_target:
        rescue_target, rescue_type, _ = _condition_subject(str(observation.get("subject_raw") or ""))
    primary = None
    primary_match = re.search(r"\b(?P<target>[A-Za-z0-9-]+)\s+mimic\b", sentence, re.I)
    if primary_match:
        primary = {"target": _clean_target(primary_match.group("target")), "type": "mimic", "observed_effect_sign": sem.observed_outcome_sign or -1}
    sem.evidence_design = "rescue"
    sem.inference_type = "rescue_inferred"
    sem.intervention_target = rescue_target
    sem.intervention_type = rescue_type or "unknown"
    sem.intervention_sign = _intervention_sign(sem.intervention_type)
    sem.secondary_intervention = primary
    if primary and rescue_target and rescue_type and sem.observed_outcome_sign:
        sem.derived_causal_sign = 1 if re.search(r"\brestore|restored|rescue|rescued|reverse|reversed\b", sentence, re.I) else None
        sem.causal_direction_provenance = "rescue_restoration_inference" if sem.derived_causal_sign else "rescue_semantics_unresolved"
        sem.causal_direction_eligible = sem.derived_causal_sign is not None
    else:
        sem.semantic_hard_exclusions.append("rescue_semantics_unresolved")
        sem.causal_direction_provenance = "rescue_semantics_unresolved"
    sem.evidence_design_eligible = False
    sem.retained_layer = RESCUE_SUPPORTED
    sem.retention_reason = "rescue_evidence_retained_for_review"
    return True


def interpret_evidence_semantics(observation: dict[str, Any]) -> EvidenceSemantics:
    sentence = _text(observation.get("evidence_sentence"), observation.get("evidence_text"))
    relation_text = _text(observation.get("relation_raw"), observation.get("relation_family"))
    subject_raw = _text(observation.get("subject_raw"), observation.get("subject_raw_name"))
    object_raw = _text(observation.get("object_raw"), observation.get("object_raw_name"))
    context = observation.get("context") if isinstance(observation.get("context"), dict) else {}
    sem = EvidenceSemantics(
        lexical_relation=relation_text,
        lexical_direction=str(observation.get("direction") or "unknown"),
        observed_outcome_sign=_sign_from_direction(observation.get("direction")) or _sign_from_direction(relation_text),
        species_context=str(context.get("species") or "") or None,
    )
    direct_sign = _legacy_sign(observation.get("direct_relation_sign"))
    relation_family = _fold(observation.get("relation_family"))
    relation_raw_key = _fold(observation.get("relation_raw")).replace(" ", "_")
    subject_entity_type = observation.get("subject_entity_type") or observation.get("subject_type")
    object_entity_type = observation.get("object_entity_type") or observation.get("object_type")

    measured, dimension = _measurement_from_endpoint(observation.get("object_endpoint") or {}, object_raw)
    if not dimension:
        measured, dimension = _measurement_from_endpoint(observation.get("subject_endpoint") or {}, subject_raw)
    sem.measured_entity = measured
    sem.measurement_dimension = dimension

    if _is_intervention_condition_endpoint(subject_raw):
        target, intervention_type, sample = _condition_subject(subject_raw)
        sem.intervention_target = target
        sem.intervention_type = intervention_type or "unknown"
        sem.intervention_sign = _intervention_sign(sem.intervention_type)
        sem.sample_context = sample
        sem.semantic_hard_exclusions.append("intervention_condition_endpoint")
    if _is_sample_endpoint(subject_raw, subject_entity_type) or _is_sample_endpoint(object_raw, object_entity_type):
        sem.sample_context = sem.sample_context or _sample_context(_text(subject_raw, object_raw), sentence)
        sem.semantic_hard_exclusions.append("sample_context_endpoint")
    if str(observation.get("subject_canonical_id") or "").startswith("RUN:") or str(observation.get("object_canonical_id") or "").startswith("RUN:"):
        sem.semantic_hard_exclusions.append("endpoint_unresolved_fallback")

    if _rescue_semantics(observation, sem, sentence):
        return _finalize_semantics(observation, sem)

    if relation_family in NON_CAUSAL_RELATIONS or relation_raw_key in NON_CAUSAL_RELATIONS:
        sem.evidence_design = "association"
        sem.inference_type = "association_only"
        sem.retained_layer = ASSOCIATION
        sem.retention_reason = "association_evidence_retained_non_causal"
        sem.semantic_hard_exclusions.append("non_causal_evidence_design")
        return _finalize_semantics(observation, sem)

    if _is_differential_expression(observation, sentence):
        sem.evidence_design = "differential_expression"
        sem.inference_type = "association_only"
        sem.retained_layer = DIFFERENTIAL_EXPRESSION
        sem.retention_reason = "differential_expression_retained_non_causal"
        sem.semantic_hard_exclusions.append("non_causal_evidence_design")
        return _finalize_semantics(observation, sem)

    sent_target, sent_type = _sentence_intervention(sentence)
    if sent_target and sent_type:
        sem.intervention_target = sem.intervention_target or sent_target
        sem.intervention_type = sem.intervention_type if sem.intervention_type != "unknown" else sent_type
        sem.intervention_sign = sem.intervention_sign or _intervention_sign(sem.intervention_type)

    if sem.intervention_type in LOSS_OF_FUNCTION_TYPES | GAIN_OF_FUNCTION_TYPES:
        sem.evidence_design = "loss_of_function" if sem.intervention_type in LOSS_OF_FUNCTION_TYPES else "gain_of_function"
        sem.inference_type = f"{sem.evidence_design}_inferred"
        if not _targets_match(sem.intervention_target, subject_raw):
            sem.semantic_hard_exclusions.append("intervention_semantics_unresolved")
            sem.retained_layer = INTERVENTION_OBSERVATION
            sem.retention_reason = "intervention_scope_requires_review"
        elif sem.intervention_sign and sem.observed_outcome_sign:
            sem.derived_causal_sign = sem.intervention_sign * sem.observed_outcome_sign
            sem.causal_direction_provenance = (
                "loss_of_function_sign_inversion"
                if sem.evidence_design == "loss_of_function"
                else "gain_of_function_direct"
            )
            sem.causal_direction_eligible = True
            sem.evidence_design_eligible = True
            sem.retained_layer = CAUSAL_REVIEWABLE if sem.semantic_hard_exclusions else STRICT_CAUSAL_CORE
            sem.retention_reason = "intervention_causal_direction_derived"
        else:
            sem.semantic_hard_exclusions.append("intervention_semantics_unresolved")
            sem.retained_layer = INTERVENTION_OBSERVATION
            sem.retention_reason = "intervention_outcome_direction_unresolved"
        return _finalize_semantics(observation, sem)

    if (relation_family in CAUSAL_FAMILIES or relation_raw_key in CAUSAL_FAMILIES) and (direct_sign or sem.observed_outcome_sign):
        sem.evidence_design = "direct_intervention"
        sem.inference_type = "direct"
        sem.derived_causal_sign = direct_sign or sem.observed_outcome_sign
        sem.causal_direction_provenance = "direct_relation_sign" if direct_sign else "lexical_direct_causal"
        sem.causal_direction_eligible = True
        sem.evidence_design_eligible = True
        sem.retained_layer = STRICT_CAUSAL_CORE
        sem.retention_reason = "direct_causal_relation_retained"
    else:
        sem.evidence_design = "unknown"
        sem.inference_type = "unknown"
        sem.semantic_hard_exclusions.append("non_causal_evidence_design")
        sem.retained_layer = CAUSAL_REVIEWABLE
        sem.retention_reason = "relation_semantics_requires_review"

    return _finalize_semantics(observation, sem)


def _finalize_semantics(observation: dict[str, Any], sem: EvidenceSemantics) -> EvidenceSemantics:
    if sem.measurement_dimension is None:
        relation_text = _fold(_text(observation.get("relation_raw"), observation.get("relation_family"), observation.get("formal_relation"), observation.get("core_projection_relation")))
        if "phosphorylation" in relation_text or re.match(r"^\s*p[-\s]?", _text(observation.get("object_raw"), observation.get("object_raw_name")), re.I):
            sem.semantic_hard_exclusions.append("measurement_projection_missing")
            sem.measurement_projection_valid = False
    if sem.measurement_dimension == "phosphorylation":
        object_endpoint = observation.get("object_endpoint") or {}
        canonical = _text(
            observation.get("object_canonical_name"),
            observation.get("object_canonical_id"),
            object_endpoint.get("measured_entity_canonical_name"),
            object_endpoint.get("measured_entity_canonical_id"),
        )
        raw = _text(observation.get("object_raw"), observation.get("object_raw_name"))
        if re.match(r"^\s*p[-\s]?akt\s*$", raw, re.I) and re.search(r"AKT[123]_|AKT[123]\b|MOUSE", canonical):
            sem.semantic_hard_exclusions.append("unsupported_isoform_projection")
            sem.granularity_projection_valid = False
        if "MOUSE" in canonical and not sem.species_context:
            sem.semantic_hard_exclusions.append("species_projection_unverified")
            sem.species_projection_valid = False
    if sem.evidence_design == "association" and _fold(observation.get("formal_relation")) in {"increases", "decreases"}:
        sem.semantic_hard_exclusions.append("association_projected_as_regulation")

    sem.semantic_hard_exclusions = list(dict.fromkeys(sem.semantic_hard_exclusions))
    sem.semantic_warnings = list(dict.fromkeys(sem.semantic_warnings))
    sem.endpoint_semantics_eligible = not any(
        reason in sem.semantic_hard_exclusions
        for reason in ("endpoint_unresolved_fallback", "intervention_condition_endpoint", "sample_context_endpoint")
    )
    sem.relation_semantics_eligible = sem.evidence_design in STRICT_ELIGIBLE_DESIGNS and sem.derived_causal_sign in {-1, 1}
    sem.direction_provenance_consistent = "direction_provenance_inconsistent" not in sem.semantic_hard_exclusions and sem.causal_direction_eligible
    strict_ok = (
        sem.retained_layer == STRICT_CAUSAL_CORE
        and sem.endpoint_semantics_eligible
        and sem.relation_semantics_eligible
        and sem.causal_direction_eligible
        and sem.direction_provenance_consistent
        and sem.evidence_design_eligible
        and sem.species_projection_valid
        and sem.granularity_projection_valid
        and sem.measurement_projection_valid
        and not sem.semantic_hard_exclusions
    )
    if strict_ok:
        sem.conflict_eligible = True
        sem.hypothesis_eligible = True
        sem.retention_reason = "strict_core_semantics_passed"
    else:
        sem.conflict_eligible = False
        sem.hypothesis_eligible = False
        if sem.retained_layer == STRICT_CAUSAL_CORE:
            sem.retained_layer = CAUSAL_REVIEWABLE if sem.relation_semantics_eligible else INTERVENTION_OBSERVATION
            sem.retention_reason = sem.semantic_hard_exclusions[0] if sem.semantic_hard_exclusions else "strict_core_semantics_incomplete"
    return sem


def apply_evidence_semantics(observation: dict[str, Any]) -> dict[str, Any]:
    value = dict(observation)
    sem = interpret_evidence_semantics(value)
    payload = sem.to_dict()
    value["evidence_semantics"] = payload
    value["scientific_semantics_decision"] = payload
    value["scientific_edge_layer"] = sem.retained_layer
    value["retained_layer"] = sem.retained_layer
    value["core_exclusion_reasons"] = list(sem.semantic_hard_exclusions)
    value["retention_reason"] = value.get("retention_reason") or sem.retention_reason
    value["available_for_review"] = sem.available_for_review
    value["available_for_display"] = sem.available_for_display
    value["conflict_eligible"] = bool(value.get("conflict_eligible") and sem.conflict_eligible)
    value["hypothesis_eligible"] = bool(sem.hypothesis_eligible)
    value["observed_outcome_sign"] = sem.observed_outcome_sign
    value["derived_causal_sign"] = sem.derived_causal_sign
    value["causal_direction_provenance"] = sem.causal_direction_provenance
    value["causal_direction_eligible"] = sem.causal_direction_eligible
    value["causal_direction"] = _direction_from_sign(sem.derived_causal_sign)
    value["evidence_design"] = sem.evidence_design
    value["inference_type"] = sem.inference_type
    if sem.measurement_dimension:
        value["measurement_dimension"] = sem.measurement_dimension
    if sem.measured_entity:
        value["measured_entity"] = sem.measured_entity
    if sem.intervention_target:
        value["intervention_target"] = sem.intervention_target
    if sem.intervention_type != "unknown":
        value["intervention_type"] = sem.intervention_type
    if sem.sample_context:
        value["sample_context"] = sem.sample_context
    return value


def relation_from_semantic_sign(sign: int | None) -> str | None:
    if sign == 1:
        return "increases"
    if sign == -1:
        return "decreases"
    return None


__all__ = [
    "ASSOCIATION",
    "AUDIT_REJECTED",
    "CAUSAL_REVIEWABLE",
    "CONTEXT_ONLY",
    "DIFFERENTIAL_EXPRESSION",
    "INTERVENTION_OBSERVATION",
    "RESCUE_SUPPORTED",
    "STRICT_CAUSAL_CORE",
    "EvidenceSemantics",
    "apply_evidence_semantics",
    "interpret_evidence_semantics",
    "relation_from_semantic_sign",
]
