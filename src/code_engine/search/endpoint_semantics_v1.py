"""Deterministic pre-acquisition endpoint semantics in shadow mode."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Literal

from code_engine.normalization.lexical import normalize_lexical_surface


DimensionState = Literal[
    "MATCH", "AUTHORIZED_EQUIVALENT", "NOT_APPLICABLE", "UNRESOLVED", "INCOMPATIBLE"
]
EndpointState = Literal["EXACT", "AUTHORIZED_EQUIVALENT", "PARTIAL", "UNRESOLVED", "INCOMPATIBLE"]
EndpointEvidenceRole = Literal[
    "CURRENT_STUDY_MEASUREMENT", "CURRENT_STUDY_SURROGATE", "BACKGROUND_ENDPOINT",
    "DISCUSSION_ENDPOINT", "UNRESOLVED_ROLE",
]

ENDPOINT_STATES = ("EXACT", "AUTHORIZED_EQUIVALENT", "PARTIAL", "UNRESOLVED", "INCOMPATIBLE")
DIMENSIONS = (
    "measurement_entity", "measurement_property", "measurement_process", "measurement_state",
    "measurement_compartment", "measurement_condition", "response_context",
)
SPEC_FIELDS = {
    "measurement_entity": "required_entity",
    "measurement_property": "required_property",
    "measurement_process": "required_process",
    "measurement_state": "required_state",
    "measurement_compartment": "required_compartment",
    "measurement_condition": "required_condition",
    "response_context": "required_response_context",
}
DECISION_FIELDS = {
    "measurement_entity": "entity_state",
    "measurement_property": "property_state",
    "measurement_process": "process_state",
    "measurement_state": "molecular_state_state",
    "measurement_compartment": "compartment_state",
    "measurement_condition": "condition_state",
    "response_context": "response_context_state",
}

REASON_CODES = {
    "EXACT_ENTITY_MATCH", "AUTHORIZED_ENDPOINT_EQUIVALENCE", "PROPERTY_MATCH",
    "PROPERTY_INCOMPATIBLE", "PROCESS_MATCH", "PROCESS_INCOMPATIBLE", "STATE_MATCH",
    "STATE_INCOMPATIBLE", "COMPARTMENT_MATCH", "COMPARTMENT_INCOMPATIBLE",
    "CONDITION_MATCH", "CONDITION_MISSING", "CONDITION_INCOMPATIBLE",
    "RESPONSE_CONTEXT_MATCH", "RESPONSE_CONTEXT_UNRESOLVED", "ABUNDANCE_NOT_ACTIVATION",
    "TRANSCRIPTION_NOT_SECRETION", "PRECURSOR_NOT_MATURE_PRODUCT",
    "INTRACELLULAR_NOT_EXTRACELLULAR", "MORPHOLOGY_NOT_DENSITY",
    "TRANSLOCATION_NOT_UPTAKE", "GENERIC_SECRETION_NOT_STIMULATED_SECRETION",
    "VIABILITY_NOT_DRUG_SENSITIVITY", "SURROGATE_NOT_FUNCTIONAL_ENDPOINT",
    "CURRENT_STUDY_ENDPOINT", "BACKGROUND_ENDPOINT_ONLY", "MULTIPLE_ENDPOINTS_UNRESOLVED",
    "NO_ENDPOINT_EVIDENCE", "ENTITY_UNRESOLVED", "PROPERTY_UNRESOLVED",
    "PROCESS_UNRESOLVED", "STATE_UNRESOLVED", "COMPARTMENT_UNRESOLVED",
    "OPTIONAL_DIMENSION_INCOMPATIBLE_IGNORED", "TARGET_ENDPOINT_SPEC_UNRESOLVED",
}


@dataclass(frozen=True)
class EndpointSemanticRefV1:
    measurement_entity: str | None
    measurement_property: str | None
    measurement_process: str | None
    measurement_state: str | None
    measurement_compartment: str | None
    measurement_condition: str | None
    response_context: str | None
    assay_family: str | None
    resolution_status: str
    endpoint_evidence_role: EndpointEvidenceRole
    matched_surface: str
    source_field: str
    sentence_index: int
    source_sentence: str


@dataclass(frozen=True)
class EndpointTargetSpecV1:
    required_entity: str | None
    required_property: str | None
    required_process: str | None
    required_state: str | None
    required_compartment: str | None
    required_condition: str | None
    required_response_context: str | None
    authorized_equivalences: tuple[dict[str, Any], ...]
    required_dimensions: tuple[str, ...]
    optional_dimensions: tuple[str, ...]


@dataclass(frozen=True)
class EndpointSemanticDecisionV1:
    packet_id: str
    applicable: bool
    target_endpoint_spec: dict[str, Any]
    observed_endpoint_candidates: tuple[dict[str, Any], ...]
    entity_state: DimensionState
    property_state: DimensionState
    process_state: DimensionState
    molecular_state_state: DimensionState
    compartment_state: DimensionState
    condition_state: DimensionState
    response_context_state: DimensionState
    overall_state: EndpointState
    endpoint_evidence_role: EndpointEvidenceRole
    matched_surfaces: tuple[dict[str, Any], ...]
    reason_codes: tuple[str, ...]
    resolver_status: str
    registry_version: str
    policy_version: str
    decision_mode: str = "deterministic"
    preacquisition_only: bool = True
    modifies_tier: bool = False
    modifies_acquisition: bool = False
    modifies_sample_membership: bool = False
    modifies_reject_status: bool = False


def _normalized(value: Any) -> str:
    return normalize_lexical_surface(str(value or "")).normalized_surface


def _unique(values):
    return list(dict.fromkeys(values))


def _hits(text: str, patterns: list[str]):
    hits = []
    for pattern in patterns:
        for match in re.finditer(r"(?<!\w)(?:" + pattern + r")(?!\w)", text):
            hits.append((match.start(), match.end(), match.group(0)))
    return sorted(hits)


def _concept_hits(text: str, registry: dict[str, Any], dimension: str):
    found = []
    for concept, patterns in registry["concept_patterns"].get(dimension, {}).items():
        for start, end, surface in _hits(text, patterns):
            found.append({"concept": concept, "start": start, "end": end, "surface": surface})
    found.sort(key=lambda item: (item["start"], -(item["end"] - item["start"]), item["concept"]))
    accepted = []
    for item in found:
        if any(other["start"] <= item["start"] and item["end"] <= other["end"] for other in accepted):
            continue
        accepted.append(item)
    return accepted


def _concept_values(text: str, registry: dict[str, Any], dimension: str):
    return _unique(hit["concept"] for hit in _concept_hits(text, registry, dimension))


def _singular(value: str):
    if value.endswith("ies"):
        return value[:-3] + "y"
    if value.endswith("s") and not value.endswith(("ss", "sis")):
        return value[:-1]
    return value


def _strip_semantics(value: str, registry: dict[str, Any]):
    text = f" {value} "
    for dimension in ("measurement_property", "measurement_process", "measurement_state",
                      "measurement_compartment", "measurement_condition"):
        for patterns in registry["concept_patterns"][dimension].values():
            for pattern in patterns:
                text = re.sub(r"(?<!\w)(?:" + pattern + r")(?!\w)", " ", text)
    text = re.sub(r"\b(?:cellular|generic|stimulated|treatment|contrast|gene|protein|or|and|type)\b", " ", text)
    return _singular(" ".join(text.split()).strip(" -/"))


def _target_entity_values(target: dict[str, Any], registry: dict[str, Any], property_value: str | None):
    measurement = _normalized(target.get("measurement_target") or target.get("object"))
    therapy = _normalized(target.get("therapy"))
    if property_value in {"drug_response", "sensitivity", "resistance", "viability", "apoptosis"} and therapy:
        return ["drug response"]
    values = []
    for part in re.split(r"\s*/\s*|\s+or\s+", measurement):
        stripped = _strip_semantics(part, registry)
        if stripped:
            values.append(stripped)
    if not values:
        stripped = _strip_semantics(_normalized(target.get("object")), registry)
        if stripped:
            values.append(stripped)
    return _unique(values)


def _target_dimension_values(text: str, registry: dict[str, Any], dimension: str):
    values = _concept_values(text, registry, dimension)
    if dimension == "measurement_property" and "contrast" in text and ({"sensitivity", "resistance", "viability", "apoptosis", "drug_response"} & set(values)):
        return ["drug_response", *[value for value in values if value != "drug_response"]]
    return values


def build_endpoint_target_spec(target: dict[str, Any], registry: dict[str, Any]) -> EndpointTargetSpecV1:
    explicit = target.get("endpoint_target_spec")
    if explicit:
        values = dict(explicit)
        values["authorized_equivalences"] = tuple(values.get("authorized_equivalences") or ())
        values["required_dimensions"] = tuple(values.get("required_dimensions") or ())
        values["optional_dimensions"] = tuple(values.get("optional_dimensions") or ())
        return EndpointTargetSpecV1(**values)

    endpoint_text = _normalized(" ".join(str(target.get(key) or "") for key in (
        "measurement_target", "measurement_property_endpoint", "object")))
    entity_and_object_text = _normalized(" ".join(str(target.get(key) or "") for key in (
        "measurement_target", "object")))
    property_values = _target_dimension_values(endpoint_text, registry, "measurement_property")
    process_values = _target_dimension_values(endpoint_text, registry, "measurement_process")
    state_values = _target_dimension_values(entity_and_object_text, registry, "measurement_state")
    compartment_values = _target_dimension_values(endpoint_text, registry, "measurement_compartment")
    condition_values = _target_dimension_values(endpoint_text, registry, "measurement_condition")
    property_value = property_values[0] if property_values else None
    entity_values = _target_entity_values(target, registry, property_value)
    response_context = _normalized(target.get("therapy")) or None
    if property_value not in {"drug_response", "sensitivity", "resistance", "viability", "apoptosis"}:
        response_context = None
    required = {
        "measurement_entity": entity_values[0] if entity_values else None,
        "measurement_property": property_value,
        "measurement_process": process_values[0] if process_values else None,
        "measurement_state": state_values[0] if state_values else None,
        "measurement_compartment": compartment_values[0] if compartment_values else None,
        "measurement_condition": condition_values[0] if condition_values else None,
        "response_context": response_context,
    }
    authorized = []
    for dimension, values in (
        ("measurement_entity", entity_values), ("measurement_property", property_values),
        ("measurement_process", process_values), ("measurement_state", state_values),
        ("measurement_compartment", compartment_values), ("measurement_condition", condition_values),
    ):
        target_value = required[dimension]
        for source in values[1:]:
            if source != target_value:
                authorized.append({
                    "dimension": dimension, "source_concept": source, "target_concept": target_value,
                    "relation": "target_declared_acceptable_endpoint_alternative",
                    "directionality": "source_to_target",
                    "scientific_rationale": "Alternative is explicitly present in the frozen target endpoint specification.",
                    "provenance_comment": "ScientificPropositionTargetV1 endpoint fields.",
                })
    authorized.extend(target.get("authorized_endpoint_equivalences") or [])
    required_dimensions = tuple(dimension for dimension in DIMENSIONS if required[dimension] is not None)
    optional = tuple(dimension for dimension in DIMENSIONS if dimension not in required_dimensions)
    return EndpointTargetSpecV1(
        required_entity=required["measurement_entity"], required_property=required["measurement_property"],
        required_process=required["measurement_process"], required_state=required["measurement_state"],
        required_compartment=required["measurement_compartment"],
        required_condition=required["measurement_condition"],
        required_response_context=required["response_context"],
        authorized_equivalences=tuple(authorized), required_dimensions=required_dimensions,
        optional_dimensions=optional,
    )


def _entity_surfaces(target: dict[str, Any], spec: EndpointTargetSpecV1, registry: dict[str, Any]):
    values = [spec.required_entity]
    values.extend(item["source_concept"] for item in spec.authorized_equivalences
                  if item.get("dimension") == "measurement_entity")
    measurement = _normalized(target.get("measurement_target"))
    for part in re.split(r"\s*/\s*|\s+or\s+", measurement):
        stripped = _strip_semantics(part, registry)
        if stripped:
            values.append(stripped)
    raw_object = _strip_semantics(_normalized(target.get("object")), registry)
    if raw_object and _normalized(target.get("object")) != _normalized(target.get("therapy")):
        values.append(raw_object)
    surfaces = []
    for value in values:
        normalized = _normalized(value)
        if normalized and normalized != "drug response":
            surfaces.extend([normalized, _singular(normalized)])
    return sorted(_unique(surfaces), key=lambda value: (-len(value), value))


def _sentences(title: str, abstract: str):
    rows = []
    for field, source in (("title", title), ("abstract", abstract)):
        text = _normalized(source)
        for index, sentence in enumerate(part.strip() for part in re.split(r"(?<=[.;])\s+", text) if part.strip()):
            rows.append({"field": field, "sentence_index": index, "text": sentence})
    return rows


def _role(sentence: dict[str, Any], policy: dict[str, Any]):
    text = sentence["text"]
    if any(re.search(pattern, text) for pattern in policy["background_patterns"]):
        return "BACKGROUND_ENDPOINT"
    if any(re.search(pattern, text) for pattern in policy["discussion_patterns"]):
        return "DISCUSSION_ENDPOINT"
    if sentence["field"] == "title" or any(re.search(pattern, text) for pattern in policy["current_study_patterns"]):
        return "CURRENT_STUDY_MEASUREMENT"
    return "UNRESOLVED_ROLE"


def _bounded_surface_hits(text: str, surfaces: list[str]):
    hits = []
    for surface in surfaces:
        for match in re.finditer(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", text):
            hits.append({"surface": surface, "start": match.start(), "end": match.end()})
    return sorted(hits, key=lambda item: (item["start"], -(item["end"] - item["start"])))


def _is_surrogate(values: dict[str, str | None], spec: EndpointTargetSpecV1, policy: dict[str, Any]):
    for pair in policy["surrogate_pairs"]:
        dimension = pair["observed_dimension"]
        required = getattr(spec, SPEC_FIELDS[dimension])
        if values.get(dimension) == pair["observed"] and required == pair["required"]:
            return True
    return False


def extract_observed_candidates(target: dict[str, Any], spec: EndpointTargetSpecV1, *, title: str,
                                abstract: str, publication_metadata: dict[str, Any] | None,
                                registry: dict[str, Any], policy: dict[str, Any]):
    del publication_metadata  # Reserved for explicit assay metadata; never infer absent values.
    surfaces = _entity_surfaces(target, spec, registry)
    therapy_surface = _normalized(target.get("therapy"))
    candidates = []
    for sentence in _sentences(title, abstract):
        entity_hits = _bounded_surface_hits(sentence["text"], surfaces)
        response_hit = spec.required_entity == "drug response" and therapy_surface and _bounded_surface_hits(
            sentence["text"], [therapy_surface])
        if not entity_hits and not response_hit:
            continue
        concepts = {dimension: _concept_values(sentence["text"], registry, dimension)
                    for dimension in registry["concept_patterns"]}
        if "transcription" in concepts["measurement_process"]:
            concepts["measurement_property"] = [
                value for value in concepts["measurement_property"] if value != "expression"
            ]
        anchors = [("measurement_property", value) for value in concepts["measurement_property"]]
        anchors += [("measurement_process", value) for value in concepts["measurement_process"]]
        if not anchors:
            anchors = [(None, None)]
        for anchor_dimension, anchor_value in anchors:
            values = {
                "measurement_entity": spec.required_entity,
                "measurement_property": None,
                "measurement_process": None,
                "measurement_state": concepts["measurement_state"][0] if concepts["measurement_state"] else None,
                "measurement_compartment": concepts["measurement_compartment"][0] if concepts["measurement_compartment"] else None,
                "measurement_condition": concepts["measurement_condition"][0] if concepts["measurement_condition"] else None,
                "response_context": therapy_surface if response_hit else None,
                "assay_family": concepts["assay_family"][0] if concepts["assay_family"] else None,
            }
            if anchor_dimension:
                values[anchor_dimension] = anchor_value
            role = _role(sentence, policy)
            if role == "CURRENT_STUDY_MEASUREMENT" and _is_surrogate(values, spec, policy):
                role = "CURRENT_STUDY_SURROGATE"
            matched = entity_hits[0]["surface"] if entity_hits else therapy_surface
            candidates.append(EndpointSemanticRefV1(
                **values, resolution_status="resolved" if anchor_dimension else "partially_resolved",
                endpoint_evidence_role=role, matched_surface=matched,
                source_field=sentence["field"], sentence_index=sentence["sentence_index"],
                source_sentence=sentence["text"],
            ))
    unique = {}
    for candidate in candidates:
        key = (candidate.source_field, candidate.sentence_index, candidate.measurement_property,
               candidate.measurement_process, candidate.measurement_state,
               candidate.measurement_compartment, candidate.measurement_condition,
               candidate.response_context, candidate.endpoint_evidence_role)
        unique[key] = candidate
    return list(unique.values())


def _authorized(dimension: str, observed: str, required: str, spec: EndpointTargetSpecV1,
                registry: dict[str, Any]):
    relations = [*registry.get("authorized_equivalences", []), *spec.authorized_equivalences]
    for relation in relations:
        if relation.get("dimension") != dimension:
            continue
        source, target = relation.get("source_concept"), relation.get("target_concept")
        if source == observed and target == required:
            return relation
        if relation.get("directionality") == "bidirectional" and source == required and target == observed:
            return relation
    return None


def _incompatible(dimension: str, observed: str, required: str, registry: dict[str, Any]):
    for pair in registry.get("incompatible_pairs", []):
        if pair["dimension"] != dimension:
            continue
        if {pair["left"], pair["right"]} == {observed, required}:
            return pair["reason_code"]
    return None


def _dimension_reason(dimension: str, state: str):
    prefix = {
        "measurement_property": "PROPERTY", "measurement_process": "PROCESS",
        "measurement_state": "STATE", "measurement_compartment": "COMPARTMENT",
        "measurement_condition": "CONDITION", "response_context": "RESPONSE_CONTEXT",
    }.get(dimension)
    if dimension == "measurement_entity" and state == "MATCH":
        return "EXACT_ENTITY_MATCH"
    if prefix and state == "MATCH":
        return f"{prefix}_MATCH"
    if prefix and state == "INCOMPATIBLE":
        return f"{prefix}_INCOMPATIBLE"
    if dimension == "measurement_condition" and state == "UNRESOLVED":
        return "CONDITION_MISSING"
    if prefix and state == "UNRESOLVED":
        return f"{prefix}_UNRESOLVED"
    if dimension == "measurement_entity" and state == "UNRESOLVED":
        return "ENTITY_UNRESOLVED"
    return None


def _evaluate_candidate(candidate: EndpointSemanticRefV1, spec: EndpointTargetSpecV1,
                        registry: dict[str, Any]):
    states = {}
    reasons = []
    for dimension in DIMENSIONS:
        required = getattr(spec, SPEC_FIELDS[dimension])
        observed = getattr(candidate, dimension)
        if required is None:
            if observed is not None and _incompatible(dimension, observed, required or "", registry):
                states[dimension] = "INCOMPATIBLE"
                reasons.append("OPTIONAL_DIMENSION_INCOMPATIBLE_IGNORED")
            else:
                states[dimension] = "NOT_APPLICABLE"
            continue
        if observed is None:
            states[dimension] = "UNRESOLVED"
        elif observed == required:
            states[dimension] = "MATCH"
        elif _authorized(dimension, observed, required, spec, registry):
            states[dimension] = "AUTHORIZED_EQUIVALENT"
            reasons.append("AUTHORIZED_ENDPOINT_EQUIVALENCE")
        else:
            incompatible_reason = _incompatible(dimension, observed, required, registry)
            states[dimension] = "INCOMPATIBLE" if incompatible_reason else "UNRESOLVED"
            if incompatible_reason:
                reasons.append(incompatible_reason)
        generic = _dimension_reason(dimension, states[dimension])
        if generic:
            reasons.append(generic)
    required_states = [states[dimension] for dimension in spec.required_dimensions]
    if any(state == "INCOMPATIBLE" for state in required_states):
        overall = "INCOMPATIBLE"
    elif required_states and all(state == "MATCH" for state in required_states):
        overall = "EXACT"
    elif (required_states and all(state in {"MATCH", "AUTHORIZED_EQUIVALENT"} for state in required_states)
          and "AUTHORIZED_EQUIVALENT" in required_states):
        overall = "AUTHORIZED_EQUIVALENT"
    elif (any(state in {"MATCH", "AUTHORIZED_EQUIVALENT"} for state in required_states)
          and "UNRESOLVED" in required_states):
        overall = "PARTIAL"
    else:
        overall = "UNRESOLVED"
    if (spec.required_condition in {"glucose_stimulated", "stimulated"}
            and candidate.measurement_process in {"secretion", "release"}
            and candidate.measurement_condition is None):
        reasons.extend(["CONDITION_MISSING", "GENERIC_SECRETION_NOT_STIMULATED_SECRETION"])
    if candidate.endpoint_evidence_role == "CURRENT_STUDY_SURROGATE":
        reasons.append("SURROGATE_NOT_FUNCTIONAL_ENDPOINT")
    return states, overall, _unique(reasons)


def _empty_decision(packet_id: str, spec: EndpointTargetSpecV1, candidates, registry, policy,
                    reasons, role="UNRESOLVED_ROLE"):
    states = {dimension: "UNRESOLVED" if dimension in spec.required_dimensions else "NOT_APPLICABLE"
              for dimension in DIMENSIONS}
    return EndpointSemanticDecisionV1(
        packet_id=packet_id, applicable=bool(spec.required_dimensions),
        target_endpoint_spec=asdict(spec),
        observed_endpoint_candidates=tuple(asdict(candidate) for candidate in candidates),
        **{DECISION_FIELDS[dimension]: states[dimension] for dimension in DIMENSIONS},
        overall_state="UNRESOLVED", endpoint_evidence_role=role, matched_surfaces=(),
        reason_codes=tuple(_unique(reasons)), resolver_status="unresolved",
        registry_version=registry["registry_version"], policy_version=policy["policy_version"],
    )


def decide_endpoint_semantics_v1(packet_id: str, target: dict[str, Any], *, title: str,
                                 abstract: str, publication_metadata: dict[str, Any] | None,
                                 registry: dict[str, Any], policy: dict[str, Any]) -> EndpointSemanticDecisionV1:
    """Resolve endpoint compatibility without labels, fulltext, Tier, or other gate decisions."""
    if not policy.get("enabled") or not policy.get("shadow_only"):
        raise ValueError("EndpointSemanticsV1 requires enabled shadow-only policy")
    spec = build_endpoint_target_spec(target, registry)
    if not spec.required_dimensions:
        return _empty_decision(packet_id, spec, [], registry, policy,
                               ["TARGET_ENDPOINT_SPEC_UNRESOLVED"])
    candidates = extract_observed_candidates(
        target, spec, title=title, abstract=abstract, publication_metadata=publication_metadata,
        registry=registry, policy=policy,
    )
    if not candidates:
        return _empty_decision(packet_id, spec, [], registry, policy, ["NO_ENDPOINT_EVIDENCE"])
    current = [candidate for candidate in candidates if candidate.endpoint_evidence_role in {
        "CURRENT_STUDY_MEASUREMENT", "CURRENT_STUDY_SURROGATE"}]
    if not current:
        if any(candidate.endpoint_evidence_role == "BACKGROUND_ENDPOINT" for candidate in candidates):
            return _empty_decision(packet_id, spec, candidates, registry, policy,
                                   ["BACKGROUND_ENDPOINT_ONLY"], "BACKGROUND_ENDPOINT")
        return _empty_decision(packet_id, spec, candidates, registry, policy,
                               ["NO_ENDPOINT_EVIDENCE"])
    evaluated = [(candidate, *_evaluate_candidate(candidate, spec, registry)) for candidate in current]
    overall_values = {overall for _, _, overall, _ in evaluated}
    signatures = {(candidate.measurement_property, candidate.measurement_process,
                   candidate.measurement_state, candidate.measurement_compartment,
                   candidate.measurement_condition, candidate.response_context)
                  for candidate, _, _, _ in evaluated}
    if len(signatures) > 1 and ("INCOMPATIBLE" in overall_values or len(overall_values) > 1):
        return _empty_decision(packet_id, spec, current, registry, policy,
                               ["MULTIPLE_ENDPOINTS_UNRESOLVED"])
    rank = {"EXACT": 4, "AUTHORIZED_EQUIVALENT": 3, "PARTIAL": 2, "INCOMPATIBLE": 1, "UNRESOLVED": 0}
    candidate, states, overall, reasons = max(evaluated, key=lambda item: rank[item[2]])
    reasons.append("CURRENT_STUDY_ENDPOINT")
    if candidate.endpoint_evidence_role == "CURRENT_STUDY_SURROGATE":
        reasons.append("SURROGATE_NOT_FUNCTIONAL_ENDPOINT")
    reason_codes = tuple(_unique(reasons))
    unknown = set(reason_codes) - REASON_CODES
    if unknown:
        raise ValueError(f"unknown EndpointSemanticsV1 reason codes: {unknown}")
    return EndpointSemanticDecisionV1(
        packet_id=packet_id, applicable=True, target_endpoint_spec=asdict(spec),
        observed_endpoint_candidates=tuple(asdict(item) for item in candidates),
        **{DECISION_FIELDS[dimension]: states[dimension] for dimension in DIMENSIONS},
        overall_state=overall, endpoint_evidence_role=candidate.endpoint_evidence_role,
        matched_surfaces=({"surface": candidate.matched_surface, "field": candidate.source_field,
                           "sentence_index": candidate.sentence_index,
                           "source_sentence": candidate.source_sentence},),
        reason_codes=reason_codes, resolver_status="resolved" if overall != "UNRESOLVED" else "unresolved",
        registry_version=registry["registry_version"], policy_version=policy["policy_version"],
    )
