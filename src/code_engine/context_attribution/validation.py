from __future__ import annotations

import hashlib
import re
from typing import Any

from .models import ContextExtraction, ContextPairAttribution
from .registry import resolve_factors

_QUANTITY = re.compile(r"^\s*[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*(?:±|\+/-)\s*\d+(?:\.\d+)?)?\s*([%°µμA-Za-z][\w%°µμ./^-]*)?\s*$")

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def _anchors(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(x.get("anchor_id") or x.get("evidence_span_id")): x for x in contract.get("evidence_anchors", [])}

def _anchor_errors(contract: dict[str, Any]) -> list[str]:
    errors = []
    for aid, anchor in _anchors(contract).items():
        text = str(anchor.get("text") or "")
        if anchor.get("text_hash") and anchor["text_hash"] != _hash(text):
            errors.append(f"anchor_hash_mismatch:{aid}")
        start, end = anchor.get("char_start"), anchor.get("char_end")
        if start is not None and end is not None and (start < 0 or end < start):
            errors.append(f"anchor_offset_invalid:{aid}")
        source = contract.get("evidence_sentence") if contract.get("input_mode") == "abstract_sentence_only" else None
        if source is not None and start is not None and end is not None and source[start:end] != text:
            errors.append(f"anchor_offset_text_mismatch:{aid}")
    return errors

def validate_context_extraction(payload: ContextExtraction | dict[str, Any], contract: dict[str, Any],
                                profiles: list[str], *, accepted_normalizations: set[tuple[str, str]] | None = None
                                ) -> tuple[ContextExtraction, list[str]]:
    value = payload if isinstance(payload, ContextExtraction) else ContextExtraction.model_validate(payload)
    errors = _anchor_errors(contract)
    if value.observation_id != contract.get("observation_id"): errors.append("observation_id_mismatch")
    if value.input_mode != contract.get("input_mode"): errors.append("input_mode_mismatch")
    known, anchors = resolve_factors(profiles), _anchors(contract)
    accepted_normalizations = accepted_normalizations or set()
    for factor in value.context_factors:
        if factor.factor_id not in known:
            errors.append(f"unsupported_factor:{factor.factor_id}"); continue
        if factor.status != "unknown" and not factor.evidence_anchor_ids:
            errors.append(f"unbound_factor:{factor.factor_id}")
        for aid in factor.evidence_anchor_ids:
            if aid not in anchors: errors.append(f"anchor_not_in_observation:{factor.factor_id}:{aid}")
            elif value.input_mode == "abstract_sentence_only" and anchors[aid].get("source_role") != "abstract":
                errors.append(f"abstract_fulltext_anchor_forbidden:{aid}")
        if factor.evidence_text and factor.evidence_text not in {str(anchors[x].get("text")) for x in factor.evidence_anchor_ids if x in anchors}:
            errors.append(f"evidence_text_mismatch:{factor.factor_id}")
        bound_text = " ".join(str(anchors[x].get("text") or "") for x in factor.evidence_anchor_ids if x in anchors)
        if factor.status == "explicit" and factor.raw_value.casefold() not in bound_text.casefold():
            errors.append(f"explicit_value_not_in_evidence:{factor.factor_id}")
        if factor.factor_id in {"observed_outcome", "biological_endpoint", "yield", "selectivity", "conversion"}:
            if any(anchors[x].get("source_role") == "methods" for x in factor.evidence_anchor_ids if x in anchors):
                errors.append(f"methods_anchor_cannot_prove_result:{factor.factor_id}")
        definition = known[factor.factor_id]
        if definition["value_type"] in {"quantity", "duration", "integer"} and factor.status != "unknown":
            match = _QUANTITY.match(factor.raw_value)
            if not match: errors.append(f"value_not_parseable:{factor.factor_id}")
            elif definition["value_type"] == "integer" and not factor.raw_value.strip().isdigit():
                errors.append(f"value_not_integer:{factor.factor_id}")
            elif match.group(1) and definition.get("units") and match.group(1) not in definition["units"]:
                errors.append(f"unit_not_allowed:{factor.factor_id}:{match.group(1)}")
        if factor.normalized_value and factor.normalized_value != factor.raw_value:
            if (factor.factor_id, factor.normalized_value) not in accepted_normalizations:
                errors.append(f"normalization_unresolved:{factor.factor_id}")
        if factor.status == "conflicting" and factor.normalized_value not in {None, "unknown"}:
            errors.append(f"conflicting_factor_must_not_resolve:{factor.factor_id}")
    value.validation_status = "rejected" if errors else "validated"
    return value, errors

