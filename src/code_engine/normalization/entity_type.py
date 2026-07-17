"""Generic weak entity-type candidate inference.

No pilot entity dictionary lives here. Hints are candidates, never canonical
identity decisions.
"""

from __future__ import annotations

import re
from typing import Any

CANONICAL_ENTITY_TYPES: tuple[str, ...] = (
    "gene",
    "gene_or_protein",
    "protein",
    "protein_family",
    "protein_complex",
    "receptor",
    "enzyme",
    "drug",
    "compound",
    "metabolite",
    "pathway",
    "biological_process",
    "disease",
    "phenotype",
    "cell_type",
    "cell_line",
    "tissue",
    "organ",
    "clinical_outcome",
    "assay",
    "assay_readout",
    "unknown",
)

TYPE_ALIASES: dict[str, str] = {
    "molecular_endpoint": "assay_readout",
    "compound_or_biomolecule": "compound",
    "receptor_complex": "receptor",
    "behavioral_assay": "assay",
    "treatment": "unknown",
    "experimental_condition": "unknown",
    "context": "unknown",
}

ONTOLOGY_RESOLVABLE_TYPES = {
    "biological_process",
    "pathway",
    "disease",
    "phenotype",
    "compound",
    "metabolite",
    "cell_type",
    "cell_line",
    "tissue",
    "organ",
}

STRUCTURED_ATTRIBUTE_TYPES = {
    "assay",
    "assay_readout",
    "clinical_outcome",
}

GENE_PROTEIN_COMPATIBLE_TYPES = {"gene", "protein", "gene_or_protein", "receptor", "enzyme"}


def compatible_entity_types(entity_type: str | None) -> list[str]:
    value = canonical_entity_type(entity_type)
    if value == "gene_or_protein":
        return ["gene", "protein"]
    if value == "protein_family":
        return ["protein_family", "protein"]
    if value == "protein_complex":
        return ["protein_complex", "protein"]
    if value == "receptor":
        return ["receptor", "protein"]
    if value == "enzyme":
        return ["enzyme", "protein", "gene"]
    return [] if value == "unknown" else [value]


def detect_measurement_dimension(value: str) -> str | None:
    text = str(value or "").casefold()
    if any(term in text for term in ("mrna", "transcript", "qpcr", "rt-pcr", "real-time pcr", "rna-seq", "rna seq")):
        return "mRNA expression"
    if any(term in text for term in ("protein level", "protein expression", "western blot", "immunoblot", "immunohistochemistry", "elisa")):
        return "protein level"
    if "expression" in text or "level" in text or "levels" in text:
        return "expression"
    if "activation" in text or "activity" in text or "phosphorylation" in text:
        return "activation"
    return None


def refine_type_for_cleaned_mention(raw_text: str, cleaned_surface: str, *, original_entity_type: str | None = None,
                                    structured_entity_type: str | None = None, cleaner_suggested_type: str | None = None,
                                    context_text: str | None = None) -> dict[str, Any]:
    original = canonical_entity_type(original_entity_type)
    structured = canonical_entity_type(structured_entity_type)
    suggested = canonical_entity_type(cleaner_suggested_type)
    combined = " ".join(str(x or "") for x in (raw_text, cleaned_surface, context_text))
    measurement = detect_measurement_dimension(combined)
    lower_cleaned = str(cleaned_surface or "").casefold()

    deterministic = "unknown"
    method = "unknown"
    if "pathway" in lower_cleaned or "signaling" in lower_cleaned or "signalling" in lower_cleaned:
        deterministic, method = "pathway", "deterministic_alias_type_inference"
    elif measurement == "mRNA expression":
        deterministic, method = "gene", "assay_context_refinement"
    elif measurement == "protein level":
        deterministic, method = "protein", "assay_context_refinement"
    elif measurement == "expression" and original in {"assay", "assay_readout", "unknown"}:
        deterministic, method = "gene_or_protein", "assay_context_refinement"
    elif any(token in lower_cleaned for token in ("tgf-β", "tgf-beta", "tgfb")) and lower_cleaned in {"tgf-β", "tgf-beta", "tgfb", "transforming growth factor beta"}:
        deterministic, method = "protein_family", "deterministic_alias_type_inference"

    priority: list[tuple[str, str]] = []
    if original not in {"unknown", "assay", "assay_readout", "clinical_outcome"}:
        priority.append((original, "original_expected_entity_type"))
    if structured not in {"unknown", "assay", "assay_readout", "clinical_outcome"}:
        priority.append((structured, "structured_field_type"))
    if deterministic != "unknown":
        priority.append((deterministic, method))
    if original in {"assay", "assay_readout"} and deterministic != "unknown":
        priority.insert(0, (deterministic, method))
    if suggested != "unknown":
        priority.append((suggested, "llm_cleaner_type_suggestion"))

    final_type, final_method = priority[0] if priority else ("unknown", "unknown")
    higher = {t for t, m in priority if m != "llm_cleaner_type_suggestion"}
    conflict = bool(suggested != "unknown" and higher and suggested not in higher and final_type != suggested)
    if conflict and final_type not in GENE_PROTEIN_COMPATIBLE_TYPES.union({"pathway", "protein_family", "protein_complex"}):
        final_type, final_method = "unknown", "type_conflict_downgraded"
    return {
        "raw_mention": raw_text,
        "cleaned_mention": cleaned_surface,
        "original_entity_type": original,
        "cleaner_suggested_type": suggested,
        "final_expected_entity_type": final_type,
        "type_resolution_method": final_method,
        "type_conflict": conflict,
        "measurement_dimension": measurement,
    }


def canonical_entity_type(entity_type: str | None) -> str:
    value = str(entity_type or "unknown").strip().casefold()
    value = TYPE_ALIASES.get(value, value)
    return value if value in CANONICAL_ENTITY_TYPES else "unknown"


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
