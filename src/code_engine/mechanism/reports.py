"""MechanismGraph summaries and Markdown reporting."""

from __future__ import annotations

from pathlib import Path

from code_engine.mechanism.models import MechanismBuildReport, MechanismGraph


def build_mechanism_report(graph: MechanismGraph) -> MechanismBuildReport:
    return MechanismBuildReport(graph_id=graph.graph_id, node_count=len(graph.nodes), edge_count=len(graph.edges), path_count=len(graph.paths), conflict_annotation_count=len(graph.conflict_annotations), evidence_link_count=sum(len(edge.evidence_ids) for edge in graph.edges), claim_link_count=sum(len(edge.claim_ids) for edge in graph.edges), observation_link_count=sum(len(edge.observation_ids) for edge in graph.edges), skipped_low_confidence_count=int(graph.counts.get("skipped_low_confidence_count", 0)), skipped_unresolved_count=int(graph.counts.get("skipped_unresolved_count", 0)), warnings=list(graph.warnings))


def mechanism_graph_summary(graph: MechanismGraph) -> dict:
    report = build_mechanism_report(graph)
    support = sorted(graph.edges, key=lambda edge: (-edge.support_count, edge.edge_id))[:10]
    conflicted = sorted((edge for edge in graph.edges if edge.has_conflict), key=lambda edge: (-len(edge.conflict_edge_ids), edge.edge_id))[:10]
    return {**report.model_dump(), "top_mechanism_edges_by_support_count": [edge.model_dump() for edge in support], "top_conflicted_mechanism_edges": [edge.model_dump() for edge in conflicted]}


def render_mechanism_graph_report(graph: MechanismGraph, report: str | Path) -> Path:
    target = Path(report)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# MechanismGraph Report", "", f"- Graph ID: `{graph.graph_id}`", f"- Nodes: {len(graph.nodes)}", f"- Edges: {len(graph.edges)}", f"- Paths: {len(graph.paths)}", f"- Conflict annotations: {len(graph.conflict_annotations)}", "", "## Top mechanism edges", ""]
    lines.extend(f"- `{edge.edge_id}`: {edge.subject_name} → {edge.object_name}; {edge.relation_type}; support={edge.support_count}" for edge in sorted(graph.edges, key=lambda item: (-item.support_count, item.edge_id))[:10])
    lines += ["", "## Conflicted mechanism edges", ""]
    lines.extend([f"- `{edge.edge_id}`: {', '.join(edge.conflict_types)}" for edge in graph.edges if edge.has_conflict] or ["- None"])
    lines += ["", "## Warnings", ""] + ([f"- {item}" for item in graph.warnings] or ["- None"])
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
