"""Scoped immutable artifact inventory."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..identities import sha256_bytes, stable_identity


def inventory_files(root: Path, paths: Iterable[Path], *, artifact_kind: str) -> list[dict]:
    rows = []
    for path in sorted(set(paths), key=lambda p: str(p)):
        raw = path.read_bytes()
        relative = str(path.relative_to(root))
        payload = {"kind": artifact_kind, "relative_path": relative, "sha256": sha256_bytes(raw)}
        rows.append({
            "artifact_kind": artifact_kind, "existing_path": relative, "relative_path": relative,
            "sha256": payload["sha256"], "size": len(raw), "immutable_source_status": "historical_read_only",
            "available_explicit_ids": [], "available_source_refs": [], "available_prompt_refs": [],
            "available_parser_refs": [], "lineage_completeness": "not_assessed",
            "candidate_matching_features": {}, "provenance": {"offline": True},
            "schema_version": "historical_extraction_asset_inventory_v1",
            "identity": stable_identity("historical_extraction_asset_inventory_v1", payload),
        })
    return rows

