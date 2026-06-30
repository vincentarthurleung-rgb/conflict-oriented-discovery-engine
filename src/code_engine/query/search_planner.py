"""Sanitized PubMed/PMC search planning from research intent."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from code_engine.common.json_io import write_json
from code_engine.query.intent import ResearchIntent
from code_engine.query.seed_triples import SeedResearchTriple
from code_engine.domain.models import DomainProfile
from code_engine.domain.router import default_domain_router
from code_engine.schemas.models import CODEBaseModel
from code_engine.encoder.models import SemanticIntakeResult
from code_engine.encoder.semantic_verifier import sanitize_semantic_query


class LiteratureSearchQuery(CODEBaseModel):
    query_id: str
    query_string: str
    source: str = "pubmed"
    purpose: str
    priority: int = 1
    must_include: list[str] = Field(default_factory=list)
    should_include: list[str] = Field(default_factory=list)
    exclude_terms: list[str] = Field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    max_results: int = 50
    expected_domain: str = "general_biomedical"
    from_seed_triples: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    expected_prompt_profile: str = "general_biomedical_l1_v2"
    stage: str = "abstract_retrieval"
    precision_level: str = "medium"
    requires_open_access: bool = False
    requires_fulltext: bool = False
    expansion_sources: list[str] = Field(default_factory=list)
    allowed_for_conflict_source: bool = True
    query: str = ""

    @model_validator(mode="after")
    def align_query_alias(self):
        self.query = self.query or self.query_string
        return self


SearchQuery = LiteratureSearchQuery


class LiteratureSearchPlan(CODEBaseModel):
    intent_id: str
    primary_queries: list[LiteratureSearchQuery] = Field(default_factory=list)
    secondary_queries: list[LiteratureSearchQuery] = Field(default_factory=list)
    mechanism_queries: list[LiteratureSearchQuery] = Field(default_factory=list)
    comparison_queries: list[LiteratureSearchQuery] = Field(default_factory=list)
    clinical_queries: list[LiteratureSearchQuery] = Field(default_factory=list)
    pmc_queries: list[LiteratureSearchQuery] = Field(default_factory=list)
    pubmed_queries: list[LiteratureSearchQuery] = Field(default_factory=list)
    negative_filters: list[str] = Field(default_factory=list)
    max_total_results: int = 100
    dedup_keys: list[str] = Field(default_factory=lambda: ["pmid", "pmcid", "doi", "normalized_title_hash"])
    warnings: list[str] = Field(default_factory=list)
    candidate_papers: list[dict[str, Any]] = Field(default_factory=list)
    exclusion_terms: list[str] = Field(default_factory=list)
    priority: str = "normal"
    domain_id: str = "general_biomedical"
    subdomain_id: str | None = None
    search_profile_id: str = "general_biomedical_search"
    prompt_profile_id: str = "general_biomedical_l1_v2"
    validator_profile_id: str = "general_validation"
    source_domain_profile: dict[str, Any] = Field(default_factory=dict)
    query_generation_mode: str = "deterministic_fallback"
    sanitizer_warnings: list[str] = Field(default_factory=list)
    semantic_confidence: float = 0.0
    manual_review_required: bool = False
    seed_triple: dict[str, Any] = Field(default_factory=dict)
    abstract_retrieval: dict[str, Any] = Field(default_factory=lambda: {
        "sources": ["pubmed"], "source_order": ["pubmed"],
        "open_access_required": False, "fulltext_required": False,
    })
    fulltext_escalation: dict[str, Any] = Field(default_factory=lambda: {
        "sources": ["pmc", "publisher", "oa_resolver"],
        "open_access_required": True, "fulltext_required": True,
        "only_for_selected_conflict_candidates": True,
    })
    query_groups: list[dict[str, Any]] = Field(default_factory=list)


def sanitize_query(query: str) -> tuple[str, list[str]]:
    raw = " ".join(str(query or "").split())
    warnings = []
    if not raw or any(token in raw.casefold() for token in ("http://", "https://", "<script", "drop table")):
        return "", ["unsafe_or_empty_query_removed"]
    cleaned = re.sub(r"[^\w\s()\[\]\"'*,.+:/-]", " ", raw, flags=re.UNICODE)
    cleaned = " ".join(cleaned.split())[:500]
    if cleaned != raw:
        warnings.append("query_sanitized")
    return cleaned, warnings


def _query(text: str, purpose: str, intent: ResearchIntent, *, source: str = "pubmed", seed_ids: list[str] | None = None, priority: int = 1) -> LiteratureSearchQuery | None:
    cleaned, warnings = sanitize_query(text)
    if not cleaned:
        return None
    profile = intent.prompt_profile_id
    return LiteratureSearchQuery(
        query_id=hashlib.sha256(f"{source}|{cleaned}".encode()).hexdigest()[:16],
        query_string=cleaned,
        source=source,
        purpose=purpose,
        priority=priority,
        must_include=[item for item in intent.primary_entities if item],
        exclude_terms=["editorial", "retracted publication"],
        expected_domain=intent.domain_id,
        expected_prompt_profile=profile,
        from_seed_triples=seed_ids or [],
        warnings=warnings,
    )


def _unique(items: list[LiteratureSearchQuery | None]) -> list[LiteratureSearchQuery]:
    return list({item.query_string: item for item in items if item}.values())


def build_literature_search_plan(
    intent: ResearchIntent,
    *,
    seed_triples: list[SeedResearchTriple] | None = None,
    domain_profile: DomainProfile | None = None,
    llm_client: Any | None = None,
    use_llm: bool = False,
    candidate_papers: list[dict[str, Any]] | None = None,
    output_root: str | Path = ".",
    write_outputs: bool = False,
    semantic_intake: SemanticIntakeResult | dict[str, Any] | None = None,
    explicit_profile_expansions: list[str] | None = None,
    unified_seed_triple: dict[str, Any] | None = None,
) -> LiteratureSearchPlan:
    profile = domain_profile or default_domain_router().resolve(intent.domain_id) or default_domain_router().route_text(intent.raw_user_input)
    primary = intent.primary_entities[0] if intent.primary_entities else intent.primary_entity
    disease = intent.disease_or_condition
    seed_ids = [item.triple_id for item in seed_triples or []]
    primary_texts, secondary_texts, mechanism_texts, comparison_texts, clinical_texts = [], [], [], [], []
    semantic = SemanticIntakeResult.model_validate(semantic_intake) if isinstance(semantic_intake, dict) else semantic_intake
    query_generation_mode = "deterministic_fallback"
    sanitizer_warnings: list[str] = [
        warning for warning in (semantic.verification_warnings if semantic else [])
        if "query" in warning
    ]
    if semantic and semantic.recommended_search_queries:
        query_generation_mode = "llm_semantic" if semantic.semantic_mode == "llm_semantic" else "deterministic_fallback"
        for candidate in semantic.recommended_search_queries:
            cleaned, item_warnings = sanitize_semantic_query(candidate)
            sanitizer_warnings.extend(item_warnings)
            if cleaned:
                primary_texts.append(cleaned)
    elif semantic:
        # Domain-agnostic fallback composition only.
        semantic_intent = semantic.research_intent
        primaries = semantic_intent.primary_entities or semantic_intent.intervention_entities
        diseases = semantic_intent.disease_or_condition
        outcomes = semantic_intent.outcome_entities
        mechanisms = semantic_intent.mechanism_entities
        if primaries and (outcomes or diseases):
            primary_texts.append(" ".join([primaries[0], *(outcomes[:1] or diseases[:1])]))
        if primaries and mechanisms:
            mechanism_texts.append(f"{primaries[0]} {mechanisms[0]}")
        if diseases and semantic_intent.intervention_entities:
            primary_texts.append(f"{diseases[0]} {semantic_intent.intervention_entities[0]}")
        if len(semantic_intent.comparison_entities) >= 2:
            comparison_texts.append(" ".join(semantic_intent.comparison_entities[:2]))
        if not (primary_texts or mechanism_texts or comparison_texts):
            primary_texts.extend(item.text for item in semantic.search_concepts[:3])
    elif primary and disease:
        # Legacy direct-call compatibility path. New workflow calls pass semantic_intake.
        primary_texts += [f"{primary} {disease}", f"{primary} antidepressant response"]
    if explicit_profile_expansions:
        mechanism_texts.extend(explicit_profile_expansions)
    if intent.needs_comparison and len(intent.comparison_entities) >= 2:
        left, right = intent.comparison_entities[:2]
        comparison_texts += [
            f"{left} {right} {disease} mechanism",
            f"{left} {right} antidepressant response comparison",
        ]
        primary_texts.append(f"{left} {right} {disease} comparison")
    if semantic is None and profile.domain_id == "drug_target_binding":
        subject = primary or "drug"
        target = intent.mechanism_entities[0] if intent.mechanism_entities else "target receptor"
        mechanism_texts += [
            f"{subject} {target} binding affinity Ki IC50",
            f"{subject} receptor antagonist agonist modulator",
            f"{subject} {target} ChEMBL DrugBank BindingDB",
        ]
    if semantic is None and profile.domain_id == "clinical_outcome":
        subject = primary or "intervention"
        condition = disease or "treatment-resistant depression"
        clinical_texts += [
            f"{subject} {condition} randomized controlled trial efficacy safety",
            f"{subject} {condition} response remission adverse events",
        ]
    if semantic is None and profile.domain_id == "pathway_biology":
        mechanism_texts.append(f"{primary or 'biomedical'} pathway activation mechanism")
    if semantic is None and profile.domain_id == "protein_interaction":
        mechanism_texts.append(f"{primary or 'protein'} protein interaction ligand receptor")
    for triple in seed_triples or []:
        mechanism_texts.append(f"{triple.subject} {triple.object} mechanism")
    if unified_seed_triple:
        subject = str((unified_seed_triple.get("subject") or {}).get("name") or "")
        relation = str((unified_seed_triple.get("relation") or {}).get("name") or "")
        obj = str((unified_seed_triple.get("object") or {}).get("name") or "")
        contexts = list((unified_seed_triple.get("context") or {}).get("context_terms") or [])
        core = " ".join(item for item in (subject, obj, *contexts[:1]) if item)
        if core:
            primary_texts.insert(0, core)
        if subject and obj:
            mechanism_texts.insert(0, " ".join(item for item in (subject, obj, relation) if item))
    if not (primary_texts or secondary_texts or mechanism_texts or comparison_texts or clinical_texts):
        primary_texts.append(intent.raw_user_input)
    warnings = []
    if use_llm and llm_client is not None:
        response = llm_client.extract_json("Generate PubMed/PMC search queries as JSON for: " + intent.raw_user_input)
        for item in response.get("queries", []):
            text = item.get("query_string") if isinstance(item, dict) else item
            cleaned, item_warnings = sanitize_query(str(text or ""))
            if cleaned:
                secondary_texts.append(cleaned)
            warnings.extend(item_warnings)
    primary_queries = _unique([_query(text, "primary", intent, seed_ids=seed_ids) for text in primary_texts])
    secondary_queries = _unique([_query(text, "secondary", intent, seed_ids=seed_ids) for text in secondary_texts])
    mechanism_queries = _unique([_query(text, "mechanism", intent, seed_ids=seed_ids) for text in mechanism_texts])
    comparison_queries = _unique([_query(text, "comparison", intent, seed_ids=seed_ids) for text in comparison_texts])
    clinical_queries = _unique([_query(text, "clinical", intent, seed_ids=seed_ids, priority=2) for text in clinical_texts])
    base = primary_queries + secondary_queries + mechanism_queries + comparison_queries + clinical_queries
    purpose_map = {"primary": "core_triple", "secondary": "broad_recall", "mechanism": "mechanism_recall", "comparison": "context_recall", "clinical": "context_recall"}
    precision_map = {"primary": "high", "mechanism": "medium", "comparison": "medium", "clinical": "medium", "secondary": "broad"}
    pubmed_queries = [item.model_copy(update={"source": "pubmed", "stage": "abstract_retrieval",
                                                   "purpose": purpose_map.get(item.purpose, item.purpose),
                                                   "precision_level": precision_map.get(item.purpose, "medium"),
                                                   "requires_open_access": False, "requires_fulltext": False}) for item in base]
    # Full-text escalation resolves PMCID/OA availability for selected papers; it
    # does not replay the broad abstract query against PMC.
    pmc_queries: list[LiteratureSearchQuery] = []
    query_groups = []
    for group, queries in (("core_triple", primary_queries), ("domain_mechanism_expansion", mechanism_queries), ("context_expansion", clinical_queries), ("broad_recall", secondary_queries)):
        query_groups.append({"group": group, "stage": "abstract_retrieval", "source": "pubmed", "queries": [item.model_copy(update={"source": "pubmed", "stage": "abstract_retrieval", "purpose": purpose_map.get(item.purpose, item.purpose), "precision_level": precision_map.get(item.purpose, "medium"), "requires_open_access": False, "requires_fulltext": False}).model_dump(mode="json") for item in queries]})
    query_groups.insert(1, {"group": "entity_alias_expansion", "stage": "abstract_retrieval", "source": "pubmed", "queries": []})
    query_groups.append({"group": "fulltext_escalation", "stage": "fulltext_escalation", "source": "pmc", "queries": [], "only_for_selected_conflict_candidates": True})
    plan = LiteratureSearchPlan(
        intent_id=intent.intent_id,
        primary_queries=primary_queries,
        secondary_queries=secondary_queries,
        mechanism_queries=mechanism_queries,
        comparison_queries=comparison_queries,
        clinical_queries=clinical_queries,
        pubmed_queries=pubmed_queries,
        pmc_queries=pmc_queries,
        negative_filters=["editorial", "retracted publication"],
        exclusion_terms=["editorial", "retracted publication"],
        priority="high" if intent.time_scope == "current" or intent.needs_comparison else "normal",
        candidate_papers=candidate_papers or [],
        warnings=list(dict.fromkeys(warnings)),
        domain_id=profile.domain_id,
        subdomain_id=profile.subdomain_id,
        search_profile_id=profile.search_profile_id,
        prompt_profile_id=profile.prompt_profile_id,
        validator_profile_id=profile.validator_profile_id,
        source_domain_profile=profile.to_dict(), query_generation_mode=query_generation_mode,
        sanitizer_warnings=list(dict.fromkeys(sanitizer_warnings)),
        semantic_confidence=min(semantic.research_intent.confidence, semantic.domain_routing.confidence) if semantic else intent.confidence,
        manual_review_required=semantic.domain_routing.requires_manual_review if semantic else False,
        seed_triple=unified_seed_triple or {}, query_groups=query_groups,
    )
    if write_outputs:
        root = Path(output_root)
        write_json(root / f"data/query/search_plan_{intent.intent_id}.json", plan.model_dump())
        report = root / f"reports/search_plan_{intent.intent_id}.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# Literature Search Plan\n\n" + "\n".join(f"- `{item.query_string}` ({item.source})" for item in base) + "\n", encoding="utf-8")
    return plan
