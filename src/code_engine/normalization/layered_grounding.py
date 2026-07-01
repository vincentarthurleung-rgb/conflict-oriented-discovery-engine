"""Run-local entity hints and layered L2 evidence retention decisions."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimeEntityHint:
    name: str
    aliases: tuple[str, ...]
    entity_type: str | None
    role: str
    source: str
    confidence: float

    @property
    def canonical_id(self) -> str:
        return "RUN:" + hashlib.sha256(f"{self.role}|{self.name.casefold()}".encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "aliases": list(self.aliases), "canonical_id": self.canonical_id,
                "curated": False, "used_for_core_graph": self.role in {"seed_subject", "seed_object"}}


PROCESS_PATTERNS = (
    (r"\bactivation of\s+(.+)$", "process_about_entity"),
    (r"\blow activity of\s+(.+)$", "activity_state_about_entity"),
    (r"\b(.+?)\s+(activation|expression|signaling|pathway|activity)$", "process_about_entity"),
)


def normalize_mention(value: str) -> str:
    return " ".join(re.sub(r"[^\w\s/-]", " ", str(value).casefold()).split())


def load_runtime_entity_hints(run_dir: str | Path) -> list[RuntimeEntityHint]:
    root = Path(run_dir); artifacts = root / "artifacts"
    intent_path = artifacts / "semantic_search_intent.json"
    intake_path = artifacts / "intake.json"
    payload = json.loads(intent_path.read_text(encoding="utf-8")) if intent_path.exists() else {}
    source = "semantic_search_intent"
    seed = payload.get("seed_triple") or {}
    if not seed and intake_path.exists():
        seed = json.loads(intake_path.read_text(encoding="utf-8")).get("unified_seed_triple") or {}
        source = "seed_triple"
    hints = []
    for field, role in (("subject", "seed_subject"), ("object", "seed_object")):
        entity = seed.get(field) or {}; name = str(entity.get("name") or "").strip()
        if name:
            aliases = tuple(dict.fromkeys([name, *(str(x) for x in entity.get("aliases") or [])]))
            hints.append(RuntimeEntityHint(name, aliases, entity.get("type"), role, source, 0.95))
    context = seed.get("context") or {}
    for term in context.get("terms") or context.get("context_terms") or []:
        if str(term).strip():
            hints.append(RuntimeEntityHint(str(term), (str(term),), "context", "context", source, 0.8))
    return hints


def match_runtime_hint(mention: str, hints: list[RuntimeEntityHint]) -> dict[str, Any] | None:
    normalized = normalize_mention(mention)
    best = None
    for hint in hints:
        for alias in hint.aliases:
            target = normalize_mention(alias)
            exact = normalized == target
            contained = bool(target and re.search(r"(?<!\w)" + re.escape(target) + r"(?!\w)", normalized))
            if not (exact or contained):
                continue
            role = "entity"
            if not exact:
                role = "process_about_entity"
                for pattern, label in PROCESS_PATTERNS:
                    if re.search(pattern, normalized): role = label; break
            score = hint.confidence if exact else min(0.88, hint.confidence - 0.07)
            candidate = {"canonical_name": hint.name, "canonical_id": hint.canonical_id,
                         "entity_type": hint.entity_type or "unknown", "role": hint.role,
                         "source": "runtime_hint", "match_type": "exact_alias" if exact else "alias_substring_or_pattern",
                         "mention_role": role, "score": round(score, 3), "hint_source": hint.source}
            if best is None or candidate["score"] > best["score"]: best = candidate
    return best


def decide_l2_evidence_layer(item: dict[str, Any], subject_resolution: Any, object_resolution: Any,
                             subject_hint: dict[str, Any] | None, object_hint: dict[str, Any] | None,
                             hints: list[RuntimeEntityHint]) -> dict[str, Any]:
    sentence = str(item.get("evidence_sentence") or "")
    combined = " ".join((str(item.get("subject_raw") or ""), str(item.get("object_raw") or ""), sentence)).casefold()
    roles = {hint.role: hint for hint in hints}
    subject_seed = roles.get("seed_subject"); object_seed = roles.get("seed_object")
    subject_mentioned = bool(subject_seed and any(normalize_mention(alias) in normalize_mention(combined) for alias in subject_seed.aliases))
    object_mentioned = bool(object_seed and any(normalize_mention(alias) in normalize_mention(combined) for alias in object_seed.aliases))
    context_mentioned = any(h.role == "context" and normalize_mention(h.name) in normalize_mention(combined) for h in hints)
    seed_score = round((0.45 * subject_mentioned) + (0.45 * object_mentioned) + (0.1 * context_mentioned), 3)
    strict_subject = bool(subject_resolution.allow_high_confidence_graph_use or (subject_hint and subject_hint["role"] == "seed_subject" and subject_hint["match_type"] == "exact_alias"))
    strict_object = bool(object_resolution.allow_high_confidence_graph_use or (object_hint and object_hint["role"] == "seed_object" and object_hint["match_type"] == "exact_alias"))
    relation_confidence = float(item.get("direction_confidence", item.get("confidence", 0.0)) or 0.0)
    if not sentence.strip():
        layer, retained, reason, excluded = "excluded", False, None, "missing_evidence_sentence"
    elif strict_subject and strict_object and subject_mentioned and object_mentioned:
        layer, retained, reason, excluded = "core_canonical_graph", True, "high_confidence_seed_aligned_canonical_entities", None
    elif subject_mentioned and object_mentioned:
        layer, retained, reason, excluded = "mechanism_layer", True, "seed_subject_and_seed_object_detected_with_mechanistic_relation", None
    elif subject_mentioned and (object_mentioned or "through" in combined or "dependent" in combined):
        layer, retained, reason, excluded = "mechanism_layer", True, "seed_aligned_mechanistic_intermediate", None
    elif context_mentioned:
        layer, retained, reason, excluded = "context_layer", True, "runtime_seed_context_overlap", None
    elif subject_hint or object_hint:
        layer, retained, reason, excluded = "review_layer", True, "partial_runtime_entity_grounding_requires_review", None
    else:
        layer, retained, reason, excluded = "excluded", False, None, "off_seed_relation"
    core = layer == "core_canonical_graph"
    relevance = "direct_seed_relation" if core else "mechanistic_intermediate" if layer == "mechanism_layer" else "context_only" if layer == "context_layer" else "off_seed" if not retained else "unknown"
    return {"retained": retained, "graph_layer": layer, "canonical_graph_eligible": core,
            "seed_alignment_score": seed_score,
            "entity_grounding_score": round((float(subject_resolution.confidence) + float(object_resolution.confidence) + (subject_hint or {}).get("score", 0) + (object_hint or {}).get("score", 0)) / 4, 3),
            "relation_confidence_score": relation_confidence,
            "context_completeness_score": 1.0 if item.get("context") or item.get("context_mentions") or item.get("context_slots") else 0.0,
            "excluded_from_core_reason": None if core else ("object_is_process_or_outcome_not_canonical_entity" if layer == "mechanism_layer" else "not_strict_canonical_seed_relation"),
            "excluded_from_retention_reason": excluded, "retention_reason": reason,
            "computed_seed_subject_mentioned": subject_mentioned, "computed_seed_object_mentioned": object_mentioned,
            "computed_context_mentioned": context_mentioned, "computed_seed_relevance": relevance}


__all__ = ["RuntimeEntityHint", "decide_l2_evidence_layer", "load_runtime_entity_hints", "match_runtime_hint", "normalize_mention"]
