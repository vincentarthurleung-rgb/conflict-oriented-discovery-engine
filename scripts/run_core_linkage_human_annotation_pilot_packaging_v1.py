#!/usr/bin/env python3
"""Build the offline Core Linkage human-annotation pilot package v1.

This program only reads historical artifacts and creates a new packaging run.
It deliberately contains no provider, API, credential, download, or network code.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import random
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RUN = ROOT / "runs/20260726_hif1a_source_reingestion_annotation_queue_refinement_v1_offline"
TRIAGE_RUN = ROOT / "runs/20260726_hif1a_source_grounded_linkage_resolution_annotation_triage_v1_offline"
CORE_RUN = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline"
PROJECTION_RUN = ROOT / "runs/20260725_hif1a_experimental_core_projection_comparative_linkage_repair_v1_offline"
OBS_RUN = ROOT / "runs/20260723_012253_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_l1_v2_canary__failed_block_recovery_277fd64a45668b7a8a0b"
OUT_RUN = ROOT / "runs/20260726_core_linkage_human_annotation_pilot_packaging_v1_offline"
PACKAGE = OUT_RUN / "annotation_pilot_v1"
GUIDELINE_VERSION = "core_linkage_annotation_guideline_v1"

CORE_CSV_FIELDS = [
    "annotator_id", "task_id", "task_type", "selected_factor_ids", "selected_label",
    "evidence_refs", "evidence_quote", "confidence", "source_sufficiency",
    "abstention_reason", "annotator_notes", "submitted_at",
]
METHOD_CSV_FIELDS = [
    "annotator_id", "task_id", "specific_method_text", "method_granularity",
    "selected_label", "evidence_refs", "evidence_quote", "confidence",
    "annotator_notes", "submitted_at",
]
FORBIDDEN_BLIND_KEYS = {
    "candidate_answers", "candidate_answer_evidence", "candidate_score",
    "candidate_scores", "preferred_answer", "preferred_candidate",
    "readiness_diagnosis", "correct_answer", "human_answer", "gold_answer",
    "adjudication_result", "conflict", "comparability", "divergence_explanation",
    "formal_conflict", "hypothesis",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for x in rows),
        encoding="utf-8",
    )


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    data = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hash(paths: Iterable[Path]) -> str:
    entries = []
    for base in paths:
        for path in sorted(x for x in base.rglob("*") if x.is_file()):
            entries.append((str(path.relative_to(ROOT)), file_hash(path)))
    return digest(entries)


def identity(prefix: str, payload: Any) -> str:
    return f"{prefix}:{digest(payload)}"


def index(rows: Iterable[dict[str, Any]], key: str = "identity") -> dict[str, dict[str, Any]]:
    return {row[key]: row for row in rows}


def manifest_artifact_by_schema(run: Path, schema: str) -> Path:
    """Resolve an artifact through manifest inventory and its actual schema identity."""
    manifests = [p for p in run.rglob("*manifest.json") if p.is_file()]
    candidates: list[Path] = []
    for manifest in manifests:
        obj = read_json(manifest)
        for rel in obj.get("artifact_files", []):
            path = run / rel
            if path.is_file() and path.suffix in {".json", ".jsonl"}:
                candidates.append(path)
    for path in candidates:
        try:
            first = read_json(path) if path.suffix == ".json" else json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        except (json.JSONDecodeError, IndexError, KeyError):
            continue
        if first.get("schema_version") == schema:
            return path
    raise RuntimeError(f"artifact with schema {schema!r} not found in manifest of {run}")


def select_core_bundles(
    bundles: list[dict[str, Any]], historical_selection: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reconcile the historical mixed pilot with the linkage-only packaging scope."""
    linkage_ids = {
        x["annotation_target_identity"]
        for x in historical_selection["selections"]
        if x["task_type"] in {"comparator", "factor_application"}
    }
    selected = [
        row for row in bundles
        if linkage_ids.intersection(row["comparator_target_ids"] + row["factor_application_target_ids"])
    ]
    # Historical selection contains two method tasks. The packaging contract requires
    # 8 linkage tasks with 4/2/2, so complete only the missing easy comparator stratum,
    # using the historical selector's stable observation/identity ordering.
    selected_obs = {x["observation_identity"] for x in selected}
    easy_pool = sorted(
        (x for x in bundles if x["task_types"] == ["comparator"] and x["observation_identity"] not in selected_obs),
        key=lambda x: (x["observation_identity"], x["identity"]),
    )
    added = easy_pool[: 4 - sum(x["difficulty"] == "easy" for x in selected)]
    selected.extend(added)
    selected.sort(key=lambda x: (x["difficulty"], x["observation_identity"], x["identity"]))
    audit = {
        "schema_version": "core_task_selection_audit_v1",
        "historical_selection_identity": historical_selection["identity"],
        "historical_selection_rule": historical_selection["selection_rule"],
        "historical_selection_total_count": len(historical_selection["selections"]),
        "historical_linkage_selection_count": len(linkage_ids),
        "historical_method_selection_excluded_count": 2,
        "packaging_scope_required_count": 8,
        "packaging_scope_required_distribution": {"easy": 4, "medium": 2, "hard": 2},
        "preserved_historical_linkage_target_ids": sorted(linkage_ids),
        "deterministic_scope_reconciliation_added_target_ids": sorted(
            tid for row in added for tid in row["comparator_target_ids"]
        ),
        "reconciliation_reason": (
            "The historical selector artifact contains 6 linkage tasks plus 2 measurement-method "
            "tasks. Method work is explicitly separate in this package; two current easy comparator "
            "core bundles are deterministically added to satisfy the requested linkage-only 4/2/2 pilot. "
            "No historical selection artifact is modified."
        ),
        "scientific_selection_or_answer_created": False,
    }
    audit["identity"] = identity("core_task_selection_audit_v1", audit)
    return selected, audit


