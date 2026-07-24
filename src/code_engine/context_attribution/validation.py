from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from .composition import (
    COMPOSER_VERSION, COMPOSITION_POLICY_VERSION, compose, composition_identity,
    load_composition_policy,
)
from .models import ContextExtraction, ContextPairAttribution
from .registry import resolve_factors
from .token_spans import (
    ANCHOR_TOKENIZER_VERSION, EXPLICIT_SPAN_VERSION, SPAN_HYDRATOR_VERSION,
    resolve_explicit_span,
)

VALIDATOR_VERSION = "context_attribution_validator_v4"
RECOVERY_VALIDATOR_VERSION = "context_attribution_validator_v5"
HYDRATOR_VERSION = "context_attribution_anchor_hydrator_v3"
LOCAL_CHAIN_INFERENCE_POLICY_VERSION = COMPOSITION_POLICY_VERSION

_QUANTITY = re.compile(r"^\s*[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*(?:±|\+/-)\s*\d+(?:\.\d+)?)?\s*([%°µμA-Za-z][\w%°µμ./^-]*)?\s*$")

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def _anchors(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(x.get("anchor_id") or x.get("evidence_span_id")): x for x in contract.get("evidence_anchors", [])}

def _surface(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    normalized = "".join(" " if unicodedata.category(char)[0] in {"P", "Z"} else char
                         for char in normalized)
    return " ".join(normalized.split())

def _surface_present(raw_value: str, text: str) -> bool:
    needle, haystack = _surface(raw_value), _surface(text)
    return bool(needle and needle in haystack)

def _chain_nodes(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    chain = contract.get("experimental_logic_chain") or {}
    return {str(key): value for key, value in chain.items() if isinstance(value, dict)}


def _field_candidates(value: Any, field_path: str, locator: str = "value") -> list[tuple[str, Any, str]]:
    """Resolve an allowlisted field path without accepting arbitrary flattened JSON text."""
    parts = field_path.split(".")
    if not all(parts) or any(part.isdigit() for part in parts):
        return []

    def walk(current: Any, remaining: list[str], here: str) -> list[tuple[str, Any, str]]:
        if isinstance(current, list):
            return [
                item
                for index, child in enumerate(current)
                for item in walk(child, remaining, f"{here}[{index}]")
            ]
        if not isinstance(current, dict) or not remaining or remaining[0] not in current:
            return []
        child = current[remaining[0]]
        child_path = f"{here}.{remaining[0]}"
        if len(remaining) == 1:
            return [(child_path, child, here)]
        return walk(child, remaining[1:], child_path)

    return walk(value, parts, locator)

def hydrate_context_extraction(payload: ContextExtraction | dict[str, Any],
                               contract: dict[str, Any]) -> tuple[ContextExtraction, dict[str, Any]]:
    """Replace model-authored evidence copies with authoritative contract spans."""
    value = payload if isinstance(payload, ContextExtraction) else ContextExtraction.model_validate(payload)
    anchors = _anchors(contract)
    contract_order = {aid: index for index, aid in enumerate(anchors)}
    hydrated_factors = []
    for factor in value.context_factors:
        supplied_text = factor.evidence_text
        unique = list(dict.fromkeys(factor.evidence_anchor_ids))
        valid = sorted((aid for aid in unique if aid in anchors), key=contract_order.get)
        invalid = [aid for aid in unique if aid not in anchors]
        factor.evidence_anchor_ids = [*valid, *invalid]
        factor.authoritative_evidence = [
            {
                "anchor_id": aid,
                "text": str(anchors[aid].get("text") or ""),
                "text_hash": anchors[aid].get("text_hash"),
                "char_start": anchors[aid].get("char_start"),
                "char_end": anchors[aid].get("char_end"),
                "source_section": anchors[aid].get("source_section"),
                "source_role": anchors[aid].get("source_role"),
            }
            for aid in valid
        ]
        factor.evidence_text = "\n\n".join(item["text"] for item in factor.authoritative_evidence) or None
        span_resolution, span_error = (None, None)
        if factor.status == "explicit" and not factor.legacy_unverifiable:
            span_resolution, span_error = resolve_explicit_span(factor.explicit_span, anchors)
            if span_resolution is not None:
                factor.raw_value = span_resolution["raw_value"]
                factor.raw_value_source = "explicit_token_span"
                factor.explicit_span_resolution = span_resolution
        hydrated_factors.append({
            "factor_id": factor.factor_id,
            "authoritative_anchor_ids": valid,
            "unknown_anchor_ids": invalid,
            "model_evidence_text_ignored": supplied_text is not None,
            "model_evidence_text_matched_authority": (
                supplied_text is None or supplied_text == factor.evidence_text
            ),
            "explicit_span_resolution": span_resolution,
            "explicit_span_error": span_error,
        })
    audit = {
        "hydrator_version": HYDRATOR_VERSION,
        "authoritative_source": "observation_contract",
        "factors": hydrated_factors,
    }
    value.provenance = {**value.provenance, "deterministic_hydration": audit}
    return value, audit

def _resolve_normalization(factor: Any, definition: dict[str, Any],
                           accepted: set[tuple[str, str]]) -> str | None:
    candidate = factor.normalized_value or factor.normalized_candidate
    if factor.status == "unknown":
        factor.normalized_value = None
        factor.normalized_candidate = None
        factor.normalization_status = "not_applicable"
        factor.normalization_provenance = {"validator_version": VALIDATOR_VERSION}
        return None
    if not candidate:
        factor.normalized_value = None
        factor.normalization_status = "not_requested"
        factor.normalization_provenance = {"validator_version": VALIDATOR_VERSION}
        if definition.get("normalization_policy") == "resolver_acceptance_required":
            return f"normalization_required:{factor.factor_id}"
        return None
    factor.normalized_candidate = candidate
    source_value = factor.raw_value or factor.composed_value
    if candidate == source_value:
        factor.normalized_value = candidate
        factor.normalization_status = "resolved_identity"
        factor.normalization_provenance = {"resolver": "identity", "validator_version": VALIDATOR_VERSION}
        return None
    if (factor.factor_id, candidate) in accepted:
        factor.normalized_value = candidate
        factor.normalization_status = "resolved_supplied"
        factor.normalization_provenance = {"resolver": "accepted_normalizations",
                                           "validator_version": VALIDATOR_VERSION}
        return None
    mappings = definition.get("controlled_normalizations") or {}
    resolved = mappings.get(_surface(source_value))
    if resolved == candidate:
        factor.normalized_value = candidate
        factor.normalization_status = "resolved_controlled"
        factor.normalization_provenance = {
            "resolver": "context_registry_controlled_mapping",
            "mapping_key": _surface(source_value),
            "validator_version": VALIDATOR_VERSION,
        }
        return None
    factor.normalized_value = None
    factor.normalization_status = "unresolved_candidate"
    factor.normalization_provenance = {"resolver": "context_registry_controlled_mapping",
                                       "validator_version": VALIDATOR_VERSION}
    if definition.get("normalization_policy") == "resolver_acceptance_required":
        return f"normalization_unresolved:{factor.factor_id}"
    return None

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
                                profiles: list[str], *, accepted_normalizations: set[tuple[str, str]] | None = None,
                                registry: dict[str, Any] | None = None,
                                ) -> tuple[ContextExtraction, list[str]]:
    provider_composed = isinstance(payload, dict) and any(
        "composed_value" in factor and factor.get("composed_value") is not None
        for factor in payload.get("context_factors", [])
    )
    value, hydration_audit = hydrate_context_extraction(payload, contract)
    errors = _anchor_errors(contract)
    if provider_composed:
        errors.append("provider_composed_value_forbidden")
    if value.observation_id != contract.get("observation_id"): errors.append("observation_id_mismatch")
    if value.input_mode != contract.get("input_mode"): errors.append("input_mode_mismatch")
    known, anchors, chain_nodes = resolve_factors(profiles, registry), _anchors(contract), _chain_nodes(contract)
    accepted_normalizations = accepted_normalizations or set()
    hydration_by_factor = {
        item["factor_id"]: item for item in hydration_audit.get("factors", [])
    }
    for factor in value.context_factors:
        if factor.factor_id not in known:
            errors.append(f"unsupported_factor:{factor.factor_id}"); continue
        if factor.status != "unknown" and not factor.evidence_anchor_ids:
            errors.append(f"unbound_factor:{factor.factor_id}")
        if factor.legacy_unverifiable and factor.status == "inferred_from_local_chain":
            errors.append(f"legacy_local_inference_unverifiable:{factor.factor_id}")
        if factor.legacy_unverifiable and factor.status == "explicit":
            errors.append(f"legacy_explicit_span_unverifiable:{factor.factor_id}")
        for aid in factor.evidence_anchor_ids:
            if aid not in anchors: errors.append(f"anchor_not_in_observation:{factor.factor_id}:{aid}")
            elif value.input_mode == "abstract_sentence_only" and anchors[aid].get("source_role") != "abstract":
                errors.append(f"abstract_fulltext_anchor_forbidden:{aid}")
        if factor.status == "explicit" and not factor.legacy_unverifiable:
            span_error = hydration_by_factor.get(factor.factor_id, {}).get("explicit_span_error")
            if span_error:
                errors.append(f"{span_error}:{factor.factor_id}")
            if factor.explicit_span and factor.evidence_anchor_ids != [
                factor.explicit_span.evidence_anchor_id
            ]:
                errors.append(f"explicit_span_anchor_binding_mismatch:{factor.factor_id}")
        if factor.status == "inferred_from_local_chain":
            if value.input_mode != "fulltext_evidence_chain":
                errors.append(f"local_inference_requires_fulltext:{factor.factor_id}")
            if not factor.source_chain_node_ids:
                errors.append(f"local_inference_missing_chain_node:{factor.factor_id}")
            unknown_nodes = [node for node in factor.source_chain_node_ids if node not in chain_nodes]
            for node in unknown_nodes:
                errors.append(f"local_inference_unknown_chain_node:{factor.factor_id}:{node}")
            policy, _ = load_composition_policy()
            rule = policy["rules"].get(factor.inference_rule or "")
            if not rule or factor.factor_id not in rule.get("factor_ids", []):
                errors.append(f"local_inference_rule_not_allowed:{factor.factor_id}")
                rule = None
            expected = (rule or {}).get("components", [])
            actual_shape = [
                {"chain_node_id": item.chain_node_id, "field_path": item.field_path}
                for item in factor.raw_components
            ]
            expected_shape = [
                {"chain_node_id": item["chain_node_id"], "field_path": item["field_path"]}
                for item in expected
            ]
            if rule and actual_shape != expected_shape:
                errors.append(f"local_inference_component_order_or_shape_invalid:{factor.factor_id}")
            seen: set[tuple[str, str, str]] = set()
            provenance: list[dict[str, Any]] = []
            record_locators: dict[str, set[str]] = {}
            for index, component in enumerate(factor.raw_components):
                key = (component.chain_node_id, component.field_path, _surface(component.surface))
                if key in seen:
                    errors.append(f"local_inference_duplicate_component:{factor.factor_id}:{index}")
                seen.add(key)
                node = chain_nodes.get(component.chain_node_id)
                if node is None:
                    continue
                node_anchors = {
                    str(aid) for aid in node.get("authoritative_evidence_anchor_ids", [])
                }
                if not set(component.evidence_anchor_ids) <= node_anchors:
                    errors.append(
                        f"local_inference_component_anchor_not_bound_to_node:{factor.factor_id}:{index}"
                    )
                candidates = _field_candidates(node.get("value"), component.field_path)
                non_null = [(path, field_value, locator) for path, field_value, locator in candidates
                            if field_value is not None]
                if not non_null:
                    errors.append(
                        f"local_inference_component_field_missing_or_null:{factor.factor_id}:{index}"
                    )
                    continue
                matches = [item for item in non_null if component.surface == str(item[1])]
                if len(matches) != 1:
                    reason = "surface_not_in_field" if not matches else "field_ambiguous"
                    errors.append(
                        f"local_inference_component_{reason}:{factor.factor_id}:{index}"
                    )
                    continue
                path, field_value, locator = matches[0]
                slot = expected[index] if index < len(expected) else {}
                record_locators.setdefault(component.chain_node_id, set()).add(locator)
                provenance.append({
                    "component_index": index,
                    "chain_node_id": component.chain_node_id,
                    "field_path": component.field_path,
                    "resolved_field_path": path,
                    "authoritative_field_value": field_value,
                    "surface": component.surface,
                    "evidence_anchor_ids": component.evidence_anchor_ids,
                    "authoritative_evidence": [
                        {
                            "anchor_id": aid,
                            "text": str(anchors[aid].get("text") or ""),
                            "text_hash": anchors[aid].get("text_hash"),
                            "char_start": anchors[aid].get("char_start"),
                            "char_end": anchors[aid].get("char_end"),
                            "source_section": anchors[aid].get("source_section") or anchors[aid].get("section"),
                            "source_role": anchors[aid].get("source_role"),
                        }
                        for aid in component.evidence_anchor_ids if aid in anchors
                    ],
                })
            for node_id, locators in record_locators.items():
                if len(locators) > 1 and sum(
                    x.chain_node_id == node_id for x in factor.raw_components
                ) > 1:
                    errors.append(
                        f"local_inference_components_cross_node_records:{factor.factor_id}:{node_id}"
                    )
            component_anchor_ids = list(dict.fromkeys(
                aid for item in factor.raw_components for aid in item.evidence_anchor_ids
            ))
            if factor.evidence_anchor_ids != component_anchor_ids:
                errors.append(f"local_inference_factor_anchors_must_match_components:{factor.factor_id}")
            if len(provenance) == len(factor.raw_components) and rule:
                factor.composed_value = compose(
                    rule, [item.surface for item in factor.raw_components]
                )
                factor.composition_rule = factor.inference_rule
                factor.composition_provenance = provenance
                comparator_classes = rule.get("optional_normalized_classes") or {}
                if factor.factor_id in {"comparator", "placebo_or_standard_care"}:
                    factor.normalization_provenance["comparator_normalization_policy_version"] = (
                        "context_comparator_normalization_v1"
                    )
                    if factor.normalized_candidate is not None:
                        expected_class = comparator_classes.get(factor.composed_value)
                        if factor.normalized_candidate != expected_class:
                            errors.append(
                                f"comparator_normalized_class_unresolved:{factor.factor_id}"
                            )
        elif factor.source_chain_node_ids or factor.inference_rule:
            errors.append(f"chain_provenance_on_non_inferred_factor:{factor.factor_id}")
        if factor.factor_id in {"observed_outcome", "biological_endpoint", "yield", "selectivity", "conversion"}:
            if any(anchors[x].get("source_role") == "methods" for x in factor.evidence_anchor_ids if x in anchors):
                errors.append(f"methods_anchor_cannot_prove_result:{factor.factor_id}")
        definition = known[factor.factor_id]
        if definition["value_type"] in {"quantity", "duration", "integer"} and factor.status != "unknown":
            effective_value = factor.raw_value or factor.composed_value or ""
            match = _QUANTITY.match(effective_value)
            if not match: errors.append(f"value_not_parseable:{factor.factor_id}")
            elif definition["value_type"] == "integer" and not effective_value.strip().isdigit():
                errors.append(f"value_not_integer:{factor.factor_id}")
            elif match.group(1) and definition.get("units") and match.group(1) not in definition["units"]:
                errors.append(f"unit_not_allowed:{factor.factor_id}:{match.group(1)}")
        normalization_error = _resolve_normalization(factor, definition, accepted_normalizations)
        if normalization_error:
            errors.append(normalization_error)
        if factor.status == "conflicting" and factor.normalized_value not in {None, "unknown"}:
            errors.append(f"conflicting_factor_must_not_resolve:{factor.factor_id}")
    value.validation_status = "rejected" if errors else "validated"
    value.provenance["deterministic_validation"] = {
        "validator_version": VALIDATOR_VERSION,
        "hydrator_version": HYDRATOR_VERSION,
        "anchor_tokenizer_version": ANCHOR_TOKENIZER_VERSION,
        "explicit_span_version": EXPLICIT_SPAN_VERSION,
        "explicit_span_hydrator_version": SPAN_HYDRATOR_VERSION,
        "local_chain_inference_policy_version": LOCAL_CHAIN_INFERENCE_POLICY_VERSION,
        **composition_identity(),
        "valid": not errors,
        "errors": list(errors),
        "hydration": hydration_audit,
    }
    return value, errors


def validate_context_extraction_v5(
    payload: ContextExtraction | dict[str, Any], contract: dict[str, Any],
    profiles: list[str], *, accepted_normalizations: set[tuple[str, str]] | None = None,
    registry: dict[str, Any] | None = None,
) -> tuple[ContextExtraction, list[str]]:
    """v5 wrapper: v6 anchor authority is derived before this full validator."""
    value, errors = validate_context_extraction(
        payload, contract, profiles,
        accepted_normalizations=accepted_normalizations, registry=registry,
    )
    audit = value.provenance.get("deterministic_validation") or {}
    audit["base_validator_version"] = VALIDATOR_VERSION
    audit["validator_version"] = RECOVERY_VALIDATOR_VERSION
    audit["factor_anchor_authority"] = "system_derived_before_validation"
    value.provenance["deterministic_validation"] = audit
    return value, errors

def validate_pair_attribution(payload: ContextPairAttribution | dict[str, Any], *,
                              pair_id: str, extraction_a: ContextExtraction,
                              extraction_b: ContextExtraction, profiles: list[str],
                              registry: dict[str, Any] | None = None,
                              ) -> tuple[ContextPairAttribution, list[str]]:
    value = payload if isinstance(payload, ContextPairAttribution) else ContextPairAttribution.model_validate(payload)
    errors: list[str] = []
    if value.pair_id != pair_id: errors.append("pair_id_mismatch")
    if value.claim_a_observation_id != extraction_a.observation_id: errors.append("claim_a_observation_id_mismatch")
    if value.claim_b_observation_id != extraction_b.observation_id: errors.append("claim_b_observation_id_mismatch")
    known = resolve_factors(profiles, registry)
    values_a = {x.factor_id: x.raw_value or x.composed_value for x in extraction_a.context_factors}
    values_b = {x.factor_id: x.raw_value or x.composed_value for x in extraction_b.context_factors}
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
