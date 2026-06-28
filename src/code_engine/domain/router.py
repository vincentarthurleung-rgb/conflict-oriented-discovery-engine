"""DomainProfile registry and domain-id validator.

Semantic classification belongs to ``code_engine.encoder``. Keyword routing is
retained only as an explicitly degraded compatibility fallback.
"""

import json
from pathlib import Path

from code_engine.domain.models import DomainProfile, default_domain_profiles


class DomainRouter:
    def __init__(self, profiles: list[DomainProfile] | None = None):
        active = profiles or default_domain_profiles()
        self._profiles = {profile.domain_id.casefold(): profile for profile in active}

    def resolve(self, name: str) -> DomainProfile | None:
        needle = str(name).casefold()
        if needle in self._profiles:
            return self._profiles[needle]
        return next((profile for profile in self._profiles.values() if needle in {alias.casefold() for alias in profile.aliases}), None)

    @property
    def allowed_domain_ids(self) -> set[str]:
        return set(self._profiles)

    def validate_domain_id(self, domain_id: str) -> bool:
        return str(domain_id).casefold() in self._profiles

    def get_or_default(self, domain_id: str) -> DomainProfile:
        return self.resolve(domain_id) or self._profiles["general_biomedical"]

    def profiles(self) -> list[DomainProfile]:
        return list(self._profiles.values())

    def profile_summaries(self) -> list[dict]:
        return [
            {"domain_id": item.domain_id, "profile_id": item.profile_id,
             "subdomain_id": item.subdomain_id, "display_name": item.display_name,
             "description": item.description, "key_entity_types": list(item.key_entity_types),
             "key_relation_types": list(item.key_relation_types), "key_evidence_types": list(item.key_evidence_types)}
            for item in self._profiles.values()
        ]

    def route_text(self, text: str) -> DomainProfile:
        return self.route_deterministic_fallback(text)

    def route_deterministic_fallback(self, text: str, config_path: str | Path = "configs/domain_routing_fallback.json") -> DomainProfile:
        """Compatibility-only degraded routing loaded from configuration."""

        try:
            payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._profiles["general_biomedical"]
        lowered = str(text or "").casefold()
        for route in payload.get("routes", []):
            if any(str(term).casefold() in lowered for term in route.get("terms", [])):
                return self.get_or_default(str(route.get("domain_id", "")))
        return self._profiles["general_biomedical"]


def default_domain_router() -> DomainRouter:
    return DomainRouter()
