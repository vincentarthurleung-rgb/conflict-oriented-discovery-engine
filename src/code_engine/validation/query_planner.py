"""Capability- and resource-aware planning before validator execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from code_engine.schemas.validation import (
    ValidationAnchor, ValidationQueryPlan, ValidationQuestion,
    ValidationResourcePolicy, ValidatorRoute,
)
from code_engine.validation.cache import ValidationQueryCache, build_validation_cache_key
from code_engine.validation.index_manifest import load_validation_index_manifest, validate_validation_index_manifest
from code_engine.validation.index_schema import load_validation_index_schema, validate_index_record_against_schema
from code_engine.validation.resource_guard import enforce_validation_resource_policy, summarize_validation_resource_usage
from code_engine.validation.storage import ValidationLocalIndex


INDEX_EXTENSIONS = (".jsonl", ".sqlite", ".db", ".duckdb", ".parquet")


def _find_index(index_dir: str | None, index_name: str | None) -> tuple[Path | None, str | None]:
    if not index_dir or not index_name:
        return None, None
    root = Path(index_dir)
    nested_root = root / index_name
    for filename, index_type in (("records.jsonl", "jsonl"), ("records.sqlite", "sqlite"), ("records.parquet", "parquet"), ("records.duckdb", "duckdb")):
        nested = nested_root / filename
        if nested.is_file():
            return nested, index_type
    for extension in INDEX_EXTENSIONS:
        candidate = root / f"{index_name}{extension}"
        if candidate.is_file():
            return candidate, extension.lstrip(".")
    return None, None


def _validate_index_binding(path: Path, validator) -> tuple[bool, list[str], dict[str, str]]:
    schema_path, manifest_path = path.parent / "schema.json", path.parent / "manifest.json"
    if not schema_path.is_file() or not manifest_path.is_file():
        return False, ["schema_or_manifest_missing"], {}
    try:
        schema = load_validation_index_schema(schema_path)
        manifest = load_validation_index_manifest(manifest_path)
        checked = validate_validation_index_manifest(manifest, schema)
        errors = list(checked.errors)
        if schema.index_name != getattr(validator, "schema_name", None):
            errors.append("validator_schema_name_mismatch")
        if schema.schema_version != getattr(validator, "schema_version", None):
            errors.append("validator_schema_version_mismatch")
        if path.suffix == ".jsonl":
            with path.open("r", encoding="utf-8") as handle:
                first = next((json.loads(line) for line in handle if line.strip()), None)
            if first is not None:
                record_check = validate_index_record_against_schema(first, schema)
                if not record_check.valid:
                    errors.append(f"index_record_missing_required_fields:{','.join(record_check.missing_fields)}")
        return not errors, list(dict.fromkeys(checked.warnings + errors)), {
            "schema_path": str(schema_path), "manifest_path": str(manifest_path),
        }
    except Exception as exc:
        return False, [f"index_binding_error:{type(exc).__name__}:{exc}"], {}


def _cache_path(cache_dir: str | None) -> Path | None:
    if not cache_dir:
        return None
    path = Path(cache_dir)
    return path if path.suffix in {".sqlite", ".db"} else path / "validation_query_cache.sqlite"


def plan_validation_queries(
    routes: list[ValidatorRoute], questions: list[ValidationQuestion],
    anchors: list[ValidationAnchor], registry, resource_policy: ValidationResourcePolicy,
    preferred_mode: str = "auto",
) -> list[ValidationQueryPlan]:
    questions_by_id = {item.question_id: item for item in questions}
    anchors_by_id = {item.anchor_id: item for item in anchors}
    plans = []
    for route in routes:
        question = questions_by_id[route.question_id]
        anchor = anchors_by_id[route.anchor_id]
        capability = registry.get_capability(route.validator_name)
        cache_key = build_validation_cache_key(
            route.validator_name, question.validator_intent, question.entities,
            question.relation_family, question.polarity_type, question.direction,
            question.contexts, "validator_capability_v1",
        )
        stable = f"{route.route_id}|{cache_key}"
        plan = ValidationQueryPlan(
            query_plan_id=hashlib.sha256(stable.encode()).hexdigest()[:16],
            anchor_id=anchor.anchor_id, question_id=question.question_id,
            validator_name=route.validator_name, query_type=question.validator_intent,
            query_entities=question.entities,
            query_context={
                "anchor_context": question.contexts,
                "expected_direction": question.expected_direction,
                "relation_family": question.relation_family,
                "polarity_type": question.polarity_type,
            },
            index_name=capability.index_name, cache_key=cache_key,
            max_records=min(capability.default_max_records, resource_policy.max_records_per_validator, resource_policy.max_records_per_anchor),
            max_signals=min(capability.default_max_signals, resource_policy.max_signals_per_validator),
            max_raw_payload_bytes=resource_policy.max_raw_payload_bytes_per_validator,
            timeout_seconds=resource_policy.max_query_seconds,
            status="planned", reason="resource_selection_pending",
        )
        if not question.entities:
            plan.status, plan.execution_mode, plan.reason = "too_broad", "blocked", "query_has_no_entities"
            plans.append(plan)
            continue
        if route.validator_name == "NullValidator":
            plan.status, plan.execution_mode, plan.reason = "allowed", "disabled", "null_validator_no_coverage_route"
            plans.append(plan)
            continue
        index_path, index_type = _find_index(resource_policy.index_dir, capability.index_name)
        cache_path = _cache_path(resource_policy.cache_dir)
        cache_hit = False
        if resource_policy.cache_enabled and cache_path and cache_path.exists():
            iterator = ValidationQueryCache(cache_path).lookup(cache_key, 1)
            cache_hit = next(iterator, None) is not None
        mode = preferred_mode
        if mode == "auto":
            if capability.supports_local_index and index_path:
                mode = "local_index"
            elif capability.supports_cache_only and cache_hit:
                mode = "cache_only"
            elif capability.supports_remote_api:
                mode = "remote_api"
            elif capability.supports_local_index:
                mode = "local_index"
            else:
                mode = "disabled"
        if mode == "disabled":
            plan.status, plan.execution_mode, plan.reason = "blocked", "disabled", "validation_disabled"
        elif mode == "local_index":
            plan.execution_mode = "local_index"
            if not capability.supports_local_index or not index_path:
                plan.status, plan.reason = "no_index", "configured_local_index_missing"
            else:
                validator = registry.create(route.validator_name)
                binding_valid, binding_warnings, binding_paths = _validate_index_binding(index_path, validator)
                if not binding_valid:
                    plan.status, plan.reason = "no_index", "schema_bound_index_unavailable"
                    plan.warnings.extend(binding_warnings)
                    plans.append(plan)
                    continue
                plan.query_context.update({"index_path": str(index_path), "index_type": index_type, **binding_paths})
                estimate = ValidationLocalIndex(
                    capability.index_name or route.validator_name, route.validator_name,
                    index_type or "", index_path, **binding_paths,
                ).estimate_query(plan)
                plan.estimated_records = estimate.get("estimated_records")
                plan.estimated_memory_mb = estimate.get("estimated_memory_mb")
                plan.estimated_output_bytes = estimate.get("estimated_output_bytes")
                plan.estimated_query_seconds = estimate.get("estimated_query_seconds")
                plan.status, plan.reason = "allowed", "local_index_available"
        elif mode == "cache_only":
            plan.execution_mode = "cache_only"
            if not resource_policy.cache_enabled:
                plan.status, plan.reason = "no_cache", "validation_cache_disabled"
            elif not cache_hit:
                plan.status, plan.reason = "no_cache", "cache_miss_no_scientific_conclusion"
                plan.warnings.append("cache_miss_is_not_no_coverage")
            else:
                plan.status, plan.reason = "allowed", "validation_cache_hit"
                plan.query_context["cache_path"] = str(cache_path)
        elif mode == "remote_api":
            plan.execution_mode = "remote_api"
            if not capability.supports_remote_api:
                plan.status, plan.reason = "provider_not_configured", "validator_has_no_remote_capability"
            elif not (resource_policy.external_validation_enabled and resource_policy.network_enabled):
                plan.status, plan.execution_mode, plan.reason = "blocked", "blocked", "remote_requires_execute_network_external_validation"
            else:
                plan.status, plan.reason = "allowed", "remote_provider_permitted_pending_runtime_configuration"
        else:
            plan.status, plan.execution_mode, plan.reason = "blocked", "blocked", f"unknown_query_mode:{mode}"
        plans.append(plan)
    return enforce_validation_resource_policy(plans, resource_policy)


def write_validation_query_plans(plans: list[ValidationQueryPlan], output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    records = output / "validation_query_plan.jsonl"
    summary = output / "validation_query_plan_summary.json"
    records.write_text("".join(item.model_dump_json() + "\n" for item in plans), encoding="utf-8")
    summary.write_text(json.dumps(summarize_validation_resource_usage(plans), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"plans": str(records), "summary": str(summary)}


__all__ = ["plan_validation_queries", "write_validation_query_plans"]
