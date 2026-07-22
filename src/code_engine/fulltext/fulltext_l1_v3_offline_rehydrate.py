"""Zero-network rehydration of the frozen native Prompt-v6 provider smoke."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from code_engine.fulltext.evidence_anchors import EVIDENCE_ANCHOR_VERSION
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import (
    HYDRATOR_VERSION, audit_draft_anchor_bindings,
    hydrate_draft_response_v3,
)
from code_engine.fulltext.fulltext_l1_v2 import SCHEMA_VERSION, formal_schema_hash
from code_engine.fulltext.fulltext_l1_v3_smoke import (
    FROZEN_SELECTION as FRESH_V7_SELECTION, PLAN_ARTIFACT as FRESH_V7_PLAN_ARTIFACT,
    _block_metrics, _context, _protected_hashes, _resolve_inventory,
)
from code_engine.schemas.fulltext_observation import FulltextL1V3Response
from code_engine.schemas.fulltext_observation_draft import DRAFT_SCHEMA_VERSION, FulltextL1DraftResponse


ORIGIN = "offline_rehydrate_existing_native_prompt_v6_responses"
REHYDRATE_SCHEMA_VERSION = "fulltext_l1_v3_anchor_authoritative_rehydrate_summary_v1"
REHYDRATE_CONTRACT_VERSION = "fulltext_l1_v3_prompt_v6_compatibility_adapter_v1"
CACHE_IDENTITY_VERSION = "fulltext_l1_v3_anchor_authoritative_offline_cache_v1"
SUMMARY_ARTIFACT = "fulltext_l1_v3_anchor_authoritative_rehydrate_summary.json"
AUDIT_ARTIFACT = "fulltext_l1_v3_anchor_authoritative_rehydrate_audit.jsonl"
REPORT_ARTIFACT = "fulltext_l1_v3_anchor_authoritative_rehydrate.md"
CACHE_DIR = "cache/fulltext_l1_v3_anchor_authoritative_rehydrate"
LEGACY_PROMPT_VERSION = "fulltext_experimental_observation_prompt_v6_anchor_contract"
LEGACY_DRAFT_SCHEMA_VERSION = "fulltext_l1_experimental_observation_draft_schema_v2_anchor_ids"
LEGACY_RESULTS_ARTIFACT = "fulltext_l1_v3_provider_smoke_results.json"
LEGACY_FROZEN_SELECTION: tuple[tuple[str, str], ...] = (
    ("PMC7689016_32_0", "single_intervention_resolved_nonempty"),
    ("PMC7744182_1_0", "multi_intervention"),
    ("PMC7749157_1_0", "reviewable_raw_category"),
    ("PMC7269543_4_0", "legacy_empty_high_risk"),
    ("PMC7708218_12_0", "mixed_or_multi_endpoint"),
)


def _hash(value: Any) -> str:
    payload = (value if isinstance(value, bytes) else value.encode("utf-8") if isinstance(value, str)
               else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _convert_reference(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "evidence_anchor_ids": list(value.get("evidence_anchor_ids") or []),
        "span_type": value.get("span_type"),
        "model_selected_excerpt_raw": value.get("text"),
    }


def adapt_native_v6_draft(payload: dict[str, Any]) -> dict[str, Any]:
    """Explicit compatibility boundary; never used for native v7 validation."""
    converted = json.loads(json.dumps(payload))
    converted["schema_version"] = DRAFT_SCHEMA_VERSION
    for row in converted.get("experimental_observations") or []:
        row["evidence_references"] = [_convert_reference(x) for x in row.pop("evidence_texts")]
        row["observation"]["evidence"] = _convert_reference(row["observation"].pop("evidence_text"))
        measurement = row["measurement"]
        measurement["evidence"] = _convert_reference(measurement.pop("evidence_text", None))
        row["interpretation_evidence"] = _convert_reference(row.pop("interpretation_evidence_text", None))
        for intervention in row["interventions"]:
            intervention["evidence"] = _convert_reference(intervention.pop("evidence_text", None))
    return converted


def _source_paths(artifacts: Path, result: dict[str, Any]) -> tuple[Path, Path]:
    cache = artifacts / "cache/fulltext_l1_v3_provider_smoke"
    key = str(result["cache_identity"])
    return cache / f"{key}.raw_response.txt", cache / f"{key}.draft.json"


def _report(summary: dict[str, Any]) -> str:
    lines = ["# Fulltext L1 v3 authoritative-anchor offline rehydrate", ""]
    for key in (
        "origin", "scanned_blocks", "raw_observation_count", "formal_valid_observation_count",
        "formal_resolved_count", "formal_reviewable_count", "formal_rejected_count",
        "formal_complete_blocks", "formal_incomplete_blocks", "unique_anchor_id_count",
        "anchor_reference_count", "anchor_excerpt_match_count", "anchor_excerpt_mismatch_count",
        "anchor_excerpt_missing_count", "api_calls", "network_calls", "downloads",
        "scientific_input_complete", "partial_block_failures", "publication_allowed",
        "next_step",
    ):
        lines.append(f"- {key}: `{summary[key]}`")
    lines.extend(["", "## Per block", ""])
    for row in summary["blocks"]:
        lines.append(
            f"- `{row['block_id']}`: raw={row['raw_observation_count']}, "
            f"formal={row['formal_valid_observation_count']}, resolved={row['formal_resolved_count']}, "
            f"reviewable={row['formal_reviewable_count']}, rejected={row['formal_rejected_count']}, "
            f"excerpt_mismatch={row['anchor_excerpt_mismatch_count']}, status={row['formal_block_status']}"
        )
    return "\n".join(lines) + "\n"


def offline_rehydrate(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir); artifacts = run_dir / "artifacts"
    before = _protected_hashes(run_dir)
    provider_results_path = artifacts / LEGACY_RESULTS_ARTIFACT
    if not provider_results_path.is_file():
        raise FileNotFoundError(f"missing native v6 smoke results: {provider_results_path}")
    provider_results = json.loads(provider_results_path.read_text(encoding="utf-8"))
    if provider_results.get("origin") != "native_prompt_v6_formal_v3_provider_output":
        raise RuntimeError("source artifacts are not the frozen native Prompt-v6 smoke")
    by_block = {row["block_id"]: row for row in provider_results.get("results") or []}
    if list(by_block) != [block_id for block_id, _ in LEGACY_FROZEN_SELECTION]:
        raise RuntimeError("native v6 smoke block set/order is not the frozen five-block selection")
    inventory, _config = _resolve_inventory(run_dir)
    preflight_path = artifacts / "fulltext_l1_v3_provider_smoke_preflight.json"
    preflight = json.loads(preflight_path.read_text(encoding="utf-8")) if preflight_path.is_file() else {}
    existing_path = artifacts / SUMMARY_ARTIFACT
    raw_hashes = {}
    for block_id, _ in LEGACY_FROZEN_SELECTION:
        raw_path, _draft_path = _source_paths(artifacts, by_block[block_id])
        raw_hashes[block_id] = _hash(raw_path.read_bytes())
    input_identity = _hash({"provider_results": _hash(provider_results_path.read_bytes()), "raw_hashes": raw_hashes,
                            "contract": REHYDRATE_CONTRACT_VERSION, "hydrator": HYDRATOR_VERSION,
                            "draft_schema": DRAFT_SCHEMA_VERSION, "formal_schema": formal_schema_hash()})
    fresh_plan = {
        "schema_version": "fulltext_l1_v3_anchor_authoritative_provider_smoke_plan_v2",
        "mode": "plan_only", "origin": ORIGIN, "maximum_provider_calls": 2,
        "planned_provider_calls": 2, "provider_call_executed": False,
        "entries": [{"block_id": block_id, "validation_role": role,
                     "provider_call_planned": True, "provider_call_executed": False}
                    for block_id, role in FRESH_V7_SELECTION],
    }
    _write_json(artifacts / FRESH_V7_PLAN_ARTIFACT, fresh_plan)
    if existing_path.is_file():
        existing = json.loads(existing_path.read_text(encoding="utf-8"))
        if existing.get("input_identity") == input_identity:
            if before != _protected_hashes(run_dir):
                raise RuntimeError("offline rehydrate modified protected state")
            return existing

    cache_root = artifacts / CACHE_DIR; cache_root.mkdir(parents=True, exist_ok=True)
    audit_rows: list[dict[str, Any]] = []; blocks: list[dict[str, Any]] = []
    valid_raw_json_blocks = draft_valid_blocks = raw_observations = 0
    for block_id, selection_role in LEGACY_FROZEN_SELECTION:
        original = by_block[block_id]; raw_path, draft_path = _source_paths(artifacts, original)
        raw_bytes = raw_path.read_bytes(); draft_bytes = draft_path.read_bytes()
        try:
            raw_payload = json.loads(raw_bytes)
            valid_raw_json_blocks += 1
        except json.JSONDecodeError as exc:
            blocks.append({"block_id": block_id, "selection_role": selection_role,
                           "raw_observation_count": 0, "formal_valid_observation_count": 0,
                           "formal_resolved_count": 0, "formal_reviewable_count": 0,
                           "formal_rejected_count": 0, "formal_block_status": "incomplete",
                           "failure": f"raw_json_invalid:{exc}"})
            continue
        saved_draft = json.loads(draft_bytes)
        raw_count = len(raw_payload.get("experimental_observations") or [])
        raw_observations += raw_count
        converted = adapt_native_v6_draft(saved_draft)
        context = _context(run_dir, inventory[block_id])
        try:
            draft = FulltextL1DraftResponse.model_validate(converted)
            draft_valid_blocks += 1
        except ValidationError as exc:
            block = {"block_id": block_id, "selection_role": selection_role,
                     "raw_observation_count": raw_count, "formal_valid_observation_count": 0,
                     "formal_resolved_count": 0, "formal_reviewable_count": 0,
                     "formal_rejected_count": raw_count, "formal_block_status": "incomplete",
                     "failure": f"draft_schema_failure:{exc}"}
            blocks.append(block); audit_rows.append(block); continue
        anchor_audit = audit_draft_anchor_bindings(draft, context)
        hydrated = hydrate_draft_response_v3(draft, context)
        formal = FulltextL1V3Response.model_validate(hydrated.formal_response).model_dump(mode="json")
        metrics = _block_metrics(formal, hydrated.audit, hydrated.rejected)
        complete = not hydrated.rejected and metrics["formal_valid_observation_count"] == raw_count
        authoritative = all(
            span["text"] == context.block_text[span["char_start"]:span["char_end"]]
            and _hash(span["text"]) == span["text_hash"]
            and span["source_document_id"] == context.source_document_id
            and span["anchor_version"] == EVIDENCE_ANCHOR_VERSION
            for row in formal["experimental_observations"]
            for span in row["provenance"]["evidence_spans"]
        )
        cache_identity = _hash({"version": CACHE_IDENTITY_VERSION, "input_identity": input_identity,
                                "block_id": block_id, "raw_response_hash": raw_hashes[block_id]})
        formal_path = cache_root / f"{cache_identity}.formal.json"
        block_audit_path = cache_root / f"{cache_identity}.audit.json"
        provenance = {
            "origin": ORIGIN, "original_prompt_version": preflight.get("prompt_version", LEGACY_PROMPT_VERSION),
            "original_prompt_hash": preflight.get("prompt_hash"),
            "original_draft_schema_version": preflight.get("draft_schema_version", LEGACY_DRAFT_SCHEMA_VERSION),
            "original_draft_schema_hash": preflight.get("draft_schema_hash"),
            "original_raw_response_hash": raw_hashes[block_id],
            "original_draft_artifact_hash": _hash(draft_bytes),
            "original_cache_identity": original["cache_identity"],
            "rehydrate_contract_version": REHYDRATE_CONTRACT_VERSION,
            "authoritative_anchor_version": EVIDENCE_ANCHOR_VERSION,
            "hydrator_version": HYDRATOR_VERSION, "formal_schema_version": SCHEMA_VERSION,
            "formal_schema_hash": formal_schema_hash(), "rehydrated_at": datetime.now(timezone.utc).isoformat(),
        }
        block = {"block_id": block_id, "selection_role": selection_role,
                 "raw_observation_count": raw_count, **metrics, **anchor_audit,
                 "formal_block_status": "complete" if complete else "incomplete",
                 "all_formal_evidence_from_registry": authoritative,
                 "cache_identity": cache_identity, "formal_path": str(formal_path),
                 "audit_path": str(block_audit_path), "provenance": provenance}
        _write_json(formal_path, formal)
        _write_json(block_audit_path, {"block": block, "hydration_audit": hydrated.audit,
                                       "rejected": hydrated.rejected})
        blocks.append(block)
        audit_rows.append({"record_type": "block", **block})

    def total(key: str) -> int:
        return sum(int(row.get(key, 0) or 0) for row in blocks)

    four_nonempty_success = sum(
        row.get("raw_observation_count", 0) > 0 and row.get("formal_valid_observation_count") == row.get("raw_observation_count")
        for row in blocks
    )
    summary = {
        "schema_version": REHYDRATE_SCHEMA_VERSION, "origin": ORIGIN,
        "input_identity": input_identity, "scanned_blocks": len(blocks),
        "valid_raw_json_blocks": valid_raw_json_blocks, "draft_valid_blocks": draft_valid_blocks,
        "raw_observation_count": raw_observations,
        **{key: total(key) for key in (
            "formal_valid_observation_count", "formal_resolved_count", "formal_reviewable_count",
            "formal_rejected_count", "graph_eligible_count", "strict_core_eligible_count",
            "conflict_eligible_count", "hypothesis_eligible_count", "unique_anchor_id_count",
            "anchor_reference_count", "anchor_id_valid_reference_count", "anchor_id_missing_count",
            "anchor_id_cross_block_count", "anchor_role_violation_count",
            "anchor_registry_integrity_failure_count", "anchor_excerpt_match_count",
            "anchor_excerpt_mismatch_count", "anchor_excerpt_missing_count",
            "formal_evidence_binding_success_count", "formal_evidence_binding_failure_count",
        )},
        "formal_complete_blocks": sum(row.get("formal_block_status") == "complete" for row in blocks),
        "formal_incomplete_blocks": sum(row.get("formal_block_status") == "incomplete" for row in blocks),
        "formal_zero_hydrated_blocks": sum(row.get("raw_observation_count", 0) > 0 and not row.get("formal_valid_observation_count", 0) for row in blocks),
        "api_calls": 0, "network_calls": 0, "downloads": 0,
        "all_formal_evidence_from_registry": all(row.get("all_formal_evidence_from_registry", False) for row in blocks),
        "protected_state_hashes_unchanged": before == _protected_hashes(run_dir),
        "scientific_input_complete": False, "partial_block_failures": True,
        "publication_allowed": False, "reentry_executed": False, "l2_executed": False,
        "projection_executed": False, "atlas_publication_executed": False,
        "fresh_provider_smoke_executed": False,
        "provider_smoke_plan": {
            "required": True,
            "reason": "native Draft v3 renames evidence objects; offline compatibility cannot prove native conformance",
            "maximum_calls": 2, "planned_blocks": [block_id for block_id, _ in FRESH_V7_SELECTION],
            "executed": False,
        },
        "next_step": ("plan_at_most_two_block_native_v7_smoke" if four_nonempty_success >= 3
                      else "fix_remaining_offline_formal_failures_before_provider_planning"),
        "blocks": blocks,
    }
    if not summary["protected_state_hashes_unchanged"]:
        raise RuntimeError("offline rehydrate modified protected run-state artifacts")
    _write_json(existing_path, summary)
    (artifacts / AUDIT_ARTIFACT).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in audit_rows), encoding="utf-8"
    )
    (artifacts / REPORT_ARTIFACT).write_text(_report(summary), encoding="utf-8")
    if raw_hashes != {block_id: _hash(_source_paths(artifacts, by_block[block_id])[0].read_bytes())
                      for block_id, _ in LEGACY_FROZEN_SELECTION}:
        raise RuntimeError("offline rehydrate modified a native raw response")
    return summary


__all__ = ["ORIGIN", "SUMMARY_ARTIFACT", "AUDIT_ARTIFACT", "REPORT_ARTIFACT",
           "adapt_native_v6_draft", "offline_rehydrate"]
