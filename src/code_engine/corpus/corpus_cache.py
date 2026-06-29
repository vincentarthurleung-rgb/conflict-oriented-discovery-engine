"""Stable content fingerprints for incremental corpus processing."""

from __future__ import annotations
import hashlib
import json
import re

from code_engine.corpus.models import PaperRegistryRecord


def compute_text_hash(text: str | None) -> str | None:
    if not text or not str(text).strip():
        return None
    normalized = re.sub(r"\s+", " ", str(text)).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def compute_sections_hash(sections: list[dict] | None) -> str | None:
    if not sections:
        return None
    normalized = [{"order": index, "title": str(item.get("title") or item.get("section_title") or "").strip(), "text": re.sub(r"\s+", " ", str(item.get("text") or item.get("content") or "")).strip()} for index, item in enumerate(sections)]
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def build_content_fingerprint(paper_record: PaperRegistryRecord, source_scope: str) -> str:
    if source_scope == "abstract":
        content = paper_record.abstract_hash
    elif source_scope in {"full_text", "section", "span"}:
        content = paper_record.fulltext_hash or paper_record.sections_hash
    else:
        content = paper_record.abstract_hash or paper_record.fulltext_hash or paper_record.sections_hash
    raw = f"{paper_record.canonical_paper_id}|{source_scope}|{content or 'missing'}"
    return hashlib.sha256(raw.encode()).hexdigest()


__all__ = ["compute_text_hash", "compute_sections_hash", "build_content_fingerprint"]
