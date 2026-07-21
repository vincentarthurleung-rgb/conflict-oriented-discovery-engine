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

LEGACY_HANDOFF_SCHEMA_VERSION = "atlas_handoff_v1"
HANDOFF_SCHEMA_VERSION = "atlas_handoff_v2"
SUPPORTED_HANDOFF_SCHEMA_VERSIONS = {LEGACY_HANDOFF_SCHEMA_VERSION, HANDOFF_SCHEMA_VERSION}
FULLTEXT_REENTRY_PROFILE = "fulltext_reentry"
ABSTRACT_L2_PROFILE = "abstract_l2_projection"
SUPPORTED_HANDOFF_PROFILES = {FULLTEXT_REENTRY_PROFILE, ABSTRACT_L2_PROFILE}
CAPABILITY_SCHEMA_VERSION = "atlas_capability_effectiveness_v1"
DOMAIN_TAXONOMY_VERSION = "code_domain_taxonomy_v1"
SOURCE_UNIT_SCHEMA_VERSION = "claim_source_unit_v1"
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
    "experimental_evidence_chains": "artifacts/experimental_evidence_chains.jsonl",
    "evidence_reasoning_chains": "artifacts/evidence_reasoning_chains.jsonl",
    "fulltext_entity_upgrade_audit": "artifacts/fulltext_entity_upgrade_audit.jsonl",
    "canonical_edge_evidence_families": "artifacts/canonical_edge_evidence_families.jsonl",
    "claim_evidence_links": "artifacts/claim_evidence_links.jsonl",
    "unlinked_claim_reasons": "artifacts/unlinked_claim_reasons.jsonl",
    "experimental_evidence_chain_summary": "artifacts/experimental_evidence_chain_summary.json",
    "fulltext_context_consolidations": "artifacts/fulltext_context_consolidations.jsonl",
    "fulltext_context_consolidation_summary": "artifacts/fulltext_context_consolidation_summary.json",
    "source_text_units": "artifacts/claim_evaluation_source_units.jsonl",
}
ABSTRACT_L2_REQUIRED_ARTIFACTS = {
    "case_profile": "artifacts/case_domain_profile.json",
    "search_plan": "artifacts/search_plan.json",
    "abstract_l1_claims": "artifacts/abstract_l1_claims.jsonl",
    "run_summary": "artifacts/replay_terminal_state_audit.json",
    "entity_normalization_summary": "artifacts/l2_abstract_summary.json",
    "l2_core_graph_observations": "artifacts/l2_core_graph_observations.jsonl",
    "core_graph_gate_audit": "artifacts/core_graph_gate_audit.jsonl",
    "formal_graph_edges": "artifacts/merged_evidence_graph_edges.jsonl",
    "formal_graph_nodes": "artifacts/merged_evidence_graph_nodes.jsonl",
    "graph_conflict_summary": "artifacts/graph_conflict_summary.json",
    "graph_conflict_candidates": "artifacts/graph_conflict_candidates.jsonl",
    "hypothesis_summary": "artifacts/hypothesis_summary.json",
}
ABSTRACT_L2_OPTIONAL_ARTIFACTS = {
    "l2_abstract_observations": "artifacts/l2_abstract_observations.json",
    "l2_graph_observations": "artifacts/l2_graph_observations.jsonl",
    "merged_evidence_graph_summary": "artifacts/merged_evidence_graph_summary.json",
    "core_observation_summary": "artifacts/core_observation_summary.json",
    "core_observations": "artifacts/core_observations.jsonl",
    "formal_graph_backfill_summary": "artifacts/formal_graph_backfill_summary.json",
    "run_paper_manifest": "artifacts/run_paper_manifest.jsonl",
    "context_compatibility_audit": "artifacts/context_compatibility_audit.jsonl",
}

