"""Serializable contracts for paper identity, caching, and corpus operations."""

from __future__ import annotations

from typing import Any
from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


class PaperIdentity(CODEBaseModel):
    canonical_paper_id: str
    canonical_paper_key: str
    identity_confidence: float = 0.0
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    normalized_doi: str | None = None
    normalized_title_hash: str | None = None
    title_year_author_hash: str | None = None
    duplicate_of: str | None = None
    duplicate_resolution_method: str | None = None
    warnings: list[str] = Field(default_factory=list)


class BibliographicMetadata(CODEBaseModel):
    canonical_paper_id: str
    title: str | None = None
    normalized_title: str | None = None
    journal: str | None = None
    journal_iso: str | None = None
    publication_year: int | None = None
    publication_date: str | None = None
    authors: list[str] = Field(default_factory=list)
    first_author: str | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    publication_type: str | None = None
    source_database: str | None = None
    source_url: str | None = None
    citation_string: str | None = None
    metadata_quality: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class PaperSourceRecord(CODEBaseModel):
    canonical_paper_id: str
    source_database: str | None = None
    source_url: str | None = None
    original_paper_id: str | None = None
    run_id: str | None = None
    query: str | None = None


class PaperContentRecord(CODEBaseModel):
    canonical_paper_id: str
    abstract_hash: str | None = None
    fulltext_hash: str | None = None
    sections_hash: str | None = None
    abstract_available: bool = False
    fulltext_available: bool = False


class PaperProcessingStatus(CODEBaseModel):
    abstract_l1: str = "not_run"
    fulltext_l1: str = "not_run"
    l2_abstract: str = "not_run"
    l2_fulltext: str = "not_run"
    mechanism: str = "not_run"
    hypothesis: str = "not_run"
    validation: str = "not_run"


class PaperProvenanceRef(CODEBaseModel):
    canonical_paper_id: str | None = None
    paper_id: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    title: str | None = None
    journal: str | None = None
    publication_year: int | None = None
    warnings: list[str] = Field(default_factory=list)


class PaperRegistryRecord(CODEBaseModel):
    canonical_paper_id: str
    canonical_paper_key: str
    identity: PaperIdentity
    bibliographic: BibliographicMetadata
    abstract_available: bool = False
    fulltext_available: bool = False
    abstract_hash: str | None = None
    fulltext_hash: str | None = None
    sections_hash: str | None = None
    first_seen_run_id: str | None = None
    last_seen_run_id: str | None = None
    seen_in_queries: list[str] = Field(default_factory=list)
    seen_in_prompt_ids: list[str] = Field(default_factory=list)
    seen_count: int = 0
    created_at: str
    updated_at: str
    processing_status: dict[str, Any] = Field(default_factory=lambda: PaperProcessingStatus().model_dump())
    artifact_refs: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class KnowledgeMergeResult(CODEBaseModel):
    status: str
    update_global: bool = False
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    duplicate_count: int = 0
    object_type_counts: dict[str, int] = Field(default_factory=dict)
    artifact_refs: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class CoveragePrecheckResult(CODEBaseModel):
    coverage_score: float = 0.0
    recommended_action: str = "insufficient_global_store"
    dimensions: dict[str, float] = Field(default_factory=dict)
    matched_papers: list[dict] = Field(default_factory=list)
    matched_conflicts: list[dict] = Field(default_factory=list)
    matched_hypotheses: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "PaperIdentity", "BibliographicMetadata", "PaperRegistryRecord", "PaperSourceRecord",
    "PaperContentRecord", "PaperProcessingStatus", "PaperProvenanceRef",
    "KnowledgeMergeResult", "CoveragePrecheckResult",
]
