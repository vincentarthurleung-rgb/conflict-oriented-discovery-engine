from code_engine.normalization.providers.base import ExternalCandidateProvider


class UniProtCandidateProvider(ExternalCandidateProvider):
    name = "UniProtCandidateProvider"
    resource_name = "UniProt"
    supported_entity_types = ["protein", "gene", "receptor", "receptor_complex", "protein_complex"]
