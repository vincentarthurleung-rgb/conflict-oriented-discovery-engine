"""Run-level partial and final report rendering."""

from __future__ import annotations

import json
from pathlib import Path

from code_engine.workflow.models import RunState, STEP_ORDER
from code_engine.evidence_graph.graph_reports import render_merged_evidence_graph_section
from code_engine.temporal.reports import render_temporal_evidence_section
from code_engine.workflow.run_state import record_artifact


def _next_command(state: RunState, run_dir: Path) -> str:
    pending = next((name for name in STEP_ORDER if state.steps[name].status in {"pending", "blocked", "failed"}), None)
    if pending:
        return f"python -m code_engine.cli.run --resume {run_dir} --execute --until {state.until}"
    return f"python -m code_engine.cli.run --resume {run_dir}"


def render_run_report(state: RunState, run_dir: str | Path, *, final: bool = False) -> Path:
    directory = Path(run_dir)
    lines = [
        f"# {state.summary.get('triple_metadata', {}).get('seed_triple_title') or 'C.O.D.E. Research Workflow Run'}", "", f"- Run ID: `{state.run_id}`",
        f"- Triple ID: `{state.summary.get('triple_metadata', {}).get('triple_id') or 'not resolved'}`",
        f"- Query hash: `{state.summary.get('triple_metadata', {}).get('query_hash') or 'not resolved'}`",
        f"- Query: {state.query}", f"- Mode: `{state.mode}`", f"- Status: `{state.final_status}`",
        f"- Domain profile: `{state.domain_profile_id or 'not resolved'}`",
        f"- Semantic mode: `{state.semantic_mode or 'not run'}`",
        f"- Semantic confidence: `{state.semantic_confidence if state.semantic_confidence is not None else 'unknown'}`",
        f"- Manual review required: `{str(state.requires_manual_review).lower()}`",
        f"- L1 mode: `{state.l1_mode}`",
        f"- Full-text escalation enabled: `{str(state.fulltext_escalation_enabled).lower()}`",
        f"- Estimated L1 cost: `${state.l1_estimated_cost_usd:.6f}`",
        f"- Actual L1 cost: `{state.l1_actual_cost_usd if state.l1_actual_cost_usd is not None else 'not available'}`",
        f"- API calls: {state.api_calls_made}", f"- Network calls: {state.network_calls_made}",
        f"- Using legacy data: `{str(bool(state.summary.get('using_legacy_data'))).lower()}`",
        f"- Runtime data status: `{state.summary.get('runtime_data_status', 'unknown')}`",
        f"- External calls enabled: `{json.dumps(state.summary.get('external_calls_enabled', {}), sort_keys=True)}`",
        "", "## Workflow steps", "",
    ]
    readiness = state.summary.get("pilot_readiness", {})
    lines += ["", "## Pilot Readiness", "",
              "**NOT READY FOR REAL DATA PILOT**" if readiness.get("status") == "not_ready" else "**READY WITH WARNINGS**" if readiness.get("status") == "ready_with_warnings" else "**DRY-RUN SAFE**",
              "", f"- Blocking reasons: `{json.dumps(readiness.get('blocking_reasons', []))}`",
              f"- Warnings: `{json.dumps(readiness.get('warnings', []))}`", ""]
    if "l1_llm_client_not_configured" in readiness.get("blocking_reasons", []):
        lines += ["Real L1 extraction did not run because no L1 client was configured.", ""]
    contamination = readiness.get("legacy_contamination_check", {})
    provenance = state.summary.get("runtime_provenance", {})
    temporal_filter = provenance.get("paper_year_filter", readiness.get("paper_year_filter", {}))
    lines += ["### Temporal filter", "",
              f"- enabled: `{str(temporal_filter.get('enabled', False)).lower()}`",
              f"- temporal_role: `{temporal_filter.get('temporal_role', 'unrestricted')}`",
              f"- paper_year_from: `{temporal_filter.get('paper_year_from')}`",
              f"- paper_year_to: `{temporal_filter.get('paper_year_to')}`",
              f"- hardcoded_cutoff_used: `{str(temporal_filter.get('hardcoded_cutoff_used', False)).lower()}`", ""]
    lines += ["### Experiment Contamination Preflight", "",
              f"- Status: `{contamination.get('status', 'unknown')}`",
              f"- Import path: `{provenance.get('code_engine_import_path')}`",
              f"- Current-run only: `{str(provenance.get('current_run_only', False)).lower()}`",
              f"- Legacy pipelines used: `{str(contamination.get('legacy_pipeline_used', False)).lower()}`",
              f"- Historical runs read: `{str(contamination.get('historical_runs_read', False)).lower()}`",
              f"- Global evidence injected before reasoning: `{str(contamination.get('global_evidence_injected_before_reasoning', False)).lower()}`", ""]
    l2_context = state.steps["l2_abstract"].summary
    reproducibility = provenance.get("search_reproducibility", {})
    replay = provenance.get("search_plan_replay", {})
    lines += ["## Search reproducibility", "",
              f"- planner mode: `{reproducibility.get('planner_mode')}`",
              f"- frozen search plan used: `{str(reproducibility.get('frozen_search_plan_used', False)).lower()}`",
              f"- frozen search plan hash: `{reproducibility.get('frozen_search_plan_hash')}`",
              f"- executable query hash: `{reproducibility.get('executable_query_hash')}`",
              f"- PubMed date syntax: `{reproducibility.get('pubmed_date_syntax', 'pdat_range')}`",
              f"- LLM planner called: `{str(replay.get('llm_search_intent_called', not reproducibility.get('frozen_search_plan_used', False))).lower()}`",
              f"- deterministic fallback called: `{str(replay.get('deterministic_fallback_called', False)).lower()}`",
              f"- search plan drift detected: `{str(replay.get('search_plan_drift_detected', False)).lower()}`", ""]
    lines += ["## L2 layered retention", "",
              f"- normalized observations: {l2_context.get('normalized_observation_count', 0)}",
              f"- retained observations: {l2_context.get('retained_observation_count', 0)}",
              f"- excluded from retention: {l2_context.get('excluded_from_retention_count', 0)}",
              f"- non-core observations: {l2_context.get('non_core_observation_count', 0)}",
              f"- core observations: {l2_context.get('core_canonical_observation_count', 0)}",
              f"- mechanism / context / review / excluded: {l2_context.get('mechanism_observation_count', 0)} / {l2_context.get('context_observation_count', 0)} / {l2_context.get('review_observation_count', 0)} / {l2_context.get('excluded_observation_count', 0)}",
              "", "Non-core does not mean discarded; retained mechanism, context, and review evidence remains available for downstream non-core reasoning.", ""]
    lines += ["## Context grounding", "",
              f"- context-specific run: `{str((provenance.get('context_aware_evidence_layering') or {}).get('context_specific_run', False)).lower()}`",
              f"- strong-context core observations: {l2_context.get('strong_context_matched_core_observation_count', 0)}",
              f"- query-only context downgraded from core: {l2_context.get('context_query_only_downgraded_from_core_count', 0)}",
              f"- cross-context mechanism observations: {l2_context.get('cross_context_mechanism_observation_count', 0)}",
              f"- context mismatch downgraded from core: {l2_context.get('context_mismatch_downgraded_from_core_count', 0)}", "",
              "Retrieval query context is used for acquisition but is insufficient for context-specific core graph admission.", "",
              "## Seed predicate anchoring", "",
              f"- anchored core candidates: {l2_context.get('anchored_core_candidate_count', 0)}",
              f"- ambiguous predicate anchors: {l2_context.get('ambiguous_predicate_anchor_count', 0)}",
              f"- predicate direction inconsistencies blocked from core: {l2_context.get('predicate_direction_inconsistency_count', 0)}", ""]
    for name in STEP_ORDER:
        record = state.steps[name]
        detail = record.skipped_reason or ", ".join(record.warnings[:2])
        lines.append(f"- `{name}`: **{record.status}**" + (f" — {detail}" if detail else ""))
    lines += ["", "## Step summaries", ""]
    for name in (
        "search", "acquisition", "abstract_l1", "l2_abstract",
        "abstract_conflict_screening", "fulltext_escalation", "fulltext_l1",
        "l2_fulltext", "fulltext_conflict_confirmation", "l1", "l2",
        "mechanism", "conflict", "hypothesis", "validation",
    ):
        title = "L2 Entity Resolution" if name == "l2" else name
        lines += [f"### {title}", "", f"```json\n{json.dumps(state.steps[name].summary, ensure_ascii=False, indent=2)}\n```", ""]
    lines += [
        "## Hypothesis Formation", "",
        f"- Hypothesis source modes: `{json.dumps(state.hypothesis_source_mode_counts, sort_keys=True)}`",
        f"- Candidate count: {state.hypothesis_candidate_count}",
        f"- Generated hyperedge count: {state.hypothesis_count}",
        f"- Fulltext-grounded count: {state.hypothesis_fulltext_grounded_count}",
        f"- Mechanism-grounded count: {state.hypothesis_mechanism_grounded_count}",
        f"- Abstract-only follow-up count: {state.hypothesis_abstract_only_count}",
        f"- Manual review count: {state.hypothesis_requires_manual_review_count}",
        f"- Top hypotheses: `{json.dumps(state.steps['hypothesis'].summary.get('top_hypotheses', []), ensure_ascii=False)}`",
        f"- Warnings: `{json.dumps(state.steps['hypothesis'].warnings, ensure_ascii=False)}`", "",
        "## Coverage gaps", "",
        f"- Full-text unavailable papers: {state.counts.get('fulltext_unavailable_paper_count', 0)}",
        f"- Insufficient full-text coverage: {state.counts.get('insufficient_fulltext_coverage_count', 0)}",
        "- Missing full text is a coverage gap, not contradictory evidence.", "",
    ]
    validation = state.steps["validation"].summary
    lines += [
        "## Global Corpus / Paper Registry", "",
        f"- Corpus directory: `{state.global_corpus_dir}`",
        f"- Registry enabled / global update: {state.paper_registry_enabled} / {state.update_global_corpus}",
        f"- Input / new / duplicate papers: {state.paper_dedup_total} / {state.paper_dedup_new_count} / {state.paper_dedup_duplicate_count}",
        f"- Missing DOI / journal: {state.paper_missing_doi_count} / {state.paper_missing_journal_count}", "",
        "## Bibliographic Provenance", "",
        f"- Top conflicts: `{json.dumps(state.steps['abstract_conflict_screening'].summary.get('top_conflicts', []), ensure_ascii=False)}`",
        f"- Top hypotheses with DOI/title/journal/year: `{json.dumps(state.steps['hypothesis'].summary.get('top_hypotheses', []), ensure_ascii=False)}`", "",
        "## L1 Task Cache", "",
        f"- Abstract hits / misses: {state.abstract_l1_cache_hit_count} / {state.abstract_l1_cache_miss_count}",
        f"- Full-text hits / misses: {state.fulltext_l1_cache_hit_count} / {state.fulltext_l1_cache_miss_count}",
        f"- Estimated API calls saved: {state.estimated_l1_api_calls_saved}", "",
        "## KnowledgeStore Merge", "",
        f"- Enabled: {state.knowledge_merge_enabled}",
        f"- Inserted / updated / skipped: {state.knowledge_merge_inserted_count} / {state.knowledge_merge_updated_count} / {state.knowledge_merge_skipped_count}", "",
        "## Coverage Precheck", "",
        f"- Enabled: {state.coverage_precheck_enabled}",
        f"- Score: {state.coverage_precheck_score}",
        f"- Recommended action: `{state.coverage_recommended_action}`",
        "- Coverage recommendations do not short-circuit the pipeline by default.", "",
        "## Resource-aware external validation", "",
        f"- Anchors: {validation.get('validation_anchor_count', 0)}",
        f"- Questions: {validation.get('validation_question_count', 0)}",
        f"- Validator routes: {validation.get('validation_route_count', 0)}",
        f"- Query plans: {validation.get('validation_query_plan_count', 0)}",
        f"- Allowed / blocked: {validation.get('validation_allowed_query_count', 0)} / {validation.get('validation_blocked_query_count', 0)}",
        f"- Execution modes: `{json.dumps(validation.get('validation_execution_mode_counts', {}), sort_keys=True)}`",
        f"- Blocked reasons: `{json.dumps(validation.get('blocked_reasons', {}), sort_keys=True)}`",
        f"- Cache hits / misses: {validation.get('validation_cache_hit_count', 0)} / {validation.get('validation_cache_miss_count', 0)}",
        f"- Evidence / signals: {validation.get('validation_actual_evidence_count', 0)} / {validation.get('validation_signal_count', 0)}",
        f"- Aggregate status: `{validation.get('validation_aggregate_status', 'not_run')}`",
        f"- Estimated memory: {validation.get('validation_estimated_memory_mb', 0.0)} MB",
        f"- Estimated / actual records: {validation.get('validation_estimated_records', 0)} / {validation.get('validation_actual_records_seen', 0)}",
        f"- Actual query / total validation seconds: {validation.get('validation_actual_query_seconds', 0.0)} / {validation.get('validation_actual_total_seconds', 0.0)}",
        f"- Actual JSONL / raw payload bytes: {validation.get('validation_actual_jsonl_bytes_written', 0)} / {validation.get('validation_actual_raw_payload_bytes_written', 0)}",
        f"- Local indexes used: `{json.dumps(validation.get('local_indexes_used', []))}`",
        f"- Remote validators planned: `{json.dumps(validation.get('remote_validators_planned', []))}`",
        f"- Remote queries executed: {validation.get('remote_query_count_executed', 0)}",
        "- External evidence is not proof; validation signals are not proof.",
        "- No record found is not contradiction; cache miss is not no coverage.",
        "- Trial existence, binding activity, pathway membership, and cancer-cell dependency have limited interpretation.", "",
    ]
    timeline_path = directory / "artifacts" / "conflict_evidence_timelines.jsonl"
    timelines = []
    if timeline_path.exists():
        for line in timeline_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                timelines.append(json.loads(line))
    lines += render_temporal_evidence_section(timelines)
    graph_summary_path = directory / "artifacts" / "merged_evidence_graph_summary.json"
    graph_summary = json.loads(graph_summary_path.read_text(encoding="utf-8")) if graph_summary_path.exists() else {}
    def read_jsonl(name: str) -> list[dict]:
        path = directory / "artifacts" / name
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    lines += render_merged_evidence_graph_section(
        graph_summary, read_jsonl("graph_conflict_candidates.jsonl"),
        read_jsonl("graph_reasoning_traces.jsonl"), read_jsonl("merged_evidence_graph_nodes.jsonl"),
        read_jsonl("merged_evidence_graph_edges.jsonl"),
    )
    lines += ["## Warnings", ""] + ([f"- {item}" for item in state.warnings] or ["- None"])
    failed_or_blocked = [f"{name}: {record.status}" for name, record in state.steps.items() if record.status in {"failed", "blocked", "skipped", "manual_review_required"}]
    lines += ["", "## Failed or skipped steps", ""] + ([f"- {item}" for item in failed_or_blocked] or ["- None"])
    lines += ["", "## Next recommended command", "", f"`{_next_command(state, directory)}`", ""]
    report = directory / ("final_report.md" if final else "run_report.md")
    report.write_text("\n".join(lines), encoding="utf-8")
    if final:
        payload = directory / "artifacts" / "final_report.json"
        payload.write_text(json.dumps({"run_id": state.run_id, "query": state.query, "status": state.final_status, **state.summary.get("triple_metadata", {}), "steps": {name: state.steps[name].summary for name in STEP_ORDER}, "warnings": state.warnings}, ensure_ascii=False, indent=2), encoding="utf-8")
        record_artifact(state, "final_report", payload)
    record_artifact(state, "run_report", directory / "run_report.md")
    return report
