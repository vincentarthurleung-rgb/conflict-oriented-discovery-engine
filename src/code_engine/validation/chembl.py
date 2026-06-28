"""Local-index-aware ChEMBL validator skeleton."""

from code_engine.validation.skeleton import ExternalIndexValidator


class ChEMBLValidator(ExternalIndexValidator):
    name = "ChEMBLValidator"
    supported_domains = ("drug_target_binding", "neuropharmacology")
    supported_relation_types = ("drug_target_binding", "receptor_modulation")
    supported_entity_types = ("compound", "protein", "receptor_complex")
    required_resources = ("chembl_index",)
    supported_anchor_types = ("triple_anchor", "hypothesis_anchor", "mechanism_gap_anchor")
    supported_validation_intents = ("binding_activity_check",)
    supports_local_index = True
    supports_remote_api = True
    index_name = "chembl"
    source_database = "ChEMBL"
    evidence_type = "binding_activity_record"
    default_signal_type = "binding_support"
    interpretation_limits = ("Binding/activity record is not mechanism proof.",)
