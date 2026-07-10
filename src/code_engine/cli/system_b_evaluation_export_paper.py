"""Export Atlas evaluation runs into paper-ready tables and provenance files."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from sqlalchemy import select

from code_engine.system_b.persistence.database import create_atlas_engine, database_url as resolve_database_url, session_factory, session_scope
from code_engine.system_b.persistence.models import ExportEvent, GoldRecord, MetricResult, MetricRun
from code_engine.system_b.persistence.services.audit_service import canonical_json, write_audit_event
from code_engine.system_b.persistence.services.review_service import sha256_text


TABLES = [
    "table_1_dataset_statistics.csv",
    "table_2_component_fidelity.csv",
    "table_3_conflict_detection.csv",
    "table_4_context_attribution.csv",
    "table_5_hypothesis_evaluation.csv",
    "table_6_forward_validation.csv",
    "table_7_baselines_ablations.csv",
    "table_8_efficiency.csv",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) or ["status", "missing_reason"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def export_paper(database_url: str | None, output_root: Path, project_id: str, metric_run_id: str, actor_user_id: str | None = None) -> Path:
    engine = create_atlas_engine(resolve_database_url(database_url))
    Session = session_factory(engine)
    with session_scope(Session) as session:
        run = session.get(MetricRun, metric_run_id)
        if not run or run.project_id != project_id:
            raise SystemExit("metric_run_not_found")
        results = session.execute(select(MetricResult).where(MetricResult.metric_run_id == metric_run_id).order_by(MetricResult.metric_id)).scalars().all()
        out = output_root / project_id / metric_run_id
        metric_rows = [{
            "metric_id": row.metric_id,
            "value": row.value,
            "ci_low": row.ci_low,
            "ci_high": row.ci_high,
            "status": row.status,
            "missing_reason": row.missing_reason,
            "sample_size_cases": row.sample_size_cases,
            "sample_size_items": row.sample_size_items,
        } for row in results]
        summary = {"metric_run_id": metric_run_id, "project_id": project_id, "status": run.status, "metric_count": len(metric_rows)}
        _write_json(out / "evaluation_manifest.json", {"project_id": project_id, "metric_run_id": metric_run_id, "status": run.status})
        _write_json(out / "metric_summary.json", summary)
        _write_jsonl(out / "metric_results.jsonl", metric_rows)
        _write_jsonl(out / "quality_warnings.jsonl", [] if run.status == "ready" else [{"status": run.status, "missing_reason": run.error_message}])
        public_by_table = {
            "table_3_conflict_detection.csv": [row for row in metric_rows if row["metric_id"] in {"macro_f1", "micro_f1", "weighted_f1", "precision", "recall", "f1"}],
        }
        for table in TABLES:
            _write_csv(out / "paper_tables" / table, public_by_table.get(table) or [{"status": "not_computed", "missing_reason": "metric_not_available"}])
        gold = session.execute(select(GoldRecord).where(GoldRecord.project_id == project_id, GoldRecord.status == "frozen", GoldRecord.gold_version == int(run.gold_dataset_version or 0))).scalars().all()
        _write_json(out / "provenance" / "protocol_lock.json", {"protocol_id": run.protocol_id})
        _write_json(out / "provenance" / "metric_run.json", {"metric_run_id": run.metric_run_id, "started_by_user_id": run.started_by_user_id, "config_hash": run.config_hash, "git_commit": run.git_commit})
        _write_json(out / "provenance" / "gold_manifest.json", {"gold_version": run.gold_dataset_version, "gold_record_ids": [row.gold_record_id for row in gold]})
        _write_json(out / "provenance" / "annotator_provenance.json", {"policy": "internal_only_user_ids_retained_in_provenance"})
        file_hash = sha256_text(canonical_json(summary))
        _write_json(out / "provenance" / "export_manifest.json", {"file_hash": file_hash, "public_tables_exclude_usernames": True})
        event = ExportEvent(actor_user_id=actor_user_id, actor_username_snapshot="", export_type="paper", project_id=project_id, protocol_id=run.protocol_id, file_hash=file_hash, field_policy_json=canonical_json({"public_tables_exclude_usernames": True}))
        session.add(event)
        write_audit_event(session, action="paper_export", object_type="metric_run", object_id=metric_run_id, actor={"user_id": actor_user_id}, project_id=project_id, metadata={"output": str(out), "file_hash": file_hash})
        return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url")
    parser.add_argument("--output-root", default="system_b_outputs/evaluation")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--metric-run-id", required=True)
    parser.add_argument("--actor-user-id")
    args = parser.parse_args(argv)
    out = export_paper(args.database_url, Path(args.output_root), args.project_id, args.metric_run_id, args.actor_user_id)
    print(json.dumps({"ok": True, "output_dir": str(out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
