"""Run-level partial and final report rendering."""

from __future__ import annotations

import json
from pathlib import Path

from code_engine.workflow.models import RunState, STEP_ORDER
from code_engine.workflow.run_state import record_artifact


def _next_command(state: RunState, run_dir: Path) -> str:
    pending = next((name for name in STEP_ORDER if state.steps[name].status in {"pending", "blocked", "failed"}), None)
    if pending:
        return f"python -m code_engine.cli.run --resume {run_dir} --execute --until {state.until}"
    return f"python -m code_engine.cli.run --resume {run_dir}"


def render_run_report(state: RunState, run_dir: str | Path, *, final: bool = False) -> Path:
    directory = Path(run_dir)
    lines = [
        "# C.O.D.E. Research Workflow Run", "", f"- Run ID: `{state.run_id}`",
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
    lines += ["## Warnings", ""] + ([f"- {item}" for item in state.warnings] or ["- None"])
    failed_or_blocked = [f"{name}: {record.status}" for name, record in state.steps.items() if record.status in {"failed", "blocked", "skipped", "manual_review_required"}]
    lines += ["", "## Failed or skipped steps", ""] + ([f"- {item}" for item in failed_or_blocked] or ["- None"])
    lines += ["", "## Next recommended command", "", f"`{_next_command(state, directory)}`", ""]
    report = directory / ("final_report.md" if final else "run_report.md")
    report.write_text("\n".join(lines), encoding="utf-8")
    if final:
        payload = directory / "artifacts" / "final_report.json"
        payload.write_text(json.dumps({"run_id": state.run_id, "query": state.query, "status": state.final_status, "steps": {name: state.steps[name].summary for name in STEP_ORDER}, "warnings": state.warnings}, ensure_ascii=False, indent=2), encoding="utf-8")
        record_artifact(state, "final_report", payload)
    record_artifact(state, "run_report", directory / "run_report.md")
    return report
