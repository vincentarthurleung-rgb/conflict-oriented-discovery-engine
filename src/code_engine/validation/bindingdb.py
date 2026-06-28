"""Local-index-aware BindingDB validator skeleton."""

from code_engine.validation.skeleton import ExternalIndexValidator


class BindingDBValidator(ExternalIndexValidator):
    name = "BindingDBValidator"
    supported_domains = ("drug_target_binding", "neuropharmacology")
    supported_relation_types = ("drug_target_binding", "receptor_modulation")
    supported_entity_types = ("compound", "protein", "receptor_complex")
    required_resources = ("bindingdb_index",)
