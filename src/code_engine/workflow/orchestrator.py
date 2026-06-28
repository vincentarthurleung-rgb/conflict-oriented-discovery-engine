"""Unified end-to-end workflow orchestrator."""

from __future__ import annotations

from pathlib import Path

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
    "abstract_conflict_screening": ("abstract_l1_claims", "l2_abstract_observations"),
    "fulltext_escalation": ("abstract_conflict_candidates", "paper_processing_records"),
    "fulltext_l1": ("fulltext_escalation_plan", "domain_profile"),
    "l2_fulltext": ("fulltext_evidence_records", "domain_profile"),
    "fulltext_conflict_confirmation": ("abstract_conflict_candidates", "fulltext_evidence_records", "l2_fulltext_observations"),
    "l1": ("payload_report", "domain_profile"),
    "l1_5": ("l1_summary",), "l2": ("l1_5_summary", "domain_profile"),
    "mechanism": ("l2_observations", "l1_summary", "domain_profile"),
    "conflict": ("l2_observations", "mechanism_graph"), "hypothesis": ("conflict_graph_summary", "mechanism_graph"),
    "validation": ("hypothesis_summary", "domain_profile"),
    "report": ("validation_summary",),
}


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def run_workflow(
    query: str = "", run_dir: Path | None = None, until: str = "report", execute: bool = False,
    api: bool = False, network: bool = False, max_papers: int | None = None,
    resume: Path | None = None, allow_legacy: bool = False,
    allow_uncertain_intake: bool = False, semantic_confidence_threshold: float = 0.6,
    semantic_llm_client=None,
    entity_network_lookup: bool = False, entity_llm_proposer: bool = False,
    entity_resolution_policy=None,
    l1_mode: str = "legacy", enable_fulltext_escalation: bool = False,
    fulltext_escalation_trigger: str = "conflict_entropy",
    min_abstract_conflict_entropy: float = 0.65, min_abstract_evidence_count: int = 3,
    max_fulltext_papers_per_conflict: int = 5, max_sections_per_paper: int = 5,
    max_spans_per_paper: int = 8, max_l1_calls_per_prompt: int | None = None,
    max_l1_input_tokens_per_prompt: int | None = None, l1_budget_usd: float | None = None,
    l1_pricing_profile: str = "deepseek_default", allow_budget_overrun: bool = False,
    l1_llm_client=None,
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
) -> RunState:
    if until not in STEP_ORDER:
        raise WorkflowConfigurationError(f"Unknown --until step: {until}")
    if not 0.0 <= semantic_confidence_threshold <= 1.0:
        raise WorkflowConfigurationError("semantic confidence threshold must be between 0 and 1")
    root = _repository_root()
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
    state.summary["using_legacy_data"] = bool(allow_legacy)
    state.summary["external_calls_enabled"] = {"api": bool(execute and api), "network": bool(execute and network)}
    state.entity_network_lookup_enabled = bool(execute and network and entity_network_lookup)
    state.entity_llm_proposer_enabled = bool(execute and api and entity_llm_proposer)
    state.entity_resolution_policy = str(entity_resolution_policy) if entity_resolution_policy else None
    state.l1_mode = l1_mode
    state.fulltext_escalation_enabled = bool(enable_fulltext_escalation)
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
    try:
        for index, name in enumerate(STEP_ORDER):
            if index > stop_index:
                break
            record = state.steps[name]
            if record.status not in {"pending", "running", "failed"}:
                continue
            update_step_status(state, name, WorkflowStepStatus.RUNNING.value)
            save_run_state(state, directory)
            if name == "report":
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
                )
                for artifact_name, artifact_path in result.artifacts.items():
                    record_artifact(state, artifact_name, artifact_path)
                state.counts.update(result.counts)
                for field in (
                    "validation_anchor_count", "validation_question_count", "validation_route_count",
                    "validation_query_plan_count", "validation_allowed_query_count",
                    "validation_blocked_query_count", "validation_estimated_records",
                    "validation_actual_evidence_count", "validation_signal_count",
                    "validation_cache_hit_count", "validation_cache_miss_count",
                    "validation_result_count",
                ):
                    if field in result.counts:
                        setattr(state, field, int(result.counts[field]))
                if "validation_estimated_memory_mb" in result.summary:
                    state.validation_estimated_memory_mb = float(result.summary["validation_estimated_memory_mb"])
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
        save_run_state(state, directory)
        return state
    except Exception as exc:
        step = state.current_step or "unknown"
        if step in state.steps:
            mark_run_failed(state, step, f"{type(exc).__name__}: {exc}")
        state.summary["runtime_data_status"] = "failed"
        render_run_report(state, directory)
        save_run_state(state, directory)
        raise
