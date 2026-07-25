"""Conservative replayability v2 classification."""
from __future__ import annotations

from .models import AuthorityLevel, ReplayabilityStatusV2


def classify_replayability_v2(*, source_authority: AuthorityLevel | None,
                              raw_authority: AuthorityLevel | None,
                              parsed_available: bool, parser_available: bool,
                              complete_provenance: bool = False,
                              lineage_conflict: bool = False,
                              source_reingestion_needed: bool = False) -> ReplayabilityStatusV2:
    if lineage_conflict:
        return ReplayabilityStatusV2.ambiguity
    authoritative = {AuthorityLevel.exact_bound, AuthorityLevel.deterministically_reconstructed}
    if source_authority in authoritative and raw_authority in authoritative and parsed_available and parser_available:
        if complete_provenance:
            if source_authority == raw_authority == AuthorityLevel.exact_bound:
                return ReplayabilityStatusV2.fully_direct
            return ReplayabilityStatusV2.fully_reconstructed
        return (
            ReplayabilityStatusV2.raw_direct if raw_authority == AuthorityLevel.exact_bound
            else ReplayabilityStatusV2.raw_reconstructed
        )
    if parsed_available:
        return ReplayabilityStatusV2.parsed_only if parser_available else ReplayabilityStatusV2.partial
    if source_reingestion_needed:
        return ReplayabilityStatusV2.reingest
    return ReplayabilityStatusV2.reextract

