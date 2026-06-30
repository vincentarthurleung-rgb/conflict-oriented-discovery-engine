"""Atomic persistence and mutation helpers for RunState."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.workflow.models import RunState, STEP_ORDER, WorkflowStepRecord, WorkflowStepStatus


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(query: str) -> str:
    text = query.casefold()
    words = re.findall(r"[a-z0-9]+", text)
    meaningful = [word for word in words if word not in {"i", "want", "to", "know", "about", "current"}]
    return "_".join(meaningful[:5]) or "research_run"


def make_run_id(query: str) -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{_slug(query)}"


def create_run_state(
    query: str, *, execute: bool = False, api: bool = False, network: bool = False,
    until: str = "report", max_papers: int | None = None, run_id: str | None = None,
    l1_mode: str = "legacy", fulltext_escalation_enabled: bool = False,
) -> RunState:
    now = utc_now()
    return RunState(
        run_id=run_id or make_run_id(query), created_at=now, updated_at=now, query=query,
        mode="execute" if execute else "dry_run", api_enabled=bool(api),
        network_enabled=bool(network), until=until, max_papers=max_papers,
        l1_mode=l1_mode, fulltext_escalation_enabled=fulltext_escalation_enabled,
        steps={name: WorkflowStepRecord(step_name=name) for name in STEP_ORDER},
        summary={"using_legacy_data": False, "runtime_data_status": "planning", "external_calls_enabled": {"api": bool(execute and api), "network": bool(execute and network)}},
    )


def save_run_state(run_state: RunState, run_dir: str | Path) -> Path:
    directory = Path(run_dir)
    (directory / "artifacts").mkdir(parents=True, exist_ok=True)
    (directory / "logs").mkdir(parents=True, exist_ok=True)
    run_state.updated_at = utc_now()
    target = directory / "run_state.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(run_state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


def load_run_state(run_dir: str | Path) -> RunState:
    return RunState.from_dict(json.loads((Path(run_dir) / "run_state.json").read_text(encoding="utf-8")))


def update_step_status(run_state: RunState, step_name: str, status: str, *, summary: dict[str, Any] | None = None,
                       warnings: list[str] | None = None, errors: list[str] | None = None,
                       input_refs: list[str] | None = None, output_refs: list[str] | None = None,
                       api_calls_made: int | None = None, network_calls_made: int | None = None,
                       skipped_reason: str | None = None) -> WorkflowStepRecord:
    record = run_state.steps[step_name]
    now = utc_now()
    if status == WorkflowStepStatus.RUNNING.value:
        record.started_at = now
        run_state.current_step = step_name
    if status in {item.value for item in WorkflowStepStatus if item not in {WorkflowStepStatus.PENDING, WorkflowStepStatus.RUNNING}}:
        record.completed_at = now
    record.status = status
    if summary is not None:
        record.summary = summary
    if warnings:
        record.warnings.extend(item for item in warnings if item not in record.warnings)
    if errors:
        record.errors.extend(errors)
    if input_refs is not None:
        record.input_refs = input_refs
    if output_refs is not None:
        record.output_refs = output_refs
    if api_calls_made is not None:
        delta = api_calls_made - record.api_calls_made
        record.api_calls_made = api_calls_made
        run_state.api_calls_made += max(0, delta)
    if network_calls_made is not None:
        delta = network_calls_made - record.network_calls_made
        record.network_calls_made = network_calls_made
        run_state.network_calls_made += max(0, delta)
    record.skipped_reason = skipped_reason
    return record


def record_artifact(run_state: RunState, name: str, path: str | Path) -> None:
    run_state.artifacts[name] = str(path)


def record_warning(run_state: RunState, warning: str, step_name: str | None = None) -> None:
    if warning not in run_state.warnings:
        run_state.warnings.append(warning)
    if step_name and warning not in run_state.steps[step_name].warnings:
        run_state.steps[step_name].warnings.append(warning)


def record_error(run_state: RunState, error: str, step_name: str | None = None) -> None:
    run_state.errors.append(error)
    if step_name:
        run_state.steps[step_name].errors.append(error)


def mark_run_completed(run_state: RunState, *, partial: bool = False) -> None:
    run_state.current_step = None
    run_state.final_status = "partial" if partial else ("completed" if run_state.mode == "execute" else "planned")


def mark_run_failed(run_state: RunState, step_name: str, error: str) -> None:
    run_state.failed_step = step_name
    run_state.current_step = None
    run_state.final_status = "failed"
    update_step_status(run_state, step_name, WorkflowStepStatus.FAILED.value, errors=[error])
    record_error(run_state, error)
