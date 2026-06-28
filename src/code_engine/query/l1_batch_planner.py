"""Prompt-aware, budget-aware dry-run planning for incremental L1 batches."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from code_engine.acquisition.manifest import match_candidate_papers_to_inventory
from code_engine.common.json_io import write_json
from code_engine.query.intent import ResearchIntent
from code_engine.query.prompt_compatibility import (
    ChunkProcessingRecord,
    PromptProfileFingerprint,
    compare_prompt_compatibility,
)
from code_engine.query.search_planner import LiteratureSearchPlan
from code_engine.schemas.models import CODEBaseModel


class L1BatchProcessingPlan(CODEBaseModel):
    intent_id: str
    required_prompt_fingerprint: dict[str, Any]
    papers_reused: list[dict[str, Any]] = Field(default_factory=list)
    papers_need_download: list[dict[str, Any]] = Field(default_factory=list)
    papers_need_payload_build: list[dict[str, Any]] = Field(default_factory=list)
    chunks_reused: list[dict[str, Any]] = Field(default_factory=list)
    chunks_need_l1: list[dict[str, Any]] = Field(default_factory=list)
    chunks_need_l1_5: list[dict[str, Any]] = Field(default_factory=list)
    chunks_need_reextraction_due_to_prompt: list[dict[str, Any]] = Field(default_factory=list)
    chunks_need_reextraction_due_to_schema: list[dict[str, Any]] = Field(default_factory=list)
    chunks_need_reextraction_due_to_policy: list[dict[str, Any]] = Field(default_factory=list)
    chunks_need_reextraction_due_to_chunk_hash: list[dict[str, Any]] = Field(default_factory=list)
    estimated_api_calls: int = 0
    estimated_tokens: int = 0
    budget_limit: dict[str, int | None] = Field(default_factory=dict)
    budget_status: str = "within_budget"
    batch_files: list[list[str]] = Field(default_factory=list)
    recommended_action: str = "no_action_needed"
    api_calls_made: int = 0
    dry_run: bool = True
    warnings: list[str] = Field(default_factory=list)


def _chunk_descriptor(paper: dict[str, Any], chunk: dict[str, Any], reason: str = "") -> dict[str, Any]:
    return {
        "paper_id": paper.get("paper_id"),
        "chunk_id": chunk.get("chunk_id"),
        "chunk_hash": chunk.get("chunk_hash", ""),
        "reason": reason,
        "estimated_tokens": int(chunk.get("estimated_tokens") or chunk.get("token_count") or 1200),
    }


def _paper_chunks(paper: dict[str, Any]) -> list[dict[str, Any]]:
    chunks = list(paper.get("chunks") or [])
    if chunks:
        return chunks
    count = int(paper.get("chunk_count") or 0)
    return [{"chunk_id": f"chunk_{index}", "chunk_hash": ""} for index in range(count)]


REQUIRED_RECORD_FINGERPRINT_FIELDS = {
    "paper_id", "chunk_id", "chunk_hash", "domain_id", "prompt_profile_id",
    "prompt_version", "output_schema_version", "extraction_policy_version",
    "model_name", "model_family", "domain_profile_id", "compiled_prompt_hash",
}


def _has_fingerprint_metadata(record: dict[str, Any]) -> bool:
    nested = record.get("prompt_fingerprint")
    source = nested if isinstance(nested, dict) and nested else record
    return all(str(source.get(field) or "") for field in REQUIRED_RECORD_FINGERPRINT_FIELDS)


def plan_l1_batch_for_intent(
    intent: ResearchIntent,
    search_plan: LiteratureSearchPlan,
    inventory: dict[str, Any],
    required_prompt_fingerprint: PromptProfileFingerprint,
    dry_run: bool = True,
    budget: dict[str, int] | None = None,
    *,
    allow_model_family_reuse: bool = False,
    allow_legacy_l1_reuse: bool = False,
    output_root: str | Path = ".",
    write_outputs: bool = False,
) -> L1BatchProcessingPlan:
    """Classify local chunks for reuse or reprocessing without executing work."""

    match_report = match_candidate_papers_to_inventory(search_plan, inventory)
    papers_need_download = list(match_report.needs_download)
    papers_need_payload_build = []
    papers_reused = []
    reused, need_l1, need_l1_5 = [], [], []
    reextract_prompt, reextract_schema, reextract_policy, reextract_hash = [], [], [], []

    for candidate in match_report.candidate_papers:
        paper = candidate.get("matched_inventory_paper")
        if not paper or not paper.get("raw_available"):
            continue
        if not paper.get("stage1_payload_available"):
            papers_need_payload_build.append(paper)
            continue
        chunks = _paper_chunks(paper)
        paper_reusable = bool(chunks)
        for chunk in chunks:
            record_payload = chunk.get("l1_record") or chunk.get("processing_record")
            has_fingerprint = bool(record_payload) and _has_fingerprint_metadata(record_payload)
            if not record_payload or not has_fingerprint:
                descriptor = _chunk_descriptor(paper, chunk, "missing_prompt_fingerprint" if paper.get("l1_extracted") else "missing_l1_output")
                if paper.get("l1_extracted") and allow_legacy_l1_reuse:
                    descriptor["reason"] = "legacy_l1_reuse_explicitly_allowed"
                    descriptor["warnings"] = ["legacy_l1_missing_fingerprint"]
                    reused.append(descriptor)
                elif paper.get("l1_extracted"):
                    reextract_prompt.append(descriptor)
                else:
                    need_l1.append(descriptor)
                if not (paper.get("l1_extracted") and allow_legacy_l1_reuse):
                    paper_reusable = False
            else:
                nested = record_payload.get("prompt_fingerprint")
                normalized_record = (
                    {**nested, **record_payload}
                    if isinstance(nested, dict) and nested
                    else record_payload
                )
                record = ChunkProcessingRecord.model_validate(normalized_record)
                decision = compare_prompt_compatibility(
                    record,
                    required_prompt_fingerprint,
                    required_chunk_hash=str(chunk.get("chunk_hash") or record.chunk_hash),
                    allow_model_family_reuse=allow_model_family_reuse,
                )
                descriptor = _chunk_descriptor(paper, chunk, decision.reason)
                if decision.can_reuse:
                    reused.append(descriptor)
                elif decision.reason == "schema_version_changed":
                    reextract_schema.append(descriptor)
                    paper_reusable = False
                elif decision.reason == "chunk_hash_changed":
                    reextract_hash.append(descriptor)
                    paper_reusable = False
                elif decision.reason == "policy_version_changed":
                    reextract_policy.append(descriptor)
                    paper_reusable = False
                else:
                    reextract_prompt.append(descriptor)
                    paper_reusable = False
            if not chunk.get("l1_5_output") and not paper.get("l1_5_refined"):
                need_l1_5.append(_chunk_descriptor(paper, chunk, "missing_l1_5_output"))
        if paper_reusable:
            papers_reused.append(paper)

    l1_actions = need_l1 + reextract_prompt + reextract_schema + reextract_policy + reextract_hash
    unique_actions = {(item["paper_id"], item["chunk_id"]): item for item in l1_actions}
    estimated_calls = len(unique_actions)
    estimated_tokens = sum(item["estimated_tokens"] for item in unique_actions.values())
    limits = {
        "max_api_calls": (budget or {}).get("max_api_calls"),
        "max_tokens": (budget or {}).get("max_tokens"),
        "max_new_papers": (budget or {}).get("max_new_papers"),
    }
    over_budget = any(
        limit is not None and actual > limit
        for actual, limit in (
            (estimated_calls, limits["max_api_calls"]),
            (estimated_tokens, limits["max_tokens"]),
            (len(papers_need_download), limits["max_new_papers"]),
        )
    )
    action_ids = [f"{paper_id}:{chunk_id}" for paper_id, chunk_id in sorted(unique_actions)]
    batch_files = [action_ids[index:index + 50] for index in range(0, len(action_ids), 50)]
    if over_budget:
        recommended_action = "request_user_budget"
    elif papers_need_download or (not search_plan.candidate_papers and intent.needs_literature_search):
        recommended_action = "run_download_then_l1_batch"
    elif papers_need_payload_build or l1_actions:
        recommended_action = "run_l1_batch_only"
    elif reused:
        recommended_action = "reuse_existing_l1"
    else:
        recommended_action = "no_action_needed"
    warnings = list(match_report.warnings)
    if not dry_run:
        warnings.append("execution_not_implemented_forced_dry_run")
    plan = L1BatchProcessingPlan(
        intent_id=intent.intent_id,
        required_prompt_fingerprint=required_prompt_fingerprint.model_dump(),
        papers_reused=papers_reused,
        papers_need_download=papers_need_download,
        papers_need_payload_build=papers_need_payload_build,
        chunks_reused=reused,
        chunks_need_l1=need_l1,
        chunks_need_l1_5=need_l1_5,
        chunks_need_reextraction_due_to_prompt=reextract_prompt,
        chunks_need_reextraction_due_to_schema=reextract_schema,
        chunks_need_reextraction_due_to_policy=reextract_policy,
        chunks_need_reextraction_due_to_chunk_hash=reextract_hash,
        estimated_api_calls=estimated_calls,
        estimated_tokens=estimated_tokens,
        budget_limit=limits,
        budget_status="over_budget" if over_budget else "within_budget",
        batch_files=batch_files,
        recommended_action=recommended_action,
        api_calls_made=0,
        dry_run=True,
        warnings=warnings,
    )
    if write_outputs:
        root = Path(output_root)
        write_json(root / f"data/query/l1_batch_plan_{intent.intent_id}.json", plan.model_dump())
        markdown = root / f"reports/l1_batch_plan_{intent.intent_id}.md"
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(
            "# L1 Batch Processing Plan\n\n"
            f"- Reused chunks: {len(plan.chunks_reused)}\n"
            f"- L1/re-extraction calls estimated: {plan.estimated_api_calls}\n"
            f"- Actual API calls: {plan.api_calls_made}\n"
            f"- Recommended action: {plan.recommended_action}\n",
            encoding="utf-8",
        )
    return plan
