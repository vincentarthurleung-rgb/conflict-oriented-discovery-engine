"""Pure offline replayability classification."""
from __future__ import annotations

from .models import ReplayabilityStatus


def classify_replayability(
    *, source_available: bool, source_complete: bool, raw_available: bool,
    raw_hash_valid: bool, parsed_available: bool, parser_identity_available: bool,
    source_reingestion_required: bool = False, missing_target_semantics: bool = False,
) -> ReplayabilityStatus:
    if source_reingestion_required or not source_available:
        return ReplayabilityStatus.source_reingestion_required
    if raw_available and not raw_hash_valid:
        return ReplayabilityStatus.invalid
    if raw_available and raw_hash_valid and parser_identity_available:
        return (
            ReplayabilityStatus.fully_replayable_zero_api
            if source_complete and not missing_target_semantics
            else ReplayabilityStatus.replayable_from_raw_response
        )
    if parsed_available:
        return ReplayabilityStatus.replayable_from_parsed_candidate_only
    if missing_target_semantics:
        return ReplayabilityStatus.provider_reextraction_required
    return ReplayabilityStatus.partially_replayable
