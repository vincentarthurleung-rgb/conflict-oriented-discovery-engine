"""Shared Atlas publication service for completed scientific runs."""
from __future__ import annotations

import json
import tempfile
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.integration.atlas_handoff import (
    ABSTRACT_L2_PROFILE,
    FULLTEXT_REENTRY_PROFILE,
    HandoffError,
    build_abstract_l2_handoff_manifest,
    build_handoff_manifest,
    publish_atlas_handoff,
    validate_handoff,
)
from code_engine.system_b.system_a_sync import sync_system_a

PUBLICATION_SCHEMA_VERSION = "atlas_publication_result_v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _run_id(run_dir: Path) -> str:
    return run_dir.resolve().name


def _case_id_from_run(run_dir: Path) -> str | None:
    artifacts = run_dir / "artifacts"
    for path in (artifacts / "case_domain_profile.json", artifacts / "replay_manifest.json", run_dir / "fulltext_reentry_manifest.json"):
        value = _read_json(path, {})
        if isinstance(value, dict) and value.get("case_id"):
            return str(value["case_id"])
    return None


def determine_handoff_profile(run_dir: str | Path, *, runs_root: str | Path = "runs") -> dict[str, Any]:
    """Return the highest-evidence valid handoff profile available for a completed run."""
    run = Path(run_dir).resolve()
    root = Path(runs_root).resolve()
    candidates: list[dict[str, Any]] = []
    for profile, builder in (
        (FULLTEXT_REENTRY_PROFILE, build_handoff_manifest),
        (ABSTRACT_L2_PROFILE, build_abstract_l2_handoff_manifest),
    ):
        try:
            manifest = builder(run, runs_root=root)
            candidates.append({
                "handoff_profile": profile,
                "status": "valid",
                "case_id": manifest.get("case_id"),
                "source_run_id": manifest.get("source_run_id") or run.name,
                "content_hash": manifest.get("content_hash"),
                "selection_reason": "fulltext_reentry_preferred" if profile == FULLTEXT_REENTRY_PROFILE else "abstract_l2_available",
            })
        except Exception as error:
            candidates.append({
                "handoff_profile": profile,
                "status": "rejected",
                "error_code": getattr(error, "code", type(error).__name__),
                "error_summary": str(error),
            })
    selected = next((item for item in candidates if item["handoff_profile"] == FULLTEXT_REENTRY_PROFILE and item["status"] == "valid"), None)
    selected = selected or next((item for item in candidates if item["handoff_profile"] == ABSTRACT_L2_PROFILE and item["status"] == "valid"), None)
    if not selected:
        raise HandoffError("no_publishable_handoff_profile", json.dumps(candidates, ensure_ascii=False))
    return {"selected": selected, "candidates": candidates}


def _prior_activation(output_root: Path, case_id: str | None) -> dict[str, Any]:
    if not case_id:
        return {}
    registry = _read_json(output_root / "active_projections_by_case.json", {})
    cases = registry.get("cases") if isinstance(registry, dict) else {}
    return cases.get(case_id, {}) if isinstance(cases, dict) else {}


