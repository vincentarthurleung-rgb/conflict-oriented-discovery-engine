"""Compatibility namespace for local artifact indexes."""

from code_engine.acquisition.manifest import CandidatePaperMatchReport, match_candidate_papers_to_inventory
from code_engine.storage.mechanism_index import (
    load_mechanism_index, query_conflicted_mechanism_edges,
    query_evidence_for_mechanism_edge, query_mechanism_edges_for_entity,
    query_mechanism_paths_between,
)

__all__ = [
    "CandidatePaperMatchReport", "match_candidate_papers_to_inventory",
    "load_mechanism_index", "query_conflicted_mechanism_edges",
    "query_evidence_for_mechanism_edge", "query_mechanism_edges_for_entity",
    "query_mechanism_paths_between",
]
