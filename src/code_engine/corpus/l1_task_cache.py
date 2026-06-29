"""Task-family-aware L1 cache independent of raw prompt strings."""

from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field
from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl, iter_jsonl
from code_engine.schemas.models import CODEBaseModel


class L1TaskSignature(CODEBaseModel):
    task_family: str
    source_scope: str
    canonical_paper_id: str
    content_hash: str
    schema_version: str
    prompt_profile_id: str | None = None
    prompt_fingerprint: str | None = None
    model_name: str | None = None
    domain_id: str | None = None
    l1_mode: str | None = None


class L1TaskCacheRecord(CODEBaseModel):
    task_cache_key: str
    signature: L1TaskSignature
    status: str = "miss"
    artifact_refs: dict = Field(default_factory=dict)
    claim_count: int = 0
    evidence_count: int = 0
    created_at: str
    updated_at: str
    run_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def build_l1_task_cache_key(signature: L1TaskSignature) -> str:
    payload = signature.model_dump(mode="json")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _compatible(left: L1TaskSignature, right: L1TaskSignature) -> bool:
    return all(getattr(left, key) == getattr(right, key) for key in ("task_family", "source_scope", "canonical_paper_id", "content_hash", "schema_version", "domain_id", "l1_mode"))


def lookup_l1_task_cache(signature: L1TaskSignature, cache_dir: Path) -> L1TaskCacheRecord | None:
    exact_key = build_l1_task_cache_key(signature)
    compatible = None
    incompatible = None
    for payload in iter_jsonl(Path(cache_dir) / "l1_task_cache.jsonl"):
        record = L1TaskCacheRecord.model_validate(payload)
        if record.task_cache_key == exact_key:
            result = record.model_copy(deep=True)
            result.status = "hit" if record.status in {"stored", "hit", "completed", "compatible_task_family_hit"} else record.status
            return result
        if record.signature.canonical_paper_id == signature.canonical_paper_id and record.signature.task_family == signature.task_family:
            if record.signature.content_hash != signature.content_hash:
                continue
            if record.signature.schema_version != signature.schema_version:
                incompatible = record.model_copy(deep=True)
                incompatible.status = "incompatible_schema"
                incompatible.warnings = list(dict.fromkeys([*incompatible.warnings, "schema_version_mismatch"]))
                continue
            if _compatible(record.signature, signature):
                compatible = record.model_copy(deep=True)
    if compatible:
        compatible.status = "compatible_task_family_hit"
        compatible.warnings = list(dict.fromkeys([*compatible.warnings, "prompt_or_model_signature_differs"] ))
    return compatible or incompatible


def store_l1_task_cache_record(record: L1TaskCacheRecord, cache_dir: Path) -> None:
    directory = Path(cache_dir)
    records = {item["task_cache_key"]: item for item in iter_jsonl(directory / "l1_task_cache.jsonl")}
    records[record.task_cache_key] = record.model_dump(mode="json")
    atomic_write_jsonl(directory / "l1_task_cache.jsonl", (records[key] for key in sorted(records)))
    atomic_write_json(directory / "l1_task_cache_summary.json", {"task_count": len(records), "status_counts": _counts(records.values())})


def _counts(records) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in records:
        status = str(item.get("status") or "unknown")
        result[status] = result.get(status, 0) + 1
    return result


class L1TaskCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)

    def lookup(self, signature: L1TaskSignature) -> L1TaskCacheRecord | None:
        return lookup_l1_task_cache(signature, self.cache_dir)

    def store(self, record: L1TaskCacheRecord) -> None:
        store_l1_task_cache_record(record, self.cache_dir)

    @staticmethod
    def new_record(signature: L1TaskSignature, run_id: str, artifact_refs: dict, *, claim_count: int = 0, evidence_count: int = 0) -> L1TaskCacheRecord:
        now = datetime.now(timezone.utc).isoformat()
        return L1TaskCacheRecord(task_cache_key=build_l1_task_cache_key(signature), signature=signature, status="stored", artifact_refs=artifact_refs, claim_count=claim_count, evidence_count=evidence_count, created_at=now, updated_at=now, run_ids=[run_id])


__all__ = ["L1TaskSignature", "L1TaskCacheRecord", "L1TaskCache", "build_l1_task_cache_key", "lookup_l1_task_cache", "store_l1_task_cache_record"]
