"""Targeted full-text evidence extraction over selected spans only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from code_engine.extraction.evidence_tiers import EvidenceTier
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


def _cache_key(span: dict[str, Any], profile: dict[str, Any]) -> str:
    stable = "|".join((str(span.get("paper_id")), str(span.get("span_id")), str(span.get("text")), str(profile.get("prompt_profile_id", ""))))
    return hashlib.sha256(stable.encode()).hexdigest()


def _records_from_response(
    response: dict[str, Any], span: dict[str, Any], candidates: dict[str, dict[str, Any]],
    profile: dict[str, Any], cache_key: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence_records, claims = [], []
    linked_candidate_ids = list(span.get("conflict_candidate_ids") or [])
    linked_abstract_ids = list(dict.fromkeys(
        claim_id
        for candidate_id in linked_candidate_ids
        for claim_id in candidates.get(str(candidate_id), {}).get("claim_ids", [])
    ))
    for index, raw in enumerate(response.get("claims") or response.get("causal_tuples") or []):
        relation_raw = str(raw.get("relation_raw") or raw.get("relation") or "")
        sentence = str(raw.get("evidence_sentence") or span.get("text") or "")
        direction = normalize_directional_relation(
            relation_raw, raw.get("subject_type"), raw.get("object_type"), sentence,
            profile.get("domain_id"),
        )
        evidence_id = str(raw.get("evidence_id") or hashlib.sha256(f"{cache_key}|{index}".encode()).hexdigest()[:16])
        context = dict(raw.get("context_slots") or raw.get("context") or {})
        record = {
            "evidence_id": evidence_id,
            "paper_id": str(span.get("paper_id") or "UNKNOWN"),
            "pmid": raw.get("pmid"),
            "publication_year": span.get("publication_year") or raw.get("publication_year"),
            "source_scope": "full_text",
            "evidence_tier": EvidenceTier.FULLTEXT_EVIDENCE.value,
            "evidence_sentence": sentence,
            "evidence_span_id": str(span.get("span_id") or ""),
            "section_id": str(span.get("section_id") or ""),
            "section_type": str(span.get("section_type") or "unknown"),
            "subject_raw": str(raw.get("subject_raw") or raw.get("subject") or ""),
            "subject_type": str(raw.get("subject_type") or "unknown"),
            "relation_raw": relation_raw,
            "object_raw": str(raw.get("object_raw") or raw.get("object") or ""),
            "object_type": str(raw.get("object_type") or "unknown"),
            "relation_family": str(raw.get("relation_family") or direction.relation_family),
            "polarity_type": str(raw.get("polarity_type") or direction.polarity_type),
            "direction": str(raw.get("direction") or direction.direction),
            "direction_confidence": float(raw.get("direction_confidence", direction.confidence)),
            "direct_relation_sign": raw.get("direct_relation_sign", 0),
            "therapeutic_direction": str(raw.get("therapeutic_direction") or "unknown"),
            "negated": bool(raw.get("negated", False)),
            "null_or_no_effect": bool(raw.get("null_or_no_effect", False)),
            "speculative": bool(raw.get("speculative", False)),
            "confidence": float(raw.get("confidence", 0.0)),
            "context_slots": context,
            "assay": raw.get("assay") or context.get("assay") or context.get("assay_or_readout"),
            "species": raw.get("species") or context.get("species"),
            "cell_type": raw.get("cell_type") or context.get("cell_type"),
            "tissue_or_region": raw.get("tissue_or_region") or context.get("tissue_or_region") or context.get("brain_region"),
            "dose": raw.get("dose") or context.get("dose"),
            "timepoint": raw.get("timepoint") or context.get("timepoint") or context.get("time_after_treatment"),
            "linked_abstract_claim_ids": linked_abstract_ids,
            "linked_conflict_candidate_ids": linked_candidate_ids,
            "llm_extraction_ref": cache_key,
            "warnings": list(dict.fromkeys(list(raw.get("warnings") or []) + direction.warnings)),
        }
        evidence_records.append(record)
        claims.append({**record, "claim_id": str(raw.get("claim_id") or f"claim_{evidence_id}")})
    return evidence_records, claims


def run_fulltext_evidence_l1(
    evidence_spans: list[dict],
    conflict_candidates: list[dict],
    domain_profile: dict | None,
    run_dir: Path | None,
    execute: bool = False,
    api_enabled: bool = False,
    budget_policy: dict | None = None,
    *,
    llm_client: Any | None = None,
    allow_budget_overrun: bool = False,
    pilot_profile: str | None = None,
    paper_year_filter: dict | None = None,
) -> dict:
    """Extract only selected full-text spans after budget and cache checks."""

    profile = dict(domain_profile or {})
    prompt_profile = resolve_l1_prompt_profile(profile, pilot_profile)
    from code_engine.temporal.paper_year_filter import filter_papers_by_year, paper_year_filter_from_dict
    year_filter = paper_year_filter_from_dict(paper_year_filter)
    original_spans = list(evidence_spans)
    evidence_spans, year_counts = filter_papers_by_year(original_spans, year_filter)
    temporal_violation = bool(year_filter.enabled and year_counts["papers_excluded_by_year_filter"])
    policy = dict(budget_policy or {})
    estimate = estimate_l1_cost([str(item.get("text") or "") for item in evidence_spans], model_pricing_profile=policy.get("model_pricing_profile", "deepseek_default"))
    decision = enforce_l1_budget(estimate, policy, execute=execute and api_enabled, allow_budget_overrun=allow_budget_overrun)
    output_dir = Path(run_dir) if run_dir is not None else None
    cache_path = output_dir / "fulltext_l1_cache.json" if output_dir else None
    cache = {"entries": {}}
    if cache_path and cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache = {"entries": {}}
    candidates = {str(item.get("candidate_id")): item for item in conflict_candidates}
    evidence_records: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    calls = 0
    cache_hits = 0
    recovery_warnings: list[str] = []
    prompt_calls: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    attempted_l1_papers = successful_l1_papers = 0
    for span in evidence_spans:
        if str(span.get("source_scope")) != "full_text":
            continue
        key = _cache_key(span, profile)
        cached = cache.get("entries", {}).get(key)
        if cached:
            span_evidence = list(cached.get("evidence_records", []))
            span_claims = list(cached.get("claims", []))
            cache_hits += 1
        elif execute and api_enabled and not decision["blocked"] and llm_client is not None:
            attempted_l1_papers += 1
            compiled = compile_l1_prompt(prompt_profile, str(span.get("text") or ""))
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
                    write_l1_diagnostic(output_dir, stage="fulltext_l1", paper_id=str(span.get("paper_id") or "UNKNOWN"), pmid=span.get("pmid"), prompt_metadata=metadata, raw_response=raw_response, error_type=warning, parsed_json_type="list" if "list" in warning else "dict", recoverable=True, recovery_action=warning)
            except Exception as exc:
                calls += 1
                paper_id = str(span.get("paper_id") or "UNKNOWN")
                failure = l1_failure_record(stage="fulltext_l1", paper_id=paper_id, paper=span,
                                            prompt_metadata=metadata, exc=exc)
                errors.append(failure)
                write_l1_diagnostic(output_dir, stage="fulltext_l1", paper_id=paper_id, pmid=span.get("pmid"), prompt_metadata=metadata, raw_response=getattr(exc, "raw_response", ""), error_type=failure["error_type"], parsed_json_type=getattr(exc, "parsed_json_type", "unknown"), recoverable=False, recovery_action="paper_failed_workflow_continued")
                span_evidence, span_claims = [], []
                evidence_records.extend(span_evidence); claims.extend(span_claims)
                continue
            span_evidence, span_claims = _records_from_response(response, span, candidates, profile, key)
            for item in [*span_evidence, *span_claims]:
                item.update(metadata)
            cache.setdefault("entries", {})[key] = {"evidence_records": span_evidence, "claims": span_claims}
        else:
            span_evidence, span_claims = [], []
        evidence_records.extend(span_evidence)
        claims.extend(span_claims)
    budget_report = build_l1_budget_report(estimate, decision, actual_calls=calls)
    failed_l1_papers = len(errors)
    all_failed = attempted_l1_papers > 0 and successful_l1_papers == 0
    summary = {
        "execution_mode": "execute_api" if execute and api_enabled else "dry_run_plan",
        "selected_span_count": len(evidence_spans),
        "fulltext_evidence_count": len(evidence_records),
        "fulltext_claim_count": len(claims),
        "planned_l1_call_count": estimate["estimated_calls"],
        "api_calls_made": calls,
        "cache_hit_count": cache_hits,
        "budget_report": budget_report,
        "warnings": (["l1_budget_blocked"] if decision["blocked"] else []) + list(dict.fromkeys(recovery_warnings)),
        "prompt_profile_id": prompt_profile.profile_id,
        "prompt_profile_version": prompt_profile.version,
        "fulltext_l1_prompt_uses_compiled_profile": True,
        "prompt_calls": prompt_calls,
        "attempted_l1_papers": attempted_l1_papers, "successful_l1_papers": successful_l1_papers,
        "failed_l1_papers": failed_l1_papers,
        "timeout_count": sum(item["error_type"] == "timeout" for item in errors),
        "api_error_count": sum(item["error_type"] == "api_error" for item in errors),
        "parse_error_count": sum(item["error_type"] == "json_parse_failed" for item in errors),
        "schema_error_count": sum(item["error_type"] == "schema_validation_failed" for item in errors),
        "workflow_continued_after_l1_errors": bool(errors),
        "blocked_reason": "all_l1_extractions_failed" if all_failed else None,
        "paper_year_filter": year_filter.to_dict(),
        "papers_excluded_by_year_filter": year_counts["papers_excluded_by_year_filter"],
        "papers_missing_year_excluded": year_counts["papers_missing_year_excluded"],
        "temporal_filter_violation_detected": temporal_violation,
    }
    if execute and api_enabled and llm_client is None:
        summary["warnings"].append("llm_client_not_configured")
    artifacts = {}
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = output_dir / "fulltext_evidence_records.jsonl"
        claims_path = output_dir / "fulltext_l1_claims.jsonl"
        summary_path = output_dir / "fulltext_l1_summary.json"
        _write_jsonl(evidence_path, evidence_records)
        _write_jsonl(claims_path, claims)
        _write_jsonl(output_dir / "fulltext_l1_errors.jsonl", errors)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        if execute and api_enabled and calls:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts = {"evidence_records": str(evidence_path), "claims": str(claims_path), "summary": str(summary_path),
                     "errors": str(output_dir / "fulltext_l1_errors.jsonl")}
    return {"evidence_records": evidence_records, "claims": claims, "summary": summary, "artifacts": artifacts}


__all__ = ["run_fulltext_evidence_l1"]
