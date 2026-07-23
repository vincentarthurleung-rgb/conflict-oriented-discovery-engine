from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

IDENTITY_BUNDLE_VERSION = "context_attribution_identity_bundle_v1"
NORMALIZATION_POLICY_SCHEMA_VERSION = "context_normalization_policy_schema_v3"
COMPARATOR_NORMALIZATION_POLICY_SCHEMA_VERSION = (
    "context_comparator_normalization_policy_schema_v1"
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PolicyIdentity:
    version: str
    schema_version: str
    resolution_source: str
    path: str | None
    content_sha256: str
    parent_path: str | None
    parent_sha256: str | None
    identity_sha256: str
    active: bool
    inactive_reason: str | None

    @classmethod
    def embedded(
        cls, *, version: str, schema_version: str, payload: dict[str, Any],
        parent_path: str, parent_sha256: str, active: bool = True,
        inactive_reason: str | None = None,
    ) -> "PolicyIdentity":
        content_sha256 = canonical_sha256(payload)
        identity_payload = {
            "version": version,
            "schema_version": schema_version,
            "resolution_source": "embedded_in_registry"
            if "registry" in parent_path else "embedded_in_composition_policy",
            "path": None,
            "content_sha256": content_sha256,
            "parent_path": parent_path,
            "parent_sha256": parent_sha256,
            "active": active,
            "inactive_reason": inactive_reason,
        }
        return cls(**identity_payload, identity_sha256=canonical_sha256(identity_payload))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def prefixed(self, prefix: str) -> dict[str, Any]:
        return {f"{prefix}_{key}": value for key, value in self.to_dict().items()}


def normalization_policy_payload(registry: dict[str, Any]) -> dict[str, Any]:
    version = registry.get("normalization_registry_version")
    if version != "context_normalization_policy_v3":
        raise ValueError(f"normalization_policy_version_mismatch:{version}")
    defaults = registry.get("factor_defaults")
    overrides = registry.get("factor_overrides")
    if not isinstance(defaults, dict) or not isinstance(overrides, dict):
        raise ValueError("normalization_policy_subtree_missing")
    relevant_overrides = {
        factor_id: {
            key: definition[key]
            for key in ("normalization_policy", "controlled_normalizations")
            if key in definition
        }
        for factor_id, definition in overrides.items()
        if isinstance(definition, dict)
        and any(key in definition for key in ("normalization_policy", "controlled_normalizations"))
    }
    return {
        "schema_version": NORMALIZATION_POLICY_SCHEMA_VERSION,
        "policy_version": version,
        "factor_defaults": {
            key: defaults[key]
            for key in ("normalization_policy", "controlled_normalizations")
            if key in defaults
        },
        "factor_overrides": relevant_overrides,
    }


def comparator_normalization_policy_payload(
    composition_policy: dict[str, Any],
) -> dict[str, Any]:
    version = composition_policy.get("comparator_normalization_policy_version")
    if version != "context_comparator_normalization_v1":
        raise ValueError(f"comparator_normalization_policy_version_mismatch:{version}")
    rules = {
        rule_id: {"optional_normalized_classes": rule["optional_normalized_classes"]}
        for rule_id, rule in (composition_policy.get("rules") or {}).items()
        if isinstance(rule, dict) and rule.get("optional_normalized_classes")
    }
    if not rules:
        raise ValueError("comparator_normalization_policy_subtree_missing")
    return {
        "schema_version": COMPARATOR_NORMALIZATION_POLICY_SCHEMA_VERSION,
        "policy_version": version,
        "rules": rules,
    }


def resolve_policy_identities(
    *, registry: dict[str, Any], registry_path: str, registry_sha256: str,
    composition_policy: dict[str, Any], composition_path: str,
    composition_sha256: str,
) -> tuple[PolicyIdentity, PolicyIdentity]:
    normalization_payload = normalization_policy_payload(registry)
    comparator_payload = comparator_normalization_policy_payload(composition_policy)
    normalization = PolicyIdentity.embedded(
        version=normalization_payload["policy_version"],
        schema_version=normalization_payload["schema_version"],
        payload=normalization_payload,
        parent_path=registry_path,
        parent_sha256=registry_sha256,
    )
    comparator = PolicyIdentity.embedded(
        version=comparator_payload["policy_version"],
        schema_version=comparator_payload["schema_version"],
        payload=comparator_payload,
        parent_path=composition_path,
        parent_sha256=composition_sha256,
    )
    return normalization, comparator


def validate_policy_identity(identity: PolicyIdentity) -> list[str]:
    errors: list[str] = []
    if len(identity.content_sha256) != 64:
        errors.append(f"policy_content_identity_missing:{identity.version}")
    if len(identity.identity_sha256) != 64:
        errors.append(f"policy_identity_missing:{identity.version}")
    expected_identity = canonical_sha256({
        key: value for key, value in identity.to_dict().items()
        if key != "identity_sha256"
    })
    if identity.identity_sha256 != expected_identity:
        errors.append(f"policy_identity_hash_mismatch:{identity.version}")
    if identity.active and identity.inactive_reason is not None:
        errors.append(f"active_policy_has_inactive_reason:{identity.version}")
    if not identity.active and not identity.inactive_reason:
        errors.append(f"inactive_policy_reason_missing:{identity.version}")
    if identity.resolution_source.startswith("embedded_"):
        if identity.path is not None or not identity.parent_path or not identity.parent_sha256:
            errors.append(f"embedded_policy_parent_identity_missing:{identity.version}")
    return errors


__all__ = [
    "COMPARATOR_NORMALIZATION_POLICY_SCHEMA_VERSION", "IDENTITY_BUNDLE_VERSION",
    "NORMALIZATION_POLICY_SCHEMA_VERSION", "PolicyIdentity", "canonical_json",
    "canonical_sha256", "comparator_normalization_policy_payload",
    "normalization_policy_payload", "resolve_policy_identities",
    "validate_policy_identity",
]
