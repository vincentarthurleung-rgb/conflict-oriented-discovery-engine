"""Run-local entity hints and layered L2 evidence retention decisions."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from code_engine.search.context_guard import expand_context_terms


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


@dataclass(frozen=True)
class ContextSourceEvidence:
    source: str
    strength: str
    matched_terms: tuple[str, ...]
    text_excerpt: str | None = None


@dataclass(frozen=True)
class ContextCompatibilityResult:
    score: float
    status: str
    matched_terms: tuple[str, ...]
    missing_terms: tuple[str, ...]
    mismatch_reasons: tuple[str, ...]
    evidence_context_terms: tuple[str, ...]
    abstract_context_terms: tuple[str, ...]
    title_context_terms: tuple[str, ...]
    metadata_context_terms: tuple[str, ...]
    seed_context_terms: tuple[str, ...]
    query_context_terms: tuple[str, ...]
    semantic_intent_context_terms: tuple[str, ...]
    paper_context_terms: tuple[str, ...]
    strong_context_terms_matched: tuple[str, ...]
    weak_context_terms_matched: tuple[str, ...]
    strong_context_match: bool
    weak_context_match: bool
    query_context_only: bool
    core_context_eligible: bool
    context_sources: tuple[ContextSourceEvidence, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key, item in list(value.items()):
            if isinstance(item, tuple): value[key] = list(item)
        return value


@dataclass(frozen=True)
class PredicateAnchorResult:
    anchor_status: str
    seed_predicate_span: str | None
    seed_predicate_direction: str | None
    seed_relation_family: str | None
    sentence_primary_predicate: str | None
    direct_relation_sign: int
    confidence: float
    warnings: tuple[str, ...]
    predicate_direction_consistent: bool

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self); value["warnings"] = list(self.warnings)
        value["predicate_anchor_status"] = value.pop("anchor_status")
        return value


_PREDICATES = {
    "activation": (("activate", "activates", "activated", "activating", "activation", "increase", "increases", "increased"), 1, "activate"),
    "inhibition": (("inhibit", "inhibits", "inhibited", "inhibiting", "inhibition", "suppress", "suppresses", "suppressed"), -1, "inhibit"),
}


def _mentions(text: str, terms: list[str] | tuple[str, ...]) -> list[str]:
    lowered = text.casefold()
    return [term for term in terms if re.search(r"(?<!\w)" + re.escape(str(term).casefold()) + r"(?!\w)", lowered)]


def compute_context_compatibility(observation: dict[str, Any], seed_triple: dict[str, Any],
                                  semantic_search_intent: dict[str, Any] | None = None,
                                  query_record: dict[str, Any] | None = None,
                                  paper_metadata: dict[str, Any] | None = None) -> ContextCompatibilityResult:
    context = seed_triple.get("context") or {}
    raw_seed = list(context.get("terms") or context.get("context_terms") or [])
    if semantic_search_intent:
        intent_context = ((semantic_search_intent.get("seed_triple") or {}).get("context") or {})
        raw_seed.extend(intent_context.get("terms") or intent_context.get("context_terms") or [])
    aliases = expand_context_terms([str(term) for term in raw_seed])
    if not aliases:
        return ContextCompatibilityResult(1.0, "context_not_required", (), (), (), (), (), (), (), (), (), (), (), (), (),
                                          False, False, False, True, ())
    evidence_text = str(observation.get("evidence_sentence") or observation.get("evidence_span") or "")
    l1_context_text = " ".join(str(observation.get(key) or "") for key in ("context", "context_mentions", "context_slots"))
    paper = paper_metadata or {}
    title_text = str(paper.get("title") or "")
    abstract_text = str(paper.get("abstract") or paper.get("abstract_text") or "")
    metadata_text = " ".join(str(paper.get(key) or "") for key in
                             ("journal", "journal_title", "keywords", "mesh_terms", "disease", "condition", "tissue", "cell_type", "species"))
    query_text = str((query_record or {}).get("query") or (query_record or {}).get("query_string") or "")
    evidence_matches = _mentions(evidence_text, aliases)
    l1_matches = _mentions(l1_context_text, aliases)
    abstract_matches = _mentions(abstract_text, aliases)
    title_matches = _mentions(title_text, aliases)
    metadata_matches = _mentions(metadata_text, aliases)
    query_matches = _mentions(query_text, aliases)
    intent_context = ((semantic_search_intent or {}).get("seed_triple") or {}).get("context") or {}
    semantic_terms = _mentions(" ".join(str(x) for x in intent_context.get("terms") or intent_context.get("context_terms") or []), aliases)
    strong = list(dict.fromkeys([*evidence_matches, *l1_matches, *abstract_matches, *title_matches, *metadata_matches]))
    weak = list(dict.fromkeys([*query_matches, *semantic_terms]))
    matched = list(dict.fromkeys([*strong, *weak]))
    sources = tuple(ContextSourceEvidence(source, strength, tuple(terms), text[:240] or None) for source, strength, terms, text in (
        ("evidence_sentence", "strong", evidence_matches, evidence_text),
        ("l1_context_slots", "strong", l1_matches, l1_context_text),
        ("abstract", "strong", abstract_matches, abstract_text),
        ("title", "strong", title_matches, title_text),
        ("metadata", "strong", metadata_matches, metadata_text),
        ("retrieval_query", "weak", query_matches, query_text),
        ("semantic_intent", "weak", semantic_terms, " ".join(str(x) for x in intent_context.get("terms") or [])),
    ) if terms)
    if strong:
        status, score, eligible, reasons = "context_matched", 1.0, True, ()
    elif weak or (query_record or {}).get("context_strict"):
        status, score, eligible, reasons = "context_query_only", 0.35, False, ("query_context_only_insufficient_for_context_specific_core",)
    else:
        status, score, eligible, reasons = "context_missing", 0.2, False, ("required_context_not_grounded",)
    return ContextCompatibilityResult(score, status, tuple(matched), tuple(x for x in aliases if x not in matched), reasons,
                                      tuple(evidence_matches), tuple(abstract_matches), tuple(title_matches), tuple(metadata_matches),
                                      tuple(aliases), tuple(query_matches), tuple(semantic_terms),
                                      tuple(dict.fromkeys([*abstract_matches, *title_matches, *metadata_matches])),
                                      tuple(strong), tuple(weak), bool(strong), bool(weak), bool(weak and not strong), eligible, sources)


def anchor_seed_predicate(evidence_sentence: str, subject_aliases: list[str], object_aliases: list[str],
                          seed_relation_family: str, l1_claim: dict[str, Any]) -> PredicateAnchorResult:
    sentence = str(evidence_sentence or ""); lowered = sentence.casefold()
    primary_hits = [(match.start(), word) for family in _PREDICATES.values() for word in family[0]
                    for match in re.finditer(r"(?<!\w)" + re.escape(word) + r"(?!\w)", lowered)]
    primary = min(primary_hits)[1] if primary_hits else None
    candidates: list[tuple[int, int, str, str, int, str]] = []
    for family, (words, sign, direction) in _PREDICATES.items():
        for word in words:
            for match in re.finditer(r"(?<!\w)" + re.escape(word) + r"(?!\w)", lowered):
                for alias in object_aliases:
                    object_match = re.search(r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)", lowered[match.end():match.end() + 100])
                    if object_match:
                        end = match.end() + object_match.end()
                        candidates.append((end - match.start(), match.start(), sentence[match.start():end], family, sign, direction))
        for alias in object_aliases:
            for object_match in re.finditer(r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)", lowered):
                tail = lowered[object_match.end():object_match.end() + 40]
                for word in words:
                    predicate_match = re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", tail)
                    if predicate_match:
                        end = object_match.end() + predicate_match.end()
                        candidates.append((end - object_match.start(), object_match.start(), sentence[object_match.start():end], family, sign, direction))
    if not candidates:
        return PredicateAnchorResult("no_seed_predicate_found", None, None, None, primary, 0, 0.0,
                                     ("ambiguous_seed_predicate_anchor",), False)
    candidates.sort(key=lambda item: (item[0], item[1])); best = candidates[0]
    tied_families = {item[3] for item in candidates if item[0] <= best[0] + 8}
    if len(tied_families) > 1:
        return PredicateAnchorResult("ambiguous_multiple_predicates", best[2], None, None, primary, 0, 0.35,
                                     ("ambiguous_seed_predicate_anchor",), False)
    multiple = len({item[3] for item in candidates}) > 1 or sum(lowered.count(word) for values in _PREDICATES.values() for word in values[0]) > 1
    status = "multiple_predicates_resolved" if multiple or (primary and primary not in best[2].casefold()) else "seed_object_anchored"
    expected = str(seed_relation_family or "").casefold()
    expected_family = "activation" if any(x in expected for x in ("activat", "increase", "promot", "upregulat")) else "inhibition" if any(x in expected for x in ("inhibit", "decrease", "suppress", "downregulat")) else ""
    consistent = not expected_family or best[3] == expected_family
    warnings = () if consistent else ("predicate_direction_inconsistent",)
    return PredicateAnchorResult(status, best[2], best[5], best[3], primary, best[4], 0.95, warnings, consistent)


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
                             hints: list[RuntimeEntityHint], *, seed_triple: dict[str, Any] | None = None,
                             semantic_search_intent: dict[str, Any] | None = None,
                             query_record: dict[str, Any] | None = None,
                             paper_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
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
    seed = seed_triple or {}
    relation = seed.get("relation") or {}
    anchor = anchor_seed_predicate(sentence,
        list(subject_seed.aliases) if subject_seed else [], list(object_seed.aliases) if object_seed else [],
        str(relation.get("family") or relation.get("name") or ""), item)
    compatibility = compute_context_compatibility(item, seed, semantic_search_intent, query_record, paper_metadata)
    if not sentence.strip():
        layer, retained, reason, excluded = "excluded", False, None, "missing_evidence_sentence"
    elif strict_subject and strict_object and subject_mentioned and object_mentioned and not anchor.predicate_direction_consistent:
        layer, retained, reason, excluded = "review_layer", True, "seed_relation_retained_for_predicate_review", "predicate_direction_inconsistent"
    elif strict_subject and strict_object and subject_mentioned and object_mentioned and anchor.anchor_status in {"no_seed_predicate_found", "ambiguous_multiple_predicates"}:
        layer, retained, reason, excluded = "review_layer", True, "seed_relation_retained_for_predicate_review", "ambiguous_seed_predicate_anchor"
    elif strict_subject and strict_object and subject_mentioned and object_mentioned and not compatibility.core_context_eligible:
        if compatibility.status == "context_query_only":
            layer, retained, reason, excluded = "cross_context_mechanism_layer", True, "seed_relation_supported_but_context_not_evidence_grounded", "query_context_only_insufficient_for_context_specific_core"
        else:
            layer, retained, reason, excluded = "cross_context_mechanism_layer", True, "seed_relation_supported_but_context_mismatch", "context_mismatch" if compatibility.status == "context_mismatch" else "context_missing_for_context_specific_core"
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
    anchored_fields = anchor.to_dict()
    if anchor.seed_predicate_direction and anchor.predicate_direction_consistent:
        seed_family_text = str(relation.get("family") or relation.get("name") or "").casefold()
        relation_family = anchor.seed_relation_family if any(token in seed_family_text for token in ("activat", "inhibit", "increase", "decrease", "promot", "suppress", "upregulat", "downregulat")) else str(item.get("relation_family") or anchor.seed_relation_family)
        anchored_fields.update({"direction": anchor.seed_predicate_direction, "relation_family": relation_family,
                                "relation_raw": anchor.seed_predicate_span, "direct_relation_sign": anchor.direct_relation_sign})
    return {"retained": retained, "graph_layer": layer, "canonical_graph_eligible": core,
            "seed_alignment_score": seed_score,
            "entity_grounding_score": round((float(subject_resolution.confidence) + float(object_resolution.confidence) + (subject_hint or {}).get("score", 0) + (object_hint or {}).get("score", 0)) / 4, 3),
            "relation_confidence_score": relation_confidence,
            "context_completeness_score": 1.0 if item.get("context") or item.get("context_mentions") or item.get("context_slots") else 0.0,
            "excluded_from_retention_reason": None if retained else excluded, "retention_reason": reason,
            "excluded_from_core_reason": None if core else (excluded or ("object_is_process_or_outcome_not_canonical_entity" if layer == "mechanism_layer" else "not_strict_canonical_seed_relation")),
            "context_compatibility_score": compatibility.score, "context_compatibility_status": compatibility.status,
            "core_context_eligible": compatibility.core_context_eligible, "context_compatibility": compatibility.to_dict(),
            **anchored_fields,
            "computed_seed_subject_mentioned": subject_mentioned, "computed_seed_object_mentioned": object_mentioned,
            "computed_context_mentioned": context_mentioned, "computed_seed_relevance": relevance}


__all__ = ["ContextCompatibilityResult", "ContextSourceEvidence", "PredicateAnchorResult", "RuntimeEntityHint", "anchor_seed_predicate", "compute_context_compatibility", "decide_l2_evidence_layer", "load_runtime_entity_hints", "match_runtime_hint", "normalize_mention"]
