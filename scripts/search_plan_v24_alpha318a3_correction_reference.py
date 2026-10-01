"""Frozen alpha3.18A.3 linked-citation eligibility; no network or inference."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


SCHEMA_VERSION = "CorrectionReferenceEligibilityV1"
STATES = (
    "CORRECTION_REFERENCE_CLEAR",
    "CORRECTION_REFERENCE_INELIGIBLE",
    "CORRECTION_REFERENCE_UNRESOLVED",
)

# Exact strings from the user-supplied linked-citation protocol. The locally
# preserved PubMed XML contains a subset; an unknown future RefType fails closed.
HARD_INELIGIBLE = frozenset({
    "RetractionIn", "ExpressionOfConcernIn", "CorrectedandRepublishedIn",
    "RetractedandRepublishedIn", "RetractionOf", "ExpressionOfConcernFor",
    "ErratumFor",
})
UNRESOLVED = frozenset({
    "ErratumIn", "UpdateIn", "CorrectedandRepublishedFrom",
    "RetractedandRepublishedFrom",
})
CONDITIONAL_UPDATE = frozenset({"UpdateOf"})
ORDINARY = frozenset({
    "CommentIn", "CommentOn", "AssociatedDataset", "AssociatedPublication",
    "Cites", "SummaryForPatientsIn", "OriginalReportIn",
})
RECOGNIZED = HARD_INELIGIBLE | UNRESOLVED | CONDITIONAL_UPDATE | ORDINARY
EXPLICIT_PUBLICATION_TYPE_EXCLUSIONS = frozenset({
    "Retracted Publication", "Retraction Notice", "Published Erratum",
})


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_pubmed_relationships(raw_xml: bytes) -> dict[str, Any]:
    """Extract only structured types and linked-citation provenance from one article."""
    root = ET.fromstring(raw_xml)
    articles = [node for node in root.iter() if _local(node.tag) == "PubmedArticle"]
    if len(articles) != 1:
        raise ValueError("exactly one PubmedArticle required")
    citation = next((node for node in articles[0] if _local(node.tag) == "MedlineCitation"), None)
    if citation is None:
        raise ValueError("MedlineCitation required")
    types: list[str] = []
    refs: list[dict[str, str | None]] = []
    for node in citation:
        if _local(node.tag) == "Article":
            for group in node:
                if _local(group.tag) == "PublicationTypeList":
                    for entry in group:
                        if _local(entry.tag) == "PublicationType":
                            types.append("".join(entry.itertext()).strip())
        elif _local(node.tag) == "CommentsCorrectionsList":
            for entry in node:
                if _local(entry.tag) != "CommentsCorrections":
                    continue
                linked_pmid = next(("".join(child.itertext()).strip() for child in entry
                                    if _local(child.tag) == "PMID"), None)
                ref_source = next(("".join(child.itertext()).strip() for child in entry
                                   if _local(child.tag) == "RefSource"), None)
                refs.append({"ref_type": entry.get("RefType", ""),
                             "linked_pmid": linked_pmid or None,
                             "ref_source": ref_source or None})
    return {"publication_types": types, "relationships": refs}


def classify(publication_types: list[str], relationships: list[dict[str, str | None]],
             independent_primary_state: str | None = None) -> dict[str, Any]:
    """Apply INELIGIBLE > UNRESOLVED > CLEAR, preserving all matching reasons.

    UpdateOf is provisionally unresolved before JATS. After the frozen JATS
    source-type gate, re-evaluate it using the source's independent state.
    """
    if independent_primary_state not in (None, "SOURCE_TYPE_ELIGIBLE",
                                         "SOURCE_TYPE_INELIGIBLE", "SOURCE_TYPE_UNRESOLVED"):
        raise ValueError("invalid independent primary-source state")
    ineligible: list[str] = []
    unresolved: list[str] = []
    for publication_type in sorted(set(publication_types) & EXPLICIT_PUBLICATION_TYPE_EXCLUSIONS):
        ineligible.append("PUBLICATION_TYPE:" + publication_type)
    for relation in relationships:
        ref_type = relation.get("ref_type") or ""
        if ref_type in HARD_INELIGIBLE:
            ineligible.append("REF_TYPE:" + ref_type)
        elif ref_type in UNRESOLVED:
            unresolved.append("REF_TYPE:" + ref_type)
        elif ref_type in CONDITIONAL_UPDATE:
            if independent_primary_state == "SOURCE_TYPE_INELIGIBLE":
                ineligible.append("REF_TYPE:UpdateOf:INDEPENDENT_SOURCE_INELIGIBLE")
            elif independent_primary_state != "SOURCE_TYPE_ELIGIBLE":
                unresolved.append("REF_TYPE:UpdateOf:INDEPENDENT_SOURCE_NOT_YET_ELIGIBLE")
        elif ref_type not in ORDINARY:
            unresolved.append("UNKNOWN_REF_TYPE:" + (ref_type or "<MISSING>"))
    if ineligible:
        state = "CORRECTION_REFERENCE_INELIGIBLE"
    elif unresolved:
        state = "CORRECTION_REFERENCE_UNRESOLVED"
    else:
        state = "CORRECTION_REFERENCE_CLEAR"
    return {"schema_version": SCHEMA_VERSION, "state": state,
            "ineligible_reasons": sorted(set(ineligible)),
            "unresolved_reasons": sorted(set(unresolved)),
            "linked_relationships": relationships,
            "claim_boundary": "frozen local PubMed citation snapshot only; CLEAR is not global publication-integrity proof"}
