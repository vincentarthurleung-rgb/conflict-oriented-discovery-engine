from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from code_engine.fulltext.candidate_selection import classify_oa_candidate, select_conflict_related_papers
from code_engine.fulltext.conflict_confirmation import confirm_fulltext_conflicts
from code_engine.fulltext.l1_extraction import extract_fulltext_claims
from code_engine.fulltext.pmc_id_resolver import resolve_pmcid
from code_engine.fulltext.pmc_oa_client import check_oa_availability
from code_engine.fulltext.pmc_oa_downloader import download_oa_article


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _expose_summary(artifacts: Path, summary: dict) -> None:
    path = artifacts / "pipeline_stage_summary.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    payload["l35_fulltext_confirmation"] = summary
    _write_json(path, payload)
    block = "\n## L3.5 OA Full-Text Retrieval and Confirmation\n\n" + "\n".join(f"- {key}: {value}" for key, value in summary.items()) + "\n"
    for name in ("pipeline_stage_summary.md", "whitebox_case_report.md"):
        target = artifacts / name
        if target.is_file():
            target.write_text(target.read_text(encoding="utf-8") + block, encoding="utf-8")
    hypothesis = artifacts / "hypothesis_summary.json"
    if hypothesis.is_file():
        try:
            hp = json.loads(hypothesis.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            hp = {}
        hp.update(full_text_confirmation_status=summary.get("status"), full_text_candidate_paper_count=summary.get("scientific_candidate_count", 0),
                  full_text_available_count=summary.get("relevant_oa_candidate_count", 0), full_text_l1_claim_count=summary.get("fulltext_l1_claim_count", 0),
                  full_text_confirmed_conflict_count=summary.get("fulltext_confirmed_conflict_count", 0))
        _write_json(hypothesis, hp)


def _counts(candidates: list[dict]) -> dict:
    return {
        "scientific_candidate_count": len(candidates),
        "relevance_passed_candidate_count": sum(bool(x.get("relevance_passed")) for x in candidates),
        "oa_available_candidate_count": sum(bool(x.get("oa_available")) for x in candidates),
        "relevant_oa_candidate_count": sum(x.get("candidate_tier") == "high_relevance_oa" for x in candidates),
        "selected_fulltext_count": sum(bool(x.get("selected_for_fulltext_l1")) for x in candidates),
        "high_relevance_non_oa_count": sum(x.get("candidate_tier") == "high_relevance_non_oa" for x in candidates),
        "low_relevance_oa_count": sum(x.get("candidate_tier") == "low_relevance_oa" for x in candidates),
        "low_relevance_oa_backfill_blocked_count": sum("low_relevance_oa_backfill_blocked" in x.get("blocked_reasons", []) for x in candidates),
    }


def run_l35_pmc_oa_stage(run_dir: str | Path, *, enabled: bool, network_enabled: bool = False, api_enabled: bool = False,
                         max_papers: int = 20, include_near_conflicts: bool = False, extractor: Callable | None = None,
                         l1_client=None, l1_provider: str | None = None, l1_model: str | None = None,
                         max_sections_per_paper: int = 12, max_chunks_per_paper: int = 24, max_chars_per_chunk: int = 6000,
                         max_total_chunks: int = 200, l1_read_timeout_seconds: float = 240, l1_max_retries: int = 1,
                         id_transport=None, oa_transport=None, download_transport=None) -> dict:
    run = Path(run_dir); artifacts = run / "artifacts"; artifacts.mkdir(parents=True, exist_ok=True)
    selection = select_conflict_related_papers(artifacts, include_near_conflicts=include_near_conflicts, max_papers=max_papers) if enabled else {
        "candidate_papers": [], "status": "not_enabled", "message": "Full-text confirmation is disabled by case policy."}
    candidates = selection["candidate_papers"]
    discovery_path = artifacts / "fulltext_discovery_escalation_candidates.jsonl"
    discovery_count = sum(bool(line.strip()) for line in discovery_path.read_text(encoding="utf-8").splitlines()) if discovery_path.is_file() else 0
    handoff = {"fulltext_escalation_candidate_count": discovery_count, "l35_candidate_paper_count": len(candidates),
        "fulltext_handoff_consistent": not enabled or not discovery_count or discovery_count == len(candidates),
        "fulltext_handoff_warnings": [] if not enabled or not discovery_count or discovery_count == len(candidates) else ["discovery_escalation_l35_count_mismatch"]}
    empty_counts = _counts(candidates)
    if not enabled or not candidates:
        status = "not_enabled" if not enabled else "completed_no_candidates"
        summary = {"status": status, "candidate_paper_count": 0, **empty_counts, "pmcid_resolved_count": 0,
            "oa_available_count": 0, "fulltext_downloaded_count": 0, "fulltext_l1_claim_count": 0,
            "fulltext_confirmed_conflict_count": 0, "copyright_safe": True, "non_oa_skipped_count": 0,
            "no_relevant_oa": False, "message": selection.get("message"), **handoff}
        _write_jsonl(artifacts / "l35_fulltext_candidate_papers.jsonl", candidates)
        for name in ("l35_fulltext_retrieval_results.jsonl", "l35_fulltext_l1_claims.jsonl", "l35_fulltext_conflict_confirmations.jsonl", "l35_fulltext_oa_candidate_papers.jsonl"):
            _write_jsonl(artifacts / name, [])
        for name in ("l35_fulltext_retrieval_summary.json", "l35_fulltext_l1_summary.json", "l35_fulltext_conflict_confirmation_summary.json"):
            _write_json(artifacts / name, summary)
        _expose_summary(artifacts, summary)
        return summary

    resolved: list[dict] = []; availability_by_id: dict[str, dict] = {}
    cache = artifacts / "cache/pmc_idconv"; fulltext_root = artifacts / "fulltext/pmc_oa"
    classified: list[dict] = []
    for paper in candidates:
        identity = resolve_pmcid(paper, network_enabled=network_enabled, cache_dir=cache, transport=id_transport); resolved.append(identity)
        enriched = {**paper, "pmcid": identity.get("pmcid") or paper.get("pmcid")}
        oa = check_oa_availability(enriched["pmcid"], network_enabled=network_enabled, transport=oa_transport) if enriched.get("pmcid") else {"oa_status": "unavailable", "reason": "no_pmcid", "decision": "skip_no_resource"}
        key = str(enriched.get("paper_id") or enriched.get("pmid")); availability_by_id[key] = oa
        classified.append(classify_oa_candidate(enriched, oa_available=oa.get("oa_status") == "available"))
    quota = max(0, min(max_papers, int(selection.get("max_fulltext_papers", max_papers))))
    selected_ids = set([str(x.get("paper_id") or x.get("pmid")) for x in classified if x.get("relevance_passed") and x.get("oa_available")][:quota])
    classified = [classify_oa_candidate(x, oa_available=bool(x.get("oa_available")), selected=str(x.get("paper_id") or x.get("pmid")) in selected_ids) for x in classified]
    _write_jsonl(artifacts / "l35_fulltext_candidate_papers.jsonl", classified)
    executable = [x for x in classified if x.get("selected_for_fulltext_l1")]
    _write_jsonl(artifacts / "l35_fulltext_oa_candidate_papers.jsonl", executable)

    results: list[dict] = []; claims: list[dict] = []
    for paper in executable:
        key = str(paper.get("paper_id") or paper.get("pmid")); oa = availability_by_id[key]
        result = download_oa_article(paper, oa, fulltext_root, network_enabled=network_enabled, transport=download_transport); results.append(result)
        if result.get("full_text_status") == "available" and extractor is not None:
            article = json.loads((fulltext_root / paper["pmcid"] / "article_text.json").read_text(encoding="utf-8"))
            claims += extract_fulltext_claims(paper, article, extractor=extractor, provider=os.getenv("L1_PROVIDER"), model=os.getenv("MODEL_NAME"))
    l1_summary = {"fulltext_l1_status": "skipped", "api_calls_made": 0, "limit_hit": False}
    if extractor is None and executable:
        from code_engine.fulltext.fulltext_l1_extractor import run_fulltext_l1_extraction
        l1 = run_fulltext_l1_extraction(run_dir=run, fulltext_candidates_path=artifacts / "l35_fulltext_oa_candidate_papers.jsonl",
            parsed_articles_dir=fulltext_root, l1_provider=l1_provider or os.getenv("L1_PROVIDER", ""), l1_model=l1_model or os.getenv("MODEL_NAME", ""),
            api_enabled=api_enabled, network_enabled=network_enabled, max_papers=max_papers, max_sections_per_paper=max_sections_per_paper,
            max_chunks_per_paper=max_chunks_per_paper, max_chars_per_chunk=max_chars_per_chunk, max_total_chunks=max_total_chunks,
            client=l1_client, read_timeout_seconds=l1_read_timeout_seconds, max_retries=l1_max_retries)
        claims = l1["claims"]; l1_summary = l1["summary"]
    conflict_map = {}
    for paper in executable:
        for cid in paper.get("conflict_candidate_ids", []):
            if cid is not None:
                item = conflict_map.setdefault(str(cid), {"candidate_id": str(cid), "paper_ids": [], "relation_family": paper.get("conflict_relation") or paper.get("relation_family")})
                item["paper_ids"].append(str(paper.get("paper_id")))
    confirmation = confirm_fulltext_conflicts(list(conflict_map.values()), claims, results, l1_status=l1_summary.get("fulltext_l1_status"))
    counts = _counts(classified); downloaded = sum(x.get("full_text_status") == "available" for x in results)
    if not counts["relevant_oa_candidate_count"]:
        stage_status = "completed_no_relevant_oa"
    elif l1_summary.get("fulltext_l1_status") == "blocked":
        stage_status = "partially_completed_fulltext_l1_not_run"
    else:
        stage_status = "completed" if downloaded == len(executable) and l1_summary.get("fulltext_l1_status") == "completed" else "partially_completed"
    summary = {"status": stage_status, "fulltext_confirmation_status": stage_status, "candidate_paper_count": len(classified), **counts,
        "pmcid_resolved_count": sum(bool(x.get("pmcid")) for x in resolved), "oa_available_count": counts["oa_available_candidate_count"],
        "fulltext_downloaded_count": downloaded, "fulltext_l1_claim_count": len(claims),
        "fulltext_confirmed_conflict_count": confirmation["summary"]["fulltext_confirmed_conflict_count"],
        "fulltext_l1_api_calls": l1_summary.get("api_calls_made", 0), "fulltext_limit_hit": l1_summary.get("limit_hit", False),
        "copyright_safe": True, "non_oa_skipped_count": counts["high_relevance_non_oa_count"],
        "no_relevant_oa": not bool(counts["relevant_oa_candidate_count"]),
        "warnings": [] if stage_status != "partially_completed_fulltext_l1_not_run" else ["fulltext_l1_not_run_api_network_or_client_unavailable"], **handoff}
    _write_jsonl(artifacts / "l35_fulltext_retrieval_results.jsonl", results); _write_jsonl(artifacts / "l35_fulltext_l1_claims.jsonl", claims)
    _write_jsonl(artifacts / "l35_fulltext_conflict_confirmations.jsonl", confirmation["confirmations"])
    _write_json(artifacts / "l35_fulltext_retrieval_summary.json", summary); _write_json(artifacts / "l35_fulltext_l1_summary.json", {**l1_summary, "copyright_safe": True})
    _write_json(artifacts / "l35_fulltext_conflict_confirmation_summary.json", {**summary, **confirmation["summary"]})
    _expose_summary(artifacts, summary)
    return summary
