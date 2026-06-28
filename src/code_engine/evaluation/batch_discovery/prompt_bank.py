"""JSONL prompt-bank loading and stable manifest generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_prompt_bank(path: str | Path, max_prompts: int | None = None) -> list[dict[str, Any]]:
    source = Path(path)
    records = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        item = json.loads(line)
        query = str(item.get("query") or item.get("prompt") or "").strip()
        if not query:
            raise ValueError(f"Prompt bank line {line_number} has no query/prompt")
        item["query"] = query
        item.setdefault("prompt_id", hashlib.sha256(query.encode()).hexdigest()[:16])
        records.append(item)
        if max_prompts is not None and len(records) >= max_prompts:
            break
    return records


def build_prompt_bank_manifest(records: list[dict[str, Any]], source: str | Path) -> dict[str, Any]:
    return {
        "source": str(source),
        "prompt_count": len(records),
        "prompt_ids": [str(item["prompt_id"]) for item in records],
        "content_hash": hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
    }


__all__ = ["load_prompt_bank", "build_prompt_bank_manifest"]
