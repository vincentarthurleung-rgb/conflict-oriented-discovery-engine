"""Idempotent merge planning and optional writes to the global JSONL knowledge store."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Iterable, Iterator

from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl, iter_jsonl
from code_engine.corpus.models import KnowledgeMergeResult


SOURCES = [
    ("papers", "run_paper_manifest.jsonl", "jsonl", "canonical_paper_id"),
    ("papers", "batch_paper_manifest.jsonl", "jsonl", "canonical_paper_id"),
    ("claims", "abstract_l1_claims.jsonl", "jsonl", None),
    ("claims", "fulltext_l1_claims.jsonl", "jsonl", None),
    ("observations", "l2_abstract_observations.json", "json", None),
    ("observations", "l2_fulltext_observations.json", "json", None),
    ("conflicts", "abstract_conflict_candidates.jsonl", "jsonl", "candidate_id"),
    ("conflicts", "fulltext_conflict_confirmation.jsonl", "jsonl", "candidate_id"),
    ("fulltext_evidence", "fulltext_evidence_records.jsonl", "jsonl", "evidence_id"),
    ("mechanism_nodes", "mechanism_graph.json", "graph:nodes", "node_id"),
    ("mechanism_edges", "mechanism_graph.json", "graph:edges", "edge_id"),
    ("mechanism_paths", "mechanism_graph.json", "graph:paths", "path_id"),
    ("hypotheses", "hypothesis_hyperedges.jsonl", "jsonl", "hypothesis_id"),
    ("hypotheses", "batch_hypothesis_hyperedges.jsonl", "jsonl", "hypothesis_id"),
    ("validation_results", "external_validation_results.jsonl", "jsonl", None),
]


def _source_records(path: Path, mode: str) -> Iterator[dict]:
    if mode == "jsonl":
        yield from iter_jsonl(path)
    elif path.exists():
        value = json.loads(path.read_text(encoding="utf-8"))
        if mode == "json" and isinstance(value, list):
            yield from (item for item in value if isinstance(item, dict))
        elif mode.startswith("graph:"):
            yield from (item for item in value.get(mode.split(":", 1)[1], []) if isinstance(item, dict))


def _key(kind: str, item: dict, explicit: str | None) -> str:
    if explicit and item.get(explicit):
        return str(item[explicit])
    if kind == "claims":
        parts = [item.get("canonical_paper_id") or item.get("paper_id"), item.get("source_scope"), item.get("subject_raw") or item.get("subject"), item.get("object_raw") or item.get("object"), item.get("relation_family"), item.get("direction"), item.get("claim_text") or item.get("evidence_sentence")]
    elif kind == "observations":
        parts = [item.get(name) for name in ("canonical_paper_id", "subject_canonical_id", "object_canonical_id", "relation_family", "polarity_type", "direction", "evidence_id")]
    elif kind == "validation_results":
        parts = [item.get(name) for name in ("hypothesis_id", "anchor_id", "validator_name", "query_plan_id")]
    else:
        parts = [item]
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def merge_run_artifacts_into_knowledge_store(run_dir: Path, corpus_dir: Path, *, update_global: bool = False, dry_run: bool = True) -> KnowledgeMergeResult:
    run_dir, corpus_dir = Path(run_dir), Path(corpus_dir)
    artifacts, store = run_dir / "artifacts", corpus_dir / "knowledge_store"
    if not artifacts.exists():
        artifacts = run_dir
    state_path = run_dir / "run_state.json"
    run_id = run_dir.name
    if state_path.exists():
        run_id = str(json.loads(state_path.read_text(encoding="utf-8")).get("run_id") or run_id)
    audit: list[dict] = []
    planned: dict[str, list[dict]] = {}
    inserted = updated = skipped = 0
    counts: dict[str, int] = {}
    grouped = {kind: [] for kind, *_ in SOURCES}
    for kind, filename, mode, explicit in SOURCES:
        grouped[kind].append((filename, mode, explicit))
    for kind, source_specs in grouped.items():
        destination = store / f"{kind}.jsonl"
        existing_keys = set()
        existing_runs: dict[str, set[str]] = {}
        for item in iter_jsonl(destination):
            explicit = next((spec[2] for spec in source_specs if spec[2] and item.get(spec[2])), None)
            existing_key = _key(kind, item, explicit)
            existing_keys.add(existing_key)
            existing_runs[existing_key] = set(map(str, item.get("source_run_ids", [])))
        additions = []
        provenance_updates: dict[str, str] = {}
        for filename, mode, explicit in source_specs:
            for raw in _source_records(artifacts / filename, mode):
                item = dict(raw)
                key = _key(kind, item, explicit)
                if key in existing_keys:
                    if run_id not in existing_runs.get(key, set()):
                        updated += 1
                        provenance_updates[key] = str(artifacts / filename)
                        existing_runs.setdefault(key, set()).add(run_id)
                        audit.append({"object_type": kind, "object_key": key, "action": "updated_provenance" if update_global and not dry_run else "planned_update", "run_id": run_id})
                    else:
                        skipped += 1
                        audit.append({"object_type": kind, "object_key": key, "action": "skipped_duplicate", "run_id": run_id})
                    continue
                existing_keys.add(key)
                existing_runs[key] = {run_id}
                item.update({"first_seen_run_id": item.get("first_seen_run_id") or run_id, "last_seen_run_id": run_id, "source_run_ids": list(dict.fromkeys([*item.get("source_run_ids", []), run_id])), "source_artifact_refs": list(dict.fromkeys([*item.get("source_artifact_refs", []), str(artifacts / filename)]))})
                additions.append(item)
                inserted += 1
                audit.append({"object_type": kind, "object_key": key, "action": "inserted" if update_global and not dry_run else "planned_insert", "run_id": run_id})
        planned[kind] = additions
        counts[kind] = len(additions)
        if update_global and not dry_run and (additions or provenance_updates):
            existing = iter_jsonl(destination)
            atomic_write_jsonl(destination, _chain(_merge_existing(kind, existing, source_specs, provenance_updates, run_id), additions))
    status = "updated" if update_global and not dry_run else "planned"
    result = KnowledgeMergeResult(status=status, update_global=bool(update_global and not dry_run), inserted_count=inserted, updated_count=updated, skipped_count=skipped, duplicate_count=skipped, object_type_counts=counts)
    plan_path = artifacts / "knowledge_merge_plan.json"
    audit_path = artifacts / "knowledge_merge_audit.jsonl"
    summary_path = artifacts / "knowledge_merge_summary.json"
    atomic_write_json(plan_path, {"status": status, "update_global": result.update_global, "planned_counts": counts, "global_store": str(store)})
    atomic_write_jsonl(audit_path, iter(audit))
    result.artifact_refs = {"plan": str(plan_path), "audit": str(audit_path), "summary": str(summary_path)}
    atomic_write_json(summary_path, result.model_dump(mode="json"))
    if update_global and not dry_run:
        atomic_write_json(store / "knowledge_store_summary.json", result.model_dump(mode="json"))
        existing_audit = iter_jsonl(store / "merge_audit.jsonl")
        atomic_write_jsonl(store / "merge_audit.jsonl", _chain(existing_audit, audit))
    return result


def _chain(first: Iterable[dict], second: Iterable[dict]) -> Iterator[dict]:
    yield from first
    yield from second


def _merge_existing(kind: str, records: Iterable[dict], source_specs: list[tuple], updates: dict[str, str], run_id: str) -> Iterator[dict]:
    for item in records:
        explicit = next((spec[2] for spec in source_specs if spec[2] and item.get(spec[2])), None)
        key = _key(kind, item, explicit)
        if key in updates:
            item = {**item, "last_seen_run_id": run_id, "source_run_ids": list(dict.fromkeys([*item.get("source_run_ids", []), run_id])), "source_artifact_refs": list(dict.fromkeys([*item.get("source_artifact_refs", []), updates[key]]))}
        yield item


__all__ = ["merge_run_artifacts_into_knowledge_store"]
