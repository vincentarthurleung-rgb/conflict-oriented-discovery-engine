"""curated_omics validation index builder."""

from code_engine.validation.index_builders.base import ValidationIndexBuilder


class CuratedOmicsIndexBuilder(ValidationIndexBuilder):
    name = "curated_omics_index_builder"
    validator_name = "CuratedOmicsValidator"
    schema_name = "curated_omics"


__all__ = ["CuratedOmicsIndexBuilder"]
