"""Local-index-aware STRING validator skeleton."""

from code_engine.validation.skeleton import ExternalIndexValidator


class STRINGValidator(ExternalIndexValidator):
    name = "STRINGValidator"
    supported_domains = ("protein_interaction",)
    supported_relation_types = ("protein_interaction", "ligand_receptor")
    supported_entity_types = ("gene", "protein", "receptor_complex")
    required_resources = ("string_index",)
