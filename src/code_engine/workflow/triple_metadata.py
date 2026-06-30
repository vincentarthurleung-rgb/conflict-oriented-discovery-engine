"""Post-run seed-triple cards and resume-safe manifests."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.schemas.triples import SeedTriple
from code_engine.workflow.models import RunState


TRIPLE_META_FIELDS = ("batch_id", "triple_id", "query_id", "query_hash", "seed_triple", "seed_triple_title")
SUMMARY_ARTIFACTS = (
    "l2_abstract_summary.json", "l2_fulltext_summary.json", "hypothesis_summary.json",
    "conflict_evidence_timeline_summary.json", "validation_summary.json",
)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def triple_metadata(seed: SeedTriple, batch_id: str | None) -> dict[str, Any]:
    return {
        "batch_id": batch_id, "triple_id": seed.triple_id, "query_id": seed.query_hash[:16],
        "query_hash": seed.query_hash, "seed_triple": seed.model_dump(mode="json"),
        "seed_triple_title": seed.display_title,
    }


def write_triple_run_manifest(
    run_dir: Path, state: RunState, seed: SeedTriple, batch_id: str | None,
    *, input_hash: str | None = None, status: str = "running",
) -> Path:
    target = Path(run_dir) / "triple_run_manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    payload = {
        **existing, **triple_metadata(seed, batch_id), "run_id": state.run_id,
        "run_dir": str(Path(run_dir).resolve()), "input_hash": input_hash,
        "status": status, "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _artifact_path(state: RunState, *names: str) -> str | None:
    for name in names:
        if state.artifacts.get(name):
            return state.artifacts[name]
    return None


def finalize_triple_card(
    run_dir: Path, state: RunState, seed: SeedTriple, batch_id: str | None,
    *, input_hash: str | None = None,
) -> tuple[Path, Path]:
    directory = Path(run_dir).resolve()
    blocked = any(item.status in {"blocked", "failed"} for item in state.steps.values())
    status = "blocked" if state.failed_step else ("partial" if blocked else "completed")
    paths = {
        "final_report": _artifact_path(state, "final_report", "final_report_markdown"),
        "graph_conflicts": _artifact_path(state, "evidence_graph_core_conflicts", "graph_conflict_candidates"),
        "hypotheses": _artifact_path(state, "hypothesis_hyperedges"),
        "timeline": _artifact_path(state, "conflict_evidence_timelines"),
        "validation": _artifact_path(state, "validation_summary"),
    }
    summary = {
        "paper_count": int(state.paper_dedup_total or state.counts.get("candidate_paper_count", 0)),
        "claim_count": int(state.counts.get("abstract_claim_count", 0) + state.counts.get("fulltext_claim_count", 0)),
        "relation_bundle_count": int(state.counts.get("relation_bundle_count", 0)),
        "conflict_count": int(state.counts.get("graph_conflict_candidate_count", state.counts.get("conflict_edge_count", 0))),
        "hypothesis_count": int(state.hypothesis_count),
        "timeline_count": int(state.counts.get("conflict_timeline_count", 0)),
    }
    card = {
        **triple_metadata(seed, batch_id), "display_title": seed.display_title,
        "run_id": state.run_id, "run_dir": str(directory), "artifact_paths": paths,
        "summary": summary, "status": status, "warnings": list(state.warnings),
        "created_at": state.created_at,
    }
    card_path = directory / "triple_card.json"
    card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    required_candidates = [
        card_path,
        directory / "final_report.md",
        directory / "artifacts/runtime_provenance_report.json",
        directory / "artifacts/pilot_readiness_report.json",
        directory / "artifacts/final_report.json",
        *(Path(path) for path in paths.values() if path),
    ]
    required = sorted({path.resolve() for path in required_candidates if path.is_file()})
    manifest_path = write_triple_run_manifest(directory, state, seed, batch_id, input_hash=input_hash, status=status)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["required_artifact_hashes"] = {str(path.relative_to(directory)): file_hash(path) for path in required}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return card_path, manifest_path


def annotate_summary_artifacts(run_dir: Path, seed: SeedTriple, batch_id: str | None) -> None:
    """Attach experiment identity to JSON summaries without altering reasoning records."""

    metadata = triple_metadata(seed, batch_id)
    artifacts = Path(run_dir) / "artifacts"
    for name in SUMMARY_ARTIFACTS:
        path = artifacts / name
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payload.update(metadata)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resume_manifest_valid(run_dir: Path, input_hash: str) -> bool:
    directory = Path(run_dir)
    path = directory / "triple_run_manifest.json"
    if not path.is_file():
        return False
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if manifest.get("input_hash") != input_hash or manifest.get("status") not in {"completed", "partial"}:
        return False
    hashes = manifest.get("required_artifact_hashes") or {}
    return bool(hashes) and all((directory / name).is_file() and file_hash(directory / name) == expected for name, expected in hashes.items())


__all__ = ["TRIPLE_META_FIELDS", "SUMMARY_ARTIFACTS", "triple_metadata", "write_triple_run_manifest", "annotate_summary_artifacts", "finalize_triple_card", "resume_manifest_valid", "file_hash"]
