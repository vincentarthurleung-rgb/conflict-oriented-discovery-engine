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
    coverage = VERDICT_TO_COVERAGE.get(coverage_verdict or hypothesis.get("coverage_status", ""), "unresolved_no_coverage")
    mechanism = " -> ".join(mechanism_path) if len(mechanism_path) >= 2 else "unspecified"
    limitations = list(hypothesis.get("tradeoffs_or_limitations") or hypothesis.get("validation_limitations") or [])
    if unresolved:
        limitations.append("No deterministic validator coverage.")
    warnings = [] if mechanism_path else ["mechanism_path_unavailable"]
    return HypothesisHyperedge(
        hypothesis_id=str(hypothesis.get("hypothesis_id") or "UNKNOWN"),
        seed_query=seed_query,
        seed_pair=seed_pair,
        entities=[{"name": name, "entity_type": "unknown"} for name in entity_names if name],
        contexts=contexts,
        mechanism_path=mechanism_path,
        predicted_missing_links=list(hypothesis.get("predicted_missing_links") or []),
        conflict_bottlenecks=bottlenecks,
        proposed_mechanism=mechanism,
        tradeoffs_or_limitations=list(dict.fromkeys(limitations)),
        supporting_edge_ids=supporting,
        contradicting_edge_ids=contradicting,
        evidence_ids=evidence_ids,
        validation_requirements=list(hypothesis.get("validation_requirements") or (["deterministic_external_validation"] if unresolved else [])),
        coverage_status=coverage,
        novelty_score=float(hypothesis.get("novelty_score", 0.0)),
        feasibility_score=float(hypothesis.get("feasibility_score", 0.0)),
        significance_score=float(hypothesis.get("significance_score", 0.0)),
        overall_score=float(hypothesis.get("overall_score", hypothesis.get("global_ranking_score", 0.0))),
        status=str(hypothesis.get("status") or "candidate"),
        warnings=warnings,
    )

