"""Deterministic validation-question construction."""

import hashlib
import json
from pathlib import Path

from code_engine.schemas.validation import ValidationAnchor, ValidationQuestion


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


def build_validation_questions_from_anchors(
    anchors: list[ValidationAnchor], domain_profile: dict | None = None,
) -> list[ValidationQuestion]:
    """Translate anchors into semantic questions without executing providers."""

    profile = domain_profile or {}
    if hasattr(profile, "to_dict"):
        profile = profile.to_dict()
    questions = []
    for anchor in anchors:
        hypothesis_id = anchor.linked_hypothesis_ids[0] if anchor.linked_hypothesis_ids else "UNKNOWN"
        stable = f"{anchor.anchor_id}|{anchor.validation_intent}"
        entities = [dict(item) for item in anchor.entities]
        canonical_count = sum(bool(item.get("canonical_id") or item.get("id")) for item in entities)
        warnings = list(anchor.warnings)
        if canonical_count < len(entities):
            warnings.append("exploratory_question_missing_canonical_entities")
        questions.append(ValidationQuestion(
            question_id=hashlib.sha256(stable.encode()).hexdigest()[:16],
            hypothesis_id=hypothesis_id,
            anchor_id=anchor.anchor_id,
            validator_intent=anchor.validation_intent,
            domain_id=anchor.domain_id or profile.get("domain_id"),
            validator_profile_id=str(profile.get("validator_profile_id") or "general_validation"),
            relation_type=anchor.relation_family or "unknown",
            relation_family=anchor.relation_family,
            polarity_type=anchor.polarity_type,
            direction=anchor.direction,
            entities=entities,
            subject_entity=str(entities[0].get("name") or "") if entities else "",
            object_entity=str(entities[1].get("name") or "") if len(entities) > 1 else "",
            context=dict(anchor.contexts),
            contexts=dict(anchor.contexts),
            expected_direction=anchor.direction,
            quality_requirements={"canonical_entity_count": canonical_count, "minimum_anchor_confidence": 0.5},
            question_text=f"Assess {anchor.validation_intent} for anchor {anchor.anchor_id} using conservative external evidence.",
            preferred_validators=list(profile.get("preferred_validators") or []),
            fallback_validators=list(profile.get("fallback_validators") or ["NullValidator"]),
            warnings=list(dict.fromkeys(warnings)),
        ))
    return questions


def write_validation_questions(questions: list[ValidationQuestion], output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    records = output / "validation_questions.jsonl"
    summary = output / "validation_question_summary.json"
    records.write_text("".join(item.model_dump_json() + "\n" for item in questions), encoding="utf-8")
    intents: dict[str, int] = {}
    for item in questions:
        intents[item.validator_intent] = intents.get(item.validator_intent, 0) + 1
    summary.write_text(json.dumps({"question_count": len(questions), "validation_intent_counts": intents}, indent=2), encoding="utf-8")
    return {"questions": str(records), "summary": str(summary)}


__all__ = ["build_validation_question", "build_validation_questions_from_anchors", "write_validation_questions"]
