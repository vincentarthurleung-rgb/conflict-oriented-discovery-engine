"""Deterministic, offline-only source reingestion and queue refinement helpers.

The helpers in this module deliberately recover source *scope*.  They never
select a comparator, factor application, or measurement method.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .identities import core_identity


def stable_identity(kind: str, payload: dict[str, Any]) -> str:
    """Return an identity that excludes provenance and pre-existing identities."""
    basis = {k: v for k, v in payload.items() if k not in {"identity", "provenance"}}
    return core_identity(kind, basis)


def source_text_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode()).hexdigest()


def _text(node: ET.Element | None) -> str:
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip() if node is not None else ""


def inspect_local_xml(xml_path: Path, *, relative_to: Path) -> dict[str, Any]:
    """Index section paragraphs and captions without interpreting scientific meaning."""
    if not xml_path.is_file():
        return {
            "available": False, "path": None, "methods": [], "results": [],
            "figures": [], "tables": [], "supplement_references": [],
        }
    root = ET.parse(xml_path).getroot()
    rel = str(xml_path.relative_to(relative_to))
    sections: list[dict[str, Any]] = []
    methods: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for sidx, sec in enumerate(root.findall(".//body//sec")):
        title = _text(sec.find("./title"))
        refs = []
        for pidx, paragraph in enumerate(sec.findall("./p")):
            text = _text(paragraph)
            if text:
                refs.append({
                    "ref": f"{rel}#sec-{sidx}-p-{pidx}",
                    "text": text, "hash": source_text_hash(text), "heading": title,
                })
        record = {"ref": f"{rel}#sec-{sidx}", "heading": title, "paragraphs": refs}
        sections.append(record)
        lowered = title.lower()
        if any(token in lowered for token in ("method", "material", "experimental")):
            methods.append(record)
        if any(token in lowered for token in ("result", "finding")):
            results.append(record)

    def captions(xpath: str, label: str) -> list[dict[str, str]]:
        found = []
        for idx, node in enumerate(root.findall(xpath)):
            text = _text(node)
            if text:
                found.append({
                    "ref": f"{rel}#{label}-{idx}", "text": text,
                    "hash": source_text_hash(text),
                })
        return found

    # The authoritative local corpus also contains BioC XML.  A BioC passage
    # carries section/type metadata instead of JATS ``body/sec`` elements.
    if not sections and root.tag == "collection":
        section_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        figures, tables = [], []
        for pidx, passage in enumerate(root.findall(".//passage")):
            info = {x.attrib.get("key", ""): x.text or "" for x in passage.findall("./infon")}
            section_type = info.get("section_type", "").upper()
            passage_type = info.get("type", "").lower()
            text = re.sub(r"\s+", " ", passage.findtext("./text") or "").strip()
            if not text:
                continue
            item = {
                "ref": f"{rel}#passage-{pidx}", "text": text,
                "hash": source_text_hash(text), "heading": section_type,
            }
            if section_type == "FIG" or "fig_caption" in passage_type:
                figures.append(item)
            elif section_type == "TABLE" or "table_caption" in passage_type:
                tables.append(item)
            elif passage_type in {"paragraph", "abstract"}:
                section_groups[section_type].append(item)
        for section_type, paragraphs in section_groups.items():
            record = {
                "ref": f"{rel}#section-{section_type.lower()}",
                "heading": section_type, "paragraphs": paragraphs,
            }
            sections.append(record)
            if section_type == "METHODS":
                methods.append(record)
            if section_type == "RESULTS":
                results.append(record)
    else:
        figures = captions(".//fig/caption", "figure-caption")
        tables = captions(".//table-wrap/caption", "table-caption")

    supplement_references = []
    for idx, node in enumerate(root.findall(".//supplementary-material")):
        text = _text(node)
        supplement_references.append({
            "ref": f"{rel}#supplement-reference-{idx}",
            "text": text, "content_available": False,
        })
    return {
        "available": True, "path": rel, "sections": sections, "methods": methods,
        "results": results, "figures": figures, "tables": tables,
        "supplement_references": supplement_references,
    }


def recover_source_block(
    requirement: dict[str, Any], *, xml_index: dict[str, Any],
    affected_target_ids: list[str], affected_observation_ids: list[str],
    provenance: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Classify one block and create an immutable sidecar revision when possible."""
    available = bool(xml_index["available"])
    methods = [p for s in xml_index.get("methods", []) for p in s["paragraphs"]]
    results = [p for s in xml_index.get("results", []) for p in s["paragraphs"]]
    figures = xml_index.get("figures", [])
    tables = xml_index.get("tables", [])
    supplements = xml_index.get("supplement_references", [])
    recovered_refs = sorted({
        *(x["ref"] for x in methods), *(x["ref"] for x in results),
        *(x["ref"] for x in figures), *(x["ref"] for x in tables),
    })
    if not available:
        recovery_type, status = "external_content_absent", "unrecoverable_local"
    elif methods:
        recovery_type, status = "local_xml_methods_reparse", "locally_recovered"
    elif figures or tables:
        recovery_type, status = "local_xml_caption_reparse", "locally_recovered"
    elif results:
        recovery_type, status = "local_xml_section_reparse", "locally_recovered"
    else:
        recovery_type, status = "unrecoverable_local", "unrecoverable_local"
    record = {
        "source_recovery_id": "",
        "document_identity": requirement.get("source_document_identity"),
        "source_block_identity": requirement.get("source_block_identity"),
        "affected_observation_ids": sorted(set(affected_observation_ids)),
        "affected_target_ids": sorted(set(affected_target_ids)),
        "local_source_paths": [xml_index["path"]] if xml_index.get("path") else [],
        "xml_availability": available,
        "methods_availability": bool(methods),
        "results_availability": bool(results),
        "figure_caption_availability": bool(figures),
        "table_caption_availability": bool(tables),
        "supplement_availability": "reference_only" if supplements else "not_present",
        "source_anchor_status": "rebuilt" if recovered_refs else "missing",
        "recovery_type": recovery_type,
        "recovery_action": "create_immutable_source_sidecar" if recovered_refs else "plan_external_retrieval",
        "recovery_status": status,
        "recovered_source_refs": recovered_refs,
        "remaining_gaps": [] if recovered_refs else requirement.get("missing_source_components", []),
        "external_retrieval_candidate": not bool(recovered_refs),
        "execution_authorized": False,
        "network_authorized": False,
        "provenance": provenance,
        "schema_version": "local_source_asset_recovery_v1",
    }
    record["identity"] = stable_identity("local_source_asset_recovery_v1", record)
    record["source_recovery_id"] = record["identity"]
    if not recovered_refs:
        return record, None
    revision = {
        "source_asset_revision_id": "",
        "document_identity": requirement.get("source_document_identity"),
        "original_source_identity": requirement["identity"],
        "source_block_identity": requirement.get("source_block_identity"),
        "source_section_refs": [s["ref"] for s in xml_index.get("sections", [])],
        "source_paragraph_refs": [x["ref"] for x in methods + results],
        "source_sentence_refs": [],
        "methods_refs": [x["ref"] for x in methods],
        "results_refs": [x["ref"] for x in results],
        "figure_caption_refs": [x["ref"] for x in figures],
        "table_caption_refs": [x["ref"] for x in tables],
        "group_definition_refs": [],
        "supplement_reference_refs": [x["ref"] for x in supplements],
        "source_text_hashes": sorted({x["hash"] for x in methods + results + figures + tables}),
        "recovery_rule_identity": "local_source_asset_recovery_rules_v1",
        "source_authority": "authoritative_current_fulltext",
        "historical_provider_input_authority": "incomplete",
        "completeness_dimensions": {
            "methods": bool(methods), "results": bool(results),
            "captions": bool(figures or tables), "group_definitions": False,
            "supplement_content": False,
        },
        "supersedes_revision_id": None,
        "immutable": True,
        "provenance": provenance,
        "schema_version": "source_resolution_asset_revision_v2",
    }
    revision["identity"] = stable_identity("source_resolution_asset_revision_v2", revision)
    revision["source_asset_revision_id"] = revision["identity"]
    return record, revision


