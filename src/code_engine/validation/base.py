"""Uniform validator plugin interface."""

from code_engine.schemas.validation import ValidationQuestion, ValidationResult


class AbstractValidator:
    name = "AbstractValidator"
    supported_domains: tuple[str, ...] = ()
    supported_relation_types: tuple[str, ...] = ()
    supported_entity_types: tuple[str, ...] = ()
    required_resources: tuple[str, ...] = ()

    def can_validate(self, question) -> bool:
        if not isinstance(question, ValidationQuestion):
            return False
        domain_ok = not self.supported_domains or question.domain_id in self.supported_domains
        relation_ok = not self.supported_relation_types or question.relation_type in self.supported_relation_types
        observed_types = {
            str(question.context.get("subject_entity_type") or ""),
            str(question.context.get("object_entity_type") or ""),
        } - {""}
        entity_ok = (
            not self.supported_entity_types
            or not observed_types
            or bool(observed_types.intersection(self.supported_entity_types))
        )
        return domain_ok and relation_ok and entity_ok

    def validate(self, question: ValidationQuestion) -> ValidationResult:
        raise NotImplementedError
