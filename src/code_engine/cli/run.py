"""Command-line entry point for reproducible end-to-end runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.workflow.models import STEP_ORDER
from code_engine.workflow.orchestrator import run_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the C.O.D.E. research workflow")
    parser.add_argument("--query")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--until", choices=STEP_ORDER, default="report")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    api = parser.add_mutually_exclusive_group()
    api.add_argument("--api", action="store_true")
    api.add_argument("--no-api", action="store_true")
    network = parser.add_mutually_exclusive_group()
    network.add_argument("--network", action="store_true")
    network.add_argument("--no-network", action="store_true")
    parser.add_argument("--max-papers", type=int)
    parser.add_argument("--diversify-acquisition", action="store_true")
    parser.add_argument("--per-query-max-results", type=int)
    parser.add_argument("--per-query-group-max-results", action="append", default=[], metavar="GROUP=N")
    parser.add_argument("--reserve-query-group", action="append", default=[], metavar="GROUP=N")
    parser.add_argument("--paper-year-from", type=int)
    parser.add_argument("--paper-year-to", type=int)
    parser.add_argument("--temporal-role", choices=("discovery", "validation", "unrestricted"), default="unrestricted")
    parser.add_argument("--pubmed-date-syntax", choices=("pdat_range", "date_publication_range"), default="pdat_range")
    parser.add_argument("--save-search-plan", type=Path)
    parser.add_argument("--search-plan-file", type=Path)
    parser.add_argument("--freeze-search-plan", action="store_true")
    parser.add_argument("--replay-search-plan", action="store_true")
    parser.add_argument("--fail-if-search-plan-drift", action="store_true")
    parser.add_argument("--allow-legacy", action="store_true")
    parser.add_argument("--allow-uncertain-intake", action="store_true")
    parser.add_argument("--allow-deterministic-search-fallback", action="store_true")
    parser.add_argument("--disable-llm-search-intent", action="store_true")
    parser.add_argument("--semantic-confidence-threshold", type=float, default=0.6)
    entity_network = parser.add_mutually_exclusive_group()
    entity_network.add_argument("--entity-network-lookup", action="store_true")
    entity_network.add_argument("--no-entity-network-lookup", action="store_true")
    entity_llm = parser.add_mutually_exclusive_group()
    entity_llm.add_argument("--entity-llm-proposer", action="store_true")
    entity_llm.add_argument("--no-entity-llm-proposer", action="store_true")
    parser.add_argument("--entity-resolution-policy")
    parser.add_argument("--entity-registry-path", type=Path)
    parser.add_argument("--pilot-profile", choices=("ketamine",))
    parser.add_argument(
        "--l1-mode",
        choices=("abstract_screening", "progressive_fulltext", "fulltext_oracle", "legacy"),
        default="abstract_screening",
    )
    fulltext = parser.add_mutually_exclusive_group()
    fulltext.add_argument("--enable-fulltext-escalation", action="store_true")
    fulltext.add_argument("--no-fulltext-escalation", action="store_true")
    parser.add_argument("--fulltext-escalation-trigger", choices=("conflict_entropy",), default="conflict_entropy")
    parser.add_argument("--min-abstract-conflict-entropy", type=float, default=0.65)
    parser.add_argument("--min-abstract-evidence-count", type=int, default=3)
    parser.add_argument("--max-fulltext-papers-per-conflict", type=int, default=5)
    parser.add_argument("--max-sections-per-paper", type=int, default=5)
    parser.add_argument("--max-spans-per-paper", type=int, default=8)
    parser.add_argument("--max-l1-calls-per-prompt", type=int)
    parser.add_argument("--max-l1-input-tokens-per-prompt", type=int)
    parser.add_argument("--l1-budget-usd", type=float)
    parser.add_argument("--l1-pricing-profile", default="deepseek_default")
    parser.add_argument("--l1-provider", choices=("deepseek", "openai"))
    parser.add_argument("--l1-model")
    parser.add_argument("--l1-read-timeout-seconds", type=float)
    parser.add_argument("--l1-connect-timeout-seconds", type=float)
    parser.add_argument("--l1-max-retries", type=int)
    parser.add_argument("--allow-budget-overrun", action="store_true")
    parser.add_argument("--global-corpus-dir", type=Path)
    registry = parser.add_mutually_exclusive_group()
    registry.add_argument("--enable-paper-registry", action="store_true", default=True)
    registry.add_argument("--no-paper-registry", action="store_true")
    corpus_update = parser.add_mutually_exclusive_group()
    corpus_update.add_argument("--update-global-corpus", action="store_true")
    corpus_update.add_argument("--no-update-global-corpus", action="store_true")
    parser.add_argument("--allow-title-hash-paper-merge", action="store_true")
    task_cache = parser.add_mutually_exclusive_group()
    task_cache.add_argument("--enable-l1-task-cache", action="store_true", default=True)
    task_cache.add_argument("--no-l1-task-cache", action="store_true")
    parser.add_argument("--allow-compatible-l1-task-reuse", action="store_true")
    parser.add_argument("--force-reprocess-l1", action="store_true")
    parser.add_argument("--force-reprocess-paper", action="append", default=[])
    paper_cache = parser.add_mutually_exclusive_group()
    paper_cache.add_argument("--enable-paper-artifact-cache", action="store_true", default=True)
    paper_cache.add_argument("--no-cross-batch-paper-cache", action="store_true")
    parser.add_argument(
        "--paper-artifact-cache-index", type=Path,
        default=Path("data/index/paper_artifact_cache/paper_artifact_cache_index.jsonl"),
    )
    parser.add_argument("--build-paper-artifact-cache-from-runs", action="store_true")
    merge = parser.add_mutually_exclusive_group()
    merge.add_argument("--merge-knowledge-store", action="store_true", default=True)
    merge.add_argument("--no-merge-knowledge-store", action="store_true")
    global_merge = parser.add_mutually_exclusive_group()
    global_merge.add_argument("--update-global-knowledge-store", action="store_true")
    global_merge.add_argument("--no-update-global-knowledge-store", action="store_true")
    coverage = parser.add_mutually_exclusive_group()
    coverage.add_argument("--coverage-precheck", action="store_true")
    coverage.add_argument("--no-coverage-precheck", action="store_true")
    parser.add_argument("--coverage-threshold", type=float, default=0.75)
    parser.add_argument("--allow-coverage-short-circuit", action="store_true")
    timeline = parser.add_mutually_exclusive_group()
    timeline.add_argument("--enable-conflict-timeline", action="store_true", default=True)
    timeline.add_argument("--no-conflict-timeline", action="store_true")
    parser.add_argument("--timeline-cutoff-year", type=int)
    parser.add_argument("--timeline-window-size", type=int, default=5)
    parser.add_argument("--timeline-min-conflict-papers", type=int, default=3)
    parser.add_argument("--timeline-min-later-papers", type=int, default=1)
    evidence_graph = parser.add_mutually_exclusive_group()
    evidence_graph.add_argument("--enable-evidence-graph", action="store_true", default=True)
    evidence_graph.add_argument("--no-evidence-graph", action="store_true")
    parser.add_argument("--evidence-graph-min-conflict-papers", type=int, default=2)
    parser.add_argument("--evidence-graph-conflict-entropy-threshold", type=float, default=0.55)
    parser.add_argument("--evidence-graph-max-edges", type=int)
    external_validation = parser.add_mutually_exclusive_group()
    external_validation.add_argument("--external-validation", action="store_true")
    external_validation.add_argument("--no-external-validation", action="store_true")
    parser.add_argument("--validation-query-mode", choices=("auto", "local_index", "remote_api", "cache_only", "disabled"), default="auto")
    parser.add_argument("--validation-index-dir")
    parser.add_argument("--validation-cache-dir")
    parser.add_argument("--validation-cache-only", action="store_true")
    parser.add_argument("--validation-disable-cache", action="store_true")
    parser.add_argument("--validation-validator", action="append", dest="validation_validators")
    parser.add_argument("--max-validation-validators-per-question", type=int, default=4)
    parser.add_argument("--validation-max-memory-mb", type=int, default=4096)
    parser.add_argument("--validation-max-records-per-validator", type=int, default=100)
    parser.add_argument("--validation-max-records-per-anchor", type=int, default=200)
    parser.add_argument("--validation-max-signals-per-validator", type=int, default=30)
    parser.add_argument("--validation-max-signals-per-run", type=int, default=200)
    parser.add_argument("--validation-max-query-seconds", type=int, default=30)
    parser.add_argument("--validation-max-raw-payload-bytes", type=int, default=5_000_000)
    parser.add_argument("--validation-allow-large-local-scan", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.resume and not args.query:
        build_parser().error("--query is required unless --resume is used")
    from code_engine.extraction.client_factory import resolve_l1_timeout_config
    l1_timeout_config = resolve_l1_timeout_config(connect_timeout_seconds=args.l1_connect_timeout_seconds,
        read_timeout_seconds=args.l1_read_timeout_seconds, max_retries=args.l1_max_retries)
    l1_client = None
    if args.execute and args.api:
        from code_engine.extraction.client_factory import build_l1_client_from_env_or_config
        l1_client = build_l1_client_from_env_or_config(args.l1_provider, args.l1_model, **l1_timeout_config)
    if args.build_paper_artifact_cache_from_runs:
        from code_engine.corpus.paper_artifact_cache import build_paper_artifact_cache_index_from_runs
        build_paper_artifact_cache_index_from_runs(
            Path("runs"), args.paper_artifact_cache_index, include_batches=True, dry_run=False,
        )
    def group_quotas(values: list[str]) -> dict[str, int]:
        parsed = {}
        for value in values:
            group, separator, count = value.partition("=")
            if not separator or not group or not count.isdigit():
                build_parser().error(f"expected GROUP=N, got {value!r}")
            parsed[group] = int(count)
        return parsed

    state = run_workflow(
        query=args.query or "", run_dir=args.run_dir, until=args.until,
        execute=args.execute, api=args.api, network=args.network,
        max_papers=args.max_papers, resume=args.resume,
        diversify_acquisition=args.diversify_acquisition,
        per_query_max_results=args.per_query_max_results,
        per_query_group_max_results=group_quotas(args.per_query_group_max_results),
        reserve_query_group=group_quotas(args.reserve_query_group),
        paper_year_from=args.paper_year_from, paper_year_to=args.paper_year_to,
        temporal_role=args.temporal_role,
        pubmed_date_syntax=args.pubmed_date_syntax,
        save_search_plan=args.save_search_plan, search_plan_file=args.search_plan_file,
        freeze_search_plan=args.freeze_search_plan, replay_search_plan=args.replay_search_plan,
        fail_if_search_plan_drift=args.fail_if_search_plan_drift,
        allow_legacy=args.allow_legacy,
        allow_uncertain_intake=args.allow_uncertain_intake,
        allow_deterministic_search_fallback=args.allow_deterministic_search_fallback,
        disable_llm_search_intent=args.disable_llm_search_intent,
        semantic_confidence_threshold=args.semantic_confidence_threshold,
        entity_network_lookup=args.entity_network_lookup,
        entity_llm_proposer=args.entity_llm_proposer,
        entity_resolution_policy=args.entity_resolution_policy,
        entity_registry_path=args.entity_registry_path,
        pilot_profile=args.pilot_profile,
        l1_mode=args.l1_mode,
        enable_fulltext_escalation=args.enable_fulltext_escalation and not args.no_fulltext_escalation,
        fulltext_escalation_trigger=args.fulltext_escalation_trigger,
        min_abstract_conflict_entropy=args.min_abstract_conflict_entropy,
        min_abstract_evidence_count=args.min_abstract_evidence_count,
        max_fulltext_papers_per_conflict=args.max_fulltext_papers_per_conflict,
        max_sections_per_paper=args.max_sections_per_paper,
        max_spans_per_paper=args.max_spans_per_paper,
        max_l1_calls_per_prompt=args.max_l1_calls_per_prompt,
        max_l1_input_tokens_per_prompt=args.max_l1_input_tokens_per_prompt,
        l1_budget_usd=args.l1_budget_usd,
        l1_pricing_profile=args.l1_pricing_profile,
        allow_budget_overrun=args.allow_budget_overrun,
        l1_llm_client=l1_client,
        semantic_llm_client=l1_client,
        l1_timeout_config=l1_timeout_config,
        external_validation=args.external_validation and not args.no_external_validation,
        validation_query_mode=args.validation_query_mode,
        validation_index_dir=args.validation_index_dir,
        validation_cache_dir=args.validation_cache_dir,
        validation_cache_only=args.validation_cache_only,
        validation_disable_cache=args.validation_disable_cache,
        validation_validators=args.validation_validators,
        max_validation_validators_per_question=args.max_validation_validators_per_question,
        validation_max_memory_mb=args.validation_max_memory_mb,
        validation_max_records_per_validator=args.validation_max_records_per_validator,
        validation_max_records_per_anchor=args.validation_max_records_per_anchor,
        validation_max_signals_per_validator=args.validation_max_signals_per_validator,
        validation_max_signals_per_run=args.validation_max_signals_per_run,
        validation_max_query_seconds=args.validation_max_query_seconds,
        validation_max_raw_payload_bytes=args.validation_max_raw_payload_bytes,
        validation_allow_large_local_scan=args.validation_allow_large_local_scan,
        global_corpus_dir=args.global_corpus_dir,
        paper_registry_enabled=args.enable_paper_registry and not args.no_paper_registry,
        update_global_corpus=args.update_global_corpus and not args.no_update_global_corpus,
        allow_title_hash_paper_merge=args.allow_title_hash_paper_merge,
        l1_task_cache_enabled=args.enable_l1_task_cache and not args.no_l1_task_cache,
        allow_compatible_l1_task_reuse=args.allow_compatible_l1_task_reuse,
        force_reprocess_l1=args.force_reprocess_l1,
        force_reprocess_paper=args.force_reprocess_paper,
        paper_artifact_cache_enabled=args.enable_paper_artifact_cache and not args.no_cross_batch_paper_cache,
        paper_artifact_cache_index=args.paper_artifact_cache_index,
        merge_knowledge_store=args.merge_knowledge_store and not args.no_merge_knowledge_store,
        update_global_knowledge_store=args.update_global_knowledge_store and not args.no_update_global_knowledge_store,
        coverage_precheck=args.coverage_precheck and not args.no_coverage_precheck,
        coverage_threshold=args.coverage_threshold,
        allow_coverage_short_circuit=args.allow_coverage_short_circuit,
        enable_conflict_timeline=args.enable_conflict_timeline and not args.no_conflict_timeline,
        timeline_cutoff_year=args.timeline_cutoff_year,
        timeline_window_size=args.timeline_window_size,
        timeline_min_conflict_papers=args.timeline_min_conflict_papers,
        timeline_min_later_papers=args.timeline_min_later_papers,
        enable_evidence_graph=args.enable_evidence_graph and not args.no_evidence_graph,
        evidence_graph_min_conflict_papers=args.evidence_graph_min_conflict_papers,
        evidence_graph_conflict_entropy_threshold=args.evidence_graph_conflict_entropy_threshold,
        evidence_graph_max_edges=args.evidence_graph_max_edges,
    )
    directory = args.resume.resolve() if args.resume else (args.run_dir.resolve() if args.run_dir else Path("runs") / state.run_id)
    if args.json_output:
        print(json.dumps({"run_id": state.run_id, "run_dir": str(directory), "mode": state.mode, "api_calls_made": state.api_calls_made, "network_calls_made": state.network_calls_made, "final_status": state.final_status, "report": str(directory / "run_report.md")}, ensure_ascii=False))
    else:
        print(f"Run ID: {state.run_id}")
        print(f"Run dir: {directory}")
        print(f"Mode: {state.mode}")
        print(f"API calls: {state.api_calls_made}")
        print(f"Network calls: {state.network_calls_made}")
        print(f"Final status: {state.final_status}")
        print(f"Semantic mode: {state.semantic_mode}")
        print(f"Semantic confidence: {state.semantic_confidence}")
        print(f"L1 mode: {state.l1_mode}")
        print(f"Estimated L1 cost: ${state.l1_estimated_cost_usd:.6f}")
        print(f"Report: {directory / 'run_report.md'}")
        for warning in state.warnings:
            if "execute=false" in warning:
                print(f"Warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
