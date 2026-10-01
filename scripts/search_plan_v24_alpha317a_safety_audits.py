#!/usr/bin/env python3
"""Frozen, source-independent lexical-leakage and anchor-firewall checks."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path


FORBIDDEN_KEYS = frozenset({
    "pmid", "pmcid", "doi", "sourcearticlehash", "sourcetitle", "sourceevidencespan",
    "sourcerecordtoken", "buildersourceprovenance", "sourcearticle", "sourcetoken",
})
SOURCE_IDENTIFIER = re.compile(r"\bPMC[0-9]+\b|\b10\.[0-9]{4,9}/[^\s\"<>]+", re.I)


def tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)


def leakage_failed(proposition: str, title: str, evidence_sentence: str) -> bool:
    candidate = tokens(proposition)
    for source in (title, evidence_sentence):
        other = tokens(source)
        if len(candidate) >= 8 and len(other) >= 8:
            windows = {tuple(other[i:i + 8]) for i in range(len(other) - 7)}
            if any(tuple(candidate[i:i + 8]) in windows for i in range(len(candidate) - 7)):
                return True
            a, b = set(candidate), set(other)
            if len(a & b) / len(a | b) >= 0.80:
                return True
    return False


def audit_search_plan_inputs(public_root: Path, anchor_root: Path,
                             provenance_root: Path, inputs: list[Path]) -> None:
    """Raise ValueError before any restricted artifact reaches a Search Plan input."""
    public = public_root.resolve(strict=True)
    anchor = anchor_root.resolve(strict=True)
    provenance = provenance_root.resolve(strict=True)
    if len({public, anchor, provenance}) != 3 or any(
        a == b or a in b.parents or b in a.parents
        for a, b in ((public, anchor), (public, provenance), (anchor, provenance))
    ):
        raise ValueError("artifact classes must be physically disjoint")
    for candidate in inputs:
        if candidate.is_symlink() or any(part.is_symlink() for part in candidate.parents):
            raise ValueError("symlink in Search Plan input path")
        actual = candidate.resolve(strict=True)
        if public not in actual.parents or not actual.is_file() or actual.stat().st_nlink != 1:
            raise ValueError("Search Plan input is not a regular, unlinked public-pool file")
        if anchor in actual.parents or provenance in actual.parents:
            raise ValueError("restricted artifact exposed")
        document = json.loads(actual.read_text(encoding="utf-8"))
        def walk(value: object) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
                    if normalized in FORBIDDEN_KEYS:
                        raise ValueError("restricted source-identity field exposed")
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
            elif isinstance(value, str):
                if SOURCE_IDENTIFIER.search(value) or str(anchor) in value or str(provenance) in value:
                    raise ValueError("restricted source identity or path exposed")
        walk(document)