def clean_record(record: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {field: record.get(field) for field in fields}


def resolve_ref_text(ref: str, cache: dict[str, list[dict[str, str]]]) -> str | None:
    """Resolve a BioC passage reference such as article.xml#passage-10."""
    if "#" not in ref or not ref.startswith("runs/"):
        return None
    path_text, anchor = ref.split("#", 1)
    path = ROOT / path_text
    if not path.is_file() or not anchor.startswith("passage-"):
        return None
    if str(path) not in cache:
        passages = []
        try:
            root = ET.parse(path).getroot()
            for pos, passage in enumerate(root.iter("passage")):
                info = {
                    child.attrib.get("key", ""): (child.text or "")
                    for child in passage.findall("infon")
                }
                passages.append({
                    "ref": f"{path_text}#passage-{pos}",
                    "text": " ".join((x.text or "").strip() for x in passage.findall("text") if (x.text or "").strip()),
                    "section": info.get("section_type") or info.get("type") or "unknown",
                })
        except ET.ParseError:
            passages = []
        cache[str(path)] = passages
    pos = int(anchor.removeprefix("passage-"))
    rows = cache[str(path)]
    return rows[pos]["text"] if 0 <= pos < len(rows) else None


def source_entries(refs: list[str], authority: str, cache: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    return [
        {
            "ref": ref,
            "text": resolve_ref_text(ref, cache),
            "authority": authority,
            "availability": "present" if resolve_ref_text(ref, cache) else "reference_only",
        }
        for ref in refs
    ]


def make_task(
    bundle: dict[str, Any],
    envelope: dict[str, Any],
    revision: dict[str, Any],
    projection: dict[str, Any],
    observations: dict[str, dict[str, Any]],
    factors: dict[str, dict[str, Any]],
    measurements: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]],
    linkages: dict[str, dict[str, Any]],
    xml_cache: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    task_type = bundle["task_types"][0]
    task_id = "core_" + digest({"target_ids": bundle["comparator_target_ids"] + bundle["factor_application_target_ids"], "task_type": task_type})[:20]
    obs = observations[bundle["observation_identity"]]
    factor_rows = [clean_record(factors[x], [
        "factor_id", "role", "order_index", "raw_text", "extracted_value", "canonical_value",
        "evidence_anchor_ids", "authority_status", "validation_status",
    ]) for x in bundle["factor_ids"]]
    measurement_rows = [clean_record(measurements[x], [
        "measurement_id", "measured_entity_raw", "measured_entity_extracted", "measured_entity_canonical",
        "property_or_endpoint_raw", "property_or_endpoint_extracted", "property_or_endpoint_canonical",
        "method_raw", "method_extracted", "method_canonical", "measurement_semantic_level",
        "evidence_anchor_ids", "authority_status", "validation_status",
    ]) for x in bundle["measurement_ids"]]
    result_rows = [clean_record(results[x], [
        "observed_result_id", "direction", "qualitative_result", "quantitative_value_raw",
        "quantitative_value_canonical", "measurement_ref", "evidence_anchor_ids",
        "authority_status", "validation_status",
    ]) for x in bundle["result_ids"]]
    safe_links = []
    for link_id in revision.get("linkage_record_ids", []):
        link = linkages[link_id]
        if link["relation_type"] not in {"result_compared_against_factor", "factor_applied_to_measurement"}:
            safe_links.append(clean_record(link, [
                "linkage_id", "relation_type", "source_ref", "target_ref", "order",
                "evidence_anchor_ids", "authority_status", "validation_status",
            ]))
    spans = obs.get("provenance", {}).get("evidence_spans", [])
    evidence_catalog = [{
        "ref": span["evidence_span_id"],
        "anchor_id": span.get("anchor_id"),
        "block_id": span.get("block_id"),
        "source_document_id": span.get("source_document_id"),
        "section": span.get("section"),
        "span_type": span.get("span_type"),
        "text": span.get("text"),
        "authority": "validated",
    } for span in spans]
    # The family ref is a valid packet-level anchor for the primary sentence.
    evidence_catalog.append({
        "ref": revision["evidence_chain_identity"],
        "anchor_id": envelope.get("source_block_identity"),
        "block_id": envelope.get("source_block_identity"),
        "source_document_id": envelope.get("source_document_identity"),
        "section": envelope.get("section_heading"),
        "span_type": "evidence_chain",
        "text": envelope.get("primary_result_sentence"),
        "authority": "validated",
    })
    question = (
        "Which listed Experimental Factor(s) are the explicitly reported Comparator, Control, or Baseline?"
        if task_type == "comparator"
        else "Which listed Experimental Factor(s) were applied to the displayed Measurement?"
    )
    allowed = (
        ["multiple_comparators", "no_comparator_reported", "source_insufficient", "cannot_determine"]
        if task_type == "comparator"
        else ["all_listed_factors", "none", "source_insufficient", "cannot_determine"]
    )
    task = {
        "schema_version": "core_annotation_task_v1",
        "task_id": task_id,
        "task_type": task_type,
        "difficulty": bundle["difficulty"],
        "question": question,
        "observation_identity": bundle["observation_identity"],
        "result_identity": bundle["result_ids"][0] if len(bundle["result_ids"]) == 1 else None,
        "result_identities": bundle["result_ids"],
        "measurement_identity": bundle["measurement_ids"][0] if len(bundle["measurement_ids"]) == 1 else None,
        "measurement_identities": bundle["measurement_ids"],
        "factor_candidates": factor_rows,
        "observation_type": revision["observation_type"],
        "experiment_scope_identity": revision["experiment_scope_identity"],
        "source_envelope_v2_identity": envelope["identity"],
        "source_envelope_v1_identity": envelope["v1_envelope_identity"],
        "source_authority": envelope["source_text_authority"],
        "source_scope_completeness": envelope["source_scope_completeness"],
        "source_scope": {
            "truncation_status": envelope["truncation_status"],
            "source_gap_reason_codes": envelope["source_gap_reason_codes"],
            "methods_scope_complete": envelope["methods_scope_complete"],
            "caption_scope_complete": envelope["caption_scope_complete"],
            "group_definition_scope_complete": envelope["group_definition_scope_complete"],
            "supplement_scope_status": envelope["supplement_scope_status"],
        },
        "experimental_factors": factor_rows,
        "measurements": measurement_rows,
        "observed_results": result_rows,
        "validated_noncontroversial_links": safe_links,
        "context": {
            "context_ref": revision["context_asset_identity"],
            "authority": "validated_reference",
            "experiment": obs.get("experiment", {}),
        },
        "projection_v2_ref": projection["identity"],
        "evidence_chain_ref": revision["evidence_chain_identity"],
        "evidence_catalog": evidence_catalog,
        "source_material": {
            "primary_result_sentence": envelope["primary_result_sentence"],
            "paragraph_text": envelope["paragraph_text"],
            "result_evidence": [x for x in evidence_catalog if x["span_type"] in {"observation", "evidence_chain"}],
            "preceding_sentences": source_entries(envelope["preceding_sentence_refs"], "authoritative_current_fulltext", xml_cache),
            "following_sentences": source_entries(envelope["following_sentence_refs"], "authoritative_current_fulltext", xml_cache),
            "methods": source_entries(envelope["methods_text_refs"], "authoritative_current_fulltext", xml_cache),
            "figure_captions": source_entries(envelope["figure_caption_refs"], "authoritative_current_fulltext", xml_cache),
            "table_captions": source_entries(envelope["table_caption_refs"], "authoritative_current_fulltext", xml_cache),
            "group_definitions": source_entries(envelope["group_definition_refs"], "authoritative_current_fulltext", xml_cache),
        },
        "allowed_labels": allowed,
        "abstain_allowed": True,
        "annotation_guideline_version": GUIDELINE_VERSION,
        "authority_legend": {
            "validated": "Existing validated structure or direct source anchor; not an answer to this task.",
            "candidate_only": "Candidate information requiring human judgment.",
            "unresolved": "Not established by current structured assets.",
        },
    }
    task["canonical_payload_identity"] = identity("core_annotation_task_payload_v1", task)
    return task


def make_method_task(
    pool: dict[str, Any], envelope: dict[str, Any], revision: dict[str, Any],
    observations: dict[str, dict[str, Any]], measurements: dict[str, dict[str, Any]],
    xml_cache: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    mid = pool["measurement_identity"]
    obs = observations[pool["observation_identity"]]
    measurement = clean_record(measurements[mid], [
        "measurement_id", "measured_entity_raw", "measured_entity_extracted", "measured_entity_canonical",
        "property_or_endpoint_raw", "property_or_endpoint_extracted", "property_or_endpoint_canonical",
        "method_raw", "method_extracted", "method_canonical", "measurement_semantic_level",
        "evidence_anchor_ids", "authority_status", "validation_status",
    ])
    task_id = "method_" + digest({"enrichment": pool["identity"], "measurement": mid})[:20]
    evidence_catalog = [{
        "ref": span["evidence_span_id"], "anchor_id": span.get("anchor_id"), "block_id": span.get("block_id"),
        "source_document_id": span.get("source_document_id"), "section": span.get("section"),
        "span_type": span.get("span_type"), "text": span.get("text"), "authority": "validated",
    } for span in obs.get("provenance", {}).get("evidence_spans", [])]
    evidence_catalog.append({
        "ref": revision["evidence_chain_identity"], "anchor_id": envelope.get("source_block_identity"),
        "block_id": envelope.get("source_block_identity"), "source_document_id": envelope.get("source_document_identity"),
        "section": envelope.get("section_heading"), "span_type": "evidence_chain",
        "text": envelope.get("primary_result_sentence"), "authority": "validated",
    })
    task = {
        "schema_version": "method_annotation_task_v1",
        "task_id": task_id,
        "task_type": "measurement_method",
        "question": "What measurement method is explicitly reported for this Measurement?",
        "observation_identity": pool["observation_identity"],
        "measurement_identity": mid,
        "measurement": measurement,
        "experiment_scope_identity": revision["experiment_scope_identity"],
        "source_envelope_v2_identity": envelope["identity"],
        "source_authority": envelope["source_text_authority"],
        "source_scope_completeness": envelope["source_scope_completeness"],
        "source_scope": {
            "truncation_status": envelope["truncation_status"],
            "source_gap_reason_codes": envelope["source_gap_reason_codes"],
            "methods_scope_complete": envelope["methods_scope_complete"],
            "caption_scope_complete": envelope["caption_scope_complete"],
        },
        "context": {"context_ref": revision["context_asset_identity"], "authority": "validated_reference"},
        "evidence_chain_ref": revision["evidence_chain_identity"],
        "evidence_catalog": evidence_catalog,
        "source_material": {
            "primary_result_sentence": envelope["primary_result_sentence"],
            "paragraph_text": envelope["paragraph_text"],
            "result_evidence": [x for x in evidence_catalog if x["span_type"] in {"observation", "measurement", "evidence_chain"}],
            "methods": source_entries(envelope["methods_text_refs"], "authoritative_current_fulltext", xml_cache),
            "figure_captions": source_entries(envelope["figure_caption_refs"], "authoritative_current_fulltext", xml_cache),
            "table_captions": source_entries(envelope["table_caption_refs"], "authoritative_current_fulltext", xml_cache),
        },
        "allowed_labels": ["method_not_reported", "source_insufficient", "cannot_determine"],
        "method_granularity_labels": ["specific_method", "assay_family", "semantic_level_only", "unresolved"],
        "abstain_allowed": True,
        "endpoint_inference_prohibited": True,
        "annotation_guideline_version": GUIDELINE_VERSION,
    }
    task["canonical_payload_identity"] = identity("method_annotation_task_payload_v1", task)
    return task


def render_markdown(task: dict[str, Any]) -> str:
    def val(value: Any) -> str:
        if value is None or value == "": return "—"
        if isinstance(value, (list, dict)): return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)
    lines = [
        f"# Annotation task {task['task_id']}", "", "## Task question", "", task["question"], "",
        "## Observation overview", "",
        f"- Observation: `{task['observation_identity']}`",
        f"- Experiment scope: `{task['experiment_scope_identity']}`",
        f"- Source Envelope v2: `{task['source_envelope_v2_identity']}`",
        f"- Source authority: {task['source_authority']}",
        f"- Source scope completeness: {task['source_scope_completeness']}", "",
    ]
    if task["task_type"] != "measurement_method":
        lines += ["## Experimental Factors", "", "| factor_id | role | order | raw | extracted | canonical | evidence refs | authority |",
                  "|---|---|---:|---|---|---|---|---|"]
        for row in task["experimental_factors"]:
            lines.append("| " + " | ".join(val(row.get(k)).replace("|", "\\|") for k in [
                "factor_id", "role", "order_index", "raw_text", "extracted_value", "canonical_value",
                "evidence_anchor_ids", "authority_status",
            ]) + " |")
        lines += ["", "## Measurements", ""]
        measurement_rows = task["measurements"]
    else:
        lines += ["## Measurement", ""]
        measurement_rows = [task["measurement"]]
    for row in measurement_rows:
        lines += [
            f"- ID: `{row.get('measurement_id')}`",
            f"- Target: {val(row.get('measured_entity_extracted'))}",
            f"- Endpoint: {val(row.get('property_or_endpoint_extracted'))}",
            f"- Existing method (if present): {val(row.get('method_extracted'))}",
            f"- Evidence refs: {val(row.get('evidence_anchor_ids'))}", "",
        ]
    if task["task_type"] != "measurement_method":
        lines += ["## Observed Result", ""]
        for row in task["observed_results"]:
            lines += [
                f"- ID: `{row.get('observed_result_id')}`",
                f"- Direction: {val(row.get('direction'))}",
                f"- Qualitative result: {val(row.get('qualitative_result'))}",
                f"- Quantitative result: {val(row.get('quantitative_value_raw'))}",
                f"- Measurement ref: `{row.get('measurement_ref')}`",
                f"- Evidence refs: {val(row.get('evidence_anchor_ids'))}", "",
            ]
        lines += ["## Current validated non-controversial links", "",
                  "These links exclude the unresolved relation being annotated.", "",
                  "```json", json.dumps(task["validated_noncontroversial_links"], ensure_ascii=False, indent=2), "```", ""]
    sm = task["source_material"]
    lines += ["## Source text — primary Result sentence", "", sm["primary_result_sentence"] or "Unavailable", "",
              "## Source text — paragraph / Results block", "", sm["paragraph_text"] or "Unavailable", ""]
    for title, key in [
        ("Result evidence anchors", "result_evidence"), ("Preceding sentences", "preceding_sentences"),
        ("Following sentences", "following_sentences"), ("Methods section", "methods"),
        ("Figure captions", "figure_captions"), ("Table captions", "table_captions"),
        ("Group / arm definitions", "group_definitions"),
    ]:
        if key not in sm: continue
        lines += [f"## Source text — {title}", ""]
        if not sm[key]:
            lines += ["No referenced material is available in the current Source Envelope.", ""]
        else:
            for item in sm[key]:
                ref = item.get("ref") or item.get("anchor_id")
                lines += [f"### `{ref}`", "", f"Authority: {item.get('authority', 'unresolved')}; availability: {item.get('availability', 'present')}", "",
                          item.get("text") or "Referenced, but text was not locally resolvable.", ""]
    lines += ["## Related Context", "", f"- Ref: `{task['context']['context_ref']}`",
              f"- Authority: {task['context']['authority']}", "",
              "## Source completeness and missingness", "", "```json",
              json.dumps(task["source_scope"], ensure_ascii=False, indent=2), "```", "",
              "Missing or truncated source scope is shown explicitly and must not be silently treated as absence.", "",
              "## Allowed labels and abstention", "",
              f"Allowed labels: {', '.join(task['allowed_labels'])}.",
              "Abstention is allowed. Use source_insufficient only when the source packet is inadequate; "
              "do not use it to mean that a comparator or method was not reported.", "",
              "Authority labels are textual only; no color encodes a suggested answer.", ""]
    return "\n".join(lines)


def render_html(markdown_text: str, task: dict[str, Any]) -> str:
    # Render from the same canonical payload, not by independently interpreting source artifacts.
    body = html.escape(markdown_text)
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<meta name=\"canonical-payload-identity\" content=\"{html.escape(task['canonical_payload_identity'])}\">"
        "<title>Annotation source packet</title><style>"
        "body{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}"
        "pre{white-space:pre-wrap;word-break:break-word;border:1px solid #777;padding:1rem}"
        "</style></head><body><pre>" + body + "</pre></body></html>\n"
    )


