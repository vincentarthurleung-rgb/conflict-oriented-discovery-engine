from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

COMPOSITION_POLICY_VERSION = "context_local_chain_composition_v3"
COMPOSER_VERSION = "context_attribution_deterministic_composer_v1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
COMPOSITION_POLICY_PATH = Path(
    "configs/context_attribution/context_local_chain_composition_v3.json"
)


def load_composition_policy() -> tuple[dict[str, Any], str]:
    path = PROJECT_ROOT / COMPOSITION_POLICY_PATH
    raw = path.read_bytes()
    payload = json.loads(raw)
    if (
        payload.get("policy_version") != COMPOSITION_POLICY_VERSION
        or payload.get("schema_version") != "context_local_chain_composition_policy_v3"
    ):
        raise ValueError("context_composition_policy_version_mismatch")
    return payload, hashlib.sha256(raw).hexdigest()


def composition_identity() -> dict[str, str]:
    _, content_hash = load_composition_policy()
    return {
        "composer_version": COMPOSER_VERSION,
        "composition_policy_version": COMPOSITION_POLICY_VERSION,
        "composition_policy_path": COMPOSITION_POLICY_PATH.as_posix(),
        "composition_policy_content_sha256": content_hash,
    }


def compose(rule: dict[str, Any], surfaces: list[str]) -> str:
    operator = rule.get("composition_operator")
    if operator == "identity" and len(surfaces) == 1:
        return surfaces[0]
    if operator == "join_with_space":
        return " ".join(surfaces)
    if operator == "intervention_then_versus_comparator" and len(surfaces) == 3:
        return f"{surfaces[0]} {surfaces[1]} versus {surfaces[2]}"
    raise ValueError("unsupported_or_malformed_composition_operator")


def validate_registry_policy_consistency(
    registry: dict[str, Any], policy: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    rules = policy.get("rules") or {}
    defaults = registry.get("factor_defaults") or {}
    overrides = registry.get("factor_overrides") or {}
    registry_contracts = registry.get("local_inference_rule_contracts") or {}
    factor_ids = {
        factor_id for profile in (registry.get("profiles") or {}).values()
        for factor_id in profile.get("factors", [])
    }
    for factor_id in sorted(factor_ids):
        definition = {**defaults, **overrides.get(factor_id, {})}
        for rule_id in definition.get("allowed_local_inference_rules") or []:
            rule = rules.get(rule_id)
            if rule is None:
                errors.append(f"registry_rule_without_policy:{factor_id}:{rule_id}")
            elif factor_id not in rule.get("factor_ids", []):
                errors.append(f"registry_policy_factor_mismatch:{factor_id}:{rule_id}")
    for rule_id, rule in rules.items():
        if not rule.get("components") or not rule.get("composition_operator"):
            errors.append(f"policy_rule_malformed:{rule_id}")
        for factor_id in rule.get("factor_ids", []):
            definition = {**defaults, **overrides.get(factor_id, {})}
            if rule_id not in definition.get("allowed_local_inference_rules", []):
                errors.append(f"policy_rule_not_exposed_by_registry:{factor_id}:{rule_id}")
        contract = registry_contracts.get(rule_id)
        if contract is None:
            errors.append(f"policy_rule_without_registry_contract:{rule_id}")
        else:
            if contract.get("factor_ids") != rule.get("factor_ids"):
                errors.append(f"registry_policy_rule_factors_mismatch:{rule_id}")
            if contract.get("components") != rule.get("components"):
                errors.append(f"registry_policy_rule_components_mismatch:{rule_id}")
    for rule_id in registry_contracts:
        if rule_id not in rules:
            errors.append(f"registry_rule_contract_without_policy:{rule_id}")
    return errors


__all__ = [
    "COMPOSER_VERSION", "COMPOSITION_POLICY_PATH", "COMPOSITION_POLICY_VERSION",
    "compose", "composition_identity", "load_composition_policy",
    "validate_registry_policy_consistency",
]
