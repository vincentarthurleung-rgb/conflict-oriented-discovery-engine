"""Conservative Markdown rendering for run-level merged evidence graphs."""

from __future__ import annotations

from typing import Any


def render_merged_evidence_graph_section(summary: dict[str, Any], conflicts: list[dict[str, Any]],
                                         traces: list[dict[str, Any]], nodes: list[dict[str, Any]],
                                         edges: list[dict[str, Any]] | None = None) -> list[str]:
    lines = ["## Merged Evidence Graph / 合并证据图谱", "",
             "This is a run-level graph-ready reasoning layer, not a corpus-level graph search or visualization system.", ""]
    if not summary:
        return lines + ["No merged evidence graph summary was available.", ""]
    for name in ("node_count", "edge_count", "relation_bundle_count", "graph_conflict_candidate_count",
                 "graph_uncontested_relation_count", "graph_insufficient_evidence_count", "bundle_with_conflict_rate",
                 "hypothesis_matched_to_conflict_rate", "timeline_attached_to_conflict_rate"):
        lines.append(f"- {name}: `{summary.get(name, 0)}`")
    for name in ("incomplete_evidence_edge_count", "excluded_from_bundle_reasoning_count",
                 "identity_incomplete_conflict_candidate_count", "graph_conflict_candidates_used_by_hypothesis",
                 "graph_conflict_candidates_used_by_timeline"):
        lines.append(f"- {name}: `{summary.get(name, 0)}`")
    trace_by_id = {str(item.get("reasoning_trace_id")): item for item in traces}
    conflict_nodes = {str(item.get("canonical_id")): item for item in nodes if item.get("node_type") == "conflict"}
    node_by_id = {str(item.get("node_id")): item for item in nodes}
    edges = edges or []
    for conflict in [item for item in conflicts if item.get("status") == "graph_conflict_candidate"][:5]:
        trace = trace_by_id.get(str(conflict.get("reasoning_trace_id")), {})
        lines += ["", f"### Graph-derived conflict candidate: {conflict.get('subject_canonical_id')} - {conflict.get('relation_family')} - {conflict.get('object_canonical_id')}", "",
                  "Reasoning:", "", "- Derived from opposing evidence edges in the same relation bundle.",
                  f"- Paper-level direction distribution: `{conflict.get('paper_level_direction_distribution', {})}`",
                  f"- Entropy: `{conflict.get('entropy')}`", f"- Thresholds: `{trace.get('thresholds', {})}`",
                  f"- Linked evidence / papers: `{conflict.get('evidence_count', 0)}` / `{conflict.get('paper_count', 0)}`", "",
                  "Evidence examples:", "", "| Year | Direction | Paper | Evidence Span |", "|---|---|---|---|"]
        linked_ids = set(conflict.get("linked_evidence_edge_ids", []))
        examples = [item for item in nodes if item.get("node_type") == "observation" and item.get("attributes", {}).get("evidence_edge_id") in linked_ids][:5]
        for example in examples:
            attributes, provenance = example.get("attributes", {}), example.get("provenance", {})
            span = str(provenance.get("evidence_span") or provenance.get("evidence_text") or "missing").replace("|", "\\|").replace("\n", " ")
            paper = provenance.get("canonical_paper_id") or provenance.get("paper_id") or provenance.get("doi") or provenance.get("title") or "unknown"
            lines.append(f"| {provenance.get('publication_year')} | {attributes.get('direction')} | {paper} | {span} |")
        lines += ["",
                  "Timeline and hypotheses:", ""]
        node = conflict_nodes.get(str(conflict.get("graph_conflict_id")), {})
        node_id = str(node.get("node_id") or conflict.get("graph_conflict_id"))
        attached = [edge for edge in edges if edge.get("target") == node_id or edge.get("source") == node_id]
        temporal = [node_by_id.get(str(edge.get("target")), {}) for edge in attached if str(edge.get("edge_type", "")).startswith("conflict_has_")]
        hypotheses = [node_by_id.get(str(edge.get("source")), {}) for edge in attached if edge.get("edge_type") == "hypothesis_explains_conflict"]
        lines += [f"- Temporal windows: `{[item.get('attributes', {}) for item in temporal]}`.",
                  f"- Linked hypotheses: `{[item.get('canonical_id') for item in hypotheses]}`.",
                  "- A graph-derived conflict candidate is not proof that a scientific conflict is solved or that a hypothesis is true."]
    return lines + [""]
