"""Data contracts for the query-driven incremental discovery layer."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


QueryType = Literal["entity_pair", "directed_relation", "topic", "mechanism_path", "unknown"]
CoverageVerdict = Literal[
    "Sufficient_No_Update_Needed",
    "Partial_Coverage_Delta_Update_Recommended",
    "Insufficient_Run_New_Corpus_Search",
]


class ResearchQuery(CODEBaseModel):
    query_id: str
    raw_query: str
    subject_raw: str = ""
    relation_raw: str = ""
    object_raw: str = ""
    query_type: QueryType = "unknown"
    normalized_subject: str = ""
    normalized_object: str = ""
    subject_entity_type: str = "unknown"
    object_entity_type: str = "unknown"
    language: str = "unknown"
    created_at: str
    normalization_audit: Dict[str, Any] = Field(default_factory=dict)


class CoverageReport(CODEBaseModel):
    query_id: str
    normalized_subject: str = ""
    normalized_object: str = ""
    exact_pair_observations: int = 0
    neighbor_edges: List[Dict[str, Any]] = Field(default_factory=list)
    supporting_triples: List[Dict[str, Any]] = Field(default_factory=list)
    contradicting_triples: List[Dict[str, Any]] = Field(default_factory=list)
    conflict_edges: List[Dict[str, Any]] = Field(default_factory=list)
    context_mentions: List[Dict[str, Any]] = Field(default_factory=list)
    validation_results: List[Dict[str, Any]] = Field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
    available_layers: List[str] = Field(default_factory=list)
    coverage_score: float = 0.0
    missing_dimensions: List[str] = Field(default_factory=list)
    verdict: CoverageVerdict
    runtime_data_status: str = "unknown"
    knowledge_store_status: str = "unknown"
    using_legacy_data: bool = False
    warnings: List[str] = Field(default_factory=list)


class IngestionPlan(CODEBaseModel):
    query_id: str
    search_queries: List[str] = Field(default_factory=list)
    existing_papers: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_new_papers: List[Dict[str, Any]] = Field(default_factory=list)
    duplicate_papers: List[Dict[str, Any]] = Field(default_factory=list)
    papers_need_stage1: List[Dict[str, Any]] = Field(default_factory=list)
    papers_need_l1: List[Dict[str, Any]] = Field(default_factory=list)
    papers_need_l1_5: List[Dict[str, Any]] = Field(default_factory=list)
    estimated_new_chunks: int = 0
    estimated_api_calls: int = 0
    budget_limit: Dict[str, Optional[int]] = Field(default_factory=dict)
    budget_status: str = "within_budget"
    recommended_action: str = "review_dry_run_plan"
    dry_run: bool = True
    runtime_data_status: str = "unknown"
    using_legacy_data: bool = False


class QueryAnswer(CODEBaseModel):
    query_id: str
    answer_mode: str
    coverage_verdict: CoverageVerdict
    hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_summary: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    recommended_next_steps: List[str] = Field(default_factory=list)
    used_existing_graph_only: bool = True
    api_calls_made: int = 0
    runtime_data_status: str = "unknown"
    knowledge_store_status: str = "unknown"
    using_legacy_data: bool = False
