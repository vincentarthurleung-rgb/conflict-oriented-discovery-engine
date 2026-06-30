"""Deterministic biomedical relation-family and direction normalization."""

from __future__ import annotations

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


class DirectionalRelation(CODEBaseModel):
    relation_raw: str
    relation_family: str = "unknown"
    polarity_type: str = "unknown"
    direction: str = "unknown"
    confidence: float = 0.0
    direction_terms: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


TERM_GROUPS = (
    ("no_effect", ("no significant effect", "no effect", "unchanged", "not alter", "did not alter", "无显著影响", "无明显影响", "未改变")),
    ("mixed", ("mixed", "inconsistent", "conflicting", "不一致", "混合")),
    ("decrease", ("downregulate", "down-regulate", "decrease", "reduce", "lower", "下调", "减少", "降低")),
    ("increase", ("upregulate", "up-regulate", "increase", "elevate", "上调", "增加", "升高")),
    ("inhibit", ("inhibit", "suppress", "block", "attenuate", "antagonist", "抑制", "阻断", "拮抗")),
    ("activate", ("activate", "enhance", "promote", "stimulate", "agonist", "激活", "促进", "增强", "激动")),
    ("improve", ("improve", "rescue", "reverse", "ameliorate", "改善", "缓解", "逆转")),
    ("worsen", ("worsen", "exacerbate", "induce", "cause", "恶化", "加重", "诱导", "导致")),
    ("bind", ("bind", "binding", "affinity", "结合")),
    ("associated", ("associate", "correlate", "interaction", "相关", "关联", "相互作用")),
)

EXPRESSION_TERMS = ("expression", "expressed", "upregulat", "downregulat", "表达", "上调", "下调")
PATHWAY_TERMS = ("pathway", "signaling", "signal transduction", "通路", "信号")
PHENOTYPE_TERMS = ("behavior", "behaviour", "phenotype", "symptom", "depression", "response", "行为", "表型", "症状", "抑郁")
CLINICAL_TERMS = ("clinical", "patient", "remission", "efficacy", "trial", "临床", "患者", "缓解率", "疗效")
SAFETY_TERMS = ("adverse", "toxicity", "side effect", "safety", "不良反应", "毒性", "副作用", "安全性")
TARGET_TERMS = ("target", "receptor", "protein", "enzyme", "kinase", "靶点", "受体", "蛋白", "酶")


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def normalize_directional_relation(
    relation_text: str,
    subject_type: str | None = None,
    object_type: str | None = None,
    context_text: str | None = None,
    domain_id: str | None = None,
) -> DirectionalRelation:
    """Normalize relation semantics without inferring therapeutic valence."""

    raw = str(relation_text or "").strip()
    text = " ".join((raw, str(context_text or ""))).casefold()
    matched_direction = "unknown"
    matched_terms: list[str] = []
    for direction, terms in TERM_GROUPS:
        hits = [term for term in terms if term in text]
        if hits:
            matched_direction = direction
            matched_terms = hits
            break

    types = {str(subject_type or "").casefold(), str(object_type or "").casefold()}
    if _contains(text, SAFETY_TERMS):
        family, polarity = "adverse_event", "safety"
    elif _contains(text, CLINICAL_TERMS):
        family, polarity = "clinical_outcome", "clinical"
    elif _contains(text, EXPRESSION_TERMS):
        family, polarity = "gene_expression", "expression"
        if matched_direction == "activate":
            matched_direction = "increase"
        elif matched_direction == "inhibit":
            matched_direction = "decrease"
    elif _contains(text, PATHWAY_TERMS):
        family, polarity = "pathway_activity", "pathway"
    elif _contains(text, PHENOTYPE_TERMS):
        family, polarity = "phenotype_effect", "phenotypic"
    elif matched_direction == "bind" or _contains(text, TARGET_TERMS) or types.intersection({"receptor_complex", "protein", "gene"}):
        family, polarity = "drug_target", "mechanistic"
    elif matched_direction == "associated":
        family = "protein_interaction" if "interaction" in text or types == {"protein"} else "association"
        polarity = "association"
    else:
        family, polarity = "unknown", "unknown"

    warnings = []
    if matched_direction == "unknown":
        warnings.append("direction_unknown_not_for_primary_entropy")
    if matched_direction == "inhibit" and polarity == "mechanistic":
        warnings.append("mechanistic_inhibition_has_no_therapeutic_valence")
    confidence = 0.0 if matched_direction == "unknown" else (0.95 if matched_terms else 0.7)
    return DirectionalRelation(
        relation_raw=raw,
        relation_family=family,
        polarity_type=polarity,
        direction=matched_direction,
        confidence=confidence,
        direction_terms=list(dict.fromkeys(matched_terms)),
        warnings=warnings,
    )


def direction_to_legacy_sign(direction: str) -> int:
    """Compatibility-only sign mapping; it does not encode therapeutic value."""

    if direction in {"activate", "increase", "improve"}:
        return 1
    if direction in {"inhibit", "decrease", "worsen"}:
        return -1
    return 0


__all__ = ["DirectionalRelation", "normalize_directional_relation", "direction_to_legacy_sign"]
