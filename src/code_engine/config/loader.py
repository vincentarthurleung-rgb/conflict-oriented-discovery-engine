"""Strict configuration loader with explicit fallback auditing."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .validation import ConfigValidationError, validate_config_payload


DEFAULT_CONFIG_PATH = "configs/normalization/l2_l3_ontology_rules.json"
FALLBACK_AUDIT_PATH = "reports/config_fallback_audit.json"

LEGACY_CONFIG_PATHS = {
    "l2_l3_ontology_rules": "config/schemas/l2_l3_ontology_rules.json",
    "context_axis_map": "config/schemas/context_axis_map.json",
    "domain_spec": "config/schemas/domain_spec.json",
    "validation_plan": "config/schemas/validation_plan.json",
    "entity_registry": "config/schemas/entity_registry.json",
}


class PipelineConfig:
    """Validated config wrapper for deterministic pipeline modules."""

    def __init__(
        self,
        data: Dict[str, Any],
        source_path: str,
        allow_fallback: bool = False,
        fallback_events: Optional[List[Dict[str, Any]]] = None,
    ):
        self.data = data
        self.source_path = source_path
        self.allow_fallback = allow_fallback
        self.fallback_events = fallback_events or []

    @property
    def synonym_map(self) -> Dict[str, str]:
        return self.data.get("synonym_map", {})

    @property
    def forbidden_object_keywords(self) -> List[str]:
        return self.data.get("forbidden_object_keywords", [])

    @property
    def latent_pool(self) -> List[str]:
        weak_prior = self.data.get("weak_supervision_latent_prior", {})
        return weak_prior.get("latent_variables") or self.data.get("weak_supervision_pool") or self.data.get("latent_pool", [])

    @property
    def thresholds(self) -> Dict[str, float]:
        settings = self.data.get("ontology_settings", {})
        return {
            "similarity_threshold_theta": float(settings.get("similarity_threshold_theta", 0.7)),
            "marginal_entropy_conflict_gate": float(settings.get("marginal_entropy_conflict_gate", 0.10)),
            "type_i_attribution_gate": float(settings.get("type_i_attribution_gate", 0.45)),
        }


def default_l2_l3_fallback_config() -> Dict[str, Any]:
    """Small demo fallback used only when explicitly requested."""

    return {
        "ontology_settings": {
            "similarity_threshold_theta": 0.7,
            "marginal_entropy_conflict_gate": 0.10,
            "type_i_attribution_gate": 0.45,
        },
        "synonym_map": {"antidepressant response": "ANTIDEPRESSANT RESPONSE"},
        "forbidden_object_keywords": ["figure", "table", "supplementary"],
        "weak_supervision_latent_prior": {
            "latent_variables": ["HYPOXIA", "NORMOXIA", "ACUTE_PHASE", "CHRONIC_PHASE"]
        },
    }


def write_fallback_audit(events: Iterable[Dict[str, Any]], audit_path: str = FALLBACK_AUDIT_PATH) -> None:
    """Persist fallback usage so demo runs are visible in review."""

    event_list = list(events)
    if not event_list:
        return
    os.makedirs(os.path.dirname(audit_path), exist_ok=True)
    with open(audit_path, "w", encoding="utf-8") as handle:
        json.dump(
            {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "fallback_events": event_list},
            handle,
            ensure_ascii=False,
            indent=2,
        )


def _fallback_event(config_path: str, config_type: str, reason: str, modules: Optional[List[str]]) -> Dict[str, Any]:
    return {
        "module": ",".join(modules or ["pipeline"]),
        "config_type": config_type,
        "config_path": config_path,
        "reason": reason,
        "fallback_impact": [
            "synonym map",
            "forbidden keywords",
            "weak supervision pool",
            "context candidates",
        ],
    }


def resolve_config_path(config_path: str, config_type: str) -> tuple[Path, List[Dict[str, Any]]]:
    """Resolve a preferred config path and audit legacy-path fallback."""

    preferred = Path(config_path)
    if preferred.exists():
        return preferred, []
    legacy_value = LEGACY_CONFIG_PATHS.get(config_type)
    legacy = Path(legacy_value) if legacy_value else None
    if legacy is not None and legacy.exists() and str(preferred).startswith("configs/"):
        event = _fallback_event(str(legacy), config_type, f"preferred_config_missing: {preferred}", ["config_loader"])
        event["fallback_kind"] = "legacy_config_path"
        return legacy, [event]
    return preferred, []


def load_json_config(
    config_path: str,
    *,
    config_type: str,
    allow_fallback: bool = False,
    strict_config: bool = True,
    fallback_data: Optional[Dict[str, Any]] = None,
    required_modules: Optional[List[str]] = None,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Load and validate a JSON config with explicit fallback behavior."""

    path, fallback_events = resolve_config_path(config_path, config_type)
    if fallback_events:
        write_fallback_audit(fallback_events)
    if not path.exists():
        if strict_config and not allow_fallback:
            raise FileNotFoundError(f"Required config missing: {config_path}")
        data = fallback_data or default_l2_l3_fallback_config()
        fallback_events.append(_fallback_event(str(path), config_type, "missing_config_file", required_modules))
        write_fallback_audit(fallback_events)
        return data, fallback_events

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    try:
        validate_config_payload(data, config_type)
    except ConfigValidationError as exc:
        if strict_config and not allow_fallback:
            raise
        data = fallback_data or default_l2_l3_fallback_config()
        fallback_events.append(_fallback_event(config_path, config_type, f"invalid_config: {exc}", required_modules))
        write_fallback_audit(fallback_events)

    return data, fallback_events


def load_pipeline_config(
    config_path: str = DEFAULT_CONFIG_PATH,
    *,
    allow_fallback: bool = False,
    strict_config: bool = True,
    required_modules: Optional[List[str]] = None,
) -> PipelineConfig:
    """Load the L2/L3 deterministic pipeline config."""

    data, fallback_events = load_json_config(
        config_path,
        config_type="l2_l3_ontology_rules",
        allow_fallback=allow_fallback,
        strict_config=strict_config,
        fallback_data=default_l2_l3_fallback_config(),
        required_modules=required_modules,
    )
    data_fallback = any(event.get("fallback_kind") != "legacy_config_path" for event in fallback_events)
    source_path = "fallback_default" if data_fallback else str(resolve_config_path(config_path, "l2_l3_ontology_rules")[0])
    print(f"[Config] Using config file: {source_path}")
    print(f"[Config] Fallback occurred: {bool(fallback_events)}")
    return PipelineConfig(data, source_path, allow_fallback=allow_fallback, fallback_events=fallback_events)
