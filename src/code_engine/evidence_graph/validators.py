"""Non-failing graph contract checks."""

from __future__ import annotations

from collections import Counter
from typing import Any


def validate_graph_contract(nodes: list[dict[str, Any]], edges: list[dict[str, Any]],
                            bundles: list[dict[str, Any]], conflicts: list[dict[str, Any]],
                            *, hypotheses_without_match: list[str] | None = None,
                            timelines_without_match: list[str] | None = None) -> dict[str, Any]:
    node_ids = [str(item.get("node_id")) for item in nodes]
    edge_ids = [str(item.get("edge_id")) for item in edges]
    node_set = set(node_ids)
    duplicate_nodes = sorted(key for key, count in Counter(node_ids).items() if count > 1)
    duplicate_edges = sorted(key for key, count in Counter(edge_ids).items() if count > 1)
    missing_sources = sorted(str(item.get("edge_id")) for item in edges if str(item.get("source")) not in node_set)
    missing_targets = sorted(str(item.get("edge_id")) for item in edges if str(item.get("target")) not in node_set)
    bundle_ids = {str(item.get("bundle_id")) for item in bundles}
    report = {
        "status": "valid" if not (duplicate_nodes or duplicate_edges or missing_sources or missing_targets) else "warnings",
        "missing_node_targets": sorted({str(item.get("source")) for item in edges if str(item.get("source")) not in node_set} |
                                       {str(item.get("target")) for item in edges if str(item.get("target")) not in node_set}),
        "duplicate_node_ids": duplicate_nodes, "duplicate_edge_ids": duplicate_edges,
        "edges_with_missing_source": missing_sources, "edges_with_missing_target": missing_targets,
        "bundles_without_evidence": sorted(str(item.get("bundle_id")) for item in bundles if not item.get("evidence_edge_ids")),
        "conflicts_without_bundle": sorted(str(item.get("graph_conflict_id")) for item in conflicts if str(item.get("bundle_id")) not in bundle_ids),
        "hypotheses_without_conflict_match": sorted(hypotheses_without_match or []),
        "timelines_without_conflict_match": sorted(timelines_without_match or []),
        "observations_without_paper_provenance": sorted(str(item.get("node_id")) for item in nodes if item.get("node_type") == "observation" and not item.get("provenance", {}).get("paper_id") and not item.get("provenance", {}).get("canonical_paper_id")),
    }
    report["warnings"] = [key for key, value in report.items() if isinstance(value, list) and value]
    return report
