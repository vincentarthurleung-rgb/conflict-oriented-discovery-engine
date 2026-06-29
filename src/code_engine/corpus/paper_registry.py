"""Atomic JSONL paper registry with conservative identity resolution."""

from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.corpus.bibliographic_index import BibliographicIndex
from code_engine.corpus.corpus_cache import compute_sections_hash, compute_text_hash
from code_engine.corpus.identity import normalize_title, resolve_paper_identity
from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl, iter_jsonl
from code_engine.corpus.models import BibliographicMetadata, PaperRegistryRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PaperRegistry:
    def __init__(self, registry_dir: Path, records: list[PaperRegistryRecord] | None = None, warnings: list[str] | None = None, allow_title_hash_merge: bool = False):
        self.registry_dir = Path(registry_dir)
        self.records = {record.canonical_paper_id: record for record in (records or [])}
        self.warnings = warnings or []
        self.duplicate_audit: list[dict[str, Any]] = []
        self.allow_title_hash_merge = allow_title_hash_merge
        self.index = BibliographicIndex(self.records.values())

    @classmethod
    def load(cls, registry_dir: Path, allow_title_hash_merge: bool = False) -> "PaperRegistry":
        path = Path(registry_dir) / "paper_registry.jsonl"
        records, warnings = [], []
        try:
            records = [PaperRegistryRecord.model_validate(item) for item in iter_jsonl(path)]
        except (ValueError, OSError) as exc:
            warnings.append(f"paper_registry_corrupt:{type(exc).__name__}:{exc}")
        return cls(Path(registry_dir), records, warnings, allow_title_hash_merge)

    def save(self) -> None:
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        ordered = sorted(self.records.values(), key=lambda item: item.canonical_paper_id)
        atomic_write_jsonl(self.registry_dir / "paper_registry.jsonl", (item.model_dump(mode="json") for item in ordered))
        atomic_write_json(self.registry_dir / "paper_registry_summary.json", {"paper_count": len(ordered), "warning_count": len(self.warnings), "warnings": self.warnings})
        atomic_write_jsonl(self.registry_dir / "duplicate_resolution_audit.jsonl", iter(self.duplicate_audit))

    def resolve_or_create(self, paper_payload: dict, run_id: str, query: str | None = None) -> PaperRegistryRecord:
        identity = resolve_paper_identity(paper_payload, self.records.values())
        if self.allow_title_hash_merge:
            possible = next((warning.split(":", 1)[1] for warning in identity.warnings if warning.startswith("possible_duplicate_title_only:")), None)
            target = self.records.get(possible or "")
            if target:
                identity.canonical_paper_id = target.canonical_paper_id
                identity.canonical_paper_key = target.canonical_paper_key
                identity.duplicate_of = target.canonical_paper_id
                identity.duplicate_resolution_method = "title_hash_explicit_policy"
                identity.identity_confidence = 0.6
        now = _now()
        existing = self.records.get(identity.canonical_paper_id)
        if existing:
            existing.last_seen_run_id = run_id
            existing.seen_count += 1
            if query and query not in existing.seen_in_queries:
                existing.seen_in_queries.append(query)
            prompt = paper_payload.get("prompt_id")
            if prompt and str(prompt) not in existing.seen_in_prompt_ids:
                existing.seen_in_prompt_ids.append(str(prompt))
            existing.updated_at = now
            bibliography = existing.bibliographic
            incoming = {
                "title": paper_payload.get("title"), "journal": paper_payload.get("journal") or paper_payload.get("journal_title"),
                "publication_year": paper_payload.get("publication_year") or paper_payload.get("year"),
                "publication_date": paper_payload.get("publication_date"), "doi": paper_payload.get("doi"),
                "pmid": identity.pmid, "pmcid": identity.pmcid, "source_database": paper_payload.get("source_database") or paper_payload.get("source"),
                "source_url": paper_payload.get("source_url"),
            }
            for field, value in incoming.items():
                if getattr(bibliography, field) in (None, "") and value not in (None, ""):
                    setattr(bibliography, field, value)
            if not bibliography.authors and paper_payload.get("authors"):
                bibliography.authors = [str(item) for item in paper_payload["authors"]]
                bibliography.first_author = paper_payload.get("first_author") or bibliography.authors[0]
            if not existing.identity.normalized_doi and identity.normalized_doi:
                existing.identity.normalized_doi = identity.normalized_doi
                existing.identity.doi = identity.doi
                existing.warnings = [warning for warning in existing.warnings if warning != "missing_doi"]
                bibliography.warnings = [warning for warning in bibliography.warnings if warning != "missing_doi"]
            if bibliography.journal:
                existing.warnings = [warning for warning in existing.warnings if warning != "missing_journal"]
                bibliography.warnings = [warning for warning in bibliography.warnings if warning != "missing_journal"]
            self.duplicate_audit.append({"canonical_paper_id": existing.canonical_paper_id, "duplicate_of": identity.duplicate_of, "method": identity.duplicate_resolution_method, "confidence": identity.identity_confidence, "run_id": run_id})
            self.update_content_hashes(existing.canonical_paper_id, paper_payload.get("abstract"), paper_payload.get("full_text"), paper_payload.get("sections"))
            self.index.add(existing)
            return existing
        authors = [str(item) for item in paper_payload.get("authors", [])]
        first_author = paper_payload.get("first_author") or (authors[0] if authors else None)
        warnings = list(identity.warnings)
        journal = paper_payload.get("journal") or paper_payload.get("journal_title")
        if not journal:
            warnings.append("missing_journal")
        quality_fields = [paper_payload.get("title"), journal, paper_payload.get("year") or paper_payload.get("publication_year"), identity.normalized_doi or identity.pmid or identity.pmcid]
        bibliography = BibliographicMetadata(canonical_paper_id=identity.canonical_paper_id, title=paper_payload.get("title"), normalized_title=normalize_title(paper_payload.get("title")), journal=journal, journal_iso=paper_payload.get("journal_iso"), publication_year=paper_payload.get("publication_year") or paper_payload.get("year"), publication_date=paper_payload.get("publication_date"), authors=authors, first_author=first_author, doi=paper_payload.get("doi"), pmid=identity.pmid, pmcid=identity.pmcid, publication_type=paper_payload.get("publication_type"), source_database=paper_payload.get("source_database") or paper_payload.get("source"), source_url=paper_payload.get("source_url"), citation_string=paper_payload.get("citation_string"), metadata_quality=round(sum(value not in (None, "", []) for value in quality_fields) / len(quality_fields), 4), warnings=warnings)
        record = PaperRegistryRecord(canonical_paper_id=identity.canonical_paper_id, canonical_paper_key=identity.canonical_paper_key, identity=identity, bibliographic=bibliography, first_seen_run_id=run_id, last_seen_run_id=run_id, seen_in_queries=[query] if query else [], seen_in_prompt_ids=[str(paper_payload["prompt_id"])] if paper_payload.get("prompt_id") else [], seen_count=1, created_at=now, updated_at=now, warnings=warnings)
        self.records[record.canonical_paper_id] = record
        self.index.add(record)
        self.update_content_hashes(record.canonical_paper_id, paper_payload.get("abstract"), paper_payload.get("full_text"), paper_payload.get("sections"))
        return record

    def update_content_hashes(self, canonical_paper_id: str, abstract: str | None, fulltext: str | None, sections: list[dict] | None = None) -> None:
        record = self.records[canonical_paper_id]
        if abstract is not None:
            record.abstract_hash = compute_text_hash(abstract)
            record.abstract_available = bool(record.abstract_hash)
        if fulltext is not None:
            record.fulltext_hash = compute_text_hash(fulltext)
            record.fulltext_available = bool(record.fulltext_hash)
        if sections is not None:
            record.sections_hash = compute_sections_hash(sections)
            record.fulltext_available = record.fulltext_available or bool(record.sections_hash)
        record.updated_at = _now()

    def mark_processing_status(self, canonical_paper_id: str, task_key: str, status: str, artifact_refs: dict | None = None) -> None:
        record = self.records[canonical_paper_id]
        record.processing_status[task_key] = status
        if artifact_refs:
            record.artifact_refs[task_key] = artifact_refs
        record.updated_at = _now()

    def get(self, canonical_paper_id: str) -> PaperRegistryRecord | None:
        return self.records.get(canonical_paper_id)

    def find_by_doi(self, doi: str) -> PaperRegistryRecord | None:
        return self.get(self.index.find_doi(doi) or "")

    def find_by_pmid(self, pmid: str) -> PaperRegistryRecord | None:
        return self.get(self.index.find_pmid(pmid) or "")

    def find_by_pmcid(self, pmcid: str) -> PaperRegistryRecord | None:
        return self.get(self.index.find_pmcid(pmcid) or "")

    def lookup_bibliographic(self, canonical_paper_id: str) -> BibliographicMetadata | None:
        record = self.get(canonical_paper_id)
        return record.bibliographic if record else None


__all__ = ["PaperRegistry"]
