"""Versioned contracts for bounded local validation indexes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


class ValidationIndexSchema(CODEBaseModel):
    index_name: str
    validator_name: str
    schema_version: str
    source_database: str
    source_database_version: str | None = None
    record_format: str = "jsonl"
    required_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    supported_query_types: list[str] = Field(default_factory=list)
    supported_entity_types: list[str] = Field(default_factory=list)
    supported_relation_families: list[str] = Field(default_factory=list)
    supported_polarity_types: list[str] = Field(default_factory=list)
    primary_key_fields: list[str] = Field(default_factory=list)
    recommended_indexes: list[str] = Field(default_factory=list)
    direction_field: str | None = None
    score_fields: list[str] = Field(default_factory=list)
    context_fields: list[str] = Field(default_factory=list)
    interpretation_limits: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class IndexRecordValidation(CODEBaseModel):
    valid: bool
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def default_schema_root() -> Path:
    return Path(__file__).resolve().parents[3] / "configs" / "validation" / "index_schemas"


def load_validation_index_schema(path_or_name: str | Path) -> ValidationIndexSchema:
    path = Path(path_or_name)
    if not path.exists():
        path = default_schema_root() / f"{path_or_name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Validation index schema not found: {path}")
    return ValidationIndexSchema.model_validate_json(path.read_text(encoding="utf-8"))


def validate_index_record_against_schema(
    record: dict[str, Any], schema: ValidationIndexSchema,
) -> IndexRecordValidation:
    missing = [field for field in schema.required_fields if field not in record or record[field] is None]
    known = set(schema.required_fields) | set(schema.optional_fields)
    unknown = sorted(set(record) - known)
    warnings = [f"unknown_fields:{','.join(unknown)}"] if unknown else []
    return IndexRecordValidation(valid=not missing, missing_fields=missing, warnings=warnings)


def write_validation_index_schema(schema: ValidationIndexSchema, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(schema.model_dump_json(indent=2), encoding="utf-8")
    return destination


__all__ = [
    "IndexRecordValidation", "ValidationIndexSchema", "default_schema_root",
    "load_validation_index_schema", "validate_index_record_against_schema",
    "write_validation_index_schema",
]
