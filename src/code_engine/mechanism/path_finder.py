"""Bounded deterministic mechanism path enumeration."""

from __future__ import annotations

import hashlib

from code_engine.mechanism.models import MechanismGraph, MechanismPath


def find_mechanism_paths(mechanism_graph: MechanismGraph, max_path_length: int = 3, start_nodes: list[str] | None = None, end_nodes: list[str] | None = None) -> list[MechanismPath]:
    if max_path_length < 1:
        return []
    outgoing: dict[str, list] = {}
    for edge in mechanism_graph.edges:
        outgoing.setdefault(edge.source_node_id, []).append(edge)
    starts = sorted(set(start_nodes or outgoing))
    ends = set(end_nodes or [])
    paths, seen = [], set()
    max_paths_per_start = 100
    for start in starts:
        stack = [(start, [start], [])]
        produced = 0
        while stack and produced < max_paths_per_start:
            current, nodes, edges = stack.pop()
            if edges and (not ends or current in ends):
                signature = tuple(edge.edge_id for edge in edges)
                if signature not in seen:
                    seen.add(signature)
                    evidence = sorted({evidence_id for edge in edges for evidence_id in edge.evidence_ids})
                    conflicts = sorted({conflict_id for edge in edges for conflict_id in edge.conflict_edge_ids})
                    grounded = sum(bool(edge.evidence_ids) for edge in edges)
                    completeness = grounded / len(edges)
                    warnings = ["path_contains_conflicted_edge"] if conflicts else []
                    path_id = hashlib.sha256("|".join(signature).encode()).hexdigest()[:16]
                    paths.append(MechanismPath(path_id=path_id, node_ids=nodes, edge_ids=list(signature), start_node_id=start, end_node_id=current, path_length=len(edges), domain_id=mechanism_graph.domain_id, supporting_evidence_ids=evidence, conflict_edge_ids=conflicts, mechanistic_completeness=round(completeness, 6), warnings=warnings))
                    produced += 1
            if len(edges) >= max_path_length:
                continue
            for edge in reversed(sorted(outgoing.get(current, []), key=lambda item: item.edge_id)):
                if edge.target_node_id not in nodes:
                    stack.append((edge.target_node_id, nodes + [edge.target_node_id], edges + [edge]))
    return paths
