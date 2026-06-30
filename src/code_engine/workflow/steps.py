"""Thin workflow adapters around existing scientific modules."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from code_engine.domain.router import default_domain_router
from code_engine.query.intake import parse_research_intake
from code_engine.query.search_planner import LiteratureSearchPlan, build_literature_search_plan


@dataclass
class StepResult:
    status: str = "completed"
    summary: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    api_calls_made: int = 0
    network_calls_made: int = 0
    skipped_reason: str | None = None


def _write(run_dir: Path, name: str, payload: Any) -> str:
    path = run_dir / "artifacts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _read(run_dir: Path, name: str, default: Any = None) -> Any:
    path = run_dir / "artifacts" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    from code_engine.hypothesis.io import iter_jsonl
    return [item for item in iter_jsonl(path)]


def _manifest_map(run_dir: Path) -> dict[str, dict]:
    records = _read_jsonl(run_dir / "artifacts" / "run_paper_manifest.jsonl")
    result = {}
    for item in records:
        for key in (item.get("original_paper_id"), item.get("paper_id"), item.get("canonical_paper_id")):
            if key:
                result[str(key)] = item
    return result


def _attach_run_provenance(records: list[dict], run_dir: Path) -> list[dict]:
    from code_engine.corpus.artifact_provenance import attach_paper_provenance
    manifest = _manifest_map(run_dir)
    return [attach_paper_provenance(item, None, manifest) for item in records]


def _attach_linked_provenance(records: list[dict], run_dir: Path) -> list[dict]:
    from code_engine.corpus.artifact_provenance import attach_linked_paper_provenance
    manifest = _manifest_map(run_dir)
    id_to_paper: dict[str, str] = {}
    for name in ("abstract_l1_claims.jsonl", "fulltext_evidence_records.jsonl", "fulltext_l1_claims.jsonl"):
        for item in _read_jsonl(run_dir / "artifacts" / name):
            paper_id = str(item.get("canonical_paper_id") or item.get("paper_id") or "")
            for key in (item.get("claim_id"), item.get("evidence_id"), item.get("observation_id")):
                if key and paper_id:
                    id_to_paper[str(key)] = paper_id
    output = []
    for item in records:
        paper_ids = [str(value) for name in ("paper_ids", "linked_paper_ids", "linked_canonical_paper_ids") for value in item.get(name, [])]
        for name in ("claim_ids", "linked_abstract_claim_ids", "linked_evidence_ids", "evidence_ids", "input_evidence"):
            paper_ids.extend(id_to_paper[value] for value in map(str, item.get(name, [])) if value in id_to_paper)
        refs = [manifest[paper_id] for paper_id in dict.fromkeys(paper_ids) if paper_id in manifest]
        output.append(attach_linked_paper_provenance(item, refs))
    return output


def _run_id(run_dir: Path) -> str:
    state_path = run_dir / "run_state.json"
    return str(json.loads(state_path.read_text(encoding="utf-8")).get("run_id") or run_dir.name) if state_path.exists() else run_dir.name


def _cached_payload(record: Any, key: str) -> list[dict]:
    value = record.artifact_refs.get(key, [])
    if isinstance(value, list):
        return [dict(item) for item in value]
    path = Path(value) if value else None
    return _read_jsonl(path) if path and path.exists() else []


def _normalize_progressive_records(records: list[dict[str, Any]], profile: dict[str, Any], run_dir: Path, *,
                                   entity_registry_path: str | Path | None = None,
                                   execute: bool = False, network: bool = False, api: bool = False,
                                   entity_network_lookup: bool = False, entity_llm_proposer: bool = False,
                                   entity_resolution_policy: dict | None = None) -> list[dict[str, Any]]:
    """Normalize progressive claims while preserving evidence scope."""

    from code_engine.normalization.registry import LocalBiomedicalRegistry, PILOT_REGISTRY_PATH
    from code_engine.normalization.resolver import ResolverCascade

    registry_path = Path(entity_registry_path) if entity_registry_path else (PILOT_REGISTRY_PATH if profile.get("domain_id") == "neuropharmacology" else None)
    try:
        registry = LocalBiomedicalRegistry(registry_path) if registry_path else None
    except FileNotFoundError:
        registry = None

    resolver = ResolverCascade(
        domain_id=profile.get("domain_id", "general_biomedical"),
        entity_registry_profile=profile.get("entity_registry_profile", "general_entity_resolution_hub"),
        resolver_policy_id=profile.get("resolver_policy_id", "conservative_resolver_v2"),
        run_dir=run_dir,
        registry=registry, execute=execute, network_enabled=network, api_enabled=api,
        entity_network_lookup=entity_network_lookup, entity_llm_proposer=entity_llm_proposer,
        adjudicator_policy=entity_resolution_policy,
    )
    observations = []
    for item in records:
        subject = resolver.resolve_entity(str(item.get("subject_raw") or ""), {"expected_entity_type": item.get("subject_type") or ""})
        obj = resolver.resolve_entity(str(item.get("object_raw") or ""), {"expected_entity_type": item.get("object_type") or ""})
        usable = bool(subject.allow_high_confidence_graph_use and obj.allow_high_confidence_graph_use)
        observation_id = str(item.get("evidence_id") or item.get("claim_id") or "")
        observations.append({
            **item,
            "observation_id": observation_id,
            "triple_id": observation_id,
            "claim_id": item.get("claim_id"),
            "evidence_id": item.get("evidence_id") or item.get("claim_id"),
            "paper_id": item.get("paper_id"),
            "subject": subject.canonical_name or item.get("subject_raw"),
            "object": obj.canonical_name or item.get("object_raw"),
            "normalized_subject": subject.canonical_name,
            "normalized_object": obj.canonical_name,
            "subject_canonical_id": subject.canonical_id,
            "object_canonical_id": obj.canonical_id,
            "subject_canonical_name": subject.canonical_name,
            "object_canonical_name": obj.canonical_name,
            "subject_entity_type": subject.entity_type,
            "object_entity_type": obj.entity_type,
            "subject_normalization_status": subject.normalization_status,
            "object_normalization_status": obj.normalization_status,
            "normalization_status": "resolved" if usable else "low_confidence",
            "normalization_quality": "resolved_or_acceptable" if usable else "low_confidence",
            "allow_high_confidence_graph_use": usable,
            "exclude_from_high_confidence_conflict": not usable,
            "context": dict(item.get("context_slots") or item.get("context_mentions") or {}),
            "normalization": {"subject": subject.model_dump(), "object": obj.model_dump()},
        })
    return observations


def run_intake_step(*, query: str, run_dir: Path, execute: bool, api: bool,
                    allow_uncertain_intake: bool = False, semantic_confidence_threshold: float = 0.6,
                    semantic_llm_client: Any | None = None, **_: Any) -> StepResult:
    intake = parse_research_intake(query, use_api=bool(api and semantic_llm_client is not None), execute=execute, llm_client=semantic_llm_client)
    profile = default_domain_router().get_or_default(intake.research_intent.domain_id)
    intake_path = _write(run_dir, "intake.json", intake)
    profile_path = _write(run_dir, "domain_profile.json", profile.to_dict())
    summary = {
        "domain_id": profile.domain_id, "subdomain_id": profile.subdomain_id,
        "domain_profile_id": profile.profile_id, "prompt_profile_id": profile.prompt_profile_id,
        "entity_registry_profile": profile.entity_registry_profile,
        "validator_profile_id": profile.validator_profile_id,
        "seed_triple_count": len(intake.seed_triples),
        "semantic_mode": intake.semantic_mode, "semantic_confidence": intake.semantic_confidence,
        "requires_manual_review": intake.requires_manual_review,
        "alternative_domains": intake.semantic_intake.get("domain_routing", {}).get("alternative_domains", []),
        "warning_count": len(intake.semantic_warnings),
    }
    warnings = list(intake.ambiguities)
    warnings.extend(intake.semantic_warnings)
    if execute and api and semantic_llm_client is None:
        warnings.append("semantic_llm_client_not_configured_deterministic_intake_used")
    uncertain = intake.semantic_confidence < semantic_confidence_threshold or intake.requires_manual_review
    blocked = bool(execute and uncertain and not allow_uncertain_intake)
    if blocked:
        warnings.append("semantic_intake_below_confidence_threshold_execute_blocked")
    return StepResult(status="blocked" if blocked else "completed", summary=summary, artifacts={"intake": intake_path, "domain_profile": profile_path}, counts={"seed_triple_count": len(intake.seed_triples)}, warnings=warnings, api_calls_made=intake.api_calls_made, skipped_reason="uncertain_semantic_intake" if blocked else None)


def run_search_step(*, run_dir: Path, execute: bool, api: bool, max_papers: int | None, **_: Any) -> StepResult:
    intake_data = _read(run_dir, "intake.json")
    profile_data = _read(run_dir, "domain_profile.json")
    if not intake_data or not profile_data:
        return StepResult(status="blocked", warnings=["intake_artifacts_missing"], skipped_reason="intake_artifacts_missing")
    from code_engine.domain.models import DomainProfile
    from code_engine.query.intake import ResearchIntakeResult
    intake = ResearchIntakeResult.model_validate(intake_data)
    profile_data = dict(profile_data)
    for key in ("aliases", "preferred_validators", "fallback_validators", "required_context_slots", "optional_context_slots", "key_entity_types", "key_relation_types", "key_evidence_types", "warnings"):
        if key in profile_data:
            profile_data[key] = tuple(profile_data[key])
    profile = DomainProfile(**profile_data)
    plan = build_literature_search_plan(intake.research_intent, seed_triples=intake.seed_triples, domain_profile=profile, use_llm=False, semantic_intake=intake.semantic_intake)
    if max_papers is not None:
        plan.max_total_results = max_papers
        for query in plan.pubmed_queries + plan.pmc_queries:
            query.max_results = min(query.max_results, max_papers)
    path = _write(run_dir, "search_plan.json", plan)
    count = len(plan.pubmed_queries) + len(plan.pmc_queries)
    warnings = list(plan.warnings)
    if execute and api:
        warnings.append("api_enabled_but_search_query_generation_remains_deterministic")
    return StepResult(summary={"query_count": count, "domain_id": plan.domain_id, "search_profile_id": plan.search_profile_id, "prompt_profile_id": plan.prompt_profile_id, "validator_profile_id": plan.validator_profile_id, "query_generation_mode": plan.query_generation_mode, "semantic_confidence": plan.semantic_confidence, "manual_review_required": plan.manual_review_required}, artifacts={"search_plan": path}, counts={"search_query_count": count}, warnings=warnings)


def run_acquisition_step(*, run_dir: Path, repository_root: Path, execute: bool, network: bool, max_papers: int | None, **_: Any) -> StepResult:
    plan_data = _read(run_dir, "search_plan.json")
    if not plan_data:
        return StepResult(status="blocked", warnings=["search_plan_missing"], skipped_reason="search_plan_missing")
    plan = LiteratureSearchPlan.model_validate(plan_data)
    acquisition_plan = {"intent_id": plan.intent_id, "queries": [item.model_dump() for item in plan.pmc_queries + plan.pubmed_queries], "max_papers": max_papers or plan.max_total_results, "execute": execute, "network": network}
    plan_path = _write(run_dir, "acquisition_plan.json", acquisition_plan)
    if execute and network:
        from code_engine.acquisition.literature_search import execute_acquisition_plan
        report = execute_acquisition_plan(plan, repository_root=repository_root, execute=True, network=True, max_papers=max_papers or plan.max_total_results)
    else:
        report = {"intent_id": plan.intent_id, "execution_mode": "plan_only", "candidate_papers": list(plan.candidate_papers), "reused_papers": [], "downloaded_papers": [], "skipped_duplicates": [], "network_calls_made": 0, "warnings": ["network_disabled_acquisition_plan_only"]}
    report_path = _write(run_dir, "acquisition_report.json", report)
    summary = {key: len(report.get(key, [])) for key in ("candidate_papers", "reused_papers", "downloaded_papers", "skipped_duplicates")}
    calls = int(report.get("network_calls_made", 0))
    return StepResult(status="completed" if execute and network else "planned", summary=summary, artifacts={"acquisition_plan": plan_path, "acquisition_report": report_path}, counts=summary, warnings=report.get("warnings", []), network_calls_made=calls)


def run_payload_step(
    *, run_dir: Path, execute: bool, query: str = "", repository_root: Path | None = None,
    global_corpus_dir: str | Path | None = None, paper_registry_enabled: bool = True,
    update_global_corpus: bool = False, allow_title_hash_paper_merge: bool = False, **_: Any,
) -> StepResult:
    acquisition = _read(run_dir, "acquisition_report.json", {})
    downloaded = acquisition.get("downloaded_papers", [])
    report = {"payload_count": 0, "chunk_count": 0, "inputs": downloaded, "mode": "execute" if execute else "dry_run"}
    warnings = []
    status = "planned"
    reason = None
    if not downloaded:
        status, reason = "blocked", "no_raw_data_in_run"
        warnings.append("payload_build_blocked_no_raw_data_in_run")
    elif execute:
        from code_engine.preprocessing.payload_builder import build_payloads_for_downloads
        repository_root = Path(_["repository_root"])
        chunks = build_payloads_for_downloads(downloaded, repository_root)
        report.update({"payload_count": len({item["paper_id"] for item in chunks}), "chunk_count": len(chunks), "chunks": chunks})
        status = "completed"
    else:
        status = "planned"
        reason = "execute_required_for_payload_build"
        warnings.append("payload_inputs_available_execution_disabled")
    artifacts = run_dir / "artifacts"
    manifest_artifacts = {}
    dedup = {"total_input_papers": 0, "new_papers": 0, "duplicate_papers": 0, "missing_doi_count": 0, "missing_journal_count": 0}
    if paper_registry_enabled:
        from code_engine.corpus.paper_registry import PaperRegistry
        from code_engine.corpus.reports import build_run_paper_manifest
        corpus = Path(global_corpus_dir) if global_corpus_dir else Path(repository_root or Path.cwd()) / "data/corpus"
        registry = PaperRegistry.load(corpus / "paper_registry", allow_title_hash_merge=allow_title_hash_paper_merge)
        papers, seen = [], set()
        for field in ("candidate_papers", "reused_papers", "downloaded_papers"):
            for paper in acquisition.get(field, []):
                identity = str(paper.get("doi") or paper.get("pmid") or paper.get("pmcid") or paper.get("paper_id") or paper.get("title") or "")
                if identity and identity not in seen:
                    seen.add(identity); papers.append(dict(paper))
        state_path = run_dir / "run_state.json"
        run_id = json.loads(state_path.read_text(encoding="utf-8")).get("run_id", run_dir.name) if state_path.exists() else run_dir.name
        manifest, dedup, by_original = build_run_paper_manifest(papers, registry, str(run_id), query, artifacts)
        for field in ("candidate_papers", "reused_papers", "downloaded_papers"):
            acquisition[field] = [{**paper, **{key: value for key, value in by_original.get(str(paper.get("paper_id") or paper.get("pmcid") or paper.get("pmid") or ""), {}).items() if key not in {"run_id", "query", "warnings"}}} for paper in acquisition.get(field, [])]
        _write(run_dir, "acquisition_report.json", acquisition)
        if update_global_corpus:
            registry.save()
        manifest_artifacts = {"run_paper_manifest": str(artifacts / "run_paper_manifest.jsonl"), "run_bibliographic_index": str(artifacts / "run_bibliographic_index.json"), "paper_deduplication_report": str(artifacts / "paper_deduplication_report.json")}
        warnings.extend(registry.warnings)
    path = _write(run_dir, "payload_report.json", report)
    summary = {**report, **dedup, "paper_registry_enabled": paper_registry_enabled, "global_registry_updated": bool(paper_registry_enabled and update_global_corpus)}
    counts = {"payload_count": report["payload_count"], "chunk_count": report["chunk_count"], "paper_dedup_total": dedup.get("total_input_papers", 0), "paper_dedup_new_count": dedup.get("new_papers", 0), "paper_dedup_duplicate_count": dedup.get("duplicate_papers", 0), "paper_missing_doi_count": dedup.get("missing_doi_count", 0), "paper_missing_journal_count": dedup.get("missing_journal_count", 0)}
    return StepResult(status=status, summary=summary, artifacts={"payload_report": path, **manifest_artifacts}, counts=counts, warnings=warnings, skipped_reason=reason)


def run_abstract_l1_step(
    *, run_dir: Path, execute: bool, api: bool, max_papers: int | None,
    l1_mode: str = "abstract_screening", l1_budget_policy: dict | None = None,
    allow_budget_overrun: bool = False, l1_llm_client=None,
    global_corpus_dir: str | Path | None = None, l1_task_cache_enabled: bool = True,
    allow_compatible_l1_task_reuse: bool = False, force_reprocess_l1: bool = False,
    force_reprocess_paper: list[str] | None = None, update_global_corpus: bool = False,
    repository_root: Path | None = None, **_: Any,
) -> StepResult:
    if l1_mode == "legacy":
        summary = {"l1_mode": l1_mode, "abstract_claim_count": 0, "reason": "legacy_l1_mode"}
        path = _write(run_dir, "abstract_l1_summary.json", summary)
        return StepResult(status="skipped", summary=summary, artifacts={"abstract_l1_summary": path}, skipped_reason="legacy_l1_mode")
    from code_engine.extraction.abstract_screening import run_abstract_l1_screening

    acquisition = _read(run_dir, "acquisition_report.json", {})
    papers = []
    seen = set()
    for field in ("candidate_papers", "reused_papers", "downloaded_papers"):
        for paper in acquisition.get(field, []):
            paper_id = str(paper.get("paper_id") or paper.get("pmcid") or paper.get("pmid") or "")
            if paper_id and paper_id not in seen:
                seen.add(paper_id)
                papers.append(paper)
    profile = _read(run_dir, "domain_profile.json", {})
    cache_hits, cache_misses, reusable_claims, signatures = [], [], [], {}
    misses = []
    cache_dir = (Path(global_corpus_dir) if global_corpus_dir else Path(repository_root or Path.cwd()) / "data/corpus") / "l1_task_cache"
    if l1_task_cache_enabled:
        from code_engine.corpus.corpus_cache import compute_text_hash
        from code_engine.corpus.l1_task_cache import L1TaskSignature, lookup_l1_task_cache
        forced = set(force_reprocess_paper or [])
        for paper in papers:
            canonical = str(paper.get("canonical_paper_id") or paper.get("paper_id") or paper.get("pmid") or "")
            content_hash = compute_text_hash(paper.get("abstract") or paper.get("abstract_text"))
            signature = L1TaskSignature(task_family="abstract_claim_screening", source_scope="abstract", canonical_paper_id=canonical, content_hash=content_hash or "missing", schema_version="abstract_claim_v1", prompt_profile_id=profile.get("prompt_profile_id"), prompt_fingerprint=profile.get("prompt_profile_id"), model_name=type(l1_llm_client).__name__ if l1_llm_client else None, domain_id=profile.get("domain_id"), l1_mode=l1_mode)
            signatures[canonical] = signature
            cached = None if force_reprocess_l1 or canonical in forced else lookup_l1_task_cache(signature, cache_dir)
            reusable = cached and (cached.status == "hit" or (cached.status == "compatible_task_family_hit" and allow_compatible_l1_task_reuse))
            if reusable:
                cache_hits.append({"canonical_paper_id": canonical, "cache_key": cached.task_cache_key, "status": cached.status})
                for claim in _cached_payload(cached, "claims"):
                    reusable_claims.append({**claim, "reused_from_cache": True, "cache_key": cached.task_cache_key, "original_run_id": (cached.run_ids[0] if cached.run_ids else None), "original_artifact_ref": cached.artifact_refs.get("claims")})
            else:
                cache_misses.append({"canonical_paper_id": canonical, "status": "forced" if force_reprocess_l1 or canonical in forced else (cached.status if cached else "miss")})
                misses.append(paper)
    else:
        misses = papers
        cache_misses = [{"canonical_paper_id": paper.get("canonical_paper_id"), "status": "cache_disabled"} for paper in papers]
    output = run_abstract_l1_screening(
        misses, profile, run_dir / "artifacts",
        execute=execute, api_enabled=api,
        max_papers=max_papers or (l1_budget_policy or {}).get("max_papers_per_prompt", 100),
        max_l1_calls=(l1_budget_policy or {}).get("max_l1_calls_per_prompt"),
        budget_policy=l1_budget_policy, llm_client=l1_llm_client,
        allow_budget_overrun=allow_budget_overrun,
    )
    new_claims = _attach_run_provenance(output["claims"], run_dir)
    reusable_claims = _attach_run_provenance(reusable_claims, run_dir)
    output["claims"] = [*reusable_claims, *new_claims]
    from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl
    atomic_write_jsonl(run_dir / "artifacts" / "abstract_l1_claims.jsonl", iter(output["claims"]))
    paper_records = _attach_run_provenance(output["paper_records"], run_dir)
    atomic_write_jsonl(run_dir / "artifacts" / "paper_processing_records.jsonl", iter(paper_records))
    output["paper_records"] = paper_records
    if l1_task_cache_enabled and update_global_corpus:
        from code_engine.corpus.l1_task_cache import L1TaskCache, store_l1_task_cache_record
        by_paper: dict[str, list[dict]] = {}
        for claim in new_claims:
            by_paper.setdefault(str(claim.get("canonical_paper_id") or claim.get("paper_id") or ""), []).append(claim)
        for canonical, claims_for_paper in by_paper.items():
            signature = signatures.get(canonical)
            if signature:
                task_key = L1TaskCache.new_record(signature, _run_id(run_dir), {}, claim_count=len(claims_for_paper)).task_cache_key
                cache_artifact = cache_dir / "artifacts" / f"{task_key}.claims.jsonl"
                atomic_write_jsonl(cache_artifact, iter(claims_for_paper))
                record = L1TaskCache.new_record(signature, _run_id(run_dir), {"claims": str(cache_artifact)}, claim_count=len(claims_for_paper))
                store_l1_task_cache_record(record, cache_dir)
    cache_report = {"total_tasks": len(papers), "hit_count": len(cache_hits), "miss_count": len(cache_misses), "stale_count": sum(item["status"] in {"stale", "incompatible_schema"} for item in cache_misses), "compatible_family_hit_count": sum(item["status"] == "compatible_task_family_hit" for item in [*cache_hits, *cache_misses]), "reused_claim_count": len(reusable_claims), "new_claim_count": len(new_claims), "estimated_api_calls_saved": len(cache_hits)}
    atomic_write_json(run_dir / "artifacts" / "abstract_l1_cache_report.json", cache_report)
    atomic_write_jsonl(run_dir / "artifacts" / "abstract_l1_cache_hits.jsonl", iter(cache_hits))
    atomic_write_jsonl(run_dir / "artifacts" / "abstract_l1_cache_misses.jsonl", iter(cache_misses))
    summary = {"l1_mode": l1_mode, **output["summary"], **cache_report, "abstract_claim_count": len(output["claims"])}
    if summary["budget_report"].get("budget_status") == "blocked" or ("llm_client_not_configured" in summary.get("warnings", []) and bool(misses)):
        status = "blocked"
    else:
        status = "completed" if execute and api else "planned"
    artifacts = {
        "abstract_l1_claims": output["artifacts"].get("claims", ""),
        "abstract_l1_summary": output["artifacts"].get("summary", ""),
        "paper_processing_records": output["artifacts"].get("paper_records", ""),
        "abstract_l1_cache_report": str(run_dir / "artifacts" / "abstract_l1_cache_report.json"),
        "abstract_l1_cache_hits": str(run_dir / "artifacts" / "abstract_l1_cache_hits.jsonl"),
        "abstract_l1_cache_misses": str(run_dir / "artifacts" / "abstract_l1_cache_misses.jsonl"),
    }
    return StepResult(
        status=status, summary=summary, artifacts=artifacts,
        counts={"abstract_claim_count": len(output["claims"]), "abstract_processed_paper_count": summary["abstract_available_count"], "abstract_l1_cache_hit_count": len(cache_hits), "abstract_l1_cache_miss_count": len(cache_misses), "estimated_l1_api_calls_saved": len(cache_hits)},
        warnings=list(summary.get("warnings", [])), api_calls_made=int(summary["api_calls_made"]),
        skipped_reason=("l1_budget_exceeded" if summary["budget_report"].get("budget_status") == "blocked" else "l1_llm_client_not_configured") if status == "blocked" else ("abstract_l1_planning_only" if status == "planned" else None),
    )


def run_l2_abstract_step(*, run_dir: Path, l1_mode: str = "abstract_screening",
                         entity_registry_path: str | Path | None = None, execute: bool = False,
                         network: bool = False, api: bool = False, entity_network_lookup: bool = False,
                         entity_llm_proposer: bool = False, entity_resolution_policy=None, **_: Any) -> StepResult:
    if l1_mode == "legacy":
        summary = {"normalized_observation_count": 0, "reason": "legacy_l1_mode"}
        path = _write(run_dir, "l2_abstract_summary.json", summary)
        return StepResult(status="skipped", summary=summary, artifacts={"l2_abstract_summary": path}, skipped_reason="legacy_l1_mode")
    claims = _read_jsonl(run_dir / "artifacts" / "abstract_l1_claims.jsonl")
    observations = _normalize_progressive_records(
        claims, _read(run_dir, "domain_profile.json", {}), run_dir,
        entity_registry_path=entity_registry_path, execute=execute, network=network, api=api,
        entity_network_lookup=entity_network_lookup, entity_llm_proposer=entity_llm_proposer,
        entity_resolution_policy=entity_resolution_policy if isinstance(entity_resolution_policy, dict) else None,
    )
    observations_path = _write(run_dir, "l2_abstract_observations.json", observations)
    summary = {
        "normalized_observation_count": len(observations),
        "high_confidence_observation_count": sum(bool(item.get("allow_high_confidence_graph_use")) for item in observations),
        "excluded_low_confidence_count": sum(not bool(item.get("allow_high_confidence_graph_use")) for item in observations),
        "source_scope": "abstract",
    }
    summary_path = _write(run_dir, "l2_abstract_summary.json", summary)
    pilot_terms = {"ketamine", "esketamine", "arketamine", "norketamine", "hydroxynorketamine", "bdnf", "mtor"}
    pilot_mentions = sum(str(item.get("subject_raw") or "").casefold() in pilot_terms or str(item.get("object_raw") or "").casefold() in pilot_terms for item in claims)
    low_pilot_coverage = bool(pilot_mentions and summary["high_confidence_observation_count"] < max(1, pilot_mentions // 2))
    return StepResult(
        status="completed" if observations else "planned", summary=summary,
        artifacts={"l2_abstract_observations": observations_path, "l2_abstract_summary": summary_path},
        counts={key: value for key, value in summary.items() if key.endswith("_count")},
        warnings=(["entity_resolution_low_coverage_for_pilot_query"] if low_pilot_coverage else []) + ([] if observations else ["no_abstract_claims_to_normalize"]),
    )


def run_abstract_conflict_screening_step(
    *, run_dir: Path, l1_mode: str = "abstract_screening",
    min_abstract_conflict_entropy: float = 0.65,
    min_abstract_evidence_count: int = 3, **_: Any,
) -> StepResult:
    if l1_mode == "legacy":
        summary = {"candidate_count": 0, "focus_set_count": 0, "reason": "legacy_l1_mode"}
        path = _write(run_dir, "abstract_conflict_summary.json", summary)
        return StepResult(status="skipped", summary=summary, artifacts={"abstract_conflict_summary": path}, skipped_reason="legacy_l1_mode")
    from code_engine.graph.abstract_conflict_screening import build_abstract_conflict_candidates

    claims = _read_jsonl(run_dir / "artifacts" / "abstract_l1_claims.jsonl")
    observations = _read(run_dir, "l2_abstract_observations.json", [])
    output = build_abstract_conflict_candidates(
        claims, observations, min_evidence_count=min_abstract_evidence_count,
        min_entropy=min_abstract_conflict_entropy, run_dir=run_dir / "artifacts",
    )
    from code_engine.corpus.io import atomic_write_jsonl
    output["candidates"] = _attach_linked_provenance(output["candidates"], run_dir)
    output["focus_set"] = _attach_linked_provenance(output["focus_set"], run_dir)
    atomic_write_jsonl(Path(output["artifacts"]["candidates"]), iter(output["candidates"]))
    atomic_write_jsonl(Path(output["artifacts"]["focus_set"]), iter(output["focus_set"]))
    output["summary"]["top_conflicts"] = [{key: item.get(key) for key in ("candidate_id", "subject_name", "object_name", "abstract_entropy", "linked_dois", "linked_titles", "linked_journals", "publication_year_range")} for item in output["candidates"][:10]]
    artifacts = {
        "abstract_conflict_candidates": output["artifacts"]["candidates"],
        "conflict_focus_set": output["artifacts"]["focus_set"],
        "abstract_conflict_summary": output["artifacts"]["summary"],
    }
    return StepResult(
        status="completed" if claims else "planned", summary=output["summary"], artifacts=artifacts,
        counts={"abstract_conflict_candidate_count": len(output["candidates"])},
        warnings=[] if claims else ["abstract_conflict_screening_planned_no_claims"],
    )


def run_fulltext_escalation_step(
    *, run_dir: Path, l1_mode: str = "abstract_screening",
    enable_fulltext_escalation: bool = False,
    max_fulltext_papers_per_conflict: int = 5, **_: Any,
) -> StepResult:
    enabled = l1_mode in {"progressive_fulltext", "fulltext_oracle"} and enable_fulltext_escalation
    from code_engine.extraction.fulltext_escalation import plan_fulltext_escalation

    candidates = _read_jsonl(run_dir / "artifacts" / "conflict_focus_set.jsonl") if enabled else []
    records = _read_jsonl(run_dir / "artifacts" / "paper_processing_records.jsonl")
    output = plan_fulltext_escalation(
        candidates, records, max_papers_per_conflict=max_fulltext_papers_per_conflict,
        run_dir=run_dir / "artifacts",
    )
    summary = {**output["summary"], "enabled": enabled, "l1_mode": l1_mode}
    status = "planned" if enabled else "skipped"
    reason = None if enabled else "fulltext_escalation_not_enabled"
    return StepResult(
        status=status, summary=summary,
        artifacts={"fulltext_escalation_plan": output["artifacts"]["plan"], "fulltext_escalation_papers": output["artifacts"]["papers"]},
        counts={
            "fulltext_escalation_candidate_count": len(output["selected_papers"]),
            "fulltext_available_paper_count": summary["selected_paper_count"],
            "fulltext_unavailable_paper_count": summary["coverage_gap_count"],
        },
        warnings=[reason] if reason else [], skipped_reason=reason,
    )


def run_fulltext_l1_step(
    *, run_dir: Path, execute: bool, api: bool, repository_root: Path,
    l1_mode: str = "abstract_screening", enable_fulltext_escalation: bool = False,
    max_sections_per_paper: int = 5, max_spans_per_paper: int = 8,
    l1_budget_policy: dict | None = None, allow_budget_overrun: bool = False,
    l1_llm_client=None, global_corpus_dir: str | Path | None = None,
    l1_task_cache_enabled: bool = True, allow_compatible_l1_task_reuse: bool = False,
    force_reprocess_l1: bool = False, force_reprocess_paper: list[str] | None = None,
    update_global_corpus: bool = False, **_: Any,
) -> StepResult:
    enabled = l1_mode in {"progressive_fulltext", "fulltext_oracle"} and enable_fulltext_escalation
    selected = _read_jsonl(run_dir / "artifacts" / "fulltext_escalation_papers.jsonl") if enabled else []
    candidates = {str(item.get("candidate_id")): item for item in _read_jsonl(run_dir / "artifacts" / "abstract_conflict_candidates.jsonl")}
    acquisition = _read(run_dir, "acquisition_report.json", {})
    papers = {}
    for field in ("candidate_papers", "reused_papers", "downloaded_papers"):
        for paper in acquisition.get(field, []):
            paper_id = str(paper.get("paper_id") or paper.get("pmcid") or paper.get("pmid") or "")
            if paper_id:
                papers[paper_id] = paper
    from code_engine.extraction.evidence_span_selector import select_evidence_spans
    from code_engine.extraction.progressive_l1 import run_fulltext_evidence_l1
    from code_engine.extraction.section_ranker import rank_fulltext_sections_for_conflict

    spans = []
    for item in selected:
        paper = dict(papers.get(str(item.get("paper_id")), {}))
        path = paper.get("full_text_path") or paper.get("raw_path")
        if path and not paper.get("full_text") and not paper.get("sections"):
            source = Path(path)
            if not source.is_absolute():
                source = repository_root / source
            if source.exists():
                paper["full_text"] = source.read_text(encoding="utf-8")
        candidate = candidates.get(str(item.get("candidate_id")), item)
        ranked = rank_fulltext_sections_for_conflict(paper, candidate, _read(run_dir, "domain_profile.json", {}), max_sections_per_paper)
        selected_spans = select_evidence_spans(ranked, candidate, max_spans_per_paper=max_spans_per_paper)
        for span in selected_spans:
            span["canonical_paper_id"] = paper.get("canonical_paper_id") or span.get("paper_id")
        spans.extend(selected_spans)
    spans_path = run_dir / "artifacts" / "selected_fulltext_spans.jsonl"
    spans_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in spans), encoding="utf-8")
    profile = _read(run_dir, "domain_profile.json", {})
    cache_dir = (Path(global_corpus_dir) if global_corpus_dir else repository_root / "data/corpus") / "l1_task_cache"
    cache_hits, cache_misses, reusable_evidence, reusable_claims, signatures = [], [], [], [], {}
    miss_spans = []
    if l1_task_cache_enabled:
        from code_engine.corpus.corpus_cache import compute_text_hash
        from code_engine.corpus.l1_task_cache import L1TaskSignature, lookup_l1_task_cache
        forced = set(force_reprocess_paper or [])
        for span in spans:
            canonical = str(span.get("canonical_paper_id") or span.get("paper_id") or "")
            signature = L1TaskSignature(task_family="fulltext_evidence_extraction", source_scope="span", canonical_paper_id=canonical, content_hash=compute_text_hash(span.get("text")) or "missing", schema_version="fulltext_evidence_v1", prompt_profile_id=profile.get("prompt_profile_id"), prompt_fingerprint=profile.get("prompt_profile_id"), model_name=type(l1_llm_client).__name__ if l1_llm_client else None, domain_id=profile.get("domain_id"), l1_mode=l1_mode)
            signatures[str(span.get("span_id") or "")] = signature
            cached = None if force_reprocess_l1 or canonical in forced else lookup_l1_task_cache(signature, cache_dir)
            reusable = cached and (cached.status == "hit" or (cached.status == "compatible_task_family_hit" and allow_compatible_l1_task_reuse))
            if reusable:
                cache_hits.append({"canonical_paper_id": canonical, "span_id": span.get("span_id"), "cache_key": cached.task_cache_key, "status": cached.status})
                metadata = {"reused_from_cache": True, "cache_key": cached.task_cache_key, "original_run_id": (cached.run_ids[0] if cached.run_ids else None)}
                reusable_evidence.extend({**item, **metadata, "original_artifact_ref": cached.artifact_refs.get("evidence_records")} for item in _cached_payload(cached, "evidence_records"))
                reusable_claims.extend({**item, **metadata, "original_artifact_ref": cached.artifact_refs.get("claims")} for item in _cached_payload(cached, "claims"))
            else:
                miss_spans.append(span)
                cache_misses.append({"canonical_paper_id": canonical, "span_id": span.get("span_id"), "status": "forced" if force_reprocess_l1 or canonical in forced else (cached.status if cached else "miss")})
    else:
        miss_spans = spans
        cache_misses = [{"canonical_paper_id": span.get("canonical_paper_id"), "span_id": span.get("span_id"), "status": "cache_disabled"} for span in spans]
    output = run_fulltext_evidence_l1(
        miss_spans, list(candidates.values()), profile,
        run_dir / "artifacts", execute=execute and enabled, api_enabled=api and enabled,
        budget_policy=l1_budget_policy, llm_client=l1_llm_client,
        allow_budget_overrun=allow_budget_overrun,
    )
    new_evidence = _attach_run_provenance(output["evidence_records"], run_dir)
    new_claims = _attach_run_provenance(output["claims"], run_dir)
    output["evidence_records"] = [*_attach_run_provenance(reusable_evidence, run_dir), *new_evidence]
    output["claims"] = [*_attach_run_provenance(reusable_claims, run_dir), *new_claims]
    from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl
    atomic_write_jsonl(run_dir / "artifacts" / "fulltext_evidence_records.jsonl", iter(output["evidence_records"]))
    atomic_write_jsonl(run_dir / "artifacts" / "fulltext_l1_claims.jsonl", iter(output["claims"]))
    if l1_task_cache_enabled and update_global_corpus:
        from code_engine.corpus.l1_task_cache import L1TaskCache, store_l1_task_cache_record
        for span_id, signature in signatures.items():
            evidence = [item for item in new_evidence if str(item.get("evidence_span_id") or "") == span_id]
            claims = [item for item in new_claims if str(item.get("evidence_span_id") or "") == span_id]
            if not evidence and not claims:
                continue
            seed = L1TaskCache.new_record(signature, _run_id(run_dir), {}, claim_count=len(claims), evidence_count=len(evidence))
            evidence_path = cache_dir / "artifacts" / f"{seed.task_cache_key}.evidence.jsonl"
            claims_path = cache_dir / "artifacts" / f"{seed.task_cache_key}.claims.jsonl"
            atomic_write_jsonl(evidence_path, iter(evidence)); atomic_write_jsonl(claims_path, iter(claims))
            store_l1_task_cache_record(L1TaskCache.new_record(signature, _run_id(run_dir), {"evidence_records": str(evidence_path), "claims": str(claims_path)}, claim_count=len(claims), evidence_count=len(evidence)), cache_dir)
    cache_report = {"total_tasks": len(spans), "hit_count": len(cache_hits), "miss_count": len(cache_misses), "stale_count": sum(item["status"] in {"stale", "incompatible_schema"} for item in cache_misses), "compatible_family_hit_count": sum(item["status"] == "compatible_task_family_hit" for item in [*cache_hits, *cache_misses]), "reused_claim_count": len(reusable_claims), "reused_evidence_count": len(reusable_evidence), "new_claim_count": len(new_claims), "new_evidence_count": len(new_evidence), "estimated_api_calls_saved": len(cache_hits)}
    atomic_write_json(run_dir / "artifacts" / "fulltext_l1_cache_report.json", cache_report)
    atomic_write_jsonl(run_dir / "artifacts" / "fulltext_l1_cache_hits.jsonl", iter(cache_hits)); atomic_write_jsonl(run_dir / "artifacts" / "fulltext_l1_cache_misses.jsonl", iter(cache_misses))
    summary = {**output["summary"], **cache_report, "enabled": enabled, "ranked_span_count": len(spans), "l1_mode": l1_mode, "fulltext_evidence_count": len(output["evidence_records"]), "fulltext_claim_count": len(output["claims"])}
    budget_blocked = summary["budget_report"].get("budget_status") == "blocked"
    client_missing = "llm_client_not_configured" in summary.get("warnings", []) and bool(miss_spans)
    return StepResult(
        status="blocked" if budget_blocked or client_missing else ("completed" if enabled and execute and api and spans else ("planned" if enabled else "skipped")),
        summary=summary,
        artifacts={
            "selected_fulltext_spans": str(spans_path),
            "fulltext_evidence_records": output["artifacts"].get("evidence_records", ""),
            "fulltext_l1_claims": output["artifacts"].get("claims", ""),
            "fulltext_l1_summary": output["artifacts"].get("summary", ""),
            "fulltext_l1_cache_report": str(run_dir / "artifacts" / "fulltext_l1_cache_report.json"),
            "fulltext_l1_cache_hits": str(run_dir / "artifacts" / "fulltext_l1_cache_hits.jsonl"),
            "fulltext_l1_cache_misses": str(run_dir / "artifacts" / "fulltext_l1_cache_misses.jsonl"),
        },
        counts={"fulltext_evidence_count": len(output["evidence_records"]), "fulltext_l1_cache_hit_count": len(cache_hits), "fulltext_l1_cache_miss_count": len(cache_misses), "estimated_l1_api_calls_saved": len(cache_hits)},
        warnings=list(summary.get("warnings", [])) + ([] if enabled else ["fulltext_escalation_not_enabled"]),
        api_calls_made=int(summary["api_calls_made"]),
        skipped_reason="l1_budget_exceeded" if budget_blocked else ("l1_llm_client_not_configured" if client_missing else (None if enabled else "fulltext_escalation_not_enabled")),
    )


def run_l2_fulltext_step(*, run_dir: Path, l1_mode: str = "abstract_screening",
                         entity_registry_path: str | Path | None = None, execute: bool = False,
                         network: bool = False, api: bool = False, entity_network_lookup: bool = False,
                         entity_llm_proposer: bool = False, entity_resolution_policy=None, **_: Any) -> StepResult:
    enabled = l1_mode in {"progressive_fulltext", "fulltext_oracle"}
    evidence = _read_jsonl(run_dir / "artifacts" / "fulltext_evidence_records.jsonl") if enabled else []
    observations = _normalize_progressive_records(
        evidence, _read(run_dir, "domain_profile.json", {}), run_dir,
        entity_registry_path=entity_registry_path, execute=execute, network=network, api=api,
        entity_network_lookup=entity_network_lookup, entity_llm_proposer=entity_llm_proposer,
        entity_resolution_policy=entity_resolution_policy if isinstance(entity_resolution_policy, dict) else None,
    )
    path = _write(run_dir, "l2_fulltext_observations.json", observations)
    summary = {
        "normalized_fulltext_observation_count": len(observations),
        "high_confidence_fulltext_observation_count": sum(bool(item.get("allow_high_confidence_graph_use")) for item in observations),
        "source_scope": "full_text",
    }
    summary_path = _write(run_dir, "l2_fulltext_summary.json", summary)
    return StepResult(
        status="completed" if observations else ("planned" if enabled else "skipped"),
        summary=summary, artifacts={"l2_fulltext_observations": path, "l2_fulltext_summary": summary_path},
        counts={key: value for key, value in summary.items() if key.endswith("_count")},
        warnings=[] if observations or not enabled else ["no_fulltext_evidence_to_normalize"],
        skipped_reason=None if enabled else "progressive_fulltext_not_selected",
    )


def run_fulltext_conflict_confirmation_step(*, run_dir: Path, l1_mode: str = "abstract_screening", **_: Any) -> StepResult:
    from code_engine.graph.fulltext_conflict_confirmation import confirm_conflicts_with_fulltext_evidence

    enabled = l1_mode in {"progressive_fulltext", "fulltext_oracle"}
    candidates = _read_jsonl(run_dir / "artifacts" / "abstract_conflict_candidates.jsonl") if enabled else []
    evidence = _read_jsonl(run_dir / "artifacts" / "fulltext_evidence_records.jsonl") if enabled else []
    observations = _read(run_dir, "l2_fulltext_observations.json", []) if enabled else []
    output = confirm_conflicts_with_fulltext_evidence(candidates, evidence, observations, run_dir=run_dir / "artifacts")
    from code_engine.corpus.io import atomic_write_jsonl
    output["confirmations"] = _attach_linked_provenance(output["confirmations"], run_dir)
    atomic_write_jsonl(Path(output["artifacts"]["confirmations"]), iter(output["confirmations"]))
    return StepResult(
        status="completed" if evidence else ("planned" if enabled else "skipped"),
        summary=output["summary"],
        artifacts={"fulltext_conflict_confirmation": output["artifacts"]["confirmations"], "fulltext_conflict_summary": output["artifacts"]["summary"]},
        counts={key: value for key, value in output["summary"].items() if key.endswith("_count")},
        warnings=[] if evidence or not enabled else ["fulltext_confirmation_planned_insufficient_coverage"],
        skipped_reason=None if enabled else "progressive_fulltext_not_selected",
    )


def run_l1_step(*, run_dir: Path, execute: bool, api: bool, l1_mode: str = "legacy", **kwargs: Any) -> StepResult:
    if l1_mode != "legacy":
        summary = {"l1_mode": l1_mode, "extracted_claim_count": 0, "outputs": [], "reason": "progressive_l1_mode_uses_separate_steps"}
        path = _write(run_dir, "l1_summary.json", summary)
        return StepResult(status="skipped", summary=summary, artifacts={"l1_summary": path}, skipped_reason="progressive_l1_mode")
    profile = _read(run_dir, "domain_profile.json", {})
    payload = _read(run_dir, "payload_report.json", {})
    chunks = list(payload.get("chunks", []))
    plan = {"prompt_profile_id": profile.get("prompt_profile_id"), "domain_id": profile.get("domain_id"), "reused_chunks": 0, "chunks_need_l1": len(chunks), "execute": execute, "api": api}
    plan_path = _write(run_dir, "l1_plan.json", plan)
    result = {"chunks_reused": [], "chunks_extracted": [], "extraction_needed": [], "errors": [], "api_calls_made": 0}
    if chunks:
        from code_engine.domain.models import DomainProfile
        from code_engine.extraction.l1_extractor import execute_l1_extraction
        profile_payload = dict(profile)
        for key in ("aliases", "preferred_validators", "fallback_validators", "required_context_slots", "optional_context_slots", "key_entity_types", "key_relation_types", "key_evidence_types", "warnings"):
            if key in profile_payload:
                profile_payload[key] = tuple(profile_payload[key])
        result = execute_l1_extraction(chunks, repository_root=str(kwargs["repository_root"]), execute=execute, api=api, domain_profile=DomainProfile(**profile_payload))
    summary = {**plan, "reused_chunks": len(result["chunks_reused"]), "chunks_need_l1": len(result["extraction_needed"]), "extracted_claim_count": len(result["chunks_extracted"]), "api_calls_made": int(result["api_calls_made"]), "outputs": result["chunks_extracted"], "errors": result["errors"]}
    summary_path = _write(run_dir, "l1_summary.json", summary)
    reason = "no_weighted_payloads" if not chunks else ("api_disabled_l1_plan_only" if not api else None)
    status = "blocked" if not chunks else ("completed" if execute and api and not result["errors"] else "planned")
    return StepResult(status=status, summary=summary, artifacts={"l1_plan": plan_path, "l1_summary": summary_path}, counts={"reused_chunks": summary["reused_chunks"], "chunks_need_l1": summary["chunks_need_l1"], "extracted_claim_count": summary["extracted_claim_count"]}, warnings=([reason] if reason else []) + [str(item) for item in result["errors"]], api_calls_made=summary["api_calls_made"], skipped_reason=reason)


def _blocked_summary_step(filename: str, artifact_key: str, reason: str, summary: dict[str, Any], counts: dict[str, int] | None = None) -> Callable[..., StepResult]:
    def run(*, run_dir: Path, **_: Any) -> StepResult:
        path = _write(run_dir, filename, summary)
        return StepResult(status="blocked", summary=summary, artifacts={artifact_key: path}, counts=counts or {}, warnings=[reason], skipped_reason=reason)
    return run


def run_l1_5_step(*, run_dir: Path, execute: bool, repository_root: Path, l1_mode: str = "legacy", **_: Any) -> StepResult:
    if l1_mode != "legacy":
        summary = {"refined_claim_count": 0, "outputs": [], "reason": "progressive_l1_has_direct_scope_specific_l2"}
        path = _write(run_dir, "l1_5_summary.json", summary)
        return StepResult(status="skipped", summary=summary, artifacts={"l1_5_summary": path}, skipped_reason="progressive_l1_mode")
    l1 = _read(run_dir, "l1_summary.json", {})
    outputs = [repository_root / item["output_path"] for item in l1.get("outputs", []) if item.get("output_path")]
    refined = []
    if execute and outputs:
        from code_engine.extraction.l1_refiner import refine_l1_file
        target_dir = run_dir / "artifacts" / "l1_5_data"
        for index, source in enumerate(outputs):
            target = target_dir / f"{source.stem}_{index}_refined.json"
            result = refine_l1_file(source, target)
            refined.append({"input": str(source), "output": str(target), "refined_claim_count": len(result.get("refined_claims", []))})
    summary = {"refined_claim_count": sum(item["refined_claim_count"] for item in refined), "outputs": refined}
    path = _write(run_dir, "l1_5_summary.json", summary)
    reason = None if refined else "no_l1_claims_in_run"
    return StepResult(status="completed" if refined else "blocked", summary=summary, artifacts={"l1_5_summary": path}, counts={"refined_claim_count": summary["refined_claim_count"]}, warnings=[reason] if reason else [], skipped_reason=reason)


def run_l2_step(*, run_dir: Path, execute: bool, network: bool = False, api: bool = False,
                entity_network_lookup: bool = False, entity_llm_proposer: bool = False,
                entity_resolution_policy=None, entity_external_clients=None,
                entity_llm_client=None, l1_mode: str = "legacy", **_: Any) -> StepResult:
    if l1_mode != "legacy":
        summary = {"resolved_count": 0, "reason": "progressive_l1_uses_l2_abstract_and_l2_fulltext"}
        observations_path = _write(run_dir, "l2_observations.json", [])
        summary_path = _write(run_dir, "l2_normalization_audit.json", summary)
        return StepResult(status="skipped", summary=summary, artifacts={"l2_observations": observations_path, "l2_normalization_audit": summary_path}, skipped_reason="progressive_l1_mode")
    refined_dir = run_dir / "artifacts" / "l1_5_data"
    observations, audit = [], []
    artifacts_dir = run_dir / "artifacts"
    candidates_path = artifacts_dir / "entity_resolution_candidates.jsonl"
    decisions_path = artifacts_dir / "entity_resolution_decisions.jsonl"
    entity_audit_path = artifacts_dir / "entity_resolution_audit.json"
    policy = None
    if entity_resolution_policy:
        if isinstance(entity_resolution_policy, dict):
            policy = entity_resolution_policy
        else:
            policy_path = Path(entity_resolution_policy)
            if policy_path.exists():
                policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if execute and refined_dir.exists():
        from code_engine.graph.ontology_alignment import extract_normalized_observations
        from code_engine.normalization.resolver import ResolverCascade
        profile = _read(run_dir, "domain_profile.json", {})
        resolver = ResolverCascade(domain_id=profile.get("domain_id", "general_biomedical"), entity_registry_profile=profile.get("entity_registry_profile", "general_entity_resolution_hub"), resolver_policy_id=profile.get("resolver_policy_id", "conservative_resolver_v2"), run_dir=run_dir, execute=execute, network_enabled=network, api_enabled=api, entity_network_lookup=entity_network_lookup, entity_llm_proposer=entity_llm_proposer, external_clients=entity_external_clients, llm_client=entity_llm_client, adjudicator_policy=policy)
        observations, audit = extract_normalized_observations(str(refined_dir), None, [], resolver=resolver)
    candidates_path.touch(exist_ok=True)
    decisions_path.touch(exist_ok=True)
    if not entity_audit_path.exists():
        entity_audit_path.write_text(json.dumps({"total_mentions": 0, "status_counts": {}, "provider_usage_counts": {}, "network_calls_made": 0, "api_calls_made": 0}, indent=2), encoding="utf-8")
    entity_audit = json.loads(entity_audit_path.read_text(encoding="utf-8"))
    statuses: dict[str, int] = {}
    for item in audit:
        status = str(item.get("normalization_status", "unknown"))
        statuses[status] = statuses.get(status, 0) + 1
    hub_statuses = entity_audit.get("status_counts", {})
    summary = {"total_mentions": int(entity_audit.get("total_mentions", 0)), "resolved_curated_count": hub_statuses.get("resolved_curated", 0), "resolved_external_grounded_count": hub_statuses.get("resolved_external_grounded", 0), "resolved_cache_count": hub_statuses.get("resolved_cache", 0), "ambiguous_count": hub_statuses.get("ambiguous", statuses.get("ambiguous", 0)), "unresolved_count": hub_statuses.get("unresolved", 0), "manual_review_required_count": hub_statuses.get("manual_review_required", 0), "llm_suggestion_ungrounded_count": hub_statuses.get("llm_suggestion_ungrounded", 0), "provider_usage_counts": entity_audit.get("provider_usage_counts", {}), "resolved_count": statuses.get("resolved", 0), "unresolved_fallback_count": statuses.get("unresolved_fallback", 0), "excluded_low_confidence_count": sum(not item.get("allow_high_confidence_graph_use", False) for item in audit), "normalization_records": audit}
    path = _write(run_dir, "l2_normalization_audit.json", summary)
    observations_path = _write(run_dir, "l2_observations.json", observations)
    reason = None if observations else "no_l1_5_claims_in_run"
    hub_artifacts = {"entity_resolution_candidates": str(candidates_path), "entity_resolution_decisions": str(decisions_path), "entity_resolution_audit": str(entity_audit_path)}
    return StepResult(status="completed" if observations else "blocked", summary=summary, artifacts={"l2_normalization_audit": path, "l2_observations": observations_path, **hub_artifacts}, counts={key: value for key, value in summary.items() if key.endswith("_count") or key == "total_mentions"}, warnings=[reason] if reason else [], api_calls_made=int(entity_audit.get("api_calls_made", 0)), network_calls_made=int(entity_audit.get("network_calls_made", 0)), skipped_reason=reason)


def run_conflict_step(*, run_dir: Path, execute: bool, l1_mode: str = "legacy", **_: Any) -> StepResult:
    observations = _read(run_dir, "l2_observations.json", []) if l1_mode == "legacy" else _read(run_dir, "l2_fulltext_observations.json", [])
    edges, graph, attributions, audit = [], [], [], {}
    if execute and observations:
        from code_engine.graph.conflict_discovery import build_conflict_graph
        graph, edges, attributions, audit = build_conflict_graph(observations, latent_pool=[])
    types = {"Type I": 0, "Type II": 0, "Type III": 0, "Uncontested": 0}
    for edge in graph:
        key = edge.get("conflict_attribution_type", "Uncontested")
        types[key] = types.get(key, 0) + 1
    summary = {"conflict_edge_count": len(edges), "uncontested_count": types["Uncontested"], "type_i_count": types["Type I"], "type_ii_count": types["Type II"], "type_iii_count": types["Type III"], "skipped_low_confidence_observation_count": int(audit.get("skipped_low_confidence_observation_count", 0)), "conflict_edges": edges, "context_attributions": attributions}
    path = _write(run_dir, "conflict_graph_summary.json", summary)
    artifacts = {"conflict_graph_summary": path}
    mechanism_path = run_dir / "artifacts" / "mechanism_graph.json"
    if mechanism_path.exists():
        from code_engine.mechanism.conflict_annotator import annotate_mechanism_graph_with_conflicts
        from code_engine.mechanism.io import load_mechanism_graph, save_mechanism_graph
        graph = annotate_mechanism_graph_with_conflicts(load_mechanism_graph(mechanism_path), edges, attributions)
        save_mechanism_graph(graph, mechanism_path)
        annotated_path = save_mechanism_graph(graph, run_dir / "artifacts" / "mechanism_graph_annotated.json")
        annotation_path = _write(run_dir, "mechanism_conflict_annotations.json", [item.model_dump() for item in graph.conflict_annotations])
        artifacts.update({"mechanism_graph": str(mechanism_path), "mechanism_graph_annotated": str(annotated_path), "mechanism_conflict_annotations": annotation_path})
        summary["mechanism_conflict_annotation_count"] = len(graph.conflict_annotations)
        summary["mechanism_graph_annotated"] = True
    reason = None if observations else "no_normalized_observations_in_run"
    return StepResult(status="completed" if observations else "blocked", summary=summary, artifacts=artifacts, counts={key: value for key, value in summary.items() if key.endswith("_count")}, warnings=[reason] if reason else [], skipped_reason=reason)
def run_mechanism_step(*, run_dir: Path, execute: bool, l1_mode: str = "legacy", **_: Any) -> StepResult:
    observations = _read(run_dir, "l2_observations.json", []) if l1_mode == "legacy" else _read(run_dir, "l2_fulltext_observations.json", [])
    if not observations:
        summary = {"mechanism_node_count": 0, "mechanism_edge_count": 0, "mechanism_path_count": 0, "mechanism_conflict_annotation_count": 0, "reason": "no_l2_observations_in_run"}
        path = _write(run_dir, "mechanism_graph_summary.json", summary)
        return StepResult(status="blocked", summary=summary, artifacts={"mechanism_graph_summary": path}, counts={key: value for key, value in summary.items() if key.endswith("_count")}, warnings=["mechanism_build_blocked_no_l2_observations"], skipped_reason="no_l2_observations_in_run")
    if not execute:
        summary = {"mechanism_node_count": 0, "mechanism_edge_count": 0, "mechanism_path_count": 0, "mechanism_conflict_annotation_count": 0, "candidate_observation_count": len(observations), "reason": "execute_required_for_mechanism_build"}
        path = _write(run_dir, "mechanism_graph_summary.json", summary)
        return StepResult(status="planned", summary=summary, artifacts={"mechanism_graph_summary": path}, counts={key: value for key, value in summary.items() if key.endswith("_count")}, warnings=["mechanism_graph_planned_execution_disabled"], skipped_reason="execute_required_for_mechanism_build")
    from code_engine.mechanism.graph_builder import build_mechanism_graph
    from code_engine.mechanism.io import save_mechanism_graph
    from code_engine.mechanism.reports import mechanism_graph_summary, render_mechanism_graph_report
    profile = _read(run_dir, "domain_profile.json", {})
    evidence = _read(run_dir, "evidence_records.json", []) if l1_mode == "legacy" else _read_jsonl(run_dir / "artifacts" / "fulltext_evidence_records.jsonl")
    claims = []
    if l1_mode == "legacy":
        for item in _read(run_dir, "l1_summary.json", {}).get("outputs", []):
            source = Path(_["repository_root"]) / item.get("output_path", "")
            if source.is_file():
                payload = json.loads(source.read_text(encoding="utf-8"))
                claims.extend(payload if isinstance(payload, list) else [payload])
    else:
        claims = _read_jsonl(run_dir / "artifacts" / "fulltext_l1_claims.jsonl")
    graph = build_mechanism_graph(observations, evidence, claims, profile)
    graph_path = save_mechanism_graph(graph, run_dir / "artifacts" / "mechanism_graph.json")
    graph_payload = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    graph_payload["nodes"] = _attach_linked_provenance(graph_payload.get("nodes", []), run_dir)
    graph_payload["edges"] = _attach_linked_provenance(graph_payload.get("edges", []), run_dir)
    graph_payload["paths"] = _attach_linked_provenance(graph_payload.get("paths", []), run_dir)
    from code_engine.corpus.io import atomic_write_json
    atomic_write_json(Path(graph_path), graph_payload)
    report_payload = mechanism_graph_summary(graph)
    summary_path = _write(run_dir, "mechanism_graph_summary.json", report_payload)
    annotation_path = _write(run_dir, "mechanism_conflict_annotations.json", [])
    report_path = render_mechanism_graph_report(graph, run_dir / "artifacts" / "mechanism_graph_report.md")
    counts = {"mechanism_node_count": len(graph.nodes), "mechanism_edge_count": len(graph.edges), "mechanism_path_count": len(graph.paths), "mechanism_conflict_annotation_count": 0}
    return StepResult(status="completed", summary={**report_payload, **counts}, artifacts={"mechanism_graph": str(graph_path), "mechanism_graph_summary": summary_path, "mechanism_conflict_annotations": annotation_path, "mechanism_graph_report": str(report_path)}, counts=counts, warnings=graph.warnings)


def run_hypothesis_step(*, run_dir: Path, execute: bool, max_papers: int | None = None, **_: Any) -> StepResult:
    from code_engine.hypothesis.search import run_hypothesis_search_for_run
    conflict = _read(run_dir, "conflict_graph_summary.json")
    mechanism = _read(run_dir, "mechanism_graph.json")
    profile = _read(run_dir, "domain_profile.json")
    result = run_hypothesis_search_for_run(conflict, mechanism, profile, run_dir, dry_run=not execute, max_hypotheses=max_papers)
    artifact_dir = run_dir / "artifacts"
    from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl
    candidates = _attach_linked_provenance(_read_jsonl(artifact_dir / "hypothesis_candidates.jsonl"), run_dir)
    hyperedges = _attach_linked_provenance(_read_jsonl(artifact_dir / "hypothesis_hyperedges.jsonl"), run_dir)
    hypothesis_refs = {str(item.get("hypothesis_id")): item for item in hyperedges}
    reasoning = []
    for item in _read_jsonl(artifact_dir / "hypothesis_reasoning_records.jsonl"):
        source = hypothesis_refs.get(str(item.get("hypothesis_id")), {})
        reasoning.append({**item, **{key: source.get(key) for key in ("linked_paper_ids", "linked_canonical_paper_ids", "linked_dois", "linked_titles", "linked_journals", "paper_count", "journal_distribution", "publication_year_range")}})
    requirements = []
    for item in _read_jsonl(artifact_dir / "hypothesis_validation_requirements.jsonl"):
        source = hypothesis_refs.get(str(item.get("hypothesis_id")), {})
        requirements.append({**item, **{key: source.get(key) for key in ("linked_paper_ids", "linked_canonical_paper_ids", "linked_dois", "linked_titles", "linked_journals")}})
    atomic_write_jsonl(artifact_dir / "hypothesis_candidates.jsonl", iter(candidates)); atomic_write_jsonl(artifact_dir / "hypothesis_hyperedges.jsonl", iter(hyperedges))
    atomic_write_jsonl(artifact_dir / "hypothesis_reasoning_records.jsonl", iter(reasoning)); atomic_write_jsonl(artifact_dir / "hypothesis_validation_requirements.jsonl", iter(requirements))
    result["top_hypotheses"] = [{**top, **{key: hypothesis_refs.get(str(top.get("hypothesis_id")), {}).get(key) for key in ("linked_dois", "linked_titles", "linked_journals", "publication_year_range")}} for top in result.get("top_hypotheses", [])]
    atomic_write_json(artifact_dir / "hypothesis_summary.json", result)
    artifact_names = (
        "hypothesis_candidates.jsonl", "hypothesis_hyperedges.jsonl",
        "hypothesis_reasoning_records.jsonl", "hypothesis_validation_requirements.jsonl",
        "hypothesis_summary.json",
    )
    artifacts = {Path(name).stem: str(artifact_dir / name) for name in artifact_names}
    count_names = (
        "hypothesis_candidate_count", "hypothesis_count", "hypothesis_high_confidence_count",
        "hypothesis_abstract_only_count", "hypothesis_fulltext_grounded_count",
        "hypothesis_mechanism_grounded_count", "hypothesis_requires_manual_review_count",
        "hypothesis_artifact_count",
    )
    return StepResult(status=result["status"], summary=result, artifacts=artifacts, counts={name: int(result.get(name, 0)) for name in count_names}, warnings=list(result.get("warnings", [])), skipped_reason=result.get("reason"))


def run_validation_step(
    *, run_dir: Path, execute: bool, network: bool = False, query: str = "",
    external_validation: bool = False, validation_query_mode: str = "auto",
    validation_index_dir: str | None = None, validation_cache_dir: str | None = None,
    validation_disable_cache: bool = False, validation_validators: list[str] | None = None,
    max_validation_validators_per_question: int = 4,
    validation_max_memory_mb: int = 4096,
    validation_max_records_per_validator: int = 100,
    validation_max_records_per_anchor: int = 200,
    validation_max_signals_per_validator: int = 30,
    validation_max_signals_per_run: int = 200,
    validation_max_query_seconds: int = 30,
    validation_max_raw_payload_bytes: int = 5_000_000,
    validation_allow_large_local_scan: bool = False,
    validation_provider_clients: dict | None = None, **_: Any,
) -> StepResult:
    from code_engine.schemas.validation import ValidationResourcePolicy
    from code_engine.validation.anchors import (
        build_validation_anchors_from_conflicts,
        build_validation_anchors_from_hypotheses,
        build_validation_anchors_from_mechanism_graph,
        build_validation_anchors_from_observations,
        write_validation_anchors,
    )
    from code_engine.validation.execution import execute_validation_query_plans
    from code_engine.validation.query_planner import plan_validation_queries, write_validation_query_plans
    from code_engine.validation.question_builder import build_validation_questions_from_anchors, write_validation_questions
    from code_engine.validation.registry import ValidatorRegistry
    from code_engine.validation.result_aggregator import aggregate_validation_signals
    from code_engine.validation.router import route_validation_questions, write_validation_routes

    profile = _read(run_dir, "domain_profile.json", {})
    from code_engine.hypothesis.io import iter_jsonl
    hypothesis_path = run_dir / "artifacts" / "hypothesis_hyperedges.jsonl"
    hypotheses = iter_jsonl(hypothesis_path) if hypothesis_path.exists() and hypothesis_path.stat().st_size else None
    if hypotheses is None:
        lowered_query = query.casefold()
        fallback_relation = (profile.get("key_relation_types") or ["identity_lookup"])[0]
        if any(term in lowered_query for term in ("signaling", "pathway", "通路", "信号")):
            fallback_relation = "pathway_mechanism"
        elif any(term in lowered_query for term in ("binding", "receptor", "affinity", "结合", "受体")):
            fallback_relation = "drug_target_binding"
        elif any(term in lowered_query for term in ("expression", "upregulat", "downregulat", "表达", "上调", "下调")):
            fallback_relation = "gene_expression"
        elif any(term in lowered_query for term in ("clinical", "trial", "patient", "临床", "患者")):
            fallback_relation = "clinical_outcome"
        hypotheses = [{
            "hypothesis_id": "PLANNED",
            "entities": [{"name": query, "entity_type": "unknown"}],
            "relation_family": fallback_relation,
            "context": {"planning_only": True},
        }]
    from itertools import chain
    conflict_payload = _read(run_dir, "conflict_graph_summary.json", {})
    conflicts = chain(conflict_payload.get("conflict_edges", []), iter_jsonl(run_dir / "artifacts" / "fulltext_conflict_confirmation.jsonl"))
    mechanism = _read(run_dir, "mechanism_graph.json", {})
    observations = _read(run_dir, "l2_fulltext_observations.json", []) or _read(run_dir, "l2_observations.json", [])
    anchors = []
    anchors.extend(build_validation_anchors_from_hypotheses(hypotheses))
    anchors.extend(build_validation_anchors_from_conflicts(conflicts))
    if mechanism:
        anchors.extend(build_validation_anchors_from_mechanism_graph(mechanism))
    anchors.extend(build_validation_anchors_from_observations(observations))
    anchors = list({item.anchor_id: item for item in anchors}.values())
    anchor_artifacts = write_validation_anchors(anchors, run_dir / "artifacts")
    questions = build_validation_questions_from_anchors(anchors, profile)
    question_artifacts = write_validation_questions(questions, run_dir / "artifacts")

    registry = ValidatorRegistry().register_defaults()
    routes = route_validation_questions(questions, registry, profile, max_validation_validators_per_question)
    warnings = []
    if validation_validators:
        allowed = set(validation_validators)
        unknown = allowed - set(registry.names())
        if unknown:
            warnings.append(f"unknown_validation_validators:{','.join(sorted(unknown))}")
        routes = [item for item in routes if item.validator_name in allowed or item.validator_name == "NullValidator"]
    route_artifacts = write_validation_routes(routes, run_dir / "artifacts")
    resource_policy = ValidationResourcePolicy(
        max_memory_mb=validation_max_memory_mb,
        max_records_per_validator=validation_max_records_per_validator,
        max_records_per_anchor=validation_max_records_per_anchor,
        max_signals_per_validator=validation_max_signals_per_validator,
        max_signals_per_run=validation_max_signals_per_run,
        max_raw_payload_bytes_per_validator=validation_max_raw_payload_bytes,
        max_query_seconds=validation_max_query_seconds,
        allow_large_local_scan=validation_allow_large_local_scan,
        external_validation_enabled=external_validation,
        network_enabled=network,
        cache_enabled=not validation_disable_cache,
        execution_enabled=bool(execute and external_validation),
        index_dir=validation_index_dir,
        cache_dir=validation_cache_dir,
    )
    query_plans = plan_validation_queries(routes, questions, anchors, registry, resource_policy, validation_query_mode)
    query_artifacts = write_validation_query_plans(query_plans, run_dir / "artifacts")
    execution = execute_validation_query_plans(
        query_plans, registry, resource_policy,
        execute=bool(execute and external_validation), network_enabled=network,
        cache_enabled=not validation_disable_cache,
        run_dir=run_dir / "artifacts", provider_clients=validation_provider_clients,
    )
    aggregate = aggregate_validation_signals(
        Path(execution.artifact_refs["signals"]), anchors, query_plans,
        resource_policy, output_dir=run_dir / "artifacts",
    )
    result_path = Path(aggregate.artifact_refs.get("results", "")) if aggregate.artifact_refs.get("results") else None
    if result_path and result_path.exists():
        from code_engine.corpus.io import atomic_write_jsonl
        anchor_refs = {item.anchor_id: item.model_dump(mode="json") for item in anchors}
        results = []
        for item in _read_jsonl(result_path):
            source = anchor_refs.get(str(item.get("anchor_id")), {})
            results.append({**item, **{key: source.get(key, []) for key in ("linked_paper_ids", "linked_canonical_paper_ids", "linked_dois", "linked_titles", "linked_journals")}})
        atomic_write_jsonl(result_path, iter(results))
    allowed_count = sum(item.status == "allowed" for item in query_plans)
    blocked_count = len(query_plans) - allowed_count
    estimated_records = sum(int(item.estimated_records or 0) for item in query_plans)
    estimated_memory = round(sum(float(item.estimated_memory_mb or 0.0) for item in query_plans), 4)
    selected = sorted({item.validator_name for item in routes})
    summary = {
        "stages": {
            "anchor_building": len(anchors), "question_building": len(questions),
            "validator_routing": len(routes), "query_planning": len(query_plans),
            "resource_check": {"allowed": allowed_count, "blocked": blocked_count},
            "external_evidence_retrieval": execution.evidence_count,
            "validation_signal_building": execution.signal_count,
            "result_aggregation": aggregate.result_count,
        },
        "external_validation_enabled": external_validation,
        "validation_query_mode": validation_query_mode,
        "selected_validators": selected,
        "validation_anchor_count": len(anchors),
        "validation_question_count": len(questions),
        "validation_route_count": len(routes),
        "validation_query_plan_count": len(query_plans),
        "validation_allowed_query_count": allowed_count,
        "validation_blocked_query_count": blocked_count,
        "validation_execution_mode_counts": dict(Counter(item.execution_mode for item in query_plans)),
        "validation_estimated_records": estimated_records,
        "validation_estimated_memory_mb": estimated_memory,
        "validation_actual_evidence_count": execution.evidence_count,
        "validation_signal_count": execution.signal_count,
        "validation_actual_records_seen": execution.actual_records_seen,
        "validation_actual_evidence_written": execution.actual_evidence_written,
        "validation_actual_signals_written": execution.actual_signals_written,
        "validation_actual_raw_payload_bytes_written": execution.actual_raw_payload_bytes_written,
        "validation_actual_jsonl_bytes_written": execution.actual_jsonl_bytes_written,
        "validation_actual_query_seconds": execution.actual_query_seconds,
        "validation_actual_total_seconds": execution.actual_total_validation_seconds,
        "validation_actual_peak_batch_records_buffered": execution.actual_peak_batch_records_buffered,
        "validation_cache_hit_count": execution.cache_hit_count,
        "validation_cache_miss_count": execution.cache_miss_count,
        "validation_result_count": aggregate.result_count,
        "validation_aggregate_status": aggregate.aggregate_status,
        "result_status_counts": aggregate.status_counts,
        "local_indexes_used": sorted({item.index_name for item in query_plans if item.execution_mode == "local_index" and item.status == "allowed" and item.index_name}),
        "remote_validators_planned": sorted({item.validator_name for item in query_plans if item.execution_mode in {"remote_api", "blocked"} and "remote" in item.reason}),
        "remote_query_count_executed": execution.network_calls_made,
        "resource_usage": execution.model_dump(mode="json", exclude={"artifact_refs"}),
        "blocked_reasons": dict(Counter(item.reason for item in query_plans if item.status != "allowed")),
        "interpretation_warnings": [
            "External evidence is not proof.", "Validation signal is not proof.",
            "No record found is not contradiction.", "Cache miss is not no_coverage.",
            "Clinical trial existence is not efficacy support.",
            "Binding/activity record is not mechanism proof.",
            "Pathway membership is not causality proof.",
            "Cancer cell-line dependency is not clinical efficacy.",
        ],
    }
    summary_path = _write(run_dir, "validation_summary.json", summary)
    plan_path = _write(run_dir, "validation_plan.json", {
        "domain_id": profile.get("domain_id"),
        "validator_profile_id": profile.get("validator_profile_id", "general_validation"),
        "anchor_refs": anchor_artifacts, "question_refs": question_artifacts,
        "route_refs": route_artifacts, "query_plan_refs": query_artifacts,
        "planning_only": not bool(execute and external_validation),
    })
    artifacts = {
        "validation_plan": plan_path, "validation_summary": summary_path,
        "validation_anchors": anchor_artifacts["anchors"], "validation_anchor_summary": anchor_artifacts["summary"],
        "validation_questions": question_artifacts["questions"], "validation_question_summary": question_artifacts["summary"],
        "validation_routes": route_artifacts["routes"], "validation_route_summary": route_artifacts["summary"],
        "validation_query_plan": query_artifacts["plans"], "validation_query_plan_summary": query_artifacts["summary"],
        "external_validation_evidence": execution.artifact_refs["evidence"],
        "external_validation_signals": execution.artifact_refs["signals"],
        "external_validation_execution_summary": execution.artifact_refs["summary"],
        "validation_resource_usage": execution.artifact_refs["resource_usage"],
        "external_validation_results": aggregate.artifact_refs.get("results", ""),
        "external_validation_aggregate_summary": aggregate.artifact_refs.get("summary", ""),
    }
    counts = {key: value for key, value in summary.items() if key.startswith("validation_") and isinstance(value, int)}
    return StepResult(
        status="completed" if execute and external_validation else "planned",
        summary=summary, artifacts=artifacts, counts=counts,
        warnings=warnings + aggregate.warnings,
        network_calls_made=execution.network_calls_made,
    )


def run_conflict_timeline_step(*, run_dir: Path, enable_conflict_timeline: bool = True,
                               timeline_cutoff_year: int | None = None,
                               timeline_window_size: int = 5,
                               timeline_min_conflict_papers: int = 3,
                               timeline_min_later_papers: int = 1, **_: Any) -> StepResult:
    from code_engine.temporal.io import run_conflict_timeline
    summary = run_conflict_timeline(
        run_dir, cutoff_year=timeline_cutoff_year, window_size=timeline_window_size,
        min_conflict_papers=timeline_min_conflict_papers, min_later_papers=timeline_min_later_papers,
        enabled=enable_conflict_timeline,
    )
    artifact_dir = run_dir / "artifacts"
    names = (
        "conflict_evidence_timelines.jsonl", "conflict_evidence_timeline_summary.json",
        "conflict_temporal_windows.jsonl", "hypothesis_later_evidence_comparisons.jsonl",
    )
    return StepResult(
        status="completed" if summary["status"] in {"completed", "no_input", "disabled"} else summary["status"],
        summary=summary, artifacts={Path(name).stem: str(artifact_dir / name) for name in names},
        counts={"conflict_timeline_count": int(summary.get("timeline_count", 0))},
        warnings=list(summary.get("warnings", [])),
    )


def run_evidence_graph_step(*, run_dir: Path, enable_evidence_graph: bool = True,
                            evidence_graph_min_conflict_papers: int = 2,
                            evidence_graph_conflict_entropy_threshold: float = 0.55,
                            evidence_graph_max_edges: int | None = None, **_: Any) -> StepResult:
    from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts
    if enable_evidence_graph:
        result = build_merged_evidence_graph_from_run_artifacts(
            run_dir, max_edges=evidence_graph_max_edges,
            min_conflict_papers=evidence_graph_min_conflict_papers,
            conflict_entropy_threshold=evidence_graph_conflict_entropy_threshold,
        )
        summary, artifacts = result["summary"], result["artifacts"]
    else:
        from code_engine.evidence_graph.graph_io import write_json, write_jsonl
        output = run_dir / "artifacts"
        names = ("merged_evidence_graph_nodes.jsonl", "merged_evidence_graph_edges.jsonl", "relation_evidence_bundles.jsonl",
                 "graph_conflict_candidates.jsonl", "graph_reasoning_traces.jsonl")
        artifacts = {Path(name).stem: write_jsonl(output / name, []) for name in names}
        summary = {"status": "disabled", "node_count": 0, "edge_count": 0, "relation_bundle_count": 0,
                   "warnings": ["evidence_graph_disabled"], "scope": "run_level_graph_ready_reasoning_layer"}
        artifacts["summary"] = write_json(output / "merged_evidence_graph_summary.json", summary)
        artifacts["contract_report"] = write_json(output / "merged_evidence_graph_contract_report.json", {"status": "disabled", "warnings": []})
        artifacts["alignment_report"] = write_json(output / "graph_conflict_alignment_report.json", {"status": "disabled", "warnings": []})
    return StepResult(status="completed", summary=summary, artifacts={f"merged_evidence_graph_{key}": value for key, value in artifacts.items()},
                      counts={"evidence_graph_node_count": int(summary.get("node_count", 0)), "evidence_graph_edge_count": int(summary.get("edge_count", 0))},
                      warnings=list(summary.get("warnings", [])))


def run_evidence_graph_core_step(*, run_dir: Path, enable_evidence_graph: bool = True,
                                 evidence_graph_min_conflict_papers: int = 2,
                                 evidence_graph_conflict_entropy_threshold: float = 0.55,
                                 evidence_graph_max_edges: int | None = None, **_: Any) -> StepResult:
    """Build bundles/reasoning before hypothesis and timeline formation."""
    if not enable_evidence_graph:
        return StepResult(status="skipped", summary={"status": "disabled", "phase": "core"}, warnings=["evidence_graph_disabled"], skipped_reason="evidence_graph_disabled")
    from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts
    result = build_merged_evidence_graph_from_run_artifacts(
        run_dir, include_temporal=False, include_hypotheses=False,
        max_edges=evidence_graph_max_edges,
        min_conflict_papers=evidence_graph_min_conflict_papers,
        conflict_entropy_threshold=evidence_graph_conflict_entropy_threshold,
    )
    summary = {**result["summary"], "phase": "core"}
    return StepResult(
        status="completed", summary=summary,
        artifacts={f"evidence_graph_core_{key}": value for key, value in result["artifacts"].items()},
        counts={"evidence_graph_core_conflict_count": int(summary.get("graph_conflict_candidate_count", 0))},
        warnings=list(summary.get("warnings", [])),
    )
STEP_RUNNERS = {
    "intake": run_intake_step, "search": run_search_step, "acquisition": run_acquisition_step,
    "payload": run_payload_step,
    "abstract_l1": run_abstract_l1_step,
    "l2_abstract": run_l2_abstract_step,
    "abstract_conflict_screening": run_abstract_conflict_screening_step,
    "fulltext_escalation": run_fulltext_escalation_step,
    "fulltext_l1": run_fulltext_l1_step,
    "l2_fulltext": run_l2_fulltext_step,
    "fulltext_conflict_confirmation": run_fulltext_conflict_confirmation_step,
    "l1": run_l1_step, "l1_5": run_l1_5_step, "l2": run_l2_step,
    "evidence_graph_core": run_evidence_graph_core_step,
    "mechanism": run_mechanism_step, "conflict": run_conflict_step, "hypothesis": run_hypothesis_step,
    "conflict_timeline": run_conflict_timeline_step, "evidence_graph": run_evidence_graph_step,
    "validation": run_validation_step,
}
