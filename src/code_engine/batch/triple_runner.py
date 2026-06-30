"""Isolated triple-first batch runner and post-run catalog builder."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl
from code_engine.corpus.paper_artifact_cache import (
    DEFAULT_PAPER_ARTIFACT_CACHE_INDEX,
    copy_cached_artifact_into_run,
    lookup_paper_artifact,
    new_cache_record,
    store_cache_record,
    write_cache_events,
)
from code_engine.schemas.triples import SeedTriple, seed_triple_from_payload
from code_engine.workflow.orchestrator import run_workflow
from code_engine.workflow.triple_metadata import resume_manifest_valid


PaperArtifactBuilder = Callable[[SeedTriple, dict[str, Any], Path], Path]


DEFAULT_CACHE_FINGERPRINTS = {
    "prompt_template_hash": "triple_batch_raw_payload_v1",
    "l1_schema_version": "paper_artifact_v1",
    "model_provider": "local",
    "model_name": "deterministic_input",
    "model_fingerprint": "no_api_v1",
    "domain_profile": "general_biomedical",
    "resolver_registry_hash": "domain_neutral_registry_v1",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _default_artifact_builder(seed: SeedTriple, paper: dict[str, Any], run_dir: Path) -> Path:
    paper_id = str(paper["canonical_paper_id"]).replace("/", "_")
    target = run_dir / "artifacts" / "cache_imports" / f"paper_{paper_id}" / "payload_report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = paper.get("artifact_payload", paper.get("payload", {"canonical_paper_id": paper["canonical_paper_id"]}))
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _prepare_papers(
    seed: SeedTriple,
    triple_payload: dict[str, Any],
    run_dir: Path,
    *,
    batch_id: str,
    cache_enabled: bool,
    cache_index: Path,
    fingerprints: dict[str, str],
    artifact_builder: PaperArtifactBuilder,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    hits: list[dict[str, Any]] = []
    misses: list[dict[str, Any]] = []
    builds = 0
    for paper in triple_payload.get("papers") or []:
        canonical_id = str(paper.get("canonical_paper_id") or "").strip()
        if not canonical_id:
            misses.append({"canonical_paper_id": "", "reason": "canonical_paper_id_missing"})
            continue
        artifact_type = str(paper.get("artifact_type") or "raw_payload")
        task_family = str(paper.get("task_family") or artifact_type)
        independent = paper.get("query_independent", True)
        record = None
        if cache_enabled:
            record = lookup_paper_artifact(
                canonical_paper_id=canonical_id,
                artifact_type=artifact_type,
                task_family=task_family,
                index_path=cache_index,
                query_independent=bool(independent),
                query_hash=seed.query_hash,
                triple_id=seed.triple_id,
                **fingerprints,
            )
        if record is not None:
            hits.append(copy_cached_artifact_into_run(record, run_dir))
            continue
        reason = "cache_disabled" if not cache_enabled else "no_fingerprint_complete_match"
        misses.append({
            "canonical_paper_id": canonical_id,
            "artifact_type": artifact_type,
            "task_family": task_family,
            "query_hash": seed.query_hash,
            "triple_id": seed.triple_id,
            "reason": reason,
        })
        source = artifact_builder(seed, paper, run_dir)
        builds += 1
        if cache_enabled:
            fresh = new_cache_record(
                canonical_paper_id=canonical_id,
                artifact_type=artifact_type,
                task_family=task_family,
                source_artifact_path=source,
                query_independent=independent,
                safe_for_cross_query_reuse=bool(paper.get("safe_for_cross_query_reuse", True)),
                source_run_id=f"{batch_id}:{seed.triple_id}",
                source_batch_id=batch_id,
                source_triple_id=seed.triple_id,
                doi=str(paper.get("doi") or ""),
                pmid=str(paper.get("pmid") or ""),
                pmcid=str(paper.get("pmcid") or ""),
                title_hash=str(paper.get("title_hash") or ""),
                query_hash=seed.query_hash if independent is not True else "",
                triple_id=seed.triple_id if independent is not True else "",
                **fingerprints,
            )
            store_cache_record(fresh, cache_index)
    write_cache_events(run_dir, hits, misses)
    return hits, misses, builds


def _catalog_row(card: dict[str, Any]) -> dict[str, Any]:
    seed = card["seed_triple"]
    summary = card.get("summary") or {}
    paths = card.get("artifact_paths") or {}
    return {
        "triple_id": card["triple_id"],
        "display_title": card["display_title"],
        "subject_canonical_id": seed["subject"].get("canonical_id", ""),
        "subject_name": seed["subject"]["name"],
        "relation_family": seed["relation"].get("family", ""),
        "relation_name": seed["relation"]["name"],
        "object_canonical_id": seed["object"].get("canonical_id", ""),
        "object_name": seed["object"]["name"],
        "context_terms": seed.get("context", {}).get("context_terms", []),
        "batch_id": card.get("batch_id"),
        "run_id": card["run_id"],
        "run_dir": card["run_dir"],
        "status": card["status"],
        "triple_card_path": str((Path(card["run_dir"]) / "triple_card.json").resolve()),
        "final_report_path": paths.get("final_report"),
        "paper_count": int(summary.get("paper_count", 0)),
        "conflict_count": int(summary.get("conflict_count", 0)),
        "hypothesis_count": int(summary.get("hypothesis_count", 0)),
        "created_at": card.get("created_at") or _now(),
    }


def run_triple_batch(
    triples: Iterable[dict[str, Any] | SeedTriple],
    batch_dir: str | Path,
    *,
    batch_id: str | None = None,
    resume: bool = False,
    paper_artifact_cache_enabled: bool = True,
    paper_artifact_cache_index: str | Path = DEFAULT_PAPER_ARTIFACT_CACHE_INDEX,
    cache_fingerprints: dict[str, str] | None = None,
    paper_artifact_builder: PaperArtifactBuilder | None = None,
    workflow_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run each seed triple in its own directory, then build read-only aggregates."""

    raw = [item.model_dump(mode="json") if isinstance(item, SeedTriple) else dict(item) for item in triples]
    seeds = [seed_triple_from_payload(item, query_text=str(item.get("query_text") or "")) for item in raw]
    if not seeds:
        raise ValueError("At least one triple is required")
    if len({seed.triple_id for seed in seeds}) != len(seeds):
        raise ValueError("Batch contains duplicate stable triple IDs")
    identifier = batch_id or _hash([seed.model_dump(mode="json") for seed in seeds])[:16]
    directory = Path(batch_dir).resolve()
    if directory.exists() and any(directory.iterdir()) and not resume:
        report = {
            "status": "blocked",
            "blocking_reasons": ["batch_output_dir_exists_without_resume"],
            "batch_id": identifier,
        }
        atomic_write_json(directory / "batch_contamination_preflight_report.json", report)
        raise FileExistsError(f"Batch directory exists; pass resume=True: {directory}")
    per_triple = directory / "per_triple"
    aggregate = directory / "aggregate"
    per_triple.mkdir(parents=True, exist_ok=True)
    aggregate.mkdir(parents=True, exist_ok=True)
    atomic_write_jsonl(directory / "triples.jsonl", (seed.model_dump(mode="json") for seed in seeds))
    manifest = {
        "batch_id": identifier,
        "created_at": _now(),
        "triple_count": len(seeds),
        "resume": bool(resume),
        "aggregate_feedback_to_triples": False,
        "paper_artifact_cache_enabled": bool(paper_artifact_cache_enabled),
        "paper_artifact_cache_index": str(Path(paper_artifact_cache_index).resolve()),
    }
    atomic_write_json(directory / "batch_manifest.json", manifest)
    preflight = {
        "status": "pass",
        "blocking_reasons": [],
        "per_triple_run_dirs_unique": True,
        "aggregate_artifacts_used_as_per_triple_input": False,
        "sibling_artifacts_used_as_per_triple_input": False,
        "global_evidence_injected_before_reasoning": False,
        "reasoning_artifact_selected_for_cross_batch_reuse": False,
        "direct_read_old_run_artifact_without_copy_in": False,
        "aggregate_feedback_to_triples": False,
    }
    atomic_write_json(directory / "batch_contamination_preflight_report.json", preflight)
    fingerprints = {**DEFAULT_CACHE_FINGERPRINTS, **(cache_fingerprints or {})}
    builder = paper_artifact_builder or _default_artifact_builder
    index = Path(paper_artifact_cache_index).resolve()
    kwargs = dict(workflow_kwargs or {})
    for enforced in ("query", "run_dir", "batch_id", "seed_triple", "triple_input_hash", "execute", "api", "network"):
        kwargs.pop(enforced, None)
    cards: list[dict[str, Any]] = []
    total_hits = total_misses = total_builds = resumed = 0
    for payload, seed in zip(raw, seeds):
        run_dir = per_triple / seed.triple_id
        input_hash = _hash({
            "seed_triple": seed.model_dump(mode="json"),
            "workflow": kwargs,
            "cache_fingerprints": fingerprints,
            "papers": payload.get("papers") or [],
        })
        if resume and resume_manifest_valid(run_dir, input_hash):
            resumed += 1
            cards.append(json.loads((run_dir / "triple_card.json").read_text(encoding="utf-8")))
            continue
        if run_dir.exists() and any(run_dir.iterdir()):
            # An invalid manifest must rerun from a clean triple-owned directory.
            import shutil
            shutil.rmtree(run_dir)
        hits, misses, builds = _prepare_papers(
            seed, payload, run_dir,
            batch_id=identifier,
            cache_enabled=paper_artifact_cache_enabled,
            cache_index=index,
            fingerprints=fingerprints,
            artifact_builder=builder,
        )
        total_hits += len(hits)
        total_misses += len(misses)
        total_builds += builds
        state = run_workflow(
            query=seed.query_text,
            run_dir=run_dir,
            batch_id=identifier,
            seed_triple=seed.model_dump(mode="json"),
            triple_input_hash=input_hash,
            paper_artifact_cache_enabled=paper_artifact_cache_enabled,
            paper_artifact_cache_index=index,
            paper_artifact_cache_hits=len(hits),
            paper_artifact_cache_misses=len(misses),
            paper_cache_hit_records=hits,
            paper_cache_miss_records=misses,
            execute=False,
            api=False,
            network=False,
            **kwargs,
        )
        cards.append(json.loads((run_dir / "triple_card.json").read_text(encoding="utf-8")))
    rows = [_catalog_row(card) for card in cards]
    index_path = aggregate / "batch_processed_triples_index.jsonl"
    atomic_write_jsonl(index_path, iter(rows))
    metrics = {
        "batch_id": identifier,
        "triple_count": len(rows),
        "resumed_triple_count": resumed,
        "paper_artifact_cache_hits": total_hits,
        "paper_artifact_cache_misses": total_misses,
        "paper_artifact_build_count": total_builds,
        "estimated_api_calls_saved": total_hits,
        "aggregate_feedback_to_triples": False,
    }
    atomic_write_json(aggregate / "batch_metrics_summary.json", metrics)
    provenance = {
        **metrics,
        "historical_runs_read": False,
        "explicit_cache_index_scanned": bool(paper_artifact_cache_enabled),
        "global_evidence_injected_before_reasoning": False,
        "reasoning_artifacts_reused_from_other_batch": False,
        "cache_hit_requires_copy_in": True,
        "per_triple_run_dirs_unique": True,
        "processed_triples_index_role": "post_run_catalog_only",
    }
    atomic_write_json(aggregate / "batch_runtime_provenance_report.json", provenance)
    report = (
        f"# Batch discovery report\n\nBatch `{identifier}` processed {len(rows)} triples.\n\n"
        f"Paper cache hits: {total_hits}; misses: {total_misses}; estimated calls saved: {total_hits}.\n\n"
        "Aggregate feedback to per-triple reasoning: false.\n"
    )
    (aggregate / "batch_discovery_report.md").write_text(report, encoding="utf-8")
    return {**provenance, "batch_dir": str(directory), "processed_triples_index": str(index_path)}


__all__ = ["DEFAULT_CACHE_FINGERPRINTS", "PaperArtifactBuilder", "run_triple_batch"]
