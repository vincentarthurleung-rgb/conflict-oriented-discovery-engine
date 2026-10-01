#!/usr/bin/env python3
"""Article-level, machine-readable JATS license extraction V2 (offline only)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlsplit

try:
    from scripts import search_plan_v24_alpha318a1_source_contracts as policy
except ModuleNotFoundError:
    import search_plan_v24_alpha318a1_source_contracts as policy


ALI_NS = "http://www.niso.org/schemas/ali/1.0/"
XLINK_NS = "http://www.w3.org/1999/xlink"
WHITELIST = frozenset({"CC0", "CC_BY", "CC_BY_SA"})
NONWHITELIST = frozenset({"by-nc", "by-nd", "by-nc-sa", "by-nc-nd"})
VERSIONS = frozenset({"2.0", "2.5", "3.0", "4.0"})


def children(parent: ET.Element, name: str) -> list[ET.Element]:
    return [node for node in parent if policy.local(node.tag) == name]


def normalize_uri(raw_uri: str) -> dict[str, Any]:
    """Normalize representation only; never infer from prose or follow links."""
    value = raw_uri.strip()
    try:
        parsed = urlsplit(value)
        if parsed.scheme.casefold() not in {"http", "https"} or parsed.username or parsed.password or (
            parsed.port is not None) or parsed.query or parsed.fragment or not parsed.netloc:
            return {"normalized_uri": None, "normalized_class": "UNKNOWN",
                    "recognized_cc_host": False, "reason": "URI_NOT_CANONICAL_CC_RESOURCE"}
    except ValueError:
        return {"normalized_uri": None, "normalized_class": "UNKNOWN",
                "recognized_cc_host": False, "reason": "URI_PARSE_INVALID"}
    host = (parsed.hostname or "").casefold()
    if host not in {"creativecommons.org", "www.creativecommons.org"}:
        return {"normalized_uri": None, "normalized_class": "UNKNOWN",
                "recognized_cc_host": False, "reason": "UNRECOGNIZED_MACHINE_URI_HOST"}
    path = parsed.path.rstrip("/").casefold()
    parts = path.split("/")
    normalized = "https://creativecommons.org" + path + "/"
    if len(parts) == 4 and parts[1:3] == ["publicdomain", "zero"] and parts[3] == "1.0":
        category = "CC0"
    elif len(parts) == 4 and parts[1] == "licenses" and parts[3] in VERSIONS:
        family = parts[2]
        category = {"by": "CC_BY", "by-sa": "CC_BY_SA"}.get(family)
        if category is None:
            category = "EXPLICIT_NONWHITELIST_CC" if family in NONWHITELIST else "UNKNOWN"
    else:
        category = "UNKNOWN"
    return {"normalized_uri": normalized, "normalized_class": category,
            "recognized_cc_host": True,
            "reason": "RECOGNIZED_CC_LICENSE_URI" if category != "UNKNOWN" else "UNCLASSIFIED_CC_RESOURCE"}


def _candidate(source_path: str, raw_uri: str, ordinal: int,
               start_date: str | None) -> dict[str, Any]:
    return {"source_path": source_path, "raw_uri": raw_uri,
            "license_element_ordinal": ordinal, "start_date": start_date,
            **normalize_uri(raw_uri)}


def extract_license_v2(jats_xml: bytes) -> dict[str, Any]:
    root = ET.fromstring(jats_xml)
    if policy.local(root.tag) != "article":
        raise ValueError("JATS_ARTICLE_ROOT_MISSING")
    fronts = children(root, "front")
    metadata = [node for front in fronts for node in children(front, "article-meta")]
    permissions = [node for article_meta in metadata for node in children(article_meta, "permissions")]
    licenses = [node for group in permissions for node in children(group, "license")]
    candidates: list[dict[str, Any]] = []
    license_provenance: list[dict[str, Any]] = []
    representation_paths: set[str] = set()
    for ordinal, license_node in enumerate(licenses, 1):
        raw_text = policy.node_text(license_node, remove_bibliography_xrefs=False)
        license_provenance.append({"license_element_ordinal": ordinal,
            "raw_license_text": raw_text, "license_attributes": dict(license_node.attrib)})
        # A: direct href on the article-level license element. The unqualified
        # form is retained because the frozen V1 extractor accepted local href.
        for attribute in (f"{{{XLINK_NS}}}href", "href"):
            if attribute in license_node.attrib:
                representation_paths.add("A")
                candidates.append(_candidate("article/front/article-meta/permissions/license/@" +
                    ("xlink:href" if attribute != "href" else "href"),
                    license_node.attrib[attribute], ordinal, None))
        # B: ALI namespace is checked exactly, not by local-name wildcard.
        for node in license_node:
            if node.tag == f"{{{ALI_NS}}}license_ref":
                representation_paths.add("B")
                candidates.append(_candidate(
                    "article/front/article-meta/permissions/license/ali:license_ref",
                    policy.node_text(node, remove_bibliography_xrefs=False), ordinal,
                    node.attrib.get("start_date")))
        # C: ext-link may nest under a direct license-p, but never outside it.
        for license_p in children(license_node, "license-p"):
            for node in license_p.iter():
                if policy.local(node.tag) != "ext-link":
                    continue
                attribute = f"{{{XLINK_NS}}}href"
                if attribute in node.attrib:
                    representation_paths.add("C")
                    candidates.append(_candidate(
                        "article/front/article-meta/permissions/license/license-p//ext-link/@xlink:href",
                        node.attrib[attribute], ordinal, None))
    classes = sorted({item["normalized_class"] for item in candidates})
    usable = [item for item in candidates if item["normalized_class"] != "UNKNOWN"]
    path_a = [item for item in candidates if item["source_path"].endswith(("/@xlink:href", "/@href")) and
              "/license/license-p/" not in item["source_path"]]
    path_c = [item for item in candidates if "/license/license-p/" in item["source_path"]]
    a_classes = {item["normalized_class"] for item in path_a}
    c_classes = {item["normalized_class"] for item in path_c}
    a_c_consistency = None if not path_a or not path_c else a_classes == c_classes
    if not candidates:
        state, reason, normalized_class = "UNRESOLVED", "LICENSE_MACHINE_URI_UNRESOLVED", None
    elif "UNKNOWN" in classes:
        state, reason, normalized_class = "UNRESOLVED", "LICENSE_MACHINE_URI_UNCLASSIFIED", None
    elif len(classes) != 1:
        state, reason, normalized_class = "UNRESOLVED", "LICENSE_MACHINE_URI_CONFLICT", None
    else:
        normalized_class = classes[0]
        if normalized_class == "EXPLICIT_NONWHITELIST_CC":
            state, reason = "INELIGIBLE", "LICENSE_OUTSIDE_LOCAL_WHITELIST"
        elif normalized_class in WHITELIST:
            state, reason = "ELIGIBLE", "WHITELISTED_ARTICLE_LICENSE"
        else:
            state, reason, normalized_class = "UNRESOLVED", "LICENSE_MACHINE_URI_UNCLASSIFIED", None
    if state == "ELIGIBLE":
        combined_text = " ".join(item["raw_license_text"] for item in license_provenance).casefold()
        if re.search(r"\b(?:non[- ]?commercial|no[- ]?derivatives|by[- ]?nc|by[- ]?nd)\b", combined_text):
            state, reason, normalized_class = "UNRESOLVED", "LICENSE_URL_TEXT_CONFLICT", None
    return {"schema_version": "ConstructionLicenseExtractionV2",
        "state": state, "reason": reason, "normalized_license_class": normalized_class,
        "normalized_unique_classes": classes,
        "candidate_count": len(candidates), "candidates": candidates,
        "license_element_count": len(licenses), "license_provenance": license_provenance,
        "representation_paths": sorted(representation_paths),
        "path_a_count": sum(item in path_a for item in candidates),
        "path_b_count": sum("/ali:license_ref" in item["source_path"] for item in candidates),
        "path_c_count": len(path_c),
        "path_a_c_class_consistent": a_c_consistency,
        "whitelist_unchanged": True, "article_level_scope_only": True,
        "plain_prose_promoted": False}


def construction_oa_v2(pmcid: str, subset: bool | None, jats_xml: bytes | None) -> dict[str, Any]:
    if not re.fullmatch(r"PMC[1-9][0-9]*", pmcid):
        return {"state": "CONSTRUCTION_OA_UNRESOLVED", "reason": "PMCID_UNRESOLVED"}
    if subset is False:
        return {"state": "CONSTRUCTION_OA_INELIGIBLE", "reason": "NOT_IN_PMC_OA_SUBSET"}
    if subset is None:
        return {"state": "CONSTRUCTION_OA_UNRESOLVED", "reason": "OA_SUBSET_CHECK_UNRESOLVED"}
    if jats_xml is None:
        return {"state": "CONSTRUCTION_OA_UNRESOLVED", "reason": "JATS_ARTIFACT_UNAVAILABLE"}
    try:
        license_result = extract_license_v2(jats_xml)
    except (ET.ParseError, ValueError):
        return {"state": "CONSTRUCTION_OA_UNRESOLVED", "reason": "JATS_XML_INVALID"}
    return {"state": "CONSTRUCTION_OA_" + license_result["state"],
            "reason": license_result["reason"], "license": license_result}
