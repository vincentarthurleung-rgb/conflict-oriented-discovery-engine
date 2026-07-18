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

from code_engine.integration.atlas_handoff import ABSTRACT_L2_PROFILE, FULLTEXT_REENTRY_PROFILE, HandoffError, canonical_json, sha256_file, validate_handoff
from code_engine.system_b.adapters.abstract_l2_projection import ADAPTER_VERSION as ABSTRACT_L2_ADAPTER_VERSION, AbstractL2ProjectionAdapter
from code_engine.system_b.adapters.fulltext_reentry_v5 import ADAPTER_VERSION, FulltextReentryV5Adapter
from code_engine.system_b.persistence.database import create_atlas_engine, session_factory
from code_engine.system_b.persistence.models import PredictionRun, SourceArtifact, SourceIngestion, utcnow
from code_engine.system_b.persistence.services.audit_service import write_audit_event
from code_engine.system_b.evaluation.claim_sampling import evaluation_readiness, sampling_frame_hash

PROJECTION_SCHEMA_VERSION = "atlas_projection_v2"


def _profile(item: dict[str, Any]) -> str:
    return str((item.get("manifest") or {}).get("handoff_profile") or FULLTEXT_REENTRY_PROFILE)


def _adapter_version_for(item: dict[str, Any], default: str) -> str:
    return ABSTRACT_L2_ADAPTER_VERSION if _profile(item) == ABSTRACT_L2_PROFILE else default


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


def _write_failure_audit(output_root: str | Path, *, code: str, summary: str, rejected: list[dict] | None = None) -> None:
    payload = {"schema_version": "system_a_sync_failure_v1", "status": "failed", "error_code": code, "error_summary": summary, "rejected": rejected or [], "occurred_at": datetime.now(timezone.utc).isoformat()}
    digest = hashlib.sha256(canonical_json({"code": code, "summary": summary, "rejected": rejected or []})).hexdigest()[:20]
    _atomic_json(Path(output_root) / "sync_audit" / f"failed_{digest}.json", payload)


def discover_handoffs(runs_root: str | Path, manifest: str | Path | None = None) -> list[Path]:
    if manifest:
        return [Path(manifest).resolve()]
    return sorted(Path(runs_root).resolve().glob("*/artifacts/atlas_handoff_manifest.json"))


