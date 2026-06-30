"""Search-plan-driven PubMed/PMC acquisition with explicit network gating."""

from __future__ import annotations

import json
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


class NCBILiteratureClient:
    """Minimal NCBI E-utilities client used only after explicit network enablement."""

    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def search(self, query: str, source: str, max_results: int, year_from: int | None = None, year_to: int | None = None) -> list[dict[str, Any]]:
        db = "pmc" if source == "pmc" else "pubmed"
        term = query
        if year_from or year_to:
            term += f" AND {year_from or 1900}:{year_to or 3000}[pdat]"
        params = urllib.parse.urlencode({"db": db, "term": term, "retmode": "json", "retmax": max_results})
        with urllib.request.urlopen(f"{self.base_url}/esearch.fcgi?{params}", timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        records = []
        for identifier in payload.get("esearchresult", {}).get("idlist", []):
            paper_id = f"PMC{identifier}" if source == "pmc" and not str(identifier).startswith("PMC") else str(identifier)
            records.append({"paper_id": paper_id, "pmcid": paper_id if source == "pmc" else None, "pmid": identifier if source == "pubmed" else None})
        return records

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
    }
    if not execute or not network:
        report["warnings"].append("network_disabled_acquisition_plan_only")
    else:
        active_client = client or NCBILiteratureClient()
        candidates: list[dict[str, Any]] = []
        for query in selected_queries:
            if len(candidates) >= max_papers:
                break
            found = active_client.search(query.query_string, query.source, min(query.max_results, max_papers - len(candidates)), year_from or query.year_from, year_to or query.year_to)
            report["network_calls_made"] += 1
            candidates.extend({**item, "source": query.source} for item in found)
        report["candidate_papers"] = candidates[:max_papers]
        seen = set(existing_keys)
        cached_index: dict[str, dict[str, Any]] = {}
        for cached in cached_papers or []:
            for value in _dedup_values(cached) | {f"paper_id:{str(cached.get('paper_id') or cached.get('canonical_paper_id') or '').casefold()}"}:
                cached_index[value] = cached
        for record in report["candidate_papers"]:
            keys = _dedup_values(record)
            paper_id = str(record.get("paper_id") or record.get("pmcid") or record.get("pmid"))
            cached = next((cached_index[key] for key in keys if key in cached_index), None) or cached_index.get(f"paper_id:{paper_id.casefold()}")
            if cached:
                report["reused_papers"].append({**record, **cached, "reused_from_paper_artifact_cache": True})
                report["paper_cache_consumed_by_acquisition"] = True
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
                continue
            content = active_client.fetch(record, record["source"])
            report["network_calls_made"] += 1
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
        report["initial_fulltext_download_count"] = sum(item.get("source") == "pmc" for item in report["downloaded_papers"])
        manifest.setdefault("metadata", {})["total_registered_assets"] = len(papers)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
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
