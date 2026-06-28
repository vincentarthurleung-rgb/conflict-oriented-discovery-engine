"""Deterministic lexical normalization before biomedical resolution."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


INVALID_SURFACES = {"", "unspecified", "unknown", "none", "n/a", "na", "null"}
GREEK_MAP = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta"}
RECEPTOR_VARIANTS = {"nmdar": "nmda receptor", "ampar": "ampa receptor"}


@dataclass(frozen=True)
class LexicalNormalizationResult:
    raw_text: str
    normalized_surface: str
    warnings: list[str] = field(default_factory=list)
    invalid: bool = False


def normalize_lexical_surface(value: str) -> LexicalNormalizationResult:
    raw = str(value or "")
    surface = unicodedata.normalize("NFKC", raw).strip().lower()
    warnings = []
    for symbol, replacement in GREEK_MAP.items():
        if symbol in surface:
            surface = surface.replace(symbol, f" {replacement} ")
            warnings.append("greek_letter_normalized")
    surface = re.sub(r"[‐‑‒–—−]", "-", surface)
    surface = re.sub(r"[^\w\s()+/.-]", " ", surface)
    surface = re.sub(r"\s+", " ", surface).strip(" .,-_/+")
    if surface in RECEPTOR_VARIANTS:
        surface = RECEPTOR_VARIANTS[surface]
        warnings.append("receptor_abbreviation_expanded")
    invalid = surface in INVALID_SURFACES or surface.startswith("failed_") or surface.startswith("failed ")
    if invalid:
        warnings.append("empty_invalid_or_placeholder")
    return LexicalNormalizationResult(raw_text=raw, normalized_surface=surface, warnings=warnings, invalid=invalid)


def clean_token(value: str) -> str:
    """Backward-compatible string-only lexical helper."""

    return normalize_lexical_surface(value).normalized_surface

