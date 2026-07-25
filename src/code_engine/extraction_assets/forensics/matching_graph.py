"""Candidate graph construction without score-based authority decisions."""
from __future__ import annotations

from typing import Any

from .identities import edge_identity
from .models import AuthorityLevel, LineageCandidateEdge


def candidate_edge(left: str, right: str, *, direct: list[str] | None = None,
                   replay: list[str] | None = None, hashes: list[str] | None = None,
                   weak: list[str] | None = None, conflicts: list[str] | None = None,
                   competing: int = 0, score: float = 0.0) -> LineageCandidateEdge:
    direct, replay, hashes, weak, conflicts = direct or [], replay or [], hashes or [], weak or [], conflicts or []
    if conflicts:
        level = AuthorityLevel.rejected
    elif direct:
        level = AuthorityLevel.exact_bound
    elif replay or hashes:
        level = AuthorityLevel.deterministically_reconstructed
    elif weak:
        level = AuthorityLevel.probable_non_authoritative
    else:
        level = AuthorityLevel.unbound
    evidence: dict[str, Any] = {"direct": direct, "replay": replay, "hashes": hashes, "conflicts": conflicts}
    eid = edge_identity(left, right, evidence)
    return LineageCandidateEdge(
        edge_id=eid, left_identity=left, right_identity=right,
        direct_evidence_types=direct, replay_evidence_types=replay, hash_evidence=hashes,
        timestamp_evidence=["candidate_only"] if "timestamp" in weak else [],
        filename_evidence=["candidate_only"] if "filename" in weak else [],
        negative_evidence=[], conflict_evidence=conflicts, authority_candidate_level=level,
        deterministic_uniqueness=competing == 0 and level in {
            AuthorityLevel.exact_bound, AuthorityLevel.deterministically_reconstructed,
        }, competing_edge_count=competing, diagnostic_score=score, identity=eid,
    )

