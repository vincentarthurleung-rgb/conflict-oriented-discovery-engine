"""Deterministic bilingual research-intent parsing for natural-language intake."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Literal

from pydantic import Field

from code_engine.common.json_io import write_json
from code_engine.domain.router import default_domain_router
from code_engine.normalization.normalizer import normalize_entity
from code_engine.schemas.models import CODEBaseModel


IntentType = Literal[
    "mechanism_overview", "entity_relation_query", "comparative_mechanism_query",
    "hypothesis_generation", "literature_update", "coverage_check", "unknown",
]

ENTITY_ALIASES = {
    "艾司氯胺酮": "esketamine",
    "氯胺酮": "ketamine",
    "抑郁症": "depression",
    "抗抑郁": "antidepressant response",
    "脑源性神经营养因子": "BDNF",
    "雷帕霉素靶蛋白": "mTOR",
    "nmda receptor": "NMDA receptor",
    "ampa receptor": "AMPA receptor",
    "antidepressant response": "antidepressant response",
    "esketamine": "esketamine",
    "ketamine": "ketamine",
    "depression": "depression",
    "bdnf": "BDNF",
    "mtor": "mTOR",
}
MECHANISM_ENTITIES = {"BDNF", "mTOR", "NMDA receptor", "AMPA receptor"}
DRUG_ENTITIES = {"ketamine", "esketamine"}
DISEASE_ENTITIES = {"depression"}


class ResearchIntent(CODEBaseModel):
    intent_id: str
    raw_user_input: str
    language: str
    intent_type: IntentType
    task_goal: str
    primary_entity: str = ""
    secondary_entities: list[str] = Field(default_factory=list)
    disease_or_condition: str = ""
    mechanism_entities: list[str] = Field(default_factory=list)
    comparison_entities: list[str] = Field(default_factory=list)
    outcome_entities: list[str] = Field(default_factory=list)
    domain_candidates: list[str] = Field(default_factory=list)
    selected_domain: str = "unknown"
    needs_literature_search: bool = True
    needs_hypothesis_generation: bool = False
    needs_mechanism_summary: bool = False
    needs_comparison: bool = False
    needs_coverage_check: bool = True
    time_scope: str = "unspecified"
    evidence_scope: str = "all_available"
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    task_type: str = "unknown"
    primary_entities: list[str] = Field(default_factory=list)
    domain_id: str = "unknown"
    research_goal: str = ""
    needs_l1_extraction: bool = True
    subdomain_id: str | None = None
    domain_profile_id: str = "general_biomedical"
    prompt_profile_id: str = "general_biomedical_l1_v2"
    entity_registry_profile: str = "general_biomedical_registry"
    validator_profile_id: str = "general_validation"
    domain_confidence: float = 0.0
    domain_warnings: list[str] = Field(default_factory=list)


def _extract_entities(raw: str) -> list[str]:
    lowered = raw.casefold()
    hits = []
    for alias, canonical in sorted(ENTITY_ALIASES.items(), key=lambda item: -len(item[0])):
        position = lowered.find(alias.casefold())
        if position >= 0:
            normalize_entity(canonical)  # Preserve the existing normalization audit boundary.
            hits.append((position, canonical))
    return list(dict.fromkeys(canonical for _, canonical in sorted(hits)))


def _select_domain(raw: str):
    profile = default_domain_router().route_text(raw)
    return [profile.domain_id], profile


def parse_research_intent(
    raw_user_input: str,
    *,
    output_root: str | Path = ".",
    write_output: bool = False,
) -> ResearchIntent:
    """Parse research intent using local rules only; unknown input never raises."""

    raw = str(raw_user_input or "").strip()
    lowered = raw.casefold()
    language = "zh" if re.search(r"[\u4e00-\u9fff]", raw) else "en"
    entities = _extract_entities(raw)
    comparison = any(token in lowered for token in ("差异", "比较", "compare", "comparison", "versus", " vs "))
    update = any(token in lowered for token in ("研究到哪", "当前", "现在", "update", "latest", "current"))
    mechanism = any(token in lowered for token in ("机制", "作用", "mechanism", "role", "effect", "解释"))
    hypothesis = any(token in lowered for token in ("假设", "hypothesis", "generate hypothesis"))
    coverage = any(token in lowered for token in ("是否充分", "coverage", "sufficient"))
    directed = "->" in raw or "=>" in raw

    if comparison:
        intent_type: IntentType = "comparative_mechanism_query"
        task_goal = "compare mechanism evidence"
    elif hypothesis:
        intent_type = "hypothesis_generation"
        task_goal = "generate evidence-bounded hypothesis candidates"
    elif update and not mechanism:
        intent_type = "literature_update"
        task_goal = "review current literature coverage"
    elif mechanism or update:
        intent_type = "mechanism_overview"
        task_goal = "understand current role/mechanism"
    elif coverage:
        intent_type = "coverage_check"
        task_goal = "assess current evidence coverage"
    elif directed or len(entities) >= 2:
        intent_type = "entity_relation_query"
        task_goal = "assess entity relation evidence"
    else:
        intent_type = "unknown"
        task_goal = "unresolved"

    primary = next((entity for entity in entities if entity in DRUG_ENTITIES), entities[0] if entities else "")
    disease = next((entity for entity in entities if entity in DISEASE_ENTITIES), "")
    mechanisms = [entity for entity in entities if entity in MECHANISM_ENTITIES]
    comparisons = [entity for entity in entities if entity in DRUG_ENTITIES] if comparison else []
    outcomes = [entity for entity in entities if entity == "antidepressant response"]
    if disease == "depression" and (mechanism or primary in DRUG_ENTITIES) and "antidepressant response" not in outcomes:
        outcomes.append("antidepressant response")
    secondary = [entity for entity in entities if entity not in {primary, disease} and entity not in mechanisms]
    domains, domain_profile = _select_domain(raw)
    selected_domain = domain_profile.domain_id
    warnings = []
    if intent_type == "unknown":
        warnings.append("unable_to_resolve_research_intent")
    if not entities:
        warnings.append("no_supported_biomedical_entity_detected")
    evidence_scope = "molecular_mechanism" if mechanism or mechanisms else "all_available"
    if any(token in lowered for token in ("clinical", "patient", "患者", "临床")):
        evidence_scope = "clinical"
    elif any(token in lowered for token in ("animal", "mouse", "rat", "动物", "小鼠")):
        evidence_scope = "animal_model"
    elif any(token in lowered for token in ("behavior", "behaviour", "行为")):
        evidence_scope = "behavioral_assay"
    intent_id = hashlib.sha256(raw.casefold().encode("utf-8")).hexdigest()[:16]
    intent = ResearchIntent(
        intent_id=intent_id,
        raw_user_input=raw,
        language=language,
        intent_type=intent_type,
        task_goal=task_goal,
        primary_entity=primary,
        secondary_entities=secondary,
        disease_or_condition=disease,
        mechanism_entities=mechanisms,
        comparison_entities=comparisons,
        outcome_entities=outcomes,
        domain_candidates=domains,
        selected_domain=selected_domain,
        needs_literature_search=intent_type != "unknown",
        needs_hypothesis_generation=hypothesis,
        needs_mechanism_summary=intent_type in {"mechanism_overview", "comparative_mechanism_query"},
        needs_comparison=comparison,
        needs_coverage_check=True,
        time_scope="current" if update else "unspecified",
        evidence_scope=evidence_scope,
        confidence=round(min(0.95, 0.35 + 0.15 * len(entities) + (0.2 if intent_type != "unknown" else 0.0)), 2),
        warnings=warnings,
        task_type=intent_type,
        primary_entities=[primary] if primary else [],
        domain_id=selected_domain,
        research_goal=task_goal,
        needs_l1_extraction=intent_type != "unknown",
        subdomain_id=domain_profile.subdomain_id,
        domain_profile_id=domain_profile.profile_id,
        prompt_profile_id=domain_profile.prompt_profile_id,
        entity_registry_profile=domain_profile.entity_registry_profile,
        validator_profile_id=domain_profile.validator_profile_id,
        domain_confidence=0.9 if domain_profile.domain_id != "general_biomedical" else 0.5,
        domain_warnings=list(domain_profile.warnings),
    )
    if write_output:
        write_json(Path(output_root) / f"data/query/intent_{intent.intent_id}.json", intent.model_dump())
    return intent
