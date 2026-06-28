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
    source: str = "deterministic_rule"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
