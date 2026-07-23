"""Explicit two-block Prompt v8 / Formal v3 provider smoke profile.

Planning is offline. Execution is available only to the separately gated CLI
and never mutates the scientific run, downstream stages, or Atlas state.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from code_engine.extraction.client_factory import build_json_client_from_config
from code_engine.extraction.deepseek_client import DeepSeekExtractionError, deepseek_thinking_mode_audit
from code_engine.fulltext.evidence_anchors import EVIDENCE_ANCHOR_VERSION
from code_engine.fulltext.experimental_semantics_registry import REGISTRY_VERSION
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import (
    COMPLETENESS_POLICY_VERSION, HYDRATOR_VERSION, TrustedDraftContextV3,
    audit_draft_anchor_bindings, hydrate_draft_response_v3,
)
from code_engine.fulltext.fulltext_l1_v2 import (
    DEFAULT_MAX_TOKENS, DEFAULT_THINKING_MODE, PROMPT_VERSION, SCHEMA_VERSION,
    build_prompt, estimate_tokens, formal_schema_hash, prompt_hash, schema_hash,
    split_transport_metadata,
)
from code_engine.fulltext.fulltext_l1_v2_smoke import (
    _block_inventory, _config_hash, _historical_config, _jsonl, _markdown_report,
    _sha, _write_json,
)
from code_engine.schemas.fulltext_observation import FulltextL1V3Response
from code_engine.schemas.fulltext_observation_draft import DRAFT_SCHEMA_VERSION, FulltextL1DraftResponse


SMOKE_PROFILE = "fulltext_l1_v3_anchor_authoritative_provider_smoke_v2"
MANIFEST_SCHEMA_VERSION = "fulltext_l1_v3_anchor_authoritative_provider_smoke_manifest_v2"
PREFLIGHT_SCHEMA_VERSION = "fulltext_l1_v3_anchor_authoritative_provider_smoke_preflight_v2"
RESULTS_SCHEMA_VERSION = "fulltext_l1_v3_anchor_authoritative_provider_smoke_results_v2"
MAXIMUM_CALLS = 2
PROVIDER = "deepseek"
MODEL = "deepseek-v4-pro"
PLAN_ARTIFACT = "fulltext_l1_v3_anchor_authoritative_provider_smoke_plan.json"
MANIFEST_ARTIFACT = "fulltext_l1_v3_anchor_authoritative_provider_smoke_manifest.json"
PREFLIGHT_ARTIFACT = "fulltext_l1_v3_anchor_authoritative_provider_smoke_preflight.json"
RESULTS_ARTIFACT = "fulltext_l1_v3_anchor_authoritative_provider_smoke_results.json"
RESULTS_MARKDOWN_ARTIFACT = "fulltext_l1_v3_anchor_authoritative_provider_smoke_results.md"
CACHE_DIR = "cache/fulltext_l1_v3_anchor_authoritative_provider_smoke"

FROZEN_SELECTION: tuple[tuple[str, str], ...] = (
    ("PMC7689016_32_0", "single_intervention_resolved_nonempty"),
    ("PMC7744182_1_0", "multi_intervention"),
)

PROTECTED_STATE_PATHS = (
    "artifacts/fulltext_l1_v2_summary.json",
    "artifacts/l35_fulltext_l1_summary.json",
    "artifacts/pipeline_stage_summary.json",
    "artifacts/l35_fulltext_conflict_confirmation_summary.json",
    "artifacts/fulltext_bridge_replay_manifest.json",
    "fulltext_bridge_replay_manifest.json",
)


def _hash(value: Any) -> str:
    data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _protected_hashes(run_dir: Path) -> dict[str, str]:
    return {name: _sha((run_dir / name).read_bytes()) for name in PROTECTED_STATE_PATHS if (run_dir / name).is_file()}


def _load_plan(artifacts: Path) -> tuple[dict[str, Any], str]:
    path = artifacts / PLAN_ARTIFACT
    if not path.is_file():
        raise FileNotFoundError(f"required frozen v3 smoke plan is missing: {path}")
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan.get("schema_version") != "fulltext_l1_v3_anchor_authoritative_provider_smoke_plan_v2":
        raise RuntimeError("invalid v3 smoke plan schema version")
    entries = list(plan.get("entries") or [])
    actual = [(str(x.get("block_id")), str(x.get("validation_role"))) for x in entries]
    if len({block_id for block_id, _ in actual}) != len(actual):
        raise RuntimeError("v3 smoke plan contains duplicate blocks")
    if actual != list(FROZEN_SELECTION):
        raise RuntimeError(f"v3 smoke plan does not match frozen five-block selection: {actual}")
    if plan.get("maximum_provider_calls") != MAXIMUM_CALLS or plan.get("planned_provider_calls") != MAXIMUM_CALLS:
        raise RuntimeError("v3 smoke plan call bound must be exactly five")
    return plan, _sha(path.read_bytes())


def _resolve_inventory(run_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    artifacts = run_dir / "artifacts"
    records = _jsonl(artifacts / "fulltext_l1_v2_execution_records.jsonl")
    if not records:
        raise FileNotFoundError("run-local Fulltext L1 execution records are required")
    config = _historical_config(artifacts, records)
    inventory = _block_inventory(run_dir, records, config)
    missing = [block_id for block_id, _ in FROZEN_SELECTION if block_id not in inventory]
    if missing:
        raise RuntimeError(f"frozen v3 smoke blocks cannot be resolved from run-local sources: {missing}")
    return inventory, config


def v3_smoke_cache_key(*, source_hash: str, block_hash: str, rendered_prompt_hash: str,
                       config_hash: str) -> str:
    return _hash({
        "cache_identity_version": "fulltext_l1_v3_provider_smoke_cache_v1",
        "smoke_profile": SMOKE_PROFILE, "provider": PROVIDER, "model": MODEL,
        "prompt_version": PROMPT_VERSION, "prompt_hash": prompt_hash(),
        "rendered_prompt_hash": rendered_prompt_hash,
        "draft_schema_version": DRAFT_SCHEMA_VERSION, "draft_schema_hash": schema_hash(),
        "formal_schema_version": SCHEMA_VERSION, "formal_schema_hash": formal_schema_hash(),
        "hydrator_version": HYDRATOR_VERSION, "semantics_registry_version": REGISTRY_VERSION,
        "evidence_anchor_version": EVIDENCE_ANCHOR_VERSION,
        "completeness_policy_version": COMPLETENESS_POLICY_VERSION,
        "thinking_mode": DEFAULT_THINKING_MODE, "max_tokens": DEFAULT_MAX_TOKENS,
        "source_hash": source_hash, "block_hash": block_hash, "config_hash": config_hash,
    })


def _fresh_cache_status(cache_root: Path, key: str, *, block_id: str, source_hash: str,
                        block_hash: str, rendered_prompt_hash: str) -> tuple[bool, str | None, dict[str, Any] | None]:
    path = cache_root / f"{key}.json"
    if not path.is_file():
        return False, None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        FulltextL1DraftResponse.model_validate(payload.get("draft_response"))
        FulltextL1V3Response.model_validate(payload.get("formal_response"))
    except (OSError, json.JSONDecodeError, ValidationError):
        return False, str(path), None
    valid = (
        payload.get("cache_identity") == key
        and payload.get("smoke_profile") == SMOKE_PROFILE
        and payload.get("origin") == "native_prompt_v8_results_anchor_contract_formal_v3_provider_smoke"
        and payload.get("provider") == PROVIDER and payload.get("model") == MODEL
        and payload.get("prompt_version") == PROMPT_VERSION and payload.get("prompt_hash") == prompt_hash()
        and payload.get("rendered_prompt_hash") == rendered_prompt_hash
        and payload.get("draft_schema_version") == DRAFT_SCHEMA_VERSION and payload.get("draft_schema_hash") == schema_hash()
        and payload.get("formal_schema_version") == SCHEMA_VERSION and payload.get("formal_schema_hash") == formal_schema_hash()
        and payload.get("hydrator_version") == HYDRATOR_VERSION
        and payload.get("semantics_registry_version") == REGISTRY_VERSION
        and payload.get("evidence_anchor_version") == EVIDENCE_ANCHOR_VERSION
        and payload.get("completeness_policy_version") == COMPLETENESS_POLICY_VERSION
        and payload.get("thinking_mode") == DEFAULT_THINKING_MODE
        and payload.get("max_tokens") == DEFAULT_MAX_TOKENS
        and payload.get("source_hash") == source_hash and payload.get("block_hash") == block_hash
        and payload.get("block_id") == block_id
    )
    return valid, str(path), payload if valid else None


def build_v3_manifest(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir); artifacts = run_dir / "artifacts"
    _plan, plan_hash = _load_plan(artifacts)
    inventory, config = _resolve_inventory(run_dir)
    missing = [block_id for block_id, _ in FROZEN_SELECTION if block_id not in inventory]
    if missing:
        raise RuntimeError(f"frozen v3 smoke blocks cannot be resolved from run-local sources: {missing}")
    config_hash = _config_hash(config)
    cache_root = artifacts / CACHE_DIR
    entries: list[dict[str, Any]] = []
    for block_id, role in FROZEN_SELECTION:
        item = inventory[block_id]; block = item["block"]; paper = item["paper"]
        block_hash = str(block.get("chunk_hash") or _sha(str(block["text"])))
        source_hash = str(item["source_fulltext_hash"])
        rendered_prompt = build_prompt(paper, block)
        rendered_prompt_hash = _sha(rendered_prompt)
        key = v3_smoke_cache_key(source_hash=source_hash, block_hash=block_hash,
                                 rendered_prompt_hash=rendered_prompt_hash, config_hash=config_hash)
        hit, cache_path, _payload = _fresh_cache_status(
            cache_root, key, block_id=block_id, source_hash=source_hash,
            block_hash=block_hash, rendered_prompt_hash=rendered_prompt_hash,
        )
        entries.append({
            "block_id": block_id, "selection_role": role, "selection_reason": role,
            "plan_hash": plan_hash, "block_hash": block_hash, "source_hash": source_hash,
            "paper_id": paper.get("paper_id"), "pmid": paper.get("pmid"), "pmcid": paper.get("pmcid"),
            "parent_block_id": block.get("parent_block_id") or block_id,
            "child_block_id": block.get("child_block_id"),
            "rendered_prompt_hash": rendered_prompt_hash,
            "estimated_input_tokens": estimate_tokens(rendered_prompt),
            "configured_max_tokens": DEFAULT_MAX_TOKENS,
            "cache_identity": key, "cache_hit": hit, "cache_status": "hit" if hit else "miss",
            "cache_path": cache_path, "provider_call_required": not hit,
        })
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION, "smoke_profile": SMOKE_PROFILE,
        "source_plan_artifact": PLAN_ARTIFACT, "source_plan_hash": plan_hash,
        "source_run": str(run_dir), "manifest_only": True, "selection_is_frozen": True,
        "planned_provider_calls": sum(bool(x["provider_call_required"]) for x in entries),
        "maximum_calls": MAXIMUM_CALLS, "maximum_provider_calls": MAXIMUM_CALLS,
        "sample_count": len(entries),
        "manifest_hash": _hash(entries), "entries": entries,
    }


def build_v3_preflight(manifest: dict[str, Any]) -> dict[str, Any]:
    thinking = deepseek_thinking_mode_audit(DEFAULT_THINKING_MODE)
    calls = sum(bool(x["provider_call_required"]) for x in manifest["entries"])
    entries = [{
        **{key: row[key] for key in (
            "block_id", "selection_role", "selection_reason", "plan_hash", "block_hash", "source_hash",
            "rendered_prompt_hash", "estimated_input_tokens", "configured_max_tokens", "cache_identity",
            "cache_hit", "cache_status", "cache_path", "provider_call_required",
        )},
        "prompt_version": PROMPT_VERSION, "prompt_hash": prompt_hash(),
        "draft_schema_version": DRAFT_SCHEMA_VERSION, "draft_schema_hash": schema_hash(),
        "formal_schema_version": SCHEMA_VERSION, "formal_schema_hash": formal_schema_hash(),
        "hydrator_version": HYDRATOR_VERSION, "semantics_registry_version": REGISTRY_VERSION,
        "evidence_anchor_version": EVIDENCE_ANCHOR_VERSION,
        "completeness_policy_version": COMPLETENESS_POLICY_VERSION,
        "response_format": {"type": "json_object"}, "thinking_mode": DEFAULT_THINKING_MODE,
    } for row in manifest["entries"]]
    return {
        "schema_version": PREFLIGHT_SCHEMA_VERSION, "mode": "plan_only", "smoke_profile": SMOKE_PROFILE,
        "api_calls": 0, "network_calls": 0, "downloads": 0,
        "planned_provider_calls": calls, "maximum_calls": MAXIMUM_CALLS,
        "manifest_only": True, "manifest_blocks": [x["block_id"] for x in manifest["entries"]],
        "manifest_hash": manifest["manifest_hash"], "plan_hash": manifest["source_plan_hash"],
        "prompt_version": PROMPT_VERSION, "prompt_hash": prompt_hash(),
        "draft_schema_version": DRAFT_SCHEMA_VERSION, "draft_schema_hash": schema_hash(),
        "formal_schema_version": SCHEMA_VERSION, "formal_schema_hash": formal_schema_hash(),
        "hydrator_version": HYDRATOR_VERSION, "semantics_registry_version": REGISTRY_VERSION,
        "evidence_anchor_version": EVIDENCE_ANCHOR_VERSION,
        "completeness_policy_version": COMPLETENESS_POLICY_VERSION,
        "thinking_mode": thinking["effective_mode"], "thinking_parameter_sent": thinking["thinking_parameter_sent"],
        "thinking_mode_verified": thinking["thinking_mode_verified"],
        "configured_max_tokens": DEFAULT_MAX_TOKENS,
        "cache_hits": sum(bool(x["cache_hit"]) for x in manifest["entries"]),
        "estimated_total_input_tokens": sum(x["estimated_input_tokens"] for x in manifest["entries"] if x["provider_call_required"]),
        "execution_blocked": not thinking["thinking_mode_verified"],
        "blocking_reason": None if thinking["thinking_mode_verified"] else "thinking_mode_unverified",
        "rerun_decision": "insufficient_evidence_do_not_rerun", "entries": entries,
    }


def write_v3_plan_artifacts(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir); artifacts = run_dir / "artifacts"
    before = _protected_hashes(run_dir)
    manifest = build_v3_manifest(run_dir)
    preflight = build_v3_preflight(manifest)
    _write_json(artifacts / MANIFEST_ARTIFACT, manifest)
    _write_json(artifacts / PREFLIGHT_ARTIFACT, preflight)
    after = _protected_hashes(run_dir)
    if before != after:
        raise RuntimeError("plan-only modified protected run-state artifacts")
    return {
        **{key: preflight[key] for key in (
            "mode", "smoke_profile", "api_calls", "network_calls", "downloads",
            "planned_provider_calls", "maximum_calls", "manifest_only", "manifest_blocks",
            "prompt_version", "prompt_hash", "draft_schema_version", "draft_schema_hash",
            "formal_schema_version", "formal_schema_hash", "hydrator_version",
            "semantics_registry_version", "evidence_anchor_version", "completeness_policy_version",
            "thinking_mode", "thinking_parameter_sent", "thinking_mode_verified", "execution_blocked",
            "rerun_decision", "cache_hits",
        )},
        "protected_state_hashes_unchanged": True,
        "scientific_input_complete": False, "partial_block_failures": True,
        "publication_allowed": False, "provider_results_created": False,
    }


def _validate_native_anchors(draft: FulltextL1DraftResponse, *, block_id: str, source_document_id: str,
                             block_text: str, section: str | None) -> dict[str, Any]:
    context = TrustedDraftContextV3(
        run_id="anchor_validation", block_id=block_id, parent_block_id=block_id,
        child_block_id=None, block_text=block_text, source_block_hash=_sha(block_text),
        source_document_id=source_document_id, paper_id=source_document_id,
        pmid=None, pmcid=None, fulltext_source_hash=_sha(block_text),
        source_artifact="anchor_validation", section=section,
    )
    return audit_draft_anchor_bindings(draft, context)


def _context(run_dir: Path, item: dict[str, Any]) -> TrustedDraftContextV3:
    block, paper = item["block"], item["paper"]
    section_value = block.get("section") or {}
    section = section_value.get("section_title") if isinstance(section_value, dict) else str(section_value or "") or None
    return TrustedDraftContextV3(
        run_id=run_dir.name, block_id=str(block["block_id"]),
        parent_block_id=block.get("parent_block_id") or block["block_id"],
        child_block_id=block.get("child_block_id"), block_text=str(block["text"]),
        source_block_hash=str(block.get("chunk_hash") or _sha(str(block["text"]))),
        source_document_id=str(paper.get("pmcid") or paper.get("pmid") or paper.get("paper_id")),
        paper_id=str(paper.get("paper_id") or paper.get("pmid") or paper.get("pmcid")),
        pmid=str(paper.get("pmid")) if paper.get("pmid") is not None else None,
        pmcid=str(paper.get("pmcid")) if paper.get("pmcid") is not None else None,
        fulltext_source_hash=str(item["source_fulltext_hash"]),
        source_artifact=str(item.get("article_path") or "article_text.json"), section=section,
    )


def _write_block_artifacts(cache_root: Path, key: str, *, raw: Any = None, draft: Any = None,
                           formal: Any = None, audit: Any = None) -> dict[str, str]:
    paths: dict[str, str] = {}
    if raw not in (None, ""):
        path = cache_root / f"{key}.raw_response.txt"; path.write_text(str(raw), encoding="utf-8"); paths["raw_response_path"] = str(path)
    for label, value in (("draft", draft), ("formal", formal), ("audit", audit)):
        if value is not None:
            path = cache_root / f"{key}.{label}.json"; _write_json(path, value); paths[f"{label}_path"] = str(path)
    return paths


def _reasoning_violation(transport: dict[str, Any]) -> tuple[bool, int | str]:
    usage = transport.get("usage") or {}
    value = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if value is None: value = usage.get("reasoning_tokens")
    tokens: int | str = int(value) if value is not None else "unavailable"
    return (isinstance(tokens, int) and tokens > 0) or bool(transport.get("reasoning_content_present")), tokens


def _block_metrics(formal_response: dict[str, Any], audit: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> dict[str, Any]:
    rows = list(formal_response.get("experimental_observations") or [])
    return {
        "formal_valid_observation_count": len(rows),
        "formal_resolved_count": sum(x.get("formal_status") == "resolved" for x in audit),
        "formal_reviewable_count": sum(x.get("formal_status") == "reviewable" for x in audit),
        "formal_rejected_count": len(rejected),
        "multi_intervention_count": sum(len(x.get("interventions") or []) > 1 for x in rows),
        "mixed_direction_count": sum((x.get("candidate_relation") or {}).get("lexical_direction") == "mixed" for x in rows),
        "unknown_category_count": sum(
            (x.get("experiment") or {}).get("design_type") == "unknown"
            or (x.get("measurement") or {}).get("measurement_dimension") == "unknown"
            or (x.get("candidate_relation") or {}).get("lexical_direction") == "unclear"
            or any(y.get("intervention_type") == "unknown" for y in x.get("interventions") or []) for x in rows
        ),
        "graph_eligible_count": sum(bool((x.get("eligibility") or {}).get("graph_eligible")) for x in rows),
        "strict_core_eligible_count": sum(bool((x.get("eligibility") or {}).get("strict_core_eligible")) for x in rows),
        "conflict_eligible_count": sum(bool((x.get("eligibility") or {}).get("conflict_eligible")) for x in rows),
        "hypothesis_eligible_count": sum(bool((x.get("eligibility") or {}).get("hypothesis_eligible")) for x in rows),
    }


def _aggregate_results(results: list[dict[str, Any]], *, calls: int, stopped_reason: str | None) -> dict[str, Any]:
    def total(key: str) -> int: return sum(int(x.get(key, 0) or 0) for x in results)
    draft_failures = Counter(str(x.get("draft_failure_reason")) for x in results if x.get("draft_failure_reason"))
    finish_reasons = Counter(str(x.get("finish_reason") or "unavailable") for x in results if x.get("api_called"))
    legacy = next((x for x in results if x.get("block_id") == "PMC7269543_4_0"), {})
    return {
        "schema_version": RESULTS_SCHEMA_VERSION, "mode": "executed", "smoke_profile": SMOKE_PROFILE,
        "origin": "native_prompt_v8_results_anchor_contract_formal_v3_provider_output",
        "api_calls": calls, "network_calls": calls, "downloads": 0, "maximum_calls": MAXIMUM_CALLS,
        "cache_hits": sum(x.get("cache_hit", False) for x in results),
        "provider_errors": sum(x.get("status") == "provider_error" for x in results),
        "finish_reason_counts": dict(sorted(finish_reasons.items())),
        "reasoning_token_violations": sum(x.get("reasoning_token_violation", False) for x in results),
        "output_truncation_count": sum(x.get("output_truncation", False) for x in results),
        "draft_valid_blocks": sum(x.get("draft_valid", False) for x in results),
        "draft_failed_blocks": sum(x.get("draft_valid") is False for x in results),
        "raw_observation_count": total("raw_observation_count"),
        "unknown_extra_paths": [p for x in results for p in x.get("unknown_extra_paths", [])],
        "draft_failure_reasons": dict(sorted(draft_failures.items())),
        **{key: total(key) for key in (
            "anchor_reference_count", "unique_anchor_id_count", "anchor_id_valid_reference_count",
            "anchor_id_missing_count", "anchor_id_cross_block_count",
            "anchor_registry_integrity_failure_count", "anchor_role_violation_count",
            "anchor_excerpt_match_count", "anchor_excerpt_mismatch_count",
            "anchor_excerpt_missing_count", "formal_evidence_binding_success_count",
            "formal_evidence_binding_failure_count",
        )},
        **{key: total(key) for key in (
            "formal_valid_observation_count", "formal_resolved_count", "formal_reviewable_count",
            "formal_rejected_count", "multi_intervention_count", "mixed_direction_count",
            "unknown_category_count", "graph_eligible_count", "strict_core_eligible_count",
            "conflict_eligible_count", "hypothesis_eligible_count",
        )},
        "formal_complete_blocks": sum(x.get("formal_block_status") == "complete" for x in results),
        "formal_incomplete_blocks": sum(x.get("formal_block_status") == "incomplete" for x in results),
        "formal_zero_hydrated_blocks": sum(x.get("raw_observation_count", 0) > 0 and x.get("formal_valid_observation_count", 0) == 0 for x in results),
        "legacy_empty": {
            "block_id": "PMC7269543_4_0", "raw_empty": legacy.get("raw_observation_count", 0) == 0,
            "raw_nonempty": legacy.get("raw_observation_count", 0) > 0,
            "draft_empty": legacy.get("draft_valid") is True and legacy.get("raw_observation_count", 0) == 0,
            "draft_nonempty": legacy.get("draft_valid") is True and legacy.get("raw_observation_count", 0) > 0,
            "formal_valid_nonempty": legacy.get("formal_valid_observation_count", 0) > 0,
            "false_negative_candidate_status": "candidate" if legacy.get("raw_observation_count", 0) > 0 else "not_observed",
        },
        "stopped_early": stopped_reason is not None, "stopped_reason": stopped_reason,
        "rerun_decision": "insufficient_evidence_do_not_rerun",
        "scientific_input_complete": False, "partial_block_failures": True,
        "publication_allowed": False, "reentry_executed": False, "l2_executed": False,
        "projection_executed": False, "atlas_publication_executed": False,
        "results": results,
    }


def execute_v3_smoke(run_dir: Path, *, api_authorized: bool, client: Any | None = None,
                     _thinking_audit: dict[str, Any] | None = None) -> dict[str, Any]:
    if not api_authorized:
        raise PermissionError("v3 smoke execution requires both --execute and --api")
    thinking = _thinking_audit or deepseek_thinking_mode_audit(DEFAULT_THINKING_MODE)
    if not thinking.get("thinking_mode_verified") or thinking.get("effective_mode") != "disabled":
        raise RuntimeError("thinking_mode_unverified")
    run_dir = Path(run_dir); artifacts = run_dir / "artifacts"; before = _protected_hashes(run_dir)
    saved_manifest_path = artifacts / MANIFEST_ARTIFACT
    if not saved_manifest_path.is_file():
        raise FileNotFoundError("run the v3 smoke CLI in plan-only mode before execution")
    saved = json.loads(saved_manifest_path.read_text(encoding="utf-8"))
    current = build_v3_manifest(run_dir)
    if saved.get("smoke_profile") != SMOKE_PROFILE or saved.get("manifest_hash") != current.get("manifest_hash"):
        raise RuntimeError("saved v3 smoke manifest is stale or incompatible; rerun plan-only")
    entries = list(current["entries"])
    if [x["block_id"] for x in entries] != [x[0] for x in FROZEN_SELECTION] or len(entries) != MAXIMUM_CALLS:
        raise RuntimeError("v3 smoke manifest violates frozen five-call bound")
    inventory, _config = _resolve_inventory(run_dir)
    cache_root = artifacts / CACHE_DIR; cache_root.mkdir(parents=True, exist_ok=True)
    client = client or build_json_client_from_config(PROVIDER, MODEL, max_retries=0)
    if client is None: raise RuntimeError("DeepSeek provider is not configured")
    results: list[dict[str, Any]] = []; calls = 0; stopped_reason: str | None = None; draft_failure_count = 0
    for entry in entries:
        block_id = entry["block_id"]; item = inventory[block_id]; key = entry["cache_identity"]
        hit, cache_path, cached = _fresh_cache_status(
            cache_root, key, block_id=block_id, source_hash=entry["source_hash"],
            block_hash=entry["block_hash"], rendered_prompt_hash=entry["rendered_prompt_hash"],
        )
        if hit and cached:
            results.append({**cached["block_result"], "status": "native_v6_cache_hit", "api_called": False,
                            "cache_hit": True, "cache_path": cache_path}); continue
        if calls >= MAXIMUM_CALLS: raise RuntimeError("v3 smoke provider call bound exceeded")
        raw: Any = None; transport: dict[str, Any] = {}; base = {
            "block_id": block_id, "selection_role": entry["selection_role"], "api_called": True,
            "cache_hit": False, "cache_identity": key, "prompt_version": PROMPT_VERSION,
            "draft_schema_version": DRAFT_SCHEMA_VERSION, "formal_schema_version": SCHEMA_VERSION,
            "hydrator_version": HYDRATOR_VERSION, "evidence_anchor_version": EVIDENCE_ANCHOR_VERSION,
            "configured_max_tokens": DEFAULT_MAX_TOKENS, "thinking_mode": DEFAULT_THINKING_MODE,
        }
        try:
            method = getattr(client, "extract_json_result", None) or getattr(client, "extract_json")
            calls += 1
            response = method(build_prompt(item["paper"], item["block"]), model=MODEL, temperature=0, top_p=1,
                              max_tokens=DEFAULT_MAX_TOKENS, retry_on_length=False,
                              thinking_mode=DEFAULT_THINKING_MODE)
            payload, transport = split_transport_metadata(response); raw = transport.get("raw_response")
            violation, reasoning_tokens = _reasoning_violation(transport)
            if violation:
                result = {**base, "status": "thinking_disabled_not_honored", "draft_valid": False,
                          "reasoning_token_violation": True, "reasoning_tokens": reasoning_tokens,
                          "finish_reason": transport.get("finish_reason"), "formal_block_status": "incomplete"}
                result.update(_write_block_artifacts(
                    cache_root, key, raw=raw, draft={"status": "not_validated", "payload": payload},
                    formal={"status": "not_produced", "reason": "thinking_disabled_not_honored"}, audit=result,
                )); results.append(result)
                stopped_reason = "thinking_disabled_not_honored"; break
            if transport.get("finish_reason") == "length":
                result = {**base, "status": "output_truncated", "draft_valid": False, "output_truncation": True,
                          "reasoning_tokens": reasoning_tokens, "finish_reason": "length", "formal_block_status": "incomplete"}
                result.update(_write_block_artifacts(
                    cache_root, key, raw=raw, draft={"status": "not_validated", "payload": payload},
                    formal={"status": "not_produced", "reason": "finish_reason_length"}, audit=result,
                )); results.append(result)
                stopped_reason = "finish_reason_length_no_retry"; break
            raw_rows = payload.get("experimental_observations") if isinstance(payload, dict) else None
            raw_count = len(raw_rows) if isinstance(raw_rows, list) else 0
            try:
                draft = FulltextL1DraftResponse.model_validate(payload)
            except ValidationError as exc:
                extras = [".".join(map(str, x["loc"])) for x in exc.errors() if x.get("type") == "extra_forbidden"]
                result = {**base, "status": "draft_schema_failure", "draft_valid": False,
                          "raw_observation_count": raw_count, "unknown_extra_paths": extras,
                          "draft_failure_reason": exc.errors()[0]["type"] if exc.errors() else "validation_error",
                          "finish_reason": transport.get("finish_reason"), "formal_rejected_count": raw_count,
                          "formal_block_status": "incomplete"}
                result.update(_write_block_artifacts(
                    cache_root, key, raw=raw, draft={"status": "invalid", "payload": payload},
                    formal={"status": "not_produced", "reason": "draft_schema_failure"}, audit=result,
                )); results.append(result)
                draft_failure_count += 1
                if draft_failure_count >= 2: stopped_reason = "systemic_draft_schema_drift"; break
                continue
            context = _context(run_dir, item)
            anchor_audit = _validate_native_anchors(
                draft, block_id=block_id, source_document_id=context.source_document_id,
                block_text=context.block_text, section=context.section,
            )
            if not anchor_audit["valid"]:
                result = {**base, **anchor_audit, "status": "evidence_anchor_failure", "draft_valid": True,
                          "raw_observation_count": raw_count, "formal_rejected_count": raw_count,
                          "finish_reason": transport.get("finish_reason"), "formal_block_status": "incomplete"}
                result.update(_write_block_artifacts(
                    cache_root, key, raw=raw, draft=draft.model_dump(mode="json"),
                    formal={"status": "not_produced", "reason": "evidence_anchor_failure"}, audit=result,
                )); results.append(result)
                continue
            hydrated = hydrate_draft_response_v3(draft, context)
            formal_response = FulltextL1V3Response.model_validate(hydrated.formal_response).model_dump(mode="json")
            metrics = _block_metrics(formal_response, hydrated.audit, hydrated.rejected)
            status = "formal_complete" if not hydrated.rejected else "formal_partial" if metrics["formal_valid_observation_count"] else "formal_zero"
            result = {**base, **anchor_audit, **metrics, "status": status, "draft_valid": True,
                      "raw_observation_count": raw_count, "finish_reason": transport.get("finish_reason"),
                      "usage": transport.get("usage") or {}, "reasoning_tokens": reasoning_tokens,
                      "formal_block_status": "complete" if not hydrated.rejected else "incomplete"}
            paths = _write_block_artifacts(cache_root, key, raw=raw, draft=draft.model_dump(mode="json"),
                                           formal=formal_response, audit={"hydration_audit": hydrated.audit, "rejected": hydrated.rejected})
            result.update(paths)
            cache_payload = {
                "cache_identity": key, "smoke_profile": SMOKE_PROFILE,
                "origin": "native_prompt_v8_results_anchor_contract_formal_v3_provider_smoke", "provider": PROVIDER, "model": MODEL,
                "prompt_version": PROMPT_VERSION, "prompt_hash": prompt_hash(),
                "rendered_prompt_hash": entry["rendered_prompt_hash"],
                "draft_schema_version": DRAFT_SCHEMA_VERSION, "draft_schema_hash": schema_hash(),
                "formal_schema_version": SCHEMA_VERSION, "formal_schema_hash": formal_schema_hash(),
                "hydrator_version": HYDRATOR_VERSION, "semantics_registry_version": REGISTRY_VERSION,
                "evidence_anchor_version": EVIDENCE_ANCHOR_VERSION,
                "completeness_policy_version": COMPLETENESS_POLICY_VERSION,
                "thinking_mode": DEFAULT_THINKING_MODE, "max_tokens": DEFAULT_MAX_TOKENS,
                "source_hash": entry["source_hash"], "block_hash": entry["block_hash"], "block_id": block_id,
                "draft_response": draft.model_dump(mode="json"), "formal_response": formal_response,
                "hydration_audit": hydrated.audit, "rejected": hydrated.rejected, "block_result": result,
            }
            _write_json(cache_root / f"{key}.json", cache_payload); results.append(result)
        except DeepSeekExtractionError as exc:
            error_transport = {"usage": exc.usage, **exc.provider_metadata}
            violation, reasoning_tokens = _reasoning_violation(error_transport)
            status = ("thinking_disabled_not_honored" if violation else "output_truncated" if exc.finish_reason == "length"
                      else "malformed_json" if exc.error_kind == "malformed_json" else "provider_error")
            calls_record = {**base, "status": status, "draft_valid": False,
                            "provider_error_kind": exc.error_kind, "finish_reason": exc.finish_reason,
                            "reasoning_token_violation": violation, "reasoning_tokens": reasoning_tokens,
                            "draft_failure_reason": "malformed_json" if status == "malformed_json" else None,
                            "output_truncation": exc.finish_reason == "length", "formal_block_status": "incomplete"}
            calls_record.update(_write_block_artifacts(
                cache_root, key, raw=exc.raw_response,
                draft={"status": "not_validated", "reason": status},
                formal={"status": "not_produced", "reason": status}, audit=calls_record,
            )); results.append(calls_record)
            stopped_reason = ("thinking_disabled_not_honored" if violation else "finish_reason_length_no_retry"
                              if exc.finish_reason == "length" else "malformed_json" if status == "malformed_json"
                              else "provider_fatal_error")
            break
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            result = {**base, "status": "malformed_json", "draft_valid": False,
                      "draft_failure_reason": type(exc).__name__, "error": str(exc),
                      "formal_block_status": "incomplete"}
            result.update(_write_block_artifacts(
                cache_root, key, raw=raw, draft={"status": "not_validated", "reason": type(exc).__name__},
                formal={"status": "not_produced", "reason": "malformed_json"}, audit=result,
            )); results.append(result)
            stopped_reason = "malformed_json"; break
    output = _aggregate_results(results, calls=calls, stopped_reason=stopped_reason)
    after = _protected_hashes(run_dir)
    if before != after: raise RuntimeError("v3 provider smoke modified protected run-state artifacts")
    output["protected_state_hashes_unchanged"] = True
    _write_json(artifacts / RESULTS_ARTIFACT, output)
    (artifacts / RESULTS_MARKDOWN_ARTIFACT).write_text(_markdown_report("Fulltext L1 v3 provider smoke results", (
        ("smoke_profile", SMOKE_PROFILE), ("api_calls", calls), ("maximum_calls", MAXIMUM_CALLS),
        ("draft_valid_blocks", output["draft_valid_blocks"]),
        ("formal_valid_observation_count", output["formal_valid_observation_count"]),
        ("formal_complete_blocks", output["formal_complete_blocks"]),
        ("formal_incomplete_blocks", output["formal_incomplete_blocks"]),
        ("rerun_decision", output["rerun_decision"]), ("publication_allowed", False),
    )), encoding="utf-8")
    return output


__all__ = [
    "SMOKE_PROFILE", "MAXIMUM_CALLS", "FROZEN_SELECTION", "build_v3_manifest", "build_v3_preflight",
    "v3_smoke_cache_key", "write_v3_plan_artifacts", "execute_v3_smoke",
]
