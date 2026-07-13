"""Final cross-boundary verification for one-command orchestration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from code_engine.integration.atlas_handoff import sha256_file, validate_handoff
from code_engine.system_b.adapters import ADAPTER_VERSION
from code_engine.system_b.persistence.database import create_atlas_engine, session_factory
from code_engine.system_b.persistence.models import Annotation, Assignment, GoldRecord, MetricRun, PredictionRun, ReviewItem, SourceIngestion


def _jsonl(path: Path) -> list[dict]:
    if not path.is_file(): return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluation_counts(database_url: str) -> dict[str, int]:
    factory = session_factory(create_atlas_engine(database_url)); session = factory()
    try:
        return {"review_items": session.scalar(select(func.count()).select_from(ReviewItem)) or 0,
                "assignments": session.scalar(select(func.count()).select_from(Assignment)) or 0,
                "annotations": session.scalar(select(func.count()).select_from(Annotation)) or 0,
                "gold": session.scalar(select(func.count()).select_from(GoldRecord)) or 0,
                "metrics": session.scalar(select(func.count()).select_from(MetricRun)) or 0}
    finally: session.close()


def current_projection(output_root: Path) -> tuple[dict, Path, dict]:
    registry = json.loads((output_root / "current_projection.json").read_text(encoding="utf-8"))
    relative = Path(registry["projection_relative_path"])
    if relative.is_absolute() or ".." in relative.parts: raise ValueError("unsafe current projection path")
    root = (output_root / relative).resolve()
    if output_root.resolve() not in root.parents: raise ValueError("current projection escapes output root")
    manifest_path = root / "projection_manifest.json"
    expected_hash = registry.get("projection_manifest_sha256")
    if not expected_hash or sha256_file(manifest_path) != expected_hash:
        raise ValueError("current projection manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return registry, root, manifest


def verify_case_to_atlas(*, case_id: str, reentry_run: Path, handoff_manifest: Path, runs_root: Path,
                         database_url: str, output_root: Path, safety_baseline: dict, prior_cases: list[str]) -> dict[str, Any]:
    validated = validate_handoff(handoff_manifest, runs_root=runs_root)
    source = validated["manifest"]
    factory = session_factory(create_atlas_engine(database_url)); session = factory()
    try:
        ingestion = session.execute(select(SourceIngestion).where(SourceIngestion.source_run_id == source["source_run_id"], SourceIngestion.manifest_hash == validated["manifest_hash"], SourceIngestion.adapter_version == ADAPTER_VERSION)).scalar_one_or_none()
        if not ingestion or ingestion.status != "completed": raise ValueError("completed ingestion missing")
        prediction = session.execute(select(PredictionRun).where(PredictionRun.source_ingestion_id == ingestion.ingestion_id)).scalar_one_or_none()
        if not prediction: raise ValueError("prediction run missing")
    finally: session.close()
    registry, projection_root, projection_manifest = current_projection(output_root)
    current_cases = sorted({row["case_id"] for row in projection_manifest.get("source_manifests", [])})
    if case_id not in current_cases: raise ValueError("current projection does not contain requested case")
    lost = sorted(set(prior_cases) - set(current_cases))
    if lost: raise ValueError("current projection lost prior cases: " + ", ".join(lost))
    evidence = _jsonl(projection_root / "dossier_evidence.jsonl")
    contexts = _jsonl(projection_root / "context_rows.jsonl")
    exploratory = _jsonl(projection_root / "exploratory_triples.jsonl")
    conflicts = _jsonl(projection_root / "conflict_predictions.jsonl")
    case_evidence = [row for row in evidence if row.get("case_id") == case_id]
    if len(case_evidence) < int(source["counts"]["input_fulltext_claim_count"]): raise ValueError("dossier evidence below legal claim count")
    if any(row.get("conflict_eligible") is not True for row in conflicts): raise ValueError("formal conflict gate violation")
    forbidden = {"evidence", "paper", "claim"}
    if any(str(row.get("entity_type") or "").casefold() in forbidden for row in _jsonl(projection_root / "display_entities_v2.jsonl")): raise ValueError("provenance object became KG node")
    after = evaluation_counts(database_url)
    if after != safety_baseline: raise ValueError(f"evaluation state changed: before={safety_baseline}, after={after}")
    quarantine = list((output_root / "quarantine").glob("*.json")) if (output_root / "quarantine").is_dir() else []
    return {"status": "passed", "ingestion_id": ingestion.ingestion_id, "prediction_run_id": prediction.prediction_run_id,
            "projection_id": registry["projection_id"], "current_cases": current_cases, "current_case_count": len(current_cases),
            "prior_cases_preserved": not lost, "claim_count": source["counts"]["input_fulltext_claim_count"],
            "case_dossier_evidence_count": len(case_evidence), "dossier_count": json.loads((projection_root / "dossier_index.json").read_text())["dossier_count"],
            "context_row_count": sum(row.get("case_id") == case_id for row in contexts),
            "exploratory_triple_count": sum(case_id in (row.get("case_ids") or []) for row in exploratory),
            "formal_conflict_count": sum(row.get("case_id") == case_id for row in conflicts),
            "evaluation_counts": after, "quarantine_count": len(quarantine), "projection_root": str(projection_root)}
