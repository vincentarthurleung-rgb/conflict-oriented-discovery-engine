"""Deterministic domain selection for extraction planning."""

from code_engine.domain.models import DomainProfile


class DomainRouter:
    def __init__(self, profiles: list[DomainProfile] | None = None):
        self._profiles = {profile.name.casefold(): profile for profile in profiles or []}

    def resolve(self, name: str) -> DomainProfile | None:
        return self._profiles.get(str(name).casefold())

    def route_text(self, text: str) -> DomainProfile:
        """Select neuropharmacology for supported local terms, else general."""

        lowered = str(text or "").casefold()
        if any(term in lowered for term in (
            "ketamine", "esketamine", "depression", "bdnf", "nmda", "ampa", "mtor",
        )):
            return self.resolve("neuropharmacology") or DomainProfile(
                "neuropharmacology", prompt_id="neuropharmacology"
            )
        return self.resolve("general_biomedical") or DomainProfile(
            "general_biomedical", prompt_id="general_biomedical"
        )


def default_domain_router() -> DomainRouter:
    return DomainRouter([
        DomainProfile("general_biomedical", aliases=("biomedical",), prompt_id="general_biomedical"),
        DomainProfile(
            "neuropharmacology",
            aliases=("ketamine", "depression"),
            prompt_id="neuropharmacology",
        ),
    ])
