"""Conservative coverage decisions: provider omission never proves source absence."""
from __future__ import annotations

from typing import Any

from .models import SourcePresence


def source_presence(*, returned_by_provider: bool, deterministic_source_audit: str | None = None) -> SourcePresence:
    if deterministic_source_audit == "present":
        return SourcePresence.confirmed_present
    if deterministic_source_audit == "absent":
        return SourcePresence.confirmed_absent
    return SourcePresence.unknown


def zero_api_options(row: dict[str, Any]) -> list[str]:
    options: list[str] = []
    if row.get("preserved_in_raw_response"):
        options.append("reparse_existing_raw_response")
    if row.get("preserved_in_parsed_payload"):
        options.append("migrate_existing_parsed_payload")
    if row.get("deterministic_validation_available"):
        options.append("rerun_deterministic_validator")
    if row.get("normalization_available"):
        options.append("rerun_normalization")
    if any(options):
        options.append("rebuild_derived_artifacts")
    return options
