"""Rule-based reasoning record construction from grounded hypothesis fields."""

import hashlib

from code_engine.schemas.hypothesis_hyperedge import HypothesisHyperedge
from code_engine.schemas.reasoning_record import ReasoningRecord


def build_reasoning_record(hyperedge: HypothesisHyperedge) -> ReasoningRecord:
    bottleneck = ", ".join(hyperedge.conflict_bottlenecks) or "unspecified"
    mechanism = hyperedge.proposed_mechanism or "unspecified"
    tradeoff = "; ".join(hyperedge.tradeoffs_or_limitations) or "unspecified"
    warnings = []
    if "unspecified" in {bottleneck, mechanism, tradeoff}:
        warnings.append("one_or_more_reasoning_dimensions_unresolved")
    key = f"{hyperedge.hypothesis_id}|{bottleneck}|{mechanism}|{tradeoff}"
    grounded = sum(value != "unspecified" for value in (bottleneck, mechanism, tradeoff))
    return ReasoningRecord(
        record_id=hashlib.sha256(key.encode()).hexdigest()[:16],
        hypothesis_id=hyperedge.hypothesis_id,
        bottleneck=bottleneck,
        mechanism=mechanism,
        tradeoff=tradeoff,
        evidence_ids=hyperedge.evidence_ids,
        confidence=round(grounded / 3.0, 4),
        warnings=warnings,
    )