def rebuild_envelope_v2(
    envelope: dict[str, Any], revision: dict[str, Any] | None,
    *, provenance: dict[str, Any],
) -> dict[str, Any]:
    """Build task-specific completeness flags while keeping v1 immutable."""
    task = envelope["task_type"]
    methods = list(envelope.get("methods_text_refs", []))
    figures = list(envelope.get("figure_caption_refs", []))
    tables = list(envelope.get("table_caption_refs", []))
    groups = list(envelope.get("group_definition_refs", []))
    if revision:
        methods = sorted(set(methods + revision["methods_refs"]))
        figures = sorted(set(figures + revision["figure_caption_refs"]))
        tables = sorted(set(tables + revision["table_caption_refs"]))
        groups = sorted(set(groups + revision["group_definition_refs"]))
    old_complete = str(envelope["source_scope_completeness"]).startswith("complete_for_")
    component_scope = {
        "comparator": old_complete if task == "comparator" else None,
        "factor_application": old_complete if task == "factor_application" else None,
        "measurement_method": old_complete if task == "measurement_method" else None,
    }
    gaps = []
    if not envelope.get("primary_result_sentence"):
        gaps.append("primary_result_sentence_absent")
    if task == "comparator" and not groups:
        gaps.append("group_definition_scope_unverified")
    if task == "factor_application" and not envelope.get("factor_identities"):
        gaps.append("factor_scope_absent")
    if task == "measurement_method" and not methods and not figures and not tables:
        gaps.append("method_scope_absent")
    payload = {
        **envelope,
        "v1_envelope_identity": envelope["identity"],
        "source_asset_revision_v2_ref": revision["identity"] if revision else None,
        "component_specific_scope": component_scope,
        "comparator_scope_complete": component_scope["comparator"],
        "factor_application_scope_complete": component_scope["factor_application"],
        "method_scope_complete": component_scope["measurement_method"],
        "caption_scope_complete": bool(figures or tables),
        "methods_scope_complete": bool(methods),
        "group_definition_scope_complete": bool(groups),
        "supplement_scope_status": (
            "reference_only" if revision and revision["supplement_reference_refs"] else "not_present"
        ),
        "source_gap_reason_codes": sorted(gaps),
        "local_recovery_applied": revision is not None,
        "source_reingestion_still_required": bool(gaps and not revision),
        "external_retrieval_candidate": bool(gaps and not revision),
        "immutable": True,
        "methods_text_refs": methods,
        "figure_caption_refs": figures,
        "table_caption_refs": tables,
        "group_definition_refs": groups,
        "provenance": provenance,
        "schema_version": "source_grounded_experimental_resolution_envelope_v2",
    }
    payload.pop("envelope_id", None)
    payload["identity"] = stable_identity(
        "source_grounded_experimental_resolution_envelope_v2", payload
    )
    payload["envelope_id"] = payload["identity"]
    return payload


