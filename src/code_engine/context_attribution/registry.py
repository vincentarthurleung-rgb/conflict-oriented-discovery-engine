from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY = Path("configs/context_attribution/context_registry_v1.json")

def load_registry(path: str | Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not payload.get("registry_version") or not isinstance(payload.get("profiles"), dict):
        raise ValueError("invalid_context_registry")
    return payload

def resolve_factors(profiles: list[str], registry: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    registry = registry or load_registry()
    defaults, overrides = registry["factor_defaults"], registry.get("factor_overrides", {})
    resolved: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        definition = registry["profiles"].get(profile)
        if definition is None:
            raise ValueError(f"unknown_domain_profile:{profile}")
        critical = set(definition.get("critical", []))
        for factor_id in definition["factors"]:
            value = {**defaults, **overrides.get(factor_id, {}), "factor_id": factor_id}
            if factor_id in critical:
                value["criticality"] = "critical"
            value["applicability"] = profile
            resolved[factor_id] = value
    return resolved
