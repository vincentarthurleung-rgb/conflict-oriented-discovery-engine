"""Planning only: determine the least expensive offline recovery mode."""
from __future__ import annotations


RECOVERY_PRIORITY = (
    "migrate_existing_validated_context", "migrate_existing_context_candidate",
    "reparse_authoritative_raw", "recover_from_parsed_payload",
    "deterministic_exact_anchor_reconstruction", "deterministic_scope_propagation",
    "rerun_validator", "rerun_normalization", "rebuild_consolidation",
    "selective_provider_reextraction", "source_reingestion",
)


def preferred_recovery_mode(available: list[str]) -> str:
    return next((mode for mode in RECOVERY_PRIORITY if mode in available), "unavailable")
