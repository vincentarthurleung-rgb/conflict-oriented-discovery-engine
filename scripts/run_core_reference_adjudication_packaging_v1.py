#!/usr/bin/env python3
"""Package every current Core Linkage target for blind reference adjudication.

This is a deterministic, offline packaging program.  It reads immutable historical
artifacts, never imports provider code, and never infers or edits a scientific link.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TRIAGE = ROOT / "runs/20260726_hif1a_source_grounded_linkage_resolution_annotation_triage_v1_offline/artifacts"
REFINEMENT = ROOT / "runs/20260726_hif1a_source_reingestion_annotation_queue_refinement_v1_offline/artifacts"
CORE = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"
PROJECTION = ROOT / "runs/20260725_hif1a_experimental_core_projection_comparative_linkage_repair_v1_offline/artifacts"
OBSERVATIONS = ROOT / (
    "runs/20260723_012253_hif1a_hypoxia_cancer_response_discovery_v1_"
    "fulltext_l1_v2_canary__failed_block_recovery_277fd64a45668b7a8a0b/"
    "artifacts/fulltext_experiment_observations.jsonl"
)
PILOT_IDS = ROOT / (
    "runs/20260726_core_linkage_human_annotation_pilot_packaging_v1_offline/"
    "annotation_pilot_v1/manifests/task_identity_mapping.jsonl"
)
OUT_RUN = ROOT / "runs/20260816_core_reference_adjudication_packaging_v1_offline"
PACK = OUT_RUN / "reference_adjudication_pack_v1"
BLIND = PACK / "blind_reference_pack"
ADMIN = PACK / "admin_system_metadata_pack"

COMPARATOR_QUESTION = """For this specific Observed Result, which listed Experimental Factor is the reference arm against which the result is reported?

Select only the control, baseline, or reference condition.

Do not select the experimental arm merely because it participates in the comparison."""
FACTOR_QUESTION = """Which listed Experimental Factor(s) are explicitly applicable to this specific Measurement?

Select only Factor(s) whose application to the Measurement is supported by the supplied source evidence.

