"""Section-level validation helpers for repository configuration files."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


class ConfigValidationError(ValueError):
    """Raised when a configuration file exists but lacks required structure."""


def _require_dict(payload: Dict[str, Any], key: str, config_name: str) -> Dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict) or not value:
        raise ConfigValidationError(f"{config_name} requires non-empty object section `{key}`")
    return value


def _require_list(payload: Dict[str, Any], key: str, config_name: str) -> List[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ConfigValidationError(f"{config_name} requires non-empty list section `{key}`")
    return value


def _require_list_field(payload: Dict[str, Any], key: str, config_name: str) -> List[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ConfigValidationError(f"{config_name} requires list section `{key}`")
    return value


def _require_any(payload: Dict[str, Any], keys: Iterable[str], config_name: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value:
            return key
    joined = ", ".join(f"`{k}`" for k in keys)
    raise ConfigValidationError(f"{config_name} requires one of: {joined}")


def validate_l2_l3_ontology_rules(payload: Dict[str, Any]) -> None:
    """Validate ontology/conflict-discovery config sections."""

    settings = _require_dict(payload, "ontology_settings", "l2_l3_ontology_rules")
    for key in ("similarity_threshold_theta", "marginal_entropy_conflict_gate", "type_i_attribution_gate"):
        if key in settings and not isinstance(settings[key], (int, float)):
            raise ConfigValidationError(f"ontology_settings.{key} must be numeric")
    _require_dict(payload, "synonym_map", "l2_l3_ontology_rules")
    _require_list_field(payload, "forbidden_object_keywords", "l2_l3_ontology_rules")
    weak_key = _require_any(payload, ("weak_supervision_latent_prior", "weak_supervision_pool", "latent_pool"), "l2_l3_ontology_rules")
    if weak_key == "weak_supervision_latent_prior":
        latent = payload[weak_key].get("latent_variables")
        if not isinstance(latent, list) or not latent:
            raise ConfigValidationError("weak_supervision_latent_prior.latent_variables must be a non-empty list")
    elif weak_key == "weak_supervision_pool" and not isinstance(payload[weak_key], list):
        raise ConfigValidationError("weak_supervision_pool must be a list")
    elif weak_key == "latent_pool" and not isinstance(payload[weak_key], list):
        raise ConfigValidationError("latent_pool must be a list")


def validate_context_axis_map(payload: Dict[str, Any]) -> None:
    """Validate context axis map values and aliases."""

    axes = _require_dict(payload, "axes", "context_axis_map")
    for axis, values in axes.items():
        if not axis or not isinstance(values, dict) or not values:
            raise ConfigValidationError("each context axis must be a non-empty object")
        for value, aliases in values.items():
            if not value:
                raise ConfigValidationError(f"context axis `{axis}` contains an empty value")
            if isinstance(aliases, dict):
                candidates = aliases.get("values") or aliases.get("aliases") or aliases.get("patterns")
            else:
                candidates = aliases
            if not isinstance(candidates, list) or not any(str(item).strip() for item in candidates):
                raise ConfigValidationError(f"context axis `{axis}.{value}` needs values/aliases/patterns")


def validate_domain_spec(payload: Dict[str, Any]) -> None:
    """Validate domain bootstrap configuration."""

    if not (payload.get("domain_name") or payload.get("domain")):
        raise ConfigValidationError("domain_spec requires `domain_name` or `domain`")
    for key in ("core_entities", "relation_vocabulary", "context_axes", "validation_resources"):
        _require_list(payload, key, "domain_spec")


def validate_validation_plan(payload: Dict[str, Any]) -> None:
    """Validate validator routing configuration."""

    if not payload.get("rules") and not payload.get("validator_registry") and not payload.get("default_validators"):
        raise ConfigValidationError("validation_plan requires routing rules, validator_registry, or default_validators")
    unknown_ok = False
    for rule in payload.get("rules", []):
        validators = rule.get("validators", [])
        if rule.get("hypothesis_pattern") == "unknown" and (
            "NullValidator" in validators or "Unresolved_No_Coverage" in validators
        ):
            unknown_ok = True
    default_validators = payload.get("default_validators", [])
    if "NullValidator" in default_validators:
        unknown_ok = True
    if not unknown_ok:
        raise ConfigValidationError("validation_plan must route unknown coverage to NullValidator/Unresolved_No_Coverage")


VALIDATORS = {
    "l2_l3_ontology_rules": validate_l2_l3_ontology_rules,
    "context_axis_map": validate_context_axis_map,
    "domain_spec": validate_domain_spec,
    "validation_plan": validate_validation_plan,
}


def validate_config_payload(payload: Dict[str, Any], config_type: str) -> None:
    """Dispatch section-level validation by config type."""

    if config_type not in VALIDATORS:
        raise ConfigValidationError(f"Unknown config type: {config_type}")
    VALIDATORS[config_type](payload)
