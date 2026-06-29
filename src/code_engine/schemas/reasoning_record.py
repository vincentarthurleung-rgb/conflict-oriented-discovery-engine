"""Rule-derived bottleneck, mechanism, and tradeoff records."""

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


class ReasoningRecord(CODEBaseModel):
    record_id: str
    hypothesis_id: str
    bottleneck: str = "unspecified"
    mechanism: str = "unspecified"
    tradeoff: str = "unspecified"
    evidence_ids: list[str] = Field(default_factory=list)
    input_conflicts: list[str] = Field(default_factory=list)
    input_mechanism_paths: list[str] = Field(default_factory=list)
    input_evidence: list[str] = Field(default_factory=list)
    conflict_bottleneck: str = "unspecified"
    mechanism_bridge: str = "unspecified"
    context_partition: str = "unspecified"
    why_this_hypothesis: str = ""
    why_not_validated_yet: str = "Validation occurs after hypothesis formation."
    validation_requirements: list = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    linked_paper_ids: list[str] = Field(default_factory=list)
    linked_canonical_paper_ids: list[str] = Field(default_factory=list)
    linked_dois: list[str] = Field(default_factory=list)
    linked_titles: list[str] = Field(default_factory=list)
    linked_journals: list[str] = Field(default_factory=list)
    source: str = "deterministic_rule"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
