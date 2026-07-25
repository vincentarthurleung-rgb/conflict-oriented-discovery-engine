"""Stable one-to-one lineage resolution."""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from .models import AuthorityLevel, LineageCandidateEdge

RANK = {
    AuthorityLevel.exact_bound: 2,
    AuthorityLevel.deterministically_reconstructed: 1,
    AuthorityLevel.probable_non_authoritative: 0,
    AuthorityLevel.unbound: -1,
    AuthorityLevel.rejected: -2,
}


def resolve_one_to_one(edges: Iterable[LineageCandidateEdge]) -> dict[str, object]:
    ordered = sorted(edges, key=lambda e: (e.left_identity, e.right_identity, e.edge_id))
    candidates = [e for e in ordered if RANK[e.authority_candidate_level] > 0 and not e.conflict_evidence]
    left_counts = Counter(e.left_identity for e in candidates)
    right_counts = Counter(e.right_identity for e in candidates)
    accepted = [
        e.edge_id for e in candidates
        if left_counts[e.left_identity] == 1 and right_counts[e.right_identity] == 1
    ]
    ambiguous = [
        e.edge_id for e in candidates
        if left_counts[e.left_identity] > 1 or right_counts[e.right_identity] > 1
    ]
    return {
        "accepted_edge_ids": accepted, "ambiguous_edge_ids": ambiguous,
        "one_to_one_valid": not ambiguous, "input_order_independent": True,
        "conflict_count": len(ambiguous),
    }

