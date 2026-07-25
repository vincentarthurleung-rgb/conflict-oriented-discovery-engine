"""Post-forensic planning; this module cannot execute provider calls."""
from __future__ import annotations

from typing import Any


def recovery_mode(row: dict[str, Any]) -> str | None:
    checks = (
        ("authoritative_raw_available", "raw_rebinding"),
        ("authoritative_parsed_migration_available", "parsed_migration"),
        ("authoritative_anchor_reconstruction_available", "anchor_reconstruction"),
        ("validator_replay_available", "validator_replay"),
        ("normalization_replay_available", "normalization_replay"),
        ("derived_schema_only", "derived_only"),
    )
    return next((mode for field, mode in checks if row.get(field) is True), None)


def compress_requirements(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {key: 0 for key in (
        "raw_rebinding", "parsed_migration", "anchor_reconstruction",
        "validator_replay", "normalization_replay", "derived_only",
    )}
    remaining: list[dict[str, Any]] = []
    for row in rows:
        mode = recovery_mode(row)
        if mode:
            counts[mode] += 1
        else:
            remaining.append(row)
    blocks = {str(row["source_block_identity"]) for row in remaining}
    return {
        "pre_forensic_reextraction_upper_bound": len(rows),
        "requirements_eliminated_by_raw_rebinding": counts["raw_rebinding"],
        "requirements_eliminated_by_parsed_migration": counts["parsed_migration"],
        "requirements_eliminated_by_anchor_reconstruction": counts["anchor_reconstruction"],
        "requirements_eliminated_by_validator_replay": counts["validator_replay"],
        "requirements_eliminated_by_normalization_replay": counts["normalization_replay"],
        "requirements_eliminated_as_derived_only": counts["derived_only"],
        "post_forensic_reextraction_required_count": len(remaining),
        "post_forensic_unique_block_count": len(blocks),
        "post_forensic_estimated_minimal_provider_calls": len(blocks),
    }

