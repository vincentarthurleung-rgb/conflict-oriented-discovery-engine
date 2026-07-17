"""Configuration-driven annotation schema registry."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFINITIONS_DIR = Path(__file__).parent / "definitions"

ITEM_TYPE_SCHEMA_MAP = {
    "claim": "claim_review_v1",
    "fulltext_l1_claim": "claim_review_v1",
    "fulltext_reviewable_observation": "claim_review_v1",
    "abstract_reviewable_observation": "claim_review_v1",
    "conflict_pair": "conflict_pair_v1",
    "non_comparable_direction_pair": "conflict_pair_v1",
    "weak_candidate": "conflict_pair_v1",
    "context_attribution": "context_attribution_v1",
    "context": "context_attribution_v1",
    "hypothesis": "hypothesis_expert_v1",
    "formal_hypothesis": "hypothesis_expert_v1",
    "forward_validation": "forward_validation_v1",
    "source_unit_claim_gold": "source_unit_claim_gold_v1",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def schema_hash(definition: dict) -> str:
    return hashlib.sha256(canonical_json(definition).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AnnotationSchema:
    schema_id: str
    version: str
    definition: dict
    sha256: str

    @property
    def instructions_version(self) -> str:
        return str(self.definition.get("instructions_version") or "")

    @property
    def instructions_hash(self) -> str:
        return str(self.definition.get("instructions_hash") or "")

    def form_definition(self) -> dict:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.version,
            "schema_hash": self.sha256,
            "title": self.definition.get("title", self.schema_id),
            "description": self.definition.get("description", ""),
            "fields": self.definition.get("fields", []),
            "skip_options": self.definition.get("skip_options", []),
            "instructions_version": self.instructions_version,
            "instructions_hash": self.instructions_hash,
            "frozen": bool(self.definition.get("frozen", False)),
        }


@lru_cache(maxsize=None)
def get_schema(schema_id: str) -> AnnotationSchema:
    path = DEFINITIONS_DIR / f"{schema_id}.json"
    if not path.is_file():
        raise KeyError(f"annotation_schema_not_found:{schema_id}")
    definition = json.loads(path.read_text(encoding="utf-8"))
    if definition.get("schema_id") != schema_id:
        raise ValueError(f"schema_id_mismatch:{schema_id}")
    return AnnotationSchema(
        schema_id=schema_id,
        version=str(definition.get("version") or ""),
        definition=definition,
        sha256=schema_hash(definition),
    )


def schema_for_item_type(item_type: str) -> AnnotationSchema | None:
    schema_id = ITEM_TYPE_SCHEMA_MAP.get(str(item_type or "").strip())
    return get_schema(schema_id) if schema_id else None


def all_schemas() -> list[AnnotationSchema]:
    return [get_schema(path.stem) for path in sorted(DEFINITIONS_DIR.glob("*.json"))]
