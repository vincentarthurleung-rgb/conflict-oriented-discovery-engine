"""Deterministic first-class domain routing."""

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

    def route_text(self, text: str) -> DomainProfile:
        lowered = str(text or "").casefold()
        clinical = ("clinical", "trial", "efficacy", "safety", "remission", "response rate", "treatment-resistant", "临床", "疗效", "缓解率")
        binding = ("binding", "affinity", " ki ", "ic50", "ec50", "antagonist", "agonist", "blockade", "receptor blockade", "结合", "阻断")
        interaction = ("protein interaction", "protein-protein", "ppi", "ligand receptor")
        pathway = ("pathway", "signaling cascade", "通路")
        neuro = ("ketamine", "esketamine", "氯胺酮", "艾司氯胺酮", "depression", "抑郁", "bdnf", "mtor", "ampa", "nmda")
        if any(term in lowered for term in clinical):
            return self._profiles["clinical_outcome"]
        if any(term in lowered for term in binding):
            return self._profiles["drug_target_binding"]
        if any(term in lowered for term in interaction):
            return self._profiles["protein_interaction"]
        if any(term in lowered for term in pathway):
            return self._profiles["pathway_biology"]
        if any(term in lowered for term in neuro):
            return self._profiles["neuropharmacology"]
        return self._profiles["general_biomedical"]


def default_domain_router() -> DomainRouter:
    return DomainRouter()
