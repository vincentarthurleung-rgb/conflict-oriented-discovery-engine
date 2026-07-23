from __future__ import annotations

import hashlib
import json
import re
from typing import Any

ANCHOR_TOKENIZER_VERSION = "context_attribution_anchor_tokenizer_v1"
EXPLICIT_SPAN_VERSION = "context_attribution_explicit_token_span_v1"
SPAN_HYDRATOR_VERSION = "context_attribution_explicit_span_hydrator_v1"
MAX_EXPLICIT_SPAN_TOKENS = 64
TOKEN_CATALOG_IDENTITY_VERSION = "context_attribution_token_catalog_identity_v1"
TOKEN_OFFSET_SEMANTICS = "unicode_code_point_char_end_exclusive"

_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tokenize_anchor(anchor_id: str, text: str) -> list[dict[str, Any]]:
    """Tokenize with Unicode code-point offsets and exclusive char_end."""
    return [
        {
            "token_id": f"{anchor_id}:T{index}",
            "text": match.group(0),
            "char_start": match.start(),
            "char_end": match.end(),
        }
        for index, match in enumerate(_TOKEN.finditer(text))
    ]


def anchor_token_contract(anchor: dict[str, Any]) -> dict[str, Any]:
    value = dict(anchor)
    anchor_id = str(value.get("anchor_id") or value.get("evidence_span_id") or "")
    text = str(value.get("text") or "")
    digest = text_sha256(text)
    value["anchor_id"] = anchor_id
    value["text_sha256"] = digest
    value["text_hash"] = digest
    value["tokenizer_version"] = ANCHOR_TOKENIZER_VERSION
    value["char_offset_semantics"] = "unicode_code_points_zero_based_end_exclusive"
    value["tokens"] = tokenize_anchor(anchor_id, text)
    return value


def attach_token_catalog(contract: dict[str, Any]) -> dict[str, Any]:
    value = dict(contract)
    anchors = [anchor_token_contract(item) for item in value.get("evidence_anchors") or []]
    value["evidence_anchors"] = anchors
    value["anchor_tokenizer_version"] = ANCHOR_TOKENIZER_VERSION
    value["explicit_span_version"] = EXPLICIT_SPAN_VERSION
    observation_identity = observation_token_catalog_identity(
        str(value.get("observation_id") or ""), anchors
    )
    value["token_catalog_identity_version"] = TOKEN_CATALOG_IDENTITY_VERSION
    value["token_catalog_identity"] = observation_identity["observation_token_catalog_sha256"]
    value["observation_token_catalog_identity"] = observation_identity
    return value


def token_catalog_identity(anchors: list[dict[str, Any]]) -> str:
    entries = [anchor_token_catalog_identity(item) for item in anchors]
    raw = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def anchor_token_catalog_identity(anchor: dict[str, Any]) -> dict[str, Any]:
    anchor_id = str(anchor.get("anchor_id") or anchor.get("evidence_span_id") or "")
    text = str(anchor.get("text") or "")
    tokens = list(anchor.get("tokens") or tokenize_anchor(anchor_id, text))
    token_payload = [
        {
            "token_id": token.get("token_id"),
            "index": index,
            "text": token.get("text"),
            "char_start": token.get("char_start"),
            "char_end": token.get("char_end"),
        }
        for index, token in enumerate(tokens)
    ]
    payload = {
        "anchor_id": anchor_id,
        "anchor_text_sha256": anchor.get("text_sha256") or text_sha256(text),
        "tokenizer_version": anchor.get("tokenizer_version") or ANCHOR_TOKENIZER_VERSION,
        "offset_semantics": TOKEN_OFFSET_SEMANTICS,
        "tokens": token_payload,
    }
    return {
        "anchor_id": anchor_id,
        "anchor_text_sha256": payload["anchor_text_sha256"],
        "tokenizer_version": payload["tokenizer_version"],
        "token_count": len(tokens),
        "token_catalog_sha256": _canonical_sha256(payload),
    }


def observation_token_catalog_identity(
    observation_id: str, anchors: list[dict[str, Any]]
) -> dict[str, Any]:
    ordered = sorted(anchors, key=lambda item: str(item.get("anchor_id") or ""))
    catalog_entries = [anchor_token_catalog_identity(item) for item in ordered]
    anchor_text_entries = [
        {
            "anchor_id": str(item.get("anchor_id") or ""),
            "anchor_text_sha256": item.get("text_sha256")
            or text_sha256(str(item.get("text") or "")),
            "source_section": item.get("source_section") or item.get("section"),
            "source_role": item.get("source_role"),
            "char_start": item.get("char_start"),
            "char_end": item.get("char_end"),
        }
        for item in ordered
    ]
    return {
        "identity_version": TOKEN_CATALOG_IDENTITY_VERSION,
        "observation_id": observation_id,
        "anchor_catalog_entries": catalog_entries,
        "observation_token_catalog_sha256": _canonical_sha256({
            "identity_version": TOKEN_CATALOG_IDENTITY_VERSION,
            "observation_id": observation_id,
            "anchor_catalog_entries": catalog_entries,
        }),
        "observation_anchor_text_identity_sha256": _canonical_sha256({
            "identity_version": TOKEN_CATALOG_IDENTITY_VERSION,
            "observation_id": observation_id,
            "anchor_text_entries": anchor_text_entries,
        }),
        "anchor_count": len(ordered),
        "token_count": sum(item["token_count"] for item in catalog_entries),
    }


