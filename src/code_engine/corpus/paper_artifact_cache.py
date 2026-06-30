"""Fingerprint-strict, paper-level artifact reuse with mandatory copy-in."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pydantic import Field

from code_engine.corpus.io import atomic_write_jsonl, iter_jsonl
from code_engine.schemas.models import CODEBaseModel


DEFAULT_PAPER_ARTIFACT_CACHE_INDEX = Path("data/index/paper_artifact_cache/paper_artifact_cache_index.jsonl")
ALLOWED_ARTIFACT_TYPES = {"raw_payload", "abstract_l1_claims", "fulltext_l1_claims", "selected_fulltext_spans"}
ALLOWED_FILENAMES = {
    "payload_report.json": "raw_payload",
    "abstract_l1_claims.jsonl": "abstract_l1_claims",
    "fulltext_l1_claims.jsonl": "fulltext_l1_claims",
    "selected_fulltext_spans.jsonl": "selected_fulltext_spans",
    "fulltext_evidence_spans.jsonl": "selected_fulltext_spans",
}
REASONING_ARTIFACT_FILENAMES = {
    "relation_evidence_bundles.jsonl", "graph_conflict_candidates.jsonl",
    "graph_reasoning_traces.jsonl", "hypothesis_hyperedges.jsonl",
    "conflict_evidence_timelines.jsonl", "hypothesis_later_evidence_comparisons.jsonl",
    "external_validation_results.jsonl", "validation_summary.json", "final_report.json", "final_report.md",
}
FINGERPRINT_FIELDS = (
    "prompt_template_hash", "l1_schema_version", "model_provider", "model_name",
    "model_fingerprint", "domain_profile", "resolver_registry_hash",
)


def artifact_content_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PaperArtifactCacheRecord(CODEBaseModel):
    cache_record_id: str
    canonical_paper_id: str
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    title_hash: str = ""
    artifact_type: str
    task_family: str
    query_independent: bool | None = None
    safe_for_cross_query_reuse: bool = False
    prompt_template_hash: str = ""
    l1_schema_version: str = ""
    model_provider: str = ""
    model_name: str = ""
    model_fingerprint: str = ""
    domain_profile: str = ""
    resolver_registry_hash: str = ""
    query_hash: str = ""
    triple_id: str = ""
    source_run_id: str = ""
    source_batch_id: str = ""
    source_triple_id: str = ""
    source_artifact_path: str
    artifact_content_hash: str
    created_at: str
    reuse_allowed: bool = False
    warnings: list[str] = Field(default_factory=list)


def _fingerprint_payload(payload: dict[str, Any]) -> dict[str, str]:
    return {field: str(payload.get(field) or "") for field in FINGERPRINT_FIELDS}


def new_cache_record(
    *, canonical_paper_id: str, artifact_type: str, task_family: str,
    source_artifact_path: str | Path, query_independent: bool | None,
    safe_for_cross_query_reuse: bool, source_run_id: str = "",
    source_batch_id: str = "", source_triple_id: str = "",
    query_hash: str = "", triple_id: str = "", doi: str = "", pmid: str = "",
    pmcid: str = "", title_hash: str = "", **fingerprints: Any,
) -> PaperArtifactCacheRecord:
    path = Path(source_artifact_path).resolve()
    warnings: list[str] = []
    if artifact_type not in ALLOWED_ARTIFACT_TYPES or path.name in REASONING_ARTIFACT_FILENAMES:
        warnings.append("reasoning_artifact_not_cacheable")
    missing = [field for field, value in _fingerprint_payload(fingerprints).items() if not value]
    if missing:
        warnings.append("missing_required_fingerprint")
    if query_independent is not True and not (query_hash and triple_id):
        warnings.append("query_specific_identity_missing")
    content_hash = artifact_content_hash(path)
    identity = {
        "paper": canonical_paper_id, "artifact_type": artifact_type, "task_family": task_family,
        **_fingerprint_payload(fingerprints), "query_independent": query_independent,
        "query_hash": query_hash if query_independent is not True else "",
        "triple_id": triple_id if query_independent is not True else "",
        "content_hash": content_hash,
    }
    record_id = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
    allowed = bool(
        artifact_type in ALLOWED_ARTIFACT_TYPES and path.name not in REASONING_ARTIFACT_FILENAMES
        and not missing and query_independent is not None and safe_for_cross_query_reuse
        and (query_independent is True or bool(query_hash and triple_id))
    )
    return PaperArtifactCacheRecord(
        cache_record_id=record_id, canonical_paper_id=canonical_paper_id,
        doi=doi, pmid=pmid, pmcid=pmcid, title_hash=title_hash,
        artifact_type=artifact_type, task_family=task_family,
        query_independent=query_independent, safe_for_cross_query_reuse=safe_for_cross_query_reuse,
        **_fingerprint_payload(fingerprints), query_hash=query_hash, triple_id=triple_id,
        source_run_id=source_run_id, source_batch_id=source_batch_id,
        source_triple_id=source_triple_id, source_artifact_path=str(path),
        artifact_content_hash=content_hash, created_at=datetime.now(timezone.utc).isoformat(),
        reuse_allowed=allowed, warnings=warnings,
    )


def store_cache_record(record: PaperArtifactCacheRecord, index_path: str | Path = DEFAULT_PAPER_ARTIFACT_CACHE_INDEX) -> None:
    path = Path(index_path)
    records = {str(item.get("cache_record_id")): item for item in iter_jsonl(path)}
    records[record.cache_record_id] = record.model_dump(mode="json")
    atomic_write_jsonl(path, (records[key] for key in sorted(records)))


def lookup_paper_artifact(
    *, canonical_paper_id: str, artifact_type: str, task_family: str,
    index_path: str | Path = DEFAULT_PAPER_ARTIFACT_CACHE_INDEX,
    query_independent: bool, query_hash: str = "", triple_id: str = "", **fingerprints: Any,
) -> PaperArtifactCacheRecord | None:
    expected = _fingerprint_payload(fingerprints)
    for payload in iter_jsonl(Path(index_path)):
        record = PaperArtifactCacheRecord.model_validate(payload)
        if not record.reuse_allowed or not record.safe_for_cross_query_reuse:
            continue
        if (record.canonical_paper_id, record.artifact_type, record.task_family) != (canonical_paper_id, artifact_type, task_family):
            continue
        if any(getattr(record, field) != value for field, value in expected.items()):
            continue
        if query_independent:
            if record.query_independent is not True:
                continue
        elif record.query_independent is not False or record.query_hash != query_hash or record.triple_id != triple_id:
            continue
        source = Path(record.source_artifact_path)
        if not source.is_file() or artifact_content_hash(source) != record.artifact_content_hash:
            continue
        return record
    return None


def copy_cached_artifact_into_run(record: PaperArtifactCacheRecord, current_run_dir: str | Path) -> dict[str, Any]:
    if record.artifact_type not in ALLOWED_ARTIFACT_TYPES or Path(record.source_artifact_path).name in REASONING_ARTIFACT_FILENAMES:
        raise ValueError("Reasoning artifacts cannot be copied through the paper cache")
    source = Path(record.source_artifact_path)
    if not source.is_file() or artifact_content_hash(source) != record.artifact_content_hash:
        raise ValueError("Cached artifact content hash mismatch")
    paper_dir = Path(current_run_dir) / "artifacts/cache_imports" / f"paper_{record.canonical_paper_id.replace('/', '_')}"
    paper_dir.mkdir(parents=True, exist_ok=True)
    target = paper_dir / source.name
    shutil.copy2(source, target)
    cache_record_path = paper_dir / "cache_record.json"
    cache_record_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return {
        "canonical_paper_id": record.canonical_paper_id, "artifact_type": record.artifact_type,
        "cache_record_id": record.cache_record_id, "source_run_id": record.source_run_id,
        "source_batch_id": record.source_batch_id, "source_triple_id": record.source_triple_id,
        "copied_into_current_run": True, "current_artifact_path": str(target.resolve()),
        "fingerprint_verified": True, "reuse_scope": "cross_batch_paper_level",
        "reasoning_artifact_reused": False,
    }


def write_cache_events(run_dir: str | Path, hits: Iterable[dict[str, Any]], misses: Iterable[dict[str, Any]]) -> tuple[Path, Path]:
    artifacts = Path(run_dir) / "artifacts"
    hit_path, miss_path = artifacts / "paper_artifact_cache_hits.jsonl", artifacts / "paper_artifact_cache_misses.jsonl"
    atomic_write_jsonl(hit_path, iter(hits))
    atomic_write_jsonl(miss_path, iter(misses))
    return hit_path, miss_path


def build_paper_artifact_cache_index_from_runs(
    runs_root: Path, cache_index_path: Path, *, include_batches: bool = True, dry_run: bool = True,
) -> dict[str, Any]:
    """Index only allowlisted paper artifacts; incomplete records stay non-reusable."""

    roots = list(Path(runs_root).glob("*/artifacts"))
    if include_batches:
        roots.extend(Path(runs_root).glob("batch_*/per_triple/*/artifacts"))
    records: list[PaperArtifactCacheRecord] = []
    skipped_reasoning = 0
    for artifacts in sorted(set(path.resolve() for path in roots)):
        for path in artifacts.iterdir() if artifacts.is_dir() else ():
            if path.name in REASONING_ARTIFACT_FILENAMES:
                skipped_reasoning += 1
                continue
            artifact_type = ALLOWED_FILENAMES.get(path.name)
            if not artifact_type or not path.is_file():
                continue
            run_dir = artifacts.parent
            state_path = run_dir / "run_state.json"
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
            metadata = state.get("summary", {}).get("triple_metadata", {})
            record = new_cache_record(
                canonical_paper_id="UNKNOWN", artifact_type=artifact_type,
                task_family=artifact_type, source_artifact_path=path,
                query_independent=None, safe_for_cross_query_reuse=False,
                source_run_id=str(state.get("run_id") or run_dir.name),
                source_batch_id=str(metadata.get("batch_id") or ""),
                source_triple_id=str(metadata.get("triple_id") or ""),
            )
            records.append(record)
    if not dry_run:
        atomic_write_jsonl(cache_index_path, (record.model_dump(mode="json") for record in records))
    return {
        "candidate_record_count": len(records), "reusable_record_count": sum(item.reuse_allowed for item in records),
        "reasoning_artifacts_skipped": skipped_reasoning, "dry_run": dry_run,
        "cache_index_path": str(cache_index_path),
    }


__all__ = [
    "DEFAULT_PAPER_ARTIFACT_CACHE_INDEX", "ALLOWED_ARTIFACT_TYPES", "REASONING_ARTIFACT_FILENAMES",
    "PaperArtifactCacheRecord", "artifact_content_hash", "new_cache_record", "store_cache_record",
    "lookup_paper_artifact", "copy_cached_artifact_into_run", "write_cache_events",
    "build_paper_artifact_cache_index_from_runs",
]