Do not assume that every Factor in the Observation applies to every Measurement."""
ALLOWED = {
    "comparator": [
        "valid_candidate_selected", "multiple_reference_arms", "candidate_set_incomplete",
        "no_reference_arm_reported", "source_insufficient", "cannot_determine",
    ],
    "factor_application": [
        "valid_candidate_selected", "multiple_applicable_factors", "candidate_set_incomplete",
        "no_factor_application_reported", "source_insufficient", "cannot_determine",
    ],
}
BLIND_FORBIDDEN_KEYS = {
    "role", "factor_role", "control_arm_raw", "comparison_arm_raw", "baseline_arm_raw",
    "experimental_design_raw", "design_normalization_status", "design_normalization_rule_id",
    "design_review_reasons", "difficulty", "selection_reason", "annotation_priority",
    "readiness_status", "machine_reuse_status", "remediation_status", "candidate_authority",
    "candidate_score", "diagnostic_score", "preferred_candidate", "system_prediction",
    "system_selected_factor", "existing_comparator_prediction", "gold_candidate_status",
    "annotator_A", "annotator_B", "selected_label", "annotator_notes", "submitted_at",
    "agreement", "adjudication",
}
TASK_ANSWER_KEYS = {"selected_factor_ids", "expected_reference_arm_raw", "evidence_quote"}
IDENTITY_FIELDS = {
    "blind_payload_identity", "canonical_payload_identity", "identity_sha256",
    "recomputed_sha256", "identity_match",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: Any) -> str:
    data = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(*args: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=not binary)
    return result.stdout


def indexed(path: Path, key: str = "identity") -> dict[str, dict[str, Any]]:
    return {row[key]: row for row in read_jsonl(path)}


def payload_hash(task: dict[str, Any]) -> str:
    return sha256({key: value for key, value in task.items() if key not in IDENTITY_FIELDS})


def attach_identity(task: dict[str, Any]) -> dict[str, Any]:
    value = payload_hash(task)
    task["blind_payload_identity"] = f"blind_reference_task_payload_v1:{value}"
    task["canonical_payload_identity"] = task["blind_payload_identity"]
    task["identity_sha256"] = value
    task["recomputed_sha256"] = payload_hash(task)
    task["identity_match"] = task["identity_sha256"] == task["recomputed_sha256"]
    return task


def source_entry(ref: str, xml_cache: dict[Path, list[dict[str, str]]]) -> dict[str, Any]:
    path_text, marker = (ref.split("#", 1) + [""])[:2]
    path = ROOT / path_text
    text = None
    if path.is_file() and marker.startswith("passage-"):
        if path not in xml_cache:
            passages: list[dict[str, str]] = []
            try:
                root = ET.parse(path).getroot()
                for passage in root.iter("passage"):
                    info = {x.attrib.get("key", ""): (x.text or "") for x in passage.findall("infon")}
                    passages.append({
                        "text": " ".join((x.text or "").strip() for x in passage.findall("text") if (x.text or "").strip()),
                        "section": info.get("section_type") or info.get("type") or "unknown",
                    })
            except ET.ParseError:
                passages = []
            xml_cache[path] = passages
        try:
            position = int(marker.removeprefix("passage-"))
            text = xml_cache[path][position]["text"]
        except (ValueError, IndexError):
            text = None
    return {
        "ref": ref,
        "text": text if text else "not_available",
        "source_authority": "authoritative_current_fulltext",
        "availability": "present" if text else "not_available",
    }


def source_entries(refs: list[str], xml_cache: dict[Path, list[dict[str, str]]]) -> list[dict[str, Any]]:
    if not refs:
        return [{
            "ref": None, "text": "not_available", "source_authority": "not_available",
            "availability": "not_available",
        }]
    return [source_entry(ref, xml_cache) for ref in refs]


def source_scope(envelope: dict[str, Any], material: dict[str, Any]) -> dict[str, bool]:
    return {
        "methods_available": any(x["availability"] == "present" for x in material["methods"]),
        "results_available": bool(envelope.get("primary_result_sentence") or envelope.get("paragraph_text")),
        "figure_caption_available": any(x["availability"] == "present" for x in material["figure_captions"]),
        "table_caption_available": any(x["availability"] == "present" for x in material["table_captions"]),
        "group_definition_available": any(x["availability"] == "present" for x in material["group_definitions"]),
        "supplement_available": envelope.get("supplement_scope_status") == "present",
        "truncation_detected": envelope.get("truncation_status") not in {None, "not_detected"},
    }


def clean_factor(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in (
        "factor_id", "raw_text", "extracted_value", "canonical_value", "order_index", "evidence_anchor_ids"
    )}


def clean_measurement(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in (
        "measurement_id", "measured_entity_raw", "measured_entity_extracted", "measured_entity_canonical",
        "property_or_endpoint_raw", "property_or_endpoint_extracted", "property_or_endpoint_canonical",
        "method_raw", "method_extracted", "method_canonical", "measurement_semantic_level", "evidence_anchor_ids",
    )}


def clean_result(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in (
        "observed_result_id", "direction", "qualitative_result", "quantitative_value_raw",
        "quantitative_value_canonical", "measurement_ref", "evidence_anchor_ids",
        "statistical_statement", "uncertainty_text", "significance_status",
    )}


def build_evidence_catalog(observation: dict[str, Any], envelope: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for span in observation.get("provenance", {}).get("evidence_spans", []):
        rows.append({
            "ref": span["evidence_span_id"], "anchor_id": span.get("anchor_id"),
            "block_id": span.get("block_id"), "source_document_id": span.get("source_document_id"),
            "section": span.get("section"), "text": span.get("text"),
            "source_authority": "current_fulltext_evidence_span",
        })
    for ref in envelope.get("evidence_chain_refs", []):
        rows.append({
            "ref": ref, "anchor_id": envelope.get("source_block_identity"),
            "block_id": envelope.get("source_block_identity"),
            "source_document_id": envelope.get("source_document_identity"),
            "section": envelope.get("section_heading"), "text": envelope.get("primary_result_sentence"),
            "source_authority": envelope.get("source_text_authority"),
        })
    unique = {row["ref"]: row for row in rows}
    return [unique[key] for key in sorted(unique)]


def stable_task_id(target: dict[str, Any], pilot_ids: dict[tuple[str, str], str]) -> str:
    key = (target["observation_identity"], target["task_type"])
    if key in pilot_ids:
        return pilot_ids[key]
    value = sha256({"target_ids": [target["annotation_target_id"]], "task_type": target["task_type"]})
    return "core_" + value[:20]


def make_blind_task(
    target: dict[str, Any], envelope: dict[str, Any], observation: dict[str, Any],
    factors: dict[str, dict[str, Any]], measurements: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]], pilot_ids: dict[tuple[str, str], str],
    xml_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    material = {
        "primary_result_sentence": envelope.get("primary_result_sentence") or "not_available",
        "result_paragraph": envelope.get("paragraph_text") or "not_available",
        "preceding_sentences": source_entries(envelope.get("preceding_sentence_refs", []), xml_cache),
        "following_sentences": source_entries(envelope.get("following_sentence_refs", []), xml_cache),
        "methods": source_entries(envelope.get("methods_text_refs", []), xml_cache),
        "figure_captions": source_entries(envelope.get("figure_caption_refs", []), xml_cache),
        "table_captions": source_entries(envelope.get("table_caption_refs", []), xml_cache),
        "group_definitions": source_entries(envelope.get("group_definition_refs", []), xml_cache),
    }
    refs = sorted({x["ref"] for value in material.values() if isinstance(value, list) for x in value if x["ref"]})
    task = {
        "task_id": stable_task_id(target, pilot_ids),
        "task_type": target["task_type"],
        "observation_identity": target["observation_identity"],
        "experiment_scope_identity": target["experiment_scope_identity"],
        "question": COMPARATOR_QUESTION if target["task_type"] == "comparator" else FACTOR_QUESTION,
        "factor_candidates": [clean_factor(factors[value]) for value in target["factor_candidate_ids"]],
        "measurement": clean_measurement(measurements[target["measurement_identity"]]),
        "observed_result": clean_result(results[target["result_identity"]]),
        "source_scope": source_scope(envelope, material),
        "source_document_id": envelope["source_document_identity"],
        "source_authority": envelope["source_text_authority"],
        "source_material_refs": refs,
        "source_material": material,
        "evidence_catalog": build_evidence_catalog(observation, envelope),
        "allowed_statuses": ALLOWED[target["task_type"]],
        "schema_version": "blind_reference_task_payload_v1",
    }
    return attach_identity(task)


def markdown_value(value: Any) -> str:
    if value is None or value == "":
        return "not_available"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def material_section(title: str, value: Any) -> list[str]:
    lines = [f"## {title}", ""]
    if isinstance(value, list):
        if not value:
            return lines + ["not_available", ""]
        for entry in value:
            lines += [f"- Ref: `{entry['ref']}`", f"  - Authority: {entry['source_authority']}",
                      f"  - Availability: {entry['availability']}", f"  - Text: {entry['text']}"]
        return lines + [""]
    return lines + [markdown_value(value), ""]


def render_markdown(task: dict[str, Any]) -> str:
    lines = [
        "# Reference Adjudication Task", "", "## Task", "", task["question"], "",
        f"Allowed statuses: {', '.join(task['allowed_statuses'])}", "", "## Observation", "",
        f"- Task ID: `{task['task_id']}`", f"- Task type: `{task['task_type']}`",
        f"- Observation: `{task['observation_identity']}`",
        f"- Experiment scope: `{task['experiment_scope_identity']}`",
        f"- Source document: `{task['source_document_id']}`", f"- Source authority: {task['source_authority']}", "",
        "## Factor Candidates", "",
        "| candidate | factor_id | raw | extracted | canonical | order | evidence refs |",
        "|---|---|---|---|---|---:|---|",
    ]
    for position, row in enumerate(task["factor_candidates"], start=1):
        cells = [f"candidate {position}", row["factor_id"], row["raw_text"], row["extracted_value"],
                 row["canonical_value"], row["order_index"], row["evidence_anchor_ids"]]
        lines.append("| " + " | ".join(markdown_value(x).replace("|", "\\|") for x in cells) + " |")
    measurement, result = task["measurement"], task["observed_result"]
    lines += ["", "## Measurement", "", "```json", json.dumps(measurement, ensure_ascii=False, indent=2, sort_keys=True),
              "```", "", "## Observed Result", "", "```json",
              json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), "```", ""]
    material = task["source_material"]
    lines += material_section("Primary Result Sentence", material["primary_result_sentence"])
    lines += material_section("Result Paragraph", material["result_paragraph"])
    lines += material_section("Preceding Sentences", material["preceding_sentences"])
    lines += material_section("Following Sentences", material["following_sentences"])
    lines += material_section("Methods", material["methods"])
    lines += material_section("Figure Captions", material["figure_captions"])
    lines += material_section("Table Captions", material["table_captions"])
    lines += material_section("Group / Arm Definitions", material["group_definitions"])
    lines += ["## Evidence Catalog", "", "```json",
              json.dumps(task["evidence_catalog"], ensure_ascii=False, indent=2, sort_keys=True), "```", "",
              "## Source Completeness", "", "```json",
              json.dumps(task["source_scope"], ensure_ascii=False, indent=2, sort_keys=True), "```", "",
              "## Canonical Payload", "", f"- canonical_payload_identity: `{task['canonical_payload_identity']}`",
              f"- identity_sha256: `{task['identity_sha256']}`",
              f"- recomputed_sha256: `{task['recomputed_sha256']}`", f"- identity_match: `{str(task['identity_match']).lower()}`", ""]
    return "\n".join(lines)


def response_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "reference_adjudication_response_v1.schema.json",
        "title": "source_grounded_reference_adjudication_v1", "type": "object",
        "additionalProperties": False,
        "required": ["task_id", "task_type", "task_validity", "selected_factor_ids", "expected_reference_arm_raw",
                     "evidence_refs", "evidence_quote", "source_sufficiency", "upstream_error_type", "confidence",
                     "adjudicator_notes"],
        "properties": {
            "task_id": {"type": "string", "minLength": 1},
            "task_type": {"enum": ["comparator", "factor_application"]},
            "task_validity": {"enum": ["valid_task", "candidate_set_incomplete", "candidate_set_wrong",
                "source_packet_inadequate", "observation_structure_wrong", "task_semantics_wrong", "cannot_determine"]},
            "selected_factor_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "expected_reference_arm_raw": {"type": ["string", "null"]},
            "evidence_refs": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "evidence_quote": {"type": ["string", "null"]},
            "source_sufficiency": {"enum": ["sufficient", "insufficient", "cannot_determine"]},
            "upstream_error_type": {"enum": ["none", "experimental_factor_missing", "experimental_factor_wrong",
                "experimental_factor_role_wrong", "experimental_arm_missing", "reference_arm_missing",
                "group_arm_representation_error", "measurement_wrong", "result_wrong", "observation_atomization_error",
                "observation_scope_error", "source_packet_scope_error", "candidate_generation_error", "other", None]},
            "confidence": {"enum": ["high", "medium", "low"]},
            "adjudicator_notes": {"type": ["string", "null"]},
        },
    }


def walk_keys(value: Any, prefix: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            yield path, key
            yield from walk_keys(child, path)
    elif isinstance(value, list):
        for position, child in enumerate(value):
            yield from walk_keys(child, f"{prefix}[{position}]")


def make_admin_task(
    blind: dict[str, Any], target: dict[str, Any], observation: dict[str, Any],
    factor_records: dict[str, dict[str, Any]], revision: dict[str, Any], projection: dict[str, Any],
    linkages: dict[str, dict[str, Any]], readiness: list[dict[str, Any]], remediation: list[dict[str, Any]],
    pilot_payload_id: str | None,
) -> dict[str, Any]:
    records = [factor_records[value] for value in target["factor_candidate_ids"]]
    experiment = observation.get("experiment", {})
    return {
        "schema_version": "admin_system_metadata_task_v1", "task_id": blind["task_id"],
        "task_type": blind["task_type"], "observation_identity": blind["observation_identity"],
        "historical_factor_records": records,
        "historical_roles": [{"factor_id": row["factor_id"], "role": row.get("role"),
                              "control_or_comparator_status": row.get("control_or_comparator_status")} for row in records],
        "control_arm_raw": experiment.get("control_arm_raw"),
        "comparison_arm_raw": experiment.get("comparison_arm_raw"),
        "baseline_arm_raw": experiment.get("baseline_arm_raw"),
        "experimental_design_raw": experiment.get("experimental_design_raw"),
        "comparison_semantics": observation.get("observation", {}).get("comparison_raw"),
        "existing_linkage_state": [linkages[value] for value in revision.get("linkage_record_ids", [])],
        "readiness_state": [row for row in readiness if row.get("observation_identity") == blind["observation_identity"]],
        "remediation_state": [row for row in remediation if row.get("observation_identity") == blind["observation_identity"]],
        "candidate_generation_provenance": target.get("provenance"),
        "candidate_authority": target.get("candidate_answers_authoritative"),
        "historical_annotation_target": target,
        "source_envelope_identity": target["source_resolution_envelope_identity"],
        "projection_v2_identity": projection["identity"],
        "historical_task_payload_identity": pilot_payload_id,
        "blind_payload_identity": blind["blind_payload_identity"],
    }


def validate(
    tasks: list[dict[str, Any]], admin_tasks: list[dict[str, Any]], factors: dict[str, dict[str, Any]],
    measurements: dict[str, dict[str, Any]], results: dict[str, dict[str, Any]], observations: dict[str, dict[str, Any]],
    targets_by_task_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    leaks = []
    for path in sorted(BLIND.rglob("*")):
        if not path.is_file() or path.suffix not in {".json", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            obj = json.loads(text)
            for key_path, key in walk_keys(obj):
                if key in BLIND_FORBIDDEN_KEYS or (path.name == "task.json" and key in TASK_ANSWER_KEYS):
                    leaks.append({"path": str(path.relative_to(PACK)), "match": key, "key_path": key_path})
        markdown_forbidden = (
            BLIND_FORBIDDEN_KEYS - {"role", "adjudication"}
            if path.suffix == ".md" else set()
        )
        tokens = set(markdown_forbidden) | {
            '"role": "control"', '"role": "comparator"', '"role": "baseline"',
            "result_compared_against_factor", "factor_applied_to_measurement",
        }
        for token in sorted(tokens):
            if token in text:
                leaks.append({"path": str(path.relative_to(PACK)), "match": token})
    blindness = {
        "schema_version": "blindness_validation_v1", "blind_pack_status": "passed" if not leaks else "failed",
        "files_scanned": sum(1 for x in BLIND.rglob("*") if x.is_file() and x.suffix in {".json", ".md"}),
        "leak_count": len(leaks), "leaks": leaks,
        "previous_human_answers_included": False, "relation_leakage_validator": "passed" if not leaks else "failed",
    }

    evidence_failures, integrity_failures, order_failures = [], [], []
    for task in tasks:
        candidate_ids = [x["factor_id"] for x in task["factor_candidates"]]
        if len(candidate_ids) != len(set(candidate_ids)) or any(x not in factors for x in candidate_ids):
            integrity_failures.append({"task_id": task["task_id"], "check": "factor_ids"})
        if task["measurement"]["measurement_id"] not in measurements:
            integrity_failures.append({"task_id": task["task_id"], "check": "measurement_id"})
        if task["observed_result"]["observed_result_id"] not in results:
            integrity_failures.append({"task_id": task["task_id"], "check": "result_id"})
        if task["observation_identity"] not in observations:
            integrity_failures.append({"task_id": task["task_id"], "check": "observation_id"})
        expected_order = targets_by_task_id[task["task_id"]]["factor_candidate_ids"]
        if candidate_ids != expected_order:
            order_failures.append(task["task_id"])
        catalog = {x["ref"] for x in task["evidence_catalog"]}
        required_evidence = {ref for row in task["factor_candidates"] for ref in row["evidence_anchor_ids"]}
        required_evidence.update(task["measurement"]["evidence_anchor_ids"])
        required_evidence.update(task["observed_result"]["evidence_anchor_ids"])
        missing = sorted(required_evidence - catalog)
        if missing:
            evidence_failures.append({"task_id": task["task_id"], "missing_evidence_refs": missing})
    integrity = {
        "schema_version": "reference_integrity_validation_v1",
        "status": "passed" if not integrity_failures and not evidence_failures and not order_failures else "failed",
        "task_count": len(tasks), "integrity_failures": integrity_failures,
        "evidence_ref_failures": evidence_failures, "candidate_order_failures": order_failures,
        "candidate_completeness_checked": False,
        "candidate_completeness_deferred_to": "source_grounded_reference_adjudication_v1",
    }
    source_failures = []
    for task in tasks:
        for ref in task["source_material_refs"]:
            source_path = ROOT / ref.split("#", 1)[0]
            if not source_path.is_file():
                source_failures.append({"task_id": task["task_id"], "ref": ref, "reason": "file_missing"})
    source_report = {
        "schema_version": "source_ref_validation_v1", "status": "passed" if not source_failures else "failed",
        "source_ref_count": sum(len(x["source_material_refs"]) for x in tasks), "failures": source_failures,
        "missing_sections_explicit": all(
            value or value == "not_available"
            for task in tasks for value in task["source_material"].values() if not isinstance(value, list)
        ) and all(
            value and all(entry.get("text") not in {None, ""} for entry in value)
            for task in tasks for value in task["source_material"].values() if isinstance(value, list)
        ),
    }
    canonical_failures = []
    for task in tasks:
        recomputed = payload_hash(task)
        markdown = BLIND / "tasks" / task["task_id"] / "source_packet.md"
        if recomputed != task["identity_sha256"] or task["recomputed_sha256"] != recomputed or not task["identity_match"]:
            canonical_failures.append({"task_id": task["task_id"], "reason": "identity_mismatch"})
        elif markdown.read_text(encoding="utf-8") != render_markdown(task):
            canonical_failures.append({"task_id": task["task_id"], "reason": "markdown_not_from_payload"})
    canonical_report = {
        "schema_version": "canonical_payload_validation_v1",
        "status": "passed" if not canonical_failures else "failed", "task_count": len(tasks),
        "failures": canonical_failures, "json_markdown_same_payload": not canonical_failures,
    }
    blind_ids = {(x["task_id"], x["observation_identity"]) for x in tasks}
    admin_ids = {(x["task_id"], x["observation_identity"]) for x in admin_tasks}
    if blind_ids != admin_ids:
        integrity["status"] = "failed"
        integrity["integrity_failures"].append({"check": "blind_admin_identity_set"})
    return {"blindness": blindness, "integrity": integrity, "source": source_report, "canonical": canonical_report}


def write_zip(path: Path, roots: list[tuple[Path, Path]]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, relative_root in roots:
            for item in sorted(x for x in source.rglob("*") if x.is_file()):
                archive.write(item, relative_root / item.relative_to(source))


def protected_hashes(paths: list[Path]) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths}


def build() -> None:
    if OUT_RUN.exists():
        raise SystemExit(f"refusing to overwrite existing run: {OUT_RUN}")
    head_before = str(run_git("rev-parse", "HEAD")).strip()
    status_before = str(run_git("status", "--short")).splitlines()
    ignored_before = str(run_git("status", "--ignored", "--short")).splitlines()
    tracked_diff_before = run_git("diff", "--binary", binary=True)
    protected = [
        TRIAGE / "comparator_annotation_targets.jsonl", TRIAGE / "factor_measurement_annotation_targets.jsonl",
        REFINEMENT / "core_annotation_observation_bundles.jsonl", REFINEMENT / "source_resolution_envelopes_v2.jsonl",
        CORE / "experimental_factor_records.jsonl", CORE / "measurement_records.jsonl",
        CORE / "observed_result_records.jsonl", CORE / "structured_experimental_observation_revisions.jsonl",
        CORE / "experimental_observation_linkages.jsonl", PROJECTION / "experimental_core_projections_v2.jsonl",
        OBSERVATIONS,
    ]
    hashes_before = protected_hashes(protected)
    for directory in (BLIND / "tasks", BLIND / "manifests", BLIND / "schemas", ADMIN / "tasks", ADMIN / "manifests",
                      PACK / "schemas", PACK / "validation", PACK / "manifests"):
        directory.mkdir(parents=True, exist_ok=True)

    comparator = read_jsonl(TRIAGE / "comparator_annotation_targets.jsonl")
    factor_application = read_jsonl(TRIAGE / "factor_measurement_annotation_targets.jsonl")
    targets = sorted(comparator + factor_application, key=lambda x: (x["task_type"], x["annotation_target_id"]))
    factors = indexed(CORE / "experimental_factor_records.jsonl")
    measurements = indexed(CORE / "measurement_records.jsonl")
    results = indexed(CORE / "observed_result_records.jsonl")
    revisions = indexed(CORE / "structured_experimental_observation_revisions.jsonl", "source_observation_identity")
    linkages = indexed(CORE / "experimental_observation_linkages.jsonl")
    projections = indexed(PROJECTION / "experimental_core_projections_v2.jsonl", "source_observation_identity")
    observations = indexed(OBSERVATIONS, "observation_id")
    envelopes = read_jsonl(REFINEMENT / "source_resolution_envelopes_v2.jsonl")
    envelope_by_v1 = {x["v1_envelope_identity"]: x for x in envelopes}
    readiness = read_jsonl(REFINEMENT / "machine_reuse_readiness_v4_candidates.jsonl")
    remediation = read_jsonl(REFINEMENT / "experimental_core_remediation_requirements_v4.jsonl")
    pilot_rows = read_jsonl(PILOT_IDS)
    pilot_ids = {(x["observation_identity"], x["task_type"]): x["task_id"] for x in pilot_rows if x["task_type"] in ALLOWED}
    pilot_payloads = {(x["observation_identity"], x["task_type"]): x["canonical_payload_identity"] for x in pilot_rows if x["task_type"] in ALLOWED}

    tasks, admin_tasks = [], []
    xml_cache: dict[Path, list[dict[str, str]]] = {}
    for target in targets:
        envelope = envelope_by_v1[target["source_resolution_envelope_identity"]]
        obs = observations[target["observation_identity"]]
        task = make_blind_task(target, envelope, obs, factors, measurements, results, pilot_ids, xml_cache)
        tasks.append(task)
        revision = revisions[target["observation_identity"]]
        admin_tasks.append(make_admin_task(
            task, target, obs, factors, revision, projections[target["observation_identity"]], linkages,
            readiness, remediation, pilot_payloads.get((target["observation_identity"], target["task_type"])),
        ))
    tasks.sort(key=lambda x: x["task_id"])
    admin_tasks.sort(key=lambda x: x["task_id"])

    for task in tasks:
        directory = BLIND / "tasks" / task["task_id"]
        write_json(directory / "task.json", task)
        (directory / "source_packet.md").write_text(render_markdown(task), encoding="utf-8")
    for task in admin_tasks:
        write_json(ADMIN / "tasks" / task["task_id"] / "task.json", task)

    index_rows = [{"task_id": x["task_id"], "task_type": x["task_type"],
                   "observation_identity": x["observation_identity"], "source_document_id": x["source_document_id"]} for x in tasks]
    write_csv(BLIND / "task_index.csv", ["task_id", "task_type", "observation_identity", "source_document_id"], index_rows)
    write_json(BLIND / "task_index.json", index_rows)
    schema = response_schema()
    write_json(PACK / "schemas/reference_adjudication_response_v1.schema.json", schema)
    write_json(BLIND / "schemas/reference_adjudication_response_v1.schema.json", schema)
    (BLIND / "README.md").write_text(
        "# Blind Core Reference Adjudication Pack v1\n\n"
        "This package supports independent, source-grounded reference adjudication. It contains no prior human answer and no system-selected answer.\n\n"
        "Comparator 说明：对于这个具体 Observed Result，论文把结果相对于哪个对照组、基线组或参考组进行报告？\n\n"
        "只选择“参考端”。不要因为某实验组参与了比较，就把实验组本身也作为 Comparator/Reference 选择。\n\n"
        "If the source identifies the relevant object but it is absent from the candidates, use `candidate_set_incomplete`. "
        "This differs from `source_insufficient`, which means the supplied source cannot support a decision.\n\n"
        "Missing source components are displayed explicitly as `not_available`. Candidate completeness has intentionally not been checked or repaired.\n",
        encoding="utf-8",
    )
    (ADMIN / "README.md").write_text(
        "# Admin System Metadata Pack v1\n\nSystem representation for later root-cause analysis. Keep separate from blind adjudication. No prior human responses are included.\n",
        encoding="utf-8",
    )

    inventory = {
        "schema_version": "core_reference_task_inventory_v1", "inventory_source": [
            str((TRIAGE / "comparator_annotation_targets.jsonl").relative_to(ROOT)),
            str((TRIAGE / "factor_measurement_annotation_targets.jsonl").relative_to(ROOT)),
        ],
        "task_count": len(tasks), "task_type_counts": dict(Counter(x["task_type"] for x in tasks)),
        "source_document_count": len({x["source_document_id"] for x in tasks}), "tasks": index_rows,
        "task_count_hardcoded": False,
    }
    write_json(PACK / "manifests/core_reference_task_inventory.json", inventory)
    write_csv(PACK / "manifests/core_reference_task_inventory.csv",
              ["task_id", "task_type", "observation_identity", "source_document_id"], index_rows)
    blind_manifest = {
        "schema_version": "blind_reference_pack_manifest_v1", "status": "pending_validation",
        "task_count": len(tasks), "task_ids": [x["task_id"] for x in tasks],
        "observation_identities": [x["observation_identity"] for x in tasks],
        "source_document_count": inventory["source_document_count"], "answers_included": False,
        "candidate_set_auto_corrected": False,
    }
    admin_manifest = {
        "schema_version": "admin_system_metadata_pack_manifest_v1", "status": "pending_validation",
        "task_count": len(admin_tasks), "task_ids": [x["task_id"] for x in admin_tasks],
        "observation_identities": [x["observation_identity"] for x in admin_tasks],
        "contains_system_metadata": True, "contains_previous_human_answers": False,
    }
    for path in (PACK / "manifests/blind_pack_manifest.json", BLIND / "manifests/blind_pack_manifest.json"):
        write_json(path, blind_manifest)
    for path in (PACK / "manifests/admin_pack_manifest.json", ADMIN / "manifests/admin_pack_manifest.json"):
        write_json(path, admin_manifest)

    target_by_task_id = {stable_task_id(target, pilot_ids): target for target in targets}
    reports = validate(tasks, admin_tasks, factors, measurements, results, observations, target_by_task_id)
    names = {"blindness": "blindness_validation.json", "integrity": "reference_integrity_validation.json",
             "source": "source_ref_validation.json", "canonical": "canonical_payload_validation.json"}
    for key, name in names.items():
        write_json(PACK / "validation" / name, reports[key])
    write_json(BLIND / "manifests/blindness_validation.json", reports["blindness"])
    passed = all(report.get("status", report.get("blind_pack_status")) == "passed" for report in reports.values())
    if not passed:
        raise SystemExit("validation failed; completed ZIP files were not created")
    blind_manifest["status"] = "completed"
    admin_manifest["status"] = "completed"
    for path in (PACK / "manifests/blind_pack_manifest.json", BLIND / "manifests/blind_pack_manifest.json"):
        write_json(path, blind_manifest)
    for path in (PACK / "manifests/admin_pack_manifest.json", ADMIN / "manifests/admin_pack_manifest.json"):
        write_json(path, admin_manifest)

    # Re-scan the final completed manifests and the embedded blindness report so
    # the pass corresponds exactly to the files that will enter the ZIP.
    reports = validate(tasks, admin_tasks, factors, measurements, results, observations, target_by_task_id)
    for key, name in names.items():
        write_json(PACK / "validation" / name, reports[key])
    write_json(BLIND / "manifests/blindness_validation.json", reports["blindness"])
    if not all(report.get("status", report.get("blind_pack_status")) == "passed" for report in reports.values()):
        raise SystemExit("final-state validation failed; completed ZIP files were not created")

    hashes_after = protected_hashes(protected)
    tracked_diff_after = run_git("diff", "--binary", binary=True)
    protection = {
        "schema_version": "historical_asset_protection_validation_v1", "git_head_before": head_before,
        "git_status_before": status_before, "git_status_ignored_before": ignored_before,
        "protected_hashes_before": hashes_before, "protected_hashes_after": hashes_after,
        "historical_assets_modified": hashes_before != hashes_after,
        "preexisting_tracked_diff_preserved": tracked_diff_before == tracked_diff_after,
        "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0,
        "credential_values_read": False, "human_annotation": 0, "gold_created": False,
        "candidate_pairs_modified": False, "formal_v3_modified": False, "atlas_activated": False,
        "active_pointer_changed": False,
    }
    protection["status"] = "passed" if not protection["historical_assets_modified"] and protection["preexisting_tracked_diff_preserved"] else "failed"
    write_json(PACK / "validation/historical_asset_protection_validation.json", protection)
    if protection["status"] != "passed":
        raise SystemExit("historical asset protection validation failed")

    write_zip(OUT_RUN / "core_reference_blind_pack_v1.zip", [(BLIND, Path("blind_reference_pack"))])
    write_zip(OUT_RUN / "core_reference_admin_metadata_pack_v1.zip", [(ADMIN, Path("admin_system_metadata_pack"))])
    checksum_files = sorted(x for x in PACK.rglob("*") if x.is_file() and x.name != "checksums.sha256")
    checksum_files += [OUT_RUN / "core_reference_blind_pack_v1.zip", OUT_RUN / "core_reference_admin_metadata_pack_v1.zip"]
    (PACK / "checksums.sha256").write_text(
        "\n".join(f"{file_hash(path)}  {path.relative_to(OUT_RUN)}" for path in checksum_files) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "completed", "task_count": len(tasks),
                      "task_type_counts": inventory["task_type_counts"],
                      "source_document_count": inventory["source_document_count"]}, sort_keys=True))


if __name__ == "__main__":
    build()