def _validate_ready(path: Path) -> None:
    ready = path.parent / "ATLAS_READY"
    try: marker = json.loads(ready.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error: raise HandoffError("ready_marker_invalid", str(error)) from error
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if marker.get("schema_version") != manifest.get("schema_version") or marker.get("manifest_sha256") != sha256_file(path):
        raise HandoffError("ready_marker_mismatch", str(path))


def _prediction_id(validated: dict, adapter_version: str) -> str:
    material = f"{validated.get('identity_hash') or validated['manifest_hash']}|{adapter_version}"
    return "pred_" + hashlib.sha256(material.encode()).hexdigest()[:24]


def _merge_projects(projects: list[dict]) -> dict:
    row_keys = ("dossier_evidence", "context_rows", "exploratory_triples", "conflict_predictions", "claim_review_candidates", "conflict_pair_candidates", "context_candidates")
    result = {key: [] for key in row_keys}
    result["predicted_claim_frame"] = []
    result["source_text_unit_frame"] = []
    result["case_metadata"] = {}
    dossier_items = {}
    display = {key: [] for key in ("display_entities_v2", "display_triples_v2", "display_chains_v2", "case_focused_triples", "case_focused_chains", "triple_evidence_links", "triple_contexts", "validator_annotations", "conflict_lens_records")}
    for project in projects:
        for key in row_keys: result[key].extend(project[key])
        result["predicted_claim_frame"].extend(project.get("predicted_claim_frame") or [])
        result["source_text_unit_frame"].extend(project.get("source_text_unit_frame") or [])
        metadata = project.get("case_metadata") or {}
        if metadata.get("case_id"):
            result["case_metadata"][metadata["case_id"]] = metadata
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
    result["predicted_claim_frame"] = sorted({str(row.get("prediction_claim_key")): row for row in result["predicted_claim_frame"]}.values(), key=lambda row: str(row.get("prediction_claim_key")))
    result["source_text_unit_frame"] = sorted({str(row.get("source_unit_id")): row for row in result["source_text_unit_frame"] if row.get("source_unit_id")}.values(), key=lambda row: str(row.get("source_unit_id")))
    result["display"] = display
    return result


def _write_projection(root: Path, projection_id: str, merged: dict, sources: list[dict], adapter_version: str) -> dict:
    root.mkdir(parents=True, exist_ok=False)
    staging = root / "evaluation_staging"; staging.mkdir()
    counts = {}
    for key, filename in (("dossier_evidence", "dossier_evidence.jsonl"), ("context_rows", "context_rows.jsonl"), ("exploratory_triples", "exploratory_triples.jsonl"), ("conflict_predictions", "conflict_predictions.jsonl")):
        counts[key] = _write_jsonl(root / filename, merged[key])
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
    all_claim_ids = {row.get("claim_id") for row in merged["dossier_evidence"] if row.get("claim_id")}
    counts["evidence_chain_count"] = len({x for x in evidence_chain_ids if x})
    counts["linked_claim_count"] = len({x for x in linked_claim_ids if x})
    counts["unlinked_claim_count"] = max(0, len(all_claim_ids) - counts["linked_claim_count"])
    counts["claim_count"] = len({x for x in all_claim_ids if x})
    if counts["linked_claim_count"] + counts["unlinked_claim_count"] != counts["claim_count"]:
        raise RuntimeError("projection claim link accounting invariant failed")
    counts["context_enriched_claim_count"] = sum(bool(row.get("context", {}).get("linked_chain_ids")) for row in merged["dossier_evidence"] if isinstance(row.get("context"), dict))
    counts_by_case = {}
    for case_id in sorted({row.get("case_id") for row in merged["dossier_evidence"] if row.get("case_id")}):
        case_rows = [row for row in merged["dossier_evidence"] if row.get("case_id") == case_id]
        case_claims = {row.get("claim_id") for row in case_rows if row.get("claim_id")}
        case_linked = {row.get("claim_id") for row in case_rows if row.get("evidence_chains")}
        case_chain_ids = {
            bundle.get("chain", {}).get("chain_id")
            for row in case_rows
            for bundle in (row.get("evidence_chains") or [])
            if isinstance(bundle, dict)
        }
        counts_by_case[case_id] = {
            "case_id": case_id,
            "projection_id": projection_id,
            "claim_count": len(case_claims),
            "evidence_chain_count": len({x for x in case_chain_ids if x}),
            "claim_evidence_link_count": sum(len(row.get("evidence_chains") or []) for row in case_rows),
            "linked_claim_count": len(case_linked),
            "unlinked_claim_count": max(0, len(case_claims) - len(case_linked)),
            "context_enriched_claim_count": sum(bool(row.get("context", {}).get("linked_chain_ids")) for row in case_rows if isinstance(row.get("context"), dict)),
        }
        if counts_by_case[case_id]["linked_claim_count"] + counts_by_case[case_id]["unlinked_claim_count"] != counts_by_case[case_id]["claim_count"]:
            raise RuntimeError(f"case claim link accounting invariant failed: {case_id}")
    counts["global_claim_count"] = counts["claim_count"]
    counts["global_evidence_chain_count"] = counts["evidence_chain_count"]
    counts["global_linked_claim_count"] = counts["linked_claim_count"]
    counts["global_unlinked_claim_count"] = counts["unlinked_claim_count"]
    _atomic_json(root / "dossier_index.json", merged["dossier_index"])
    for key, filename in (("claim_review_candidates", "claim_review_candidates.jsonl"), ("conflict_pair_candidates", "conflict_pair_candidates.jsonl"), ("context_candidates", "context_candidates.jsonl")):
        counts[key] = _write_jsonl(staging / filename, merged[key])
    sampling = {"schema_version": "evaluation_staging_v1", "automatic_import": False, "assignments_created": 0, "counts": {key: counts[key] for key in counts if key.endswith("candidates")}}
    _atomic_json(staging / "sampling_summary.json", sampling)
    for row in merged["predicted_claim_frame"]:
        row["projection_id"] = projection_id
    counts["predicted_claim_frame"] = _write_jsonl(staging / "predicted_claim_frame.jsonl", merged["predicted_claim_frame"])
    counts["source_text_unit_frame"] = _write_jsonl(staging / "source_text_unit_frame.jsonl", merged["source_text_unit_frame"])
    readiness = evaluation_readiness(merged["source_text_unit_frame"])
    readiness["frame_hash"] = sampling_frame_hash(merged["source_text_unit_frame"])
    readiness["projection_id"] = projection_id
    _atomic_json(staging / "claim_evaluation_readiness.json", readiness)
    case_metadata = {"schema_version": "atlas_case_metadata_v1", "items": [merged["case_metadata"][key] for key in sorted(merged["case_metadata"])]}
    _atomic_json(root / "case_metadata.json", case_metadata)
    for logical_name, rows in merged["display"].items(): _write_jsonl(root / f"{logical_name}.jsonl", rows)
    validation = {"status": "valid", "checks": {"evidence_not_kg_nodes": True, "formal_conflict_gate": True, "assignments_created": 0}, "counts": counts}
    _atomic_json(root / "validation_report.json", validation)
    manifest = {"schema_version": PROJECTION_SCHEMA_VERSION, "projection_id": projection_id, "adapter_version": adapter_version, "source_manifests": [{"case_id": item["manifest"]["case_id"], "source_run_id": item["manifest"]["source_run_id"], "manifest_hash": item.get("identity_hash") or item["manifest_hash"], "transport_manifest_hash": item["manifest_hash"], "handoff_schema_version": item["manifest"].get("schema_version"), "handoff_profile": _profile(item), "content_hash": item["manifest"].get("content_hash"), "prediction_run_id": _prediction_id(item, _adapter_version_for(item, adapter_version))} for item in sources], "counts": counts, "counts_by_case": counts_by_case, "case_metadata_schema_version": "atlas_case_metadata_v1", "claim_sampling_frame_scope": "selected_for_l1_extraction", "generated_at": datetime.now(timezone.utc).isoformat(), "validation_status": "valid"}
    _atomic_json(root / "projection_manifest.json", manifest)
    return manifest


def _case_active_registry(output_root: Path) -> dict[str, Any]:
    path = output_root / "active_projections_by_case.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {"schema_version": "atlas_case_active_projection_registry_v1", "cases": {}}


def _activate_cases(output_root: Path, projection_id: str, projection_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    registry = _case_active_registry(output_root)
    cases = registry.setdefault("cases", {})
    activated_at = datetime.now(timezone.utc).isoformat()
    activations = []
    for source in projection_manifest.get("source_manifests", []):
        case_id = source["case_id"]
        previous = cases.get(case_id, {}).get("active_projection_id")
        row = {
            "case_id": case_id,
            "active_projection_id": projection_id,
            "previous_projection_id": previous if previous != projection_id else cases.get(case_id, {}).get("previous_projection_id"),
            "activated_at": activated_at,
            "activation_source_run_id": source.get("source_run_id"),
            "scientific_run_id": source.get("source_run_id"),
            "projection_manifest_hash": source.get("manifest_hash"),
            "transport_manifest_hash": source.get("transport_manifest_hash"),
            "handoff_profile": source.get("handoff_profile") or FULLTEXT_REENTRY_PROFILE,
            "content_hash": source.get("content_hash"),
            "evidence_scope": "abstract_only" if source.get("handoff_profile") == ABSTRACT_L2_PROFILE else "fulltext_reentry",
            "schema_version": PROJECTION_SCHEMA_VERSION,
        }
        cases[case_id] = row
        activations.append(row)
    registry["updated_at"] = activated_at
    _atomic_json(output_root / "active_projections_by_case.json", registry)
    return activations


def sync_system_a(
    *, runs_root: str | Path = "runs", database_url: str | None = None, output_root: str | Path = "system_b_outputs/system_a_sync",
    manifest: str | Path | None = None, batch_id: str | None = None, adapter_version: str = ADAPTER_VERSION, dry_run: bool = False,
    quarantine_root: str | Path | None = None, no_database_write: bool = False, refresh_current_projection: bool = True,
    allow_evidence_scope_downgrade: bool = False,
) -> dict[str, Any]:
    paths = discover_handoffs(runs_root, manifest)
    if batch_id:
        paths = [path for path in paths if batch_id in path.parts[-3]]
    current_hashes = {}
    current_profiles = {}
    registry_path = Path(output_root) / "current_projection.json"
    if registry_path.is_file():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            projection_manifest = json.loads((Path(output_root) / registry["projection_relative_path"] / "projection_manifest.json").read_text(encoding="utf-8"))
            for source in projection_manifest.get("source_manifests", []):
                current_hashes[source["case_id"]] = source["manifest_hash"]
                current_profiles[source["case_id"]] = source.get("handoff_profile") or FULLTEXT_REENTRY_PROFILE
                source_path = Path(runs_root) / source["source_run_id"] / "artifacts/atlas_handoff_manifest.json"
                if source_path.is_file() and source_path.resolve() not in {item.resolve() for item in paths}: paths.append(source_path.resolve())
        except (OSError, KeyError, json.JSONDecodeError):
            current_hashes = {}; current_profiles = {}
    paths = sorted(paths)
    quarantine = Path(quarantine_root or Path(output_root) / "quarantine")
    valid = []; rejected = []
    for path in paths:
        try:
            _validate_ready(path)
            parsed = validate_handoff(path, runs_root=runs_root)
            profile = _profile(parsed)
            if profile == FULLTEXT_REENTRY_PROFILE and parsed["manifest"].get("adapter_hint") != "fulltext_reentry_v5":
                raise HandoffError("unsupported_adapter_hint", str(parsed["manifest"].get("adapter_hint")))
            if profile not in {FULLTEXT_REENTRY_PROFILE, ABSTRACT_L2_PROFILE}:
                raise HandoffError("unsupported_handoff_profile", profile)
            valid.append(parsed)
        except Exception as error:
            rejected.append({"manifest": str(path), "error_code": getattr(error, "code", type(error).__name__), "error_summary": str(error)})
    factory = session_factory(create_atlas_engine(database_url)) if not no_database_write else None
    existing_keys = set()
    if factory:
        session = factory()
        try:
            existing_keys = set(session.execute(select(SourceIngestion.case_id, SourceIngestion.manifest_hash, SourceIngestion.adapter_version).where(SourceIngestion.status == "completed")).all())
        except Exception:
            if not dry_run: raise
        finally: session.close()
    grouped = {}
    for item in valid: grouped.setdefault(item["manifest"]["case_id"], []).append(item)
    missing_current = sorted(set(current_hashes) - set(grouped))
    if missing_current:
        summary = ", ".join(missing_current)
        _write_failure_audit(output_root, code="current_projection_source_missing", summary=summary, rejected=rejected)
        raise HandoffError("current_projection_source_missing", summary)
    selected = []
    for case_id, candidates in sorted(grouped.items()):
        profile_priority = {FULLTEXT_REENTRY_PROFILE: 2, ABSTRACT_L2_PROFILE: 1}
        def candidate_sort_key(item: dict[str, Any]) -> tuple:
            manifest_value = item["manifest"]
            return (
                profile_priority.get(_profile(item), 0),
                str(manifest_value.get("completed_at") or manifest_value.get("generated_at") or manifest_value.get("created_at") or ""),
                str(manifest_value.get("source_run_id") or ""),
                item.get("identity_hash") or item["manifest_hash"],
            )
        current = [item for item in candidates if (item.get("identity_hash") or item["manifest_hash"]) == current_hashes.get(case_id)]
        fresh = [item for item in candidates if (case_id, item.get("identity_hash") or item["manifest_hash"], _adapter_version_for(item, adapter_version)) not in existing_keys and current_hashes.get(case_id) != (item.get("identity_hash") or item["manifest_hash"])]
        if (
            not allow_evidence_scope_downgrade
            and current_profiles.get(case_id) == FULLTEXT_REENTRY_PROFILE
            and current
            and fresh
            and all(_profile(item) == ABSTRACT_L2_PROFILE for item in fresh)
        ):
            selected.append(sorted(current, key=candidate_sort_key)[-1])
            continue
        if len(fresh) > 1:
            selected.append(sorted(fresh, key=candidate_sort_key)[-1])
            continue
        if fresh: selected.append(fresh[0]); continue
        if len(current) == 1: selected.append(current[0]); continue
        if candidates: selected.append(sorted(candidates, key=candidate_sort_key)[-1]); continue
        raise HandoffError("ambiguous_current_case_run", f"{case_id} has no selectable handoff")
    valid = selected
    new = [item for item in valid if (item["manifest"]["case_id"], item.get("identity_hash") or item["manifest_hash"], _adapter_version_for(item, adapter_version)) not in existing_keys and current_hashes.get(item["manifest"]["case_id"]) != (item.get("identity_hash") or item["manifest_hash"])]
    adapters = {FULLTEXT_REENTRY_PROFILE: FulltextReentryV5Adapter(), ABSTRACT_L2_PROFILE: AbstractL2ProjectionAdapter()}
    projects = [adapters[_profile(item)].project(item, prediction_run_id=_prediction_id(item, _adapter_version_for(item, adapter_version))) for item in valid]
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
    plan_counts["claim_count"] = len({row.get("claim_id") for row in merged["dossier_evidence"] if row.get("claim_id")})
    plan_counts["unlinked_claim_count"] = max(0, plan_counts["claim_count"] - plan_counts["linked_claim_count"])
    plan_counts["global_claim_count"] = plan_counts["claim_count"]
    plan_counts["global_evidence_chain_count"] = plan_counts["evidence_chain_count"]
    plan_counts["global_linked_claim_count"] = plan_counts["linked_claim_count"]
    plan_counts["global_unlinked_claim_count"] = plan_counts["unlinked_claim_count"]
    base_report = {"schema_version": "system_a_sync_report_v1", "ready_handoffs_scanned": len(paths), "valid_handoffs": len(valid), "new_ingestions": len(new), "no_op_ingestions": len(valid) - len(new), "quarantine_count": len(rejected), "rejected": rejected, "adapter_version": adapter_version, "counts": plan_counts, "database_write": bool(factory and not dry_run), "refresh_current_projection": bool(refresh_current_projection and not dry_run)}
    if dry_run:
        return {**base_report, "status": "dry_run", "cases": [{"case_id": item["manifest"]["case_id"], "source_run_id": item["manifest"]["source_run_id"], "manifest_hash": item["manifest_hash"], "counts": item["manifest"]["counts"]} for item in valid]}
    quarantine.mkdir(parents=True, exist_ok=True)
    for item in rejected:
        _atomic_json(quarantine / (hashlib.sha256(item["manifest"].encode()).hexdigest()[:20] + ".json"), item)
    if not new:
        current_projection = _current_id(Path(output_root))
        registry = _case_active_registry(Path(output_root))
        return {**base_report, "status": "no_op", "current_projection_id": current_projection,
                "atlas_sync_status": "completed", "atlas_activation_status": "active" if current_projection else "not_active",
                "case_activations": list((registry.get("cases") or {}).values())}
    projection_material = {"projection_schema_version": PROJECTION_SCHEMA_VERSION, "adapter_version": adapter_version, "cases": sorted((item["manifest"]["case_id"], _profile(item), item.get("identity_hash") or item["manifest_hash"]) for item in valid), "capability_summary_schema_version": "atlas_capability_effectiveness_v1"}
    projection_id = "projection_" + hashlib.sha256(canonical_json(projection_material)).hexdigest()[:24]
    output = Path(output_root); final = output / "projections" / projection_id
    temporary = output / "projections" / f".{projection_id}.{os.getpid()}.tmp"
    if temporary.exists(): shutil.rmtree(temporary)
    projection_manifest = _write_projection(temporary, projection_id, merged, valid, adapter_version)
    if factory:
        session = factory()
        try:
            for item in new:
                source = item["manifest"]
                item_adapter_version = _adapter_version_for(item, adapter_version)
                ingestion = SourceIngestion(case_id=source["case_id"], source_run_id=source["source_run_id"], manifest_hash=item.get("identity_hash") or item["manifest_hash"], handoff_schema_version=source["schema_version"], adapter_version=item_adapter_version, prediction_version=source["prediction_version"], status="projecting", namespace="system_a", discovered_at=utcnow(), started_at=utcnow(), projection_root=str(final), projection_identity_hash=projection_id.removeprefix("projection_"), domain_snapshot_json=json.dumps(source.get("domain_classification") or {}, ensure_ascii=False, sort_keys=True), capability_summary_json=json.dumps(source.get("capabilities") or {}, ensure_ascii=False, sort_keys=True))
                session.add(ingestion); session.flush()
                write_audit_event(session, action="source_ingestion_discovered", object_type="source_ingestion", object_id=ingestion.ingestion_id, case_id=source["case_id"], metadata={"source_run_id": source["source_run_id"], "manifest_hash": item["manifest_hash"]})
                write_audit_event(session, action="source_ingestion_validated", object_type="source_ingestion", object_id=ingestion.ingestion_id, case_id=source["case_id"], metadata={"schema_version": source["schema_version"]})
                write_audit_event(session, action="source_ingestion_projecting", object_type="source_ingestion", object_id=ingestion.ingestion_id, case_id=source["case_id"], metadata={"projection_id": projection_id})
                capability_names = {"input_fulltext_claims": "fulltext_l1", "fulltext_reasoning_traces": "reasoning_trace", "fulltext_context_consolidations": "context_consolidation", "reentry_manifest": "reentry"}
                for logical_name, spec in source["artifacts"].items():
                    capability = (source.get("capabilities") or {}).get(capability_names.get(logical_name, ""), {})
                    session.add(SourceArtifact(source_ingestion_id=ingestion.ingestion_id, logical_name=logical_name, relative_path=spec["relative_path"], sha256=spec["sha256"], size_bytes=spec["size_bytes"], record_count=spec.get("record_count"), required=bool(spec["required"]), validation_status="valid", schema_version=spec.get("schema_version") or "", adapter_status="supported" if capability.get("schema_supported", True) else "schema_unsupported", usable_record_count=capability.get("usable_record_count"), coverage=capability.get("coverage"), error_reason=capability.get("reason") or "", metadata_json=json.dumps(capability, ensure_ascii=False, sort_keys=True)))
                for previous in session.execute(select(PredictionRun).where(PredictionRun.case_id == source["case_id"], PredictionRun.is_current.is_(True))).scalars(): previous.is_current=False
                session.add(PredictionRun(prediction_run_id=_prediction_id(item, item_adapter_version), case_id=source["case_id"], source_ingestion_id=ingestion.ingestion_id, prediction_version=source["prediction_version"], system_a_git_commit=source.get("system_a_git_commit") or "", configuration_hash=source.get("configuration_hash") or "", source_completed_at=_parse_time(source.get("completed_at")), is_current=True))
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
    case_activations = _activate_cases(output, projection_id, projection_manifest)
    if refresh_current_projection:
        _atomic_json(output / "current_projection.json", {"schema_version": "atlas_current_projection_v1", "projection_id": projection_id, "projection_relative_path": f"projections/{projection_id}", "projection_manifest_sha256": sha256_file(final / "projection_manifest.json"), "updated_at": datetime.now(timezone.utc).isoformat()})
    return {**base_report, "status": "completed", "current_projection_id": projection_id, "projection_root": str(final),
            "atlas_sync_status": "completed", "atlas_activation_status": "active", "case_activations": case_activations,
            "database_ingestions_created": len(new) if factory else 0, "prediction_runs_created": len(new) if factory else 0}


def _parse_time(value: Any):
    if not value: return None
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError: return None


def _current_id(output: Path) -> str | None:
    try: return json.loads((output / "current_projection.json").read_text()).get("projection_id")
    except (OSError, json.JSONDecodeError): return None
