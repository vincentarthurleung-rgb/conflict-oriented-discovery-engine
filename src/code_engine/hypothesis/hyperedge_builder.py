"""Deterministic adapter from legacy candidate hypotheses to hyperedges."""

from __future__ import annotations

from typing import Any

from code_engine.schemas.hypothesis_hyperedge import HypothesisHyperedge


VERDICT_TO_COVERAGE = {
    "Sufficient_No_Update_Needed": "existing_graph_supported",
    "Partial_Coverage_Delta_Update_Recommended": "partial_coverage",
    "Insufficient_Run_New_Corpus_Search": "insufficient_coverage",
    "Unresolved_No_Coverage": "unresolved_no_coverage",
}


def build_hypothesis_hyperedge(
    hypothesis: dict[str, Any],
    *,
    conflict_edges: list[dict[str, Any]] | None = None,
    context_attributions: list[dict[str, Any]] | None = None,
    validation_results: list[dict[str, Any]] | None = None,
    coverage_verdict: str | None = None,
    seed_query: str = "",
) -> HypothesisHyperedge:
    """Build a hyperedge without inventing mechanism links absent from inputs."""

    seed_pair = str(hypothesis.get("seed_pair") or "")
    if not seed_pair and (hypothesis.get("subject_canonical_id") or hypothesis.get("object_canonical_id")):
        seed_pair = f"{hypothesis.get('subject_canonical_id') or ''}->{hypothesis.get('object_canonical_id') or ''}"
    seed_entities = [part.strip() for part in seed_pair.split("->", 1)] if "->" in seed_pair else []
    mechanism_path = list(hypothesis.get("mechanism_path") or hypothesis.get("core_path") or [])
    entity_names = list(dict.fromkeys([*seed_entities, *mechanism_path]))
    edges = conflict_edges or []
    contexts = list(hypothesis.get("separating_contexts") or [])
    for attribution in context_attributions or []:
        contexts.extend(attribution.get("ranked_contexts", []))
    supporting = [str(edge.get("edge_id")) for edge in edges if edge.get("positive_count", 0) > 0]
    contradicting = [str(edge.get("edge_id")) for edge in edges if edge.get("negative_count", 0) > 0]
    bottlenecks = [
        str(edge.get("edge_id")) for edge in edges
        if edge.get("conflict_status") == "conflicting" or edge.get("conflict_type") not in (None, "Uncontested")
    ]
    evidence_ids = list(dict.fromkeys(
        [str(item) for edge in edges for item in edge.get("supporting_triples", []) + edge.get("contradicting_triples", [])]
        + [str(trace.get("evidence_id")) for trace in hypothesis.get("whitebox_traceability", []) if trace.get("evidence_id")]
    ))
    validation = validation_results or []
    unresolved = not validation or all(item.get("status") == "Unresolved_No_Coverage" for item in validation)
    raw_coverage = coverage_verdict or hypothesis.get("coverage_status", "")
    coverage = raw_coverage if raw_coverage in {"existing_graph_supported", "partial_coverage", "insufficient_coverage", "requires_delta_ingestion", "unresolved_no_coverage"} else VERDICT_TO_COVERAGE.get(raw_coverage, "unresolved_no_coverage")
    mechanism = " -> ".join(mechanism_path) if len(mechanism_path) >= 2 else "unspecified"
    limitations = list(hypothesis.get("tradeoffs_or_limitations") or hypothesis.get("validation_limitations") or [])
    if unresolved:
        limitations.append("No deterministic validator coverage.")
    warnings = list(hypothesis.get("warnings") or [])
    if not mechanism_path:
        warnings.append("mechanism_path_unavailable")
    subject = hypothesis.get("subject_canonical_id")
    obj = hypothesis.get("object_canonical_id")
    explicit_entities = list(hypothesis.get("entities") or [])
    if not explicit_entities and (subject or obj):
        explicit_entities = [
            {"canonical_id": subject, "name": hypothesis.get("subject_name") or subject or "", "entity_type": "unknown"},
            {"canonical_id": obj, "name": hypothesis.get("object_name") or obj or "", "entity_type": "unknown"},
        ]
    requirements = list(hypothesis.get("validation_requirements") or (["deterministic_external_validation"] if unresolved else []))
    return HypothesisHyperedge(
        hypothesis_id=str(hypothesis.get("hypothesis_id") or "UNKNOWN"),
        hypothesis_type=str(hypothesis.get("hypothesis_type") or hypothesis.get("candidate_type") or "legacy_hypothesis"),
        hypothesis_text=str(hypothesis.get("hypothesis_text") or ""),
        source_mode=str(hypothesis.get("source_mode") or "legacy_adapter"),
        source_scope=str(hypothesis.get("source_scope") or "unknown"),
        evidence_tier=str(hypothesis.get("evidence_tier") or "unknown"),
        seed_query=seed_query,
        seed_pair=seed_pair,
        entities=explicit_entities or [{"name": name, "entity_type": "unknown"} for name in entity_names if name],
        contexts=contexts,
        mechanism_path=mechanism_path,
        predicted_missing_links=list(hypothesis.get("predicted_missing_links") or []),
        conflict_bottlenecks=list(hypothesis.get("conflict_bottlenecks") or hypothesis.get("linked_conflict_candidate_ids") or bottlenecks),
        proposed_mechanism=str(hypothesis.get("proposed_mechanism") or mechanism),
        tradeoffs_or_limitations=list(dict.fromkeys(limitations)),
        supporting_edge_ids=supporting,
        contradicting_edge_ids=contradicting,
        evidence_ids=list(dict.fromkeys([*evidence_ids, *hypothesis.get("linked_evidence_ids", [])])),
        linked_conflict_ids=list(hypothesis.get("linked_conflict_candidate_ids") or hypothesis.get("linked_conflict_ids") or []),
        linked_fulltext_confirmation_ids=list(hypothesis.get("linked_fulltext_confirmation_ids") or []),
        linked_mechanism_edge_ids=list(hypothesis.get("linked_mechanism_edge_ids") or []),
        linked_mechanism_path_ids=list(hypothesis.get("linked_mechanism_path_ids") or []),
        linked_observation_ids=list(hypothesis.get("linked_observation_ids") or []),
        linked_paper_ids=list(hypothesis.get("linked_paper_ids") or []),
        linked_canonical_paper_ids=list(hypothesis.get("linked_canonical_paper_ids") or []),
        linked_dois=list(hypothesis.get("linked_dois") or []),
        linked_titles=list(hypothesis.get("linked_titles") or []),
        linked_journals=list(hypothesis.get("linked_journals") or []),
        paper_count=int(hypothesis.get("paper_count") or len(hypothesis.get("linked_canonical_paper_ids") or hypothesis.get("linked_paper_ids") or [])),
        journal_distribution=dict(hypothesis.get("journal_distribution") or {}),
        publication_year_range=dict(hypothesis.get("publication_year_range") or {}),
        relation_family=str(hypothesis.get("relation_family") or "unknown"),
        polarity_type=str(hypothesis.get("polarity_type") or "unknown"),
        direction=str(hypothesis.get("direction") or "unknown"),
        context_variables=list(hypothesis.get("context_variables") or []),
        validation_requirements=requirements,
        coverage_status=coverage,
        requires_manual_review=bool(hypothesis.get("requires_manual_review")),
        requires_fulltext_confirmation=bool(hypothesis.get("requires_fulltext_confirmation")),
        requires_external_validation=bool(hypothesis.get("requires_external_validation")),
        confidence=float(hypothesis.get("confidence", 0.0)),
        novelty_score=float(hypothesis.get("novelty_score", 0.0)),
        feasibility_score=float(hypothesis.get("feasibility_score", 0.0)),
        significance_score=float(hypothesis.get("significance_score", 0.0)),
        overall_score=float(hypothesis.get("overall_score", hypothesis.get("global_ranking_score", 0.0))),
        mechanism_specificity=float(hypothesis.get("mechanism_specificity", 0.0)),
        context_specificity=float(hypothesis.get("context_specificity", 0.0)),
        evidence_strength=float(hypothesis.get("evidence_strength", 0.0)),
        conflict_strength=float(hypothesis.get("conflict_strength", 0.0)),
        score_components=dict(hypothesis.get("score_components") or {}),
        status=str(hypothesis.get("status") or "candidate"),
        warnings=warnings,
    )
