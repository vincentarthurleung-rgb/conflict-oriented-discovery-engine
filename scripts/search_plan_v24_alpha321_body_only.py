"""BODY-only projection of the unchanged historical normalization algorithm.

No ConstructionEvidenceDocument, abstract, source token, span ID or anchor is
generated. Paragraphs retain controller-side paths and exact text offsets only.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from scripts import search_plan_v24_alpha318a1_source_contracts as policy


def canonical_body(jats_xml: bytes) -> dict:
    root = ET.fromstring(jats_xml)
    if policy.local(root.tag) != "article":
        raise ValueError("JATS article root required")
    body = next((node for node in root.iter() if policy.local(node.tag) == "body"), None)
    if body is None:
        raise ValueError("JATS body missing")
    raw_paragraphs = []

    def walk(parent, path, headings):
        paragraph_ordinal = 0
        section_ordinal = 0
        for child in parent:
            name = policy.local(child.tag)
            if name == "sec":
                section_ordinal += 1
                title = policy.first_child(child, "title")
                heading = policy.normalize_heading(policy.node_text(title)) if title is not None else ""
                if heading in policy.OTHER_EXCLUDED_HEADINGS or child.attrib.get("sec-type", "").casefold() in {
                    "supplementary-material", "references", "acknowledgments", "funding"
                }:
                    continue
                walk(child, path + (section_ordinal,), headings + (heading,))
            elif name == "p":
                text = policy.node_text(child)
                if text:
                    paragraph_ordinal += 1
                    raw_paragraphs.append({"section_path": list(path), "section_headings": list(headings),
                                           "kind": "paragraph", "ordinal": paragraph_ordinal, "text": text})
            elif name in {"fig", "table-wrap"}:
                caption = policy.first_child(child, "caption")
                if caption is not None:
                    text = policy.node_text(caption)
                    if text:
                        paragraph_ordinal += 1
                        raw_paragraphs.append({"section_path": list(path), "section_headings": list(headings),
                            "kind": "figure_caption" if name == "fig" else "table_caption",
                            "ordinal": paragraph_ordinal, "text": text})

    walk(body, (), ())
    segments, paragraphs, position = [], [], 0
    for item in raw_paragraphs:
        if position >= 60000:
            break
        separator = "\n\n" if segments else ""
        if position + len(separator) >= 60000:
            break
        position += len(separator)
        text = item["text"][:60000 - position]
        if not text:
            break
        start, end = position, position + len(text)
        paragraphs.append({**item, "text": text, "start_offset": start, "end_offset": end})
        segments.append(separator + text)
        position = end
    body_text = "".join(segments)
    if not body_text:
        raise ValueError("construction body empty")
    return {"body_text": body_text, "paragraphs": paragraphs,
            "normalization": "Unicode NFKC; whitespace collapsed within paragraphs; two LF between paragraphs"}
