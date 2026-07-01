"""Unified end-to-end workflow orchestrator."""

from __future__ import annotations

from pathlib import Path
import json

from code_engine.workflow.errors import WorkflowConfigurationError
from code_engine.workflow.models import RunState, STEP_ORDER, WorkflowStepStatus
from code_engine.workflow.reports import render_run_report
from code_engine.workflow.run_state import (
    create_run_state, load_run_state, mark_run_completed, mark_run_failed, record_artifact,
    record_warning, save_run_state, update_step_status,
)
from code_engine.workflow.steps import STEP_RUNNERS


STEP_INPUT_ARTIFACTS = {
    "search": ("intake", "domain_profile"), "acquisition": ("search_plan",),
    "payload": ("acquisition_report",),
    "abstract_l1": ("acquisition_report", "domain_profile"),
    "l2_abstract": ("abstract_l1_claims", "domain_profile"),
    "evidence_graph_core": ("l2_abstract_observations", "run_paper_manifest"),
    "abstract_conflict_screening": ("abstract_l1_claims", "l2_abstract_observations"),
    "fulltext_escalation": ("abstract_conflict_candidates", "evidence_graph_core_conflicts", "paper_processing_records"),
    "fulltext_availability": ("fulltext_escalation_candidates",),
    "fulltext_acquisition": ("fulltext_availability_records",),
    "fulltext_l1": ("fulltext_acquisition_records", "domain_profile"),
    "l2_fulltext": ("fulltext_evidence_records", "domain_profile"),
    "fulltext_conflict_confirmation": ("abstract_conflict_candidates", "fulltext_evidence_records", "l2_fulltext_observations"),
    "l1": ("payload_report", "domain_profile"),
    "l1_5": ("l1_summary",), "l2": ("l1_5_summary", "domain_profile"),
    "mechanism": ("l2_observations", "l1_summary", "domain_profile"),
    "conflict": ("l2_observations", "mechanism_graph"), "hypothesis": ("conflict_graph_summary", "mechanism_graph", "evidence_graph_core_conflicts"),
    "conflict_timeline": ("hypothesis_hyperedges", "abstract_conflict_candidates", "evidence_graph_core_conflicts"),
    "evidence_graph": ("conflict_evidence_timelines", "hypothesis_hyperedges", "l2_abstract_observations"),
    "validation": ("hypothesis_summary", "domain_profile"),
    "report": ("validation_summary",),
}


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _core_design_report(provenance: dict) -> dict:
    blockers = []
    if provenance.get("abstract_retrieval_source_order") != ["pubmed"]:
        blockers.append("abstract_retrieval_not_pubmed_only")
    if provenance.get("abstract_open_access_required") or provenance.get("abstract_fulltext_required"):
        blockers.append("abstract_retrieval_has_fulltext_or_oa_filter")
    if provenance.get("initial_fulltext_download_count"):
        blockers.append("initial_acquisition_downloaded_fulltext")
    if not provenance.get("evidence_graph_core_before_fulltext_escalation"):
        blockers.append("evidence_graph_core_after_fulltext_escalation")
    if not provenance.get("triple_id_consistent_across_artifacts"):
        blockers.append("triple_id_mismatch")
    if provenance.get("paper_artifact_cache_hits") and not (
        provenance.get("paper_cache_consumed_by_l1") or provenance.get("paper_cache_consumed_by_acquisition")
    ):
        blockers.append("paper_cache_hit_not_consumed")
    if not provenance.get("l1_task_cache_fingerprint_complete"):
        blockers.append("l1_task_cache_fingerprint_incomplete")
    keys = (
        "semantic_seed_triple_source", "semantic_seed_count", "seed_triple_confidence",
        "seed_triple_human_review_required", "abstract_retrieval_source_order",
        "abstract_open_access_required", "abstract_fulltext_required",
        "fulltext_escalation_enabled", "fulltext_escalation_after_conflict_screening", "fulltext_open_access_required",
        "fulltext_candidates_from_conflicts_only", "initial_fulltext_download_count",
        "fulltext_download_count", "fulltext_downloaded_only_selected_candidates",
        "evidence_graph_core_before_fulltext_escalation", "triple_id_consistent_across_artifacts",
        "paper_cache_consumed_by_l1", "l1_task_cache_fingerprint_complete",
    )
    return {"status": "blocked" if blockers else "pass", "blocking_reasons": blockers,
            **{key: provenance.get(key) for key in keys}}


def _annotate_jsonl_metadata(paths, metadata: dict, run_dir: Path) -> None:
    for value in paths:
        path = Path(value) if value else None
        if path is None or path.suffix != ".jsonl" or not path.is_file():
            continue
        try:
            path.resolve().relative_to(run_dir.resolve())
        except ValueError:
            continue
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                payload = json.loads(line)
                records.append({**payload, **metadata})
        path.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records), encoding="utf-8")


