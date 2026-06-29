"""Bounded in-memory indexes over PaperRegistry records."""

from __future__ import annotations
from collections import defaultdict
from typing import Iterable

from code_engine.corpus.identity import normalize_doi, normalize_pmcid, normalize_pmid
from code_engine.corpus.models import PaperRegistryRecord


class BibliographicIndex:
    def __init__(self, records: Iterable[PaperRegistryRecord] = ()):
        self.doi: dict[str, str] = {}
        self.pmid: dict[str, str] = {}
        self.pmcid: dict[str, str] = {}
        self.title_hash: dict[str, list[str]] = defaultdict(list)
        for record in records:
            self.add(record)

    def add(self, record: PaperRegistryRecord) -> None:
        identity = record.identity
        if identity.normalized_doi:
            self.doi[identity.normalized_doi] = record.canonical_paper_id
        if identity.pmid:
            self.pmid[identity.pmid] = record.canonical_paper_id
        if identity.pmcid:
            self.pmcid[identity.pmcid] = record.canonical_paper_id
        if identity.normalized_title_hash and record.canonical_paper_id not in self.title_hash[identity.normalized_title_hash]:
            self.title_hash[identity.normalized_title_hash].append(record.canonical_paper_id)

    def find_doi(self, value: str) -> str | None:
        return self.doi.get(normalize_doi(value) or "")

    def find_pmid(self, value: str) -> str | None:
        return self.pmid.get(normalize_pmid(value) or "")

    def find_pmcid(self, value: str) -> str | None:
        return self.pmcid.get(normalize_pmcid(value) or "")


__all__ = ["BibliographicIndex"]