SUPPORTED_ARTIFACT_SCHEMAS = {
    "input_fulltext_claims": {"fulltext_l1_claim_v1_legacy", "fulltext_l1_claim_v1", "fulltext_l1_claim_v2"},
    "fulltext_reasoning_traces": {"fulltext_reasoning_trace_v1", "fulltext_reasoning_trace_v2"},
    "fulltext_context_consolidations": {"fulltext_context_consolidation_v1", "fulltext_context_consolidation_v2"},
    "evidence_reasoning_chains": {"evidence_reasoning_chain_v2"},
    "source_text_units": {SOURCE_UNIT_SCHEMA_VERSION},
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


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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
            rows.append(value)
    return rows


def _artifact_schema_version(logical_name: str, path: Path) -> str | None:
    if logical_name == "input_fulltext_claims":
        rows = _jsonl_rows(path)
        versions = {str(row.get("schema_version")) for row in rows if row.get("schema_version")}
        return versions.pop() if len(versions) == 1 else "fulltext_l1_claim_v1_legacy" if not versions else "mixed"
    if path.suffix == ".jsonl" and logical_name in SUPPORTED_ARTIFACT_SCHEMAS:
        versions = {str(row.get("schema_version")) for row in _jsonl_rows(path) if row.get("schema_version")}
        if logical_name == "source_text_units" and not versions:
            return SOURCE_UNIT_SCHEMA_VERSION
        return versions.pop() if len(versions) == 1 else "mixed" if versions else None
    if path.suffix == ".json":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise HandoffError("malformed_json", f"cannot read {path.name}: {error}") from error
        return str(value.get("schema_version") or "") or None if isinstance(value, dict) else None
    return None


def _artifact_spec(run: Path, logical_name: str, relative: str, required: bool) -> dict[str, Any] | None:
    path = resolve_artifact(run, relative)
    if not path.is_file():
        if required:
            raise HandoffError("missing_required_artifact", relative)
        return None
    return {
        "relative_path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "record_count": _jsonl_count(path) if path.suffix == ".jsonl" else None,
        "required": required,
        "schema_version": _artifact_schema_version(logical_name, path),
    }


def _nonempty(value: Any) -> bool:
    if value in (None, "", [], {}):
        return False
    if isinstance(value, list):
        return any(_nonempty(item) for item in value)
    if isinstance(value, dict) and "value" in value:
        return _nonempty(value.get("value"))
    return True


def _reasoning_step_has_provenance(step: Any) -> bool:
    if not isinstance(step, dict):
        return False
    return any(_nonempty(step.get(key)) for key in (
        "sentence_ids", "passage_ids", "source_spans", "evidence_anchor_ids", "provenance",
    ))


def _reasoning_usable(row: dict[str, Any]) -> bool:
    status = str(row.get("trace_status") or "").casefold()
    steps = row.get("reasoning_steps")
    return status in {"complete", "partial", "reasoning_complete", "reasoning_partial"} and isinstance(steps, list) and bool(steps) and any(_reasoning_step_has_provenance(step) for step in steps)


def _context_slots(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("consolidated_context")
    return value if isinstance(value, dict) else {}


def _context_nonempty(row: dict[str, Any]) -> bool:
    return any(_nonempty(value) for value in _context_slots(row).values()) or any(
        _nonempty(value) for value in (row.get("field_provenance") or {}).values()
    )


def _capability_status(*, present: bool, count: int, usable: int, partial_allowed: bool = False) -> str:
    if not present:
        return "artifact_missing"
    if count == 0:
        return "available_no_records"
    if usable == count:
        return "available"
    if usable == 0:
        return "produced_but_unusable"
    return "partial" if partial_allowed else "produced_but_unusable"


def _capability_summary(run: Path, specs: dict[str, dict[str, Any]], *, conflict_count: int) -> dict[str, Any]:
    def rows(name: str) -> list[dict[str, Any]]:
        spec = specs.get(name)
        return _jsonl_rows(resolve_artifact(run, spec["relative_path"])) if spec else []

    claims = rows("input_fulltext_claims")
    traces = rows("fulltext_reasoning_traces")
    contexts = rows("fulltext_context_consolidations")
    reasoning_usable = sum(_reasoning_usable(row) for row in traces)
    context_usable = sum(_context_nonempty(row) for row in contexts)
    slot_names = sorted({slot for row in contexts for slot in _context_slots(row)})
    slot_coverage = {
        slot: round(sum(_nonempty(_context_slots(row).get(slot)) for row in contexts) / len(contexts), 6)
        if contexts else 0.0
        for slot in slot_names
    }
    reasons = []
    for row in traces:
        for missing in row.get("missing_links") or []:
            if isinstance(missing, dict) and missing.get("reason"):
                reasons.append(str(missing["reason"]))
    reason = max(set(reasons), key=reasons.count) if reasons else None
    def base(name: str, records: list[dict[str, Any]], usable: int) -> dict[str, Any]:
        spec = specs.get(name)
        schema = spec.get("schema_version") if spec else None
        supported = schema in SUPPORTED_ARTIFACT_SCHEMAS.get(name, {schema}) if schema else name not in SUPPORTED_ARTIFACT_SCHEMAS
        return {
            "declared": bool(spec), "artifact_present": bool(spec), "hash_valid": bool(spec),
            "schema_supported": supported, "schema_version": schema,
            "record_count": len(records), "usable_record_count": usable,
            "coverage": round(usable / len(records), 6) if records else 0.0,
        }
    fulltext = base("input_fulltext_claims", claims, len(claims))
    fulltext["status"] = _capability_status(present=bool(specs.get("input_fulltext_claims")), count=len(claims), usable=len(claims))
    reasoning = base("fulltext_reasoning_traces", traces, reasoning_usable)
    reasoning["status"] = _capability_status(present=bool(specs.get("fulltext_reasoning_traces")), count=len(traces), usable=reasoning_usable, partial_allowed=True)
    if reason and reasoning["status"] == "produced_but_unusable":
        reasoning["reason"] = reason
    context = base("fulltext_context_consolidations", contexts, context_usable)
    context.update({"nonempty_record_count": context_usable, "slot_coverage": slot_coverage})
    context["status"] = _capability_status(present=bool(specs.get("fulltext_context_consolidations")), count=len(contexts), usable=context_usable, partial_allowed=True)
    reentry_count = specs.get("reentry_audit", {}).get("record_count")
    return {
        "schema_version": CAPABILITY_SCHEMA_VERSION,
        "fulltext_l1": fulltext,
        "reasoning_trace": reasoning,
        "context_consolidation": context,
        "reentry": {"declared": True, "artifact_present": "reentry_manifest" in specs, "hash_valid": "reentry_manifest" in specs, "record_count": reentry_count, "status": "available" if "reentry_manifest" in specs else "artifact_missing"},
        "formal_conflict": {"declared": True, "count": conflict_count, "status": "available" if conflict_count else "available_no_records"},
    }


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


def _lineage_path(value: Any, runs_root: Path) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path.resolve() if path.is_absolute() else (runs_root / path).resolve()


def _legacy_domain(case_id: str) -> dict[str, Any]:
    profile = Path("configs/generated_cases") / case_id / "case_profile.json"
    tags: list[str] = []
    if profile.is_file():
        value = _json(profile)
        tags = [str(item) for item in value.get("domain_tags") or [] if item]
    return {
        "primary_domain_id": None, "primary_domain_label": None, "secondary_domains": [],
        "legacy_domain_tags": tags, "taxonomy_version": None, "classifier_version": None,
        "classification_method": None, "confidence": None, "status": "legacy_unknown",
        "source_artifact_sha256": sha256_file(profile) if profile.is_file() else None,
        "source": "case_profile_domain_tags" if tags else "missing_artifact",
    }


def _domain_classification(case_id: str, lineage: dict[str, Any], runs_root: Path) -> dict[str, Any]:
    base = _lineage_path(lineage.get("base_run"), runs_root)
    intake_path = base / "artifacts/intake.json" if base else None
    if not intake_path or not intake_path.is_file():
        return _legacy_domain(case_id)
    intake = _json(intake_path)
    semantic = intake.get("semantic_intake") if isinstance(intake.get("semantic_intake"), dict) else {}
    routing = semantic.get("domain_routing") if isinstance(semantic.get("domain_routing"), dict) else {}
    domain_id = routing.get("domain_id")
    if not domain_id:
        return _legacy_domain(case_id)
    profile_path = base / "artifacts/domain_profile.json"
    profile = _json(profile_path) if profile_path.is_file() else {}
    confidence = routing.get("confidence")
    alternatives = []
    for item in routing.get("alternative_domains") or []:
        if isinstance(item, dict) and item.get("domain_id"):
            alternatives.append({"domain_id": str(item["domain_id"]), "label": item.get("label") or str(item["domain_id"]).replace("_", " ").title(), "confidence": item.get("confidence")})
    status = "low_confidence" if routing.get("requires_manual_review") or (isinstance(confidence, (int, float)) and confidence < 0.7) else "classified"
    return {
        "primary_domain_id": str(domain_id),
        "primary_domain_label": profile.get("display_name") or str(domain_id).replace("_", " ").title(),
        "secondary_domains": alternatives,
        "legacy_domain_tags": [],
        "taxonomy_version": DOMAIN_TAXONOMY_VERSION,
        "classifier_version": "semantic_intake_domain_routing_v1",
        "classification_method": semantic.get("semantic_mode") or intake.get("semantic_mode") or "recorded_system_a_routing",
        "confidence": confidence,
        "status": status,
        "source_artifact_sha256": sha256_file(intake_path),
        "source": "system_a_semantic_intake_domain_routing",
    }


def _source_unit_rows(case_id: str, l1_run: Path, chunks_path: Path) -> list[dict[str, Any]]:
    artifact_hash = sha256_file(chunks_path)
    rows = []
    for index, chunk in enumerate(_jsonl_rows(chunks_path)):
        text = str(chunk.get("text") or "")
        chunk_hash = str(chunk.get("chunk_hash") or hashlib.sha256(text.encode("utf-8")).hexdigest())
        identity = canonical_json({"case_id": case_id, "paper_id": chunk.get("pmid") or chunk.get("pmcid"), "parent_chunk_id": chunk.get("chunk_id"), "chunk_hash": chunk_hash})
        rows.append({
            "schema_version": SOURCE_UNIT_SCHEMA_VERSION,
            "source_unit_id": "su_" + hashlib.sha256(identity).hexdigest()[:24],
            "case_id": case_id, "paper_id": chunk.get("pmid") or chunk.get("paper_id") or chunk.get("pmcid"),
            "pmid": chunk.get("pmid"), "pmcid": chunk.get("pmcid"), "doi": chunk.get("doi"),
            "source_scope": "fulltext", "section_type": chunk.get("section_type"), "section_title": chunk.get("section_title"),
            "parent_chunk_id": chunk.get("chunk_id"), "chunk_hash": chunk_hash, "unit_index": index,
            "char_start": 0, "char_end": len(text), "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "text": text, "eligible_for_extraction": True, "chunker_version": "existing_l1_selected_chunk_boundary_v1",
            "source_artifact_sha256": artifact_hash,
        })
    return rows


def _ensure_source_text_units(run: Path, runs_root: Path, lineage: dict[str, Any] | None) -> None:
    source = _json(run / "fulltext_reentry_manifest.json")
    case_id = str(source.get("case_id") or "")
    lineage = lineage or {}
    l1_value = lineage.get("fulltext_l1_run") or source.get("fulltext_run")
    l1_run = _lineage_path(l1_value, runs_root)
    if not l1_run:
        return
    chunks = l1_run / "artifacts/l35_fulltext_discovery_selected_chunks.jsonl"
    if not chunks.is_file():
        return
    rows = _source_unit_rows(case_id, l1_run, chunks)
    payload = b"".join(canonical_json(row) for row in rows)
    destination = run / OPTIONAL_ARTIFACTS["source_text_units"]
    if destination.is_file():
        if destination.read_bytes() != payload:
            raise HandoffError("immutable_source_units_mismatch", str(destination))
        return
    _atomic_write(destination, payload)


def build_handoff_manifest(
    run_dir: str | Path,
    *,
    runs_root: str | Path = "runs",
    lineage: dict[str, Any] | None = None,
    prediction_version: str = "fulltext_reentry_v5",
    pipeline_profile: str = "fulltext_reentry_high_recall_v5",
    adapter_hint: str = "fulltext_reentry_v5",
    schema_version: str = HANDOFF_SCHEMA_VERSION,
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

    if schema_version not in SUPPORTED_HANDOFF_SCHEMA_VERSIONS:
        raise HandoffError("unsupported_schema", schema_version)
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
                "schema_version": _artifact_schema_version(logical_name, path),
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
    chain_count = artifact_specs.get("experimental_evidence_chains", {}).get("record_count", 0)
    link_count = artifact_specs.get("claim_evidence_links", {}).get("record_count", 0)
    context_count = artifact_specs.get("fulltext_context_consolidations", {}).get("record_count", 0)

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
    domain = _domain_classification(case_id, effective_lineage, root)
    capabilities = _capability_summary(run, artifact_specs, conflict_count=conflict)
    source_units_spec = artifact_specs.get("source_text_units")
    manifest = {
        "schema_version": schema_version,
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
            "evidence_chain_count": chain_count,
            "claim_evidence_link_count": link_count,
            "context_enriched_claim_count": context_count,
        },
        "available_capabilities": [
            "fulltext_claims",
            *(
                ["reasoning_traces", "experimental_context", "dossier_reasoning_view"]
                if "fulltext_reasoning_traces" in artifact_specs else []
            ),
            *(
                ["experimental_evidence_chains", "claim_evidence_links", "claim_dossier_evidence_chains"]
                if "experimental_evidence_chains" in artifact_specs else []
            ),
        ],
        "system_a_git_commit": _git_commit(),
        "configuration_hash": hashlib.sha256(canonical_json(configuration_material)).hexdigest(),
        "generated_at": completed_at or datetime.now(timezone.utc).isoformat(),
        "completed_at": completed_at,
    }
    if schema_version == HANDOFF_SCHEMA_VERSION:
        manifest.update({
            "domain_classification": domain,
            "domain_classification_snapshot_hash": hashlib.sha256(canonical_json(domain)).hexdigest(),
            "capabilities": capabilities,
            "source_text_units": ({
                "artifact_type": "claim_evaluation_source_units",
                "relative_path": source_units_spec["relative_path"], "sha256": source_units_spec["sha256"],
                "schema_version": source_units_spec["schema_version"], "record_count": source_units_spec["record_count"],
                "scope": "selected_for_l1_extraction",
            } if source_units_spec else None),
            "identity_contract": {
                "schema_version": "atlas_stable_identity_v1",
                "claim_id": "run_scoped_extraction_record_id", "claim_identity_hash": "content_stable_claim_identity",
                "source_record_hash": "artifact_record_identity", "source_unit_id": "selected_source_text_unit_identity",
                "paper_identity_priority": ["pmid", "pmcid", "doi", "paper_id"],
            },
        })
    return manifest


def build_abstract_l2_handoff_manifest(
    run_dir: str | Path,
    *,
    runs_root: str | Path = "runs",
    schema_version: str = HANDOFF_SCHEMA_VERSION,
) -> dict[str, Any]:
    run = Path(run_dir).resolve()
    root = Path(runs_root).resolve()
    try:
        run_relative = run.relative_to(root).as_posix()
    except ValueError as error:
        raise HandoffError("run_outside_root", f"run {run} is outside allowed root {root}") from error
    if schema_version not in SUPPORTED_HANDOFF_SCHEMA_VERSIONS:
        raise HandoffError("unsupported_schema", schema_version)
    artifacts_dir = run / "artifacts"
    replay = _json(artifacts_dir / "replay_manifest.json")
    terminal = _json(artifacts_dir / "replay_terminal_state_audit.json") if (artifacts_dir / "replay_terminal_state_audit.json").is_file() else {}
    scientific_status = terminal.get("final_status") or replay.get("final_status") or replay.get("scientific_status") or "completed"
    if scientific_status != "completed":
        raise HandoffError("run_not_completed", str(scientific_status))
    profile = _json(artifacts_dir / "case_domain_profile.json")
    case_id = str(profile.get("case_id") or replay.get("case_id") or "")
    if not case_id:
        raise HandoffError("missing_case_id", "case profile has no case_id")
    specs: dict[str, dict[str, Any]] = {}
    for required, mapping in ((True, ABSTRACT_L2_REQUIRED_ARTIFACTS), (False, ABSTRACT_L2_OPTIONAL_ARTIFACTS)):
        for logical_name, relative in mapping.items():
            spec = _artifact_spec(run, logical_name, relative, required)
            if spec:
                specs[logical_name] = spec
    core_count = specs["l2_core_graph_observations"]["record_count"] or 0
    graph_count = (specs.get("l2_graph_observations") or {}).get("record_count") or 0
    conflict_summary = _json(artifacts_dir / "graph_conflict_summary.json")
    hypothesis_summary = _json(artifacts_dir / "hypothesis_summary.json")
    summary = {
        "formal_core_observation_count": core_count,
        "graph_observation_count": graph_count,
        "conflict_eligible_observation_count": sum(
            bool(row.get("conflict_eligible"))
            for row in _jsonl_rows(artifacts_dir / "l2_core_graph_observations.jsonl")
        ),
        "true_graph_conflict_count": int(conflict_summary.get("true_graph_conflict_count", 0) or 0),
        "formal_hypothesis_count": int(hypothesis_summary.get("formal_hypothesis_count", 0) or 0),
    }
    content_material = {
        "handoff_profile": ABSTRACT_L2_PROFILE,
        "case_id": case_id,
        "scientific_run_id": run.name,
        "schema_version": schema_version,
        "artifacts": {key: value["sha256"] for key, value in sorted(specs.items())},
        "scientific_summary": summary,
    }
    content_hash = hashlib.sha256(canonical_json(content_material)).hexdigest()
    projection_id = "projection_" + hashlib.sha256(canonical_json({
        "case_id": case_id,
        "scientific_run_id": run.name,
        "handoff_profile": ABSTRACT_L2_PROFILE,
        "content_hash": content_hash,
        "schema_version": schema_version,
    })).hexdigest()[:24]
    compatibility = {
        "evidence_scope": "abstract_only",
        "abstract_l1_reused": True,
        "fulltext_evidence_available": False,
        "fulltext_reentry_applied": False,
        "entity_network_lookup_used": bool(replay.get("entity_network_lookup_enabled")),
        "entity_llm_cleaner_calls": int(replay.get("entity_llm_cleaner_calls_made", 0) or 0),
        "formal_graph_generated": True,
    }
    domain = _legacy_domain(case_id)
    capabilities = {
        "schema_version": CAPABILITY_SCHEMA_VERSION,
        "abstract_l2": {"status": "available", "record_count": core_count, "usable_record_count": core_count, "coverage": 1.0 if core_count else 0.0},
        "fulltext_l1": {"status": "artifact_missing", "record_count": 0, "usable_record_count": 0, "coverage": 0.0},
        "reasoning_trace": {"status": "artifact_missing", "record_count": 0, "usable_record_count": 0, "coverage": 0.0},
        "context_consolidation": {"status": "artifact_missing", "record_count": 0, "usable_record_count": 0, "coverage": 0.0},
        "reentry": {"status": "not_applicable", "record_count": 0},
        "formal_conflict": {"declared": True, "count": summary["true_graph_conflict_count"], "status": "available" if summary["true_graph_conflict_count"] else "available_no_records"},
    }
    manifest = {
        "schema_version": schema_version,
        "handoff_profile": ABSTRACT_L2_PROFILE,
        "case_id": case_id,
        "scientific_run_id": run.name,
        "source_run_id": run.name,
        "source_run_relative_path": run_relative,
        "projection_id": projection_id,
        "bundle_id": f"{case_id}__{run.name}",
        "content_hash": content_hash,
        "run_status": "completed",
        "scientific_stage": "l2_plus_downstream",
        "prediction_version": "abstract_l2_projection_v1",
        "pipeline_profile": "abstract_l2_projection_v1",
        "adapter_hint": ABSTRACT_L2_PROFILE,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": terminal.get("completed_at") or replay.get("created_at"),
        "artifacts": dict(sorted(specs.items())),
        "artifact_manifest": dict(sorted(specs.items())),
        "counts": {
            "input_fulltext_claim_count": 0,
            "exploratory_graph_eligible_count": graph_count,
            "conflict_eligible_count": summary["conflict_eligible_observation_count"],
            **summary,
        },
        "scientific_summary": summary,
        "provenance": {
            "abstract_l1_reused": True,
            "source_run": replay.get("source_run") or replay.get("replay_source_run"),
            "current_run_calls": replay.get("current_run_calls") or {},
        },
        "compatibility": compatibility,
        "domain_classification": domain,
        "domain_classification_snapshot_hash": hashlib.sha256(canonical_json(domain)).hexdigest(),
        "capabilities": capabilities,
        "available_capabilities": ["abstract_l2_projection", "formal_core_graph"],
        "system_a_git_commit": _git_commit(),
        "configuration_hash": hashlib.sha256(canonical_json(content_material)).hexdigest(),
    }
    return manifest


def validate_handoff(manifest_path: str | Path, *, runs_root: str | Path = "runs", verify_hashes: bool = True) -> dict[str, Any]:
    path = Path(manifest_path).resolve()
    manifest = _json(path)
    if manifest.get("schema_version") not in SUPPORTED_HANDOFF_SCHEMA_VERSIONS:
        raise HandoffError("unsupported_schema", str(manifest.get("schema_version")))
    profile = manifest.get("handoff_profile") or FULLTEXT_REENTRY_PROFILE
    if profile not in SUPPORTED_HANDOFF_PROFILES:
        raise HandoffError("unsupported_handoff_profile", str(profile))
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
        schema = spec.get("schema_version")
        supported = SUPPORTED_ARTIFACT_SCHEMAS.get(logical_name)
        if schema and supported and schema not in supported:
            raise HandoffError("unsupported_artifact_schema", f"{logical_name}:{schema}")
    if profile == ABSTRACT_L2_PROFILE:
        for field in ("content_hash", "scientific_summary", "compatibility", "artifact_manifest"):
            if not manifest.get(field):
                raise HandoffError("missing_abstract_l2_field", field)
        if manifest.get("compatibility", {}).get("evidence_scope") != "abstract_only":
            raise HandoffError("invalid_abstract_l2_scope", str(manifest.get("compatibility", {}).get("evidence_scope")))
        for logical_name in ABSTRACT_L2_REQUIRED_ARTIFACTS:
            if logical_name not in artifacts:
                raise HandoffError("missing_required_artifact", logical_name)
    if manifest.get("schema_version") == HANDOFF_SCHEMA_VERSION:
        if not isinstance(manifest.get("capabilities"), dict):
            raise HandoffError("missing_capabilities", CAPABILITY_SCHEMA_VERSION)
        if not isinstance(manifest.get("domain_classification"), dict):
            raise HandoffError("missing_domain_classification", "domain_classification")
    transport_hash = sha256_file(path)
    if manifest.get("schema_version") == LEGACY_HANDOFF_SCHEMA_VERSION:
        identity_hash = transport_hash
    else:
        material = {
            "handoff_schema_version": manifest.get("schema_version"), "handoff_profile": profile, "case_id": manifest.get("case_id"),
            "artifact_hashes": {key: value.get("sha256") for key, value in sorted(artifacts.items())},
            "artifact_schemas": {key: value.get("schema_version") for key, value in sorted(artifacts.items())},
            "content_hash": manifest.get("content_hash"),
            "domain_classification_snapshot_hash": manifest.get("domain_classification_snapshot_hash"),
            "capability_summary_schema_version": (manifest.get("capabilities") or {}).get("schema_version"),
        }
        identity_hash = hashlib.sha256(canonical_json(material)).hexdigest()
    return {"manifest": manifest, "manifest_hash": transport_hash, "identity_hash": identity_hash, "run_dir": run, "warnings": warnings}


def publish_atlas_handoff(run_dir: str | Path, **kwargs: Any) -> dict[str, Any]:
    run = Path(run_dir).resolve()
    schema_version = kwargs.pop("schema_version", HANDOFF_SCHEMA_VERSION)
    handoff_profile = kwargs.pop("handoff_profile", kwargs.pop("profile", FULLTEXT_REENTRY_PROFILE))
    if schema_version == HANDOFF_SCHEMA_VERSION and handoff_profile == FULLTEXT_REENTRY_PROFILE:
        _ensure_source_text_units(run, Path(kwargs.get("runs_root", "runs")).resolve(), kwargs.get("lineage"))
    artifacts = run / "artifacts"
    manifest_path = artifacts / MANIFEST_NAME
    ready_path = artifacts / READY_NAME
    manifest = (
        build_abstract_l2_handoff_manifest(run, schema_version=schema_version, **kwargs)
        if handoff_profile == ABSTRACT_L2_PROFILE
        else build_handoff_manifest(run, schema_version=schema_version, **kwargs)
    )
    payload = canonical_json(manifest)
    digest = hashlib.sha256(payload).hexdigest()
    marker = canonical_json({"schema_version": schema_version, "manifest_sha256": digest})
    if manifest_path.is_file() and ready_path.is_file():
        if manifest_path.read_bytes() == payload and ready_path.read_bytes() == marker:
            return {"status": "no_op", "manifest_path": str(manifest_path), "manifest_hash": digest, "manifest": manifest}
    _atomic_write(manifest_path, payload)
    validated = validate_handoff(manifest_path, runs_root=kwargs.get("runs_root", "runs"))
    if validated["manifest_hash"] != digest:
        raise HandoffError("manifest_hash_mismatch", "post-write validation changed manifest hash")
    _atomic_write(ready_path, marker)
    return {"status": "published", "manifest_path": str(manifest_path), "manifest_hash": digest, "manifest": manifest}