def selected_token_catalog_identity(
    contracts: dict[str, dict[str, Any]], selected_observation_ids: list[str]
) -> dict[str, Any]:
    entries = []
    for observation_id in sorted(selected_observation_ids):
        identity = contracts[observation_id]["observation_token_catalog_identity"]
        entries.append({
            "observation_id": observation_id,
            "observation_token_catalog_sha256":
                identity["observation_token_catalog_sha256"],
            "observation_anchor_text_identity_sha256":
                identity["observation_anchor_text_identity_sha256"],
            "anchor_count": identity["anchor_count"],
            "token_count": identity["token_count"],
        })
    return {
        "token_catalog_identity_version": TOKEN_CATALOG_IDENTITY_VERSION,
        "selected_token_catalog_identity_sha256": _canonical_sha256({
            "identity_version": TOKEN_CATALOG_IDENTITY_VERSION,
            "selected_observation_token_catalog_identities": [
                {
                    "observation_id": item["observation_id"],
                    "observation_token_catalog_sha256":
                        item["observation_token_catalog_sha256"],
                }
                for item in entries
            ],
        }),
        "selected_anchor_text_identity_sha256": _canonical_sha256({
            "identity_version": TOKEN_CATALOG_IDENTITY_VERSION,
            "selected_observation_anchor_text_identities": [
                {
                    "observation_id": item["observation_id"],
                    "observation_anchor_text_identity_sha256":
                        item["observation_anchor_text_identity_sha256"],
                }
                for item in entries
            ],
        }),
        "selected_observation_token_catalog_identities": entries,
    }


def validate_selected_token_catalog_identity(
    aggregate: dict[str, Any], contracts: dict[str, dict[str, Any]],
    selected_observation_ids: list[str],
) -> list[str]:
    errors: list[str] = []
    expected = selected_token_catalog_identity(contracts, selected_observation_ids)
    if aggregate != expected:
        errors.append("selected_token_catalog_aggregate_mismatch")
    entries = aggregate.get("selected_observation_token_catalog_identities") or []
    if len(entries) != len(selected_observation_ids):
        errors.append("selected_token_catalog_identity_count_mismatch")
    for observation_id in selected_observation_ids:
        contract = contracts.get(observation_id) or {}
        identity = contract.get("observation_token_catalog_identity") or {}
        if not identity.get("observation_anchor_text_identity_sha256"):
            errors.append(f"observation_anchor_text_identity_missing:{observation_id}")
        if contract.get("anchor_tokenizer_version") != ANCHOR_TOKENIZER_VERSION:
            errors.append(f"token_catalog_tokenizer_version_mismatch:{observation_id}")
        for anchor in contract.get("evidence_anchors") or []:
            if anchor.get("text_sha256") != text_sha256(str(anchor.get("text") or "")):
                errors.append(f"token_catalog_anchor_text_hash_mismatch:{observation_id}")
    return errors


def resolve_explicit_span(
    span: Any, anchors: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any] | None, str | None]:
    anchor_id = str(getattr(span, "evidence_anchor_id", "") or "")
    start_id = str(getattr(span, "start_token_id", "") or "")
    end_id = str(getattr(span, "end_token_id", "") or "")
    anchor = anchors.get(anchor_id)
    if anchor is None:
        return None, "explicit_span_anchor_not_in_observation"
    if anchor.get("tokenizer_version") != ANCHOR_TOKENIZER_VERSION:
        return None, "explicit_span_tokenizer_version_mismatch"
    text = str(anchor.get("text") or "")
    if anchor.get("text_sha256") != text_sha256(text):
        return None, "explicit_span_anchor_hash_mismatch"
    tokens = list(anchor.get("tokens") or [])
    by_id = {str(token.get("token_id")): (index, token) for index, token in enumerate(tokens)}
    if start_id not in by_id:
        return None, "explicit_span_unknown_start_token"
    if end_id not in by_id:
        return None, "explicit_span_unknown_end_token"
    start_index, start = by_id[start_id]
    end_index, end = by_id[end_id]
    if start_index > end_index:
        return None, "explicit_span_reversed"
    if end_index - start_index + 1 > MAX_EXPLICIT_SPAN_TOKENS:
        return None, "explicit_span_too_wide"
    previous_end = None
    for token in tokens:
        begin, finish = token.get("char_start"), token.get("char_end")
        if not isinstance(begin, int) or not isinstance(finish, int):
            return None, "explicit_span_invalid_token_offsets"
        if begin < 0 or finish <= begin or finish > len(text):
            return None, "explicit_span_token_out_of_bounds"
        if previous_end is not None and begin < previous_end:
            return None, "explicit_span_overlapping_token_offsets"
        previous_end = finish
    char_start, char_end = start["char_start"], end["char_end"]
    surface = text[char_start:char_end]
    if not surface:
        return None, "explicit_span_empty_surface"
    return {
        "evidence_anchor_id": anchor_id,
        "start_token_id": start_id,
        "end_token_id": end_id,
        "start_token_index": start_index,
        "end_token_index": end_index,
        "char_start": char_start,
        "char_end": char_end,
        "raw_value": surface,
        "raw_value_source": "explicit_token_span",
        "anchor_text_sha256": anchor["text_sha256"],
        "tokenizer_version": ANCHOR_TOKENIZER_VERSION,
        "explicit_span_version": EXPLICIT_SPAN_VERSION,
        "span_hydrator_version": SPAN_HYDRATOR_VERSION,
    }, None


__all__ = [
    "ANCHOR_TOKENIZER_VERSION", "EXPLICIT_SPAN_VERSION", "MAX_EXPLICIT_SPAN_TOKENS",
    "SPAN_HYDRATOR_VERSION", "TOKEN_CATALOG_IDENTITY_VERSION",
    "anchor_token_catalog_identity", "anchor_token_contract", "attach_token_catalog",
    "observation_token_catalog_identity", "resolve_explicit_span",
    "selected_token_catalog_identity", "text_sha256", "token_catalog_identity",
    "tokenize_anchor", "validate_selected_token_catalog_identity",
]
