"""Read-only raw feature extraction and historical-parser replay helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ..identities import sha256_bytes
from .identities import canonical_payload_hash


def extract_raw_features(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
        status, error = "valid", None
    except Exception as exc:
        payload, status, error = None, "invalid", type(exc).__name__
    ids = _ids(payload) if isinstance(payload, dict) else {}
    content = _assistant_content(payload)
    return {
        "raw_sha256": sha256_bytes(raw), "byte_count": len(raw), "json_parse_status": status,
        "json_parse_error": error, "top_level_keys": sorted(payload) if isinstance(payload, dict) else [],
        "provider_request_id": ids.get("request_id"), "provider_response_id": ids.get("response_id"),
        "model": ids.get("model"), "finish_reason": ids.get("finish_reason"),
        "usage": ids.get("usage") or {}, "created_timestamp": ids.get("created"),
        "assistant_content": content, "assistant_content_hash": sha256_bytes(content.encode()) if content else None,
        "canonical_json_hash": canonical_payload_hash(payload) if payload is not None else None,
        "tool_arguments_hash": None, "embedded_block_ids": [], "embedded_observation_ids": [],
        "truncation_indicators": [], "immutable_input": True,
    }


def replay_parser(raw: bytes, parser: Callable[[Any], Any], *, parser_name: str,
                  parser_version: str, historical: bool) -> dict[str, Any]:
    raw_hash = sha256_bytes(raw)
    try:
        decoded = json.loads(raw)
        result = parser(decoded)
        return {
            "input_raw_sha256": raw_hash, "parser_name": parser_name, "parser_version": parser_version,
            "historical_parser_available": historical, "authoritative_replay_eligible": historical,
            "parse_status": "parsed", "parse_result": result,
            "canonical_payload_hash": canonical_payload_hash(result), "warnings": [], "errors": [],
            "schema_validation_status": "not_assessed",
        }
    except Exception as exc:
        return {
            "input_raw_sha256": raw_hash, "parser_name": parser_name, "parser_version": parser_version,
            "historical_parser_available": historical, "authoritative_replay_eligible": False,
            "parse_status": "parse_failed", "parse_result": None, "canonical_payload_hash": None,
            "warnings": [], "errors": [f"{type(exc).__name__}:{exc}"],
            "schema_validation_status": "invalid_or_unavailable",
        }


def _ids(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices") or [{}]
    first = choices[0] if isinstance(choices, list) and choices else {}
    return {
        "request_id": payload.get("request_id"), "response_id": payload.get("id"),
        "model": payload.get("model"), "created": payload.get("created"), "usage": payload.get("usage"),
        "finish_reason": first.get("finish_reason") if isinstance(first, dict) else None,
    }


def _assistant_content(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    raw = payload.get("__json_raw_response")
    return raw if isinstance(raw, str) else None

