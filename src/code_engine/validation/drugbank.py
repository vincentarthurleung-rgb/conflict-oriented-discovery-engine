"""Local-index-aware DrugBank validator skeleton."""

from code_engine.validation.skeleton import ExternalIndexValidator


class DrugBankValidator(ExternalIndexValidator):
    name = "DrugBankValidator"
    supported_domains = ("drug_target_binding", "neuropharmacology")
    supported_relation_types = ("drug_target_binding", "receptor_modulation")
    supported_entity_types = ("compound", "protein", "receptor_complex")
    required_resources = ("drugbank_index",)
    supported_anchor_types = ("entity_anchor", "triple_anchor", "hypothesis_anchor")
    supported_validation_intents = ("identity_lookup", "binding_activity_check")
    supports_local_index = True
    index_name = "drugbank"
    source_database = "DrugBank"
    evidence_type = "curated_drug_target_record"
    default_signal_type = "target_prior"
    interpretation_limits = ("DrugBank target identity is not mechanism proof.", "Licensed data must be configured locally.")
