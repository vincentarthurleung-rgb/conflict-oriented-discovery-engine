from __future__ import annotations

from copy import deepcopy
from typing import Any

from .composition import COMPOSITION_POLICY_VERSION, load_composition_policy
from .identities import canonical_sha256
from .models import ProviderContextExtractionV7
from .registry import load_registry, resolve_factors

INFERENCE_RULE_DERIVER_VERSION = "context_attribution_inference_rule_deriver_v1"
V6_TO_V7_ADAPTER_VERSION = "context_attribution_v6_to_v7_inference_rule_adapter_v1"


def derive_inference_rule(
    factor: dict[str, Any], contract: dict[str, Any], profiles: list[str],
    *, registry: dict[str, Any] | None = None,
    composition_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry or load_registry()
    composition_policy = composition_policy or load_composition_policy()[0]
    factor_id = str(factor.get("factor_id") or "")
    components = factor.get("raw_components") or []
    source_nodes = factor.get("source_chain_node_ids") or []
    chain = contract.get("experimental_logic_chain") or {}
    errors: list[str] = []
    shape = [
        {"chain_node_id": x.get("chain_node_id"), "field_path": x.get("field_path")}
        for x in components
    ]
    component_nodes = list(dict.fromkeys(x.get("chain_node_id") for x in components))
    if source_nodes != component_nodes:
        errors.append("component_source_node_order_or_ownership_invalid")
    for index, item in enumerate(components):
        node = chain.get(item.get("chain_node_id"))
        if not isinstance(node, dict):
            errors.append(f"component_node_invalid:{index}")
            continue
        path = str(item.get("field_path") or "")
        current: Any = node.get("value")
        for part in path.split("."):
            if isinstance(current, list):
                values = [item.get(part) for item in current
                          if isinstance(item, dict) and part in item]
                if not values:
                    errors.append(f"component_field_path_invalid:{index}")
                    current = None
                    break
                current = values
                continue
            if not part or not isinstance(current, dict) or part not in current:
                errors.append(f"component_field_path_invalid:{index}")
                current = None
                break
            current = current[part]
        if current is None and not any(x.endswith(f":{index}") for x in errors):
            errors.append(f"component_field_path_invalid:{index}")
    known = resolve_factors(profiles, registry)
    definition = known.get(factor_id) or {}
    allowed = set(definition.get("allowed_local_inference_rules") or [])
    candidates = []
    for rule_id, rule in (composition_policy.get("rules") or {}).items():
        expected = [
            {"chain_node_id": x.get("chain_node_id"), "field_path": x.get("field_path")}
            for x in rule.get("components") or []
        ]
        if rule_id in allowed and factor_id in (rule.get("factor_ids") or []) and shape == expected:
            candidates.append(rule_id)
    status = "derived" if not errors and len(candidates) == 1 else (
        "ambiguous" if not errors and len(candidates) > 1 else "rejected"
    )
    if not errors and not candidates:
        errors.append("no_legal_inference_rule")
    elif not errors and len(candidates) > 1:
        errors.append("ambiguous_legal_inference_rules")
    selected = candidates[0] if status == "derived" else None
    return {
        "deriver_version": INFERENCE_RULE_DERIVER_VERSION,
        "derived_inference_rule": selected,
        "derivation_policy_version": COMPOSITION_POLICY_VERSION,
        "matched_rule_candidates": candidates,
        "selected_rule": selected,
        "derivation_status": status,
        "derivation_errors": errors,
        "derivation_provenance": {
            "factor_id": factor_id, "component_shape": shape,
            "source_chain_node_ids": source_nodes,
            "registry_rule_allowlist": sorted(allowed),
            "free_text_rule_guessing": False,
        },
    }


def adapt_v6_to_v7(
    payload: dict[str, Any], contract: dict[str, Any], profiles: list[str],
    *, registry: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = deepcopy(payload)
    adapted = deepcopy(payload)
    adapted["schema_version"] = "observation_context_extraction_v7"
    audits = []
    failures = []
    for index, factor in enumerate(adapted.get("context_factors") or []):
        source_rule = factor.pop("inference_rule", None)
        derivation = None
        if factor.get("status") == "inferred_from_local_chain":
            derivation = derive_inference_rule(
                factor, contract, profiles, registry=registry
            )
            derived = derivation["derived_inference_rule"]
            if derivation["derivation_status"] != "derived":
                failures.append(f"rule_derivation_failed:{index}")
            if source_rule is not None and source_rule != derived:
                failures.append(f"source_provider_rule_conflict:{index}")
        audits.append({
            "factor_index": index, "factor_id": factor.get("factor_id"),
            "source_provider_inference_rule": source_rule,
            "source_rule_consistent": (
                source_rule is None or
                bool(derivation and source_rule == derivation["derived_inference_rule"])
            ),
            "rule_derivation": derivation,
        })
    # Schema is evaluated only after all factors were adapted; there is no salvage.
    ProviderContextExtractionV7.model_validate(adapted)
    audit = {
        "adapter_version": V6_TO_V7_ADAPTER_VERSION,
        "source_schema_version": source.get("schema_version"),
        "target_schema_version": adapted["schema_version"],
        "source_payload_sha256": canonical_sha256(source),
        "adapted_payload_sha256": canonical_sha256(adapted),
        "before_after_canonical_diff": {
            "schema_version": [source.get("schema_version"), adapted["schema_version"]],
            "removed_provider_authority_fields": ["context_factors[*].inference_rule"],
        },
        "factors": audits, "valid": not failures, "errors": failures,
        "scientific_text_added": False, "components_added_or_modified": False,
    }
    return adapted, audit


def materialize_internal_v5(
    adapted: dict[str, Any], adapter_audit: dict[str, Any],
) -> dict[str, Any]:
    factors = []
    factor_audits = adapter_audit["factors"]
    for factor, audit in zip(adapted["context_factors"], factor_audits, strict=True):
        value = deepcopy(factor)
        derivation = audit.get("rule_derivation")
        value["inference_rule"] = (
            derivation.get("derived_inference_rule") if derivation else None
        )
        value["evidence_anchor_ids"] = (
            list(dict.fromkeys(
                aid for component in value.get("raw_components") or []
                for aid in component.get("evidence_anchor_ids") or []
            )) if value.get("status") == "inferred_from_local_chain"
            else ([value["explicit_span"]["evidence_anchor_id"]]
                  if value.get("status") == "explicit" else [])
        )
        factors.append(value)
    return {
        **{k: deepcopy(v) for k, v in adapted.items() if k != "context_factors"},
        "schema_version": "observation_context_extraction_v5",
        "context_factors": factors,
        "provenance": {
            "inference_rule_authority": "system_deterministic",
            "inference_rule_deriver_version": INFERENCE_RULE_DERIVER_VERSION,
            "v6_to_v7_adapter": adapter_audit,
        },
        "validation_status": "unvalidated",
    }
