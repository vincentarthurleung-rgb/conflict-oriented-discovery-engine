"""Offline query-driven incremental discovery API."""

from code_engine.query.models import CoverageReport, IngestionPlan, QueryAnswer, ResearchQuery
from code_engine.query.parser import parse_research_query
from code_engine.query.intent import ResearchIntent, parse_research_intent
from code_engine.query.search_planner import LiteratureSearchPlan, build_literature_search_plan
from code_engine.query.prompt_compatibility import (
    L1PromptFingerprint,
    PromptProfileFingerprint,
    build_l1_prompt_fingerprint,
    build_required_fingerprint_for_intent,
    compute_l1_cache_key,
)
from code_engine.query.intake import ResearchIntakeResult, parse_research_intake
from code_engine.query.seed_triples import SeedResearchTriple, build_seed_triples
from code_engine.query.l1_batch_planner import L1BatchProcessingPlan, plan_l1_batch_for_intent

__all__ = [
    "CoverageReport", "IngestionPlan", "QueryAnswer", "ResearchQuery",
    "parse_research_query",
    "ResearchIntent", "parse_research_intent",
    "LiteratureSearchPlan", "build_literature_search_plan",
    "PromptProfileFingerprint", "L1PromptFingerprint", "build_l1_prompt_fingerprint",
    "compute_l1_cache_key", "build_required_fingerprint_for_intent",
    "ResearchIntakeResult", "parse_research_intake", "SeedResearchTriple", "build_seed_triples",
    "L1BatchProcessingPlan", "plan_l1_batch_for_intent",
]
