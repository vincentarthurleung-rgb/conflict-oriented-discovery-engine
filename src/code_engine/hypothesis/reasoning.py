"""Rule-based reasoning record construction from grounded hypothesis fields."""

import hashlib

from code_engine.schemas.hypothesis_hyperedge import HypothesisHyperedge
from code_engine.schemas.reasoning_record import ReasoningRecord


def build_reasoning_record(hyperedge: HypothesisHyperedge) -> ReasoningRecord:
    bottleneck = ", ".join(hyperedge.conflict_bottlenecks) or "unspecified"
    mechanism = hyperedge.proposed_mechanism or "unspecified"
    tradeoff = "; ".join(hyperedge.tradeoffs_or_limitations) or "unspecified"
    warnings = list(hyperedge.warnings)
    if "unspecified" in {bottleneck, mechanism, tradeoff}:
        warnings.append("one_or_more_reasoning_dimensions_unresolved")
    key = f"{hyperedge.hypothesis_id}|{bottleneck}|{mechanism}|{tradeoff}"
    grounded = sum(value != "unspecified" for value in (bottleneck, mechanism, tradeoff))
    abstract_only = hyperedge.source_scope == "abstract"
    limitations = list(hyperedge.tradeoffs_or_limitations)
    if abstract_only and not any("abstract" in item.casefold() for item in limitations):
        limitations.append("Only abstract-level evidence is available; full-text confirmation is required.")
    context_partition = ", ".join(hyperedge.context_variables) or ("context groups recorded" if hyperedge.hypothesis_type == "context_partition_hypothesis" else "unspecified")
    return ReasoningRecord(
        record_id=hashlib.sha256(key.encode()).hexdigest()[:16],
        hypothesis_id=hyperedge.hypothesis_id,
        bottleneck=bottleneck,
        mechanism=mechanism,
        tradeoff=tradeoff,
        evidence_ids=hyperedge.evidence_ids,
        input_conflicts=hyperedge.linked_conflict_ids,
        input_mechanism_paths=hyperedge.linked_mechanism_path_ids,
        input_evidence=hyperedge.evidence_ids,
        conflict_bottleneck=bottleneck,
        mechanism_bridge=mechanism,
        context_partition=context_partition,
        why_this_hypothesis=hyperedge.hypothesis_text or "The hypothesis is a deterministic transformation of linked run artifacts.",
        why_not_validated_yet="Validation is downstream and no validation result is used during hypothesis formation.",
        validation_requirements=hyperedge.validation_requirements,
        limitations=limitations,
        linked_paper_ids=hyperedge.linked_paper_ids,
        linked_canonical_paper_ids=hyperedge.linked_canonical_paper_ids,
        linked_dois=hyperedge.linked_dois,
        linked_titles=hyperedge.linked_titles,
        linked_journals=hyperedge.linked_journals,
        confidence=round(grounded / 3.0, 4),
        warnings=warnings,
    )
