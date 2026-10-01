#!/usr/bin/env python3
"""Offline PubMed primary-citation identity binding for alpha3.18A.5.

Only direct PubmedData/ArticleIdList identifiers identify the sampled paper.
Reference identifiers are counted for the contamination audit, never identity.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

try:
    from scripts import search_plan_v24_alpha318a1_source_contracts as policy
except ModuleNotFoundError:
    import search_plan_v24_alpha318a1_source_contracts as policy


def _children(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in node if policy.local(child.tag) == name]


def _id_records(nodes: list[ET.Element]) -> list[dict[str, str]]:
    return [{"id_type": node.get("IdType", ""), "value": policy.node_text(node)}
            for node in nodes if policy.local(node.tag) == "ArticleId"]


def _distinct(records: list[dict[str, str]], kind: str) -> list[str]:
    return sorted({record["value"] for record in records if record["id_type"] == kind})


def _publication_types(citation: ET.Element) -> list[str]:
    types: list[str] = []
    for article in _children(citation, "Article"):
        for group in _children(article, "PublicationTypeList"):
            types.extend(policy.node_text(entry) for entry in _children(group, "PublicationType"))
    return types


def _relationships(citation: ET.Element) -> list[dict[str, str | None]]:
    refs: list[dict[str, str | None]] = []
    for group in _children(citation, "CommentsCorrectionsList"):
        for entry in _children(group, "CommentsCorrections"):
            pmids = _children(entry, "PMID")
            sources = _children(entry, "RefSource")
            refs.append({"ref_type": entry.get("RefType", ""),
                         "linked_pmid": policy.node_text(pmids[0]) if pmids else None,
                         "ref_source": policy.node_text(sources[0]) if sources else None})
    return refs


def _year(citation: ET.Element) -> tuple[int | None, str | None]:
    articles = _children(citation, "Article")
    if len(articles) != 1:
        return None, "ARTICLE_METADATA_MISSING_OR_DUPLICATE"
    years: set[int] = set()
    for node in articles[0].iter():
        if policy.local(node.tag) not in {"PubDate", "ArticleDate"}:
            continue
        for date_node in node.iter():
            name = policy.local(date_node.tag)
            value = (date_node.text or "").strip()
            if name == "Year" and re.fullmatch(r"[0-9]{4}", value):
                years.add(int(value))
            elif name == "MedlineDate":
                years.update(int(item) for item in re.findall(r"\b(?:19|20)[0-9]{2}\b", value))
    if len(years) != 1 or not (2018 <= next(iter(years)) <= 2023):
        return None, "PUBLICATION_DATE_YEAR_AMBIGUOUS_OR_OUT_OF_WINDOW"
    return next(iter(years)), None


def bind_primary_citation(raw: bytes, expected_pmid: str) -> dict[str, Any]:
    """Bind by direct MedlineCitation/PMID; reject missing/duplicate/mismatch.

    PMCID/DOI zero-one-many semantics remain the frozen original semantics:
    exact IdType='pmc' and IdType='doi', distinct values, no new normalization.
    """
    root = ET.fromstring(raw)
    matching: list[tuple[ET.Element, ET.Element]] = []
    for article in root.iter():
        if policy.local(article.tag) != "PubmedArticle":
            continue
        citations = _children(article, "MedlineCitation")
        if len(citations) != 1:
            continue
        pmids = [policy.node_text(node) for node in _children(citations[0], "PMID")]
        if pmids == [expected_pmid]:
            matching.append((article, citations[0]))
    if not matching:
        raise ValueError("PRIMARY_CITATION_RECORD_MISSING")
    if len(matching) != 1:
        raise ValueError("PRIMARY_CITATION_RECORD_DUPLICATE")
    article, citation = matching[0]
    pubmed_data = _children(article, "PubmedData")
    if len(pubmed_data) > 1:
        raise ValueError("PRIMARY_CITATION_PUBMEDDATA_DUPLICATE")
    data = pubmed_data[0] if pubmed_data else None
    direct: list[dict[str, str]] = []
    references: list[dict[str, str]] = []
    legacy: list[dict[str, str]] = []
    if data is not None:
        lists = _children(data, "ArticleIdList")
        if len(lists) > 1:
            raise ValueError("PRIMARY_CITATION_ARTICLE_ID_LIST_DUPLICATE")
        if lists:
            direct = _id_records(list(lists[0]))
        # The two traversals below serve only the historical contamination audit.
        # Neither result is used to derive current-article identity.
        for ref_list in _children(data, "ReferenceList"):
            references.extend(_id_records([node for node in ref_list.iter()
                if policy.local(node.tag) == "ArticleId"]))
        legacy = _id_records([node for node in data.iter()
            if policy.local(node.tag) == "ArticleId"])
    direct_pubmed = _distinct(direct, "pubmed")
    if direct_pubmed and direct_pubmed != [expected_pmid]:
        raise ValueError("PRIMARY_CITATION_PMID_IDENTITY_MISMATCH")
    pmcids = _distinct(direct, "pmc")
    dois = _distinct(direct, "doi")
    year, year_error = _year(citation)
    reasons: list[str] = []
    if len(pmcids) != 1 or not re.fullmatch(r"PMC[1-9][0-9]*", pmcids[0]):
        reasons.append("PMCID_MISSING_OR_AMBIGUOUS")
    if len(dois) > 1:
        reasons.append("DOI_AMBIGUOUS")
    if year_error:
        reasons.append(year_error)
    return {
        "expected_sampled_pmid": expected_pmid,
        "matched_medlinecitation_pmid": expected_pmid,
        "matching_pubmed_article_count": 1,
        "direct_primary_article_ids": direct,
        "reference_article_ids": references,
        "legacy_recursive_article_ids_audit_only": legacy,
        "direct_pubmed_ids": direct_pubmed,
        "direct_pmcid_values": pmcids,
        "direct_doi_values": dois,
        "legacy_pmcid_values": _distinct(legacy, "pmc"),
        "legacy_doi_values": _distinct(legacy, "doi"),
        "pmcid": pmcids[0] if len(pmcids) == 1 and re.fullmatch(r"PMC[1-9][0-9]*", pmcids[0]) else None,
        "doi": dois[0] if len(dois) == 1 else None,
        "publication_year": year,
        "publication_types": _publication_types(citation),
        "correction_relationships": _relationships(citation),
        "metadata_state": "RESOLVED" if not reasons else "UNRESOLVED",
        "metadata_unresolved_reasons": reasons,
    }
