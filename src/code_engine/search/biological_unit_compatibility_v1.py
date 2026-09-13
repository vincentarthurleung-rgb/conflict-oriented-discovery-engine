"""Deterministic biological-unit compatibility for pre-acquisition shadow use.

This module resolves only exact curated surfaces and explicit typed relations.  It
does not score relevance, relation evidence, endpoints, acquisition, or tiers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Literal

from code_engine.normalization.lexical import normalize_lexical_surface


UnitType = Literal["cell_type", "cell_line", "tissue", "organ", "anatomical_region", "mixed", "unknown"]
ResolutionStatus = Literal["resolved", "ambiguous", "unresolved"]
CompatibilityState = Literal["EXACT", "AUTHORIZED_COMPATIBLE", "UNRESOLVED", "INCOMPATIBLE"]
EvidenceRole = Literal["experimental_biological_unit", "background_reference_unit", "mentioned_unit"]

COMPATIBILITY_STATES = ("EXACT", "AUTHORIZED_COMPATIBLE", "UNRESOLVED", "INCOMPATIBLE")
UNIT_TYPES = {"cell_type", "cell_line", "tissue", "organ", "anatomical_region", "mixed", "unknown"}
REASON_CODES = {
    "EXACT_CANONICAL_MATCH", "ALIAS_MATCH", "AUTHORIZED_SUBTYPE", "AUTHORIZED_MODEL_OF",
    "BROADER_CONTAINER_ONLY", "DISTINCT_CELL_TYPE", "DISTINCT_ANATOMICAL_REGION",
    "CELL_TYPE_UNRESOLVED", "REGION_UNRESOLVED", "MULTIPLE_CONFLICTING_UNITS",
    "NO_BIOLOGICAL_UNIT_EVIDENCE",
}


@dataclass(frozen=True)
class BiologicalUnitRefV1:
    canonical_id: str
    canonical_name: str
    unit_type: UnitType
    aliases: tuple[str, ...] = ()
    parent_ids: tuple[str, ...] = ()
    model_of_ids: tuple[str, ...] = ()
    anatomical_region_ids: tuple[str, ...] = ()
    source: str = "curated_registry"
    resolution_status: ResolutionStatus = "resolved"
    provenance: str = ""
    comment: str = ""


@dataclass(frozen=True)
class BiologicalUnitTargetV1:
    required_units: tuple[BiologicalUnitRefV1, ...]
    required_unit_types: tuple[str, ...]
    required_anatomical_regions: tuple[BiologicalUnitRefV1, ...] = ()
    allow_exact: bool = True
    allow_alias: bool = True
    allow_descendant: bool = False
    allow_model_of: bool = False
    allow_broader_container: bool = False
    require_anatomical_region_match_when_specified: bool = True


@dataclass(frozen=True)
class ObservedUnitV1:
    unit: BiologicalUnitRefV1
    evidence_role: EvidenceRole
    matched_surface: str
    normalized_surface: str
    field: str
    normalized_start: int
    normalized_end: int
    sentence: str
    match_type: str


@dataclass(frozen=True)
class BiologicalUnitCompatibilityDecisionV1:
    target_units: tuple[dict[str, Any], ...]
    target_anatomical_regions: tuple[dict[str, Any], ...]
    observed_units: tuple[dict[str, Any], ...]
    cell_identity_state: CompatibilityState
    anatomical_region_state: CompatibilityState
    overall_state: CompatibilityState
    reason_codes: tuple[str, ...]
    matched_surfaces: tuple[dict[str, Any], ...]
    source_evidence_scope: tuple[str, ...]
    resolver_status: ResolutionStatus
    registry_version: str
    policy_version: str
    decision_mode: str = "deterministic"
    preacquisition_only: bool = True
    modifies_tier: bool = False
    modifies_acquisition: bool = False
    modifies_sample_membership: bool = False


def _unique(values):
    return list(dict.fromkeys(values))


class BiologicalUnitRegistryV1:
    """Exact-only registry using the repository's existing lexical normalizer."""

    def __init__(self, payload: dict[str, Any]):
        self.version = payload["registry_version"]
        self.entries: dict[str, BiologicalUnitRefV1] = {}
        self.surface_index: dict[str, list[tuple[str, str]]] = {}
        for raw in payload["units"]:
            if raw["unit_type"] not in UNIT_TYPES:
                raise ValueError(f"unsupported biological unit type: {raw['unit_type']}")
            ref = BiologicalUnitRefV1(
                canonical_id=raw["canonical_id"], canonical_name=raw["canonical_name"],
                unit_type=raw["unit_type"], aliases=tuple(raw.get("aliases", [])),
                parent_ids=tuple(raw.get("parent_ids", [])), model_of_ids=tuple(raw.get("model_of_ids", [])),
                anatomical_region_ids=tuple(raw.get("anatomical_region_ids", [])),
                source=raw.get("source", "curated_registry"),
                resolution_status=raw.get("resolution_status", "resolved"),
                provenance=raw.get("provenance", ""), comment=raw.get("comment", ""),
            )
            if ref.canonical_id in self.entries:
                raise ValueError(f"duplicate canonical ID: {ref.canonical_id}")
            self.entries[ref.canonical_id] = ref
            surfaces = [(ref.canonical_name, "canonical_exact"), *[(alias, "alias_exact") for alias in ref.aliases]]
            for surface, match_type in surfaces:
                normalized = normalize_lexical_surface(surface).normalized_surface
                if not normalized:
                    raise ValueError(f"invalid registry surface: {surface}")
                self.surface_index.setdefault(normalized, []).append((ref.canonical_id, match_type))
        for ref in self.entries.values():
            for relation_id in (*ref.parent_ids, *ref.model_of_ids, *ref.anatomical_region_ids):
                if relation_id not in self.entries:
                    raise ValueError(f"unknown related biological unit: {relation_id}")

    def get(self, canonical_id: str) -> BiologicalUnitRefV1:
        return self.entries[canonical_id]

    def exact_surface(self, surface: str) -> tuple[BiologicalUnitRefV1, str] | None:
        normalized = normalize_lexical_surface(surface).normalized_surface
        matches = self.surface_index.get(normalized, [])
        ids = {canonical_id for canonical_id, _ in matches}
        if len(ids) != 1:
            return None
        canonical_id, match_type = matches[0]
        return self.entries[canonical_id], match_type

    def resolve_target(self, surfaces: list[str], policy: dict[str, Any]) -> BiologicalUnitTargetV1:
        units, regions = [], []
        for surface in surfaces:
            normalized = normalize_lexical_surface(surface).normalized_surface
            for candidate_surface, _, _ in _longest_surface_matches(normalized, self.surface_index):
                for canonical_id, match_type in self.surface_index[candidate_surface]:
                    if match_type == "alias_exact" and not policy["allow_alias"]:
                        continue
                    ref = self.entries[canonical_id]
                    (regions if ref.unit_type == "anatomical_region" else units).append(ref)
        units = _dedup_refs(units)
        regions = _dedup_refs(regions)
        return BiologicalUnitTargetV1(
            required_units=tuple(units), required_unit_types=tuple(_unique(ref.unit_type for ref in units)),
            required_anatomical_regions=tuple(regions),
            allow_exact=bool(policy["allow_exact"]), allow_alias=bool(policy["allow_alias"]),
            allow_descendant=bool(policy["allow_descendant"]), allow_model_of=bool(policy["allow_model_of"]),
            allow_broader_container=bool(policy["allow_broader_container"]),
            require_anatomical_region_match_when_specified=bool(policy["require_anatomical_region_match_when_specified"]),
        )

    def detect(self, title: str, abstract: str, policy: dict[str, Any]) -> list[ObservedUnitV1]:
        hits = []
        for field_name, raw_text in (("title", title), ("abstract", abstract)):
            normalized = normalize_lexical_surface(raw_text).normalized_surface
            for surface, start, end in _longest_surface_matches(normalized, self.surface_index):
                sentence = _sentence_at(normalized, start, end)
                role = _evidence_role(field_name, sentence, policy)
                for canonical_id, match_type in self.surface_index[surface]:
                    hits.append(ObservedUnitV1(
                        unit=self.entries[canonical_id], evidence_role=role, matched_surface=surface,
                        normalized_surface=surface, field=field_name, normalized_start=start,
                        normalized_end=end, sentence=sentence, match_type=match_type,
                    ))
                    for region_id in self.entries[canonical_id].anatomical_region_ids:
                        hits.append(ObservedUnitV1(
                            unit=self.entries[region_id], evidence_role=role, matched_surface=surface,
                            normalized_surface=surface, field=field_name, normalized_start=start,
                            normalized_end=end, sentence=sentence,
                            match_type="curated_anatomical_region_relation",
                        ))
        return _dedup_observations(hits)


