"""Streaming JSONL/CSV/TSV validation index builder."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel
from code_engine.validation.index_manifest import (
    ValidationIndexManifest, compute_index_checksum, write_validation_index_manifest,
)
from code_engine.validation.index_schema import (
    ValidationIndexSchema, load_validation_index_schema,
    validate_index_record_against_schema, write_validation_index_schema,
)


DEFAULT_MAX_SOURCE_BYTES = 50 * 1024 * 1024


class ValidationIndexBuildResult(CODEBaseModel):
    build_id: str
    status: str
    validator_name: str
    index_dir: str
    schema_path: str
    manifest_path: str
    record_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ValidationIndexBuilder:
    name = "validation_index_builder"
    validator_name = "AbstractValidator"
    schema_name = ""
    schema_version = "1.0.0"

    def _stream_source(self, source_path: Path) -> Iterator[dict[str, Any]]:
        suffix = source_path.suffix.casefold()
        if suffix == ".jsonl":
            with source_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        yield json.loads(line)
            return
        if suffix not in {".csv", ".tsv"}:
            raise ValueError(f"Unsupported validation index source format: {suffix}")
        with source_path.open("r", encoding="utf-8", newline="") as handle:
            yield from csv.DictReader(handle, delimiter="\t" if suffix == ".tsv" else ",")

    def transform_record(self, record: dict[str, Any]) -> dict[str, Any]:
        return record

    def build_from_source(
        self, source_path: Path, output_dir: Path, *,
        source_database_version: str | None = None, max_records: int | None = None,
        dry_run: bool = False, allow_large_source: bool = False,
    ) -> ValidationIndexBuildResult:
        source_path, output_dir = Path(source_path), Path(output_dir)
        build_id = hashlib.sha256(f"{self.name}|{source_path.resolve()}|{source_path.stat().st_mtime_ns}".encode()).hexdigest()[:16]
        schema = load_validation_index_schema(self.schema_name)
        errors: list[str] = []
        warnings: list[str] = []
        if schema.schema_version != self.schema_version or schema.validator_name != self.validator_name:
            errors.append("builder_schema_binding_mismatch")
        if source_path.stat().st_size > DEFAULT_MAX_SOURCE_BYTES and not allow_large_source:
            errors.append("source_too_large_without_allow_large_source")
        if errors:
            return ValidationIndexBuildResult(
                build_id=build_id, status="blocked", validator_name=self.validator_name,
                index_dir=str(output_dir), schema_path=str(output_dir / "schema.json"),
                manifest_path=str(output_dir / "manifest.json"), errors=errors,
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        schema_path = write_validation_index_schema(schema, output_dir / "schema.json")
        records_path = output_dir / "records.jsonl"
        record_count = 0
        observed_fields: set[str] = set()
        records_handle = None if dry_run else records_path.open("w", encoding="utf-8")
        try:
            for source_record in self._stream_source(source_path):
                if max_records is not None and record_count >= max_records:
                    warnings.append("max_records_reached")
                    break
                record = self.transform_record(dict(source_record))
                validation = validate_index_record_against_schema(record, schema)
                if not validation.valid:
                    errors.append(f"record_{record_count}_missing:{','.join(validation.missing_fields)}")
                    continue
                observed_fields.update(record)
                if records_handle:
                    records_handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                record_count += 1
        finally:
            if records_handle:
                records_handle.close()
        manifest = ValidationIndexManifest(
            index_name=schema.index_name, validator_name=schema.validator_name,
            schema_version=schema.schema_version, source_database=schema.source_database,
            source_database_version=source_database_version, build_id=build_id,
            built_at=datetime.now(timezone.utc).isoformat(), builder_name=self.name,
            builder_version="1.0.0", record_count=record_count,
            field_count=len(observed_fields), checksum=None if dry_run else compute_index_checksum(records_path),
            supported_query_types=schema.supported_query_types,
            supported_entity_types=schema.supported_entity_types,
            supported_relation_families=schema.supported_relation_families,
            storage_format="jsonl", storage_path="records.jsonl",
            metadata={"source_path": str(source_path), "dry_run": dry_run},
            warnings=warnings + (["dry_run_records_not_written"] if dry_run else []),
        )
        manifest_path = write_validation_index_manifest(manifest, output_dir / "manifest.json")
        return ValidationIndexBuildResult(
            build_id=build_id, status="dry_run" if dry_run else ("completed_with_errors" if errors else "completed"),
            validator_name=self.validator_name, index_dir=str(output_dir),
            schema_path=str(schema_path), manifest_path=str(manifest_path),
            record_count=record_count, warnings=manifest.warnings, errors=errors,
        )


__all__ = ["DEFAULT_MAX_SOURCE_BYTES", "ValidationIndexBuildResult", "ValidationIndexBuilder"]
