"""Deterministic validation-question construction."""

import hashlib

from code_engine.schemas.validation import ValidationQuestion


def build_validation_question(hypothesis, domain_profile, relation_type: str, subject: str = "", obj: str = "") -> ValidationQuestion:
    def value(name: str, default=""):
        if isinstance(hypothesis, dict):
            return hypothesis.get(name, default)
        return getattr(hypothesis, name, default)
    hypothesis_id = str(value("hypothesis_id", "UNKNOWN"))
    if not subject or not obj:
        seed = str(value("seed_pair", ""))
        if "->" in seed:
            subject, obj = [part.strip() for part in seed.split("->", 1)]
    stable = f"{hypothesis_id}|{domain_profile.domain_id}|{relation_type}|{subject}|{obj}"
    return ValidationQuestion(
        question_id=hashlib.sha256(stable.encode()).hexdigest()[:16],
        hypothesis_id=hypothesis_id,
        domain_id=domain_profile.domain_id,
        validator_profile_id=domain_profile.validator_profile_id,
        relation_type=relation_type,
        subject_entity=subject,
        object_entity=obj,
        question_text=f"Does external evidence support {subject} {relation_type} {obj}?",
        preferred_validators=list(domain_profile.preferred_validators),
        fallback_validators=list(domain_profile.fallback_validators),
    )
