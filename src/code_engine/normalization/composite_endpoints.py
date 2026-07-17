"""Conservative decomposition and projection for composite assay endpoints."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "observation_endpoint_schema.v1"
DECOMPOSITION_VERSION = "endpoint_decomposition.deterministic.v1"
DIMENSION_CLASSIFIER_VERSION = "measurement_dimension_classifier.v1"
PROJECTION_RULE_VERSION = "core_projection_rules.v1"
GRAPH_PROJECTION_VERSION = "graph_projection.v1"

MOLECULAR_DIMENSIONS = {"expression", "abundance", "phosphorylation", "activity", "localization"}
NON_MOLECULAR_PATTERNS = (
    (re.compile(r"^\s*cell viability\s*$", re.I), "phenotype"),
    (re.compile(r"^\s*tumou?r volume\s*$", re.I), "phenotype"),
    (re.compile(r"^\s*migration ability\s*$", re.I), "phenotype"),
    (re.compile(r"^\s*invasion rate\s*$", re.I), "phenotype"),
    (re.compile(r"^\s*drug resistance\s*$", re.I), "clinical_outcome"),
    (re.compile(r"^\s*overall survival\s*$", re.I), "clinical_outcome"),
    (re.compile(r"^\s*absorbance at \d+\s*nm\s*$", re.I), "assay_readout"),
    (re.compile(r"^\s*cell viability measured by .+\s*$", re.I), "assay_readout"),
)


@dataclass(frozen=True)
class EndpointDecomposition:
    endpoint_raw: str
    endpoint_type: str
    measured_entity_raw: str | None = None
    measured_entity_cleaned: str | None = None
    measurement_dimension: str | None = None
    measurement_state: str | None = None
    molecular_layer: str | None = None
    endpoint_decomposition_status: str = "not_composite"
    endpoint_decomposition_method: str = "deterministic"
    endpoint_decomposition_confidence: float = 0.0
    non_molecular_readout: bool = False

    def to_endpoint_fields(self) -> dict[str, Any]:
        return {
            "endpoint_raw": self.endpoint_raw,
            "endpoint_type": self.endpoint_type,
            "measured_entity_raw": self.measured_entity_raw,
            "measured_entity_cleaned": self.measured_entity_cleaned,
            "measured_entity_canonical_id": None,
            "measured_entity_canonical_name": None,
            "measured_entity_type": None,
            "measured_entity_resolution_status": None,
            "measured_entity_decision_id": None,
            "measurement_dimension": self.measurement_dimension,
            "measurement_state": self.measurement_state,
            "measurement_direction": None,
            "molecular_layer": self.molecular_layer,
            "endpoint_decomposition_status": self.endpoint_decomposition_status,
            "endpoint_decomposition_method": self.endpoint_decomposition_method,
            "endpoint_decomposition_confidence": self.endpoint_decomposition_confidence,
            "core_projection_status": "unsupported" if self.non_molecular_readout else "excluded",
            "core_projection_relation": None,
            "core_projection_reason": "non_molecular_readout" if self.non_molecular_readout else None,
            "schema_version": SCHEMA_VERSION,
            "endpoint_decomposition_version": DECOMPOSITION_VERSION,
            "measurement_dimension_classifier_version": DIMENSION_CLASSIFIER_VERSION,
            "core_projection_rule_version": PROJECTION_RULE_VERSION,
            "graph_projection_version": GRAPH_PROJECTION_VERSION,
        }


def _clean_entity(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -:;,.")


def decompose_endpoint(raw: str, endpoint_type: str | None = None) -> EndpointDecomposition:
    text = _clean_entity(raw)
    etype = endpoint_type or "unknown"
    if not text:
        return EndpointDecomposition(endpoint_raw=text, endpoint_type=etype, endpoint_decomposition_status="unsupported")
    for pattern, readout_type in NON_MOLECULAR_PATTERNS:
        if pattern.match(text):
            return EndpointDecomposition(
                endpoint_raw=text,
                endpoint_type=readout_type,
                measurement_dimension="other",
                endpoint_decomposition_status="unsupported",
                endpoint_decomposition_confidence=0.95,
                non_molecular_readout=True,
            )

    rules: tuple[tuple[re.Pattern[str], str, str | None, str | None], ...] = (
        (re.compile(r"^(.+?)\s+mRNA expression$", re.I), "expression", None, "mRNA"),
        (re.compile(r"^(.+?)\s+protein expression$", re.I), "expression", None, "protein"),
        (re.compile(r"^(.+?)\s+expression$", re.I), "expression", None, None),
        (re.compile(r"^(.+?)\s+protein level$", re.I), "abundance", None, "protein"),
        (re.compile(r"^(.+?)\s+level$", re.I), "abundance", None, None),
        (re.compile(r"^(.+?)\s+abundance$", re.I), "abundance", None, None),
        (re.compile(r"^(.+?)\s+phosphorylation$", re.I), "phosphorylation", None, None),
        (re.compile(r"^phosphorylated\s+(.+?)$", re.I), "phosphorylation", "phosphorylated", None),
        (re.compile(r"^(.+?)\s+activation$", re.I), "activity", "activated", None),
        (re.compile(r"^(.+?)\s+activity$", re.I), "activity", None, None),
        (re.compile(r"^(.+?)\s+localization$", re.I), "localization", None, None),
        (re.compile(r"^nuclear\s+(.+?)$", re.I), "localization", "nuclear", None),
        (re.compile(r"^cytoplasmic\s+(.+?)$", re.I), "localization", "cytoplasmic", None),
    )
    for pattern, dimension, state, layer in rules:
        match = pattern.match(text)
        if match:
            measured = _clean_entity(match.group(1))
            return EndpointDecomposition(
                endpoint_raw=text,
                endpoint_type="assay_readout" if etype in {"", "unknown"} else etype,
                measured_entity_raw=measured,
                measured_entity_cleaned=measured,
                measurement_dimension=dimension,
                measurement_state=state,
                molecular_layer=layer,
                endpoint_decomposition_status="decomposed",
                endpoint_decomposition_confidence=0.95,
            )
    return EndpointDecomposition(endpoint_raw=text, endpoint_type=etype, endpoint_decomposition_confidence=0.0)


POSITIVE_RELATIONS = {"increase", "increases", "increased", "upregulate", "upregulates", "upregulated", "enhance", "enhances", "enhanced", "activate", "activates", "activated", "promote", "promotes", "promoted", "positive"}
NEGATIVE_RELATIONS = {"decrease", "decreases", "decreased", "downregulate", "downregulates", "downregulated", "suppress", "suppresses", "suppressed", "reduce", "reduces", "reduced", "inhibit", "inhibits", "inhibited", "negative"}


def relation_direction(item: dict[str, Any]) -> str | None:
    values = [item.get("direction"), item.get("relation_raw"), item.get("relation_family"), item.get("polarity_type")]
    text = " ".join(str(value or "").casefold().replace("_", " ") for value in values)
    tokens = set(re.findall(r"[a-z]+", text))
    if tokens & POSITIVE_RELATIONS:
        return "positive"
    if tokens & NEGATIVE_RELATIONS:
        return "negative"
    sign = item.get("relation_sign")
    if sign in (1, "+1", "positive"):
        return "positive"
    if sign in (-1, "-1", "negative"):
        return "negative"
    return None


def projection_relation(item: dict[str, Any], endpoint: dict[str, Any]) -> tuple[str | None, str | None]:
    direction = relation_direction(item)
    dimension = endpoint.get("measurement_dimension")
    state = endpoint.get("measurement_state")
    if direction is None:
        return None, "relation_projection_not_supported"
    if dimension == "expression":
        return ("increases_expression_of" if direction == "positive" else "decreases_expression_of"), None
    if dimension == "abundance":
        return ("increases_abundance_of" if direction == "positive" else "decreases_abundance_of"), None
    if dimension == "phosphorylation":
        return ("increases_phosphorylation_of" if direction == "positive" else "decreases_phosphorylation_of"), None
    if dimension == "activity":
        return ("increases_activity_of" if direction == "positive" else "decreases_activity_of"), None
    if dimension == "localization" and state == "nuclear":
        return ("promotes_nuclear_localization_of" if direction == "positive" else "reduces_nuclear_localization_of"), None
    return None, "relation_projection_not_supported"


def endpoint_with_resolution(endpoint: dict[str, Any], decision: Any, decision_id: str) -> dict[str, Any]:
    status = getattr(decision, "normalization_status", None) or "unresolved_fallback"
    if status == "resolved":
        endpoint.update({
            "measured_entity_canonical_id": getattr(decision, "canonical_id", "") or None,
            "measured_entity_canonical_name": getattr(decision, "canonical_name", "") or None,
            "measured_entity_type": getattr(decision, "entity_type", "") or None,
        })
    endpoint.update({
        "measured_entity_resolution_status": status,
        "measured_entity_decision_id": decision_id,
    })
    return endpoint


def apply_core_projection(item: dict[str, Any], role: str, endpoint: dict[str, Any], *, claim_graph_eligible: bool) -> dict[str, Any]:
    endpoint = dict(endpoint)
    if endpoint.get("endpoint_decomposition_status") != "decomposed":
        if endpoint.get("core_projection_reason") is None:
            endpoint["core_projection_status"] = "excluded"
            endpoint["core_projection_reason"] = "composite_endpoint_not_decomposed"
        return endpoint
    if float(endpoint.get("endpoint_decomposition_confidence") or 0.0) < 0.9:
        endpoint.update(core_projection_status="excluded", core_projection_reason="low_decomposition_confidence")
        return endpoint
    if endpoint.get("measured_entity_resolution_status") != "resolved" or not endpoint.get("measured_entity_canonical_id"):
        reason = "canonicalization_ambiguous" if endpoint.get("measured_entity_resolution_status") == "ambiguous" else "canonicalization_unresolved"
        endpoint.update(core_projection_status="excluded", core_projection_reason=reason)
        return endpoint
    relation, reason = projection_relation(item, endpoint)
    if not relation:
        endpoint.update(core_projection_status="unsupported", core_projection_reason=reason or "relation_projection_not_supported")
        return endpoint
    if not claim_graph_eligible:
        endpoint.update(core_projection_status="excluded", core_projection_relation=relation, core_projection_reason="graph_eligibility_rejected")
        return endpoint
    endpoint.update(core_projection_status="projected", core_projection_relation=relation, core_projection_reason="successfully_projected")
    return endpoint