def _bounded_spans(text: str, surface: str):
    pattern = re.compile(r"(?<!\w)" + re.escape(surface) + r"(?!\w)")
    return [(match.start(), match.end()) for match in pattern.finditer(text)]


def _longest_surface_matches(text: str, surface_index: dict[str, Any]):
    """Prefer explicit longest surfaces while retaining exact-span ambiguities."""
    candidates = [(surface, start, end) for surface in surface_index
                  for start, end in _bounded_spans(text, surface)]
    candidates.sort(key=lambda item: (item[1], -(item[2] - item[1]), item[0]))
    accepted = []
    for candidate in candidates:
        _, start, end = candidate
        if any(other_start <= start and end <= other_end and
               (other_start, other_end) != (start, end)
               for _, other_start, other_end in accepted):
            continue
        accepted.append(candidate)
    return accepted


def _sentence_at(text: str, start: int, end: int):
    left = max(text.rfind(".", 0, start), text.rfind(";", 0, start), text.rfind(":", 0, start)) + 1
    stops = [index for index in (text.find(".", end), text.find(";", end)) if index >= 0]
    right = min(stops) + 1 if stops else len(text)
    return text[left:right].strip()


def _evidence_role(field: str, sentence: str, policy: dict[str, Any]) -> EvidenceRole:
    if field == "abstract" and any(re.search(pattern, sentence) for pattern in policy["background_role_patterns"]):
        return "background_reference_unit"
    if field == "abstract" and any(re.search(pattern, sentence) for pattern in policy["experimental_role_patterns"]):
        return "experimental_biological_unit"
    return "mentioned_unit"


