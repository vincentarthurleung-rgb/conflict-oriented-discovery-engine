"""Local JSON MechanismGraph query adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from code_engine.mechanism.io import load_mechanism_graph
from code_engine.mechanism.models import MechanismGraph


def load_mechanism_index(path: str | Path) -> MechanismGraph:
    return load_mechanism_graph(path)


def _graph(graph: MechanismGraph | dict | str | Path) -> MechanismGraph:
    if isinstance(graph, MechanismGraph):
        return graph
    if isinstance(graph, dict):
        return MechanismGraph.model_validate(graph)
    return load_mechanism_graph(graph)


def query_mechanism_edges_for_entity(entity_id: str, graph: MechanismGraph | dict | str | Path) -> list[dict[str, Any]]:
    active = _graph(graph)
    needle = str(entity_id).casefold()
    return [edge.model_dump() for edge in active.edges if needle in {str(edge.source_node_id).casefold(), str(edge.target_node_id).casefold(), str(edge.subject_canonical_id or "").casefold(), str(edge.object_canonical_id or "").casefold(), str(edge.subject_name or "").casefold(), str(edge.object_name or "").casefold()}]


def query_mechanism_paths_between(source_id: str, target_id: str, graph: MechanismGraph | dict | str | Path) -> list[dict[str, Any]]:
    active = _graph(graph)
    source, target = str(source_id).casefold(), str(target_id).casefold()
    return [path.model_dump() for path in active.paths if path.start_node_id.casefold() == source and path.end_node_id.casefold() == target]


def query_conflicted_mechanism_edges(graph: MechanismGraph | dict | str | Path) -> list[dict[str, Any]]:
    return [edge.model_dump() for edge in _graph(graph).edges if edge.has_conflict]


def query_evidence_for_mechanism_edge(edge_id: str, graph: MechanismGraph | dict | str | Path) -> list[str]:
    edge = next((item for item in _graph(graph).edges if item.edge_id == edge_id), None)
    return list(edge.evidence_ids) if edge else []