def validate_pair_attribution(payload: ContextPairAttribution | dict[str, Any], *,
                              pair_id: str, extraction_a: ContextExtraction,
                              extraction_b: ContextExtraction, profiles: list[str]
                              ) -> tuple[ContextPairAttribution, list[str]]:
    value = payload if isinstance(payload, ContextPairAttribution) else ContextPairAttribution.model_validate(payload)
    errors: list[str] = []
    if value.pair_id != pair_id: errors.append("pair_id_mismatch")
    if value.claim_a_observation_id != extraction_a.observation_id: errors.append("claim_a_observation_id_mismatch")
    if value.claim_b_observation_id != extraction_b.observation_id: errors.append("claim_b_observation_id_mismatch")
    known = resolve_factors(profiles)
    values_a = {x.factor_id: x.raw_value for x in extraction_a.context_factors}
    values_b = {x.factor_id: x.raw_value for x in extraction_b.context_factors}
    anchors_a = {x for f in extraction_a.context_factors for x in f.evidence_anchor_ids}
    anchors_b = {x for f in extraction_b.context_factors for x in f.evidence_anchor_ids}
    for factor in value.factor_comparisons:
        if factor.factor_id not in known: errors.append(f"unsupported_factor:{factor.factor_id}")
        for aid in factor.claim_a_anchor_ids:
            if aid not in anchors_a: errors.append(f"claim_a_cross_or_unknown_anchor:{aid}")
            if aid in anchors_b: errors.append(f"claim_a_anchor_cross_referenced:{aid}")
        for aid in factor.claim_b_anchor_ids:
            if aid not in anchors_b: errors.append(f"claim_b_cross_or_unknown_anchor:{aid}")
            if aid in anchors_a: errors.append(f"claim_b_anchor_cross_referenced:{aid}")
        if factor.status.startswith("missing") and factor.comparability_effect == "none":
            errors.append(f"missing_factor_treated_as_same:{factor.factor_id}")
        if factor.comparability_effect == "blocking" and not known.get(factor.factor_id, {}).get("whether_difference_can_block_comparability"):
            errors.append(f"unregistered_blocking_factor:{factor.factor_id}")
        if factor.status == "equivalent" and known.get(factor.factor_id, {}).get("value_type") in {"quantity", "duration"}:
            if not _quantities_equivalent(values_a.get(factor.factor_id, factor.claim_a_value),
                                          values_b.get(factor.factor_id, factor.claim_b_value)):
                errors.append(f"unsafe_unit_equivalence:{factor.factor_id}")
    value.validation_status = "rejected" if errors else "validated"
    return value, errors

def _quantities_equivalent(left: str, right: str) -> bool:
    conversions = {
        "M": ("molar", 1.0, 0.0), "mM": ("molar", 1e-3, 0.0),
        "uM": ("molar", 1e-6, 0.0), "µM": ("molar", 1e-6, 0.0), "μM": ("molar", 1e-6, 0.0),
        "nM": ("molar", 1e-9, 0.0), "Pa": ("pressure", 1.0, 0.0),
        "kPa": ("pressure", 1000.0, 0.0), "bar": ("pressure", 100000.0, 0.0),
        "atm": ("pressure", 101325.0, 0.0), "K": ("temperature", 1.0, 0.0),
        "C": ("temperature", 1.0, 273.15), "°C": ("temperature", 1.0, 273.15),
        "s": ("time", 1.0, 0.0), "min": ("time", 60.0, 0.0),
        "h": ("time", 3600.0, 0.0), "day": ("time", 86400.0, 0.0),
        "week": ("time", 604800.0, 0.0),
    }
    parsed = []
    for raw in (left, right):
        match = _QUANTITY.match(str(raw))
        if not match or not match.group(1) or match.group(1) not in conversions: return False
        number = float(re.match(r"\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))", str(raw)).group(1))
        family, scale, offset = conversions[match.group(1)]
        parsed.append((family, number * scale + offset))
    return parsed[0][0] == parsed[1][0] and abs(parsed[0][1] - parsed[1][1]) <= max(1e-9, abs(parsed[0][1]) * 1e-6)