def _dedup_refs(refs):
    return [next(ref for ref in refs if ref.canonical_id == canonical_id)
            for canonical_id in _unique(ref.canonical_id for ref in refs)]


def _dedup_observations(observations):
    result, seen = [], set()
    for item in observations:
        key = (item.unit.canonical_id, item.evidence_role, item.field, item.normalized_start, item.normalized_end)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _ancestors(registry: BiologicalUnitRegistryV1, ref: BiologicalUnitRefV1):
    result, pending = set(), list(ref.parent_ids)
    while pending:
        parent = pending.pop(0)
        if parent not in result:
            result.add(parent)
            pending.extend(registry.get(parent).parent_ids)
    return result


def _single_unit_state(registry, target, observed):
    target_ids = {ref.canonical_id for ref in target.required_units}
    ref = observed.unit
    if ref.canonical_id in target_ids and target.allow_exact:
        if observed.match_type in {"canonical_exact", "curated_anatomical_region_relation"}:
            return "EXACT", "EXACT_CANONICAL_MATCH"
        if observed.match_type == "alias_exact" and target.allow_alias:
            return "EXACT", "ALIAS_MATCH"
        return "UNRESOLVED", "CELL_TYPE_UNRESOLVED"
    if target.allow_descendant and target_ids & _ancestors(registry, ref):
        return "AUTHORIZED_COMPATIBLE", "AUTHORIZED_SUBTYPE"
    if target.allow_model_of and target_ids & set(ref.model_of_ids):
        return "AUTHORIZED_COMPATIBLE", "AUTHORIZED_MODEL_OF"
    if ref.unit_type in {"tissue", "organ"} and not target.allow_broader_container and any(
            unit.unit_type in {"cell_type", "cell_line"} for unit in target.required_units):
        return "UNRESOLVED", "BROADER_CONTAINER_ONLY"
    if ref.unit_type == "cell_line":
        return "UNRESOLVED", "CELL_TYPE_UNRESOLVED"
    return "INCOMPATIBLE", "DISTINCT_CELL_TYPE"


def _aggregate_cell_state(registry, target, observed):
    if not target.required_units:
        return "UNRESOLVED", ["CELL_TYPE_UNRESOLVED"], "unresolved"
    relevant = [item for item in observed if item.unit.unit_type != "anatomical_region"
                and item.evidence_role == "experimental_biological_unit"]
    if not relevant:
        if observed:
            return "UNRESOLVED", ["CELL_TYPE_UNRESOLVED"], "resolved"
        return "UNRESOLVED", ["NO_BIOLOGICAL_UNIT_EVIDENCE"], "unresolved"
    outcomes = [_single_unit_state(registry, target, item) for item in relevant]
    states, reasons = [item[0] for item in outcomes], [item[1] for item in outcomes]
    compatible = any(state in {"EXACT", "AUTHORIZED_COMPATIBLE"} for state in states)
    conflicting = any(state == "INCOMPATIBLE" for state in states)
    if compatible and conflicting:
        return "UNRESOLVED", _unique([*reasons, "MULTIPLE_CONFLICTING_UNITS"]), "ambiguous"
    if all(state == "INCOMPATIBLE" for state in states):
        return "INCOMPATIBLE", _unique(reasons), "resolved"
    if any(state == "UNRESOLVED" for state in states):
        return "UNRESOLVED", _unique(reasons), "ambiguous" if len(set(item.unit.canonical_id for item in relevant)) > 1 else "unresolved"
    if any(state == "AUTHORIZED_COMPATIBLE" for state in states):
        return "AUTHORIZED_COMPATIBLE", _unique(reasons), "resolved"
    return "EXACT", _unique(reasons), "resolved"


