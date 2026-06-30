"""Search-plan-driven PubMed/PMC acquisition with explicit network gating."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
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
        params = urllib.parse.urlencode({"db": db, "id": identifier, "rettype": "full", "retmode": "xml"})
        with urllib.request.urlopen(f"{self.base_url}/efetch.fcgi?{params}", timeout=60) as response:
            return response.read().decode("utf-8")


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
    source: str = "both",
    max_papers: int = 50,
    year_from: int | None = None,
    year_to: int | None = None,
    client: LiteratureClient | None = None,
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
    if source in {"pmc", "both"}:
        selected_queries.extend(plan.pmc_queries)
    if source in {"pubmed", "both"}:
        selected_queries.extend(plan.pubmed_queries)
    report: dict[str, Any] = {
        "intent_id": plan.intent_id,
        "execution_mode": "execute_network" if execute and network else "dry_run_no_network",
        "queries": [item.model_dump() for item in selected_queries],
        "candidate_papers": [], "downloaded_papers": [], "reused_papers": [],
        "skipped_duplicates": [], "network_calls_made": 0, "warnings": [],
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
        for record in report["candidate_papers"]:
            keys = _dedup_values(record)
            paper_id = str(record.get("paper_id") or record.get("pmcid") or record.get("pmid"))
            raw_path = root / (f"data/raw/xml/{paper_id}.xml" if record["source"] == "pmc" else f"data/raw/abstracts/{paper_id}.json")
            if keys.intersection(seen) or paper_id in papers or raw_path.exists():
                report["reused_papers"].append(record)
                continue
            content = active_client.fetch(record, record["source"])
            report["network_calls_made"] += 1
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            if record["source"] == "pmc":
                raw_path.write_text(content, encoding="utf-8")
            else:
                raw_path.write_text(json.dumps({"paper_id": paper_id, "abstract_xml": content}, ensure_ascii=False, indent=2), encoding="utf-8")
            metadata = {key: value for key, value in record.items() if key != "paper_id"}
            metadata.update({"raw_path": str(raw_path.relative_to(root)), "timestamp": datetime.now(timezone.utc).isoformat()})
            papers[paper_id] = metadata
            seen.update(keys)
            report["downloaded_papers"].append({**record, "raw_path": str(raw_path.relative_to(root))})
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
