"""Prospective, offline JATS primary-source identity integrity V2.

Keep the historical XML article-selection rules. Replace only direct-identifier
binding: canonical PMCID anchor plus present-must-agree secondary assertions.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from code_engine.extraction_assets.source_identity import normalize_identifier
from scripts import search_plan_v24_alpha318a1_source_contracts as policy


VERSION = "JATSPrimarySourceIdentityContractV2"
TYPE_MAP = {"pmc": "pmcid", "pmcid": "pmcid", "pmid": "pmid", "doi": "doi"}
SCOPE = "article/front/article-meta/article-id (direct child chain only)"
SUCCESS = "JATS_PRIMARY_IDENTITY_EXACTLY_BOUND"
CONFLICT = "JATS_DIRECT_IDENTIFIER_INTERNAL_CONFLICT"
UNRESOLVED = "JATS_PRIMARY_IDENTITY_UNRESOLVED"
FAILURE_PRECEDENCE = [CONFLICT, "JATS_PRIMARY_PMCID_MISSING", "JATS_PRIMARY_PMCID_MISMATCH",
                      "JATS_DIRECT_PMID_MISMATCH", "JATS_DIRECT_DOI_MISMATCH", UNRESOLVED]


def select_primary_article(raw: bytes) -> ET.Element:
    """Exactly the legacy canonical_jats XML parseability/article-count guard."""
    root = ET.fromstring(raw)
    articles = [node for node in root.iter() if policy.local(node.tag) == "article"]
    if len(articles) != 1:
        raise ValueError("JATS_ARTICLE_COUNT_INVALID")
    return articles[0]


def direct_identifiers(article: ET.Element) -> dict:
    records, unsupported = [], []
    fronts = policy.children(article, "front")
    metadata = [(front_number, meta_number, meta)
                for front_number, front in enumerate(fronts, 1)
                for meta_number, meta in enumerate(policy.children(front, "article-meta"), 1)]
    for front_number, meta_number, meta in metadata:
        for id_number, node in enumerate(policy.children(meta, "article-id"), 1):
            raw_type = node.get("pub-id-type", "")
            vocabulary_type = raw_type.casefold()
            raw_value = policy.node_text(node)
            provenance = {"front_ordinal": front_number, "article_meta_ordinal": meta_number,
                "article_id_ordinal": id_number, "pub_id_type": raw_type, "raw_value": raw_value,
                "path": SCOPE}
            if vocabulary_type not in TYPE_MAP:
                unsupported.append(provenance)
                continue
            kind = TYPE_MAP[vocabulary_type]
            records.append({**provenance, "identifier_type": kind,
                "canonical_value": normalize_identifier(raw_value, kind)})
    summaries = {}
    for kind in ("pmcid", "pmid", "doi"):
        assertions = [r for r in records if r["identifier_type"] == kind]
        values = sorted({r["canonical_value"] for r in assertions if r["canonical_value"]})
        unusable = sum(not r["canonical_value"] for r in assertions)
        summaries[kind] = {"assertion_count": len(assertions), "canonical_values": values,
            "distinct_canonical_count": len(values), "unusable_assertion_count": unusable,
            "effective_value": values[0] if len(values) == 1 else None,
            "multiplicity_state": CONFLICT if len(values) > 1 else
                "DIRECT_IDENTIFIER_REDUNDANT_SAME_VALUE" if len(assertions) > 1 and len(values) == 1 and not unusable else
                "DIRECT_IDENTIFIER_UNUSABLE_ASSERTION" if unusable else
                "DIRECT_IDENTIFIER_SINGLE_VALUE" if assertions else "DIRECT_IDENTIFIER_NOT_ASSERTED"}
    return {"scope": SCOPE, "assertions": records, "unsupported_types_audit_only": unsupported,
            "identifier_summaries": summaries, "reference_or_related_identifiers_scanned": False}


def validate_jats_primary_identity_v2(raw: bytes, *, expected_pmid: str,
                                      expected_pmcid: str, expected_doi: str | None) -> dict:
    """Return all identity dimensions; invalid XML remains a validity failure."""
    expected = {kind: normalize_identifier(value, kind) for kind, value in
                (("pmid", expected_pmid), ("pmcid", expected_pmcid), ("doi", expected_doi))}
    if not (isinstance(expected_pmid, str) and isinstance(expected_pmcid, str)
            and expected["pmid"] and re.fullmatch(r"[1-9][0-9]*", expected["pmid"])
            and expected["pmcid"] and re.fullmatch(r"PMC[1-9][0-9]*", expected["pmcid"])
            and (expected_doi is None or isinstance(expected_doi, str) and bool(expected["doi"]))):
        raise ValueError("CONTROLLER_EXPECTED_PRIMARY_IDENTITY_INVALID")
    try:
        article = select_primary_article(raw)
    except (ET.ParseError, ValueError) as exc:
        return {"schema_version": VERSION, "expected_identity": expected,
            "jats_validity_state": "JATS_FAILED_NO_REPLACEMENT", "structural_error": type(exc).__name__ + ":" + str(exc),
            "identity_state": None, "identity_failures": [], "direct_identifiers": None,
            "source_identity_allows_progression": False,
            "structural_parser_failure_is_identifier_mismatch": False}
    direct = direct_identifiers(article)
    summaries = direct["identifier_summaries"]
    states, failures = {}, set()
    for kind in ("pmcid", "pmid", "doi"):
        summary = summaries[kind]
        value = summary["effective_value"]
        if summary["distinct_canonical_count"] > 1:
            states[kind] = CONFLICT
            failures.add(CONFLICT)
            continue
        if kind == "pmcid" and value is None:
            states[kind] = "JATS_PRIMARY_PMCID_MISSING"
        elif summary["unusable_assertion_count"]:
            # A recognized but empty/unusable assertion is not silent absence.
            states[kind] = UNRESOLVED
        elif kind == "pmcid":
            states[kind] = "JATS_PRIMARY_PMCID_MATCH" if value == expected[kind] else "JATS_PRIMARY_PMCID_MISMATCH"
        elif summary["assertion_count"] == 0:
            states[kind] = "JATS_DIRECT_" + kind.upper() + "_NOT_ASSERTED"
        elif kind == "doi" and expected["doi"] is None:
            states[kind] = "JATS_DIRECT_DOI_NEW_ASSERTION"
        else:
            states[kind] = "JATS_DIRECT_" + kind.upper() + ("_MATCH" if value == expected[kind] else "_MISMATCH")
        if states[kind] in FAILURE_PRECEDENCE:
            failures.add(states[kind])
    ordered_failures = [state for state in FAILURE_PRECEDENCE if state in failures]
    terminal = ordered_failures[0] if ordered_failures else SUCCESS
    return {"schema_version": VERSION, "expected_identity": expected,
        "jats_validity_state": "JATS_XML_ARTICLE_STRUCTURE_VALID", "structural_error": None,
        "direct_identifiers": direct, "per_identifier_states": states,
        "identity_state": terminal, "identity_failures": ordered_failures,
        "source_identity_allows_progression": terminal == SUCCESS,
        "missing_secondary_assertions_are_identity_evidence": False,
        "authoritative_new_doi_assertion": summaries["doi"]["effective_value"]
            if terminal == SUCCESS and states["doi"] == "JATS_DIRECT_DOI_NEW_ASSERTION" else None,
        "conflicting_assertions_authoritative_for_exposure": False,
        "majority_vote_used": False, "scientific_content_used": False}
