"""Bounded JSON extraction and optional format-only repair."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object(response: Any) -> dict[str, Any] | None:
    if isinstance(response, dict):
        return response
    text = str(response or "").strip()
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None


def repair_json_response(response: Any, *, client: Any | None = None, execute: bool = False, api: bool = False) -> tuple[dict[str, Any] | None, int, list[str]]:
    extracted = extract_json_object(response)
    if extracted is not None:
        return extracted, 0, []
    if not (execute and api and client is not None):
        return None, 0, ["semantic_intake_json_extraction_failed"]
    try:
        repaired = client.extract_json("Repair JSON syntax only. Do not add, remove, or reinterpret semantic content. Return JSON only.\n" + str(response))
    except Exception as exc:
        return None, 1, [f"semantic_intake_json_repair_failed:{type(exc).__name__}"]
    extracted = extract_json_object(repaired)
    return extracted, 1, ([] if extracted is not None else ["semantic_intake_json_repair_failed"])
