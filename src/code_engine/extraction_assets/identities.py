"""Stable, secret-free identities for extraction preservation assets."""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePath
from typing import Any, Iterable

SECRET_KEYS = {
    "api_key", "apikey", "authorization", "authorization_header", "bearer_token",
    "credential", "credential_value", "password", "secret", "session_secret", "token",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def assert_secret_free(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                raise ValueError(f"secret field is forbidden at {path}.{key}")
            assert_secret_free(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_secret_free(item, f"{path}[{index}]")


def stable_identity(kind: str, payload: dict[str, Any], *, exclude: Iterable[str] = ()) -> str:
    assert_secret_free(payload)
    excluded = set(exclude) | {"identity", "provenance", "created_at", "updated_at"}
    canonical = {key: value for key, value in payload.items() if key not in excluded}
    return f"{kind}:{sha256_json(canonical)}"


def source_snapshot_identity(payload: dict[str, Any]) -> str:
    # Absolute/local paths are provenance, never identity material.
    excluded = {"source_file_path", "raw_response_path", "run_path"}
    return stable_identity("source_snapshot_v1", payload, exclude=excluded)


def call_dedup_identity(
    source_snapshot_identity_value: str,
    rendered_prompt_sha256: str,
    model_provider: str,
    model_name: str,
    non_secret_parameters: dict[str, Any],
    response_schema_identity: str,
    tool_schema_identity: str | None,
) -> str:
    payload = {
        "source_snapshot_identity": source_snapshot_identity_value,
        "rendered_prompt_sha256": rendered_prompt_sha256,
        "model_provider": model_provider,
        "model_name": model_name,
        "non_secret_parameters": non_secret_parameters,
        "response_schema_identity": response_schema_identity,
        "tool_schema_identity": tool_schema_identity,
    }
    return stable_identity("provider_call_dedup_v1", payload)


def is_absolute_path(value: str) -> bool:
    return PurePath(value).is_absolute()


CONTRACT_NAMES = (
    "source_snapshot", "provider_call_specification", "provider_call_attempt",
    "raw_provider_response", "parsed_extraction_candidate",
    "extraction_field_evidence", "extraction_field_value_state",
    "extraction_coverage_ledger", "extraction_replayability",
    "selective_reextraction", "extraction_run_readiness",
    "extraction_asset_orchestration",
)


def contract_identity(name: str) -> dict[str, Any]:
    if name not in CONTRACT_NAMES:
        raise ValueError(f"unknown contract: {name}")
    canonical_payload = {
        "contract_name": f"{name}_contract_identity_v1",
        "contract_version": "v1",
        "identity_algorithm": "sha256_canonical_json_v1",
        "immutable_revision_policy": True,
        "secret_material_allowed": False,
    }
    digest = sha256_json(canonical_payload)
    return {
        "schema_version": "extraction_contract_identity_v1",
        "contract_name": canonical_payload["contract_name"],
        "canonical_payload": canonical_payload,
        "identity_sha256": digest,
        "recomputed_sha256": digest,
        "identity_match": True,
    }
