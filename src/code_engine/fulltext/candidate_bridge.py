from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


SOURCE_FILES = (
    "fulltext_discovery_escalation_candidates.jsonl",
    "l35_fulltext_discovery_candidate_papers.jsonl",
    "fulltext_escalation_candidates.jsonl",
)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_jsonl(path: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def normalize_pmcid(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    upper = raw.upper()
    if upper.startswith("PMC") and upper[3:].isdigit():
        return "PMC" + upper[3:]
    if raw.isdigit():
        return "PMC" + raw
    return raw


def _candidate_rows(artifacts: Path) -> list[dict]:
    rows: list[dict] = []
    for name in SOURCE_FILES:
        for index, row in enumerate(_read_jsonl(artifacts / name), start=1):
            if isinstance(row, dict):
                rows.append({**row, "_source_file": name, "_source_index": index})
    plan = _read_json(artifacts / "fulltext_escalation_plan.json")
    selected = plan.get("selected") if isinstance(plan, dict) else None
    if isinstance(selected, list):
        for index, row in enumerate(selected, start=1):
            if isinstance(row, dict):
                rows.append({**row, "_source_file": "fulltext_escalation_plan.json", "_source_index": index})
    return rows


def canonical_fulltext_candidates(artifacts_dir: str | Path) -> tuple[list[dict], list[dict]]:
    artifacts = Path(artifacts_dir)
    rows = _candidate_rows(artifacts)
    if not rows:
        return [], []

    pmcids_by_pmid: dict[str, set[str]] = {}
    for row in rows:
        pmid = str(row.get("pmid") or "").strip()
        pmcid = normalize_pmcid(row.get("pmcid"))
        if pmid and pmcid:
            pmcids_by_pmid.setdefault(pmid, set()).add(pmcid)
    conflicts = {pmid: values for pmid, values in pmcids_by_pmid.items() if len(values) > 1}

    grouped: dict[str, dict] = {}
    for row in rows:
        pmid = str(row.get("pmid") or "").strip()
        doi = str(row.get("doi") or "").strip()
        title = str(row.get("title") or "").strip()
        key = f"pmid:{pmid}" if pmid else f"doi:{doi}" if doi else f"title:{title.casefold()}" if title else f"paper:{row.get('paper_id') or row.get('canonical_paper_id') or row.get('_source_file')}:{row.get('_source_index')}"
        item = grouped.setdefault(key, {"_records": [], "_source_files": [], "_pmcids": set()})
        item["_records"].append(row)
        source = row.get("_source_file")
        if source and source not in item["_source_files"]:
            item["_source_files"].append(source)
        pmcid = normalize_pmcid(row.get("pmcid"))
        if pmcid:
            item["_pmcids"].add(pmcid)

    canonical: list[dict] = []
    conflict_audit: list[dict] = []
    for item in grouped.values():
        records = item["_records"]
        primary = next((row for row in records if normalize_pmcid(row.get("pmcid"))), records[0])
        pmid = str(primary.get("pmid") or "").strip() or None
        pmcids = sorted(item["_pmcids"])
        status = "missing"
        selected_pmcid = None
        skip_reason = "missing_pmcid"
        if pmid and pmid in conflicts:
            status = "conflict"
            skip_reason = "pmcid_conflict"
            pmcids = sorted(conflicts[pmid])
            conflict_audit.append({
                "pmid": pmid,
                "title": primary.get("title"),
                "candidate_pmcids": pmcids,
                "source_files": item["_source_files"],
                "selected_pmcid": None,
                "resolution_rule": "none",
                "action_taken": "skipped_retrieval_until_resolved",
            })
        elif pmcids:
            status = "ok"
            selected_pmcid = pmcids[0]
            skip_reason = None
        canonical.append({
            **{k: v for k, v in primary.items() if not str(k).startswith("_")},
            "paper_id": primary.get("paper_id") or primary.get("canonical_paper_id") or pmid or primary.get("doi"),
            "pmid": pmid,
            "pmcid": selected_pmcid,
            "doi": primary.get("doi"),
            "title": primary.get("title"),
            "source": primary.get("source") or primary.get("selection_source") or primary.get("selection_reason") or "fulltext_candidate_bridge",
            "source_files": item["_source_files"],
            "candidate_rank": primary.get("candidate_rank") or primary.get("rank") or primary.get("_source_index"),
            "candidate_reason": primary.get("candidate_reason") or primary.get("selection_reason") or primary.get("selection_source"),
            "pmcid_integrity_status": status,
            "skip_reason": skip_reason,
            "candidate_pmcids": pmcids,
        })
    return canonical, conflict_audit


def write_pmcid_integrity_audit(artifacts_dir: str | Path, conflicts: list[dict]) -> None:
    _write_jsonl(Path(artifacts_dir) / "pmcid_integrity_audit.jsonl", conflicts)


def write_candidate_bridge_audit(artifacts_dir: str | Path, candidates: list[dict], *,
                                 case_id: str | None = None,
                                 availability_by_id: dict[str, dict] | None = None,
                                 retrieval_by_id: dict[str, dict] | None = None) -> list[dict]:
    availability_by_id = availability_by_id or {}
    retrieval_by_id = retrieval_by_id or {}
    rows: list[dict] = []
    for candidate in candidates:
        key = str(candidate.get("paper_id") or candidate.get("pmid") or "")
        skip_reason = candidate.get("skip_reason")
        if not skip_reason and candidate.get("pmcid_integrity_status") == "missing":
            skip_reason = "missing_pmcid"
        if not skip_reason and candidate.get("pmcid_integrity_status") == "conflict":
            skip_reason = "pmcid_conflict"
        oa = availability_by_id.get(key) or {}
        retrieval = retrieval_by_id.get(key) or {}
        if not skip_reason and oa and oa.get("oa_status") != "available":
            skip_reason = "oa_xml_unavailable"
        if not skip_reason and candidate.get("blocked_reasons"):
            blocked = [str(x) for x in candidate.get("blocked_reasons") or []]
            skip_reason = "low_relevance_oa_backfill_blocked" if "low_relevance_oa_backfill_blocked" in blocked else blocked[0]
        rows.append({
            "case_id": case_id,
            "pmid": candidate.get("pmid"),
            "pmcid": candidate.get("pmcid"),
            "title": candidate.get("title"),
            "source_files": candidate.get("source_files") or [],
            "passed_to_oa_diagnostics": bool(candidate.get("pmcid") and candidate.get("pmcid_integrity_status") == "ok"),
            "passed_to_retrieval": bool(retrieval),
            "skip_reason": None if retrieval else skip_reason,
            "pmcid_integrity_status": candidate.get("pmcid_integrity_status") or ("ok" if candidate.get("pmcid") else "missing"),
        })
    _write_jsonl(Path(artifacts_dir) / "fulltext_candidate_bridge_audit.jsonl", rows)
    return rows


def availability_summary_from_bridge(candidates: list[dict], audit_rows: list[dict], *,
                                     enabled: bool = True, open_access_required: bool = True,
                                     retrieval_results: list[dict] | None = None) -> dict:
    retrieval_results = retrieval_results or []
    skip_counts = Counter(row.get("skip_reason") for row in audit_rows if row.get("skip_reason"))
    with_source_pmcid = sum(bool(x.get("pmcid") or x.get("candidate_pmcids")) for x in candidates)
    return {
        "enabled": bool(enabled),
        "candidate_count": len(candidates),
        "candidate_with_pmcid_count": with_source_pmcid,
        "candidate_missing_pmcid_count": sum((x.get("pmcid_integrity_status") or ("ok" if x.get("pmcid") else "missing")) == "missing" for x in candidates),
        "pmcid_conflict_count": sum((x.get("pmcid_integrity_status") == "conflict") for x in candidates),
        "available_count": sum(row.get("skip_reason") is None or row.get("passed_to_retrieval") for row in audit_rows),
        "unavailable_count": sum(bool(row.get("skip_reason")) and not row.get("passed_to_retrieval") for row in audit_rows),
        "retrieval_attempt_count": len(retrieval_results),
        "retrieval_success_count": sum(x.get("download_status") == "success" or x.get("full_text_status") == "available" for x in retrieval_results),
        "retrieval_failed_count": sum(not (x.get("download_status") == "success" or x.get("full_text_status") == "available") for x in retrieval_results),
        "open_access_required": bool(open_access_required),
        "skip_reason_counts": dict(skip_counts),
    }


__all__ = [
    "availability_summary_from_bridge",
    "canonical_fulltext_candidates",
    "normalize_pmcid",
    "write_candidate_bridge_audit",
    "write_pmcid_integrity_audit",
]