def bundle_annotation_targets(
    targets: Iterable[dict[str, Any]], *, provenance: dict[str, Any],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for target in targets:
        grouped[target["observation_identity"]].append(target)
    bundles = []
    for observation, items in sorted(grouped.items()):
        comp = sorted(x["annotation_target_id"] for x in items if x["task_type"] == "comparator")
        factor = sorted(
            x["annotation_target_id"] for x in items if x["task_type"] == "factor_application"
        )
        source_refs = sorted({
            *(ref for x in items for ref in x.get("evidence_refs", [])),
            *(ref for x in items for ref in x.get("methods_refs", [])),
            *(ref for x in items for ref in x.get("caption_refs", [])),
        })
        payload = {
            "annotation_bundle_id": "",
            "observation_identity": observation,
            "source_envelope_identity": items[0]["source_resolution_envelope_identity"],
            "comparator_target_ids": comp,
            "factor_application_target_ids": factor,
            "task_types": sorted({x["task_type"] for x in items}),
            "target_count": len(items),
            "multi_task": len(items) > 1,
            "shared_source_material": source_refs,
            "result_ids": sorted({x["result_identity"] for x in items if x.get("result_identity")}),
            "measurement_ids": sorted({
                x["measurement_identity"] for x in items if x.get("measurement_identity")
            }),
            "factor_ids": sorted({
                fid for x in items for fid in x.get("factor_candidate_ids", [])
            }),
            "annotation_questions": [x["question_text"] for x in items],
            "allowed_labels": sorted({label for x in items for label in x["allowed_labels"]}),
            "abstain_allowed": all(x["abstain_allowed"] for x in items),
            "priority": min(x["annotation_priority"] for x in items),
            "difficulty": max(x["expected_difficulty"] for x in items),
            "domain_expert_required": any(
                x["gold_eligibility_status"] == "needs_domain_expert" for x in items
            ),
            "double_annotation_eligible": all(
                x["gold_eligibility_status"] == "eligible_for_double_annotation" for x in items
            ),
            "annotation_executed": False,
            "human_gold": False,
            "scientific_authority": False,
            "provenance": provenance,
            "schema_version": "core_annotation_observation_bundle_v1",
        }
        payload["identity"] = stable_identity("core_annotation_observation_bundle_v1", payload)
        payload["annotation_bundle_id"] = payload["identity"]
        bundles.append(payload)
    return bundles


def reconcile_sets(
    named_sets: dict[str, set[str]], *, denominator_definition: dict[str, str],
    readiness_precedence: list[str], provenance: dict[str, Any], schema_version: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    names = list(named_sets)
    universe = sorted(set().union(*named_sets.values()))
    membership = []
    for item in universe:
        present = sorted(name for name in names if item in named_sets[name])
        membership.append({
            "record_id": item, "present_in": present,
            "absent_from": sorted(set(names) - set(present)),
            "difference_reason": (
                "all_sets" if len(present) == len(names)
                else "different_upstream_denominator_or_precedence"
            ),
        })
    intersections = {}
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            intersections[f"{left}__{right}"] = sorted(named_sets[left] & named_sets[right])
    payload = {
        "sets": {name: sorted(values) for name, values in named_sets.items()},
        "all_set_ids": sorted(set.intersection(*(named_sets[n] for n in names))),
        "only_ids": {
            name: sorted(named_sets[name] - set().union(
                *(named_sets[n] for n in names if n != name)
            )) for name in names
        },
        "pairwise_intersections": intersections,
        "difference_reason_per_id": {
            x["record_id"]: x["difference_reason"] for x in membership
            if x["difference_reason"] != "all_sets"
        },
        "denominator_definition": denominator_definition,
        "readiness_precedence": readiness_precedence,
        "provenance": provenance,
        "schema_version": schema_version,
    }
    payload["identity"] = stable_identity(schema_version, payload)
    return payload, membership


def run_bounded_iterations(records: list[dict[str, Any]], *, limit: int = 6) -> list[dict[str, Any]]:
    """Validate and truncate an auditable loop at limit or two no-improvement rounds."""
    if not 1 <= limit <= 6:
        raise ValueError("autonomous iteration limit must be between 1 and 6")
    accepted, stagnant = [], 0
    for record in records[:limit]:
        if record.get("scientific_ambiguity_repaired"):
            raise ValueError("scientific ambiguity cannot be autonomously repaired")
        if record["iteration_id"] == 0 and record.get("files_changed"):
            raise ValueError("iteration 0 is scan-only")
        accepted.append(record)
        improved = record["metrics_before"] != record["metrics_after"]
        stagnant = 0 if improved else stagnant + 1
        if stagnant >= 2:
            break
    return accepted
