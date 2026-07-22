"""Configuration-driven normalization for domain-portable experimental semantics."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


REGISTRY_VERSION = "experimental_semantics_registry_v1"
REGISTRY_PATH = Path(__file__).with_name("registries") / f"{REGISTRY_VERSION}.json"


@dataclass(frozen=True)
class SemanticsNormalization:
    category: str
    raw_value: Any
    normalized_value: str
    status: str
    rule_id: str
    registry_version: str
    domain_profile: str
    confidence_policy: str
    review_reasons: tuple[str, ...]


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if registry.get("registry_version") != REGISTRY_VERSION:
        raise ValueError("experimental semantics registry version mismatch")
    return registry


def normalize_semantics(category: str, raw_value: Any, *, domain_profile: str = "generic_experimental") -> SemanticsNormalization:
    registry = load_registry()
    profiles = {"generic_experimental", *registry.get("profile_extensions", {}).keys()}
    if domain_profile not in profiles:
        raise ValueError(f"unknown experimental semantics profile: {domain_profile}")
    raw_key = "" if raw_value is None else str(raw_value).strip().casefold()
    rules = [x for x in registry["rules"] if x["category"] == category and x["domain_profile"] in {"generic_experimental", domain_profile}]
    exact = next((x for x in rules if x["raw_pattern"].casefold() == raw_key), None)
    rule = exact or next((x for x in rules if x["raw_pattern"] == "*"), None)
    if rule is None:
        fallback_values = {"design_type": "unknown", "intervention_type": "unknown", "lexical_direction": "unclear",
                           "measurement_dimension": "unknown", "intervention_role": "unknown", "combination_mode": "unknown"}
        if category not in fallback_values:
            raise ValueError(f"unsupported semantics category: {category}")
        return SemanticsNormalization(
            category, raw_value, fallback_values[category], "reviewable_unknown",
            f"{category}_unmapped_generic_v1", REGISTRY_VERSION, domain_profile,
            "fallback_preserve_raw", (f"unmapped_{category}",),
        )
    reason = rule.get("review_reason")
    return SemanticsNormalization(
        category, raw_value, rule["normalized_value"], rule["status"], rule["rule_version"],
        REGISTRY_VERSION, domain_profile, rule["confidence_policy"], (reason,) if reason else (),
    )


def registry_audit_payload() -> dict[str, Any]:
    registry = load_registry()
    return {"registry_version": REGISTRY_VERSION, "registry_path": str(REGISTRY_PATH),
            "rule_count": len(registry["rules"]), "profiles": [registry["default_profile"], *registry["profile_extensions"].keys()]}


__all__ = ["REGISTRY_VERSION", "SemanticsNormalization", "load_registry", "normalize_semantics", "registry_audit_payload"]
