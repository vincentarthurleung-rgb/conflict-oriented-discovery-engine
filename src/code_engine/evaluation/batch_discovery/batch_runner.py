"""Offline-first batch runner for conflict discovery evaluation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.evaluation.batch_discovery.annotation_schema import write_annotation_schema
from code_engine.evaluation.batch_discovery.conflict_aggregator import aggregate_conflict_candidates
from code_engine.evaluation.batch_discovery.metrics import compute_batch_metrics
from code_engine.evaluation.batch_discovery.prompt_bank import build_prompt_bank_manifest, load_prompt_bank
from code_engine.evaluation.batch_discovery.reports import render_batch_discovery_report
from code_engine.evaluation.batch_discovery.sampling import sample_conflicts
from code_engine.graph.abstract_conflict_screening import build_abstract_conflict_candidates
from code_engine.extraction.l1_budget import estimate_l1_cost
from code_engine.evaluation.batch_discovery.validation import run_batch_external_validation
from code_engine.hypothesis.candidate_builder import build_hypothesis_candidates_from_run_artifacts
from code_engine.hypothesis.hyperedge_builder import build_hypothesis_hyperedge
from code_engine.hypothesis.io import iter_jsonl, write_jsonl
from code_engine.hypothesis.scoring import score_hypothesis_candidate
from code_engine.hypothesis.validation_requirements import build_validation_requirements_for_hypothesis


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")


def run_batch_discovery(
    prompt_bank: str | Path,
    *,
    run_dir: str | Path | None = None,
    max_prompts: int | None = None,
    l1_mode: str = "abstract_screening",
    sample_conflict_count: int = 300,
    dry_run: bool = True,
    api_enabled: bool = False,
    network_enabled: bool = False,
    resume: bool = False,
    min_evidence_count: int = 3,
    min_entropy: float = 0.65,
    annotations_path: str | Path | None = None,
    per_prompt_budget: dict | None = None,
    external_validation: bool = False,
    validation_query_mode: str = "auto",
    validation_index_dir: str | None = None,
    validation_cache_dir: str | None = None,
    validation_max_anchors: int = 100,
    validation_max_query_plans: int = 400,
    validation_max_records_per_validator: int = 100,
    validation_max_signals_per_run: int = 500,
    global_corpus_dir: str | Path | None = None,
    paper_registry_enabled: bool = True, update_global_corpus: bool = False,
    l1_task_cache_enabled: bool = True, allow_compatible_l1_task_reuse: bool = False,
    merge_knowledge_store: bool = True, update_global_knowledge_store: bool = False,
) -> dict[str, Any]:
    prompts = load_prompt_bank(prompt_bank, max_prompts)
    batch_hash = hashlib.sha256("|".join(str(item["prompt_id"]) for item in prompts).encode()).hexdigest()[:10]
    directory = Path(run_dir) if run_dir is not None else Path("runs") / f"batch_{batch_hash}"
    directory.mkdir(parents=True, exist_ok=True)
    corpus_dir = Path(global_corpus_dir) if global_corpus_dir else Path("data/corpus")
    batch_paper_manifest = []
    unique_papers: set[str] = set()
    duplicate_hits = cache_hits = cache_misses = 0
    prompt_corpus_stats = []
    if paper_registry_enabled:
        from code_engine.corpus.io import atomic_write_jsonl
        from code_engine.corpus.l1_task_cache import L1TaskSignature, build_l1_task_cache_key, lookup_l1_task_cache
        from code_engine.corpus.paper_registry import PaperRegistry
        registry = PaperRegistry.load(corpus_dir / "paper_registry")
        seen_tasks: set[str] = set()
        for prompt in prompts:
            retrieved = reused = new_tasks = reused_tasks = 0
            for paper in prompt.get("papers", []):
                retrieved += 1
                before = set(registry.records)
                record = registry.resolve_or_create({**paper, "prompt_id": prompt["prompt_id"]}, f"batch_{batch_hash}", str(prompt.get("query") or prompt.get("prompt") or ""))
                duplicate = record.canonical_paper_id in unique_papers or record.canonical_paper_id in before
                duplicate_hits += int(duplicate); reused += int(duplicate)
                unique_papers.add(record.canonical_paper_id)
                batch_paper_manifest.append({"prompt_id": prompt["prompt_id"], "paper_id": paper.get("paper_id"), "canonical_paper_id": record.canonical_paper_id, "doi": record.bibliographic.doi, "title": record.bibliographic.title, "journal": record.bibliographic.journal, "publication_year": record.bibliographic.publication_year, "dedup_status": "duplicate" if duplicate else "new", "warnings": record.warnings})
                if l1_task_cache_enabled and record.abstract_hash:
                    signature = L1TaskSignature(task_family="abstract_claim_screening", source_scope="abstract", canonical_paper_id=record.canonical_paper_id, content_hash=record.abstract_hash, schema_version="abstract_claim_v1", prompt_fingerprint=str(prompt.get("prompt_profile_id") or "batch"), domain_id=prompt.get("domain_id"), l1_mode=l1_mode)
                    key = build_l1_task_cache_key(signature)
                    cached = lookup_l1_task_cache(signature, corpus_dir / "l1_task_cache")
                    reusable = key in seen_tasks or (cached and (cached.status == "hit" or (cached.status == "compatible_task_family_hit" and allow_compatible_l1_task_reuse)))
                    if reusable:
                        cache_hits += 1; reused_tasks += 1
                    else:
                        cache_misses += 1; new_tasks += 1; seen_tasks.add(key)
                        if update_global_corpus:
                            from code_engine.corpus.l1_task_cache import L1TaskCache, store_l1_task_cache_record
                            paper_claims = [{**claim, "canonical_paper_id": record.canonical_paper_id} for claim in prompt.get("abstract_claims", []) if str(claim.get("paper_id") or "") == str(paper.get("paper_id") or "")]
                            store_l1_task_cache_record(L1TaskCache.new_record(signature, f"batch_{batch_hash}", {"claims": paper_claims}, claim_count=len(paper_claims)), corpus_dir / "l1_task_cache")
            prompt_corpus_stats.append({"prompt_id": prompt["prompt_id"], "retrieved_papers": retrieved, "unique_papers": retrieved - reused, "reused_papers": reused, "new_l1_tasks": new_tasks, "reused_l1_tasks": reused_tasks})
        atomic_write_jsonl(directory / "batch_paper_manifest.jsonl", iter(batch_paper_manifest))
        atomic_write_jsonl(directory / "batch_prompt_corpus_stats.jsonl", iter(prompt_corpus_stats))
        if update_global_corpus:
            registry.save()
    if resume and (directory / "batch_run_manifest.json").exists() and (directory / "batch_metrics_summary.json").exists():
        manifest = json.loads((directory / "batch_run_manifest.json").read_text(encoding="utf-8"))
        metrics = json.loads((directory / "batch_metrics_summary.json").read_text(encoding="utf-8"))
        candidates_path = directory / "abstract_conflict_candidates.jsonl"
        sample_path = directory / "conflict_annotation_sample.jsonl"
        sample = [item for item in iter_jsonl(sample_path)]
        return {"run_dir": str(directory), "manifest": {**manifest, "resumed": True}, "metrics": metrics, "candidates": [], "candidates_path": str(candidates_path), "annotation_sample": sample, "resume_payload_bounded": True}
    per_prompt_results = []
    run_summaries = []
    bibliography_by_paper = {str(item.get("paper_id")): item for item in batch_paper_manifest if item.get("paper_id")}
    for prompt in prompts:
        claims = [{**item, **bibliography_by_paper.get(str(item.get("paper_id")), {}), "prompt_id": prompt["prompt_id"]} for item in prompt.get("abstract_claims", [])]
        observations = list(prompt.get("normalized_observations", []))
        result = build_abstract_conflict_candidates(
            claims, observations, min_evidence_count=min_evidence_count,
            min_entropy=min_entropy,
        )
        per_prompt_results.append({"prompt_id": prompt["prompt_id"], "candidates": result["candidates"]})
        run_summaries.append({
            "retrieved_paper_count": len(prompt.get("papers", [])),
            "abstract_processed_paper_count": len({item.get("paper_id") for item in claims}),
            "abstract_claim_count": len(claims),
            "normalized_observation_count": len(observations),
        })
    candidates = aggregate_conflict_candidates(per_prompt_results)
    if batch_paper_manifest:
        from code_engine.corpus.artifact_provenance import attach_linked_paper_provenance
        candidates = [attach_linked_paper_provenance(item, [bibliography_by_paper[paper_id] for paper_id in map(str, item.get("paper_ids", [])) if paper_id in bibliography_by_paper]) for item in candidates]
    focus_set = [item for item in candidates if item.get("recommended_for_fulltext_escalation")]
    sample = sample_conflicts(candidates, sample_conflict_count)
    annotations = []
    if annotations_path and Path(annotations_path).exists():
        annotations = [item for item in iter_jsonl(Path(annotations_path))]
    confirmation_path = directory / "fulltext_conflict_confirmation.jsonl"
    hypothesis_candidates = []
    hypothesis_hyperedges = []
    for candidate in build_hypothesis_candidates_from_run_artifacts(
        None, iter_jsonl(confirmation_path), iter(candidates), iter(focus_set), iter(()), iter(()),
        max_candidates=max(50, len(candidates) * 2),
    ):
        candidate["validation_requirements"] = build_validation_requirements_for_hypothesis(candidate)
        scored = score_hypothesis_candidate(candidate)
        scored["hypothesis_id"] = "H_" + str(scored["candidate_id"]).removeprefix("HC_")
        hypothesis_candidates.append(scored)
        hypothesis_hyperedges.append(build_hypothesis_hyperedge(scored).model_dump(mode="json"))
    hypothesis_statistics = {
        "hypothesis_candidate_count": len(hypothesis_candidates),
        "hypothesis_count": len(hypothesis_hyperedges),
        "traceable_hypothesis_count": sum(bool(item.get("linked_conflict_ids") or item.get("linked_evidence_ids") or item.get("evidence_ids")) for item in hypothesis_hyperedges),
        "fulltext_grounded_hypothesis_count": sum(item.get("source_scope") == "full_text" for item in hypothesis_hyperedges),
        "mechanism_grounded_hypothesis_count": sum(bool(item.get("linked_mechanism_edge_ids") or item.get("linked_mechanism_path_ids")) for item in hypothesis_hyperedges),
        "abstract_only_hypothesis_count": sum(item.get("source_scope") == "abstract" for item in hypothesis_hyperedges),
        "requires_manual_review_hypothesis_count": sum(bool(item.get("requires_manual_review")) for item in hypothesis_hyperedges),
        "note": "hypothesis accuracy is not a batch metric",
    }
    abstract_inputs = [
        str(paper.get("abstract") or paper.get("abstract_text") or "")
        for prompt in prompts for paper in prompt.get("papers", [])
        if paper.get("abstract") or paper.get("abstract_text")
    ]
    cost_estimate = estimate_l1_cost(abstract_inputs)
    metrics = compute_batch_metrics(
        prompts=prompts, candidates=candidates, annotations=annotations,
        run_summaries=run_summaries, hypothesis_statistics=hypothesis_statistics,
        estimated_cost_usd=cost_estimate["estimated_cost_usd"], actual_cost_usd=0.0,
    )
    retrieved_total = sum(item["retrieved_papers"] for item in prompt_corpus_stats)
    missing_doi = sum(not item.get("doi") for item in batch_paper_manifest)
    missing_journal = sum(not item.get("journal") for item in batch_paper_manifest)
    metrics.update({"unique_paper_count": len(unique_papers), "duplicate_paper_hit_count": duplicate_hits, "paper_overlap_rate": round(duplicate_hits / retrieved_total, 6) if retrieved_total else 0.0, "abstract_l1_cache_hit_count": cache_hits, "abstract_l1_cache_miss_count": cache_misses, "fulltext_l1_cache_hit_count": 0, "fulltext_l1_cache_miss_count": 0, "estimated_api_calls_saved_by_cache": cache_hits, "knowledge_merge_inserted_count": 0, "knowledge_merge_skipped_duplicate_count": 0, "missing_doi_rate": round(missing_doi / len(batch_paper_manifest), 6) if batch_paper_manifest else 0.0, "missing_journal_rate": round(missing_journal / len(batch_paper_manifest), 6) if batch_paper_manifest else 0.0})
    validation_result = None
    if external_validation:
        validation_result = run_batch_external_validation(
            candidates, directory, execute=not dry_run,
            query_mode=validation_query_mode, index_dir=validation_index_dir,
            cache_dir=validation_cache_dir, max_anchors=validation_max_anchors,
            max_query_plans=validation_max_query_plans,
            max_records_per_validator=validation_max_records_per_validator,
            max_signals_per_run=validation_max_signals_per_run, hypotheses=hypothesis_hyperedges,
        )
        metrics.update(validation_result["metrics"])
    manifest = {
        "batch_id": f"batch_{batch_hash}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "l1_mode": l1_mode,
        "dry_run": bool(dry_run),
        "api_enabled": bool(api_enabled and not dry_run),
        "network_enabled": bool(network_enabled and not dry_run),
        "api_calls_made": 0,
        "network_calls_made": 0,
        "resume": bool(resume),
        "per_prompt_budget": per_prompt_budget or {},
        "external_validation": {
            "enabled": bool(external_validation),
            "query_mode": validation_query_mode,
            "index_dir": validation_index_dir,
            "cache_dir": validation_cache_dir,
            "execution": "planned_only" if dry_run else "local_or_cache_execution",
            "stages": [
                "batch_validation_anchor_building", "batch_validation_question_building",
                "batch_validation_routing", "batch_validation_query_planning",
                "batch_validation_execution", "batch_validation_aggregation",
                "batch_validation_metrics",
            ] if external_validation else [],
        },
        "l1_cost_estimate": cost_estimate,
        "processed_prompt_ids": [item["prompt_id"] for item in prompts],
    }
    _write_json(directory / "prompt_bank_manifest.json", build_prompt_bank_manifest(prompts, prompt_bank))
    _write_json(directory / "batch_run_manifest.json", manifest)
    _write_jsonl(directory / "abstract_conflict_candidates.jsonl", candidates)
    _write_jsonl(directory / "conflict_focus_set.jsonl", focus_set)
    _write_jsonl(directory / "conflict_annotation_sample.jsonl", sample)
    write_jsonl(directory / "batch_hypothesis_candidates.jsonl", iter(hypothesis_candidates))
    write_jsonl(directory / "batch_hypothesis_hyperedges.jsonl", iter(hypothesis_hyperedges))
    _write_json(directory / "batch_hypothesis_summary.json", hypothesis_statistics)
    write_annotation_schema(directory / "conflict_annotation_schema.json")
    _write_json(directory / "hypothesis_statistics.json", hypothesis_statistics)
    if merge_knowledge_store:
        from code_engine.corpus.knowledge_merge import merge_run_artifacts_into_knowledge_store
        merge = merge_run_artifacts_into_knowledge_store(directory, corpus_dir, update_global=update_global_knowledge_store, dry_run=not update_global_knowledge_store)
        metrics["knowledge_merge_inserted_count"] = merge.inserted_count
        metrics["knowledge_merge_skipped_duplicate_count"] = merge.skipped_count
    _write_json(directory / "batch_metrics_summary.json", metrics)
    render_batch_discovery_report(metrics, directory / "batch_discovery_report.md")
    return {"run_dir": str(directory), "manifest": manifest, "metrics": metrics, "candidates": candidates, "annotation_sample": sample, "hypotheses": hypothesis_hyperedges, "validation": validation_result}


__all__ = ["run_batch_discovery"]
