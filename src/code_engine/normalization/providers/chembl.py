"""ChEMBL-backed normalization candidate provider metadata."""

from code_engine.normalization.providers.base import ExternalCandidateProvider


class ChEMBLCandidateProvider(ExternalCandidateProvider):
    name = "ChEMBLCandidateProvider"
    resource_name = "ChEMBL"
    supported_entity_types = ["compound", "drug", "metabolite", "protein", "receptor", "receptor_complex"]
