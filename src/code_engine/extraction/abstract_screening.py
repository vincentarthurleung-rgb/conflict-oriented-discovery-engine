"""Low-cost abstract L1 screening with cache and budget guards."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from code_engine.extraction.evidence_tiers import EvidenceTier, FullTextStatus, PaperProcessingRecord
from code_engine.extraction.l1_budget import build_l1_budget_report, enforce_l1_budget, estimate_l1_cost
from code_engine.extraction.polarity import normalize_directional_relation
from code_engine.domain.prompt_compiler import compile_l1_prompt
from code_engine.extraction.l1_response import (
    l1_failure_record, normalize_l1_json_response, resolve_l1_prompt_profile,
    write_l1_diagnostic,
)


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")


def _paper_id(paper: dict[str, Any], index: int) -> str:
    return str(paper.get("paper_id") or paper.get("pmcid") or paper.get("pmid") or f"paper_{index}")


def _fulltext_status(paper: dict[str, Any]) -> str:
    explicit = str(paper.get("full_text_status") or "")
    if explicit:
        return explicit
    if paper.get("full_text") or paper.get("sections") or paper.get("full_text_path"):
        return FullTextStatus.AVAILABLE.value
    return FullTextStatus.NOT_ATTEMPTED.value


def _cache_key(paper_id: str, abstract: str, profile: dict[str, Any]) -> str:
    payload = "|".join((paper_id, abstract, str(profile.get("prompt_profile_id", "abstract_l1_v1"))))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_claims(
    raw_claims: list[dict[str, Any]], paper: dict[str, Any], paper_id: str,
    cache_key: str, domain_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    claims = []
    for index, raw in enumerate(raw_claims):
        relation_raw = str(raw.get("relation_raw") or raw.get("relation") or "")
        normalized = normalize_directional_relation(
            relation_raw,
            raw.get("subject_type"),
            raw.get("object_type"),
            str(raw.get("evidence_sentence") or ""),
            domain_profile.get("domain_id"),
        )
        claim_id = str(raw.get("claim_id") or hashlib.sha256(f"{paper_id}|{cache_key}|{index}".encode()).hexdigest()[:16])
        claims.append({
            "claim_id": claim_id,
            "paper_id": paper_id,
            "pmid": paper.get("pmid"),
            "source_scope": "abstract",
            "evidence_tier": EvidenceTier.ABSTRACT_SCREENING.value,
            "full_text_status": _fulltext_status(paper),
            "subject_raw": str(raw.get("subject_raw") or raw.get("subject") or ""),
            "subject_type": str(raw.get("subject_type") or "unknown"),
            "relation_raw": relation_raw,
            "object_raw": str(raw.get("object_raw") or raw.get("object") or ""),
            "object_type": str(raw.get("object_type") or "unknown"),
            "relation_family": str(raw.get("relation_family") or normalized.relation_family),
            "polarity_type": str(raw.get("polarity_type") or normalized.polarity_type),
            "direction": str(raw.get("direction") or normalized.direction),
            "direction_confidence": float(raw.get("direction_confidence", normalized.confidence)),
            "direct_relation_sign": raw.get("direct_relation_sign", 0),
            "therapeutic_direction": str(raw.get("therapeutic_direction") or "unknown"),
            "negated": bool(raw.get("negated", False)),
            "null_or_no_effect": bool(raw.get("null_or_no_effect", False)),
            "speculative": bool(raw.get("speculative", False)),
            "confidence": float(raw.get("confidence", 0.0)),
            "evidence_sentence": str(raw.get("evidence_sentence") or ""),
            "context_mentions": dict(raw.get("context_mentions") or raw.get("context") or {}),
            "context": dict(raw.get("context") or raw.get("context_mentions") or {}),
            "domain_id": domain_profile.get("domain_id"),
            "llm_extraction_ref": cache_key,
            "warnings": list(dict.fromkeys(list(raw.get("warnings") or []) + normalized.warnings + ["abstract_claim_not_fulltext_evidence"])),
        })
    return claims


def run_abstract_l1_screening(
    papers: list[dict],
    domain_profile: dict | None,
    run_dir: Path | None,
    execute: bool = False,
    api_enabled: bool = False,
    max_papers: int | None = None,
    max_l1_calls: int | None = None,
    budget_policy: dict | None = None,
    *,
    llm_client: Any | None = None,
    allow_budget_overrun: bool = False,
    pilot_profile: str | None = None,
) -> dict:
    """Plan or execute abstract-only extraction; never emits full-text evidence."""

    profile = dict(domain_profile or {})
    prompt_profile = resolve_l1_prompt_profile(profile, pilot_profile)
    selected = list(papers[:max_papers] if max_papers is not None else papers)
    abstracts = [str(item.get("abstract") or item.get("abstract_text") or "").strip() for item in selected]
    callable_inputs = [text for text in abstracts if text]
    if max_l1_calls is not None:
        callable_inputs = callable_inputs[:max_l1_calls]
    policy = dict(budget_policy or {})
    if max_l1_calls is not None:
        policy["max_l1_calls_per_prompt"] = max_l1_calls
    estimate = estimate_l1_cost(callable_inputs, model_pricing_profile=policy.get("model_pricing_profile", "deepseek_default"))
    decision = enforce_l1_budget(estimate, policy, execute=execute and api_enabled, allow_budget_overrun=allow_budget_overrun)
    output_dir = Path(run_dir) if run_dir is not None else None
    cache_path = output_dir / "abstract_l1_cache.json" if output_dir else None
    cache = {"entries": {}}
    if cache_path and cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache = {"entries": {}}

    claims: list[dict[str, Any]] = []
    records: list[PaperProcessingRecord] = []
    skipped: list[dict[str, str]] = []
    calls = 0
    cache_hits = 0
    recovery_warnings: list[str] = []
    prompt_calls: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    attempted_l1_papers = successful_l1_papers = 0
    processed_inputs = 0
    for index, paper in enumerate(selected):
        paper_id = _paper_id(paper, index)
        abstract = abstracts[index]
        record = PaperProcessingRecord(
            paper_id=paper_id, pmid=paper.get("pmid"), pmcid=paper.get("pmcid"),
            doi=paper.get("doi"), title=paper.get("title"), abstract_available=bool(abstract),
            full_text_status=_fulltext_status(paper), evidence_tier=EvidenceTier.ABSTRACT_SCREENING.value,
        )
        if not abstract:
            record.warnings.append("abstract_missing_skipped")
            skipped.append({"paper_id": paper_id, "reason": "abstract_missing"})
            records.append(record)
            continue
        if max_l1_calls is not None and processed_inputs >= max_l1_calls:
            record.warnings.append("max_l1_calls_reached")
            skipped.append({"paper_id": paper_id, "reason": "max_l1_calls_reached"})
            records.append(record)
            continue
        processed_inputs += 1
        key = _cache_key(paper_id, abstract, profile)
        cached = cache.get("entries", {}).get(key)
        if cached:
            paper_claims = list(cached.get("claims", []))
            cache_hits += 1
        elif execute and api_enabled and not decision["blocked"] and llm_client is not None:
            attempted_l1_papers += 1
            compiled = compile_l1_prompt(prompt_profile, abstract)
            metadata = {
                "prompt_profile_id": compiled.prompt_profile_id, "prompt_version": compiled.prompt_version,
                "compiled_prompt_hash": compiled.compiled_prompt_hash,
                "compiled_prompt_chars": compiled.compiled_prompt_char_count,
                "context_slots_used": list(prompt_profile.context_slots), "pilot_profile": pilot_profile,
                "domain_id": compiled.domain_id,
            }
            prompt_calls.append(metadata)
            try:
                response = llm_client.extract_json(compiled.text)
                calls += 1
                raw_response = response.pop("__l1_raw_response", response) if isinstance(response, dict) else response
                response, warnings = normalize_l1_json_response(response)
                successful_l1_papers += 1
                for warning in warnings:
                    recovery_warnings.append(warning)
                    write_l1_diagnostic(output_dir, stage="abstract_l1", paper_id=paper_id, pmid=paper.get("pmid"),
                                        prompt_metadata=metadata, raw_response=raw_response, error_type=warning,
                                        parsed_json_type="list" if "list" in warning else "dict", recoverable=True,
                                        recovery_action=warning)
            except Exception as exc:
                calls += 1
                failure = l1_failure_record(stage="abstract_l1", paper_id=paper_id, paper=paper,
                                            prompt_metadata=metadata, exc=exc)
                errors.append(failure)
                record.warnings.append(f"abstract_l1_{failure['error_type']}")
                write_l1_diagnostic(output_dir, stage="abstract_l1", paper_id=paper_id, pmid=paper.get("pmid"),
                                    prompt_metadata=metadata, raw_response=getattr(exc, "raw_response", ""),
                                    error_type=failure["error_type"],
                                    parsed_json_type=getattr(exc, "parsed_json_type", "unknown"), recoverable=False,
                                    recovery_action="paper_failed_workflow_continued")
                paper_claims = []
                records.append(record)
                continue
            paper_claims = _normalize_claims(list(response["claims"]), paper, paper_id, key, profile)
            for claim in paper_claims:
                claim.update(metadata)
            cache.setdefault("entries", {})[key] = {"claims": paper_claims}
        else:
            paper_claims = []
        claims.extend(paper_claims)
        record.abstract_claim_count = len(paper_claims)
        records.append(record)

    report = build_l1_budget_report(estimate, decision, actual_calls=calls)
    failed_l1_papers = len(errors)
    all_failed = attempted_l1_papers > 0 and successful_l1_papers == 0
    summary = {
        "execution_mode": "execute_api" if execute and api_enabled else "dry_run_plan",
        "paper_count": len(selected),
        "abstract_available_count": sum(item.abstract_available for item in records),
        "abstract_missing_count": sum(not item.abstract_available for item in records),
        "abstract_claim_count": len(claims),
        "planned_l1_call_count": estimate["estimated_calls"],
        "api_calls_made": calls,
        "cache_hit_count": cache_hits,
        "skipped": skipped,
        "budget_report": report,
        "warnings": (
            (["l1_budget_blocked"] if decision["blocked"] else [])
            + (["llm_client_not_configured"] if execute and api_enabled and llm_client is None else [])
            + list(dict.fromkeys(recovery_warnings))
        ),
        "prompt_profile_id": prompt_profile.profile_id,
        "prompt_profile_version": prompt_profile.version,
        "abstract_l1_prompt_uses_compiled_profile": True,
        "hardcoded_abstract_l1_prompt_used": False,
        "prompt_calls": prompt_calls,
        "attempted_l1_papers": attempted_l1_papers,
        "successful_l1_papers": successful_l1_papers,
        "failed_l1_papers": failed_l1_papers,
        "timeout_count": sum(item["error_type"] == "timeout" for item in errors),
        "api_error_count": sum(item["error_type"] == "api_error" for item in errors),
        "parse_error_count": sum(item["error_type"] == "json_parse_failed" for item in errors),
        "schema_error_count": sum(item["error_type"] == "schema_validation_failed" for item in errors),
        "workflow_continued_after_l1_errors": bool(errors),
        "blocked_reason": "all_l1_extractions_failed" if all_failed else None,
    }
    artifacts = {}
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        claim_path = output_dir / "abstract_l1_claims.jsonl"
        record_path = output_dir / "paper_processing_records.jsonl"
        summary_path = output_dir / "abstract_l1_summary.json"
        _write_jsonl(claim_path, claims)
        _write_jsonl(record_path, [item.model_dump(mode="json") for item in records])
        _write_jsonl(output_dir / "abstract_l1_errors.jsonl", errors)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        if execute and api_enabled and calls:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts = {"claims": str(claim_path), "summary": str(summary_path), "paper_records": str(record_path),
                     "errors": str(output_dir / "abstract_l1_errors.jsonl")}
    return {"claims": claims, "paper_records": [item.model_dump(mode="json") for item in records], "summary": summary, "artifacts": artifacts}


__all__ = ["run_abstract_l1_screening"]
