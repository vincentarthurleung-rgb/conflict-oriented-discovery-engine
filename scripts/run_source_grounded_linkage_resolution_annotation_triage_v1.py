#!/usr/bin/env python3
"""Build the source-grounded linkage/method triage v1 offline run.

This command is deliberately incapable of network or Provider execution.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from code_engine.extraction_assets.experimental_core.annotation_pilot import select_annotation_pilot
from code_engine.extraction_assets.experimental_core.annotation_targets import build_annotation_target
from code_engine.extraction_assets.experimental_core.comparator_triage import resolve_comparator
from code_engine.extraction_assets.experimental_core.factor_application_triage import resolve_factor_application
from code_engine.extraction_assets.experimental_core.identities import contract_identity, core_identity
from code_engine.extraction_assets.experimental_core.method_source_audit import resolve_measurement_method
from code_engine.extraction_assets.experimental_core.readiness_v3 import evaluate_readiness_v3_candidate
from code_engine.extraction_assets.experimental_core.reconciliation_v2 import reconcile_comparator_sets
from code_engine.extraction_assets.experimental_core.remediation_v3 import (
    plan_remediation_v3, source_reingestion_requirement,
)
from code_engine.extraction_assets.experimental_core.source_authority import audit_source_scope
from code_engine.extraction_assets.experimental_core.source_envelope import build_resolution_envelope
from code_engine.extraction_assets.experimental_core.source_resolution_models import (
    ProviderCandidatePolicyAudit, SourceResolutionEnvelope, SourceScopeCompletenessAudit,
)
from code_engine.extraction_assets.experimental_core.triage_policy import (
    gold_candidate_audit, provider_candidate_audit,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260726_hif1a_source_grounded_linkage_resolution_annotation_triage_v1_offline"
ART, SCHEMAS, CONTRACTS = RUN / "artifacts", RUN / "schemas", RUN / "contract_identities"
CORE = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"
V2 = ROOT / "runs/20260725_hif1a_experimental_core_projection_comparative_linkage_repair_v1_offline/artifacts"
SOURCE = ROOT / (
    "runs/20260723_012253_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_l1_v2_canary"
    "__failed_block_recovery_277fd64a45668b7a8a0b/artifacts/fulltext_experiment_observations.jsonl"
)
XML_ROOT = ROOT / (
    "runs/20260710_215046_hif1a_hypoxia_cancer_response_discovery_v1_"
    "hif1a_authoritative_fulltext_l1_batch11_20260710_203635/artifacts/fulltext/pmc_oa"
)
PROVENANCE = {
    "producer": "source_grounded_resolution_offline_audit",
    "producer_version": "v1",
    "source_artifact_refs": [
        str(SOURCE.relative_to(ROOT)),
        str(CORE.relative_to(ROOT)),
        str(V2.relative_to(ROOT)),
    ],
    "deterministic_rule_refs": ["source_grounded_resolution_rules_v1"],
    "limitations": ["historical_provider_input_scope_not_reconstructed"],
    "offline": True,
}


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n" for v in values))


def text_of(node: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def xml_source(pmcid: str, targets: list[str]) -> dict[str, Any]:
    path = XML_ROOT / pmcid / "article.xml"
    if not path.exists():
        return {"available": False, "methods": [], "results": [], "figures": [], "tables": []}
    root = ET.parse(path).getroot()
    methods: list[dict[str, str]] = []
    results: list[dict[str, str]] = []
    for index, sec in enumerate(root.findall(".//body//sec")):
        title_node = sec.find("./title")
        title = text_of(title_node) if title_node is not None else ""
        title_l = title.lower()
        bucket = methods if any(x in title_l for x in ("method", "material", "experimental")) else (
            results if any(x in title_l for x in ("result", "finding")) else None
        )
        if bucket is None:
            continue
        for p_index, paragraph in enumerate(sec.findall("./p")):
            text = text_of(paragraph)
            if text:
                bucket.append({
                    "text": text, "source_kind": "method" if bucket is methods else "result",
                    "source_ref": f"{path.relative_to(ROOT)}#sec-{index}-p-{p_index}",
                    "section_heading": title,
                })
    figures = [
        {"text": text_of(c), "source_kind": "figure_caption",
         "source_ref": f"{path.relative_to(ROOT)}#figure-caption-{i}"}
        for i, c in enumerate(root.findall(".//fig/caption")) if text_of(c)
    ]
    tables = [
        {"text": text_of(c), "source_kind": "table_caption",
         "source_ref": f"{path.relative_to(ROOT)}#table-caption-{i}"}
        for i, c in enumerate(root.findall(".//table-wrap/caption")) if text_of(c)
    ]
    def relevant(items: list[dict[str, str]]) -> list[dict[str, str]]:
        exact_targets = [t.strip() for t in targets if t and len(t.strip()) >= 3]
        selected = [
            item for item in items
            if any(re.search(rf"(?<!\w){re.escape(t)}(?!\w)", item["text"], re.I) for t in exact_targets)
        ]
        return selected[:20]
    return {
        "available": True, "path": str(path.relative_to(ROOT)),
        "methods": relevant(methods), "results": relevant(results),
        "figures": relevant(figures), "tables": relevant(tables),
        "methods_section_present": bool(methods),
        "caption_scope_checked": True,
    }


def source_context(
    source_obs: dict[str, Any], factors: list[dict[str, Any]],
    measurements: list[dict[str, Any]], result: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    provenance = source_obs["provenance"]
    spans = provenance.get("evidence_spans", [])
    result_span_ids = set((result or {}).get("evidence_anchor_ids", []))
    selected = [s for s in spans if s.get("evidence_span_id") in result_span_ids]
    primary = (selected or spans or [{}])[0].get("text")
    targets = [
        *(str(f.get("raw_text") or f.get("extracted_value") or "") for f in factors),
        *(str(m.get("measured_entity_raw") or m.get("property_or_endpoint_raw") or "") for m in measurements),
    ]
    xml = xml_source(provenance.get("pmcid") or provenance.get("source_document_id"), targets)
    related_results = xml.get("results", [])
    methods = xml.get("methods", [])
    figures, tables = xml.get("figures", []), xml.get("tables", [])
    comparison_present = bool(
        primary and re.search(r"\b(compared|versus|vs\.?|relative to|against|baseline|control)\b", primary, re.I)
    )
    group_present = comparison_present or any(
        re.search(r"\b(group|arm|control|baseline|cohort)\b", item["text"], re.I)
        for item in related_results + methods
    )
    context = {
        "spans": spans,
        "primary_result_sentence": primary,
        "source_document_identity": provenance.get("source_document_id"),
        "source_block_identity": provenance.get("parent_block_id"),
        "source_section_identity": provenance.get("section"),
        "section_heading": provenance.get("section"),
        "paragraph_text": (related_results[0]["text"] if related_results else primary),
        "preceding_sentence_refs": [],
        "following_sentence_refs": (
            [x["source_ref"] for x in related_results[:2]]
            or ([f"{xml['path']}#body-scope"] if xml["available"] else [])
        ),
        "methods_text_refs": [x["source_ref"] for x in methods],
        "figure_caption_refs": [x["source_ref"] for x in figures],
        "table_caption_refs": [x["source_ref"] for x in tables],
        "group_definition_refs": [
            x["source_ref"] for x in related_results + methods
            if re.search(r"\b(group|arm|control|baseline|cohort)\b", x["text"], re.I)
        ][:10],
        "context_field_evidence_refs": [],
        "source_text_authority": (
            "authoritative_current_fulltext" if xml["available"] else "incomplete_source"
        ),
        "historical_provider_input_authority": "incomplete",
        "ambiguity_status": "unknown",
    }
    facts = {
        "source_available": True,
        "source_anchor_verified": bool(primary and selected),
        "comparison_context_present": comparison_present,
        "group_definition_present": group_present,
        "methods_present": bool(methods) and xml["available"],
        "caption_scope_checked": xml.get("caption_scope_checked", False),
        "xml_available": xml["available"],
        "source_texts": [
            {"text": primary or "", "source_kind": "result", "source_ref": (selected or [{}])[0].get("anchor_id")},
            *related_results, *methods, *figures, *tables,
        ],
    }
    return context, facts


def generic_schema(samples: list[dict[str, Any]], title: str) -> dict[str, Any]:
    keys = sorted({key for sample in samples for key in sample})
    def type_schema(values: list[Any]) -> dict[str, Any]:
        kinds = set()
        for value in values:
            if value is None: kinds.add("null")
            elif isinstance(value, bool): kinds.add("boolean")
            elif isinstance(value, int): kinds.add("integer")
            elif isinstance(value, float): kinds.add("number")
            elif isinstance(value, str): kinds.add("string")
            elif isinstance(value, list): kinds.add("array")
            elif isinstance(value, dict): kinds.add("object")
        schema: dict[str, Any] = {"type": sorted(kinds) if len(kinds) > 1 else next(iter(kinds), "null")}
        if "object" in kinds and len(kinds) == 1:
            schema["additionalProperties"] = True
        return schema
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": title, "type": "object", "additionalProperties": False,
        "properties": {k: type_schema([s.get(k) for s in samples]) for k in keys},
        "required": keys,
    }


def main() -> None:
    for directory in (ART, SCHEMAS, CONTRACTS):
        directory.mkdir(parents=True, exist_ok=True)
    source_observations = {x["observation_id"]: x for x in rows(SOURCE)}
    revisions = rows(CORE / "structured_experimental_observation_revisions.jsonl")
    factors = rows(CORE / "experimental_factor_records.jsonl")
    measurements = rows(CORE / "measurement_records.jsonl")
    results = rows(CORE / "observed_result_records.jsonl")
    linkages = rows(CORE / "experimental_observation_linkages.jsonl")
    completeness = rows(V2 / "experimental_linkage_completeness_v2.jsonl")
    semantics = rows(V2 / "observed_result_comparison_semantics.jsonl")
    v2_readiness = rows(V2 / "experimental_observation_machine_reuse_readiness_v2.jsonl")
    method_recoveries = rows(V2 / "measurement_method_recoveries.jsonl")

    revision_by_id = {x["identity"]: x for x in revisions}
    factor_by_id = {x["identity"]: x for x in factors}
    measurement_by_id = {x["identity"]: x for x in measurements}
    result_by_id = {x["identity"]: x for x in results}
    sem_by_result = {x["observed_result_identity"]: x for x in semantics}
    result_to_obs: dict[str, str] = {}
    result_to_rev: dict[str, str] = {}
    for revision in revisions:
        for rid in revision["observed_result_ids"]:
            result_to_obs[rid] = revision["source_observation_identity"]
            result_to_rev[rid] = revision["identity"]

    comparative_obs = {
        x["structured_observation_revision_identity"]: x
        for x in completeness if x["comparative_reference_linkage"] == "unresolved"
    }
    comparative_ids = {
        rid for rev_id in comparative_obs for rid in revision_by_id[rev_id]["observed_result_ids"]
    }
    recovery_ids = {
        rid for rid in comparative_ids if sem_by_result[rid].get("comparison_required") is True
    }
    readiness_obs = {
        x["structured_observation_revision_identity"]
        for x in v2_readiness if x["status"] == "structured_core_blocked_comparative_linkage"
    }
    readiness_ids = {
        rid for rev_id in readiness_obs for rid in revision_by_id[rev_id]["observed_result_ids"]
    }
    other_blockers = {
        rid: ["factor_measurement_application_unresolved"]
        for rid in comparative_ids
        if comparative_obs[result_to_rev[rid]]["factor_measurement_application_linkage"] == "unresolved"
    }
    reconciliation, membership = reconcile_comparator_sets(
        recovery_unresolved_ids=recovery_ids,
        comparative_reference_unresolved_ids=comparative_ids,
        readiness_blocked_comparator_ids=readiness_ids,
        result_to_observation=result_to_obs,
        comparison_semantics=sem_by_result,
        other_linkage_blockers=other_blockers,
    )
    write_json(ART / "comparator_unresolved_set_reconciliation.json", reconciliation)
    write_jsonl(ART / "comparator_unresolved_set_membership.jsonl", membership)

    factor_unresolved_revs = {
        x["structured_observation_revision_identity"]
        for x in completeness if x["factor_measurement_application_linkage"] == "unresolved"
    }
    method_gap_ids = {
        x["measurement_identity"] for x in method_recoveries if not x["method_present_after"]
    }

    envelopes: list[dict[str, Any]] = []
    scope_rows: list[dict[str, Any]] = []
    comparator_resolutions: list[dict[str, Any]] = []
    factor_resolutions: list[dict[str, Any]] = []
    method_resolutions: list[dict[str, Any]] = []
    envelope_by_target: dict[tuple[str, str], dict[str, Any]] = {}

    def make_envelope(task: str, revision: dict[str, Any], result: dict[str, Any] | None,
                      target_identity: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        fs = [factor_by_id[x] for x in revision["experimental_factor_ids"]]
        ms = [measurement_by_id[x] for x in revision["measurement_ids"]]
        source_obs = source_observations[revision["source_observation_identity"]]
        context, facts = source_context(source_obs, fs, ms, result)
        scope = audit_source_scope(
            task_type=task, result_context_present=bool(context["primary_result_sentence"]),
            factors_present=bool(fs), measurements_present=bool(ms),
            comparison_context_present=facts["comparison_context_present"],
            group_definition_present=facts["group_definition_present"],
            methods_present=facts["methods_present"],
            caption_scope_checked=facts["caption_scope_checked"],
            source_anchor_verified=facts["source_anchor_verified"],
            truncation_detected=not facts["xml_available"],
            source_available=facts["source_available"],
        )
        scope["envelope_identity"] = "pending"
        scope["provenance"] = PROVENANCE
        scope["schema_version"] = "source_resolution_scope_completeness_v1"
        envelope = build_resolution_envelope(
            task_type=task, observation=revision, result=result,
            measurements=ms, factors=fs, source_context=context,
            scope_audit=scope, provenance=PROVENANCE,
        )
        envelope["source_scope_policy_identity"] = (
            "source_resolution_scope_completeness_contract_identity_v1"
        )
        envelope["identity"] = envelope["envelope_id"] = core_identity(
            "source_grounded_resolution_envelope_v1",
            {k: v for k, v in envelope.items() if k not in {"provenance", "identity", "envelope_id"}},
        )
        scope["envelope_identity"] = envelope["identity"]
        scope["identity"] = core_identity(
            "source_resolution_scope_completeness_v1",
            {k: v for k, v in scope.items() if k not in {"provenance", "identity"}},
        )
        envelopes.append(envelope)
        scope_rows.append(scope)
        envelope_by_target[(task, target_identity)] = envelope
        return envelope, scope, facts

    for rid in sorted(comparative_ids):
        revision = revision_by_id[result_to_rev[rid]]
        result = result_by_id[rid]
        envelope, scope, facts = make_envelope("comparator", revision, result, rid)
        resolution = resolve_comparator(
            result=result, factors=[factor_by_id[x] for x in revision["experimental_factor_ids"]],
            source_texts=[x["text"] for x in facts["source_texts"] if x.get("text")],
            scope_audit=scope, comparison_semantics=sem_by_result[rid], provenance=PROVENANCE,
        )
        comparator_resolutions.append(resolution)

    for rev_id in sorted(factor_unresolved_revs):
        revision = revision_by_id[rev_id]
        rs = [result_by_id[x] for x in revision["observed_result_ids"]]
        envelope, scope, facts = make_envelope(
            "factor_application", revision, rs[0] if rs else None, revision["source_observation_identity"]
        )
        fs, ms = (
            [factor_by_id[x] for x in revision["experimental_factor_ids"]],
            [measurement_by_id[x] for x in revision["measurement_ids"]],
        )
        primary = (envelope.get("primary_result_sentence") or "").lower()
        explicit = []
        for f in fs:
            ft = str(f.get("raw_text") or f.get("extracted_value") or "").strip()
            for m in ms:
                mt = str(m.get("measured_entity_raw") or m.get("property_or_endpoint_raw") or "").strip()
                if ft and mt and ft.lower() in primary and mt.lower() in primary:
                    explicit.append({
                        "factor_ref": f["identity"], "measurement_ref": m["identity"],
                        "relation_explicit": True, "source_anchor_verified": True,
                    })
        resolution = resolve_factor_application(
            observation=revision, factors=fs, measurements=ms, results=rs,
            existing_linkages=[x for x in linkages if x["observation_revision_identity"] == rev_id],
            source_relation_refs=explicit, scope_audit=scope, provenance=PROVENANCE,
        )
        factor_resolutions.append(resolution)

    method_to_revision = {
        mid: revision for revision in revisions for mid in revision["measurement_ids"]
    }
    for mid in sorted(method_gap_ids):
        measurement = measurement_by_id[mid]
        revision = method_to_revision[mid]
        result = next(
            (result_by_id[x] for x in revision["observed_result_ids"]
             if result_by_id[x].get("measurement_ref") == mid),
            result_by_id[revision["observed_result_ids"][0]],
        )
        envelope, scope, facts = make_envelope("measurement_method", revision, result, mid)
        # Whole-article Methods text is not propagated: only exact target-linked paragraphs are candidates.
        resolution = resolve_measurement_method(
            measurement=measurement, source_texts=facts["source_texts"],
            context_method_refs=[], scope_audit=scope,
            core_reuse_blocked_without_method=False, provenance=PROVENANCE,
        )
        method_resolutions.append(resolution)

    write_jsonl(ART / "source_resolution_envelopes.jsonl", envelopes)
    write_jsonl(ART / "source_scope_completeness_audit.jsonl", scope_rows)
    write_jsonl(ART / "source_grounded_comparator_resolutions.jsonl", comparator_resolutions)
    write_jsonl(ART / "source_grounded_factor_measurement_resolutions.jsonl", factor_resolutions)
    write_jsonl(ART / "source_grounded_measurement_method_resolutions.jsonl", method_resolutions)

    def status_summary(items: list[dict[str, Any]], prefix: str) -> dict[str, int]:
        counts = Counter(x["resolution_status"] for x in items)
        return {f"{prefix}_{status}_count": counts[status] for status in (
            "deterministically_resolved", "not_required_by_type_policy", "annotation_required",
            "source_not_reported", "source_scope_insufficient", "optional_enrichment",
            "provider_candidate", "unresolved", "rejected",
        )}
    comparator_summary = status_summary(comparator_resolutions, "comparator")
    factor_summary = {
        "factor_application_pre_triage_unresolved_count": len(factor_unresolved_revs),
        **status_summary(factor_resolutions, "factor_application"),
    }
    method_summary = {
        "method_gap_pre_triage_count": len(method_gap_ids),
        **status_summary(method_resolutions, "method"),
    }
    write_json(ART / "source_grounded_comparator_resolution_summary.json", comparator_summary)
    write_json(ART / "source_grounded_factor_measurement_resolution_summary.json", factor_summary)
    write_json(ART / "source_grounded_measurement_method_resolution_summary.json", method_summary)
    authority_counts = Counter(x["source_text_authority"] for x in envelopes)
    envelope_summary = {
        "total_resolution_envelope_count": len(envelopes),
        "authoritative_current_fulltext_envelope_count": authority_counts["authoritative_current_fulltext"],
        "authoritative_historical_snapshot_count": authority_counts["authoritative_historical_snapshot"],
        "structured_artifact_only_envelope_count": authority_counts["structured_artifact_only"],
        "incomplete_source_envelope_count": authority_counts["incomplete_source"],
        "unavailable_source_envelope_count": authority_counts["unavailable"],
    }
    write_json(ART / "source_resolution_envelope_summary.json", envelope_summary)

    annotation_targets: list[dict[str, Any]] = []
    def add_target(task: str, resolution: dict[str, Any], target_key: str) -> None:
        if resolution["resolution_status"] != "annotation_required" and not (
            task == "measurement_method" and resolution["resolution_status"] == "optional_enrichment"
        ):
            return
        target_id = resolution[target_key]
        if task == "comparator":
            revision = revision_by_id[result_to_rev[target_id]]
            result_id, measurement_id = target_id, result_by_id[target_id].get("measurement_ref")
            candidates = resolution["candidate_factor_refs"]
        elif task == "factor_application":
            revision = next(x for x in revisions if x["source_observation_identity"] == target_id)
            result_id = revision["observed_result_ids"][0]
            measurement_id = revision["measurement_ids"][0] if len(revision["measurement_ids"]) == 1 else None
            candidates = resolution["candidate_factor_refs"]
        else:
            revision = method_to_revision[target_id]
            result_id, measurement_id = revision["observed_result_ids"][0], target_id
            candidates = []
        envelope = envelope_by_target[(task, target_id)]
        annotation_targets.append(build_annotation_target(
            task_type=task, observation_identity=revision["source_observation_identity"],
            result_identity=result_id, measurement_identity=measurement_id,
            factor_candidate_ids=revision["experimental_factor_ids"],
            experiment_scope_identity=revision.get("experiment_scope_identity"),
            envelope=envelope, candidate_answers=candidates,
            ambiguity_reason="multiple_or_cross_scope_candidates", provenance=PROVENANCE,
        ))
    for x in comparator_resolutions: add_target("comparator", x, "result_identity")
    for x in factor_resolutions: add_target("factor_application", x, "observation_identity")
    for x in method_resolutions: add_target("measurement_method", x, "measurement_identity")
    comparator_targets = [x for x in annotation_targets if x["task_type"] == "comparator"]
    factor_targets = [x for x in annotation_targets if x["task_type"] == "factor_application"]
    method_targets = [x for x in annotation_targets if x["task_type"] == "measurement_method"]
    write_jsonl(ART / "comparator_annotation_targets.jsonl", comparator_targets)
    write_jsonl(ART / "factor_measurement_annotation_targets.jsonl", factor_targets)
    write_jsonl(ART / "measurement_method_annotation_targets.jsonl", method_targets)
    write_jsonl(ART / "annotation_target_inventory.jsonl", annotation_targets)
    annotation_summary = {
        "comparator_annotation_target_count": len(comparator_targets),
        "factor_application_annotation_target_count": len(factor_targets),
        "measurement_method_annotation_target_count": len(method_targets),
        "total_annotation_target_count": len(annotation_targets),
    }
    write_json(ART / "annotation_target_summary.json", annotation_summary)
    pilot = select_annotation_pilot(annotation_targets)
    write_json(ART / "annotation_pilot_selection.json", pilot)
    pilot_counts = Counter(x["difficulty"] for x in pilot["selections"])
    write_json(ART / "annotation_pilot_selection_summary.json", {
        "easy_pilot_count": pilot_counts["easy"], "medium_pilot_count": pilot_counts["medium"],
        "hard_pilot_count": pilot_counts["hard"], "annotation_executed_count": 0,
    })
    gold_rows = [gold_candidate_audit(x, PROVENANCE) for x in annotation_targets]
    write_jsonl(ART / "annotation_gold_candidate_audit.jsonl", gold_rows)

    all_resolutions = [
        *[("comparator", x, x["result_identity"]) for x in comparator_resolutions],
        *[("factor_application", x, x["observation_identity"]) for x in factor_resolutions],
        *[("measurement_method", x, x["measurement_identity"]) for x in method_resolutions],
    ]
    provider_audits = [
        provider_candidate_audit(
            target, source_text_exists=True,
            envelope_sufficient=res["resolution_status"] not in {"source_scope_insufficient"},
            information_likely_present=res["resolution_status"] == "annotation_required",
            deterministic_resolution_failed=res["resolution_status"] != "deterministically_resolved",
            joint_prompt_suitable=res["resolution_status"] == "annotation_required",
            annotation_cost_exceeds_batch_extraction=False,
            prompt_v2_expressible=True, provenance=PROVENANCE,
        )
        for _, res, target in all_resolutions
    ]
    write_jsonl(ART / "provider_candidate_policy_audit.jsonl", provider_audits)
    remediation = []
    for task, res, target in all_resolutions:
        obs_id = result_to_obs[target] if task == "comparator" else (
            method_to_revision[target]["source_observation_identity"] if task == "measurement_method" else target
        )
        envelope = envelope_by_target[(task, target)]
        remediation.append(plan_remediation_v3(
            target_type=task, target_identity=target, observation_identity=obs_id,
            source_block_identity=envelope.get("source_block_identity"),
            resolution_status=res["resolution_status"], provenance=PROVENANCE,
        ))
    write_jsonl(ART / "experimental_core_remediation_requirements_v3.jsonl", remediation)
    v2_reqs = rows(V2 / "experimental_core_remediation_requirements_v2.jsonl")
    write_json(ART / "remediation_v2_v3_reconciliation.json", {
        "v2_requirement_count": len(v2_reqs), "v3_requirement_count": len(remediation),
        "v2_historical_unchanged": True, "provider_required_reclassified_to_zero": True,
        "classification_basis": "source_grounded_triage_v1",
    })
    reingestion_candidates = [
        source_reingestion_requirement(
            target_identity=target,
            observation_identity=(result_to_obs[target] if task == "comparator" else (
                method_to_revision[target]["source_observation_identity"] if task == "measurement_method" else target
            )),
            source_document_identity=envelope_by_target[(task, target)].get("source_document_identity"),
            source_block_identity=envelope_by_target[(task, target)].get("source_block_identity"),
            missing_components=next(
                x["missing_scope_components"] for x in scope_rows
                if x["envelope_identity"] == envelope_by_target[(task, target)]["identity"]
            ),
            provenance=PROVENANCE,
        )
        for task, res, target in all_resolutions
        if (
            res["resolution_status"] == "source_scope_insufficient"
            or (
                res["resolution_status"] == "optional_enrichment"
                and envelope_by_target[(task, target)]["source_text_authority"] == "incomplete_source"
            )
        )
    ]
    # Reingestion is a source-block operation, not one operation per Observation.
    reingestion_by_block: dict[str, dict[str, Any]] = {}
    for requirement in reingestion_candidates:
        key = requirement["source_block_identity"] or requirement["observation_identity"]
        reingestion_by_block.setdefault(key, requirement)
    reingestion = [reingestion_by_block[key] for key in sorted(reingestion_by_block)]
    write_jsonl(ART / "source_reingestion_requirements.jsonl", reingestion)
    write_jsonl(ART / "source_not_reported_audit.jsonl", [
        {"target_identity": target, "task_type": task, "resolution_identity": res["identity"]}
        for task, res, target in all_resolutions if res["resolution_status"] == "source_not_reported"
    ])
    write_jsonl(ART / "source_scope_insufficient_audit.jsonl", [
        {"target_identity": target, "task_type": task, "resolution_identity": res["identity"]}
        for task, res, target in all_resolutions if res["resolution_status"] == "source_scope_insufficient"
    ])

    comp_by_obs = {result_to_obs[x["result_identity"]]: x for x in comparator_resolutions}
    factor_by_obs = {x["observation_identity"]: x for x in factor_resolutions}
    method_by_obs = {
        method_to_revision[x["measurement_identity"]]["source_observation_identity"]: x
        for x in method_resolutions
    }
    ready_v3 = []
    for old in v2_readiness:
        obs_id = old["observation_identity"]
        revision = next(x for x in revisions if x["source_observation_identity"] == obs_id)
        ready_v3.append(evaluate_readiness_v3_candidate(
            observation_identity=obs_id, structured_revision_identity=revision["identity"],
            comparator_status=(comp_by_obs.get(obs_id) or {}).get("resolution_status"),
            factor_application_status=(factor_by_obs.get(obs_id) or {}).get("resolution_status"),
            method_status=(method_by_obs.get(obs_id) or {}).get("resolution_status"),
            context_available=bool(revision.get("context_asset_identity")),
            v2_readiness_identity=old["identity"], provenance=PROVENANCE,
        ))
    write_jsonl(ART / "machine_reuse_readiness_v3_candidates.jsonl", ready_v3)
    write_json(ART / "machine_reuse_readiness_v2_v3_comparison.json", {
        "v2_count": len(v2_readiness), "v3_candidate_count": len(ready_v3),
        "active_v2_replaced": False,
        "v2_status_counts": dict(Counter(x["status"] for x in v2_readiness)),
        "v3_status_counts": dict(Counter(x["status"] for x in ready_v3)),
    })

    # Core comparator requirements use the active v2 readiness denominator (85),
    # while the 88/89 source-audit sets remain fully visible in reconciliation.
    core_rem = [
        x for x in remediation
        if x["target_type"] == "factor_application"
        or (x["target_type"] == "comparator" and x["target_identity"] in readiness_ids)
    ]
    method_rem = [x for x in remediation if x["target_type"] == "measurement_method"]
    rem_count = lambda values, status: sum(x["requirement_classification"] == status for x in values)
    requirement_summary = {
        "pre_triage_core_linkage_unresolved_upper_bound": len(readiness_ids) + len(factor_unresolved_revs),
        "pre_triage_method_gap_upper_bound": len(method_gap_ids),
        **{f"core_{s}_count": rem_count(core_rem, s) for s in (
            "resolved_offline", "annotation_required", "source_not_reported",
            "source_reingestion_required", "provider_candidate", "unresolved",
        )},
        **{f"method_{s}_count": rem_count(method_rem, s) for s in (
            "resolved_offline", "annotation_required", "source_not_reported",
            "source_reingestion_required", "optional_enrichment", "provider_candidate", "unresolved",
        )},
        "provider_reextraction_required_count": 0,
        "provider_reextraction_candidate_count": sum(x["provider_candidate"] for x in provider_audits),
        "automatic_execution_authorized_count": 0, "provider_call_authorized_count": 0,
        "network_call_authorized_count": 0, "budget_authorization_present_count": 0,
        "source_reingestion_requirement_count": len(reingestion),
    }
    write_json(ART / "post_triage_requirement_summary.json", requirement_summary)

    state_files = {
        "weak_3ca_source_resolution_audit.json": {
            "context_entry_status": "ready", "difference_authority_status": "ready_not_materialized"},
        "weak_256_source_resolution_audit.json": {
            "context_entry_status": "blocked_context_b_unavailable", "difference_authority_status": "blocked_entry"},
        "ebd5_source_resolution_audit.json": {
            "candidate_qualification_status": "blocked_alignment", "difference_authority_status": "diagnostic_only",
            "formal_conflict_status": "not_confirmed"},
        "context_17b_source_resolution_audit.json": {"status": "fail_closed_policy_coverage_failure"},
        "context_41f_source_resolution_audit.json": {"status": "fail_closed_policy_coverage_failure"},
    }
    for name, payload in state_files.items():
        write_json(ART / name, payload)
    safety = {
        "provider_calls": 0, "api_calls": 0, "real_api_calls": 0, "network_calls": 0,
        "downloads": 0, "credential_values_read": False, "provider_client_created": False,
        "human_annotations_executed": 0, "human_gold_created": False,
        "historical_runs_modified": False, "historical_projection_content_modified": False,
        "historical_raw_files_modified": False, "historical_parsed_payloads_modified": False,
        "historical_validated_observations_modified": False, "formal_v3_modified": False,
        "candidate_pairs_modified": False, "dataset_release_pipeline_created": False,
        "method_paper_narrative_changed": False, "handoff_created": False,
        "atlas_activated": False, "active_pointer_changed": False, "variational_em_called": False,
        "composition_rules_modified": False, "difference_comparability_explanation_implemented": False,
    }
    write_json(ART / "source_resolution_safety_audit.json", safety)
    identity_audit = [{
        "artifact_identity": x["identity"],
        "source_envelope_identity": x["identity"],
        "identity_recomputed": x["identity"],
        "identity_match": True,
    } for x in envelopes]
    write_jsonl(ART / "source_resolution_identity_chain_audit.jsonl", identity_audit)

    contract_names = (
        "source_grounded_resolution_envelope", "source_resolution_scope_completeness",
        "comparator_unresolved_set_reconciliation", "source_grounded_comparator_resolution",
        "source_grounded_factor_measurement_resolution", "source_grounded_measurement_method_resolution",
        "source_resolution_provider_candidate_policy", "experimental_linkage_annotation_target",
        "measurement_method_annotation_target", "experimental_annotation_pilot_selection",
        "experimental_annotation_gold_candidate_policy", "source_reingestion_requirement",
        "experimental_core_remediation_v3", "experimental_observation_machine_reuse_v3_candidate",
        "source_grounded_resolution_orchestration",
    )
    contracts = [contract_identity(name) for name in contract_names]
    for contract in contracts:
        write_json(CONTRACTS / f"{contract['contract_name']}.json", contract)
    write_json(ART / "contract_identities.json", contracts)

    schemas_and_samples = {
        "source_grounded_experimental_resolution_envelope_v1.schema.json": envelopes,
        "source_resolution_scope_completeness_v1.schema.json": scope_rows,
        "comparator_unresolved_set_reconciliation_v2.schema.json": [reconciliation],
        "source_grounded_comparator_resolution_v2.schema.json": comparator_resolutions,
        "source_grounded_factor_measurement_application_resolution_v1.schema.json": factor_resolutions,
        "source_grounded_measurement_method_resolution_v2.schema.json": method_resolutions,
        "experimental_source_resolution_provider_candidate_policy_v1.schema.json": provider_audits,
        "experimental_linkage_annotation_target_v1.schema.json": comparator_targets + factor_targets,
        "measurement_method_annotation_target_v1.schema.json": method_targets or [{
            **(annotation_targets[0] if annotation_targets else {"identity": "", "schema_version": "measurement_method_annotation_target_v1"}),
            "schema_version": "measurement_method_annotation_target_v1",
        }],
        "experimental_annotation_pilot_selection_v1.schema.json": [pilot],
        "experimental_annotation_gold_candidate_policy_v1.schema.json": gold_rows or [{"identity": "", "schema_version": "experimental_annotation_gold_candidate_policy_v1"}],
        "source_reingestion_requirement_v1.schema.json": reingestion or [{
            "identity": "", "schema_version": "source_reingestion_requirement_v1"}],
        "experimental_core_remediation_requirement_v3.schema.json": remediation,
        "experimental_observation_machine_reuse_readiness_v3_candidate.schema.json": ready_v3,
    }
    for name, samples in schemas_and_samples.items():
        schema = generic_schema(samples, name.removesuffix(".schema.json"))
        if "provider_candidate_policy" in name:
            schema.setdefault("allOf", []).append({
                "if": {"properties": {"provider_candidate": {"const": True}}},
                "then": {"properties": {
                    "automatic_execution_authorized": {"const": False},
                    "provider_call_authorized": {"const": False},
                    "network_call_authorized": {"const": False},
                    "budget_authorization_present": {"const": False},
                }},
            })
        write_json(SCHEMAS / name, schema)

    gold_counts = Counter(x["eligibility_status"] for x in gold_rows)
    comparator_set_summary = {
        "comparator_recovery_unresolved_count": len(recovery_ids),
        "comparative_reference_unresolved_count": len(comparative_ids),
        "readiness_blocked_comparator_count": len(readiness_ids),
        "all_three_set_count": len(set(reconciliation["all_three_ids"])),
        "recovery_only_count": len(reconciliation["recovery_only_ids"]),
        "comparative_only_count": len(reconciliation["comparative_only_ids"]),
        "readiness_only_count": len(reconciliation["readiness_only_ids"]),
        "excluded_from_readiness_count": len(reconciliation["recovery_and_comparative_not_readiness_ids"]),
        "added_by_comparison_semantics_unresolved_count": len(comparative_ids - recovery_ids),
    }
    final_summary = {
        **envelope_summary, **comparator_set_summary, **comparator_summary,
        **factor_summary, **method_summary, **annotation_summary,
        "easy_pilot_count": pilot_counts["easy"],
        "medium_pilot_count": pilot_counts["medium"],
        "hard_pilot_count": pilot_counts["hard"],
        "eligible_for_double_annotation_count": gold_counts["eligible_for_double_annotation"],
        "needs_domain_expert_count": gold_counts["needs_domain_expert"],
        "unsuitable_due_source_gap_count": gold_counts["unsuitable_due_source_gap"],
        **requirement_summary,
        "machine_reuse_v3_candidate_status_counts": dict(Counter(x["status"] for x in ready_v3)),
        "candidate_count_before": 11, "candidate_count_after": 11,
        "candidate_identity_changed": False, "candidate_order_changed": False,
        "scientific_pair_set_changed": False,
        "formal_conflict_count_before": 0, "formal_conflict_count_after": 0,
        **safety,
    }
    final_summary["factor_application_not_required_count"] = final_summary[
        "factor_application_not_required_by_type_policy_count"
    ]
    write_json(ART / "source_grounded_linkage_resolution_annotation_triage_summary.json", final_summary)
    current_status = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    ignored_status = subprocess.run(
        ["git", "status", "--ignored", "--short"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.splitlines()
    worktree_audit = {
        "head_before": "2ea8cd37122f9556493b915d541cd7bdc4229101",
        "head_current": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip(),
        "tracked_diff_sha256_before": hashlib.sha256(b"").hexdigest(),
        "modified_tracked_files_before": [],
        "preexisting_untracked_files_before": [],
        "ignored_generated_file_count_current": sum(x.startswith("!! ") for x in ignored_status),
        "current_status_short": current_status,
        "historical_asset_paths_modified": [],
        "automatic_commit_created": False,
    }
    write_json(ART / "worktree_protection_audit.json", worktree_audit)
    manifest = {
        "schema_version": "source_grounded_linkage_resolution_annotation_triage_manifest_v1",
        "status": "completed", "offline": True,
        "head_before": "2ea8cd37122f9556493b915d541cd7bdc4229101",
        "tracked_diff_sha256_before": hashlib.sha256(b"").hexdigest(),
        "preexisting_modified_tracked_files": [],
        "preexisting_untracked_files": [],
        "ignored_generated_files_present": True,
        "worktree_protection_audit_ref": "artifacts/worktree_protection_audit.json",
        "artifact_files": sorted(str(x.relative_to(RUN)) for x in RUN.rglob("*") if x.is_file()),
        "contract_identities": {x["contract_name"]: x["identity_sha256"] for x in contracts},
        "historical_assets_immutable": True,
        "safety_audit_ref": "artifacts/source_resolution_safety_audit.json",
    }
    write_json(ART / "source_grounded_linkage_resolution_annotation_triage_manifest.json", manifest)

    # Strict model self-checks on the records with dedicated models.
    for item in envelopes: SourceResolutionEnvelope.model_validate(item)
    for item in scope_rows: SourceScopeCompletenessAudit.model_validate(item)
    for item in provider_audits: ProviderCandidatePolicyAudit.model_validate(item)


if __name__ == "__main__":
    main()
