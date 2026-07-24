from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

IDENTITY_BUNDLE_VERSION = "context_attribution_identity_bundle_v1"
PROVIDER_EXECUTION_IDENTITY_VERSION = (
    "context_attribution_provider_execution_identity_v1"
)
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


class ProviderExecutionIdentity(BaseModel):
    """Immutable effective Provider configuration; provenance is non-hashing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_execution_identity_version: str = PROVIDER_EXECUTION_IDENTITY_VERSION
    provider: str
    model: str
    thinking_mode: str
    configured_max_tokens: int = Field(gt=0)
    prompt_version: str
    extraction_schema_version: str
    comparison_schema_version: str
    configuration_source: dict[str, str]
    identity_sha256: str

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "provider_execution_identity_version":
                self.provider_execution_identity_version,
            "provider": self.provider,
            "model": self.model,
            "thinking_mode": self.thinking_mode,
            "configured_max_tokens": self.configured_max_tokens,
            "prompt_version": self.prompt_version,
            "extraction_schema_version": self.extraction_schema_version,
            "comparison_schema_version": self.comparison_schema_version,
        }

    def verify(self) -> bool:
        return (
            self.provider_execution_identity_version ==
            PROVIDER_EXECUTION_IDENTITY_VERSION
            and self.thinking_mode in {
                "enabled", "disabled", "provider_default",
            }
            and len(self.identity_sha256) == 64
            and all(char in "0123456789abcdef" for char in self.identity_sha256)
            and self.identity_sha256 == canonical_sha256(self.canonical_payload())
        )


def build_provider_execution_identity(
    *, provider: str, model: str, thinking_mode: str,
    configured_max_tokens: int, prompt_version: str,
    extraction_schema_version: str, comparison_schema_version: str,
    configuration_source: dict[str, str] | None = None,
) -> ProviderExecutionIdentity:
    payload = {
        "provider_execution_identity_version":
            PROVIDER_EXECUTION_IDENTITY_VERSION,
        "provider": provider,
        "model": model,
        "thinking_mode": thinking_mode,
        "configured_max_tokens": configured_max_tokens,
        "prompt_version": prompt_version,
        "extraction_schema_version": extraction_schema_version,
        "comparison_schema_version": comparison_schema_version,
    }
    return ProviderExecutionIdentity(
        **payload,
        configuration_source=dict(configuration_source or {}),
        identity_sha256=canonical_sha256(payload),
    )


def resolve_provider_execution_identity(
    *, provider: str | None, model: str | None, thinking_mode: str | None,
    configured_max_tokens: int | None, prompt_version: str,
    extraction_schema_version: str, comparison_schema_version: str,
    production_config: dict[str, Any] | None = None,
    fake_test: bool = False,
) -> ProviderExecutionIdentity:
    """Resolve only non-secret settings; credential variables are never inspected."""
    from code_engine.extraction.policy import (
        DEFAULT_L1_MODEL_FAMILY, DEFAULT_L1_MODEL_NAME,
    )
    from code_engine.fulltext.fulltext_l1_v2 import (
        DEFAULT_MAX_TOKENS, DEFAULT_THINKING_MODE,
    )

    config = production_config or {}
    if fake_test:
        sources = {
            key: "fake_test_configuration"
            for key in (
                "provider", "model", "thinking_mode", "configured_max_tokens",
            )
        }
        effective = (
            provider or "fake", model or "fake-recovery-v1",
            thinking_mode or "disabled",
            configured_max_tokens or DEFAULT_MAX_TOKENS,
        )
    else:
        def choose(
            explicit: Any, config_key: str, env_name: str, default: Any,
        ) -> tuple[Any, str]:
            if explicit is not None:
                return explicit, "cli"
            if config.get(config_key) is not None:
                return config[config_key], "production_config"
            if os.getenv(env_name) is not None:
                return os.getenv(env_name), env_name
            return default, "built_in_default"

        effective_provider, provider_source = choose(
            provider, "provider", "L1_PROVIDER", DEFAULT_L1_MODEL_FAMILY,
        )
        effective_model, model_source = choose(
            model, "model", "MODEL_NAME", DEFAULT_L1_MODEL_NAME,
        )
        effective_thinking, thinking_source = choose(
            thinking_mode, "thinking_mode", "FULLTEXT_L1_V2_THINKING_MODE",
            DEFAULT_THINKING_MODE,
        )
        effective_tokens, token_source = choose(
            configured_max_tokens, "configured_max_tokens",
            "FULLTEXT_L1_V2_MAX_TOKENS", DEFAULT_MAX_TOKENS,
        )
        effective = (
            effective_provider, effective_model, effective_thinking,
            int(effective_tokens),
        )
        sources = {
            "provider": provider_source, "model": model_source,
            "thinking_mode": thinking_source,
            "configured_max_tokens": token_source,
        }
    return build_provider_execution_identity(
        provider=str(effective[0]), model=str(effective[1]),
        thinking_mode=str(effective[2]), configured_max_tokens=int(effective[3]),
        prompt_version=prompt_version,
        extraction_schema_version=extraction_schema_version,
        comparison_schema_version=comparison_schema_version,
        configuration_source=sources,
    )


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
    "PROVIDER_EXECUTION_IDENTITY_VERSION", "ProviderExecutionIdentity",
    "build_provider_execution_identity", "canonical_sha256",
    "comparator_normalization_policy_payload",
    "normalization_policy_payload", "resolve_policy_identities",
    "resolve_provider_execution_identity", "validate_policy_identity",
]