def run_workflow(
    query: str = "", run_dir: Path | None = None, until: str = "report", execute: bool = False,
    api: bool = False, network: bool = False, max_papers: int | None = None,
    paper_year_from: int | None = None, paper_year_to: int | None = None,
    temporal_role: str = "unrestricted",
    resume: Path | None = None, allow_legacy: bool = False,
    allow_uncertain_intake: bool = False, semantic_confidence_threshold: float = 0.6,
    semantic_llm_client=None,
    entity_network_lookup: bool = False, entity_llm_proposer: bool = False,
    entity_resolution_policy=None, entity_registry_path: str | Path | None = None,
    pilot_profile: str | None = None,
    l1_mode: str = "legacy", enable_fulltext_escalation: bool = False,
    fulltext_escalation_trigger: str = "conflict_entropy",
    min_abstract_conflict_entropy: float = 0.65, min_abstract_evidence_count: int = 3,
    max_fulltext_papers_per_conflict: int = 5, max_sections_per_paper: int = 5,
    max_spans_per_paper: int = 8, max_l1_calls_per_prompt: int | None = None,
    max_l1_input_tokens_per_prompt: int | None = None, l1_budget_usd: float | None = None,
    l1_pricing_profile: str = "deepseek_default", allow_budget_overrun: bool = False,
    l1_llm_client=None, l1_timeout_config: dict | None = None,
    external_validation: bool = False, validation_query_mode: str = "auto",
    validation_index_dir: str | None = None, validation_cache_dir: str | None = None,
    validation_cache_only: bool = False, validation_disable_cache: bool = False,
    validation_validators: list[str] | None = None,
    max_validation_validators_per_question: int = 4,
    validation_max_memory_mb: int = 4096,
    validation_max_records_per_validator: int = 100,
    validation_max_records_per_anchor: int = 200,
    validation_max_signals_per_validator: int = 30,
    validation_max_signals_per_run: int = 200,
    validation_max_query_seconds: int = 30,
    validation_max_raw_payload_bytes: int = 5_000_000,
    validation_allow_large_local_scan: bool = False,
    validation_provider_clients: dict | None = None,
    enable_conflict_timeline: bool = True, timeline_cutoff_year: int | None = None,
    timeline_window_size: int = 5, timeline_min_conflict_papers: int = 3,
    timeline_min_later_papers: int = 1,
    enable_evidence_graph: bool = True, evidence_graph_min_conflict_papers: int = 2,
    evidence_graph_conflict_entropy_threshold: float = 0.55,
    evidence_graph_max_edges: int | None = None,
    global_corpus_dir: str | Path | None = None,
    paper_registry_enabled: bool = True, update_global_corpus: bool = False,
    allow_title_hash_paper_merge: bool = False,
    l1_task_cache_enabled: bool = True, allow_compatible_l1_task_reuse: bool = False,
    force_reprocess_l1: bool = False, force_reprocess_paper: list[str] | None = None,
    merge_knowledge_store: bool = True, update_global_knowledge_store: bool = False,
    coverage_precheck: bool = False, coverage_threshold: float = 0.75,
    allow_coverage_short_circuit: bool = False,
    batch_id: str | None = None, seed_triple: dict | None = None,
    triple_input_hash: str | None = None,
    paper_artifact_cache_enabled: bool = True,
    paper_artifact_cache_index: str | Path | None = None,
    paper_artifact_cache_hits: int = 0, paper_artifact_cache_misses: int = 0,
    paper_cache_hit_records: list[dict] | None = None,
    paper_cache_miss_records: list[dict] | None = None,
    literature_client=None, fulltext_availability_resolver=None, fulltext_client=None,
) -> RunState:
    from code_engine.workflow.runtime_provenance import (
        build_runtime_provenance, contamination_check, imported_legacy_modules, write_runtime_provenance,
    )
    legacy_modules_before = imported_legacy_modules()
    if until not in STEP_ORDER:
        raise WorkflowConfigurationError(f"Unknown --until step: {until}")
    if not 0.0 <= semantic_confidence_threshold <= 1.0:
        raise WorkflowConfigurationError("semantic confidence threshold must be between 0 and 1")
    root = _repository_root()
    from code_engine.temporal.paper_year_filter import PaperYearFilter
    paper_year_filter = PaperYearFilter(paper_year_from, paper_year_to, temporal_role,
                                        "cli_argument" if paper_year_from is not None or paper_year_to is not None else "default")
    if l1_timeout_config is None:
        from code_engine.extraction.client_factory import resolve_l1_timeout_config
        l1_timeout_config = resolve_l1_timeout_config()
    from code_engine.config.pilots import load_pilot_profile
    from code_engine.normalization.registry import DEFAULT_REGISTRY_PATH
    pilot_config = load_pilot_profile(pilot_profile, root) if pilot_profile else {}
    pilot_terms = list(pilot_config.get("terms") or [])
    pilot_search_expansions = list(pilot_config.get("search_expansions") or [])
    pilot_domain_profile = str(pilot_config.get("domain_profile") or "") or None
    if entity_registry_path is not None:
        effective_entity_registry_path = Path(entity_registry_path).resolve()
    elif pilot_config.get("entity_registry_path"):
        effective_entity_registry_path = (root / str(pilot_config["entity_registry_path"])).resolve()
    else:
        effective_entity_registry_path = (root / DEFAULT_REGISTRY_PATH).resolve()
    if resume:
        directory = Path(resume).resolve()
        state = load_run_state(directory)
        if query and query != state.query:
            raise WorkflowConfigurationError("A resumed run cannot change its query")
        was_dry_run = state.mode == "dry_run"
        state.mode = "execute" if execute else "dry_run"
        # Resume is deny-by-default: callers must explicitly pass these flags again.
        state.api_enabled = bool(api)
        state.network_enabled = bool(network)
        state.until = until
        if max_papers is not None:
            state.max_papers = max_papers
        if execute and was_dry_run:
            reset = False
            for name in STEP_ORDER:
                if state.steps[name].status in {"planned", "blocked", "failed"}:
                    reset = True
                if reset:
                    state.steps[name].status = "pending"
                    state.steps[name].completed_at = None
    else:
        if not query.strip():
            raise WorkflowConfigurationError("--query is required for a new run")
        state = create_run_state(
            query, execute=execute, api=api, network=network, until=until,
            max_papers=max_papers, l1_mode=l1_mode,
            fulltext_escalation_enabled=enable_fulltext_escalation,
        )
        directory = Path(run_dir).resolve() if run_dir else root / "runs" / state.run_id
    # Intake is executed before experiment identity/provenance so every downstream
    # artifact uses the semantic intake seed as its single source of truth.
    if state.steps["intake"].status in {"pending", "running", "failed"} or not (directory / "artifacts/intake.json").is_file():
        save_run_state(state, directory)
        intake_result = STEP_RUNNERS["intake"](
            query=state.query, run_dir=directory, execute=execute, api=bool(execute and api),
            allow_uncertain_intake=allow_uncertain_intake,
            semantic_confidence_threshold=semantic_confidence_threshold,
            semantic_llm_client=semantic_llm_client,
            pilot_domain_profile=pilot_domain_profile,
            explicit_seed_triple=seed_triple,
        )
        for artifact_name, artifact_path in intake_result.artifacts.items():
            record_artifact(state, artifact_name, artifact_path)
        for warning in intake_result.warnings:
            record_warning(state, warning, "intake")
        update_step_status(state, "intake", intake_result.status, summary=intake_result.summary,
                           warnings=intake_result.warnings, output_refs=list(intake_result.artifacts.values()),
                           api_calls_made=intake_result.api_calls_made,
                           skipped_reason=intake_result.skipped_reason)
        for field in ("domain_id", "subdomain_id", "domain_profile_id", "prompt_profile_id", "entity_registry_profile", "validator_profile_id"):
            setattr(state, field, intake_result.summary.get(field))
        state.semantic_mode = intake_result.summary.get("semantic_mode")
        state.semantic_confidence = intake_result.summary.get("semantic_confidence")
        state.requires_manual_review = bool(intake_result.summary.get("requires_manual_review"))
        save_run_state(state, directory)
    from code_engine.schemas.triples import seed_triple_from_payload
    from code_engine.workflow.triple_metadata import annotate_summary_artifacts, finalize_triple_card, triple_metadata, write_triple_run_manifest
    intake_payload = json.loads((directory / "artifacts/intake.json").read_text(encoding="utf-8"))
    seed = seed_triple_from_payload(intake_payload["unified_seed_triple"], query_text=state.query)
    run_triple_metadata = triple_metadata(seed, batch_id)
    state.summary["triple_metadata"] = run_triple_metadata
    write_triple_run_manifest(directory, state, seed, batch_id, input_hash=triple_input_hash)
    state.summary["using_legacy_data"] = bool(allow_legacy)
    state.summary["external_calls_enabled"] = {"api": bool(execute and api), "network": bool(execute and network)}
    state.entity_network_lookup_enabled = bool(execute and network and entity_network_lookup)
    state.entity_llm_proposer_enabled = bool(execute and api and entity_llm_proposer)
    state.entity_resolution_policy = str(entity_resolution_policy) if entity_resolution_policy else None
    state.l1_mode = l1_mode
    state.fulltext_escalation_enabled = bool(enable_fulltext_escalation)
    corpus_dir = Path(global_corpus_dir).resolve() if global_corpus_dir else root / "data/corpus"
    state.global_corpus_dir = str(corpus_dir)
    state.paper_registry_enabled = bool(paper_registry_enabled)
    state.update_global_corpus = bool(update_global_corpus)
    state.l1_task_cache_enabled = bool(l1_task_cache_enabled)
    state.knowledge_merge_enabled = bool(merge_knowledge_store)
    state.coverage_precheck_enabled = bool(coverage_precheck)
    state.summary["global_corpus_configuration"] = {"corpus_dir": str(corpus_dir), "paper_registry_enabled": paper_registry_enabled, "update_global_corpus": update_global_corpus, "l1_task_cache_enabled": l1_task_cache_enabled, "compatible_l1_reuse": allow_compatible_l1_task_reuse, "merge_knowledge_store": merge_knowledge_store, "update_global_knowledge_store": update_global_knowledge_store, "coverage_precheck": coverage_precheck, "coverage_short_circuit": allow_coverage_short_circuit, "allow_title_hash_paper_merge": allow_title_hash_paper_merge}
    if coverage_precheck:
        from code_engine.corpus.coverage_precheck import run_global_coverage_precheck
        from code_engine.corpus.io import atomic_write_json
        coverage = run_global_coverage_precheck(state.query, None, corpus_dir, coverage_threshold)
        state.coverage_precheck_score = coverage.coverage_score
        state.coverage_recommended_action = coverage.recommended_action
        atomic_write_json(directory / "artifacts" / "coverage_precheck.json", coverage.model_dump(mode="json"))
        record_artifact(state, "coverage_precheck", directory / "artifacts" / "coverage_precheck.json")
        if allow_coverage_short_circuit and coverage.coverage_score >= coverage_threshold and coverage.recommended_action == "use_existing_knowledge":
            state.summary["coverage_short_circuit_applied"] = True
            for step_name in STEP_ORDER:
                if step_name not in {"intake", "report"}:
                    update_step_status(state, step_name, WorkflowStepStatus.SKIPPED.value, summary={"reason": "global_coverage_short_circuit", "coverage_score": coverage.coverage_score}, skipped_reason="global_coverage_short_circuit")
    l1_budget_policy = {
        "max_l1_calls_per_prompt": max_l1_calls_per_prompt,
        "max_l1_input_tokens_per_prompt": max_l1_input_tokens_per_prompt,
        "budget_usd": l1_budget_usd,
        "model_pricing_profile": l1_pricing_profile,
        "max_fulltext_papers_per_prompt": max_fulltext_papers_per_conflict,
        "max_sections_per_paper": max_sections_per_paper,
        "max_spans_per_paper": max_spans_per_paper,
    }
    l1_budget_policy = {key: value for key, value in l1_budget_policy.items() if value is not None}
    state.summary["l1_configuration"] = {
        "l1_mode": l1_mode,
        "fulltext_escalation_enabled": bool(enable_fulltext_escalation),
        "fulltext_escalation_trigger": fulltext_escalation_trigger,
        "min_abstract_conflict_entropy": min_abstract_conflict_entropy,
        "min_abstract_evidence_count": min_abstract_evidence_count,
        "budget_policy": l1_budget_policy,
    }
    effective_validation_mode = "cache_only" if validation_cache_only else validation_query_mode
    state.summary["external_validation_configuration"] = {
        "enabled": bool(external_validation),
        "query_mode": effective_validation_mode,
        "index_dir": validation_index_dir,
        "cache_dir": validation_cache_dir,
        "cache_enabled": not validation_disable_cache,
        "selected_validators": validation_validators or [],
        "allow_large_local_scan": bool(validation_allow_large_local_scan),
    }
    state.summary["conflict_timeline_configuration"] = {
        "enabled": enable_conflict_timeline, "cutoff_year": timeline_cutoff_year,
        "window_size": timeline_window_size, "min_conflict_papers": timeline_min_conflict_papers,
        "min_later_papers": timeline_min_later_papers, "uses_external_validation": False,
    }
    state.summary["evidence_graph_configuration"] = {
        "enabled": enable_evidence_graph, "scope": "run_level_only",
        "min_conflict_papers": evidence_graph_min_conflict_papers,
        "conflict_entropy_threshold": evidence_graph_conflict_entropy_threshold,
        "max_edges": evidence_graph_max_edges, "uses_external_validation_for_reasoning": False,
    }
    automatic_pilot_registry = False
    resolver_configured = effective_entity_registry_path.exists()
    state.summary["pilot_configuration"] = {
        "pilot_profile": pilot_profile, "pilot_terms": pilot_terms,
        "profile_path": pilot_config.get("profile_path"),
        "entity_registry_path": str(effective_entity_registry_path),
    }
    blocking_reasons = []
    if execute:
        if not api: blocking_reasons.append("api_not_enabled")
        if not network: blocking_reasons.append("network_not_enabled")
        if l1_mode != "legacy" and l1_llm_client is None: blocking_reasons.append("l1_llm_client_not_configured")
        if not resolver_configured: blocking_reasons.append("progressive_resolver_not_configured")
        if not effective_entity_registry_path.exists(): blocking_reasons.append("entity_registry_path_not_found")
        if not paper_registry_enabled: blocking_reasons.append("paper_registry_disabled")
        if not enable_evidence_graph: blocking_reasons.append("evidence_graph_disabled")
        if not enable_conflict_timeline: blocking_reasons.append("conflict_timeline_disabled")
    readiness = {
        "status": "not_ready" if blocking_reasons else ("ready_with_warnings" if execute else "dry_run_safe"),
        "blocking_reasons": blocking_reasons,
        "warnings": (["compound_normalization_requires_manual_review"] if pilot_profile else []),
        "l1_client_configured": l1_llm_client is not None, "resolver_configured": resolver_configured,
        "paper_registry_enabled": paper_registry_enabled, "evidence_graph_enabled": enable_evidence_graph,
        "conflict_timeline_enabled": enable_conflict_timeline, "network_enabled": network,
        "api_enabled": api, "execute_enabled": execute,
        "l1_timeout_config": dict(l1_timeout_config),
        "paper_year_filter": paper_year_filter.to_dict(),
        **run_triple_metadata,
        "static_journal_weight_used": False,
        "belief_weight_used_for_reasoning": False,
        "impact_factor_used_for_reasoning": False,
        "paper_quality_metadata_used_for_display_only": True,
    }
    (directory / "artifacts").mkdir(parents=True, exist_ok=True)
    runtime_provenance = build_runtime_provenance(
        directory, repository_root=root, resume_explicit=bool(resume),
        entity_registry_path=effective_entity_registry_path, automatic_pilot_registry=False,
        l1_mode=l1_mode, l1_task_cache_enabled=l1_task_cache_enabled,
        update_global_corpus=update_global_corpus, paper_registry_enabled=paper_registry_enabled,
        coverage_precheck=coverage_precheck, allow_coverage_short_circuit=allow_coverage_short_circuit,
        merge_knowledge_store=merge_knowledge_store, update_global_knowledge_store=update_global_knowledge_store,
        execute=execute, legacy_modules_before=legacy_modules_before,
        pilot_profile=pilot_profile, pilot_terms=pilot_terms,
        batch_id=batch_id, triple_id=seed.triple_id, query_hash=seed.query_hash,
        seed_triple=seed.model_dump(mode="json"),
        paper_artifact_cache_enabled=paper_artifact_cache_enabled,
        paper_artifact_cache_index=paper_artifact_cache_index,
        paper_artifact_cache_hits=paper_artifact_cache_hits,
        paper_artifact_cache_misses=paper_artifact_cache_misses,
        cache_hit_records=paper_cache_hit_records or (), cache_miss_records=paper_cache_miss_records or (),
        l1_timeout_config=l1_timeout_config,
        paper_year_filter=paper_year_filter.to_dict(),
    )
    contamination = contamination_check(runtime_provenance)
    readiness["domain_decoupling_check"] = {
        "status": "blocked" if runtime_provenance["ketamine_specific_defaults_used"] else "pass",
        "ketamine_specific_defaults_used": runtime_provenance["ketamine_specific_defaults_used"],
        "default_query_is_domain_neutral": True,
        "default_registry_is_domain_neutral": True,
        "pilot_profile_explicit": bool(pilot_profile),
        "warnings": [],
    }
    readiness["legacy_contamination_check"] = contamination
    core_design = _core_design_report(runtime_provenance)
    readiness["core_design_semantics_check"] = core_design
    readiness["blocking_reasons"] = list(dict.fromkeys([*readiness["blocking_reasons"], *contamination["blocking_reasons"]]))
    if readiness["blocking_reasons"]:
        readiness["status"] = "not_ready"
    provenance_path = directory / "artifacts" / "runtime_provenance_report.json"
    write_runtime_provenance(provenance_path, runtime_provenance)
    state.summary["runtime_provenance"] = runtime_provenance
    record_artifact(state, "runtime_provenance_report", provenance_path)
    readiness_path = directory / "artifacts" / "pilot_readiness_report.json"
    readiness_path.write_text(json.dumps(readiness, ensure_ascii=False, indent=2), encoding="utf-8")
    state.summary["pilot_readiness"] = readiness
    record_artifact(state, "pilot_readiness_report", readiness_path)
    core_design_path = directory / "artifacts" / "core_design_semantics_report.json"
    core_design_path.write_text(json.dumps(core_design, ensure_ascii=False, indent=2), encoding="utf-8")
    record_artifact(state, "core_design_semantics_report", core_design_path)
    if api and not execute:
        record_warning(state, "API enabled but execute=false, no API calls will be made")
    if network and not execute:
        record_warning(state, "network enabled but execute=false, no network calls will be made")
    if entity_network_lookup and not (execute and network):
        record_warning(state, "entity network lookup requested without execute+network; no entity network calls will be made")
    if entity_llm_proposer and not (execute and api):
        record_warning(state, "entity LLM proposer requested without execute+api; no entity LLM calls will be made")
    if not allow_legacy:
        state.summary["legacy_source_policy"] = "quarantine_and_legacy_artifacts_excluded"
    save_run_state(state, directory)
    stop_index = STEP_ORDER.index(until)
    intake_blocked = state.steps["intake"].status == "blocked"
    try:
        for index, name in enumerate(STEP_ORDER):
            if index > stop_index:
                break
            if intake_blocked and name != "intake":
                break
            record = state.steps[name]
            if record.status not in {"pending", "running", "failed"}:
                continue
            update_step_status(state, name, WorkflowStepStatus.RUNNING.value)
            save_run_state(state, directory)
            if name == "report":
                if merge_knowledge_store:
                    from code_engine.corpus.knowledge_merge import merge_run_artifacts_into_knowledge_store
                    merge = merge_run_artifacts_into_knowledge_store(directory, corpus_dir, update_global=update_global_knowledge_store, dry_run=not bool(update_global_knowledge_store))
                    state.knowledge_merge_inserted_count = merge.inserted_count
                    state.knowledge_merge_updated_count = merge.updated_count
                    state.knowledge_merge_skipped_count = merge.skipped_count
                    state.summary["knowledge_merge"] = merge.model_dump(mode="json")
                    for artifact_name, artifact_path in merge.artifact_refs.items():
                        record_artifact(state, f"knowledge_merge_{artifact_name}", artifact_path)
                runtime_provenance = build_runtime_provenance(
                    directory, repository_root=root, resume_explicit=bool(resume),
                    entity_registry_path=effective_entity_registry_path, automatic_pilot_registry=False,
                    l1_mode=l1_mode, l1_task_cache_enabled=l1_task_cache_enabled,
                    update_global_corpus=update_global_corpus, paper_registry_enabled=paper_registry_enabled,
                    coverage_precheck=coverage_precheck, allow_coverage_short_circuit=allow_coverage_short_circuit,
                    merge_knowledge_store=merge_knowledge_store, update_global_knowledge_store=update_global_knowledge_store,
                    execute=execute, legacy_modules_before=legacy_modules_before,
                    pilot_profile=pilot_profile, pilot_terms=pilot_terms,
                    batch_id=batch_id, triple_id=seed.triple_id, query_hash=seed.query_hash,
                    seed_triple=seed.model_dump(mode="json"),
                    paper_artifact_cache_enabled=paper_artifact_cache_enabled,
                    paper_artifact_cache_index=paper_artifact_cache_index,
                    paper_artifact_cache_hits=paper_artifact_cache_hits,
                    paper_artifact_cache_misses=paper_artifact_cache_misses,
                    cache_hit_records=paper_cache_hit_records or (), cache_miss_records=paper_cache_miss_records or (),
                    l1_timeout_config=l1_timeout_config,
                    paper_year_filter=paper_year_filter.to_dict(),
                )
                contamination = contamination_check(runtime_provenance)
                core_design = _core_design_report(runtime_provenance)
                readiness["legacy_contamination_check"] = contamination
                readiness["core_design_semantics_check"] = core_design
                readiness["blocking_reasons"] = list(dict.fromkeys([*readiness["blocking_reasons"], *contamination["blocking_reasons"]]))
                if readiness["blocking_reasons"]:
                    readiness["status"] = "not_ready"
                state.summary["runtime_provenance"], state.summary["pilot_readiness"] = runtime_provenance, readiness
                write_runtime_provenance(provenance_path, runtime_provenance)
                readiness_path.write_text(json.dumps(readiness, ensure_ascii=False, indent=2), encoding="utf-8")
                core_design_path.write_text(json.dumps(core_design, ensure_ascii=False, indent=2), encoding="utf-8")
                result_status = "completed"
                render_run_report(state, directory, final=True)
                report_inputs = [state.artifacts[key] for key in STEP_INPUT_ARTIFACTS[name] if key in state.artifacts]
                update_step_status(state, name, result_status, summary={"partial": any(item.status in {"blocked", "failed", "pending"} for key, item in state.steps.items() if key != "report")}, input_refs=report_inputs, output_refs=[str(directory / "final_report.md"), str(directory / "artifacts" / "final_report.json")])
                record_artifact(state, "final_report_markdown", directory / "final_report.md")
            else:
                result = STEP_RUNNERS[name](
                    query=state.query, run_dir=directory, repository_root=root,
                    execute=execute, api=bool(execute and api), network=bool(execute and network),
                    max_papers=state.max_papers, allow_legacy=allow_legacy,
                    allow_uncertain_intake=allow_uncertain_intake,
                    semantic_confidence_threshold=semantic_confidence_threshold,
                    semantic_llm_client=semantic_llm_client,
                    entity_network_lookup=entity_network_lookup,
                    entity_llm_proposer=entity_llm_proposer,
                    entity_resolution_policy=entity_resolution_policy,
                    entity_registry_path=effective_entity_registry_path,
                    pilot_profile=pilot_profile,
                    pilot_terms=pilot_terms,
                    pilot_search_expansions=pilot_search_expansions,
                    pilot_domain_profile=pilot_domain_profile,
                    l1_mode=l1_mode,
                    enable_fulltext_escalation=enable_fulltext_escalation,
                    fulltext_escalation_trigger=fulltext_escalation_trigger,
                    min_abstract_conflict_entropy=min_abstract_conflict_entropy,
                    min_abstract_evidence_count=min_abstract_evidence_count,
                    max_fulltext_papers_per_conflict=max_fulltext_papers_per_conflict,
                    max_sections_per_paper=max_sections_per_paper,
                    max_spans_per_paper=max_spans_per_paper,
                    l1_budget_policy=l1_budget_policy,
                    allow_budget_overrun=allow_budget_overrun,
                    l1_llm_client=l1_llm_client,
                    l1_timeout_config=l1_timeout_config,
                    paper_year_filter=paper_year_filter.to_dict(),
                    external_validation=external_validation,
                    validation_query_mode=effective_validation_mode,
                    validation_index_dir=validation_index_dir,
                    validation_cache_dir=validation_cache_dir,
                    validation_disable_cache=validation_disable_cache,
                    validation_validators=validation_validators,
                    max_validation_validators_per_question=max_validation_validators_per_question,
                    validation_max_memory_mb=validation_max_memory_mb,
                    validation_max_records_per_validator=validation_max_records_per_validator,
                    validation_max_records_per_anchor=validation_max_records_per_anchor,
                    validation_max_signals_per_validator=validation_max_signals_per_validator,
                    validation_max_signals_per_run=validation_max_signals_per_run,
                    validation_max_query_seconds=validation_max_query_seconds,
                    validation_max_raw_payload_bytes=validation_max_raw_payload_bytes,
                    validation_allow_large_local_scan=validation_allow_large_local_scan,
                    validation_provider_clients=validation_provider_clients,
                    enable_conflict_timeline=enable_conflict_timeline,
                    timeline_cutoff_year=timeline_cutoff_year,
                    timeline_window_size=timeline_window_size,
                    timeline_min_conflict_papers=timeline_min_conflict_papers,
                    timeline_min_later_papers=timeline_min_later_papers,
                    enable_evidence_graph=enable_evidence_graph,
                    evidence_graph_min_conflict_papers=evidence_graph_min_conflict_papers,
                    evidence_graph_conflict_entropy_threshold=evidence_graph_conflict_entropy_threshold,
                    evidence_graph_max_edges=evidence_graph_max_edges,
                    global_corpus_dir=corpus_dir,
                    paper_registry_enabled=paper_registry_enabled,
                    update_global_corpus=update_global_corpus,
                    allow_title_hash_paper_merge=allow_title_hash_paper_merge,
                    l1_task_cache_enabled=l1_task_cache_enabled,
                    allow_compatible_l1_task_reuse=allow_compatible_l1_task_reuse,
                    force_reprocess_l1=force_reprocess_l1,
                    force_reprocess_paper=force_reprocess_paper,
                    literature_client=literature_client,
                    fulltext_availability_resolver=fulltext_availability_resolver,
                    fulltext_client=fulltext_client,
                )
                _annotate_jsonl_metadata(result.artifacts.values(), run_triple_metadata, directory)
                for artifact_name, artifact_path in result.artifacts.items():
                    record_artifact(state, artifact_name, artifact_path)
                result.summary.update(run_triple_metadata)
                state.counts.update(result.counts)
                for field in (
                    "paper_dedup_total", "paper_dedup_new_count", "paper_dedup_duplicate_count",
                    "paper_missing_doi_count", "paper_missing_journal_count",
                    "abstract_l1_cache_hit_count", "abstract_l1_cache_miss_count",
                    "fulltext_l1_cache_hit_count", "fulltext_l1_cache_miss_count",
                    "estimated_l1_api_calls_saved",
                    "hypothesis_candidate_count", "hypothesis_count", "hypothesis_high_confidence_count",
                    "hypothesis_abstract_only_count", "hypothesis_fulltext_grounded_count",
                    "hypothesis_mechanism_grounded_count", "hypothesis_requires_manual_review_count",
                    "hypothesis_artifact_count",
                    "validation_anchor_count", "validation_question_count", "validation_route_count",
                    "validation_query_plan_count", "validation_allowed_query_count",
                    "validation_blocked_query_count", "validation_estimated_records",
                    "validation_actual_evidence_count", "validation_signal_count",
                    "validation_cache_hit_count", "validation_cache_miss_count",
                    "validation_result_count", "validation_actual_records_seen",
                    "validation_actual_evidence_written", "validation_actual_signals_written",
                    "validation_actual_raw_payload_bytes_written", "validation_actual_jsonl_bytes_written",
                    "validation_actual_peak_batch_records_buffered",
                ):
                    if field in result.counts:
                        if field == "estimated_l1_api_calls_saved":
                            state.estimated_l1_api_calls_saved += int(result.counts[field])
                        else:
                            setattr(state, field, int(result.counts[field]))
                if "hypothesis_source_mode_counts" in result.summary:
                    state.hypothesis_source_mode_counts = dict(result.summary["hypothesis_source_mode_counts"])
                if "validation_estimated_memory_mb" in result.summary:
                    state.validation_estimated_memory_mb = float(result.summary["validation_estimated_memory_mb"])
                state.validation_actual_query_seconds = float(result.summary.get("validation_actual_query_seconds", 0.0))
                state.validation_actual_total_seconds = float(result.summary.get("validation_actual_total_seconds", 0.0))
                if "validation_aggregate_status" in result.summary:
                    state.validation_aggregate_status = str(result.summary["validation_aggregate_status"])
                budget = result.summary.get("budget_report", {})
                if budget:
                    state.l1_estimated_cost_usd += float(budget.get("estimated_cost_usd", 0.0))
                    actual = budget.get("actual_cost_usd")
                    if actual is not None:
                        state.l1_actual_cost_usd = float(state.l1_actual_cost_usd or 0.0) + float(actual)
                for warning in result.warnings:
                    record_warning(state, warning, name)
                input_refs = [state.artifacts[key] for key in STEP_INPUT_ARTIFACTS.get(name, ()) if key in state.artifacts]
                update_step_status(state, name, result.status, summary=result.summary, warnings=result.warnings, input_refs=input_refs, output_refs=list(result.artifacts.values()), api_calls_made=result.api_calls_made, network_calls_made=result.network_calls_made, skipped_reason=result.skipped_reason)
                if name == "intake":
                    for field in ("domain_id", "subdomain_id", "domain_profile_id", "prompt_profile_id", "entity_registry_profile", "validator_profile_id"):
                        setattr(state, field, result.summary.get(field))
                    state.semantic_mode = result.summary.get("semantic_mode")
                    state.semantic_confidence = result.summary.get("semantic_confidence")
                    state.requires_manual_review = bool(result.summary.get("requires_manual_review"))
            save_run_state(state, directory)
            render_run_report(state, directory)
            save_run_state(state, directory)
            if name == "intake" and state.steps[name].status == "blocked":
                break
        blocked = any(record.status == "blocked" for record in state.steps.values())
        mark_run_completed(state, partial=bool(execute and (until != "report" or blocked)))
        state.summary["runtime_data_status"] = "partial" if blocked else ("executed" if execute else "planned")
        render_run_report(state, directory)
        annotate_summary_artifacts(directory, seed, batch_id)
        card_path, manifest_path = finalize_triple_card(directory, state, seed, batch_id, input_hash=triple_input_hash)
        record_artifact(state, "triple_card", card_path)
        record_artifact(state, "triple_run_manifest", manifest_path)
        save_run_state(state, directory)
        return state
    except Exception as exc:
        step = state.current_step or "unknown"
        if step in state.steps:
            mark_run_failed(state, step, f"{type(exc).__name__}: {exc}")
        state.summary["runtime_data_status"] = "failed"
        render_run_report(state, directory)
        annotate_summary_artifacts(directory, seed, batch_id)
        card_path, manifest_path = finalize_triple_card(directory, state, seed, batch_id, input_hash=triple_input_hash)
        record_artifact(state, "triple_card", card_path)
        record_artifact(state, "triple_run_manifest", manifest_path)
        save_run_state(state, directory)
        raise
