"""First-class, auditable evidence records for graph and hypothesis objects."""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import Field, model_validator

from code_engine.schemas.models import CODEBaseModel


StatementType = Literal[
    "direct_experimental_result", "reported_finding", "background_claim",
    "review_summary", "hypothesis", "speculation", "association_only", "unknown",
]
EvidenceType = Literal[
    "in_vitro", "animal_model", "human_clinical", "omics", "behavioral_assay",
    "biochemical_assay", "imaging", "genetic_perturbation", "unknown",
]
ClaimRole = Literal[
    "supports_edge", "contradicts_edge", "supports_context", "supports_hypothesis",
    "validation_evidence", "background_only",
]


class EvidenceRecord(CODEBaseModel):
    evidence_id: str
    paper_id: str
    chunk_id: str = ""
    chunk_hash: str = ""
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    title: str = ""
    year: int | None = None
    section: str = ""
    sentence: str = ""
    quote: str = ""
    subject_span: str = ""
    relation_span: str = ""
    object_span: str = ""
    context_spans: dict[str, Any] = Field(default_factory=dict)
    statement_type: StatementType = "unknown"
    evidence_type: EvidenceType = "unknown"
    claim_role: ClaimRole = "background_only"
    extraction_prompt_profile: str = "legacy_unknown"
    domain_id: str = "unknown"
    prompt_version: str = "legacy_unknown"
    output_schema_version: str = "legacy_unknown"
    extraction_policy_version: str = "legacy_unknown"
    model_name: str = "legacy_unknown"
    model_family: str = "unknown"
    compiled_prompt_hash: str = ""
    prompt_fingerprint: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_ungrounded_high_confidence(self):
        if not (self.quote.strip() or self.sentence.strip()) and self.confidence > 0.6:
            raise ValueError("Evidence without quote/sentence cannot have high confidence")
        return self


def build_minimal_evidence_record(record: dict[str, Any]) -> EvidenceRecord:
    """Adapt a legacy trace containing only evidence_sentence and identifiers."""

    sentence = str(record.get("sentence") or record.get("evidence_sentence") or "").strip()
    paper_id = str(record.get("paper_id") or record.get("source_asset") or "UNKNOWN")
    stable_source = "|".join((paper_id, sentence, str(record.get("triple_id", ""))))
    warnings = []
    confidence = float(record.get("confidence", 0.6 if sentence else 0.0))
    if not sentence:
        warnings.append("missing_quote_and_sentence")
        confidence = min(confidence, 0.6)
    return EvidenceRecord(
        evidence_id=str(record.get("evidence_id") or hashlib.sha256(stable_source.encode()).hexdigest()[:16]),
        paper_id=paper_id,
        pmid=record.get("pmid"),
        pmcid=record.get("pmcid"),
        doi=record.get("doi"),
        title=str(record.get("title") or record.get("article_title") or ""),
        year=record.get("year"),
        section=str(record.get("section") or ""),
        sentence=sentence,
        quote=str(record.get("quote") or sentence),
        claim_role="supports_edge" if record.get("relation_sign", 1) >= 0 else "contradicts_edge",
        extraction_prompt_profile=str(record.get("extraction_prompt_profile") or "legacy_unknown"),
        domain_id=str(record.get("domain_id") or "unknown"),
        confidence=confidence,
        warnings=warnings,
    )
