"""Conservative entity-type classification with registry precedence."""

from __future__ import annotations

from typing import Any


TYPE_RULES = {
    "metabolite": {"norketamine", "nor-ketamine", "hydroxynorketamine", "h n k"},
    "compound": {"ketamine", "racemic ketamine", "esketamine", "arketamine", "ketamine hydrochloride", "ketamine hcl"},
    "gene": {"bdnf", "ntrk2", "trkb", "gria1", "glua1", "grin2b", "glun2b", "grin1", "glun1", "mtor", "camk2a", "eif4ebp1", "rps6kb1"},
    "receptor_complex": {"ampa receptor", "nmda receptor"},
    "protein_complex": {"mtorc1"},
    "pathway": {"mtor signaling", "bdnf signaling", "bdnf-trkb signaling", "glutamatergic signaling"},
    "biological_process": {"synaptogenesis", "synaptic plasticity", "dendritic spine formation"},
    "clinical_outcome": {"antidepressant response"},
    "phenotype": {"depression-like behavior", "immobility", "sucrose preference"},
    "disease": {"depression"},
    "behavioral_assay": {"forced swim test", "tail suspension test", "sucrose preference test", "fst", "tst"},
    "brain_region": {"prefrontal cortex", "hippocampus"},
    "context": {"hypoxia", "normoxia", "acute", "chronic", "acute treatment", "chronic treatment"},
}


def classify_entity_type(raw_text: str, normalized_surface: str, registry_candidates: list[Any] | None = None) -> str:
    if registry_candidates:
        candidate_types = {getattr(item, "entity_type", None) or item.get("entity_type") for item in registry_candidates}
        candidate_types.discard(None)
        if len(candidate_types) == 1:
            return next(iter(candidate_types))
    surface = str(normalized_surface or raw_text).casefold().strip()
    for entity_type, terms in TYPE_RULES.items():
        if surface in terms:
            return entity_type
    return "unknown"


def infer_entity_type(value: str) -> str:
    return classify_entity_type(value, str(value).casefold())
