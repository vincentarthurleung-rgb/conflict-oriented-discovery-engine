"""Stable local index for previously completed LLM extraction calls."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from code_engine.common.runtime import ensure_source_allowed, is_legacy_source


DEFAULT_CACHE_INDEX_PATH = Path("data/index/llm_cache_index.json")


def compute_chunk_hash(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def compute_llm_cache_key(
    paper_id: str,
    chunk_hash: str,
    prompt_version: str,
    model_name: str,
    extraction_schema_version: str,
    *,
    domain_id: str = "",
    prompt_profile_id: str = "",
    extraction_policy_version: str = "",
    chunk_id: str = "",
    model_family: str = "",
) -> str:
    components = (
        paper_id, chunk_id, chunk_hash, domain_id, prompt_profile_id, prompt_version,
        extraction_schema_version, extraction_policy_version, model_name, model_family,
    )
    return hashlib.sha256("\x1f".join(str(item) for item in components).encode("utf-8")).hexdigest()


def build_llm_cache_index(
    path: str | Path = DEFAULT_CACHE_INDEX_PATH,
    *,
    extraction_dir: str | Path = "data/processed/l1",
    allow_legacy_source: bool = False,
) -> Dict[str, Any]:
    """Create an index shell and preserve explicitly recorded cache entries."""

    target = Path(path)
    ensure_source_allowed(target, allow_legacy_source=allow_legacy_source)
    existing = _load_index(target)
    index = {
        "schema_version": "llm_cache_index_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "extraction_dir": str(extraction_dir),
        "entries": existing.get("entries", {}),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def _load_index(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"entries": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"entries": {}}


def load_llm_cache_index(
    path: str | Path = DEFAULT_CACHE_INDEX_PATH,
    *,
    allow_legacy_source: bool = False,
) -> Dict[str, Any]:
    """Load cache metadata safely; a missing cache is an explicit empty state."""

    target = Path(path)
    ensure_source_allowed(target, allow_legacy_source=allow_legacy_source)
    if not target.exists():
        return {
            "schema_version": "llm_cache_index_v1",
            "generated_at": None,
            "cache_status": "missing_empty_cache",
            "using_legacy_data": False,
            "entries": {},
            "warnings": ["LLM cache index is unavailable; an empty cache was used."],
        }
    index = _load_index(target)
    index.setdefault("schema_version", "llm_cache_index_v1")
    index.setdefault("entries", {})
    index["cache_status"] = "loaded"
    index["using_legacy_data"] = is_legacy_source(target)
    index.setdefault("warnings", [])
    if index["using_legacy_data"]:
        index["warnings"].append("Explicit legacy LLM cache source is in use.")
    return index


def has_cached_extraction(
    cache_key: str,
    path: str | Path = DEFAULT_CACHE_INDEX_PATH,
    *,
    allow_legacy_source: bool = False,
) -> bool:
    return cache_key in load_llm_cache_index(
        path, allow_legacy_source=allow_legacy_source
    ).get("entries", {})


def record_cached_extraction(
    cache_key: str,
    output_path: str | Path,
    metadata: Dict[str, Any],
    *,
    path: str | Path = DEFAULT_CACHE_INDEX_PATH,
    allow_legacy_source: bool = False,
) -> Dict[str, Any]:
    """Record a completed extraction; this function never invokes an API."""

    target = Path(path)
    ensure_source_allowed(target, allow_legacy_source=allow_legacy_source)
    index = _load_index(target)
    index.setdefault("schema_version", "llm_cache_index_v1")
    index.setdefault("entries", {})[cache_key] = {
        "output_path": str(output_path),
        "metadata": metadata,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index["entries"][cache_key]
