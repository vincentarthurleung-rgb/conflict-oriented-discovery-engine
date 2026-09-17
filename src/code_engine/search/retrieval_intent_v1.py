"""Generic proposition-semantic retrieval intents for Search Plan v2.4-dev."""

from __future__ import annotations

from typing import Any


INTENT_VERSION = "RetrievalIntentV1"
INTENT_ORDER = (
    "DIRECT_PERTURBATION",
    "INVERSE_PERTURBATION",
    "NECESSITY",
    "RESCUE",
    "FUNCTIONAL_CHAIN",
    "THERAPY_SENSITIZATION",
    "THERAPY_RESISTANCE",
    "ENDPOINT_SPECIFIC",
    "CONTEXT_SPECIFIC",
)

DIMENSION_ORDER = (
    "subject",
    "relation",
    "object_measurement_target",
    "endpoint_property",
    "biological_unit",
    "therapy",
    "disease",
    "genotype",
    "nested_treatment",
    "direction",
    "evidence_mode",
)

MINIMUM_REQUIRED_DIMENSIONS = {
    "DIRECT_PERTURBATION": ("subject", "relation", "object_measurement_target", "direction", "evidence_mode"),
    "INVERSE_PERTURBATION": ("subject", "relation", "object_measurement_target", "direction", "evidence_mode"),
    "NECESSITY": ("subject", "relation", "object_measurement_target", "evidence_mode"),
    "RESCUE": ("subject", "relation", "object_measurement_target", "direction", "evidence_mode"),
    "FUNCTIONAL_CHAIN": ("subject", "relation", "object_measurement_target", "evidence_mode"),
    "THERAPY_SENSITIZATION": ("subject", "relation", "therapy", "direction", "evidence_mode"),
    "THERAPY_RESISTANCE": ("subject", "relation", "therapy", "direction", "evidence_mode"),
    "ENDPOINT_SPECIFIC": ("object_measurement_target", "endpoint_property", "evidence_mode"),
    "CONTEXT_SPECIFIC": ("evidence_mode",),
}


class RetrievalIntentError(ValueError):
    """Raised when a retrieval intent violates the frozen generic contract."""


def _text(target: dict[str, Any]) -> str:
    values = [
        target.get("relation_family"),
        target.get("canonical_relation_family"),
        target.get("canonical_proposition_orientation"),
        target.get("subject_intervention"),
        target.get("measurement_property_endpoint"),
        target.get("required_evidence_mode"),
        *(target.get("acceptable_endpoint_evidence") or []),
    ]
    return " ".join(str(value or "") for value in values).casefold()


def _contexts(target: dict[str, Any]) -> dict[str, list[str]]:
    raw = target.get("context_qualifier_dimensions") or {}
    return {
        str(key): [str(value) for value in (values if isinstance(values, list) else [values]) if str(value).strip()]
        for key, values in raw.items()
    }


def applicable_intent_types(target: dict[str, Any]) -> list[str]:
    """Return generic applicable intents from proposition semantics, never case identity."""
    if target.get("artifact_schema_version") != "ScientificPropositionTargetV1":
        raise RetrievalIntentError("unsupported scientific proposition target schema")
    core = all(str(target.get(field) or "").strip() for field in ("subject", "relation_family", "object"))
    if not core:
        raise RetrievalIntentError("subject, relation_family, and object are required")
    text = _text(target)
    contexts = _contexts(target)
    intents = ["DIRECT_PERTURBATION"]
    if any(token in text for token in ("inhibit", "loss", "block", "deplet", "knockdown", "reduced", "inverse")):
        intents.append("INVERSE_PERTURBATION")
    if any(token in text for token in ("necess", "required for", "dependency", "dependence")):
        intents.append("NECESSITY")
    if any(token in text for token in ("rescue", "restor", "reversal", "reverse")):
        intents.append("RESCUE")
    if any(token in text for token in ("functional", "mechanis", "linked to", "linking")):
        intents.append("FUNCTIONAL_CHAIN")
    therapy = str(target.get("therapy") or "").strip() or bool(contexts.get("therapy"))
    if therapy and any(token in text for token in ("sensit", "increased response", "decreased resistance")):
        intents.append("THERAPY_SENSITIZATION")
    if therapy and any(token in text for token in ("increases resistance", "decreased resistance", "resistance to", "reduced response")):
        intents.append("THERAPY_RESISTANCE")
    if str(target.get("measurement_property_endpoint") or "").strip():
        intents.append("ENDPOINT_SPECIFIC")
    if any(contexts.values()) or target.get("context_qualifiers"):
        intents.append("CONTEXT_SPECIFIC")
    selected = set(intents)
    return [name for name in INTENT_ORDER if name in selected]


def validate_intent(intent: dict[str, Any], target: dict[str, Any]) -> None:
    intent_type = intent.get("intent_type")
    if intent_type not in INTENT_ORDER:
        raise RetrievalIntentError(f"unknown intent type: {intent_type!r}")
    if intent.get("applicability") not in {"APPLICABLE", "NOT_APPLICABLE"}:
        raise RetrievalIntentError("intent applicability must be explicit")
    required = intent.get("required_dimensions")
    optional = intent.get("optional_dimensions")
    if not isinstance(required, list) or not isinstance(optional, list):
        raise RetrievalIntentError("intent dimensions must be lists")
    if set(required) - set(DIMENSION_ORDER) or set(optional) - set(DIMENSION_ORDER):
        raise RetrievalIntentError("intent contains unknown proposition dimension")
    if set(required) & set(optional):
        raise RetrievalIntentError("required and optional dimensions overlap")
    if not set(MINIMUM_REQUIRED_DIMENSIONS[intent_type]).issubset(required):
        raise RetrievalIntentError(f"{intent_type} omits minimum required dimensions")
    unit = intent.get("biological_unit_context")
    if not isinstance(unit, dict) or unit.get("separate_from_entity_identity") is not True:
        raise RetrievalIntentError("biological unit must remain separate from entity identity")
    if intent.get("applicability") == "APPLICABLE" and intent_type not in applicable_intent_types(target):
        raise RetrievalIntentError(f"intent is not proposition-semantically applicable: {intent_type}")


__all__ = [
    "DIMENSION_ORDER",
    "INTENT_ORDER",
    "INTENT_VERSION",
    "MINIMUM_REQUIRED_DIMENSIONS",
    "RetrievalIntentError",
    "applicable_intent_types",
    "validate_intent",
]
