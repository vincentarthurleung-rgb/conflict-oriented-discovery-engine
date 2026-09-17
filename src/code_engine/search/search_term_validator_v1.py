"""Deterministic, non-authoritative term classification for v2.4-dev plans."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from typing import Any

from code_engine.search.proposition_aware_query_planner_v1 import (
    canonical_bytes,
    sha256_value,
    validate_plan,
)
from code_engine.search.retrieval_intent_v1 import DIMENSION_ORDER


VALIDATOR_VERSION = "SearchTermValidatorV1"
USABLE_CLASSES = frozenset({"AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION"})
NONEXECUTABLE_CLASSES = frozenset({"UNRESOLVED", "REJECTED"})


class SearchTermValidationError(ValueError):
    """Raised when term provenance or authority is malformed."""


def normalize_term(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _unsafe(term: str) -> bool:
    value = str(term)
    folded = value.casefold()
    return (
        not value.strip()
        or len(value) > 240
        or any(ord(char) < 32 for char in value)
        or any(token in folded for token in ("http://", "https://", "<script", "drop table"))
        or bool(re.search(r"\b(?:AND|OR|NOT)\b|\[[^]]+\]", value))
    )


def _authority_index(authorities: dict[str, Any]) -> dict[tuple[str, str], dict[str, str]]:
    result: dict[tuple[str, str], dict[str, str]] = {}
    for record in authorities.get("records", []):
        concept_type = record.get("concept_type")
        reference = str(record.get("authority_reference") or "")
        if concept_type not in DIMENSION_ORDER or not reference:
            raise SearchTermValidationError("authority record lacks generic concept type or reference")
        for term in record.get("terms", []):
            normalized = normalize_term(term)
            if not normalized:
                raise SearchTermValidationError("authority record contains empty term")
            key = (concept_type, normalized)
            existing = result.get(key)
            if existing and existing["authority_reference"] != reference:
                raise SearchTermValidationError("ambiguous deterministic term authority")
            result[key] = {"authority_reference": reference, "term": str(term)}
    return result


def _classify(
    item: dict[str, Any],
    *,
    concept_type: str,
    authority: dict[tuple[str, str], dict[str, str]],
) -> tuple[str, str | None, str]:
    term = str(item.get("term") or "")
    proposed = item.get("proposal_class")
    source = item.get("proposal_source")
    if _unsafe(term):
        return "REJECTED", None, "generic lexical-safety rejection"
    match = authority.get((concept_type, normalize_term(term)))
    if source == "CANONICAL_TARGET":
        reference = str(item.get("authority_reference") or "")
        if not reference.startswith("ScientificPropositionTargetV1#"):
            raise SearchTermValidationError("canonical target term lacks target-field authority")
        return "AUTHORIZED_EQUIVALENT", reference, "verbatim canonical target authority"
    if match:
        return "AUTHORIZED_EQUIVALENT", match["authority_reference"], "exact deterministic authority match"
    if source == "DETERMINISTIC_AUTHORITY":
        return "UNRESOLVED", None, "claimed authority did not match supplied frozen authority"
    if source != "LLM_PROPOSAL":
        return "REJECTED", None, "unknown proposal source"
    if proposed == "REJECTED":
        return "REJECTED", None, "planner-declared rejection preserved fail closed"
    if proposed == "UNRESOLVED":
        return "UNRESOLVED", None, "planner-declared uncertainty preserved fail closed"
    return "SEARCH_ONLY_EXPANSION", None, "well-formed LLM retrieval vocabulary without equivalence authority"


def validate_and_classify_plan_terms(
    plan: dict[str, Any],
    *,
    authorities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a classified plan plus a hash-bound validation receipt.

    The canonical proposition is copied byte-for-byte and never rewritten from a
    proposal. LLM claims of authorization are ignored unless deterministic
    authority independently matches the term.
    """
    validate_plan(plan)
    original_target = canonical_bytes(plan["canonical_proposition"])
    classified = deepcopy(plan)
    authority = _authority_index(authorities or {"records": []})
    audit = []
    counts = {name: 0 for name in ("AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION", "UNRESOLVED", "REJECTED")}
    for intent in classified["retrieval_intents"]:
        for concept in intent["search_concepts"]:
            concept_type = concept["concept_type"]
            concept_item = {
                "term": str(concept["canonical_value"] or concept["concept_id"]),
                "proposal_source": concept["proposal_source"],
                "proposal_class": concept["proposal_class"],
                "authority_reference": concept["authority_reference"],
            }
            cls, ref, reason = _classify(concept_item, concept_type=concept_type, authority=authority)
            concept["proposal_class"] = cls
            concept["authority_reference"] = ref
            audit.append({"item_id": concept["concept_id"], "item_kind": "concept", "assigned_class": cls, "reason": reason})
            counts[cls] += 1
            for term in concept["proposed_terms"]:
                cls, ref, reason = _classify(term, concept_type=concept_type, authority=authority)
                term["proposal_class"] = cls
                term["authority_reference"] = ref
                audit.append({"item_id": term["term_id"], "item_kind": "term", "assigned_class": cls, "reason": reason})
                counts[cls] += 1
    if canonical_bytes(classified["canonical_proposition"]) != original_target:
        raise SearchTermValidationError("term classification changed canonical identity")
    validate_plan(classified)
    plan_hash = sha256_value(classified)
    receipt_material = {
        "artifact_schema_version": "SearchTermValidationReceiptV1",
        "validator_version": VALIDATOR_VERSION,
        "status": "PASS",
        "validated_plan_sha256": plan_hash,
        "canonical_target_sha256": classified["canonical_proposition"]["target_sha256"],
        "canonical_identity_unchanged": True,
        "classification_counts": counts,
        "classification_audit": audit,
        "authority_manifest_sha256": sha256_value(authorities or {"records": []}),
    }
    receipt_material["receipt_sha256"] = hashlib.sha256(canonical_bytes(receipt_material)).hexdigest()
    return {"validated_plan": classified, "validation_receipt": receipt_material}


__all__ = [
    "NONEXECUTABLE_CLASSES",
    "SearchTermValidationError",
    "USABLE_CLASSES",
    "VALIDATOR_VERSION",
    "normalize_term",
    "validate_and_classify_plan_terms",
]
