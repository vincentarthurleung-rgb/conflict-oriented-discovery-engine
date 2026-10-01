#!/usr/bin/env python3
"""Prospective, offline alpha3.18A.1 source-policy functions; no network I/O."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit


METHODS_HEADINGS = frozenset({
    "methods", "materials and methods", "methods and materials",
    "experimental procedures", "experimental methods",
})
RESULTS_HEADINGS = frozenset({"results", "results and discussion"})
OTHER_EXCLUDED_HEADINGS = frozenset({
    "acknowledgments", "acknowledgements", "funding", "funding statement",
    "author contributions", "conflict of interest", "conflicts of interest",
    "competing interests", "supplementary material", "supplementary materials",
    "supplementary information", "supporting information", "references", "bibliography",
    "data availability statement", "ethics statement", "publisher s note",
})
EXCLUDED_PUBLICATION_TYPES = frozenset({
    "Case Reports", "Clinical Trial Protocol", "Comment", "Editorial", "Letter",
    "Meta-Analysis", "Network Meta-Analysis", "News", "Preprint", "Published Erratum",
    "Retracted Publication", "Retraction Notice", "Review", "Systematic Review",
    "Video-Audio Media",
})
ACCEPTED_PUBLICATION_TYPES = frozenset({
    "Journal Article", "Clinical Trial", "Clinical Trial, Phase I", "Clinical Trial, Phase II",
    "Comparative Study", "Controlled Clinical Trial", "Randomized Controlled Trial",
    "Observational Study", "Validation Study",
})
NEUTRAL_PUBLICATION_TYPES = frozenset({
    "English Abstract", "Multicenter Study", "Research Support, N.I.H., Extramural",
    "Research Support, N.I.H., Intramural", "Research Support, Non-U.S. Gov't",
    "Research Support, U.S. Gov't, Non-P.H.S.", "Research Support, U.S. Gov't, P.H.S.",
})
LOCAL_PUBLICATION_TYPES = EXCLUDED_PUBLICATION_TYPES | ACCEPTED_PUBLICATION_TYPES | NEUTRAL_PUBLICATION_TYPES
SCHEMA_VERSION = "ConstructionEvidenceDocumentV1"
SPAN_VERSION = "EvidenceSpanAnchorV1"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def children(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in node if local(child.tag) == name]


def first_child(node: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in node if local(child.tag) == name), None)


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def node_text(node: ET.Element, *, remove_bibliography_xrefs: bool = True) -> str:
    parts: list[str] = []
    def visit(current: ET.Element) -> None:
        if current.text:
            parts.append(current.text)
        for child in current:
            if not (remove_bibliography_xrefs and local(child.tag) == "xref" and
                    child.attrib.get("ref-type", "").casefold() == "bibr"):
                visit(child)
            if child.tail:
                parts.append(child.tail)
    visit(node)
    return normalize_text("".join(parts))


def normalize_heading(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    text = re.sub(r"^\s*(?:\d+(?:\.\d+)*|[ivxlcdm]+)[.)]\s*", "", text)
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def oa_subset_esearch_term(pmcid: str) -> str:
    if not re.fullmatch(r"PMC[1-9][0-9]*", pmcid):
        raise ValueError("invalid PMCID")
    numeric_uid = pmcid[3:]
    return f"{numeric_uid}[UID] AND open access[filter]"


def license_class_from_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme.casefold() not in {"http", "https"} or parsed.netloc.casefold() not in {
        "creativecommons.org", "www.creativecommons.org"
    } or parsed.query or parsed.fragment:
        return "UNKNOWN"
    path = parsed.path.rstrip("/").casefold()
    if path == "/publicdomain/zero/1.0":
        return "CC0"
    match = re.fullmatch(r"/licenses/(by|by-sa|by-nc|by-nd|by-nc-sa|by-nc-nd)/(2\.0|2\.5|3\.0|4\.0)", path)
    if not match:
        return "UNKNOWN"
    return {"by": "CC_BY", "by-sa": "CC_BY_SA"}.get(match.group(1), "EXPLICIT_NONWHITELIST_CC")


def extract_license(root: ET.Element) -> dict:
    article_meta = next((node for node in root.iter() if local(node.tag) == "article-meta"), None)
    if article_meta is None:
        return {"state": "UNRESOLVED", "reason": "ARTICLE_META_MISSING", "licenses": []}
    licenses = [node for node in article_meta.iter() if local(node.tag) == "license"]
    if not licenses:
        return {"state": "UNRESOLVED", "reason": "LICENSE_MISSING", "licenses": []}
    records = []
    for node in licenses:
        hrefs = [value for key, value in node.attrib.items() if local(key) == "href"]
        url = hrefs[0].strip() if len(hrefs) == 1 else None
        raw_text = node_text(node, remove_bibliography_xrefs=False)
        category = license_class_from_url(url) if url else "UNKNOWN"
        records.append({"raw_license_text": raw_text, "raw_license_url": url,
                        "normalized_license_class": category,
                        "classification_provenance": "article-meta/permissions/license/@xlink:href"})
    categories = {record["normalized_license_class"] for record in records}
    if len(categories) != 1 or any(not record["raw_license_text"] or not record["raw_license_url"] for record in records):
        return {"state": "UNRESOLVED", "reason": "LICENSE_CONFLICT_OR_INCOMPLETE", "licenses": records}
    category = next(iter(categories))
    raw_text = " ".join(record["raw_license_text"] for record in records).casefold()
    if category in {"CC0", "CC_BY", "CC_BY_SA"} and re.search(r"\b(?:non[- ]?commercial|no[- ]?derivatives|by[- ]?nc|by[- ]?nd)\b", raw_text):
        return {"state": "UNRESOLVED", "reason": "LICENSE_URL_TEXT_CONFLICT", "licenses": records}
    if category == "EXPLICIT_NONWHITELIST_CC":
        return {"state": "INELIGIBLE", "reason": "LICENSE_OUTSIDE_LOCAL_WHITELIST", "licenses": records}
    if category == "UNKNOWN":
        return {"state": "UNRESOLVED", "reason": "LICENSE_CLASS_UNKNOWN", "licenses": records}
    return {"state": "ELIGIBLE", "reason": "WHITELISTED_ARTICLE_LICENSE", "licenses": records}


def construction_oa_state(pmcid: str | None, subset_result: bool | None,
                          jats_xml: bytes | None) -> dict:
    if not pmcid or not re.fullmatch(r"PMC[1-9][0-9]*", pmcid):
        return {"state": "CONSTRUCTION_OA_UNRESOLVED", "reason": "PMCID_UNRESOLVED"}
    if subset_result is False:
        return {"state": "CONSTRUCTION_OA_INELIGIBLE", "reason": "NOT_IN_PMC_OA_SUBSET"}
    if subset_result is None:
        return {"state": "CONSTRUCTION_OA_UNRESOLVED", "reason": "OA_SUBSET_CHECK_UNRESOLVED"}
    if not jats_xml:
        return {"state": "CONSTRUCTION_OA_UNRESOLVED", "reason": "JATS_ARTIFACT_UNAVAILABLE"}
    try:
        root = ET.fromstring(jats_xml)
    except ET.ParseError:
        return {"state": "CONSTRUCTION_OA_UNRESOLVED", "reason": "JATS_XML_INVALID"}
    if local(root.tag) != "article":
        return {"state": "CONSTRUCTION_OA_UNRESOLVED", "reason": "JATS_ARTICLE_ROOT_MISSING"}
    license_result = extract_license(root)
    return {"state": f"CONSTRUCTION_OA_{license_result['state']}",
            "reason": license_result["reason"], "license": license_result}


def body_headings(root: ET.Element) -> list[dict]:
    body = next((node for node in root.iter() if local(node.tag) == "body"), None)
    if body is None:
        return []
    result: list[dict] = []
    def walk(parent: ET.Element, path: tuple[int, ...]) -> None:
        for ordinal, sec in enumerate(children(parent, "sec"), 1):
            current = path + (ordinal,)
            heading_node = first_child(sec, "title")
            heading = normalize_heading(node_text(heading_node)) if heading_node is not None else ""
            result.append({"section_path": list(current), "normalized_heading": heading})
            walk(sec, current)
    walk(body, ())
    return result


def source_type_state(publication_types: list[str] | None, jats_xml: bytes | None) -> dict:
    if not publication_types:
        return {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "PUBLICATION_TYPES_MISSING"}
    types = set(publication_types)
    if types & EXCLUDED_PUBLICATION_TYPES:
        return {"state": "SOURCE_TYPE_INELIGIBLE", "reason": "EXCLUDED_PUBLICATION_TYPE",
                "matched_types": sorted(types & EXCLUDED_PUBLICATION_TYPES)}
    if types - LOCAL_PUBLICATION_TYPES:
        return {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "UNRECOGNIZED_PUBLICATION_TYPE",
                "unknown_types": sorted(types - LOCAL_PUBLICATION_TYPES)}
    if not types & ACCEPTED_PUBLICATION_TYPES:
        return {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "POSITIVE_PUBLICATION_TYPE_ABSENT"}
    if not jats_xml:
        return {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "JATS_ARTIFACT_UNAVAILABLE"}
    try:
        root = ET.fromstring(jats_xml)
    except ET.ParseError:
        return {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "JATS_XML_INVALID"}
    article_type = root.attrib.get("article-type", "").casefold()
    if article_type in {"review-article", "editorial", "letter", "case-report", "correction", "retraction"}:
        return {"state": "SOURCE_TYPE_INELIGIBLE", "reason": "NONPRIMARY_JATS_ARTICLE_TYPE"}
    headings = body_headings(root)
    methods = [item for item in headings if item["normalized_heading"] in METHODS_HEADINGS]
    results = [item for item in headings if item["normalized_heading"] in RESULTS_HEADINGS]
    if not methods or not results:
        return {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "METHODS_OR_RESULTS_STRUCTURE_MISSING",
                "methods_paths": [x["section_path"] for x in methods],
                "results_paths": [x["section_path"] for x in results]}
    return {"state": "SOURCE_TYPE_ELIGIBLE", "reason": "POSITIVE_TYPE_AND_JATS_STRUCTURE",
            "methods_paths": [x["section_path"] for x in methods],
            "results_paths": [x["section_path"] for x in results]}


def build_construction_document(jats_xml: bytes, opaque_source_token: str) -> dict:
    """Use JATS body/abstract only; keep identities and back matter out of visible JSON."""
    if not re.fullmatch(r"src_[0-9a-f]{64}", opaque_source_token):
        raise ValueError("opaque source token has wrong shape")
    root = ET.fromstring(jats_xml)
    if local(root.tag) != "article":
        raise ValueError("JATS article root required")
    article_meta = next((node for node in root.iter() if local(node.tag) == "article-meta"), None)
    abstract_node = next((node for node in article_meta.iter() if local(node.tag) == "abstract"), None) if article_meta is not None else None
    abstract = node_text(abstract_node)[:10000] if abstract_node is not None else ""
    body = next((node for node in root.iter() if local(node.tag) == "body"), None)
    if body is None:
        raise ValueError("JATS body missing")
    raw_paragraphs: list[dict] = []
    def walk(parent: ET.Element, path: tuple[int, ...], heading_path: tuple[str, ...]) -> None:
        paragraph_ordinal = 0
        section_ordinal = 0
        for child in parent:
            name = local(child.tag)
            if name == "sec":
                section_ordinal += 1
                heading_node = first_child(child, "title")
                heading = normalize_heading(node_text(heading_node)) if heading_node is not None else ""
                if heading in OTHER_EXCLUDED_HEADINGS or child.attrib.get("sec-type", "").casefold() in {
                    "supplementary-material", "references", "acknowledgments", "funding"
                }:
                    continue
                walk(child, path + (section_ordinal,), heading_path + (heading,))
            elif name == "p":
                text = node_text(child)
                if text:
                    paragraph_ordinal += 1
                    raw_paragraphs.append({"section_path": list(path), "section_headings": list(heading_path),
                                           "kind": "paragraph", "ordinal": paragraph_ordinal, "text": text})
            elif name in {"fig", "table-wrap"}:
                caption = first_child(child, "caption")
                if caption is not None:
                    text = node_text(caption)
                    if text:
                        paragraph_ordinal += 1
                        raw_paragraphs.append({"section_path": list(path), "section_headings": list(heading_path),
                                               "kind": "figure_caption" if name == "fig" else "table_caption",
                                               "ordinal": paragraph_ordinal, "text": text})
    walk(body, (), ())
    segments: list[str] = []
    paragraphs: list[dict] = []
    position = 0
    for item in raw_paragraphs:
        if position >= 60000:
            break
        separator = "\n\n" if segments else ""
        if position + len(separator) >= 60000:
            break
        position += len(separator)
        allowed = 60000 - position
        text = item["text"][:allowed]
        if not text:
            break
        start = position
        end = start + len(text)
        anchor = "spanv1_" + digest([SPAN_VERSION, opaque_source_token,
                                      item["section_path"], item["ordinal"], sha_text(text)])
        paragraphs.append({**item, "text": text, "start_offset": start, "end_offset": end,
                           "span_id": anchor})
        segments.append(separator + text)
        position = end
    body_text = "".join(segments)
    if not body_text:
        raise ValueError("construction body empty")
    if re.search(r"\bPMC[0-9]+\b|\b10\.[0-9]{4,9}/\S+", body_text + " " + abstract, re.I):
        raise ValueError("source identifier in model-visible construction evidence")
    return {"schema_version": SCHEMA_VERSION, "abstract_text": abstract,
            "body_text": body_text, "paragraphs": paragraphs,
            "article_title_visible": False, "bibliography_visible": False,
            "normalization": "Unicode NFKC; whitespace collapsed within paragraphs; two LF between paragraphs"}


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_candidate_span(document: dict, source_field: str, start: int, end: int,
                           exact_text: str) -> str:
    if source_field != "body" or not isinstance(start, int) or not isinstance(end, int):
        raise ValueError("candidate must use a BODY evidence span")
    body = document["body_text"]
    if not (0 <= start < end <= len(body)) or body[start:end] != exact_text:
        raise ValueError("candidate evidence does not match canonical body")
    containing = [item for item in document["paragraphs"] if item["start_offset"] <= start and end <= item["end_offset"]]
    if len(containing) != 1:
        raise ValueError("candidate span must fit one canonical paragraph")
    return containing[0]["span_id"]
