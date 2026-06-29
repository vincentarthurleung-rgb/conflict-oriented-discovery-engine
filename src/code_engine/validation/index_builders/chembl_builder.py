"""chembl validation index builder."""

from code_engine.validation.index_builders.base import ValidationIndexBuilder


class ChEMBLIndexBuilder(ValidationIndexBuilder):
    name = "chembl_index_builder"
    validator_name = "ChEMBLValidator"
    schema_name = "chembl"


__all__ = ["ChEMBLIndexBuilder"]
