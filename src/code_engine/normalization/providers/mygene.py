"""MyGene-backed normalization candidate provider metadata."""

from code_engine.normalization.providers.base import ExternalCandidateProvider


class MyGeneCandidateProvider(ExternalCandidateProvider):
    name = "MyGeneCandidateProvider"
    resource_name = "EntrezGene"
    supported_entity_types = ["gene", "protein"]
