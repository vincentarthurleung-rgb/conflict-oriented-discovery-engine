"""PubChem-backed normalization candidate provider metadata."""

from code_engine.normalization.providers.base import ExternalCandidateProvider


class PubChemCandidateProvider(ExternalCandidateProvider):
    name = "PubChemCandidateProvider"
    resource_name = "PubChem"
    supported_entity_types = ["compound", "drug", "metabolite"]
