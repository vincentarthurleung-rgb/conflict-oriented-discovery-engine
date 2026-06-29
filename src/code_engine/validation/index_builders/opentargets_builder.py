"""opentargets validation index builder."""

from code_engine.validation.index_builders.base import ValidationIndexBuilder


class OpenTargetsIndexBuilder(ValidationIndexBuilder):
    name = "opentargets_index_builder"
    validator_name = "OpenTargetsValidator"
    schema_name = "opentargets"


__all__ = ["OpenTargetsIndexBuilder"]
