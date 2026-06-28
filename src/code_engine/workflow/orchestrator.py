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
    "payload": ("acquisition_report",), "l1": ("payload_report", "domain_profile"),
    "l1_5": ("l1_summary",), "l2": ("l1_5_summary", "domain_profile"),
    "conflict": ("l2_observations",), "hypothesis": ("conflict_graph_summary",),
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
        state = create_run_state(query, execute=execute, api=api, network=network, until=until, max_papers=max_papers)
        directory = Path(run_dir).resolve() if run_dir else root / "runs" / state.run_id
    state.summary["using_legacy_data"] = bool(allow_legacy)
    state.summary["external_calls_enabled"] = {"api": bool(execute and api), "network": bool(execute and network)}
    if api and not execute:
        record_warning(state, "API enabled but execute=false, no API calls will be made")
    if network and not execute:
        record_warning(state, "network enabled but execute=false, no network calls will be made")
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
                result = STEP_RUNNERS[name](query=state.query, run_dir=directory, repository_root=root, execute=execute, api=bool(execute and api), network=bool(execute and network), max_papers=state.max_papers, allow_legacy=allow_legacy, allow_uncertain_intake=allow_uncertain_intake, semantic_confidence_threshold=semantic_confidence_threshold, semantic_llm_client=semantic_llm_client)
                for artifact_name, artifact_path in result.artifacts.items():
                    record_artifact(state, artifact_name, artifact_path)
                state.counts.update(result.counts)
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
