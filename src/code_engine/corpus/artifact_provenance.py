"""Compact bibliographic provenance injection for single- and multi-paper records."""

from __future__ import annotations
from collections import Counter

from code_engine.corpus.models import BibliographicMetadata, PaperProvenanceRef
from code_engine.corpus.paper_registry import PaperRegistry


FIELDS = ("canonical_paper_id", "paper_id", "pmid", "pmcid", "doi", "title", "journal", "publication_year")


def attach_bibliographic_summary(record: dict, bibliographic: BibliographicMetadata | None) -> dict:
    output = dict(record)
    warnings = list(output.get("warnings") or [])
    if bibliographic is None:
        warnings.append("bibliographic_metadata_unavailable")
        for field in FIELDS:
            output.setdefault(field, None)
    else:
        output.update({"canonical_paper_id": bibliographic.canonical_paper_id, "pmid": bibliographic.pmid, "pmcid": bibliographic.pmcid, "doi": bibliographic.doi, "title": bibliographic.title, "journal": bibliographic.journal, "publication_year": bibliographic.publication_year})
        output.setdefault("paper_id", record.get("paper_id"))
        warnings.extend(bibliographic.warnings)
    output["warnings"] = list(dict.fromkeys(warnings))
    return output


def attach_paper_provenance(record: dict, registry: PaperRegistry | None, run_manifest: dict | None = None) -> dict:
    canonical = record.get("canonical_paper_id")
    if not canonical and run_manifest:
        original = str(record.get("paper_id") or "")
        manifest_item = run_manifest.get(original) or next((item for item in run_manifest.values() if str(item.get("canonical_paper_id")) == original), None)
        if manifest_item:
            canonical = manifest_item.get("canonical_paper_id")
    bibliography = registry.lookup_bibliographic(str(canonical)) if registry and canonical else None
    if bibliography is None and run_manifest:
        manifest_item = next((item for item in run_manifest.values() if str(item.get("canonical_paper_id")) == str(canonical)), None)
        if manifest_item:
            fields = {key: manifest_item.get(key) for key in ("title", "journal", "publication_year", "publication_date", "authors", "first_author", "doi", "pmid", "pmcid", "source_database", "source_url")}
            fields["authors"] = fields.get("authors") or []
            bibliography = BibliographicMetadata(canonical_paper_id=str(canonical), **fields)
    output = attach_bibliographic_summary({**record, "canonical_paper_id": canonical}, bibliography)
    return output


def build_paper_provenance_ref(record: dict) -> PaperProvenanceRef:
    warnings = []
    if not record.get("doi"):
        warnings.append("missing_doi")
    if not record.get("journal"):
        warnings.append("missing_journal")
    return PaperProvenanceRef(**{field: record.get(field) for field in FIELDS}, warnings=warnings)


def attach_linked_paper_provenance(record: dict, paper_refs: list[dict]) -> dict:
    output = dict(record)
    compact = [build_paper_provenance_ref(item).model_dump(mode="json") for item in paper_refs]
    output["linked_paper_ids"] = list(dict.fromkeys(str(item.get("paper_id")) for item in compact if item.get("paper_id")))
    output["linked_canonical_paper_ids"] = list(dict.fromkeys(str(item.get("canonical_paper_id")) for item in compact if item.get("canonical_paper_id")))
    output["linked_dois"] = list(dict.fromkeys(str(item.get("doi")) for item in compact if item.get("doi")))
    output["linked_titles"] = list(dict.fromkeys(str(item.get("title")) for item in compact if item.get("title")))
    output["linked_journals"] = list(dict.fromkeys(str(item.get("journal")) for item in compact if item.get("journal")))
    output["paper_count"] = len(output["linked_canonical_paper_ids"] or output["linked_paper_ids"])
    output["journal_distribution"] = dict(Counter(item.get("journal") for item in compact if item.get("journal")))
    years = [int(item["publication_year"]) for item in compact if item.get("publication_year")]
    output["publication_year_range"] = {"min": min(years), "max": max(years)} if years else {}
    provenance_warnings = [warning for item in compact for warning in item.get("warnings", [])]
    if provenance_warnings:
        output["warnings"] = list(dict.fromkeys([*output.get("warnings", []), *provenance_warnings]))
    if not compact:
        output["warnings"] = list(dict.fromkeys([*output.get("warnings", []), "linked_bibliographic_metadata_unavailable"]))
    return output


__all__ = ["attach_paper_provenance", "attach_bibliographic_summary", "build_paper_provenance_ref", "attach_linked_paper_provenance"]
