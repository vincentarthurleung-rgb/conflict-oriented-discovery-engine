"""Run-local corpus manifest and deduplication reporting."""

from __future__ import annotations
from collections import Counter
from pathlib import Path

from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl
from code_engine.corpus.paper_registry import PaperRegistry


def build_run_paper_manifest(papers: list[dict], registry: PaperRegistry, run_id: str, query: str, output_dir: Path) -> tuple[list[dict], dict, dict[str, dict]]:
    manifest, by_original = [], {}
    methods = Counter()
    for paper in papers:
        record = registry.resolve_or_create(paper, run_id, query)
        identity, bibliography = record.identity, record.bibliographic
        original = str(paper.get("paper_id") or paper.get("pmcid") or paper.get("pmid") or record.canonical_paper_id)
        duplicate = bool(identity.duplicate_of)
        method = identity.duplicate_resolution_method or "new_identity"
        methods[method] += 1
        item = {"run_id": run_id, "query": query, "original_paper_id": original, "paper_id": original, "canonical_paper_id": record.canonical_paper_id, "canonical_paper_key": record.canonical_paper_key, "dedup_status": "duplicate" if duplicate else ("possible_duplicate" if any("possible_duplicate" in warning for warning in identity.warnings) else "new"), "dedup_method": method, "identity_confidence": identity.identity_confidence, "pmid": bibliography.pmid, "pmcid": bibliography.pmcid, "doi": bibliography.doi, "title": bibliography.title, "journal": bibliography.journal, "publication_year": bibliography.publication_year, "publication_date": bibliography.publication_date, "first_author": bibliography.first_author, "authors": bibliography.authors, "abstract_hash": record.abstract_hash, "fulltext_hash": record.fulltext_hash, "sections_hash": record.sections_hash, "abstract_available": record.abstract_available, "fulltext_available": record.fulltext_available, "source_database": bibliography.source_database, "source_url": bibliography.source_url, "warnings": record.warnings}
        manifest.append(item)
        by_original[original] = item
    report = {"total_input_papers": len(papers), "new_papers": sum(item["dedup_status"] == "new" for item in manifest), "duplicate_papers": sum(item["dedup_status"] == "duplicate" for item in manifest), "doi_matches": methods["doi_exact"], "pmid_matches": methods["pmid_exact"], "pmcid_matches": methods["pmcid_exact"], "title_hash_matches": methods["title_year_first_author_exact"], "possible_duplicates": sum(item["dedup_status"] == "possible_duplicate" for item in manifest), "missing_doi_count": sum(not item.get("doi") for item in manifest), "missing_journal_count": sum(not item.get("journal") for item in manifest)}
    output = Path(output_dir)
    atomic_write_jsonl(output / "run_paper_manifest.jsonl", iter(manifest))
    atomic_write_json(output / "run_bibliographic_index.json", {item["canonical_paper_id"]: {key: item.get(key) for key in ("doi", "pmid", "pmcid", "title", "journal", "publication_year")} for item in manifest})
    atomic_write_json(output / "paper_deduplication_report.json", report)
    return manifest, report, by_original


__all__ = ["build_run_paper_manifest"]
