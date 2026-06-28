"""Local-index-aware ChEMBL validator skeleton."""

from code_engine.validation.skeleton import ExternalIndexValidator


class ChEMBLValidator(ExternalIndexValidator):
    name = "ChEMBLValidator"
    supported_domains = ("drug_target_binding", "neuropharmacology")
    supported_relation_types = ("drug_target_binding", "receptor_modulation")
    supported_entity_types = ("compound", "protein", "receptor_complex")
    required_resources = ("chembl_index",)
