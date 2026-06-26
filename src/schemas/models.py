"""Pydantic schemas for the conservative C.O.D.E. v4.0 MVP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CODEBaseModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class PaperDocument(CODEBaseModel):
    paper_id: str
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    doi: Optional[str] = None
    year: Optional[int] = None
    title: str = ""
    abstract: str = ""
    full_text: str = ""
    source: str = ""
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    raw_path: Optional[str] = None
    payload_path: Optional[str] = None


class ScientificTriple(CODEBaseModel):
    triple_id: str
    paper_id: str
    chunk_id: str
    source: str
    relation_raw: str = ""
    relation_sign: int
    target: str
    evidence_sentence: str
    confidence: float = 1.0
    context: Dict[str, Any] = Field(default_factory=dict)
    negated: bool = False
    extraction_model: str = ""
    extraction_mode: str = ""

    @field_validator("relation_sign")
    @classmethod
    def relation_sign_must_be_directional(cls, value: int) -> int:
        if value not in (-1, 0, 1):
            raise ValueError("relation_sign must be -1, 0, or 1")
        return value


class NormalizedEntity(CODEBaseModel):
    raw_term: str
    canonical_name: str
    entity_type: str = "unknown"
    ontology_ids: List[str] = Field(default_factory=list)
    mapping_method: str = "uppercase_fallback"
    confidence: float = 0.5


class ConflictEdge(CODEBaseModel):
    edge_id: str
    source: str
    target: str
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    entropy: float = 0.0
    conflict_status: str = "uncontested"
    conflict_type: str = "Uncontested"
    supporting_triples: List[str] = Field(default_factory=list)
    contradicting_triples: List[str] = Field(default_factory=list)
    independent_labs_count: int = 0


class ContextMention(CODEBaseModel):
    context_id: str
    paper_id: str
    triple_id: str
    axis: str
    value: str
    span: str
    source_sentence: str
    extraction_mode: str = "rule"
    confidence: float = 1.0


class ContextAttribution(CODEBaseModel):
    conflict_edge_id: str
    ranked_contexts: List[Dict[str, Any]] = Field(default_factory=list)
    method: str = "entropy_reduction"
    score_components: Dict[str, Any] = Field(default_factory=dict)


class CandidateHypothesis(CODEBaseModel):
    hypothesis_id: str
    claim: str = ""
    seed_pair: str
    core_path: List[str] = Field(default_factory=list)
    separating_contexts: List[Dict[str, Any]] = Field(default_factory=list)
    supporting_conflict_edges: List[str] = Field(default_factory=list)
    complexity: float = 0.0
    consistency: float = 0.0
    identifiability: float = 0.0
    score_components: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(CODEBaseModel):
    hypothesis_id: str
    validator: str
    status: str
    coverage: str
    score: Optional[float] = None
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class FinalReportItem(CODEBaseModel):
    hypothesis_id: str
    rank: int
    claim: str
    score: float
    validation_status: str
    evidence_summary: str = ""
    limitations: List[str] = Field(default_factory=list)
    recommended_experiments: List[str] = Field(default_factory=list)


def validate_json_list(path: str | Path, schema_class: type[BaseModel]) -> List[BaseModel]:
    """Validate a JSON file containing a list or common wrapped list payload."""

    json_path = Path(path)
    with json_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, dict):
        for key in ("items", "records", "hypotheses", "ranked_hypotheses", "validation_results"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break

    if not isinstance(payload, list):
        raise ValueError(f"{json_path} must contain a JSON list or a supported wrapped list")

    return [schema_class.model_validate(item) for item in payload]