def _aggregate_region_state(registry, target, observed):
    if not target.required_anatomical_regions:
        return "EXACT", [], "resolved"
    relevant = [item for item in observed if item.unit.unit_type == "anatomical_region"
                and item.evidence_role == "experimental_biological_unit"]
    if not relevant:
        return "UNRESOLVED", ["REGION_UNRESOLVED"], "unresolved"
    targets = {item.canonical_id for item in target.required_anatomical_regions}
    states = []
    for item in relevant:
        if item.unit.canonical_id in targets:
            if item.match_type in {"canonical_exact", "curated_anatomical_region_relation"}:
                states.append(("EXACT", "EXACT_CANONICAL_MATCH"))
            elif item.match_type == "alias_exact" and target.allow_alias:
                states.append(("EXACT", "ALIAS_MATCH"))
            else:
                states.append(("UNRESOLVED", "REGION_UNRESOLVED"))
        elif target.allow_descendant and targets & _ancestors(registry, item.unit):
            states.append(("AUTHORIZED_COMPATIBLE", "AUTHORIZED_SUBTYPE"))
        else:
            states.append(("INCOMPATIBLE", "DISTINCT_ANATOMICAL_REGION"))
    compatible = any(state[0] in {"EXACT", "AUTHORIZED_COMPATIBLE"} for state in states)
    conflicting = any(state[0] == "INCOMPATIBLE" for state in states)
    reasons = _unique(state[1] for state in states)
    if compatible and conflicting:
        return "UNRESOLVED", _unique([*reasons, "MULTIPLE_CONFLICTING_UNITS"]), "ambiguous"
    if conflicting and all(state[0] == "INCOMPATIBLE" for state in states):
        return "INCOMPATIBLE", reasons, "resolved"
    if any(state[0] == "UNRESOLVED" for state in states):
        return "UNRESOLVED", reasons, "unresolved"
    if any(state[0] == "AUTHORIZED_COMPATIBLE" for state in states):
        return "AUTHORIZED_COMPATIBLE", reasons, "resolved"
    return "EXACT", reasons, "resolved"


def decide_biological_unit_compatibility(
    registry: BiologicalUnitRegistryV1, policy: dict[str, Any], target_context_qualifiers: list[str],
    *, title: str, abstract: str, publication_metadata: dict[str, Any] | None = None,
) -> BiologicalUnitCompatibilityDecisionV1:
    """Decide from target plus title/abstract/metadata only; output has no gate effect."""
    del publication_metadata  # allowed interface field; registry v1 has no metadata rule.
    target = registry.resolve_target(target_context_qualifiers, policy)
    observed = registry.detect(title, abstract, policy)
    cell_state, cell_reasons, cell_status = _aggregate_cell_state(registry, target, observed)
    region_state, region_reasons, region_status = _aggregate_region_state(registry, target, observed)
    if "INCOMPATIBLE" in {cell_state, region_state}:
        overall = "INCOMPATIBLE"
    elif "UNRESOLVED" in {cell_state, region_state}:
        overall = "UNRESOLVED"
    elif "AUTHORIZED_COMPATIBLE" in {cell_state, region_state}:
        overall = "AUTHORIZED_COMPATIBLE"
    else:
        overall = "EXACT"
    statuses = {cell_status, region_status}
    resolver_status = "ambiguous" if "ambiguous" in statuses else ("unresolved" if "unresolved" in statuses else "resolved")
    reason_codes = tuple(_unique([*cell_reasons, *region_reasons]))
    if not set(reason_codes) <= REASON_CODES:
        raise ValueError("unknown reason code")
    return BiologicalUnitCompatibilityDecisionV1(
        target_units=tuple(asdict(ref) for ref in target.required_units),
        target_anatomical_regions=tuple(asdict(ref) for ref in target.required_anatomical_regions),
        observed_units=tuple({**asdict(item.unit), "evidence_role": item.evidence_role} for item in observed),
        cell_identity_state=cell_state, anatomical_region_state=region_state, overall_state=overall,
        reason_codes=reason_codes,
        matched_surfaces=tuple({"canonical_id": item.unit.canonical_id, "matched_surface": item.matched_surface,
            "match_type": item.match_type, "evidence_role": item.evidence_role, "field": item.field,
            "normalized_start": item.normalized_start, "normalized_end": item.normalized_end,
            "normalized_sentence": item.sentence} for item in observed),
        source_evidence_scope=("ScientificPropositionTargetV1.context_qualifiers", "publication.title",
                               "publication.abstract", "publication.publication_types"),
        resolver_status=resolver_status, registry_version=registry.version,
        policy_version=policy["policy_version"],
    )
