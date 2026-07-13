"""Versioned, offline System A -> Atlas handoff publication and validation."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

HANDOFF_SCHEMA_VERSION = "atlas_handoff_v1"
MANIFEST_NAME = "atlas_handoff_manifest.json"
READY_NAME = "ATLAS_READY"
LANE_FILES = {
    "core_seed_relation": "artifacts/fulltext_core_seed_observations.jsonl",
    "seed_neighborhood_mechanism": "artifacts/fulltext_seed_neighborhood_observations.jsonl",
    "reviewable_context_relation": "artifacts/fulltext_reviewable_relations.jsonl",
    "off_seed_relation": "artifacts/fulltext_off_seed_relations.jsonl",
}
REQUIRED_ARTIFACTS = {
    "reentry_manifest": "fulltext_reentry_manifest.json",
    "input_fulltext_claims": "artifacts/l35_fulltext_l1_claims.jsonl",
    **{f"lane_{key}": value for key, value in LANE_FILES.items()},
}
OPTIONAL_ARTIFACTS = {
    "paper_manifest": "artifacts/run_paper_manifest.jsonl",
    "reentry_audit": "artifacts/fulltext_reentry_audit.jsonl",
    "conflict_confirmations": "artifacts/l35_fulltext_conflict_confirmations.jsonl",
    "fulltext_claim_passage_index": "artifacts/fulltext_claim_passage_index.jsonl",
    "fulltext_reasoning_traces": "artifacts/fulltext_reasoning_traces.jsonl",
    "fulltext_reasoning_trace_summary": "artifacts/fulltext_reasoning_trace_summary.json",
    "fulltext_context_consolidations": "artifacts/fulltext_context_consolidations.jsonl",
    "fulltext_context_consolidation_summary": "artifacts/fulltext_context_consolidation_summary.json",
}


class HandoffError(ValueError):
    """Structured handoff contract failure."""

    def __init__(self, code: str, summary: str):
        self.code = code
        self.summary = summary
        super().__init__(f"{code}: {summary}")


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HandoffError("malformed_json", f"cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise HandoffError("invalid_json_type", f"{path.name} must contain an object")
    return value


def _jsonl_count(path: Path) -> int:
    count = 0
    try:
        with path.open(encoding="utf-8") as handle:
            for index, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as error:
                    raise HandoffError("malformed_jsonl", f"{path.name}:{index}: {error}") from error
                if not isinstance(value, dict):
                    raise HandoffError("invalid_jsonl_record", f"{path.name}:{index} must be an object")
                count += 1
    except OSError as error:
        raise HandoffError("artifact_read_error", f"cannot read {path}: {error}") from error
    return count


def safe_relative_path(value: str) -> PurePosixPath:
    if not value or "\\" in value:
        raise HandoffError("unsafe_path", f"invalid relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise HandoffError("unsafe_path", f"absolute or traversing path rejected: {value!r}")
    return path


def resolve_artifact(run_dir: Path, relative_path: str) -> Path:
    rel = safe_relative_path(relative_path)
    root = run_dir.resolve()
    path = (root / Path(*rel.parts)).resolve()
    if path != root and root not in path.parents:
        raise HandoffError("path_escape", f"artifact escapes run root: {relative_path}")
    return path


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _lineage_value(value: Any, runs_root: Path) -> str | None:
    if not value:
        return None
    path = Path(str(value))
    if path.is_absolute():
        try:
            return path.resolve().relative_to(runs_root.resolve()).as_posix()
        except ValueError:
            return path.name
    parts = path.parts
    return Path(*parts[1:]).as_posix() if parts and parts[0] == runs_root.name else path.as_posix()


def build_handoff_manifest(
    run_dir: str | Path,
    *,
    runs_root: str | Path = "runs",
    lineage: dict[str, Any] | None = None,
    prediction_version: str = "fulltext_reentry_v5",
    pipeline_profile: str = "fulltext_reentry_high_recall_v5",
    adapter_hint: str = "fulltext_reentry_v5",
) -> dict[str, Any]:
    run = Path(run_dir).resolve()
    root = Path(runs_root).resolve()
    try:
        run_relative = run.relative_to(root).as_posix()
    except ValueError as error:
        raise HandoffError("run_outside_root", f"run {run} is outside allowed root {root}") from error
    source = _json(run / "fulltext_reentry_manifest.json")
    if source.get("status") != "completed" or source.get("network_used") not in (False, None) or source.get("api_used") not in (False, None):
        raise HandoffError("run_not_publishable", "re-entry manifest is not a completed offline run")
    case_id = str(source.get("case_id") or "")
    if not case_id:
        raise HandoffError("missing_case_id", "re-entry manifest has no case_id")

    artifact_specs: dict[str, dict[str, Any]] = {}
    for required, mapping in ((True, REQUIRED_ARTIFACTS), (False, OPTIONAL_ARTIFACTS)):
        for logical_name, relative in mapping.items():
            path = resolve_artifact(run, relative)
            if not path.is_file():
                if required:
                    raise HandoffError("missing_required_artifact", relative)
                continue
            artifact_specs[logical_name] = {
                "relative_path": relative,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "record_count": _jsonl_count(path) if path.suffix == ".jsonl" else None,
                "required": required,
            }

    input_count = artifact_specs["input_fulltext_claims"]["record_count"]
    lane_counts = {lane: artifact_specs[f"lane_{lane}"]["record_count"] for lane in LANE_FILES}
    if input_count != sum(lane_counts.values()):
        raise HandoffError("lane_accounting_mismatch", f"input={input_count}, lane_sum={sum(lane_counts.values())}")
    for key, actual in lane_counts.items():
        declared = source.get(f"{key}_count")
        if declared is None or int(declared) != actual:
            raise HandoffError("declared_count_mismatch", f"{key}: declared={declared}, actual={actual}")
    if int(source.get("input_fulltext_claim_count", -1)) != input_count:
        raise HandoffError("declared_count_mismatch", "input_fulltext_claim_count does not match JSONL")

    audit_path = run / OPTIONAL_ARTIFACTS["reentry_audit"]
    exploratory = conflict = 0
    if audit_path.is_file():
        with audit_path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                exploratory += row.get("exploratory_graph_eligible") is True
                conflict += row.get("conflict_eligible") is True
    if exploratory != int(source.get("exploratory_graph_eligible_count", -1)):
        raise HandoffError("declared_count_mismatch", "exploratory_graph_eligible_count does not match audit")
    if conflict != int(source.get("conflict_eligible_count", -1)):
        raise HandoffError("declared_count_mismatch", "conflict_eligible_count does not match audit")

    source_lineage = lineage or {}
    effective_lineage = {
        "base_run": source_lineage.get("base_run", source.get("base_run")),
        "pmcid_repair_run": source_lineage.get("pmcid_repair_run"),
        "fulltext_l1_run": source_lineage.get("fulltext_l1_run", source.get("fulltext_run")),
        "reentry_run": source_lineage.get("reentry_run", run_relative),
    }
    effective_lineage = {key: _lineage_value(value, root) for key, value in effective_lineage.items()}
    completed_at = source.get("completed_at") or source.get("created_at")
    configuration_material = {
        "prediction_version": prediction_version,
        "pipeline_profile": pipeline_profile,
        "adapter_hint": adapter_hint,
        "source_artifacts": {key: value["sha256"] for key, value in sorted(artifact_specs.items())},
    }
    return {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "case_id": case_id,
        "source_run_id": run.name,
        "source_run_relative_path": run_relative,
        "run_status": "completed",
        "prediction_version": prediction_version,
        "pipeline_profile": pipeline_profile,
        "adapter_hint": adapter_hint,
        "lineage": effective_lineage,
        "artifacts": dict(sorted(artifact_specs.items())),
        "counts": {
            "input_fulltext_claim_count": input_count,
            **{f"{key}_count": value for key, value in lane_counts.items()},
            "exploratory_graph_eligible_count": exploratory,
            "conflict_eligible_count": conflict,
        },
        "available_capabilities": [
            "fulltext_claims",
            *(
                ["reasoning_traces", "experimental_context", "dossier_reasoning_view"]
                if "fulltext_reasoning_traces" in artifact_specs else []
            ),
        ],
        "system_a_git_commit": _git_commit(),
        "configuration_hash": hashlib.sha256(canonical_json(configuration_material)).hexdigest(),
        "generated_at": completed_at or datetime.now(timezone.utc).isoformat(),
        "completed_at": completed_at,
    }


def validate_handoff(manifest_path: str | Path, *, runs_root: str | Path = "runs", verify_hashes: bool = True) -> dict[str, Any]:
    path = Path(manifest_path).resolve()
    manifest = _json(path)
    if manifest.get("schema_version") != HANDOFF_SCHEMA_VERSION:
        raise HandoffError("unsupported_schema", str(manifest.get("schema_version")))
    if manifest.get("run_status") != "completed":
        raise HandoffError("run_not_completed", str(manifest.get("run_status")))
    root = Path(runs_root).resolve()
    run_relative = safe_relative_path(str(manifest.get("source_run_relative_path") or ""))
    run = (root / Path(*run_relative.parts)).resolve()
    if root not in run.parents:
        raise HandoffError("run_outside_root", str(run))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise HandoffError("invalid_artifacts", "artifacts must be an object")
    warnings = []
    for logical_name, spec in artifacts.items():
        if not isinstance(spec, dict):
            raise HandoffError("invalid_artifact_spec", str(logical_name))
        artifact = resolve_artifact(run, str(spec.get("relative_path") or ""))
        if not artifact.is_file():
            if spec.get("required"):
                raise HandoffError("missing_required_artifact", str(logical_name))
            warnings.append({"logical_name": logical_name, "warning": "optional_artifact_missing"})
            continue
        if verify_hashes and sha256_file(artifact) != spec.get("sha256"):
            raise HandoffError("hash_mismatch", str(logical_name))
        if artifact.stat().st_size != spec.get("size_bytes"):
            raise HandoffError("size_mismatch", str(logical_name))
        if artifact.suffix == ".jsonl" and _jsonl_count(artifact) != spec.get("record_count"):
            raise HandoffError("record_count_mismatch", str(logical_name))
    return {"manifest": manifest, "manifest_hash": sha256_file(path), "run_dir": run, "warnings": warnings}


def publish_atlas_handoff(run_dir: str | Path, **kwargs: Any) -> dict[str, Any]:
    run = Path(run_dir).resolve()
    artifacts = run / "artifacts"
    manifest_path = artifacts / MANIFEST_NAME
    ready_path = artifacts / READY_NAME
    manifest = build_handoff_manifest(run, **kwargs)
    payload = canonical_json(manifest)
    digest = hashlib.sha256(payload).hexdigest()
    marker = canonical_json({"schema_version": HANDOFF_SCHEMA_VERSION, "manifest_sha256": digest})
    if manifest_path.is_file() and ready_path.is_file():
        if manifest_path.read_bytes() == payload and ready_path.read_bytes() == marker:
            return {"status": "no_op", "manifest_path": str(manifest_path), "manifest_hash": digest, "manifest": manifest}
    _atomic_write(manifest_path, payload)
    validated = validate_handoff(manifest_path, runs_root=kwargs.get("runs_root", "runs"))
    if validated["manifest_hash"] != digest:
        raise HandoffError("manifest_hash_mismatch", "post-write validation changed manifest hash")
    _atomic_write(ready_path, marker)
    return {"status": "published", "manifest_path": str(manifest_path), "manifest_hash": digest, "manifest": manifest}
