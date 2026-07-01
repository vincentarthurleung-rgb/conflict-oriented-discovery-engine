"""Shared parsing, recovery, and run-scoped diagnostics for L1 responses."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.domain.models import PromptProfile


class L1ResponseError(ValueError):
    def __init__(self, error_type: str, message: str, *, raw_response: Any = None, parsed_json_type: str = "unknown"):
        super().__init__(message)
        self.error_type = error_type
        self.raw_response = raw_response
        self.parsed_json_type = parsed_json_type


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def normalize_l1_json_response(value: Any) -> tuple[dict[str, Any], list[str]]:
    """Normalize only explicitly supported response variants; reject everything else."""

    warnings: list[str] = []
    raw = value
    if isinstance(value, str):
        text = value.strip()
        fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
        if fence:
            text = fence.group(1).strip()
            warnings.append("l1_response_markdown_fence_stripped")
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise L1ResponseError("json_parse_failed", str(exc), raw_response=raw, parsed_json_type="string") from exc
    if isinstance(value, list):
        value = {"claims": value}
        warnings.append("l1_response_wrapped_list_as_claims")
    elif not isinstance(value, dict):
        raise L1ResponseError("response_not_object", "L1 response JSON must be an object or claims list", raw_response=raw, parsed_json_type=_type_name(value))
    if "claims" not in value and "causal_tuples" in value:
        value = {**value, "claims": value["causal_tuples"]}
        value.pop("causal_tuples", None)
        warnings.append("legacy_causal_tuples_converted_to_claims")
    if "claims" not in value:
        raise L1ResponseError("missing_claims_root", "L1 response object must contain claims", raw_response=raw, parsed_json_type="dict")
    if not isinstance(value["claims"], list) or any(not isinstance(item, dict) for item in value["claims"]):
        raise L1ResponseError("schema_validation_failed", "claims must be a list of objects", raw_response=raw, parsed_json_type="dict")
    inherited = value.pop("__l1_warnings", [])
    warnings.extend(str(item) for item in inherited)
    return value, list(dict.fromkeys(warnings))


def resolve_l1_prompt_profile(domain_profile: dict[str, Any] | None, pilot_profile: str | None = None) -> PromptProfile:
    """Resolve workflow domain metadata to the registered executable prompt profile."""
    from code_engine.domain.prompt_registry import default_prompt_registry

    metadata = dict(domain_profile or {})
    profile_id = str(metadata.get("prompt_profile_id") or "general_biomedical_l1_v2")
    if pilot_profile == "ketamine":
        profile_id = "neuropharmacology_ketamine_l1_v2_1"
    registry = default_prompt_registry()
    try:
        return registry.get_profile(profile_id)
    except KeyError:
        domain_id = str(metadata.get("domain_id") or "general_biomedical")
        try:
            return registry.get_profile(domain_id)
        except KeyError:
            return registry.get_profile("general_biomedical_l1_v2")


def _redact(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)((?:api[_-]?key|token|secret)\s*[:=]\s*[\"']?)[^\s,\"'}]+", r"\1[REDACTED]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", text)
    return text


def write_l1_diagnostic(
    output_dir: Path | None, *, stage: str, paper_id: str, pmid: Any,
    prompt_metadata: dict[str, Any], raw_response: Any, error_type: str,
    parsed_json_type: str, recoverable: bool, recovery_action: str,
) -> dict[str, Any]:
    record = {
        "stage": stage, "paper_id": paper_id, "pmid": pmid,
        "prompt_profile_id": prompt_metadata.get("prompt_profile_id"),
        "prompt_version": prompt_metadata.get("prompt_version"),
        "compiled_prompt_hash": prompt_metadata.get("compiled_prompt_hash"),
        "error_type": error_type, "parsed_json_type": parsed_json_type,
        "raw_response_excerpt": _redact(raw_response)[:1000],
        "recoverable": recoverable, "recovery_action": recovery_action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw_response_available": raw_response not in (None, ""),
    }
    if output_dir is None:
        record["raw_response_path"] = ""
        return record
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "l1_raw_responses"
    raw_dir.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", paper_id)[:100] or "unknown"
    raw_path = raw_dir / f"{stage}_{safe_id}_{prompt_metadata.get('compiled_prompt_hash', 'unknown')[:12]}.txt"
    raw_path.write_text(_redact(raw_response), encoding="utf-8")
    record["raw_response_path"] = str(raw_path)
    log_name = "l1_parse_warnings.jsonl" if recoverable else "l1_parse_errors.jsonl"
    with (output_dir / log_name).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def classify_l1_exception(exc: Exception) -> str:
    explicit = str(getattr(exc, "error_type", "") or "")
    if explicit:
        return explicit
    message = str(exc).casefold()
    if "timed out" in message or "timeout" in message:
        return "timeout"
    if "json" in message or "claims root" in message:
        return "json_parse_failed"
    return "api_error"


def l1_failure_record(*, stage: str, paper_id: str, paper: dict[str, Any],
                      prompt_metadata: dict[str, Any], exc: Exception) -> dict[str, Any]:
    details = dict(getattr(exc, "details", {}) or {})
    error_type = classify_l1_exception(exc)
    return {
        "stage": stage, "paper_id": paper_id, "pmid": paper.get("pmid"), "title": paper.get("title"),
        "prompt_profile_id": prompt_metadata.get("prompt_profile_id"),
        "prompt_version": prompt_metadata.get("prompt_version"),
        "compiled_prompt_hash": prompt_metadata.get("compiled_prompt_hash"),
        "error_type": error_type, "error_message": str(exc)[:1000],
        "retry_count": max(0, int(getattr(exc, "attempts", details.get("attempts", 1))) - 1),
        "recoverable": True, "continued": True,
        "provider": getattr(exc, "provider", None), "model": getattr(exc, "model", None),
        "timeout_type": getattr(exc, "timeout_type", None),
        "timeout_seconds": getattr(exc, "timeout_seconds", None),
        "max_retries": getattr(exc, "max_retries", None),
        "attempts": getattr(exc, "attempts", details.get("attempts")),
        "prompt_hash": prompt_metadata.get("compiled_prompt_hash"),
        "prompt_chars": prompt_metadata.get("compiled_prompt_chars", 0),
        "raw_response_available": getattr(exc, "raw_response", None) not in (None, ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["L1ResponseError", "classify_l1_exception", "l1_failure_record", "normalize_l1_json_response", "resolve_l1_prompt_profile", "write_l1_diagnostic"]
