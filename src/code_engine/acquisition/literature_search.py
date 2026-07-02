"""Search-plan-driven PubMed/PMC acquisition with explicit network gating."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from code_engine.acquisition.manifest import normalized_title_hash
from code_engine.query.search_planner import LiteratureSearchPlan, LiteratureSearchQuery


class LiteratureClient(Protocol):
    def search(self, query: str, source: str, max_results: int, year_from: int | None = None, year_to: int | None = None) -> list[dict[str, Any]]: ...
    def fetch(self, record: dict[str, Any], source: str) -> str: ...


class SearchResults(list[dict[str, Any]]):
    """Search records plus the ESearch total, which may exceed returned IDs."""

    def __init__(self, values: list[dict[str, Any]], reported_total_count: int) -> None:
        super().__init__(values)
        self.reported_total_count = reported_total_count


class NCBILiteratureClient:
    """Minimal NCBI E-utilities client used only after explicit network enablement."""

    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def search(self, query: str, source: str, max_results: int, year_from: int | None = None, year_to: int | None = None) -> list[dict[str, Any]]:
        db = "pmc" if source == "pmc" else "pubmed"
        term = query
        if (year_from or year_to) and "[pdat]" not in term.casefold() and "[date - publication]" not in term.casefold():
            term += f" AND {year_from or 1900}:{year_to or 3000}[pdat]"
        params = urllib.parse.urlencode({"db": db, "term": term, "retmode": "json", "retmax": max_results})
        with urllib.request.urlopen(f"{self.base_url}/esearch.fcgi?{params}", timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        records = []
        for identifier in payload.get("esearchresult", {}).get("idlist", []):
            paper_id = f"PMC{identifier}" if source == "pmc" and not str(identifier).startswith("PMC") else str(identifier)
            records.append({"paper_id": paper_id, "pmcid": paper_id if source == "pmc" else None, "pmid": identifier if source == "pubmed" else None})
        return SearchResults(records, int(payload.get("esearchresult", {}).get("count") or len(records)))

    def fetch(self, record: dict[str, Any], source: str) -> str:
        db = "pmc" if source == "pmc" else "pubmed"
        identifier = record.get("pmcid") or record.get("pmid") or record["paper_id"]
        identifier = str(identifier).removeprefix("PMC") if db == "pmc" else str(identifier)
        params = urllib.parse.urlencode({"db": db, "id": identifier, "rettype": "full" if db == "pmc" else "abstract", "retmode": "xml"})
        with urllib.request.urlopen(f"{self.base_url}/efetch.fcgi?{params}", timeout=60) as response:
            return response.read().decode("utf-8")


def _xml_text(node: ET.Element | None) -> str:
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def parse_pubmed_xml(xml_text: str, *, fallback_pmid: str = "") -> dict[str, Any]:
    """Parse PubMed XML into the metadata and abstract fields consumed by L1."""

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return {"pmid": fallback_pmid, "abstract": "", "abstract_text": "", "abstract_sections": [],
                "abstract_available": False, "abstract_missing_reason": f"pubmed_xml_parse_error:{exc}",
                "metadata_source": "pubmed_xml"}
    article = root.find(".//PubmedArticle")
    if article is None:
        article = root
    sections = []
    for item in article.findall(".//Abstract/AbstractText"):
        value = _xml_text(item)
        if value:
            sections.append({"label": item.attrib.get("Label") or item.attrib.get("NlmCategory") or "", "text": value})
    abstract = "\n".join(f"{item['label']}: {item['text']}" if item["label"] else item["text"] for item in sections)
    identifiers = {str(item.attrib.get("IdType") or "").casefold(): _xml_text(item) for item in article.findall(".//ArticleId")}
    payload = {
        "pmid": _xml_text(article.find(".//PMID")) or fallback_pmid,
        "pmcid": identifiers.get("pmc"), "doi": identifiers.get("doi"),
        "title": _xml_text(article.find(".//ArticleTitle")),
        "journal": _xml_text(article.find(".//Journal/Title")),
        "publication_year": _xml_text(article.find(".//PubDate/Year")) or _xml_text(article.find(".//ArticleDate/Year")) or None,
        "abstract": abstract, "abstract_text": abstract, "abstract_sections": sections,
        "abstract_available": bool(abstract), "metadata_source": "pubmed_xml",
    }
    if not abstract:
        payload["abstract_missing_reason"] = "pubmed_record_has_no_abstract"
    return payload


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"metadata": {}, "papers": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _dedup_values(record: dict[str, Any]) -> set[str]:
    values = set()
    for field in ("pmid", "pmcid", "doi"):
        value = str(record.get(field) or "").strip().casefold()
        if value:
            values.add(f"{field}:{value}")
    title_hash = normalized_title_hash(record.get("title", ""))
    if title_hash:
        values.add(f"title:{title_hash}")
    return values


def execute_acquisition_plan(
    plan: LiteratureSearchPlan,
    *,
    repository_root: str | Path = ".",
    execute: bool = False,
    network: bool = False,
    source: str = "pubmed",
    max_papers: int = 50,
    year_from: int | None = None,
    year_to: int | None = None,
    client: LiteratureClient | None = None,
    cached_papers: list[dict[str, Any]] | None = None,
    diversify_acquisition: bool = False,
    per_query_max_results: int | None = None,
    per_query_group_max_results: dict[str, int] | None = None,
    reserve_query_group: dict[str, int] | None = None,
) -> dict[str, Any]:
    root = Path(repository_root)
    manifest_path = root / "data/metadata/global_manifest.json"
    manifest = _read_manifest(manifest_path)
    papers = manifest.setdefault("papers", {})
    existing_keys: set[str] = set()
    for paper_id, metadata in papers.items():
        existing_keys.update(_dedup_values({
            "paper_id": paper_id,
            "pmcid": paper_id if str(paper_id).startswith("PMC") else None,
            "pmid": paper_id if str(paper_id).isdigit() else None,
            **metadata,
        }))
    selected_queries: list[LiteratureSearchQuery] = []
    if source in {"pubmed", "both"}:
        selected_queries.extend(plan.pubmed_queries)
    if source == "pmc":
        selected_queries.extend(plan.pmc_queries)
    report: dict[str, Any] = {
        "intent_id": plan.intent_id,
        "execution_mode": "execute_network" if execute and network else "dry_run_no_network",
        "queries": [item.model_dump() for item in selected_queries],
        "candidate_papers": [], "downloaded_papers": [], "reused_papers": [],
        "skipped_duplicates": [], "network_calls_made": 0, "warnings": [],
        "initial_fulltext_download_count": 0,
        "paper_cache_consumed_by_acquisition": False,
        "query_diagnostics": [],
        "pubmed_esearch_reported_total_count": 0, "pubmed_esearch_returned_id_count": 0,
        "pubmed_efetch_attempted_count": 0, "pubmed_efetch_returned_record_count": 0,
        "pubmed_reused_existing_record_count": 0, "pubmed_new_raw_record_count": 0,
        "pubmed_post_filter_record_count": 0, "pubmed_dedup_removed_count": 0,
    }
    query_count = len(selected_queries)
    even_caps = []
    if query_count:
        quotient, remainder = divmod(max_papers, query_count)
        even_caps = [quotient + int(index < remainder) for index in range(query_count)]
    report["diversified_acquisition"] = {
        "enabled": bool(diversify_acquisition),
        "strategy": "per_query_explicit" if per_query_max_results is not None else "per_query_even_split",
        "global_max_papers": max_papers,
        "per_query_cap_default": per_query_max_results or (max(even_caps) if even_caps else 0),
        "group_quota_supported": False,
    }
    if diversify_acquisition and (per_query_group_max_results or reserve_query_group):
        report["warnings"].append("query_group_quotas_not_implemented_even_split_used")
    if not execute or not network:
        report["warnings"].append("network_disabled_acquisition_plan_only")
    else:
        active_client = client or NCBILiteratureClient()
        candidates: list[dict[str, Any]] = []
        candidate_by_key: dict[str, dict[str, Any]] = {}
        for query_index, query in enumerate(selected_queries):
            if len(candidates) >= max_papers and not diversify_acquisition:
                for skipped_query in selected_queries[query_index:]:
                    report["query_diagnostics"].append({"intent_id": plan.intent_id, "pubmed_query_id": skipped_query.query_id,
                    "query_id": skipped_query.query_id, "query_string": skipped_query.query_string,
                    "query_group": skipped_query.query_group, "query_scope": skipped_query.query_scope,
                    "year_from": skipped_query.year_from, "year_to": skipped_query.year_to, "source": skipped_query.source, "attempt": 0,
                    "request_url_or_params_hash": "", "esearch_status": "skipped", "esearch_return_count": 0,
                    "esearch_reported_total_count": 0, "retstart": 0, "retmax": skipped_query.max_results,
                    "requested_retmax": 0, "effective_query_cap": 0, "limited_by_diversified_quota": False,
                    "efetch_attempted": False, "efetch_status": None, "efetch_requested_count": 0,
                    "efetch_returned_count": 0, "reused_existing_record_count": 0, "new_raw_record_count": 0,
                    "post_filter_record_count": 0, "dedup_removed_count": 0, "downloaded_count": 0,
                    "candidate_count": 0, "effective_acquisition_count": 0,
                    "excluded_by_year_filter_count": 0, "missing_year_count": 0,
                    "skip_reason": "global_max_papers_already_satisfied", "error_type": None,
                    "error_message": None, "elapsed_seconds": 0.0})
                break
            report["network_calls_made"] += 1
            quota = (per_query_max_results if per_query_max_results is not None else even_caps[query_index]) if diversify_acquisition else max_papers - len(candidates)
            requested = max(0, min(query.max_results, quota)); started = time.monotonic()
            diagnostic = {"intent_id": plan.intent_id, "pubmed_query_id": query.query_id,
                "query_id": query.query_id, "query_string": query.query_string,
                "query_group": query.query_group, "query_scope": query.query_scope,
                "year_from": year_from if year_from is not None else query.year_from,
                "year_to": year_to if year_to is not None else query.year_to, "source": query.source, "attempt": 1,
                "request_url_or_params_hash": hashlib.sha256(f"{query.source}|{query.query_string}|{requested}".encode()).hexdigest(),
                "esearch_status": "success", "esearch_return_count": 0, "esearch_reported_total_count": 0,
                "retstart": 0, "retmax": requested, "requested_retmax": requested,
                "effective_query_cap": requested, "limited_by_diversified_quota": bool(diversify_acquisition and requested < query.max_results),
                "efetch_attempted": False, "efetch_status": None, "efetch_requested_count": 0,
                "efetch_returned_count": 0, "reused_existing_record_count": 0, "new_raw_record_count": 0,
                "post_filter_record_count": 0, "dedup_removed_count": 0, "downloaded_count": 0,
                "candidate_count": 0, "effective_acquisition_count": 0,
                "excluded_by_year_filter_count": 0, "missing_year_count": 0,
                "skip_reason": None, "error_type": None, "error_message": None, "elapsed_seconds": 0.0}
            try:
                found = active_client.search(query.query_string, query.source, requested,
                    year_from if year_from is not None else query.year_from,
                    year_to if year_to is not None else query.year_to)
                diagnostic["esearch_return_count"] = len(found)
                diagnostic["esearch_reported_total_count"] = int(getattr(found, "reported_total_count", len(found)))
                diagnostic["esearch_status"] = "success" if found else "zero_results"
                report["pubmed_esearch_reported_total_count"] += diagnostic["esearch_reported_total_count"]
                report["pubmed_esearch_returned_id_count"] += len(found)
                for item in found:
                    record = {**item, "source": query.source, "retrieval_query_id": query.query_id,
                              "first_seen_query_id": query.query_id, "matched_query_ids": [query.query_id],
                              "matched_query_groups": [query.query_group], "matched_query_scopes": [query.query_scope],
                              "query_record": query.model_dump(mode="json")}
                    keys = sorted(_dedup_values(record)) or [f"paper_id:{record.get('paper_id')}"]
                    prior = next((candidate_by_key[value] for value in keys if value in candidate_by_key), None)
                    if prior is not None:
                        report["pubmed_dedup_removed_count"] += 1
                        diagnostic["dedup_removed_count"] += 1
                        for field, value in (("matched_query_ids", query.query_id), ("matched_query_groups", query.query_group), ("matched_query_scopes", query.query_scope)):
                            if value not in prior[field]: prior[field].append(value)
                    elif len(candidates) < max_papers:
                        for value in keys:
                            candidate_by_key[value] = record
                        candidates.append(record)
                        diagnostic["candidate_count"] += 1
            except Exception as exc:
                diagnostic.update(esearch_status="timeout" if isinstance(exc, TimeoutError) else "http_error",
                                  error_type=type(exc).__name__, error_message=str(exc)[:1000])
                report["warnings"].append(f"pubmed_query_failed:{query.query_id}:{type(exc).__name__}")
            diagnostic["elapsed_seconds"] = round(time.monotonic() - started, 6)
            report["query_diagnostics"].append(diagnostic)
        report["candidate_papers"] = candidates[:max_papers]
        seen = set(existing_keys)
        cached_index: dict[str, dict[str, Any]] = {}
        for cached in cached_papers or []:
            for value in _dedup_values(cached) | {f"paper_id:{str(cached.get('paper_id') or cached.get('canonical_paper_id') or '').casefold()}"}:
                cached_index[value] = cached
        for record in report["candidate_papers"]:
            keys = _dedup_values(record)
            paper_id = str(record.get("paper_id") or record.get("pmcid") or record.get("pmid"))
            diagnostic = next((item for item in report["query_diagnostics"] if item["query_id"] == record.get("retrieval_query_id")), None)
            cached = next((cached_index[key] for key in keys if key in cached_index), None) or cached_index.get(f"paper_id:{paper_id.casefold()}")
            if cached:
                report["reused_papers"].append({**record, **cached, "reused_from_paper_artifact_cache": True})
                report["paper_cache_consumed_by_acquisition"] = True
                if diagnostic: diagnostic["reused_existing_record_count"] += 1
                seen.update(keys)
                continue
            raw_path = root / (f"data/raw/xml/{paper_id}.xml" if record["source"] == "pmc" else f"data/raw/abstracts/{paper_id}.json")
            if keys.intersection(seen) or paper_id in papers or raw_path.exists():
                existing = dict(papers.get(paper_id) or {})
                if record["source"] == "pubmed" and raw_path.exists() and not (existing.get("abstract") or existing.get("abstract_text")):
                    try:
                        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
                        existing.update(parse_pubmed_xml(str(raw_payload.get("abstract_xml") or ""), fallback_pmid=str(record.get("pmid") or paper_id)))
                    except (OSError, json.JSONDecodeError):
                        pass
                report["reused_papers"].append({**record, **existing, "raw_path": str(raw_path.relative_to(root)) if raw_path.exists() else existing.get("raw_path")})
                if diagnostic: diagnostic["reused_existing_record_count"] += 1
                continue
            report["network_calls_made"] += 1
            if diagnostic:
                diagnostic["efetch_attempted"] = True
                diagnostic["efetch_requested_count"] += 1
            report["pubmed_efetch_attempted_count"] += 1
            try:
                content = active_client.fetch(record, record["source"])
                if diagnostic:
                    diagnostic["efetch_status"] = "success"
                    diagnostic["efetch_returned_count"] += 1
                report["pubmed_efetch_returned_record_count"] += 1
            except Exception as exc:
                if diagnostic:
                    diagnostic["efetch_status"] = "timeout" if isinstance(exc, TimeoutError) else "http_error"
                    diagnostic["error_type"] = type(exc).__name__; diagnostic["error_message"] = str(exc)[:1000]
                report["warnings"].append(f"pubmed_fetch_failed:{paper_id}:{type(exc).__name__}")
                continue
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            if record["source"] == "pmc":
                raw_path.write_text(content, encoding="utf-8")
                parsed = {}
            else:
                raw_path.write_text(json.dumps({"paper_id": paper_id, "abstract_xml": content}, ensure_ascii=False, indent=2), encoding="utf-8")
                parsed = parse_pubmed_xml(content, fallback_pmid=str(record.get("pmid") or paper_id))
            metadata = {key: value for key, value in {**record, **parsed}.items() if key != "paper_id"}
            metadata.update({"raw_path": str(raw_path.relative_to(root)), "timestamp": datetime.now(timezone.utc).isoformat()})
            papers[paper_id] = metadata
            seen.update(keys)
            report["downloaded_papers"].append({**record, **parsed, "raw_path": str(raw_path.relative_to(root)), "raw_xml_path": str(raw_path.relative_to(root))})
            if diagnostic:
                diagnostic["new_raw_record_count"] += 1
                diagnostic["downloaded_count"] += 1
            report["pubmed_new_raw_record_count"] += 1
        report["initial_fulltext_download_count"] = sum(item.get("source") == "pmc" for item in report["downloaded_papers"])
        manifest.setdefault("metadata", {})["total_registered_assets"] = len(papers)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report["pubmed_reused_existing_record_count"] = len(report["reused_papers"])
    report["downloaded_papers_count"] = len(report["downloaded_papers"])
    report["candidate_papers_count"] = len(report["candidate_papers"])
    report["retrieved_or_reused_papers_count"] = len(report["downloaded_papers"]) + len(report["reused_papers"])
    report["effective_acquisition_count"] = report["retrieved_or_reused_papers_count"] or report["candidate_papers_count"]
    for diagnostic in report["query_diagnostics"]:
        diagnostic["effective_acquisition_count"] = diagnostic.get("downloaded_count", 0) + diagnostic.get("reused_existing_record_count", 0)
    diagnostics = report["query_diagnostics"]
    report.update({"query_diagnostics_available": True, "pubmed_query_count": len(selected_queries),
        "pubmed_query_success_count": sum(item["esearch_status"] == "success" for item in diagnostics),
        "pubmed_query_zero_result_count": sum(item["esearch_status"] == "zero_results" for item in diagnostics),
        "pubmed_query_error_count": sum(item["esearch_status"] in {"http_error", "parse_error", "timeout"} for item in diagnostics),
        "pubmed_query_skipped_count": sum(item["esearch_status"] == "skipped" for item in diagnostics),
        "acquisition_short_circuit_detected": any(item["esearch_status"] == "skipped" for item in diagnostics),
        "acquisition_short_circuit_reason": next((item["skip_reason"] for item in diagnostics if item["esearch_status"] == "skipped"), None)})
    attempted = [item for item in diagnostics if item["esearch_status"] != "skipped"]
    if not report["candidate_papers"]:
        if attempted and all(item["esearch_status"] == "zero_results" for item in attempted): report["reason"] = "all_queries_zero_results"
        elif attempted and all(item["esearch_status"] in {"http_error", "parse_error", "timeout"} for item in attempted): report["reason"] = "all_queries_failed"
        elif not attempted: report["reason"] = "network_disabled" if not execute or not network else "all_queries_skipped"
        else: report["reason"] = "no_candidates_after_query_attempts"
    data_path = root / f"data/query/acquisition_report_{plan.intent_id}.json"
    md_path = root / f"reports/acquisition_report_{plan.intent_id}.md"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        "# Acquisition Report\n\n"
        f"- Candidates: {len(report['candidate_papers'])}\n"
        f"- Downloaded: {len(report['downloaded_papers'])}\n"
        f"- Reused: {len(report['reused_papers'])}\n"
        f"- Network calls: {report['network_calls_made']}\n",
        encoding="utf-8",
    )
    return report