def publish_completed_scientific_run(
    run_dir: str | Path,
    case_profile: str | Path | dict[str, Any] | None = None,
    atlas_config: dict[str, Any] | None = None,
    *,
    publication_source: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Publish one completed run into the aggregate Atlas projection without rerunning science."""
    run = Path(run_dir).resolve()
    config = atlas_config or {}
    runs_root = Path(config.get("runs_root") or run.parent).resolve()
    output_root_value = config.get("output_root") or config.get("system_b_output_root")
    case_id = _case_id_from_run(run)
    if case_profile and not case_id:
        profile_value = case_profile if isinstance(case_profile, dict) else _read_json(Path(case_profile), {})
        if isinstance(profile_value, dict) and profile_value.get("case_id"):
            case_id = str(profile_value["case_id"])
    base = {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "scientific_run_id": _run_id(run),
        "case_id": case_id,
        "publication_source": publication_source,
        "published_at": _now(),
        "error": None,
    }
    l1_summary = _read_json(run / "artifacts" / "fulltext_l1_v2_summary.json", {})
    unresolved_block_failures = bool(
        isinstance(l1_summary, dict)
        and (l1_summary.get("partial_block_failures") or l1_summary.get("scientific_input_complete") is False)
    )
    if unresolved_block_failures:
        output_root = Path(output_root_value) if output_root_value else None
        prior = _prior_activation(output_root, case_id) if output_root is not None else {}
        result = {
            **base,
            "handoff_status": "blocked",
            "atlas_sync_status": "blocked",
            "atlas_sync_reason": "unresolved_fulltext_l1_block_failures",
            "atlas_activation_status": "not_active",
            "previous_projection_id": prior.get("active_projection_id"),
            "active_projection_id": prior.get("active_projection_id"),
            "aggregate_projection_changed": False,
            "atlas_sync_retryable": True,
            "error": {"code": "scientific_input_incomplete", "summary": "failed fulltext blocks must be recovered before publication"},
        }
        _atomic_json(run / "artifacts" / "atlas_publication_result.json", result)
        return result
    if not output_root_value:
        return {
            **base,
            "handoff_status": "skipped",
            "atlas_sync_status": "skipped",
            "atlas_sync_reason": "atlas_not_configured",
            "atlas_activation_status": "not_active",
            "aggregate_projection_changed": False,
        }
    output_root = Path(output_root_value)
    prior = _prior_activation(output_root, case_id)
    try:
        selection = determine_handoff_profile(run, runs_root=runs_root)
        profile = selection["selected"]["handoff_profile"]
        if dry_run:
            result = {
                **base,
                "handoff_profile": profile,
                "handoff_status": "would_publish",
                "profile_selection": selection,
                "atlas_sync_status": "dry_run",
                "atlas_activation_status": "not_active",
                "previous_projection_id": prior.get("active_projection_id"),
                "aggregate_projection_changed": False,
            }
            _atomic_json(run / "artifacts" / "atlas_publication_result.json", result)
            return result
        publish_kwargs: dict[str, Any] = {"runs_root": runs_root, "handoff_profile": profile}
        if config.get("lineage"):
            publish_kwargs["lineage"] = config["lineage"]
        published = publish_atlas_handoff(run, **publish_kwargs)
        validated = validate_handoff(published["manifest_path"], runs_root=runs_root)
        manifest = validated["manifest"]
        sync = sync_system_a(
            runs_root=runs_root,
            output_root=output_root,
            manifest=published["manifest_path"],
            database_url=config.get("database_url"),
            no_database_write=bool(config.get("no_database_write", True)),
            refresh_current_projection=bool(config.get("refresh_current_projection", True)),
            allow_evidence_scope_downgrade=bool(config.get("allow_evidence_scope_downgrade", False)),
        )
        activation = next((row for row in sync.get("case_activations", []) if row.get("case_id") == manifest.get("case_id")), {})
        if not activation:
            activation = _prior_activation(output_root, manifest.get("case_id"))
        projection_id = sync.get("current_projection_id")
        previous_projection_id = activation.get("previous_projection_id") or prior.get("active_projection_id")
        result = {
            **base,
            "case_id": manifest.get("case_id") or case_id,
            "handoff_profile": profile,
            "handoff_status": "completed",
            "handoff_manifest": published["manifest_path"],
            "handoff_manifest_hash": validated.get("manifest_hash"),
            "handoff_identity_hash": validated.get("identity_hash"),
            "handoff_content_hash": manifest.get("content_hash"),
            "case_content_hash": manifest.get("content_hash"),
            "profile_selection": selection,
            "atlas_sync_status": "completed" if sync.get("status") in {"completed", "no_op"} else sync.get("status"),
            "sync_status": sync.get("status"),
            "atlas_activation_status": sync.get("atlas_activation_status"),
            "projection_id": projection_id,
            "previous_projection_id": previous_projection_id,
            "active_projection_id": activation.get("active_projection_id") or projection_id,
            "aggregate_projection_changed": sync.get("status") == "completed" and projection_id != prior.get("active_projection_id"),
            "atlas_sync_retryable": False,
            "error": None,
        }
        _atomic_json(run / "artifacts" / "atlas_publication_result.json", result)
        return result
    except Exception as error:
        result = {
            **base,
            "handoff_status": "failed",
            "atlas_sync_status": "failed",
            "atlas_activation_status": "not_active",
            "atlas_sync_retryable": True,
            "previous_projection_id": prior.get("active_projection_id"),
            "aggregate_projection_changed": False,
            "error": {"code": getattr(error, "code", type(error).__name__), "summary": str(error)},
        }
        _atomic_json(run / "artifacts" / "atlas_publication_result.json", result)
        return result
