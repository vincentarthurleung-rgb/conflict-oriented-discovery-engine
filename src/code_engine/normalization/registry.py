"""Local curated biomedical registry with deterministic candidate lookup."""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from code_engine.config.validation import validate_entity_registry
from code_engine.normalization.lexical import normalize_lexical_surface
from code_engine.normalization.models import EntityRelation, NormalizationCandidate


DEFAULT_REGISTRY_PATH = Path("configs/normalization/entity_registry.json")
LEGACY_REGISTRY_PATH = Path("config/schemas/entity_registry.json")


BUILTIN_DEMO_REGISTRY = {
    "version": "entity_registry_demo_fallback_v1",
    "description": "Explicit fallback containing only minimal demo entities.",
    "entities": [
        {"canonical_id": "CHEM:KETAMINE", "canonical_name": "ketamine", "entity_type": "compound", "semantic_level": "parent_compound", "aliases": ["ketamine"], "external_ids": {}, "relations": []},
        {"canonical_id": "GENE:BDNF", "canonical_name": "BDNF", "entity_type": "gene", "semantic_level": "gene_or_protein", "aliases": ["BDNF"], "external_ids": {}, "relations": []},
    ],
}


class LocalBiomedicalRegistry:
    def __init__(self, path: str | Path = DEFAULT_REGISTRY_PATH, *, allow_fallback: bool = False):
        requested = Path(path)
        self.warnings: list[str] = []
        if requested.exists():
            active_path = requested
            payload = json.loads(active_path.read_text(encoding="utf-8"))
        elif requested == DEFAULT_REGISTRY_PATH and LEGACY_REGISTRY_PATH.exists():
            active_path = LEGACY_REGISTRY_PATH
            payload = json.loads(active_path.read_text(encoding="utf-8"))
            self.warnings.append("preferred_registry_missing_legacy_registry_used")
        elif allow_fallback:
            active_path = Path("builtin_demo_registry")
            payload = BUILTIN_DEMO_REGISTRY
            self.warnings.append("registry_missing_builtin_demo_fallback_used")
        else:
            raise FileNotFoundError(f"Biomedical entity registry missing: {requested}")
        self.path = active_path
        self.payload = payload
        self.warnings.extend(validate_entity_registry(payload))
        self.entities = list(payload["entities"])
        self.canonical_index: dict[str, list[dict[str, Any]]] = {}
        self.alias_index: dict[str, list[dict[str, Any]]] = {}
        for entity in self.entities:
            canonical_surface = normalize_lexical_surface(entity["canonical_name"]).normalized_surface
            self.canonical_index.setdefault(canonical_surface, []).append(entity)
            for alias in entity.get("aliases", []):
                alias_surface = normalize_lexical_surface(alias).normalized_surface
                self.alias_index.setdefault(alias_surface, []).append(entity)

    @staticmethod
    def _candidate(entity: dict[str, Any], score: float, match_type: str, warnings: list[str] | None = None) -> NormalizationCandidate:
        return NormalizationCandidate(
            canonical_id=entity["canonical_id"],
            canonical_name=entity["canonical_name"],
            entity_type=entity["entity_type"],
            semantic_level=entity["semantic_level"],
            aliases=list(entity.get("aliases", [])),
            external_ids=dict(entity.get("external_ids", {})),
            relations=[EntityRelation.model_validate(relation) for relation in entity.get("relations", [])],
            score=score,
            source="local_curated_registry",
            match_type=match_type,
            warnings=warnings or [],
        )

    def lookup(self, raw_text: str, normalized_surface: str) -> list[NormalizationCandidate]:
        raw_surface = str(raw_text).strip().casefold()
        if normalized_surface in self.canonical_index:
            match_type = "registry_exact" if raw_surface == normalized_surface else "lexical_normalized_exact"
            return [self._candidate(entity, 1.0, match_type) for entity in self.canonical_index[normalized_surface]]
        if normalized_surface in self.alias_index:
            candidates = self.alias_index[normalized_surface]
            match_type = "case_insensitive_exact" if any(raw_text == alias for entity in candidates for alias in entity.get("aliases", [])) else "alias_exact"
            ambiguity = ["duplicate_alias_in_registry"] if len({entity["canonical_id"] for entity in candidates}) > 1 else []
            return [self._candidate(entity, 0.97, match_type, ambiguity) for entity in candidates]
        fuzzy = []
        for surface in set(self.canonical_index) | set(self.alias_index):
            score = SequenceMatcher(None, normalized_surface, surface).ratio()
            if score >= 0.84:
                for entity in self.canonical_index.get(surface, []) + self.alias_index.get(surface, []):
                    fuzzy.append(self._candidate(entity, round(score * 0.8, 4), "fuzzy_candidate", ["fuzzy_match_requires_review"]))
        by_id = {}
        for candidate in fuzzy:
            if candidate.canonical_id not in by_id or candidate.score > by_id[candidate.canonical_id].score:
                by_id[candidate.canonical_id] = candidate
        return sorted(by_id.values(), key=lambda item: (-item.score, item.canonical_id))[:5]

