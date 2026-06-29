"""Deterministic paper identity normalization and conservative deduplication."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Iterable

from code_engine.corpus.models import PaperIdentity, PaperRegistryRecord


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    value = str(doi).strip().casefold()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)", "", value)
    value = value.strip().rstrip(".,;)")
    return value or None


def normalize_pmid(pmid: str | None) -> str | None:
    if not pmid:
        return None
    value = re.sub(r"^pmid\s*:\s*", "", str(pmid).strip(), flags=re.I)
    digits = re.sub(r"\D", "", value)
    return digits or None


def normalize_pmcid(pmcid: str | None) -> str | None:
    if not pmcid:
        return None
    value = re.sub(r"[^a-zA-Z0-9]", "", str(pmcid)).upper()
    if value and not value.startswith("PMC") and value.isdigit():
        value = "PMC" + value
    return value or None


def normalize_title(title: str | None) -> str | None:
    if not title:
        return None
    value = unicodedata.normalize("NFKC", str(title)).casefold()
    value = re.sub(r"(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)10\.\S+", " ", value)
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def _sha(value: str | None) -> str | None:
    return hashlib.sha256(value.encode()).hexdigest() if value else None


def compute_title_hash(title: str | None) -> str | None:
    return _sha(normalize_title(title))


def compute_title_year_author_hash(title, year, first_author) -> str | None:
    normalized = normalize_title(title)
    if not normalized or not year or not first_author:
        return None
    author = re.sub(r"\s+", " ", str(first_author).casefold()).strip()
    return _sha(f"{normalized}|{year}|{author}")


def build_canonical_paper_key(metadata: dict) -> str:
    doi = normalize_doi(metadata.get("doi"))
    pmid = normalize_pmid(metadata.get("pmid"))
    pmcid = normalize_pmcid(metadata.get("pmcid"))
    authors = metadata.get("authors") or []
    first_author = metadata.get("first_author") or (authors[0] if authors else None)
    year = metadata.get("publication_year") or metadata.get("year")
    title_author = compute_title_year_author_hash(metadata.get("title"), year, first_author)
    title_hash = compute_title_hash(metadata.get("title"))
    if doi:
        return f"doi:{doi}"
    if pmid:
        return f"pmid:{pmid}"
    if pmcid:
        return f"pmcid:{pmcid}"
    if title_author:
        return f"title_year_author:{title_author}"
    if title_hash:
        return f"title:{title_hash}"
    fallback = "|".join(str(metadata.get(key) or "") for key in ("paper_id", "source", "source_url"))
    return f"unresolved:{_sha(fallback) or _sha('missing-paper-identity')}"


def resolve_paper_identity(metadata: dict, existing_records: Iterable[PaperRegistryRecord]) -> PaperIdentity:
    doi, pmid, pmcid = normalize_doi(metadata.get("doi")), normalize_pmid(metadata.get("pmid")), normalize_pmcid(metadata.get("pmcid"))
    title_hash = compute_title_hash(metadata.get("title"))
    authors = metadata.get("authors") or []
    first_author = metadata.get("first_author") or (authors[0] if authors else None)
    title_author = compute_title_year_author_hash(metadata.get("title"), metadata.get("publication_year") or metadata.get("year"), first_author)
    possible_duplicate = None
    for record in existing_records:
        identity = record.identity
        method, confidence = None, 0.0
        if doi and identity.normalized_doi == doi:
            method, confidence = "doi_exact", 1.0
        elif pmid and identity.pmid == pmid:
            method, confidence = "pmid_exact", 0.98
        elif pmcid and identity.pmcid == pmcid:
            method, confidence = "pmcid_exact", 0.97
        elif title_author and identity.title_year_author_hash == title_author:
            method, confidence = "title_year_first_author_exact", 0.9
        elif title_hash and identity.normalized_title_hash == title_hash:
            possible_duplicate = record.canonical_paper_id
            continue
        if method:
            return PaperIdentity(canonical_paper_id=record.canonical_paper_id, canonical_paper_key=record.canonical_paper_key, identity_confidence=confidence, pmid=pmid, pmcid=pmcid, doi=metadata.get("doi"), normalized_doi=doi, normalized_title_hash=title_hash, title_year_author_hash=title_author, duplicate_of=record.canonical_paper_id, duplicate_resolution_method=method)
    key = build_canonical_paper_key(metadata)
    if possible_duplicate and key.startswith("title:"):
        discriminator = "|".join(str(metadata.get(name) or "") for name in ("paper_id", "source", "source_url"))
        key = f"possible_duplicate:{title_hash}:{_sha(discriminator) or _sha(json.dumps(metadata, sort_keys=True, ensure_ascii=False, default=str))}"
    canonical_id = "PAPER_" + hashlib.sha256(key.encode()).hexdigest()[:20]
    warnings = []
    if possible_duplicate:
        warnings.append(f"possible_duplicate_title_only:{possible_duplicate}")
    if not doi:
        warnings.append("missing_doi")
    if not title_hash:
        warnings.append("missing_title")
    confidence = 1.0 if doi else 0.95 if pmid else 0.93 if pmcid else 0.75 if title_author else 0.4 if title_hash else 0.2
    return PaperIdentity(canonical_paper_id=canonical_id, canonical_paper_key=key, identity_confidence=confidence, pmid=pmid, pmcid=pmcid, doi=metadata.get("doi"), normalized_doi=doi, normalized_title_hash=title_hash, title_year_author_hash=title_author, warnings=warnings)


__all__ = ["normalize_doi", "normalize_pmid", "normalize_pmcid", "normalize_title", "compute_title_hash", "compute_title_year_author_hash", "build_canonical_paper_key", "resolve_paper_identity"]
