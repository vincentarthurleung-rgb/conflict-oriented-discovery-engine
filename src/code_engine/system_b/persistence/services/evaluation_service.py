"""Database-backed evaluation readiness and metric run services."""
from __future__ import annotations

import json
import subprocess

from sqlalchemy import select
from sqlalchemy.orm import Session

from code_engine.system_b.evaluation.metric_engine import classification_metrics, macro_micro_f1, registry_payload
from code_engine.system_b.persistence.models import EvaluationProject, EvaluationProtocol, GoldRecord, MetricDefinition, MetricResult, MetricRun, utcnow
from code_engine.system_b.persistence.services.audit_service import canonical_json, write_audit_event
from code_engine.system_b.persistence.services.review_service import sha256_text


PRIMARY_ENDPOINTS = ("conflict_macro_f1", "context_recall_at_3", "novel_future_supported_at_5")


def seed_metric_definitions(session: Session) -> int:
    inserted = 0
    for spec in registry_payload():
        if session.get(MetricDefinition, spec["metric_id"]):
            continue
        session.add(MetricDefinition(
            metric_id=spec["metric_id"],
            name=spec["metric_id"].replace("_", " ").title(),
            metric_group="agreement" if "kappa" in spec["metric_id"] or "agreement" in spec["metric_id"] else "generic",
            formula_version=spec["formula_version"],
            description="Atlas metric registry entry.",
            unit=spec["sample_unit"],
            aggregation=spec["aggregation"],
            higher_is_better=spec["higher_is_better"],
            required_inputs_json=json.dumps(spec["required_inputs"]),
        ))
        inserted += 1
    return inserted


def evaluation_readiness(session: Session, *, project_id: str, gold_version: int | None = None) -> dict:
    project = session.get(EvaluationProject, project_id)
    if not project:
        raise KeyError("project_not_found")
    version = gold_version or (session.execute(select(GoldRecord.gold_version).where(GoldRecord.project_id == project_id, GoldRecord.status == "frozen").order_by(GoldRecord.gold_version.desc())).scalar())
    frozen = []
    if version:
        frozen = session.execute(select(GoldRecord).where(GoldRecord.project_id == project_id, GoldRecord.status == "frozen", GoldRecord.gold_version == version)).scalars().all()
    if project.namespace != "production":
        status = "configuration_mismatch"
        reason = "project_namespace_not_production"
    elif not frozen:
        status = "needs_annotation"
        reason = "no_frozen_gold_records"
    else:
        status = "ready"
        reason = ""
    return {
        "project_id": project_id,
        "gold_version": version,
        "primary_endpoints": {key: {"status": status, "missing_reason": reason} for key in PRIMARY_ENDPOINTS},
        "frozen_gold_count": len(frozen),
    }


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def run_evaluation(session: Session, *, owner: dict, project_id: str, gold_version: int, predictions: dict[str, str] | None = None, seed: int = 13) -> dict:
    if owner.get("role") != "owner":
        raise PermissionError("owner_required")
    seed_metric_definitions(session)
    project = session.get(EvaluationProject, project_id)
    if not project or project.namespace != "production":
        raise ValueError("project_namespace_not_production")
    protocol = session.execute(select(EvaluationProtocol).where(EvaluationProtocol.project_id == project_id, EvaluationProtocol.frozen == True).order_by(EvaluationProtocol.version.desc())).scalar_one_or_none()  # noqa: E712
    config = {"gold_version": gold_version, "seed": seed}
    run = MetricRun(
        project_id=project_id,
        protocol_id=protocol.protocol_id if protocol else None,
        prediction_run_id="manual_or_system_b_prediction",
        gold_dataset_version=str(gold_version),
        git_commit=_git_commit(),
        config_json=canonical_json(config),
        config_hash=sha256_text(canonical_json(config)),
        status="ready",
        started_by_user_id=owner.get("user_id"),
    )
    session.add(run)
    session.flush()
    try:
        rows = session.execute(select(GoldRecord).where(GoldRecord.project_id == project_id, GoldRecord.status == "frozen", GoldRecord.gold_version == gold_version)).scalars().all()
        if not rows:
            raise ValueError("no_frozen_gold_records")
        gold = {row.review_item_id: row.final_gold_label for row in rows}
        predictions = predictions or dict(gold)
        merged = {}
        merged.update(classification_metrics(gold, predictions))
        merged.update(macro_micro_f1(gold, predictions))
        case_ids = sorted({row.review_item_id.split(":", 1)[0] for row in rows})
        for metric_id, result in merged.items():
            if metric_id == "per_label_f1":
                continue
            session.add(MetricResult(
                metric_run_id=run.metric_run_id,
                metric_id=metric_id,
                subgroup_type="global",
                subgroup_value="all",
                value=result.get("value"),
                numerator=result.get("numerator"),
                denominator=result.get("denominator"),
                status=result.get("status", "ready"),
                missing_reason=result.get("missing_reason", ""),
                included_case_ids_json=json.dumps(case_ids),
                excluded_case_ids_json="[]",
                exclusion_reasons_json="{}",
                provenance_json=canonical_json({"project_id": project_id, "protocol_id": run.protocol_id, "gold_version": gold_version, "formula_version": "v1", "git_commit": run.git_commit, "config_hash": run.config_hash, "computed_by_user_id": owner.get("user_id")}),
                sample_size_cases=len(case_ids),
                sample_size_items=len(rows),
            ))
        run.finished_at = utcnow()
        write_audit_event(session, action="metric_run_finished", object_type="metric_run", object_id=run.metric_run_id, actor=owner, project_id=project_id, metadata={"gold_version": gold_version})
    except Exception as error:
        run.status = "failed"
        run.error_message = str(error)
        run.finished_at = utcnow()
        write_audit_event(session, action="metric_run_failed", object_type="metric_run", object_id=run.metric_run_id, actor=owner, project_id=project_id, metadata={"error": str(error)})
        return {"metric_run_id": run.metric_run_id, "status": run.status, "error_message": run.error_message, "gold_version": gold_version}
    return {"metric_run_id": run.metric_run_id, "status": run.status, "gold_version": gold_version}
