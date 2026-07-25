"""Authority validation with intentionally fail-closed rules."""
from __future__ import annotations

from typing import Any

from .models import AuthorityLevel, HistoricalLineageBinding
from ..identities import stable_identity

DIRECT_TYPES = {
    "provider_request_id_exact", "provider_response_id_exact", "raw_sha256_reference_exact",
    "cache_index_foreign_key_exact", "attempt_raw_path_exact", "manifest_foreign_key_exact",
    "call_dedup_identity_exact", "parsed_raw_identity_exact",
}


def make_binding(
    left_identity: str,
    right_identity: str | None,
    *,
    direct_evidence: list[dict[str, Any]] | None = None,
    deterministic_evidence: list[dict[str, Any]] | None = None,
    weak_evidence: list[str] | None = None,
    candidate_identities: list[str] | None = None,
    conflict_reasons: list[str] | None = None,
    algorithm_version: str = "historical_lineage_rebinding_v1",
    one_to_one_valid: bool = True,
) -> HistoricalLineageBinding:
    direct = direct_evidence or []
    deterministic = deterministic_evidence or []
    weak = weak_evidence or []
    conflicts = conflict_reasons or []
    candidates = sorted(set(candidate_identities or ([right_identity] if right_identity else [])))
    valid_direct = [row for row in direct if row.get("type") in DIRECT_TYPES]
    if conflicts:
        level = AuthorityLevel.rejected
    elif valid_direct and right_identity and len(candidates) == 1 and one_to_one_valid:
        level = AuthorityLevel.exact_bound
    elif deterministic and right_identity and len(candidates) == 1 and one_to_one_valid:
        level = AuthorityLevel.deterministically_reconstructed
    elif candidates:
        level = AuthorityLevel.probable_non_authoritative
    else:
        level = AuthorityLevel.unbound
    authoritative = level in {AuthorityLevel.exact_bound, AuthorityLevel.deterministically_reconstructed}
    proof = None
    if level == AuthorityLevel.deterministically_reconstructed:
        proof = {"candidate_count": 1, "one_to_one_valid": True, "input_order_independent": True}
    payload = {
        "left_identity": left_identity, "right_identity": right_identity,
        "binding_authority_level": level.value, "candidate_identities": candidates,
    }
    return HistoricalLineageBinding(
        binding_id=stable_identity("historical_lineage_binding_id_v1", payload),
        left_identity=left_identity, right_identity=right_identity,
        binding_authority_level=level, authoritative=authoritative,
        formal_replay_use_allowed=authoritative, direct_evidence=valid_direct,
        deterministic_evidence=deterministic, weak_evidence=weak,
        conflict_reasons=conflicts, algorithm_version=algorithm_version if deterministic else None,
        candidate_identities=candidates, excluded_candidates=[],
        uniqueness_proof=proof, one_to_one_valid=one_to_one_valid,
        identity=stable_identity("historical_lineage_binding_v1", payload),
    )

