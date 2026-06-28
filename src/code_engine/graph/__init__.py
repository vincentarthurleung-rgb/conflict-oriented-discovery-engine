"""Normalization, conflict, context, and local knowledge graph operations."""

from code_engine.graph.conflict_discovery import build_conflict_graph
from code_engine.graph.ontology_alignment import extract_normalized_observations
from code_engine.graph.probabilistic_conflict import ProbabilisticConflictState, compute_probabilistic_conflict_state

__all__ = [
    "build_conflict_graph", "extract_normalized_observations",
    "ProbabilisticConflictState", "compute_probabilistic_conflict_state",
]
