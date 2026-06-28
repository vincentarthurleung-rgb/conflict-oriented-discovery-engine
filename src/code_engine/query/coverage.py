"""Coverage scoring over the local artifact inventory and knowledge store."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from code_engine.query.models import CoverageReport, ResearchQuery
from code_engine.acquisition.manifest import find_unprocessed_papers_for_query, load_artifact_inventory
from code_engine.graph.knowledge_store import (
    load_knowledge_store,
    query_conflicts_for_pair,
    query_contexts_for_pair,
    query_exact_pair,
    query_hypotheses_for_pair,
    query_neighbors,
    query_validation_for_pair,
)


COVERAGE_WEIGHTS = {
    "exact_pair": 0.3,
    "conflict_edge": 0.2,
    "context_mentions": 0.2,
    "validation_result": 0.1,
    "neighbor_evidence": 0.2,
}
SUFFICIENT_THRESHOLD = 0.65
PARTIAL_THRESHOLD = 0.30
MIN_NEIGHBOR_EDGES = 2


def _available_layers(inventory: Dict[str, Any], store: Dict[str, Any]) -> list[str]:
    papers = inventory.get("papers", [])
    layers = []
    checks = (
        ("L0", any(item.get("raw_available") for item in papers)),
        ("Stage1", any(item.get("stage1_payload_available") for item in papers)),
        ("L1", any(item.get("l1_extracted") for item in papers)),
        ("L1.5", any(item.get("l1_5_refined") for item in papers)),
        ("L3", bool(store.get("triples"))),
        ("L4", bool(store.get("context_mentions"))),
        ("L5", bool(store.get("validation_results"))),
    )
    for layer, available in checks:
        if available:
            layers.append(layer)
    return layers


def _verdict(score: float) -> str:
    if score >= SUFFICIENT_THRESHOLD:
        return "Sufficient_No_Update_Needed"
    if score >= PARTIAL_THRESHOLD:
        return "Partial_Coverage_Delta_Update_Recommended"
    return "Insufficient_Run_New_Corpus_Search"


def _write_report(report: CoverageReport, data_path: Path, markdown_path: Path) -> None:
    data_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown = [
        "# Query Coverage Report",
        "",
        f"- Query ID: {report.query_id}",
        f"- Normalized pair: {report.normalized_subject} -> {report.normalized_object}",
        f"- Coverage score: {report.coverage_score:.2f}",
        f"- Verdict: {report.verdict}",
        f"- Runtime data status: {report.runtime_data_status}",
        f"- Knowledge store status: {report.knowledge_store_status}",
        f"- Using legacy data: {str(report.using_legacy_data).lower()}",
        f"- Exact observations: {report.exact_pair_observations}",
        f"- Neighbor edges: {len(report.neighbor_edges)}",
        f"- Context mentions: {len(report.context_mentions)}",
        f"- Validation results: {len(report.validation_results)}",
        "",
        "## Missing Dimensions",
        "",
    ]
    markdown.extend(f"- {item}" for item in report.missing_dimensions or ["None detected by the MVP rules."])
    markdown_path.write_text("\n".join(markdown) + "\n", encoding="utf-8")


def analyze_coverage(
    query: ResearchQuery,
    *,
    inventory: Dict[str, Any] | None = None,
    knowledge_store: Dict[str, Any] | None = None,
    repository_root: str | Path = ".",
    write_outputs: bool = True,
) -> CoverageReport:
    """Score local evidence availability; never calls a network or LLM API."""

    active_inventory = (
        inventory if inventory is not None
        else load_artifact_inventory(repository_root=repository_root)
    )
    store = (
        knowledge_store if knowledge_store is not None
        else load_knowledge_store(repository_root=repository_root)
    )
    subject, obj = query.normalized_subject, query.normalized_object
    exact = query_exact_pair(subject, obj, store) if subject and obj else []
    subject_neighbors = query_neighbors(subject, store=store) if subject else []
    object_neighbors = query_neighbors(obj, store=store) if obj else []
    neighbor_map = {
        f"{item.get('subject')}->{item.get('object')}": item
        for item in subject_neighbors + object_neighbors
    }
    neighbors = list(neighbor_map.values())
    conflicts = query_conflicts_for_pair(subject, obj, store) if subject and obj else []
    contexts = query_contexts_for_pair(subject, obj, store) if subject and obj else []
    validation = query_validation_for_pair(subject, obj, store) if subject and obj else []
    hypotheses = query_hypotheses_for_pair(subject, obj, store) if subject and obj else []
    supporting = [item for item in exact if item.get("relation_sign", 0) > 0]
    contradicting = [item for item in exact if item.get("relation_sign", 0) < 0]

    score = 0.0
    score += COVERAGE_WEIGHTS["exact_pair"] if exact else 0.0
    score += COVERAGE_WEIGHTS["conflict_edge"] if conflicts else 0.0
    score += COVERAGE_WEIGHTS["context_mentions"] if contexts else 0.0
    score += COVERAGE_WEIGHTS["validation_result"] if validation else 0.0
    score += COVERAGE_WEIGHTS["neighbor_evidence"] if len(neighbors) >= MIN_NEIGHBOR_EDGES else 0.0
    score = round(score, 2)

    missing = []
    if not exact:
        missing.append("no_exact_pair")
    if len(supporting) < 2:
        missing.append("few_supporting_triples")
    if not contexts:
        missing.append("no_context_mentions")
    if not validation:
        missing.append("no_validation_coverage")
    recent_years = [paper.get("year") for paper in active_inventory.get("papers", []) if isinstance(paper.get("year"), int)]
    if not recent_years or max(recent_years) < 2021:
        missing.append("no_recent_papers")
    if find_unprocessed_papers_for_query(query, active_inventory):
        missing.append("no_l1_extraction_for_candidate_papers")

    report = CoverageReport(
        query_id=query.query_id,
        normalized_subject=subject,
        normalized_object=obj,
        exact_pair_observations=len(exact),
        neighbor_edges=neighbors,
        supporting_triples=supporting,
        contradicting_triples=contradicting,
        conflict_edges=conflicts,
        context_mentions=contexts,
        validation_results=validation,
        hypotheses=hypotheses,
        available_layers=_available_layers(active_inventory, store),
        coverage_score=score,
        missing_dimensions=missing,
        verdict=_verdict(score),
        runtime_data_status=str(active_inventory.get("runtime_data_status", "unknown")),
        knowledge_store_status=str(store.get("knowledge_store_status", "unknown")),
        using_legacy_data=bool(
            active_inventory.get("using_legacy_data", False)
            or store.get("using_legacy_data", False)
        ),
        warnings=list(dict.fromkeys(
            list(active_inventory.get("warnings", [])) + list(store.get("warnings", []))
        )),
    )
    if write_outputs:
        root = Path(repository_root)
        _write_report(
            report,
            root / f"data/query/coverage_{query.query_id}.json",
            root / f"reports/query_coverage_{query.query_id}.md",
        )
    return report
