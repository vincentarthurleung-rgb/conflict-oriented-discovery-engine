"""Read-only preflight audit for external validation resources."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel
from code_engine.schemas.validation import ValidationResourcePolicy
from code_engine.validation.index_manifest import load_validation_index_manifest, validate_validation_index_manifest
from code_engine.validation.index_schema import load_validation_index_schema, validate_index_record_against_schema


class ValidationPreflightReport(CODEBaseModel):
    status: str
    registered_validators: list[str] = Field(default_factory=list)
    validator_capabilities: list[dict[str, Any]] = Field(default_factory=list)
    index_status: dict[str, dict[str, Any]] = Field(default_factory=dict)
    cache_status: str = "not_configured"
    duckdb_available: bool = False
    sqlite_available: bool = True
    resource_policy_valid: bool = True
    large_local_scan_enabled: bool = False
    remote_clients_status: str = "disabled"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def run_external_validation_preflight(
    index_dir: Path | None, cache_dir: Path | None, registry,
    resource_policy: ValidationResourcePolicy,
) -> ValidationPreflightReport:
    warnings: list[str] = []
    errors: list[str] = []
    index_status: dict[str, dict[str, Any]] = {}
    root = Path(index_dir) if index_dir else None
    for capability in registry.list_capabilities():
        name = capability.index_name
        if not capability.supports_local_index or not name:
            continue
        directory = root / name if root else None
        if not directory or not directory.exists():
            index_status[name] = {"status": "not_configured", "validator_name": capability.validator_name}
            continue
        schema_path, manifest_path = directory / "schema.json", directory / "manifest.json"
        if not schema_path.is_file() or not manifest_path.is_file():
            index_status[name] = {"status": "invalid", "reason": "schema_or_manifest_missing"}
            errors.append(f"{name}:schema_or_manifest_missing")
            continue
        try:
            schema = load_validation_index_schema(schema_path)
            manifest = load_validation_index_manifest(manifest_path)
            checked = validate_validation_index_manifest(manifest, schema)
            storage_path = directory / manifest.storage_path
            valid = checked.valid and storage_path.is_file()
            sample_warnings = []
            if valid and manifest.storage_format == "jsonl":
                with storage_path.open("r", encoding="utf-8") as handle:
                    sample = next((json.loads(line) for line in handle if line.strip()), None)
                if sample is not None:
                    sample_check = validate_index_record_against_schema(sample, schema)
                    valid = sample_check.valid
                    sample_warnings = sample_check.warnings
            index_status[name] = {
                "status": "ready" if valid else "invalid", "record_count": manifest.record_count,
                "storage_format": manifest.storage_format, "warnings": checked.warnings + sample_warnings,
            }
            if not valid:
                errors.append(f"{name}:invalid_schema_manifest_or_storage")
        except Exception as exc:
            index_status[name] = {"status": "invalid", "reason": f"{type(exc).__name__}:{exc}"}
            errors.append(f"{name}:invalid_index_metadata")
    duckdb_available = importlib.util.find_spec("duckdb") is not None
    uses_duckdb = any(item.get("storage_format") in {"duckdb", "parquet"} for item in index_status.values())
    if not duckdb_available and not uses_duckdb:
        warnings.append("duckdb_not_installed_but_not_required")
    elif not duckdb_available:
        errors.append("duckdb_required_but_not_installed")
    cache_status = "not_configured"
    if cache_dir:
        candidate = Path(cache_dir)
        cache_path = candidate if candidate.suffix in {".sqlite", ".db"} else candidate / "validation_query_cache.sqlite"
        cache_status = "available" if cache_path.is_file() else "configured_empty"
    policy_valid = all((
        resource_policy.max_records_per_validator > 0,
        resource_policy.max_signals_per_run > 0,
        resource_policy.max_query_seconds > 0,
        resource_policy.max_concurrent_validator_queries == 1,
    ))
    if not policy_valid:
        errors.append("resource_policy_invalid")
    if resource_policy.allow_large_local_scan:
        warnings.append("large_local_scan_enabled")
    configured_count = sum(item.get("status") == "ready" for item in index_status.values())
    if errors:
        status = "not_ready"
    elif warnings or configured_count < len(index_status):
        status = "ready_with_warnings"
    else:
        status = "ready"
    return ValidationPreflightReport(
        status=status, registered_validators=registry.names(),
        validator_capabilities=[item.model_dump(mode="json") for item in registry.list_capabilities()],
        index_status=index_status, cache_status=cache_status,
        duckdb_available=duckdb_available, sqlite_available=sqlite3.sqlite_version_info > (0,),
        resource_policy_valid=policy_valid,
        large_local_scan_enabled=resource_policy.allow_large_local_scan,
        remote_clients_status="enabled_by_policy_but_not_executed" if resource_policy.network_enabled and resource_policy.external_validation_enabled else "disabled",
        warnings=warnings, errors=errors,
    )


def write_preflight_report(report: ValidationPreflightReport, output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path, markdown_path = output / "validation_preflight_report.json", output / "validation_preflight_report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    lines = ["# External Validation Preflight", "", f"Status: `{report.status}`", "", "## Indexes", ""]
    lines.extend(f"- `{name}`: `{detail.get('status')}`" for name, detail in sorted(report.index_status.items()))
    lines += ["", "## Warnings", ""] + ([f"- {item}" for item in report.warnings] or ["- None"])
    lines += ["", "## Errors", ""] + ([f"- {item}" for item in report.errors] or ["- None"])
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


__all__ = ["ValidationPreflightReport", "run_external_validation_preflight", "write_preflight_report"]
