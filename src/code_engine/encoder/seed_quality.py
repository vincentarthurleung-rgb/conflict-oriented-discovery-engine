"""Generic linguistic quality checks for non-evidence seed triples."""
from __future__ import annotations

from typing import Any

STOPWORD_OBJECTS = {"has","have","had","is","are","was","were","in","on","and","or","but","with","without",
                    "role","roles","effect","effects","result","results","associated","association"}


def validate_seed_triple(seed: dict[str, Any], *, confidence_threshold: float = 0.6) -> dict[str, Any]:
    def name(field: str) -> str:
        value=seed.get(field); return str(value.get("name") or "").strip() if isinstance(value,dict) else str(value or "").strip()
    subject,obj,relation=name("subject"),name("object"),name("relation")
    confidence=float(seed.get("confidence") or 0.0); review=bool(seed.get("human_review_required"))
    warnings=[]; invalid=False
    for field,value in (("subject",subject),("object",obj),("relation",relation)):
        if not value: warnings.append(f"seed_{field}_missing"); invalid=True
    if obj.casefold() in STOPWORD_OBJECTS: warnings.append("seed_object_is_stopword"); invalid=True
    if subject and obj and subject.casefold()==obj.casefold(): warnings.append("seed_subject_object_identical"); invalid=True
    for field,value in (("subject",subject),("object",obj)):
        if value and len(value)<2: warnings.append(f"seed_{field}_too_short"); invalid=True
    if relation.casefold()=="unspecified_association" and confidence<confidence_threshold:
        warnings.append("low_confidence_unspecified_relation")
    if confidence<confidence_threshold: warnings.append("seed_confidence_below_threshold")
    if review: warnings.append("seed_requires_human_review")
    quality="invalid" if invalid else "low" if confidence<confidence_threshold or review else "high" if confidence>=0.8 else "medium"
    return {"valid":not invalid,"quality":quality,"warnings":list(dict.fromkeys(warnings)),
            "subject":subject,"relation":relation,"object":obj,"confidence":confidence,"human_review_required":review}


__all__=["STOPWORD_OBJECTS","validate_seed_triple"]
