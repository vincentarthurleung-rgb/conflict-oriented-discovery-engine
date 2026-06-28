"""Evidence-scope contracts for progressive abstract/full-text processing."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from code_engine.schemas.models import CODEBaseModel


class EvidenceTier(str, Enum):
    ABSTRACT_SCREENING = "abstract_screening"
    ABSTRACT_CONFLICT_SIGNAL = "abstract_conflict_signal"
    FULLTEXT_EVIDENCE = "fulltext_evidence"
    FULLTEXT_MECHANISM = "fulltext_mechanism"
    MANUAL_REVIEW = "manual_review"
    COVERAGE_GAP = "coverage_gap"


class FullTextStatus(str, Enum):
    NOT_ATTEMPTED = "not_attempted"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INACCESSIBLE = "inaccessible"
    PARSED = "parsed"
    PARSE_FAILED = "parse_failed"
    ABSTRACT_ONLY = "abstract_only"


FULLTEXT_ELIGIBLE_STATUSES = {FullTextStatus.AVAILABLE.value, FullTextStatus.PARSED.value}
FULLTEXT_EVIDENCE_TIERS = {EvidenceTier.FULLTEXT_EVIDENCE.value, EvidenceTier.FULLTEXT_MECHANISM.value}


class PaperProcessingRecord(CODEBaseModel):
    paper_id: str
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    title: str | None = None
    abstract_available: bool = False
    full_text_status: str = FullTextStatus.NOT_ATTEMPTED.value
    evidence_tier: str = EvidenceTier.ABSTRACT_SCREENING.value
    selected_for_fulltext_escalation: bool = False
    selection_reason: str | None = None
    conflict_candidate_ids: list[str] = Field(default_factory=list)
    abstract_claim_count: int = 0
    fulltext_evidence_count: int = 0
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_scope(self):
        if self.full_text_status in {
            FullTextStatus.UNAVAILABLE.value,
            FullTextStatus.INACCESSIBLE.value,
            FullTextStatus.ABSTRACT_ONLY.value,
            FullTextStatus.PARSE_FAILED.value,
        }:
            if self.evidence_tier not in {
                EvidenceTier.ABSTRACT_CONFLICT_SIGNAL.value,
                EvidenceTier.COVERAGE_GAP.value,
            }:
                self.evidence_tier = EvidenceTier.COVERAGE_GAP.value
            if "fulltext_unavailable_not_mechanism_evidence" not in self.warnings:
                self.warnings.append("fulltext_unavailable_not_mechanism_evidence")
        return self

    @property
    def high_confidence_mechanism_eligible(self) -> bool:
        return (
            self.full_text_status in FULLTEXT_ELIGIBLE_STATUSES
            and self.evidence_tier in FULLTEXT_EVIDENCE_TIERS
        )


def is_high_confidence_mechanism_evidence(record: dict) -> bool:
    """Return true only for traceable full-text evidence tiers."""

    return (
        str(record.get("source_scope", "")) == "full_text"
        and str(record.get("evidence_tier", "")) in FULLTEXT_EVIDENCE_TIERS
    )


__all__ = [
    "EvidenceTier", "FullTextStatus", "PaperProcessingRecord",
    "FULLTEXT_ELIGIBLE_STATUSES", "is_high_confidence_mechanism_evidence",
]
