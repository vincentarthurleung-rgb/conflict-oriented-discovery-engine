"""Zero-network reparse of paid Fulltext L1 v2 smoke responses."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import (
    COMPLETENESS_POLICY_VERSION, HYDRATOR_VERSION, TrustedDraftContextV3,
    hydrate_draft_response_v3,
)
from code_engine.fulltext.evidence_anchors import EVIDENCE_ANCHOR_VERSION
from code_engine.fulltext.experimental_semantics_registry import REGISTRY_VERSION
from code_engine.fulltext.fulltext_l1_v2_smoke import _block_inventory, _historical_config, _jsonl
from code_engine.schemas.fulltext_observation import FulltextL1V3Response
from code_engine.schemas.fulltext_observation_draft import (
    DRAFT_SCHEMA_VERSION, FulltextL1DraftResponse,
)


REPARSE_VERSION = "fulltext_l1_v3_smoke_offline_rehydrate_v1"
ORIGIN = "offline_reparse_existing_smoke_response"


def _hash(value: Any) -> str:
    data = value if isinstance(value, bytes) else str(value).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _evidence(value: Any, default_type: str) -> dict[str, Any] | None:
    if isinstance(value, str) and value:
        return {"model_selected_excerpt_raw": value, "evidence_anchor_ids": ["legacy_exact_text:S0001"], "span_type": default_type}
    if isinstance(value, dict) and isinstance(value.get("text"), str) and value["text"]:
        span_type = str(value.get("span_type") or default_type)
        if span_type not in {"setup", "methods", "intervention", "comparison", "measurement", "observation", "interpretation", "other"}:
            span_type = default_type
        return {"model_selected_excerpt_raw": value["text"], "evidence_anchor_ids": ["legacy_exact_text:S0001"], "span_type": span_type}
    return None


def _intervention(value: dict[str, Any], fallback_evidence: dict[str, Any] | None, *, role_raw: str) -> dict[str, Any]:
    return {
        "role_raw": role_raw,
        "intervention_type_raw": value.get("intervention_type"),
        "intervention_target_mention": value.get("intervention_target_mention"),
        "agent_or_drug_mention": value.get("agent_or_drug_mention"),
        "intervention_method_raw": value.get("intervention_method"),
        "dose_raw": value.get("dose"), "duration_raw": value.get("duration_time"),
        "route_raw": value.get("route"),
        "condition_raw": value.get("condition_raw"),
        "evidence": _evidence(value.get("intervention_span"), "intervention") or fallback_evidence,
    }


def adapt_v4_formal_direct_to_draft(payload: dict[str, Any]) -> dict[str, Any]:
    """Explicit historical-format adapter; this is not accepted by prompt v5."""
    rows = payload.get("experimental_observations")
    if not isinstance(rows, list):
        raise ValueError("response does not contain experimental_observations list")
    drafts: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"observation {index} is not an object")
        provenance = row.get("provenance") or {}
        experiment = row.get("experiment") or {}
        intervention = row.get("intervention") or {}
        measurement = row.get("measurement") or {}
        observation = row.get("observation") or {}
        interpretation = row.get("author_interpretation") or {}
        relation = row.get("candidate_relation") or {}
        evidence_texts = []
        for item in provenance.get("evidence_spans") or []:
            converted = _evidence(item, "other")
            if converted and converted not in evidence_texts:
                evidence_texts.append(converted)
        observation_evidence = _evidence(observation.get("observation_span"), "observation")
        if observation_evidence is None:
            observation_evidence = next((x for x in evidence_texts if x["span_type"] == "observation"), None)
        if observation_evidence is None and evidence_texts:
            observation_evidence = {**evidence_texts[0], "span_type": "observation"}
        if observation_evidence is None:
            raise ValueError(f"observation {index} has no evidence text")
        if observation_evidence not in evidence_texts:
            evidence_texts.append(observation_evidence)
        primary_evidence = _evidence(intervention.get("intervention_span"), "intervention")
        interventions = [_intervention(intervention, primary_evidence, role_raw="primary")]
        secondary = intervention.get("secondary_intervention")
        if isinstance(secondary, dict):
            interventions.append(_intervention(secondary, _evidence(secondary.get("intervention_span"), "intervention"), role_raw="secondary"))
        elif isinstance(secondary, str) and secondary:
            interventions.append({
                "role_raw": "secondary",
                "intervention_type_raw": "unknown", "intervention_target_mention": secondary,
                "agent_or_drug_mention": None, "intervention_method_raw": None, "dose_raw": None,
                "duration_raw": None, "route_raw": None, "condition_raw": secondary, "evidence": None,
            })
        for combo in intervention.get("combination_intervention") or []:
            if isinstance(combo, str) and combo:
                interventions.append({
                    "role_raw": "co_treatment",
                    "intervention_type_raw": "unknown", "intervention_target_mention": combo,
                    "agent_or_drug_mention": None, "intervention_method_raw": None, "dose_raw": None,
                    "duration_raw": None, "route_raw": None, "condition_raw": combo, "evidence": None,
                })
        measured_evidence = _evidence(measurement.get("measurement_span"), "measurement")
        interpretation_evidence = _evidence(interpretation.get("interpretation_span"), "interpretation")
        draft = {
            "experiment": {
                "experiment_label_raw": str(experiment.get("experiment_id") or f"experiment_{index}"),
                "evidence_family_label_raw": str(experiment.get("evidence_family_id") or experiment.get("experiment_id") or f"family_{index}"),
                "experimental_design_raw": experiment.get("experimental_design"),
                "design_type_raw": str(experiment.get("design_type") or "unknown"),
                "species_raw": experiment.get("species"), "model_system_raw": experiment.get("model_system"),
                "cell_line_or_type_raw": experiment.get("cell_line") or experiment.get("cell_type"),
                "tissue_raw": experiment.get("tissue"), "disease_model_raw": experiment.get("disease_model"),
                "genotype_raw": experiment.get("genotype"), "cohort_raw": experiment.get("cohort"),
                "sample_raw": experiment.get("replicate_sample_information"),
                "comparison_arm_raw": experiment.get("comparison_arm"), "control_arm_raw": experiment.get("control_arm"),
            },
            "interventions": interventions,
            "combination_mode_raw": "unknown",
            "measurement": {
                "measurement_dimension_raw": str(measurement.get("measurement_dimension") or "unknown"),
                "measured_entity_mention": measurement.get("measured_entity_mention"),
                "outcome_mention": measurement.get("outcome_mention"),
                "assay_or_readout_raw": measurement.get("assay") or measurement.get("measurement_method"),
                "endpoint_raw": measurement.get("outcome_mention"), "evidence": measured_evidence,
            },
            "observation": {
                "observed_result": observation.get("observed_result"),
                "lexical_direction_raw": relation.get("lexical_direction"),
                "quantitative_result_raw": observation.get("effect_size_or_magnitude"),
                "statistical_support_raw": observation.get("statistical_support"),
                "uncertainty_raw": observation.get("uncertainty"),
                "comparison_raw": observation.get("comparison_relation"),
                "negation": bool(observation.get("negation", False)), "evidence": observation_evidence,
            },
            "interpretation_raw": interpretation.get("author_interpretation") or interpretation.get("author_conclusion"),
            "interpretation_evidence": interpretation_evidence,
            "candidate_relation": {
                "subject_mention": relation.get("subject_mention"), "object_mention": relation.get("object_mention"),
                "relation_wording_raw": relation.get("relation_raw"),
                "lexical_direction_raw": relation.get("lexical_direction"),
                "evidence_design_raw": relation.get("evidence_design_candidate"),
                "confidence_or_qualification_raw": observation.get("uncertainty"),
            },
            "statement_role": row.get("statement_role") or "unknown",
            "evidence_references": evidence_texts,
            "extraction_warnings_raw": list(row.get("extraction_warnings") or []),
        }
        drafts.append(draft)
    result = {"schema_version": DRAFT_SCHEMA_VERSION, "experimental_observations": drafts}
    return FulltextL1DraftResponse.model_validate(result).model_dump(mode="json")


def _raw_path(run_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_file():
        return path
    candidate = run_dir.parent.parent / path
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(value)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reparse_smoke_responses_offline(run_dir: str | Path) -> dict[str, Any]:
    run = Path(run_dir)
    artifacts = run / "artifacts"
    manifest = json.loads((artifacts / "fulltext_l1_v2_smoke_manifest.json").read_text(encoding="utf-8"))
    provider_results = json.loads((artifacts / "fulltext_l1_v2_provider_smoke_results.json").read_text(encoding="utf-8"))
    result_by_block = {str(x["block_id"]): x for x in provider_results.get("results") or []}
    records = _jsonl(artifacts / "fulltext_l1_v2_execution_records.jsonl")
    config = _historical_config(artifacts, records)
    needed_ids = {str(x["block_id"]) for x in manifest.get("samples") or []}
    reconstruction_records = [x for x in records if str(x.get("block_id")) in needed_ids]
    inventory = _block_inventory(run, reconstruction_records, config)
    audit_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    enum_mappings: Counter[str] = Counter(); enum_unresolved: Counter[str] = Counter()
    formal_failures: Counter[str] = Counter(); evidence_counts: Counter[str] = Counter()
    raw_observations = hydrated_count = rejected_count = multi_count = 0
    formal_resolved = formal_reviewable = mixed_count = unknown_count = 0
    anchor_resolved = text_exact = graph_eligible = strict_core_eligible = 0
    valid_json = draft_success = 0
    fully = partial = unresolved = 0
    legacy = Counter()
    for sample in manifest.get("samples") or []:
        block_id = str(sample["block_id"]); result = result_by_block[block_id]
        path = _raw_path(run, str(result["raw_response_path"])); raw_text = path.read_text(encoding="utf-8")
        raw_hash = _hash(raw_text)
        base = {
            "reparse_version": REPARSE_VERSION, "origin": ORIGIN, "block_id": block_id,
            "sample_group": sample["sample_group"], "raw_response_path": str(path),
            "raw_response_hash": raw_hash, "original_prompt_version": result.get("prompt_version"),
            "original_prompt_hash": result.get("prompt_hash"), "original_schema_target": result.get("schema_version"),
            "reparse_draft_schema_version": DRAFT_SCHEMA_VERSION, "hydration_version": HYDRATOR_VERSION,
            "semantics_registry_version": REGISTRY_VERSION,
            "evidence_anchor_version": EVIDENCE_ANCHOR_VERSION,
            "completeness_policy_version": COMPLETENESS_POLICY_VERSION,
        }
        block_status = "unresolved"
        raw_count = formal_count = rejected_for_block = 0
        has_multi_intervention = False
        block_resolved_count = 0; block_mixed = False; block_reviewable_categories: list[str] = []
        try:
            payload = json.loads(raw_text); valid_json += 1
            values = payload.get("experimental_observations") if isinstance(payload, dict) else None
            raw_count = len(values) if isinstance(values, list) else 0
            raw_observations += raw_count
            if sample["sample_group"] == "historical_completed_empty":
                legacy["legacy_empty_raw_nonempty_count" if raw_count else "legacy_empty_raw_empty_count"] += 1
            draft_payload = adapt_v4_formal_direct_to_draft(payload)
            draft = FulltextL1DraftResponse.model_validate(draft_payload); draft_success += 1
            if sample["sample_group"] == "historical_completed_empty" and raw_count:
                legacy["legacy_empty_draft_valid_nonempty_count"] += 1
            item = inventory[block_id]; block = item["block"]; paper = item["paper"]
            section_value = block.get("section") or {}
            section = section_value.get("section_title") if isinstance(section_value, dict) else str(section_value or "") or None
            context = TrustedDraftContextV3(
                run_id=run.name, block_id=block_id, parent_block_id=sample.get("parent_block_id"),
                child_block_id=sample.get("child_block_id"), block_text=str(block["text"]),
                source_block_hash=str(block.get("chunk_hash") or sample.get("original_block_hash")),
                source_document_id=str(paper.get("pmcid") or paper.get("pmid") or paper.get("paper_id")),
                paper_id=str(paper.get("paper_id") or paper.get("pmid") or paper.get("pmcid")),
                pmid=str(paper.get("pmid")) if paper.get("pmid") is not None else None,
                pmcid=str(paper.get("pmcid")) if paper.get("pmcid") is not None else None,
                fulltext_source_hash=item["source_fulltext_hash"], source_artifact=item["article_path"],
                section=section,
            )
            hydrated = hydrate_draft_response_v3(draft, context)
            FulltextL1V3Response.model_validate(hydrated.formal_response)
            formal_count = len(hydrated.formal_response["experimental_observations"])
            rejected_for_block = len(hydrated.rejected)
            hydrated_count += formal_count; rejected_count += rejected_for_block
            for formal in hydrated.formal_response["experimental_observations"]:
                if len(formal["interventions"]) > 1:
                    multi_count += 1; has_multi_intervention = True
                if formal["candidate_relation"]["lexical_direction"] == "mixed": mixed_count += 1
                block_mixed = block_mixed or formal["candidate_relation"]["lexical_direction"] == "mixed"
                unknown_count += int(formal["experiment"]["design_type"] == "unknown")
                unknown_count += int(formal["measurement"]["measurement_dimension"] == "unknown")
                unknown_count += sum(x["intervention_type"] == "unknown" for x in formal["interventions"])
                graph_eligible += int(formal["eligibility"]["graph_eligible"])
                strict_core_eligible += int(formal["eligibility"]["strict_core_eligible"])
            for row in hydrated.audit:
                formal_resolved += int(row.get("formal_status") == "resolved")
                block_resolved_count += int(row.get("formal_status") == "resolved")
                formal_reviewable += int(row.get("formal_status") == "reviewable")
                anchor_resolved += int(row.get("evidence_anchor_resolved_count", 0))
                text_exact += int(row.get("evidence_text_exact_count", 0))
                for mapping in row.get("normalization_audit") or []:
                    enum_mappings[f"{mapping['category']}:{mapping['raw_value']}->{mapping['normalized_value']}:{mapping['status']}"] += 1
                    if mapping["status"] != "resolved": block_reviewable_categories.append(mapping["category"])
                audit_rows.append({**base, "record_type": "observation", **row})
            for rejected in hydrated.rejected:
                formal_failures[rejected["status"]] += 1
                if rejected["status"] == "enum_unresolved":
                    enum_unresolved[rejected["reason"]] += 1
                audit_rows.append({**base, "record_type": "observation", **rejected})
            if rejected_for_block == 0:
                fully += 1; block_status = "fully_hydrated"
            elif formal_count:
                partial += 1; block_status = "partially_hydrated"
            else:
                unresolved += 1
            if sample["sample_group"] == "historical_completed_empty" and raw_count:
                if formal_count:
                    legacy["legacy_empty_formal_valid_nonempty_count"] += 1
                # Preserve visibility of the original Formal-direct schema failure
                # even when the new Draft/hydration path safely recovers it.
                if result.get("status") == "schema_failure" or rejected_for_block or not formal_count:
                    legacy["legacy_empty_nonempty_schema_failure_count"] += 1
                legacy["legacy_empty_false_negative_candidate_count"] += 1
        except json.JSONDecodeError as exc:
            unresolved += 1; formal_failures["malformed_json"] += 1
            audit_rows.append({**base, "record_type": "block", "status": "malformed_json", "reason": str(exc)})
        except (ValidationError, ValueError) as exc:
            unresolved += 1; formal_failures["draft_schema_failure"] += 1
            if sample["sample_group"] == "historical_completed_empty" and raw_count:
                legacy["legacy_empty_nonempty_schema_failure_count"] += 1
                legacy["legacy_empty_false_negative_candidate_count"] += 1
            audit_rows.append({**base, "record_type": "block", "status": "draft_schema_failure", "reason": str(exc)})
        row = {**base, "record_type": "block", "status": block_status,
               "raw_observation_count": raw_count, "hydrated_observation_count": formal_count,
               "rejected_observation_count": rejected_for_block,
               "has_unsupported_multi_intervention": has_multi_intervention,
               "formal_resolved_observation_count": block_resolved_count,
               "has_mixed_direction": block_mixed,
               "reviewable_categories": sorted(set(block_reviewable_categories)),
               "scientific_input_complete": False, "publication_allowed": False}
        block_rows.append(row); audit_rows.append(row)
    scanned = len(manifest.get("samples") or [])
    sample_by_id = {str(x["block_id"]): x for x in manifest.get("samples") or []}
    selected_ids: set[str] = set(); provider_plan_entries: list[dict[str, Any]] = []
    def pick(role: str, predicate) -> None:
        match = next((x for x in block_rows if x["block_id"] not in selected_ids and predicate(x)), None)
        if match:
            selected_ids.add(match["block_id"])
            provider_plan_entries.append({"block_id": match["block_id"], "validation_role": role,
                                          "provider_call_planned": True, "provider_call_executed": False})
    pick("single_intervention_resolved_nonempty", lambda x: x["formal_resolved_observation_count"] > 0 and not x["has_unsupported_multi_intervention"] and not x["has_mixed_direction"] and not x["reviewable_categories"])
    pick("multi_intervention", lambda x: x["has_unsupported_multi_intervention"])
    pick("reviewable_raw_category", lambda x: "intervention_type" in x["reviewable_categories"] or "design_type" in x["reviewable_categories"])
    pick("legacy_empty_high_risk", lambda x: x["sample_group"] == "historical_completed_empty" and sample_by_id[x["block_id"]].get("legacy_empty_risk_subgroup") == "high_false_negative_risk")
    pick("mixed_or_multi_endpoint", lambda x: x["has_mixed_direction"])
    next_selection: list[dict[str, Any]] = []
    for row in [x for x in block_rows if x["sample_group"] == "historical_nonempty_schema_failure" and x["status"] != "fully_hydrated"][:3]:
        next_selection.append({"block_id": row["block_id"], "selection_roles": ["old_nonempty_failure"],
                               "reason": row["status"], "multi_intervention": row["has_unsupported_multi_intervention"]})
    legacy_risk = [x for x in block_rows if x["sample_group"] == "historical_completed_empty"
                   and sample_by_id[x["block_id"]].get("legacy_empty_risk_subgroup") == "high_false_negative_risk"][:2]
    for row in legacy_risk:
        next_selection.append({"block_id": row["block_id"], "selection_roles": ["legacy_empty_high_risk"],
                               "reason": "prompt_version_sensitivity_check", "multi_intervention": False})
    multi = next((x for x in block_rows if x["has_unsupported_multi_intervention"]), None)
    if multi:
        existing = next((x for x in next_selection if x["block_id"] == multi["block_id"]), None)
        if existing:
            existing["selection_roles"].append("multi_intervention_complex")
        elif len(next_selection) < 6:
            next_selection.append({"block_id": multi["block_id"], "selection_roles": ["multi_intervention_complex"],
                                   "reason": multi["status"], "multi_intervention": True})
    summary = {
        "schema_version": REPARSE_VERSION, "origin": ORIGIN,
        "scanned_smoke_blocks": scanned, "valid_json_blocks": valid_json,
        "draft_schema_success_blocks": draft_success, "draft_schema_failure_blocks": scanned - draft_success,
        "raw_observation_count": raw_observations,
        "formal_valid_observation_count": hydrated_count,
        "formal_resolved_observation_count": formal_resolved,
        "formal_reviewable_observation_count": formal_reviewable,
        "formal_rejected_observation_count": rejected_count,
        "hydrated_observation_count": hydrated_count, "rejected_observation_count": rejected_count,
        "multi_intervention_observation_count": multi_count, "mixed_direction_count": mixed_count,
        "unknown_category_count": unknown_count,
        "evidence_anchor_resolved_count": anchor_resolved,
        "evidence_text_exact_count": text_exact,
        "evidence_unresolved_count": rejected_count,
        "draft_parse_unresolved_blocks": scanned - draft_success,
        "formal_fully_hydrated_blocks": fully, "formal_partially_hydrated_blocks": partial,
        "formal_zero_hydrated_blocks": sum(x["hydrated_observation_count"] == 0 and x["raw_observation_count"] > 0 for x in block_rows),
        "formal_complete_blocks": fully, "formal_incomplete_blocks": partial + sum(x["status"] == "unresolved" for x in block_rows),
        "fully_hydrated_blocks": fully, "partially_hydrated_blocks": partial, "unresolved_blocks": unresolved,
        "graph_eligible_count": graph_eligible, "strict_core_eligible_count": strict_core_eligible,
        "enum_mapping_counts": dict(sorted(enum_mappings.items())),
        "enum_unresolved_counts": dict(sorted(enum_unresolved.items())),
        "multi_intervention_count": multi_count,
        "formal_schema_failure_reasons": dict(sorted(formal_failures.items())),
        **{key: legacy[key] for key in (
            "legacy_empty_raw_empty_count", "legacy_empty_raw_nonempty_count",
            "legacy_empty_draft_valid_nonempty_count", "legacy_empty_formal_valid_nonempty_count",
            "legacy_empty_nonempty_schema_failure_count", "legacy_empty_false_negative_candidate_count",
        )},
        "api_calls": 0, "network_calls": 0, "downloads": 0,
        "scientific_input_complete": False, "partial_block_failures": True,
        "publication_allowed": False, "reentry_executed": False, "l2_executed": False,
        "projection_executed": False, "atlas_publication_executed": False,
        "offline_reparse_is_not_prompt_v5_or_v6_provider_success": True,
        "next_smoke_plan": {
            "execute": False, "maximum_blocks": 5,
            "selection": provider_plan_entries,
            "required_mix": "resolved single intervention, multi-intervention, reviewable raw category, high-risk legacy empty, mixed direction or multi-endpoint",
        },
    }
    _write_json(artifacts / "fulltext_l1_v3_smoke_offline_rehydrate_summary.json", summary)
    audit_path = artifacts / "fulltext_l1_v3_smoke_offline_rehydrate_audit.jsonl"
    audit_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in audit_rows), encoding="utf-8")
    lines = [
        "# Fulltext L1 Formal v3 smoke offline rehydration", "",
        f"- Origin: `{ORIGIN}` (not a Prompt v5/v6 provider run)",
        f"- Blocks: {scanned}; Draft-valid: {draft_success}; fully hydrated: {fully}; partial: {partial}; unresolved: {unresolved}",
        f"- Raw observations: {raw_observations}; Formal hydrated: {hydrated_count}; rejected: {rejected_count}",
        f"- Legacy-empty raw nonempty: {legacy['legacy_empty_raw_nonempty_count']}; false-negative candidates: {legacy['legacy_empty_false_negative_candidate_count']}",
        "- Calls: API 0; network 0; downloads 0", "- Scientific completeness: false; publication allowed: false", "",
        "## Block results", "",
        *[f"- `{x['block_id']}`: {x['status']} (raw={x['raw_observation_count']}, hydrated={x['hydrated_observation_count']}, rejected={x['rejected_observation_count']})" for x in block_rows],
    ]
    (artifacts / "fulltext_l1_v3_smoke_offline_rehydrate.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    provider_plan = {
        "schema_version": "fulltext_l1_v3_provider_smoke_plan_v1", "mode": "plan_only",
        "maximum_provider_calls": 5, "planned_provider_calls": len(provider_plan_entries),
        "entries": provider_plan_entries,
        "validation_requirements": ["draft_strict_success", "evidence_anchor_validity", "formal_v3_validity",
                                    "graph_and_core_eligibility", "legacy_empty_raw_nonempty_visibility", "no_schema_drift"],
        "api_calls": 0, "network_calls": 0, "downloads": 0,
        "requires_separate_authorization": True, "executed": False,
    }
    _write_json(artifacts / "fulltext_l1_v3_provider_smoke_plan.json", provider_plan)
    (artifacts / "fulltext_l1_v3_provider_smoke_plan.md").write_text("\n".join([
        "# Fulltext L1 v3 provider smoke plan", "", "Plan only; separate provider authorization is required.", "",
        *[f"- `{x['block_id']}` — {x['validation_role']}" for x in provider_plan_entries], "",
        "Planned calls: 5 maximum. Executed calls: 0.",
    ]) + "\n", encoding="utf-8")
    return {"summary": summary, "blocks": block_rows}


__all__ = ["REPARSE_VERSION", "ORIGIN", "adapt_v4_formal_direct_to_draft", "reparse_smoke_responses_offline"]
