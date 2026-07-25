"""Canonical identities used by historical lineage forensics."""
from __future__ import annotations

import json
import unicodedata
from decimal import Decimal
from typing import Any

from ..identities import sha256_bytes, sha256_json, stable_identity

CONTRACT_NAMES = (
    "historical_extraction_asset_inventory", "historical_lineage_binding",
    "source_snapshot_forensic_recovery", "raw_response_forensic_features",
    "historical_parser_replay", "forensic_parsed_payload_comparison",
    "lineage_candidate_graph", "lineage_uniqueness_validator",
    "provider_attempt_lineage_recovery", "extraction_replayability_v2",
    "selective_reextraction_v2", "extraction_record_research_readiness_tier",
    "historical_lineage_forensics_orchestration",
)


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", str(k)): _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, float):
        if not (value == value and abs(value) != float("inf")):
            raise ValueError("non-finite numbers are not canonicalizable")
        return Decimal(str(value))
    return value


def canonical_payload_bytes(value: Any) -> bytes:
    """v1: NFC, ordered object keys, preserved null/unknown keys and list order."""
    normalized = _normalize(value)
    return json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        default=lambda item: format(item, "f") if isinstance(item, Decimal) else str(item),
    ).encode("utf-8")


def canonical_payload_hash(value: Any) -> str:
    return sha256_bytes(canonical_payload_bytes(value))


def forensic_contract_identity(name: str) -> dict[str, Any]:
    if name not in CONTRACT_NAMES:
        raise ValueError(f"unknown forensic contract: {name}")
    version = "v2" if name in {"extraction_replayability_v2", "selective_reextraction_v2"} else "v1"
    public_name = {
        "extraction_replayability_v2": "extraction_replayability",
        "selective_reextraction_v2": "selective_reextraction",
    }.get(name, name)
    canonical_payload = {
        "contract_name": f"{public_name}_contract_identity_{version}",
        "contract_version": version,
        "identity_algorithm": "sha256_canonical_json_v1",
        "authority_policy": "direct_or_deterministic_unique_only",
        "one_to_one_required": True,
        "offline_only": True,
        "historical_mutation_allowed": False,
        "score_is_authority": False,
    }
    digest = sha256_json(canonical_payload)
    return {
        "schema_version": "historical_lineage_forensics_contract_identity_v1",
        "contract_name": canonical_payload["contract_name"],
        "canonical_payload": canonical_payload,
        "identity_sha256": digest,
        "recomputed_sha256": digest,
        "identity_match": True,
    }


def edge_identity(left: str, right: str, evidence: dict[str, Any]) -> str:
    return stable_identity("lineage_candidate_edge_v1", {
        "left_identity": left, "right_identity": right, "evidence": evidence,
    })
