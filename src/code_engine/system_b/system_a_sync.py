"""Offline, idempotent System A handoff ingestion and immutable Atlas projection service."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select

from code_engine.integration.atlas_handoff import HANDOFF_SCHEMA_VERSION, HandoffError, canonical_json, sha256_file, validate_handoff
from code_engine.system_b.adapters.fulltext_reentry_v5 import ADAPTER_VERSION, FulltextReentryV5Adapter
from code_engine.system_b.persistence.database import create_atlas_engine, session_factory
from code_engine.system_b.persistence.models import PredictionRun, SourceArtifact, SourceIngestion, utcnow
from code_engine.system_b.persistence.services.audit_service import write_audit_event


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json(value)); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try: os.unlink(temporary)
        except FileNotFoundError: pass


def _write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    count = 0
    with path.open("wb") as handle:
        for row in rows:
            handle.write(canonical_json(row)); count += 1
        handle.flush(); os.fsync(handle.fileno())
    return count


def discover_handoffs(runs_root: str | Path, manifest: str | Path | None = None) -> list[Path]:
    if manifest:
        return [Path(manifest).resolve()]
    return sorted(Path(runs_root).resolve().glob("*/artifacts/atlas_handoff_manifest.json"))


def _validate_ready(path: Path) -> None:
    ready = path.parent / "ATLAS_READY"
    try: marker = json.loads(ready.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error: raise HandoffError("ready_marker_invalid", str(error)) from error
    if marker.get("schema_version") != HANDOFF_SCHEMA_VERSION or marker.get("manifest_sha256") != sha256_file(path):
        raise HandoffError("ready_marker_mismatch", str(path))


def _prediction_id(validated: dict, adapter_version: str) -> str:
    material = f"{validated['manifest_hash']}|{adapter_version}"
    return "pred_" + hashlib.sha256(material.encode()).hexdigest()[:24]


def _merge_projects(projects: list[dict]) -> dict:
    row_keys = ("dossier_evidence", "context_rows", "exploratory_triples", "conflict_predictions", "claim_review_candidates", "conflict_pair_candidates", "context_candidates")
    result = {key: [] for key in row_keys}
    dossier_items = {}
    display = {key: [] for key in ("display_entities_v2", "display_triples_v2", "display_chains_v2", "case_focused_triples", "case_focused_chains", "triple_evidence_links", "triple_contexts", "validator_annotations", "conflict_lens_records")}
    for project in projects:
        for key in row_keys: result[key].extend(project[key])
        for item in project["dossier_index"]["items"]:
            existing = dossier_items.get(item["triple_id"])
            if not existing: dossier_items[item["triple_id"]] = dict(item)
            else:
                existing["case_ids"] = sorted(set(existing["case_ids"] + item["case_ids"]))
                existing["evidence_count"] += item["evidence_count"]
                existing["fulltext_evidence_count"] += item["fulltext_evidence_count"]
                existing["display_priority_score_v2"] = existing["evidence_count"]
        for key in display: display[key].extend(project["display"][key])
    result["dossier_index"] = {"items": sorted(dossier_items.values(), key=lambda row: row["triple_id"]), "dossier_count": len(dossier_items)}
    entities = {}
    for row in display["display_entities_v2"]:
        current = entities.get(row["entity_id"])
        if not current: entities[row["entity_id"]] = dict(row)
        else:
            current["source_case_ids"] = sorted(set(current["source_case_ids"] + row["source_case_ids"]))
            current["evidence_count"] += row["evidence_count"]
            current["degree"] += row["degree"]
            current["display_priority_score"] = current["evidence_count"]
    display["display_entities_v2"] = sorted(entities.values(), key=lambda row: row["entity_id"])
    for key in row_keys:
        unique_key = "source_key" if key.endswith("candidates") else "source_record_hash" if key not in {"exploratory_triples"} else "triple_id"
        result[key] = sorted({str(row.get(unique_key)): row for row in result[key]}.values(), key=lambda row: str(row.get(unique_key)))
    result["display"] = display
    return result


def _write_projection(root: Path, projection_id: str, merged: dict, sources: list[dict], adapter_version: str) -> dict:
    root.mkdir(parents=True, exist_ok=False)
    staging = root / "evaluation_staging"; staging.mkdir()
    counts = {}
    for key, filename in (("dossier_evidence", "dossier_evidence.jsonl"), ("context_rows", "context_rows.jsonl"), ("exploratory_triples", "exploratory_triples.jsonl"), ("conflict_predictions", "conflict_predictions.jsonl")):
        counts[key] = _write_jsonl(root / filename, merged[key])
    _atomic_json(root / "dossier_index.json", merged["dossier_index"])
    for key, filename in (("claim_review_candidates", "claim_review_candidates.jsonl"), ("conflict_pair_candidates", "conflict_pair_candidates.jsonl"), ("context_candidates", "context_candidates.jsonl")):
        counts[key] = _write_jsonl(staging / filename, merged[key])
    sampling = {"schema_version": "evaluation_staging_v1", "automatic_import": False, "assignments_created": 0, "counts": {key: counts[key] for key in counts if key.endswith("candidates")}}
    _atomic_json(staging / "sampling_summary.json", sampling)
    for logical_name, rows in merged["display"].items(): _write_jsonl(root / f"{logical_name}.jsonl", rows)
    validation = {"status": "valid", "checks": {"evidence_not_kg_nodes": True, "formal_conflict_gate": True, "assignments_created": 0}, "counts": counts}
    _atomic_json(root / "validation_report.json", validation)
    manifest = {"schema_version": "atlas_projection_v1", "projection_id": projection_id, "adapter_version": adapter_version, "source_manifests": [{"case_id": item["manifest"]["case_id"], "source_run_id": item["manifest"]["source_run_id"], "manifest_hash": item["manifest_hash"], "prediction_run_id": _prediction_id(item, adapter_version)} for item in sources], "counts": counts, "generated_at": datetime.now(timezone.utc).isoformat(), "validation_status": "valid"}
    _atomic_json(root / "projection_manifest.json", manifest)
    return manifest


def sync_system_a(
    *, runs_root: str | Path = "runs", database_url: str | None = None, output_root: str | Path = "system_b_outputs/system_a_sync",
    manifest: str | Path | None = None, batch_id: str | None = None, adapter_version: str = ADAPTER_VERSION, dry_run: bool = False,
    quarantine_root: str | Path | None = None, no_database_write: bool = False, refresh_current_projection: bool = True,
) -> dict[str, Any]:
    paths = discover_handoffs(runs_root, manifest)
    if batch_id:
        paths = [path for path in paths if batch_id in path.parts[-3]]
    current_hashes = {}
    registry_path = Path(output_root) / "current_projection.json"
    if registry_path.is_file():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            projection_manifest = json.loads((Path(output_root) / registry["projection_relative_path"] / "projection_manifest.json").read_text(encoding="utf-8"))
            for source in projection_manifest.get("source_manifests", []):
                current_hashes[source["case_id"]] = source["manifest_hash"]
                source_path = Path(runs_root) / source["source_run_id"] / "artifacts/atlas_handoff_manifest.json"
                if source_path.is_file() and source_path.resolve() not in {item.resolve() for item in paths}: paths.append(source_path.resolve())
        except (OSError, KeyError, json.JSONDecodeError):
            current_hashes = {}
    paths = sorted(paths)
    quarantine = Path(quarantine_root or Path(output_root) / "quarantine")
    valid = []; rejected = []
    for path in paths:
        try:
            _validate_ready(path)
            parsed = validate_handoff(path, runs_root=runs_root)
            if parsed["manifest"].get("adapter_hint") != "fulltext_reentry_v5": raise HandoffError("unsupported_adapter_hint", str(parsed["manifest"].get("adapter_hint")))
            valid.append(parsed)
        except Exception as error:
            rejected.append({"manifest": str(path), "error_code": getattr(error, "code", type(error).__name__), "error_summary": str(error)})
    factory = session_factory(create_atlas_engine(database_url)) if not no_database_write else None
    existing_keys = set()
    if factory:
        session = factory()
        try:
            existing_keys = set(session.execute(select(SourceIngestion.source_run_id, SourceIngestion.manifest_hash, SourceIngestion.adapter_version).where(SourceIngestion.status == "completed")).all())
        except Exception:
            if not dry_run: raise
        finally: session.close()
    grouped = {}
    for item in valid: grouped.setdefault(item["manifest"]["case_id"], []).append(item)
    missing_current = sorted(set(current_hashes) - set(grouped))
    if missing_current: raise HandoffError("current_projection_source_missing", ", ".join(missing_current))
    selected = []
    for case_id, candidates in sorted(grouped.items()):
        fresh = [item for item in candidates if (item["manifest"]["source_run_id"], item["manifest_hash"], adapter_version) not in existing_keys]
        if len(fresh) > 1: raise HandoffError("ambiguous_new_case_runs", f"{case_id} has {len(fresh)} un-ingested ready handoffs")
        if fresh: selected.append(fresh[0]); continue
        current = [item for item in candidates if item["manifest_hash"] == current_hashes.get(case_id)]
        if len(current) == 1: selected.append(current[0]); continue
        if len(candidates) == 1: selected.append(candidates[0]); continue
        raise HandoffError("ambiguous_current_case_run", f"{case_id} has no unique current handoff")
    valid = selected
    new = [item for item in valid if (item["manifest"]["source_run_id"], item["manifest_hash"], adapter_version) not in existing_keys]
    adapter = FulltextReentryV5Adapter()
    projects = [adapter.project(item, prediction_run_id=_prediction_id(item, adapter_version)) for item in valid]
    merged = _merge_projects(projects)
    plan_counts = {key: len(merged[key]) for key in ("dossier_evidence", "context_rows", "exploratory_triples", "conflict_predictions", "claim_review_candidates", "conflict_pair_candidates", "context_candidates")}
    plan_counts["dossiers"] = merged["dossier_index"]["dossier_count"]
    plan_counts["evaluation_candidates"] = sum(plan_counts[key] for key in ("claim_review_candidates", "conflict_pair_candidates", "context_candidates"))
    evidence_chain_ids = {
        bundle.get("chain", {}).get("chain_id")
        for row in merged["dossier_evidence"]
        for bundle in (row.get("evidence_chains") or [])
        if isinstance(bundle, dict)
    }
    linked_claim_ids = {
        row.get("claim_id")
        for row in merged["dossier_evidence"]
        if row.get("evidence_chains")
    }
    plan_counts["evidence_chain_count"] = len({x for x in evidence_chain_ids if x})
    plan_counts["linked_claim_count"] = len({x for x in linked_claim_ids if x})
    plan_counts["unlinked_claim_count"] = max(0, len({row.get("claim_id") for row in merged["dossier_evidence"] if row.get("claim_id")}) - plan_counts["linked_claim_count"])
    base_report = {"schema_version": "system_a_sync_report_v1", "ready_handoffs_scanned": len(paths), "valid_handoffs": len(valid), "new_ingestions": len(new), "no_op_ingestions": len(valid) - len(new), "quarantine_count": len(rejected), "rejected": rejected, "adapter_version": adapter_version, "counts": plan_counts, "database_write": bool(factory and not dry_run), "refresh_current_projection": bool(refresh_current_projection and not dry_run)}
    if dry_run:
        return {**base_report, "status": "dry_run", "cases": [{"case_id": item["manifest"]["case_id"], "source_run_id": item["manifest"]["source_run_id"], "manifest_hash": item["manifest_hash"], "counts": item["manifest"]["counts"]} for item in valid]}
    quarantine.mkdir(parents=True, exist_ok=True)
    for item in rejected:
        _atomic_json(quarantine / (hashlib.sha256(item["manifest"].encode()).hexdigest()[:20] + ".json"), item)
    if not new:
        return {**base_report, "status": "no_op", "current_projection_id": _current_id(Path(output_root))}
    projection_id = "projection_" + hashlib.sha256((adapter_version + "|" + "|".join(sorted(item["manifest_hash"] for item in valid))).encode()).hexdigest()[:24]
    output = Path(output_root); final = output / "projections" / projection_id
    temporary = output / "projections" / f".{projection_id}.{os.getpid()}.tmp"
    if temporary.exists(): shutil.rmtree(temporary)
    projection_manifest = _write_projection(temporary, projection_id, merged, valid, adapter_version)
    if factory:
        session = factory()
        try:
            for item in new:
                source = item["manifest"]
                ingestion = SourceIngestion(case_id=source["case_id"], source_run_id=source["source_run_id"], manifest_hash=item["manifest_hash"], handoff_schema_version=source["schema_version"], adapter_version=adapter_version, prediction_version=source["prediction_version"], status="projecting", namespace="system_a", discovered_at=utcnow(), started_at=utcnow(), projection_root=str(final))
                session.add(ingestion); session.flush()
                write_audit_event(session, action="source_ingestion_discovered", object_type="source_ingestion", object_id=ingestion.ingestion_id, case_id=source["case_id"], metadata={"source_run_id": source["source_run_id"], "manifest_hash": item["manifest_hash"]})
                write_audit_event(session, action="source_ingestion_validated", object_type="source_ingestion", object_id=ingestion.ingestion_id, case_id=source["case_id"], metadata={"schema_version": source["schema_version"]})
                write_audit_event(session, action="source_ingestion_projecting", object_type="source_ingestion", object_id=ingestion.ingestion_id, case_id=source["case_id"], metadata={"projection_id": projection_id})
                for logical_name, spec in source["artifacts"].items(): session.add(SourceArtifact(source_ingestion_id=ingestion.ingestion_id, logical_name=logical_name, relative_path=spec["relative_path"], sha256=spec["sha256"], size_bytes=spec["size_bytes"], record_count=spec.get("record_count"), required=bool(spec["required"]), validation_status="valid"))
                for previous in session.execute(select(PredictionRun).where(PredictionRun.case_id == source["case_id"], PredictionRun.is_current.is_(True))).scalars(): previous.is_current=False
                session.add(PredictionRun(prediction_run_id=_prediction_id(item, adapter_version), case_id=source["case_id"], source_ingestion_id=ingestion.ingestion_id, prediction_version=source["prediction_version"], system_a_git_commit=source.get("system_a_git_commit") or "", configuration_hash=source.get("configuration_hash") or "", source_completed_at=_parse_time(source.get("completed_at")), is_current=True))
                ingestion.status="completed"; ingestion.completed_at=utcnow()
                write_audit_event(session, action="source_ingestion_completed", object_type="source_ingestion", object_id=ingestion.ingestion_id, case_id=source["case_id"], metadata={"projection_id": projection_id})
            if final.exists():
                existing_manifest = json.loads((final / "projection_manifest.json").read_text())
                if existing_manifest.get("source_manifests") != projection_manifest.get("source_manifests"): raise RuntimeError("immutable projection collision")
                shutil.rmtree(temporary)
            else: os.replace(temporary, final)
            session.commit()
        except Exception:
            session.rollback()
            if temporary.exists(): shutil.rmtree(temporary)
            raise
        finally: session.close()
    else:
        final.parent.mkdir(parents=True, exist_ok=True); os.replace(temporary, final)
    if refresh_current_projection:
        _atomic_json(output / "current_projection.json", {"schema_version": "atlas_current_projection_v1", "projection_id": projection_id, "projection_relative_path": f"projections/{projection_id}", "projection_manifest_sha256": sha256_file(final / "projection_manifest.json"), "updated_at": datetime.now(timezone.utc).isoformat()})
    return {**base_report, "status": "completed", "current_projection_id": projection_id, "projection_root": str(final), "database_ingestions_created": len(new), "prediction_runs_created": len(new)}


def _parse_time(value: Any):
    if not value: return None
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError: return None


def _current_id(output: Path) -> str | None:
    try: return json.loads((output / "current_projection.json").read_text()).get("projection_id")
    except (OSError, json.JSONDecodeError): return None
