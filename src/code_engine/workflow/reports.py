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
    for name in ("search", "acquisition", "l1", "l2", "conflict", "hypothesis", "validation"):
        lines += [f"### {name}", "", f"```json\n{json.dumps(state.steps[name].summary, ensure_ascii=False, indent=2)}\n```", ""]
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
