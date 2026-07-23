from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

COMPOSITION_POLICY_VERSION = "context_local_chain_composition_v2"
COMPOSER_VERSION = "context_attribution_deterministic_composer_v1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
COMPOSITION_POLICY_PATH = Path(
    "configs/context_attribution/context_local_chain_composition_v2.json"
)


def load_composition_policy() -> tuple[dict[str, Any], str]:
    path = PROJECT_ROOT / COMPOSITION_POLICY_PATH
    raw = path.read_bytes()
    payload = json.loads(raw)
    if (
        payload.get("policy_version") != COMPOSITION_POLICY_VERSION
        or payload.get("schema_version") != "context_local_chain_composition_policy_v2"
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


__all__ = [
    "COMPOSER_VERSION", "COMPOSITION_POLICY_PATH", "COMPOSITION_POLICY_VERSION",
    "compose", "composition_identity", "load_composition_policy",
]
