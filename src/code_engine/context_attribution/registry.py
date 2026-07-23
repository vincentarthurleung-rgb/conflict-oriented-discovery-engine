from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATHS = {
    "context_factor_registry_v1": Path("configs/context_attribution/context_registry_v1.json"),
    "context_factor_registry_v2": Path("configs/context_attribution/context_registry_v2.json"),
}
CURRENT_REGISTRY_VERSION = "context_factor_registry_v2"
LEGACY_REGISTRY_VERSION = "context_factor_registry_v1"
DEFAULT_REGISTRY = REGISTRY_PATHS[CURRENT_REGISTRY_VERSION]


@dataclass(frozen=True)
class RegistryResolution:
    registry_version: str
    registry_path: str
    registry_content_sha256: str
    registry_schema_version: str
    registry_resolution_source: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _absolute(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_registry(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise FileNotFoundError(f"context_registry_not_found:{path}")
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid_context_registry_json:{path}") from exc
    if not isinstance(payload, dict) or not payload.get("registry_version"):
        raise ValueError(f"invalid_context_registry:{path}")
    if not isinstance(payload.get("profiles"), dict):
        raise ValueError(f"invalid_context_registry_profiles:{path}")
    return payload, hashlib.sha256(raw).hexdigest()


def resolve_registry(
    *,
    requested_registry_version: str | None = None,
    prompt_version: str | None = None,
    extraction_schema_version: str | None = None,
    artifact_identity: Mapping[str, Any] | None = None,
    explicit_path: str | Path | None = None,
    expected_content_sha256: str | None = None,
) -> RegistryResolution:
    """Resolve one immutable registry identity; never discover or fall back to a latest file."""
    artifact_identity = artifact_identity or {}
    artifact_version = artifact_identity.get("registry_version")
    if requested_registry_version:
        version, source = requested_registry_version, "explicit_registry_version"
    elif artifact_version:
        version, source = str(artifact_version), "artifact_registry_identity"
    elif prompt_version in {"context_attribution_prompts_v1", "context_attribution_prompts_v2"}:
        version, source = LEGACY_REGISTRY_VERSION, "prompt_compatibility"
    elif extraction_schema_version == "observation_context_extraction_v2":
        version, source = LEGACY_REGISTRY_VERSION, "extraction_schema_compatibility"
    else:
        version, source = CURRENT_REGISTRY_VERSION, "current_pipeline_default"
    if version not in REGISTRY_PATHS:
        raise ValueError(f"unknown_context_registry_version:{version}")

    canonical_path = REGISTRY_PATHS[version]
    path = Path(explicit_path) if explicit_path is not None else Path(
        artifact_identity.get("registry_path") or canonical_path
    )
    if _relative(_absolute(path)) != canonical_path.as_posix():
        raise ValueError(f"context_registry_version_path_mismatch:{version}:{path}")
    payload, content_hash = _read_registry(_absolute(path))
    internal_version = str(payload.get("schema_version") or payload["registry_version"])
    if payload["registry_version"] != version or internal_version != version:
        raise ValueError(
            f"context_registry_internal_version_mismatch:{version}:"
            f"{payload.get('registry_version')}:{internal_version}"
        )
    expected_hash = expected_content_sha256 or artifact_identity.get("registry_content_sha256")
    if expected_hash and str(expected_hash) != content_hash:
        raise ValueError(f"context_registry_hash_mismatch:{version}")
    if explicit_path is not None:
        source = "explicit_registry_override"
    return RegistryResolution(
        registry_version=version,
        registry_path=canonical_path.as_posix(),
        registry_content_sha256=content_hash,
        registry_schema_version=internal_version,
        registry_resolution_source=source,
    )


def load_registry(
    path: str | Path | None = None,
    *,
    resolution: RegistryResolution | None = None,
) -> dict[str, Any]:
    if resolution is None:
        if path is not None:
            relative = _relative(_absolute(path))
            matches = [version for version, known in REGISTRY_PATHS.items()
                       if known.as_posix() == relative]
            if not matches:
                raise ValueError(f"unregistered_context_registry_path:{path}")
            resolution = resolve_registry(
                requested_registry_version=matches[0], explicit_path=path
            )
        else:
            resolution = resolve_registry()
    payload, content_hash = _read_registry(_absolute(resolution.registry_path))
    if payload["registry_version"] != resolution.registry_version:
        raise ValueError("context_registry_resolution_version_mismatch")
    if content_hash != resolution.registry_content_sha256:
        raise ValueError("context_registry_resolution_hash_mismatch")
    return payload


def resolve_factors(
    profiles: list[str],
    registry: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
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


__all__ = [
    "CURRENT_REGISTRY_VERSION", "DEFAULT_REGISTRY", "LEGACY_REGISTRY_VERSION",
    "PROJECT_ROOT", "REGISTRY_PATHS", "RegistryResolution", "load_registry",
    "resolve_factors", "resolve_registry",
]
