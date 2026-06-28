"""Sanitized PubMed/PMC search planning from research intent."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from pydantic import Field

from code_engine.common.json_io import write_json
from code_engine.query.intent import ResearchIntent
from code_engine.query.seed_triples import SeedResearchTriple
from code_engine.schemas.models import CODEBaseModel


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
    expected_prompt_profile: str = "general_biomedical"


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
    profile = "neuropharmacology" if intent.domain_id == "neuropharmacology" else "general_biomedical"
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
    llm_client: Any | None = None,
    use_llm: bool = False,
    candidate_papers: list[dict[str, Any]] | None = None,
    output_root: str | Path = ".",
    write_outputs: bool = False,
) -> LiteratureSearchPlan:
    primary = intent.primary_entities[0] if intent.primary_entities else intent.primary_entity
    disease = intent.disease_or_condition
    seed_ids = [item.triple_id for item in seed_triples or []]
    primary_texts, secondary_texts, mechanism_texts, comparison_texts, clinical_texts = [], [], [], [], []
    if primary and disease:
        primary_texts += [f"{primary} {disease}", f"{primary} antidepressant response"]
    if primary == "ketamine" and disease == "depression":
        mechanism_texts += [
            "ketamine BDNF depression",
            "ketamine NMDA receptor antidepressant",
            "ketamine AMPA receptor antidepressant",
            "ketamine mTOR BDNF depression",
            "ketamine synaptic plasticity antidepressant",
            "ketamine depression behavioral assay",
        ]
        secondary_texts.append("esketamine depression mechanism")
        clinical_texts.append("ketamine depression clinical trial antidepressant response")
    if intent.needs_comparison and len(intent.comparison_entities) >= 2:
        left, right = intent.comparison_entities[:2]
        comparison_texts += [
            f"{left} {right} {disease} mechanism",
            f"{left} {right} antidepressant response comparison",
        ]
        primary_texts.append(f"{left} {right} {disease} comparison")
    for triple in seed_triples or []:
        mechanism_texts.append(f"{triple.subject} {triple.object} mechanism")
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
    pubmed_queries = [item.model_copy(update={"source": "pubmed"}) for item in base]
    pmc_queries = [item.model_copy(update={"source": "pmc"}) for item in base]
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
    )
    if write_outputs:
        root = Path(output_root)
        write_json(root / f"data/query/search_plan_{intent.intent_id}.json", plan.model_dump())
        report = root / f"reports/search_plan_{intent.intent_id}.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# Literature Search Plan\n\n" + "\n".join(f"- `{item.query_string}` ({item.source})" for item in base) + "\n", encoding="utf-8")
    return plan