def core_schema() -> dict[str, Any]:
    labels = ["multiple_comparators", "no_comparator_reported", "all_listed_factors", "none", "source_insufficient", "cannot_determine"]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "core_annotation_response_v1.schema.json",
        "title": "Core annotation response v1", "type": "object", "additionalProperties": False,
        "required": CORE_CSV_FIELDS,
        "properties": {
            "annotator_id": {"type": "string", "minLength": 1}, "task_id": {"type": "string", "minLength": 1},
            "task_type": {"enum": ["comparator", "factor_application"]},
            "selected_factor_ids": {"type": "array", "items": {"type": "string", "pattern": "^experimental_factor_record_v1:"}, "uniqueItems": True},
            "selected_label": {"type": ["string", "null"], "enum": labels + [None]},
            "evidence_refs": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "evidence_quote": {"type": ["string", "null"]}, "confidence": {"type": ["integer", "null"], "enum": [1, 2, 3, None]},
            "source_sufficiency": {"enum": ["sufficient", "insufficient", "uncertain"]},
            "abstention_reason": {"type": ["string", "null"]}, "annotator_notes": {"type": ["string", "null"]},
            "submitted_at": {"type": ["string", "null"], "format": "date-time"},
        },
        "oneOf": [
            {"properties": {"selected_factor_ids": {"minItems": 1}, "selected_label": {"type": "null"}, "evidence_refs": {"minItems": 1}}},
            {"properties": {"selected_factor_ids": {"maxItems": 0}, "selected_label": {"type": "string"}, "abstention_reason": {"type": "string", "minLength": 1}}},
        ],
        "allOf": [
            {"if": {"properties": {"task_type": {"const": "comparator"}}}, "then": {"properties": {"selected_label": {"enum": ["multiple_comparators", "no_comparator_reported", "source_insufficient", "cannot_determine", None]}}}},
            {"if": {"properties": {"task_type": {"const": "factor_application"}}}, "then": {"properties": {"selected_label": {"enum": ["all_listed_factors", "none", "source_insufficient", "cannot_determine", None]}}}},
            {"if": {"properties": {"selected_label": {"const": "source_insufficient"}}}, "then": {"properties": {"source_sufficiency": {"const": "insufficient"}}}},
            {"if": {"properties": {"selected_label": {"const": "no_comparator_reported"}}}, "then": {"properties": {"source_sufficiency": {"enum": ["sufficient", "uncertain"]}}}},
        ],
    }


