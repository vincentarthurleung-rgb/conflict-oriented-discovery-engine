#!/usr/bin/env python3
"""Deterministic, offline post-Builder V2 checks for prospective alpha3.18B.

This module never calls a provider. It composes previously frozen schemas and
helpers; scientific quality remains exclusively with the later quality stage.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any

try:
    from scripts import search_plan_v24_alpha317c_reconcile_builder_offline as builder
    from scripts import search_plan_v24_alpha317d_preregister_quality_v2_offline as quality
    from scripts import search_plan_v24_alpha317a_safety_audits as leakage
    from scripts import search_plan_v24_alpha318a1_source_contracts as source
except ModuleNotFoundError:
    import search_plan_v24_alpha317c_reconcile_builder_offline as builder
    import search_plan_v24_alpha317d_preregister_quality_v2_offline as quality
    import search_plan_v24_alpha317a_safety_audits as leakage
    import search_plan_v24_alpha318a1_source_contracts as source


SCIENTIFIC_FIELDS = (
    "actor_or_intervention", "action", "relation_direction", "response_or_endpoint",
    "biological_unit", "species", "intrinsic_conditioning", "intrinsic_therapy_context",
    "intrinsic_disease_or_genotype_context",
)


def private_identity_from_jats(jats_xml: bytes, pmid: str, pmcid: str,
                               doi: str | None) -> dict[str, str]:
    """Extract front-matter identities for private pre-call audits only."""
    root = ET.fromstring(jats_xml)
    if source.local(root.tag) != "article":
        raise ValueError("PRIVATE_IDENTITY_JATS_ROOT_INVALID")
    fronts = source.children(root, "front")
    articles = [x for front in fronts for x in source.children(front, "article-meta")]
    journals = [x for front in fronts for x in source.children(front, "journal-meta")]
    titles = [source.node_text(x) for article in articles
              for group in source.children(article, "title-group")
              for x in source.children(group, "article-title")]
    journal_titles = [source.node_text(x) for journal in journals
                      for group in source.children(journal, "journal-title-group")
                      for x in source.children(group, "journal-title")]
    author_names = [source.node_text(x) for article in articles
                    for group in source.children(article, "contrib-group")
                    for contrib in source.children(group, "contrib")
                    if contrib.get("contrib-type") == "author"
                    for x in source.children(contrib, "name")]
    author_surnames = [source.node_text(x) for article in articles
                       for group in source.children(article, "contrib-group")
                       for contrib in source.children(group, "contrib")
                       if contrib.get("contrib-type") == "author"
                       for name in source.children(contrib, "name")
                       for x in source.children(name, "surname")]
    if not titles or not journal_titles or not author_names or any(
        not value for value in titles + journal_titles + author_names):
        raise ValueError("PRIVATE_IDENTITY_FRONT_MATTER_INCOMPLETE")
    identity = {"pmid": pmid, "pmcid": pmcid, "doi": doi or ""}
    identity.update({f"title_{i}": value for i, value in enumerate(titles, 1)})
    identity.update({f"journal_{i}": value for i, value in enumerate(journal_titles, 1)})
    identity.update({f"author_{i}": value for i, value in enumerate(author_names, 1)})
    identity.update({f"author_surname_{i}": value for i, value in enumerate(author_surnames, 1) if value})
    return identity


def _validate_schema(value: Any, schema: dict[str, Any], path: str = "$._") -> None:
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    matching = (kind is None or
                ("object" in kinds and isinstance(value, dict)) or
                ("array" in kinds and isinstance(value, list)) or
                ("string" in kinds and isinstance(value, str)) or
                ("integer" in kinds and isinstance(value, int) and not isinstance(value, bool)) or
                ("null" in kinds and value is None))
    if not matching:
        raise ValueError("BUILDER_SCHEMA_TYPE:" + path)
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("BUILDER_SCHEMA_ENUM:" + path)
    if isinstance(value, dict):
        required = set(schema.get("required", []))
        properties = schema.get("properties", {})
        if not required.issubset(value):
            raise ValueError("BUILDER_SCHEMA_MISSING_REQUIRED:" + path)
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            raise ValueError("BUILDER_SCHEMA_ADDITIONAL_PROPERTY:" + path)
        for key, item in value.items():
            if key in properties:
                _validate_schema(item, properties[key], path + "." + key)
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            raise ValueError("BUILDER_SCHEMA_ARRAY_LENGTH:" + path)
        for index, item in enumerate(value):
            _validate_schema(item, schema["items"], f"{path}[{index}]")
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ValueError("BUILDER_SCHEMA_STRING_LENGTH:" + path)
    elif isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError("BUILDER_SCHEMA_MINIMUM:" + path)


def validate_builder_response(raw: bytes, expected_source_token: str,
                              frozen_schema: dict[str, Any]) -> dict[str, Any]:
    """Validate one completed inference; invalid output never triggers repair."""
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("BUILDER_RESPONSE_MALFORMED_JSON") from exc
    _validate_schema(parsed, frozen_schema)
    if parsed["source_record_token"] != expected_source_token:
        raise ValueError("BUILDER_RESPONSE_SOURCE_IDENTITY_MISMATCH")
    if len(parsed["candidates"]) > 3:
        raise ValueError("BUILDER_RESPONSE_CARDINALITY_EXCEEDED")
    return parsed


def evidence_sentence(body: str, start: int, end: int) -> str:
    """Use the containing .!?/newline segment; ambiguous crossing uses all body."""
    if not (0 <= start < end <= len(body)):
        raise ValueError("EVIDENCE_SENTENCE_OFFSETS_INVALID")
    if any(ch in ".!?\n" for ch in body[start:end]):
        return body
    left = max((i + 1 for i in range(start) if body[i] in ".!?\n"), default=0)
    right = next((i for i in range(end, len(body)) if body[i] in ".!?\n"), len(body))
    return body[left:right].strip() or body


def precheck_candidates(response: dict[str, Any], document: dict[str, Any],
                        private_title: str) -> dict[str, Any]:
    """Canonical ID/dedup, BODY existence, and frozen lexical leakage only."""
    token = response["source_record_token"]
    raw_candidates = response["candidates"]
    canonical_bytes_by_sha: dict[str, bytes] = {}
    for candidate in raw_candidates:
        raw = builder.canonical(candidate)
        digest = builder.sha(raw)
        if digest in canonical_bytes_by_sha and canonical_bytes_by_sha[digest] != raw:
            raise RuntimeError("BUILDER_CANDIDATE_HASH_COLLISION")
        canonical_bytes_by_sha[digest] = raw
    canonical = builder.canonicalize_candidates(token, raw_candidates)
    if len({item["candidate_id"] for item in canonical}) != len(canonical):
        raise RuntimeError("BUILDER_CANDIDATE_ID_COLLISION")
    records: list[dict[str, Any]] = []
    survivors: list[dict[str, Any]] = []
    for item in canonical:
        candidate = item["candidate"]
        span = candidate["construction_evidence_span"]
        record = {"candidate_id": item["candidate_id"],
            "candidate_payload_sha256": item["candidate_payload_sha256"],
            "original_array_positions_private": item["original_array_positions"],
            "builder_schema_state": "BUILDER_SCHEMA_VALID",
            "deterministic_id_state": "DETERMINISTIC_ID_ASSIGNED",
            "exact_dedup_state": "UNIQUE" if len(item["original_array_positions"]) == 1 else "DUPLICATES_COLLAPSED"}
        try:
            anchor = source.resolve_candidate_span(document, span["source_field"],
                span["start_offset"], span["end_offset"], span["exact_text"])
        except ValueError as exc:
            record.update({"grounding_reference_state": "GROUNDING_REFERENCE_FAILED",
                "grounding_reason": str(exc), "leakage_gate_state": "NOT_RUN_AFTER_GROUNDING_FAILURE"})
            records.append(record)
            continue
        sentence = evidence_sentence(document["body_text"], span["start_offset"], span["end_offset"])
        failed = leakage.leakage_failed(candidate["neutral_proposition"], private_title, sentence)
        record.update({"grounding_reference_state": "GROUNDING_REFERENCE_VALID",
            "private_anchor_id": anchor,
            "leakage_gate_state": "LEXICAL_LEAKAGE_FAILED" if failed else "LEXICAL_LEAKAGE_PASSED"})
        records.append(record)
        if not failed:
            survivors.append(item)
    return {"raw_candidate_count": len(raw_candidates), "schema_valid_candidate_count": len(raw_candidates),
        "exact_duplicate_candidates_removed": len(raw_candidates) - len(canonical),
        "grounding_reference_failures": sum(row["grounding_reference_state"] == "GROUNDING_REFERENCE_FAILED" for row in records),
        "leakage_failures": sum(row["leakage_gate_state"] == "LEXICAL_LEAKAGE_FAILED" for row in records),
        "quality_adjudication_input_candidates": len(survivors),
        "candidate_records_private": records, "survivors_private": survivors}


def build_quality_payload(private_source_token: str, survivors: list[dict[str, Any]],
                          document: dict[str, Any], private_identity: dict[str, str]) -> dict[str, Any]:
    if not 1 <= len(survivors) <= 3:
        raise ValueError("QUALITY_GROUP_CARDINALITY")
    if survivors != sorted(survivors, key=lambda item: (
        item["candidate_payload_sha256"], item["candidate_id"])):
        raise ValueError("QUALITY_GROUP_CANDIDATE_ORDER_NOT_CANONICAL")
    packets = []
    for item in survivors:
        candidate = item["candidate"]
        span = candidate["construction_evidence_span"]
        # Re-validate the frozen BODY reference; no private anchor crosses to quality.
        source.resolve_candidate_span(document, span["source_field"],
            span["start_offset"], span["end_offset"], span["exact_text"])
        packet = {"candidate_id": item["candidate_id"],
            "scientific_fields": {key: candidate[key] for key in SCIENTIFIC_FIELDS},
            "neutral_proposition": candidate["neutral_proposition"],
            "evidence": quality.evidence_packet(document["body_text"],
                span["start_offset"], span["end_offset"], span["exact_text"])}
        packets.append(packet)
    payload = {"source_group_id": quality.source_group_id(private_source_token),
        "candidate_packets": packets}
    quality.audit_quality_payload(payload, {**private_identity, "private_source_token": private_source_token})
    return payload


def build_quality_request(payload: dict[str, Any], quality_schema: dict[str, Any],
                          system_prompt: str, user_template: str,
                          machine_output_appendix: str) -> dict[str, Any]:
    user = user_template.format(source_group_id=payload["source_group_id"],
        candidate_packets_json=json.dumps(payload["candidate_packets"], sort_keys=True,
            ensure_ascii=False, separators=(",", ":")),
        output_schema_json=json.dumps(quality_schema, sort_keys=True,
            ensure_ascii=False, separators=(",", ":")),
        machine_output_appendix=machine_output_appendix)
    return {"model": "deepseek-v4-pro", "thinking": {"type": "enabled"},
        "reasoning_effort": "high", "response_format": {"type": "json_object"},
        "stream": False,
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user}]}
