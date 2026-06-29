"""Manifest loading, validation, and checksums for validation indexes."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel
from code_engine.validation.index_schema import ValidationIndexSchema


class ValidationIndexManifest(CODEBaseModel):
    index_name: str
    validator_name: str
    schema_version: str
    source_database: str
    source_database_version: str | None = None
    build_id: str
    built_at: str
    builder_name: str
    builder_version: str
    record_count: int
    field_count: int
    checksum: str | None = None
    supported_query_types: list[str] = Field(default_factory=list)
    supported_entity_types: list[str] = Field(default_factory=list)
    supported_relation_families: list[str] = Field(default_factory=list)
    storage_format: str
    storage_path: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ManifestValidation(CODEBaseModel):
    valid: bool
    blocked: bool = False
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def load_validation_index_manifest(path: str | Path) -> ValidationIndexManifest:
    manifest_path = Path(path)
    if manifest_path.is_dir():
        manifest_path = manifest_path / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Validation index manifest not found: {manifest_path}")
    return ValidationIndexManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))


def validate_validation_index_manifest(
    manifest: ValidationIndexManifest, schema: ValidationIndexSchema, *, block_version_mismatch: bool = True,
) -> ManifestValidation:
    errors: list[str] = []
    warnings: list[str] = []
    if manifest.index_name != schema.index_name:
        errors.append("index_name_mismatch")
    if manifest.validator_name != schema.validator_name:
        errors.append("validator_name_mismatch")
    if manifest.schema_version != schema.schema_version:
        warnings.append("schema_version_mismatch")
        if block_version_mismatch:
            errors.append("schema_version_mismatch_blocked")
    if manifest.storage_format != schema.record_format:
        errors.append("record_format_mismatch")
    if manifest.record_count < 0 or manifest.field_count < len(schema.required_fields):
        errors.append("manifest_count_invalid")
    return ManifestValidation(valid=not errors, blocked=bool(errors), warnings=warnings, errors=errors)


def compute_index_checksum(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def write_validation_index_manifest(manifest: ValidationIndexManifest, path: str | Path) -> Path:
    destination = Path(path)
    if destination.suffix != ".json":
        destination = destination / "manifest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return destination


__all__ = [
    "ManifestValidation", "ValidationIndexManifest", "compute_index_checksum",
    "load_validation_index_manifest", "validate_validation_index_manifest",
    "write_validation_index_manifest",
]