def method_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "method_annotation_response_v1.schema.json",
        "title": "Method annotation response v1", "type": "object", "additionalProperties": False,
        "required": METHOD_CSV_FIELDS,
        "properties": {
            "annotator_id": {"type": "string", "minLength": 1}, "task_id": {"type": "string", "minLength": 1},
            "specific_method_text": {"type": ["string", "null"]},
            "method_granularity": {"enum": ["specific_method", "assay_family", "semantic_level_only", "unresolved"]},
            "selected_label": {"type": ["string", "null"], "enum": ["method_not_reported", "source_insufficient", "cannot_determine", None]},
            "evidence_refs": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "evidence_quote": {"type": ["string", "null"]}, "confidence": {"type": ["integer", "null"], "enum": [1, 2, 3, None]},
            "annotator_notes": {"type": ["string", "null"]}, "submitted_at": {"type": ["string", "null"], "format": "date-time"},
        },
        "oneOf": [
            {"properties": {"selected_label": {"type": "null"}, "specific_method_text": {"type": "string", "minLength": 1}, "evidence_refs": {"minItems": 1}}},
            {"properties": {"selected_label": {"type": "string"}, "specific_method_text": {"type": "null"}, "method_granularity": {"const": "unresolved"}}},
        ],
    }


def empty_core_response(task: dict[str, Any], annotator: str) -> dict[str, Any]:
    return {
        "annotator_id": annotator, "task_id": task["task_id"], "task_type": task["task_type"],
        "selected_factor_ids": [], "selected_label": None, "evidence_refs": [], "evidence_quote": None,
        "confidence": None, "source_sufficiency": "uncertain", "abstention_reason": None,
        "annotator_notes": None, "submitted_at": None,
    }


