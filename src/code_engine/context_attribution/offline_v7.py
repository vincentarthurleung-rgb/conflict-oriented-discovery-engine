from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .code_provenance import build_code_provenance
from .comparison_adapter import adapt_pair_v2_to_v3
from .composition import composition_identity
from .identities import canonical_sha256
from .inference_rules import (
    INFERENCE_RULE_DERIVER_VERSION, V6_TO_V7_ADAPTER_VERSION,
    adapt_v6_to_v7, materialize_internal_v5,
)
from .models import ContextExtraction
from .recovery import _contracts
from .registry import load_registry, resolve_registry
from .validation import (
    PAIR_VALIDATOR_VERSION_V3, VALIDATOR_VERSION_V6,
    validate_context_extraction_v6, validate_pair_attribution_v3,
)

OFFLINE_PLAN_VERSION = "context_attribution_v7_offline_revalidation_plan_v1"
OFFLINE_SUMMARY_VERSION = "context_attribution_recovery_execution_summary_v2"
EXTRACTION_ALLOWLIST = {
    "ftl1v3_17b7314297cabac677007b35",
    "ftl1v3_41f0090d726e6e8591a58574",
}
COMPARISON_ALLOWLIST = {"weak-ebd5deb14f4f39dfffe6"}


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def build_offline_plan(
    *, repository_root: Path, input_run: Path, source_run: Path,
    output_run: Path, profiles: list[str],
) -> dict[str, Any]:
    calls_path = source_run / "artifacts/context_attribution_provider_calls.jsonl"
    summary_path = source_run / "artifacts/context_attribution_summary.json"
    rows = _rows(calls_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    recovery_source = Path(summary.get("source_run") or "")
    recovery_source_plan_path = (
        recovery_source / "artifacts/context_attribution_plan.json"
    )
    recovery_source_plan = (
        json.loads(recovery_source_plan_path.read_text(encoding="utf-8"))
        if recovery_source_plan_path.is_file() else {}
    )
    registry_identity = resolve_registry().to_dict()
    composition = composition_identity()
    contracts = _contracts(input_run, profiles)
    ids = {str(x.get("record_id")) for x in rows}
    expected = EXTRACTION_ALLOWLIST | COMPARISON_ALLOWLIST
    errors = []
    if source_run.resolve() == output_run.resolve():
        errors.append("source_output_run_collision")
    if summary.get("provider_mode") != "production":
        errors.append("source_summary_not_production")
    if len(rows) != 3 or ids != expected:
        errors.append("source_provider_rows_not_exact_allowlist")
    if not recovery_source_plan:
        errors.append("recovery_source_identity_plan_missing")
    for key, current in (
        ("registry_version", registry_identity["registry_version"]),
        ("registry_content_sha256", registry_identity["registry_content_sha256"]),
        ("composition_policy_version", composition["composition_policy_version"]),
        ("composition_policy_content_sha256",
         composition["composition_policy_content_sha256"]),
        ("normalization_policy_version", "context_normalization_policy_v3"),
        ("comparator_normalization_policy_version",
         "context_comparator_normalization_v1"),
    ):
        if recovery_source_plan.get(key) != current:
            errors.append(f"scientific_policy_identity_drift:{key}")
    source_records = []
    for row in rows:
        parsed = row.get("parsed_payload")
        request_identity = row.get("request_identity")
        execution_identity = row.get("provider_execution_identity")
        if not isinstance(parsed, dict):
            errors.append(f"parsed_payload_missing:{row.get('record_id')}")
        if not request_identity:
            errors.append(f"request_identity_missing:{row.get('record_id')}")
        if not isinstance(execution_identity, dict):
            errors.append(f"provider_execution_identity_missing:{row.get('record_id')}")
        if row.get("call_type") == "extraction" and row.get("record_id") in contracts:
            contract = contracts[str(row["record_id"])]
            if row.get("token_catalog_identity") != contract.get("token_catalog_identity"):
                errors.append(f"token_catalog_identity_drift:{row.get('record_id')}")
            expected_anchor = (
                contract.get("observation_token_catalog_identity") or {}
            ).get("observation_anchor_text_identity_sha256")
            if row.get("anchor_text_identity") != expected_anchor:
                errors.append(f"anchor_text_identity_drift:{row.get('record_id')}")
        source_records.append({
            "call_id": row.get("record_id"),
            "call_type": row.get("call_type"),
            "source_artifact": "artifacts/context_attribution_provider_calls.jsonl",
            "source_provider_row_id": row.get("recovery_attempt_id"),
            "source_request_identity": request_identity,
            "source_provider_execution_identity": execution_identity,
            "source_parsed_payload_sha256": (
                canonical_sha256(parsed) if isinstance(parsed, dict) else None
            ),
            "source_schema_version": (
                parsed.get("schema_version") if isinstance(parsed, dict) else None
            ),
            "source_raw_response_available": False,
            "source_transport_provenance_complete": False,
            "source_payload_provenance_level": "parsed_payload_only",
            "offline_replay_reusable": bool(
                isinstance(parsed, dict) and request_identity and execution_identity
            ),
            "production_transport_reusable": False,
        })
    code = build_code_provenance(
        repository_root,
        execution_entrypoint="code_engine.context_attribution.offline_v7.execute_offline_v7",
    )
    plan = {
        "schema_version": OFFLINE_PLAN_VERSION,
        "source_run": source_run.as_posix(),
        "input_run": input_run.as_posix(),
        "output_run": output_run.as_posix(),
        "extraction_call_allowlist": sorted(EXTRACTION_ALLOWLIST),
        "comparison_call_allowlist": sorted(COMPARISON_ALLOWLIST),
        "extraction_prompt_version": "context_attribution_prompts_v7",
        "comparison_prompt_version": "context_pair_attribution_prompts_v3",
        "extraction_schema_version": "observation_context_extraction_v7",
        "comparison_schema_version": "context_pair_attribution_v3",
        "extraction_validator_version": VALIDATOR_VERSION_V6,
        "comparison_validator_version": PAIR_VALIDATOR_VERSION_V3,
        "inference_rule_deriver_version": INFERENCE_RULE_DERIVER_VERSION,
        "extraction_adapter_version": V6_TO_V7_ADAPTER_VERSION,
        "comparison_adapter_version":
            "context_pair_attribution_v2_to_v3_missing_value_adapter_v1",
        "source_records": source_records,
        "registry_identity": registry_identity,
        "composition_identity": composition,
        "normalization_policy_version": "context_normalization_policy_v3",
        "comparator_normalization_policy_version":
            "context_comparator_normalization_v1",
        "provider_client_permitted": False,
        "credential_read_permitted": False,
        "network_permitted": False,
        "activation_permitted": False,
        "code_provenance": code,
        "validation_errors": errors,
        "valid": not errors,
    }
    identity_payload = {k: v for k, v in plan.items() if k not in {
        "source_run", "input_run", "output_run", "validation_errors", "valid",
    }}
    plan["identity_sha256"] = canonical_sha256(identity_payload)
    return plan


def execute_offline_v7(
    *, repository_root: Path, input_run: Path, source_run: Path,
    output_run: Path, profiles: list[str],
) -> dict[str, Any]:
    if output_run.exists() and any(output_run.iterdir()):
        raise FileExistsError(f"offline_output_not_empty:{output_run}")
    plan = build_offline_plan(
        repository_root=repository_root, input_run=input_run,
        source_run=source_run, output_run=output_run, profiles=profiles,
    )
    if not plan["valid"]:
        raise RuntimeError("offline_plan_rejected:" + ",".join(plan["validation_errors"]))
    artifacts = output_run / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    _atomic_json(artifacts / "context_attribution_offline_revalidation_plan.json", plan)
    source_rows = _rows(source_run / "artifacts/context_attribution_provider_calls.jsonl")
    by_id = {str(x["record_id"]): x for x in source_rows}
    contracts = _contracts(input_run, profiles)
    registry = load_registry()

    reused = _rows(source_run / "artifacts/observation_context_extractions.jsonl")
    validated: dict[str, ContextExtraction] = {}
    extraction_rows: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    adapters: list[dict[str, Any]] = []
    for raw in reused:
        internal_raw = deepcopy(raw)
        if internal_raw.get("schema_version") in {
            "observation_context_extraction_v6", "observation_context_extraction_v7"
        }:
            internal_raw["schema_version"] = "observation_context_extraction_v5"
        value = ContextExtraction.model_validate(internal_raw)
        if value.validation_status != "validated":
            continue
        validated[value.observation_id] = value
        extraction_rows.append(deepcopy(raw))
        audits.append({
            "record_type": "extraction", "record_id": value.observation_id,
            "valid": True, "source": (
                "offline_validated_reuse" if value.observation_id.startswith("ftl1v3_710")
                else "source_validated_reuse"
            ),
        })
    for oid in sorted(EXTRACTION_ALLOWLIST):
        row = by_id[oid]
        source_payload = row["parsed_payload"]
        if canonical_sha256(source_payload) != next(
            x["source_parsed_payload_sha256"] for x in plan["source_records"]
            if x["call_id"] == oid
        ):
            raise RuntimeError(f"source_payload_hash_drift:{oid}")
        adapted, adapter = adapt_v6_to_v7(
            source_payload, contracts[oid], profiles, registry=registry
        )
        if adapter["valid"]:
            internal = materialize_internal_v5(adapted, adapter)
            value, errors = validate_context_extraction_v6(
                internal, contracts[oid], profiles, registry=registry
            )
        else:
            value = None
            errors = list(adapter["errors"])
        identity = canonical_sha256({
            "provenance": "offline_revalidated_from_paid_parsed_payload",
            "source_payload_sha256": adapter["source_payload_sha256"],
            "schema_version": "observation_context_extraction_v7",
            "validator_version": VALIDATOR_VERSION_V6,
            "adapter_version": V6_TO_V7_ADAPTER_VERSION,
            "token_catalog_identity": contracts[oid].get("token_catalog_identity"),
        })
        dumped = None
        if value is not None:
            value.extraction_identity = identity
            dumped = value.model_dump(mode="json")
            dumped["schema_version"] = "observation_context_extraction_v7"
            dumped["provenance"] = {
                **dumped.get("provenance", {}),
                "source_kind": "offline_revalidated_from_paid_parsed_payload",
                "source_transport_provenance_complete": False,
                "source_payload_provenance_level": "parsed_payload_only",
                "adapter_audit": adapter,
            }
        if not errors:
            assert value is not None and dumped is not None
            validated[oid] = value
            extraction_rows.append(dumped)
        adapters.append({
            "record_id": oid, "source_run": source_run.as_posix(),
            "source_artifact_path": "artifacts/context_attribution_provider_calls.jsonl",
            "source_provider_row_id": row.get("recovery_attempt_id"),
            "source_request_identity": row.get("request_identity"),
            "source_provider_execution_identity": row.get("provider_execution_identity"),
            "source_raw_response_available": False,
            "source_transport_provenance_complete": False,
            "source_payload_provenance_level": "parsed_payload_only",
            **adapter,
        })
        audits.append({
            "record_type": "extraction", "record_id": oid,
            "valid": not errors, "errors": errors,
            "source": "offline_revalidated_from_paid_parsed_payload",
            "schema_version": "observation_context_extraction_v7",
            "validator_version": VALIDATOR_VERSION_V6,
            "failure_layer": None if not errors else (
                "deterministic_validation" if adapter["valid"] else "rule_derivation"
            ),
        })

    pid = next(iter(COMPARISON_ALLOWLIST))
    comparison_source = by_id[pid]["parsed_payload"]
    a = comparison_source["claim_a_observation_id"]
    b = comparison_source["claim_b_observation_id"]
    comparison_rows: list[dict[str, Any]] = []
    comparison_schema_rejections = 0
    if a in validated and b in validated:
        try:
            adapted_pair, pair_adapter = adapt_pair_v2_to_v3(comparison_source)
            pair, pair_errors = validate_pair_attribution_v3(
                adapted_pair, pair_id=pid, extraction_a=validated[a],
                extraction_b=validated[b], profiles=profiles, registry=registry,
            )
            pair.comparison_identity = canonical_sha256({
                "source_payload_sha256": pair_adapter["source_payload_sha256"],
                "adapter_version": pair_adapter["adapter_version"],
                "validator_version": PAIR_VALIDATOR_VERSION_V3,
            })
            dumped_pair = pair.model_dump(mode="json")
            if not pair_errors:
                comparison_rows.append(dumped_pair)
            adapters.append({
                "record_id": pid, "source_run": source_run.as_posix(),
                "source_artifact_path": "artifacts/context_attribution_provider_calls.jsonl",
                "source_request_identity": by_id[pid].get("request_identity"),
                "source_provider_execution_identity":
                    by_id[pid].get("provider_execution_identity"),
                "source_raw_response_available": False,
                "source_transport_provenance_complete": False,
                "source_payload_provenance_level": "parsed_payload_only",
                **pair_adapter,
            })
            audits.append({
                "record_type": "comparison", "record_id": pid,
                "valid": not pair_errors, "errors": pair_errors,
                "source": "offline_revalidated_from_paid_parsed_payload",
                "schema_version": "context_pair_attribution_v3",
                "validator_version": PAIR_VALIDATOR_VERSION_V3,
            })
        except Exception as exc:
            comparison_schema_rejections = 1
            audits.append({
                "record_type": "comparison", "record_id": pid, "valid": False,
                "errors": [str(exc)], "failure_layer": "schema",
                "source": "offline_revalidated_from_paid_parsed_payload",
            })
    else:
        audits.append({
            "record_type": "comparison", "record_id": pid, "valid": False,
            "errors": ["endpoint_not_validated"], "failure_layer": "readiness",
        })
    extraction_rejections = sum(
        x["record_type"] == "extraction" and not x["valid"] for x in audits
    )
    provider_artifact = artifacts / "context_attribution_provider_calls.jsonl"
    _atomic_jsonl(provider_artifact, [])
    _atomic_jsonl(artifacts / "observation_context_extractions.jsonl", extraction_rows)
    _atomic_jsonl(artifacts / "context_pair_attributions.jsonl", comparison_rows)
    _atomic_jsonl(artifacts / "context_attribution_validation_audit.jsonl", audits)
    _atomic_jsonl(artifacts / "context_attribution_adapter_audit.jsonl", adapters)
    _atomic_jsonl(artifacts / "context_attribution_execution_ledger.jsonl", [
        {
            "call_type": x["record_type"], "record_id": x["record_id"],
            "status": "validated" if x["valid"] else "rejected",
            "provider_call": False,
        } for x in audits
    ])
    summary = {
        "schema_version": OFFLINE_SUMMARY_VERSION,
        "execution_status": "completed",
        "provenance": "offline_revalidated_from_paid_parsed_payload",
        "source_run": source_run.as_posix(),
        "input_run": input_run.as_posix(),
        "provider_calls": 0, "extraction_provider_calls": 0,
        "comparison_provider_calls": 0, "api_calls": 0, "real_api_calls": 0,
        "network_call_attempt_count": 0, "network_calls": 0,
        "provider_client_created": False,
        "provider_call_artifact_created": (
            provider_artifact.is_file() and provider_artifact.stat().st_size > 0
        ),
        "provider_call_artifact_record_count": 0,
        "credential_values_read": False, "credential_values_logged": False,
        "credential_values_persisted": False, "credential_source_names": [],
        "raw_response_record_count": 0, "complete_provider_artifact_count": 0,
        "source_transport_provenance_complete": False,
        "source_payload_provenance_level": "parsed_payload_only",
        "reused_validated_extraction_count": len(reused),
        "offline_target_extraction_count": len(EXTRACTION_ALLOWLIST),
        "validated_extraction_count": len(extraction_rows),
        "rejected_extraction_count": extraction_rejections,
        "validated_pair_count": len(comparison_rows),
        "comparison_schema_rejection_count": comparison_schema_rejections,
        "handoff_created": False, "activation": False,
        "active_pointer_unchanged": True, "variational_em_called": False,
        "code_provenance": plan["code_provenance"],
        "code_provenance_identity_sha256":
            plan["code_provenance"]["identity_sha256"],
        "offline_plan_identity_sha256": plan["identity_sha256"],
    }
    _atomic_json(artifacts / "context_attribution_summary.json", summary)
    return summary
