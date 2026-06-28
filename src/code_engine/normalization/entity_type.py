"""Generic weak entity-type candidate inference.

No pilot entity dictionary lives here. Hints are candidates, never canonical
identity decisions.
"""

from __future__ import annotations

import re
from typing import Any


def infer_entity_type_candidates(value: str, *, l1_entity_type_hint: str | None = None, provider_candidates: list[Any] | None = None) -> list[dict[str, Any]]:
    ranked: dict[str, dict[str, Any]] = {}

    def add(entity_type: str | None, confidence: float, source: str):
        if not entity_type or entity_type == "unknown":
            return
        current = ranked.get(entity_type)
        if current is None or confidence > current["confidence"]:
            ranked[entity_type] = {"entity_type": entity_type, "confidence": confidence, "source": source}

    add(l1_entity_type_hint, 0.98, "l1_entity_type_hint")
    for candidate in provider_candidates or []:
        getter = candidate.get if isinstance(candidate, dict) else lambda key, default=None: getattr(candidate, key, default)
        entity_type = getter("entity_type")
        if getter("is_grounded", False):
            source = "external_grounded_candidate" if not getter("is_curated", False) else "curated_candidate"
            add(entity_type, 0.92 if source == "external_grounded_candidate" else 0.9, source)
        elif getter("provider_name") == "LocalCacheProvider":
            add(entity_type, 0.88, "accepted_cache_candidate")
        elif getter("is_llm_suggested", False):
            add(entity_type, 0.4, "llm_weak_suggestion")
    text = " ".join(str(value or "").split())
    lowered = text.casefold()
    if re.fullmatch(r"[A-Z][A-Z0-9-]{1,11}", text):
        add("gene", 0.45, "universal_lexical_weak_hint")
        add("protein", 0.4, "universal_lexical_weak_hint")
    if "receptor" in lowered:
        add("receptor_complex", 0.48, "universal_lexical_weak_hint")
    if " complex" in f" {lowered}":
        add("protein_complex", 0.45, "universal_lexical_weak_hint")
    if "signaling" in lowered or "pathway" in lowered:
        add("pathway", 0.48, "universal_lexical_weak_hint")
    if any(term in lowered for term in ("trial", "response", "remission")):
        add("clinical_outcome", 0.4, "universal_lexical_weak_hint")
    if any(term in lowered for term in ("forced swim", "sucrose preference", "tail suspension")) and ("test" in lowered or "assay" in lowered):
        add("behavioral_assay", 0.5, "universal_lexical_weak_hint")
    return sorted(ranked.values(), key=lambda item: (-item["confidence"], item["entity_type"]))


def classify_entity_type(raw_text: str, normalized_surface: str, registry_candidates: list[Any] | None = None) -> str:
    """Compatibility adapter; weak lexical hints never become a final type."""

    candidates = infer_entity_type_candidates(raw_text or normalized_surface, provider_candidates=registry_candidates)
    return candidates[0]["entity_type"] if candidates and candidates[0]["confidence"] >= 0.8 else "unknown"


def infer_entity_type(value: str) -> str:
    return classify_entity_type(value, str(value).casefold())