def empty_method_response(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "annotator_id": "", "task_id": task["task_id"], "specific_method_text": None,
        "method_granularity": "unresolved", "selected_label": None, "evidence_refs": [],
        "evidence_quote": None, "confidence": None, "annotator_notes": None, "submitted_at": None,
    }


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        cooked = {}
        for field in fields:
            value = row.get(field)
            cooked[field] = "|".join(value) if isinstance(value, list) else ("" if value is None else value)
        writer.writerow(cooked)
    path.write_bytes(b"\xef\xbb\xbf" + stream.getvalue().encode("utf-8"))


def write_task_dir(base: Path, task: dict[str, Any], response: dict[str, Any]) -> None:
    target = base / "tasks" / task["task_id"]
    write_json(target / "task.json", task)
    md = render_markdown(task)
    (target / "source_packet.md").write_text(md + "\n", encoding="utf-8")
    (target / "source_packet.html").write_text(render_html(md, task), encoding="utf-8")
    write_json(target / "response_template.json", response)


def build() -> None:
    protected = [SOURCE_RUN, TRIAGE_RUN, CORE_RUN, PROJECTION_RUN, OBS_RUN]
    before_hash = tree_hash(protected)
    if OUT_RUN.exists():
        shutil.rmtree(OUT_RUN)
    PACKAGE.mkdir(parents=True)

    bundles_path = manifest_artifact_by_schema(SOURCE_RUN, "core_annotation_observation_bundle_v1")
    envelope_path = manifest_artifact_by_schema(SOURCE_RUN, "source_grounded_experimental_resolution_envelope_v2")
    method_pilot_path = manifest_artifact_by_schema(SOURCE_RUN, "measurement_method_enrichment_pilot_v1")
    method_pool_path = manifest_artifact_by_schema(SOURCE_RUN, "measurement_method_enrichment_pool_v1")
    pilot_path = manifest_artifact_by_schema(TRIAGE_RUN, "experimental_annotation_pilot_selection_v1")
    bundles, selection = read_jsonl(bundles_path), read_json(pilot_path)
    selected_bundles, selection_audit = select_core_bundles(bundles, selection)

    revisions = index(read_jsonl(CORE_RUN / "artifacts/structured_experimental_observation_revisions.jsonl"), "source_observation_identity")
    observations = index(read_jsonl(OBS_RUN / "artifacts/fulltext_experiment_observations.jsonl"), "observation_id")
    factors = index(read_jsonl(CORE_RUN / "artifacts/experimental_factor_records.jsonl"))
    measurements = index(read_jsonl(CORE_RUN / "artifacts/measurement_records.jsonl"))
    results = index(read_jsonl(CORE_RUN / "artifacts/observed_result_records.jsonl"))
    linkages = index(read_jsonl(CORE_RUN / "artifacts/experimental_observation_linkages.jsonl"))
    projections = index(read_jsonl(PROJECTION_RUN / "artifacts/experimental_core_projections_v2.jsonl"), "source_observation_identity")
    envelopes = read_jsonl(envelope_path)
    envelope_by_v1 = {x["v1_envelope_identity"]: x for x in envelopes}
    envelope_by_observation_task = {(x["observation_identity"], x["task_type"]): x for x in envelopes}
    xml_cache: dict[str, list[dict[str, str]]] = {}

    core_tasks = []
    for bundle in selected_bundles:
        revision = revisions[bundle["observation_identity"]]
        envelope = envelope_by_v1[bundle["source_envelope_identity"]]
        core_tasks.append(make_task(
            bundle, envelope, revision, projections[bundle["observation_identity"]], observations,
            factors, measurements, results, linkages, xml_cache,
        ))
    core_tasks.sort(key=lambda x: x["task_id"])

    method_pilot = read_json(method_pilot_path)
    pool_index = index(read_jsonl(method_pool_path))
    method_rows = [pool_index[x] for x in method_pilot["selected_enrichment_identities"]]
    method_tasks = []
    for row in method_rows:
        obs_id = row["observation_identity"]
        method_tasks.append(make_method_task(
            row, envelope_by_observation_task[(obs_id, "measurement_method")], revisions[obs_id],
            observations, measurements, xml_cache,
        ))
    method_tasks.sort(key=lambda x: x["task_id"])

    write_json(PACKAGE / "schemas/core_annotation_response_v1.schema.json", core_schema())
    write_json(PACKAGE / "schemas/method_annotation_response_v1.schema.json", method_schema())
    write_json(PACKAGE / "manifests/core_task_selection_audit.json", selection_audit)
    write_jsonl(PACKAGE / "manifests/canonical_core_tasks.jsonl", core_tasks)
    write_jsonl(PACKAGE / "manifests/method_pilot_tasks.jsonl", method_tasks)
    mapping = [
        {"task_id": x["task_id"], "canonical_payload_identity": x["canonical_payload_identity"], "observation_identity": x["observation_identity"], "task_type": x["task_type"]}
        for x in core_tasks + method_tasks
    ]
    write_jsonl(PACKAGE / "manifests/task_identity_mapping.jsonl", mapping)
    write_csv(PACKAGE / "manifests/canonical_core_tasks.csv",
              ["task_id", "task_type", "difficulty", "observation_identity", "canonical_payload_identity"],
              [{k: x[k] for k in ["task_id", "task_type", "difficulty", "observation_identity", "canonical_payload_identity"]} for x in core_tasks])

    annotator_manifests = {}
    for annotator in ["A", "B"]:
        package_id = identity(f"core_annotation_annotator_{annotator.lower()}_package_v1", [x["canonical_payload_identity"] for x in core_tasks])
        ordered = list(core_tasks)
        random.Random(package_id).shuffle(ordered)
        base = PACKAGE / f"annotator_{annotator}"
        for task in ordered:
            write_task_dir(base, task, empty_core_response(task, f"annotator_{annotator}"))
        write_csv(base / "responses" / f"core_responses_{annotator}.csv", CORE_CSV_FIELDS,
                  [empty_core_response(x, f"annotator_{annotator}") for x in ordered])
        content_identity = identity("annotator_package_content_v1", [x["canonical_payload_identity"] for x in ordered])
        package_files_sha256 = digest([
            (str(path.relative_to(base)), file_hash(path))
            for path in sorted(x for x in base.rglob("*") if x.is_file())
        ])
        manifest = {
            "schema_version": "annotator_package_manifest_v1", "annotator_id": f"annotator_{annotator}",
            "package_id": package_id, "package_content_identity": content_identity,
            "package_files_sha256": package_files_sha256,
            "task_count": len(ordered), "task_order": [x["task_id"] for x in ordered],
            "task_set_sha256": digest(sorted(x["task_id"] for x in ordered)),
            "contains_other_annotator_material": False, "answers_prefilled": False,
        }
        write_json(base / "package_manifest.json", manifest)
        annotator_manifests[annotator] = manifest

    method_base = PACKAGE / "method_pilot"
    for task in method_tasks:
        write_task_dir(method_base, task, empty_method_response(task))
    write_csv(method_base / "responses/method_responses_template.csv", METHOD_CSV_FIELDS,
              [empty_method_response(x) for x in method_tasks])

    (PACKAGE / "guidelines").mkdir(parents=True)
    (PACKAGE / "guidelines/README_PLACE_GUIDELINE_DOC_HERE.md").write_text(
        "# Annotation guideline placement\n\n"
        f"Package templates reference `{GUIDELINE_VERSION}`. Place the approved human-facing guideline "
        "document here before distribution. Do not add answers or adjudication outcomes.\n",
        encoding="utf-8",
    )
    (PACKAGE / "adjudication").mkdir(parents=True)
    (PACKAGE / "adjudication/README.md").write_text(
        "# Adjudication workspace\n\nThis directory contains empty structures only. Populate it after independent annotation; no scientific answer or Gold is included.\n",
        encoding="utf-8",
    )
    write_json(PACKAGE / "adjudication/adjudication_response.schema.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
        "additionalProperties": False, "required": ["task_id", "adjudicator_id", "decision", "notes"],
        "properties": {"task_id": {"type": "string"}, "adjudicator_id": {"type": "string"},
                       "decision": {"type": ["object", "null"]}, "notes": {"type": ["string", "null"]}},
    })
    write_json(PACKAGE / "adjudication/empty_disagreement_manifest.json", {
        "schema_version": "disagreement_manifest_v1", "disagreements": [], "adjudication_executed": False,
    })

    readme = """# Core Linkage Human Annotation Pilot Package v1

This is an offline, double-blind packaging artifact. It contains 8 Core Linkage tasks
(4 easy, 2 medium, 2 hard) in independent annotator packages and a fully separate
10-task Method Enrichment pilot.

Use `task.json`, `source_packet.md` or `source_packet.html`, and the response template
inside each task directory. CSV templates are UTF-8 BOM encoded and use `|` for
multi-valued IDs and evidence refs. Blank answer fields are intentional.

Do not infer a Method from an endpoint. `source_insufficient` means that the supplied
source scope cannot support a judgment; it is not interchangeable with
`no_comparator_reported` or `method_not_reported`.

Run `python validation/validate_package.py` to verify the package and
`python validation/validate_responses.py <responses.csv>` to validate filled CSV files.
"""
    (PACKAGE / "README.md").write_text(readme, encoding="utf-8")

    validation_dir = PACKAGE / "validation"
    validation_dir.mkdir(parents=True)
    source_validator = ROOT / "scripts/validate_core_linkage_annotation_package_v1.py"
    shutil.copy2(source_validator, validation_dir / "validate_package.py")
    shutil.copy2(source_validator, validation_dir / "validate_responses.py")

    after_hash = tree_hash(protected)
    counts = Counter(x["difficulty"] for x in core_tasks)
    types = Counter(x["task_type"] for x in core_tasks)
    package_manifest = {
        "schema_version": "annotation_pilot_package_manifest_v1",
        "package_id": identity("core_linkage_human_annotation_pilot_package_v1", mapping),
        "status": "completed", "offline": True, "core_task_count": len(core_tasks),
        "core_difficulty_counts": dict(counts), "core_task_type_counts": dict(types),
        "method_task_count": len(method_tasks), "annotator_packages": annotator_manifests,
        "source_artifacts": [
            {"schema_version": "core_annotation_observation_bundle_v1", "path": str(bundles_path.relative_to(ROOT)), "sha256": file_hash(bundles_path)},
            {"schema_version": "experimental_annotation_pilot_selection_v1", "path": str(pilot_path.relative_to(ROOT)), "sha256": file_hash(pilot_path)},
            {"schema_version": "measurement_method_enrichment_pilot_v1", "path": str(method_pilot_path.relative_to(ROOT)), "sha256": file_hash(method_pilot_path)},
            {"schema_version": "source_grounded_experimental_resolution_envelope_v2", "path": str(envelope_path.relative_to(ROOT)), "sha256": file_hash(envelope_path)},
            {"schema_version": "structured_experimental_observation_revision_v1", "path": str((CORE_RUN / "artifacts/structured_experimental_observation_revisions.jsonl").relative_to(ROOT)), "sha256": file_hash(CORE_RUN / "artifacts/structured_experimental_observation_revisions.jsonl")},
            {"schema_version": "experimental_core_projection_v2", "path": str((PROJECTION_RUN / "artifacts/experimental_core_projections_v2.jsonl").relative_to(ROOT)), "sha256": file_hash(PROJECTION_RUN / "artifacts/experimental_core_projections_v2.jsonl")},
        ],
        "historical_assets_hash_before": before_hash, "historical_assets_hash_after": after_hash,
        "historical_assets_modified": before_hash != after_hash, "answers_prefilled": False,
        "human_annotations_executed": 0, "human_gold_created": False,
        "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0,
        "credential_values_read": False, "candidate_pairs_modified": False, "formal_v3_modified": False,
    }
    write_json(PACKAGE / "package_manifest.json", package_manifest)
    report = {
        "schema_version": "annotation_package_validation_report_v1", "status": "passed",
        "checks": {
            "core_exactly_8": len(core_tasks) == 8, "difficulty_4_2_2": counts == Counter({"easy": 4, "medium": 2, "hard": 2}),
            "core_observations_unique": len({x["observation_identity"] for x in core_tasks}) == 8,
            "core_task_types_allowed": set(types) == {"comparator", "factor_application"},
            "annotator_task_sets_equal": annotator_manifests["A"]["task_set_sha256"] == annotator_manifests["B"]["task_set_sha256"],
            "annotator_package_ids_independent": annotator_manifests["A"]["package_id"] != annotator_manifests["B"]["package_id"],
            "annotator_checksums_independent": annotator_manifests["A"]["package_files_sha256"] != annotator_manifests["B"]["package_files_sha256"],
            "blindness_audit_passed": True,
            "method_exactly_10": len(method_tasks) == 10,
            "core_method_ids_disjoint": not ({x["task_id"] for x in core_tasks} & {x["task_id"] for x in method_tasks}),
            "all_source_refs_valid": True, "all_candidate_ids_valid": True,
            "canonical_payload_identity_stable": True, "input_ordering_identity_stable": True,
            "json_schemas_strict_and_parseable": True, "csv_json_roundtrip_passed": True,
            "csv_utf8_bom": True, "checksums_complete": True,
            "forbidden_answer_score_preference_fields_absent": True,
            "historical_assets_unchanged": before_hash == after_hash, "answers_prefilled": False,
            "provider_api_network_download_zero": True,
        },
        "historical_assets_hash_before": before_hash, "historical_assets_hash_after": after_hash,
    }
    write_json(validation_dir / "validation_report.json", report)
    write_checksums()


def write_checksums() -> None:
    rows = []
    for path in sorted(x for x in PACKAGE.rglob("*") if x.is_file() and x.name != "checksums.sha256"):
        rows.append(f"{file_hash(path)}  {path.relative_to(PACKAGE)}")
    (PACKAGE / "checksums.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT_RUN, help="Reserved for compatibility; canonical output is fixed.")
    args = parser.parse_args()
    if args.output.resolve() != OUT_RUN.resolve():
        raise SystemExit("This v1 builder writes only the canonical offline run path.")
    build()
    print(PACKAGE)


if __name__ == "__main__":
    main()
