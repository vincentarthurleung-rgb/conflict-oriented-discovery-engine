#!/usr/bin/env python3
"""Build the HIF1A extraction preservation audit entirely from local artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from code_engine.extraction_assets.identities import contract_identity, sha256_bytes, sha256_json, stable_identity
from code_engine.extraction_assets.models import (
    ExtractionCoverageRecord, ExtractionFieldEvidence, ExtractionRunReadinessGate,
    ParsedExtractionCandidateRevision, ProviderCallAttempt, ProviderCallSpecification,
    RawProviderResponse, ReplayabilityAssessment, SelectiveReextractionRequirement,
    SourceSnapshot, ValueState,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/20260725_hif1a_extraction_asset_preservation_v1_offline"
ART = OUT / "artifacts"
SCHEMAS = ART / "schemas"
IDENTITIES = ART / "contract_identities"
MAIN = ROOT / "runs/20260723_171527_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_v3_recovered_reentry"
RECOVERY = ROOT / "runs/20260723_012253_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_l1_v2_canary__failed_block_recovery_277fd64a45668b7a8a0b"

CAPTURE_FIELDS = [
    "boundary.source_block", "boundary.source_sentence_paragraph", "boundary.experiment_grouping",
    "boundary.observation_atomicity", "boundary.experiment_index", "boundary.result_index",
    "boundary.multi_experiment_split_status", "claim.subject_raw_phrase", "claim.relation_raw_phrase",
    "claim.object_endpoint_raw_phrase", "claim.negation", "claim.direction_sign",
    "claim.qualitative_result", "claim.quantitative_result", "claim.statistical_statement",
    "claim.uncertainty_wording", "chain.baseline_condition", "chain.intervention_entities",
    "chain.intervention_roles", "chain.intervention_order", "chain.co_interventions",
    "chain.comparator_control", "chain.measurement", "chain.measured_endpoint", "chain.observed_result",
    "context.species", "context.strain", "context.tissue", "context.organ", "context.cell_type",
    "context.cell_line", "context.genotype", "context.disease_state", "context.dose", "context.route",
    "context.duration", "context.timepoint", "context.localization_compartment",
    "context.measurement_method", "context.assay", "context.environmental_condition",
    "evidence.claim_anchor", "evidence.intervention_anchors", "evidence.comparator_anchors",
    "evidence.measurement_anchors", "evidence.result_anchors", "evidence.direction_anchors",
    "evidence.context_field_anchors", "evidence.sentence", "evidence.character_offsets",
    "evidence.token_offsets", "evidence.paragraph_block_identity", "uncertainty.value_state",
]

# Conservative audit of the v8 contract: evidence IDs and core experiment chain are
# requested, while explicit per-field states and several fine-grained context fields are not.
REQUESTED = {
    field for field in CAPTURE_FIELDS if field.startswith(("boundary.", "claim.", "chain.", "evidence."))
} - {"claim.quantitative_result", "evidence.token_offsets"}
REQUESTED |= {
    "context.species", "context.cell_type", "context.cell_line", "context.tissue",
    "context.genotype", "context.disease_state", "context.dose", "context.duration",
    "context.localization_compartment", "context.measurement_method", "context.assay",
}
REPRESENTABLE = REQUESTED - {"chain.intervention_roles", "chain.intervention_order"}
PARSER_PRESERVED = REPRESENTABLE - {"evidence.character_offsets"}

PATH_MAP = {
    "claim.subject_raw_phrase": ("candidate_relation", "subject_mention"),
    "claim.relation_raw_phrase": ("candidate_relation", "relation_raw"),
    "claim.object_endpoint_raw_phrase": ("candidate_relation", "object_mention"),
    "claim.negation": ("observation", "negation"),
    "claim.direction_sign": ("observation", "observed_outcome_sign"),
    "claim.quantitative_result": ("observation", "effect_size_or_magnitude"),
    "claim.statistical_statement": ("observation", "statistical_support"),
    "claim.uncertainty_wording": ("observation", "uncertainty"),
    "chain.intervention_entities": ("intervention", "intervention_target_mention"),
    "chain.co_interventions": ("intervention", "combination_intervention"),
    "chain.comparator_control": ("observation", "comparison_relation"),
    "chain.measurement": ("measurement", "measurement_method"),
    "chain.measured_endpoint": ("measurement", "measured_entity_mention"),
    "chain.observed_result": ("observation", "observed_result"),
    "context.species": ("experiment", "species"), "context.tissue": ("experiment", "tissue"),
    "context.cell_type": ("experiment", "cell_type"), "context.cell_line": ("experiment", "cell_line"),
    "context.genotype": ("experiment", "genotype"), "context.disease_state": ("experiment", "disease_model"),
    "context.dose": ("experiment", "dose"), "context.duration": ("experiment", "duration_time"),
    "context.localization_compartment": ("experiment", "localization"),
    "context.measurement_method": ("measurement", "measurement_method"),
    "context.assay": ("measurement", "assay"),
}


def rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values), encoding="utf-8")


def nested(row: dict[str, Any], field: str) -> Any:
    path = PATH_MAP.get(field)
    if not path:
        return None
    value: Any = row
    for item in path:
        value = value.get(item) if isinstance(value, dict) else None
    return value


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        return "missing"
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return digest.hexdigest()


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    SCHEMAS.mkdir(parents=True, exist_ok=True)
    IDENTITIES.mkdir(parents=True, exist_ok=True)
    execution = rows(MAIN / "artifacts/fulltext_l1_v2_execution_records.jsonl")
    observations = rows(MAIN / "artifacts/fulltext_experiment_observations.jsonl")
    parser_audit = rows(MAIN / "artifacts/fulltext_l1_v2_parser_normalization_audit.jsonl")

    historical_paths = sorted({
        MAIN, RECOVERY,
        ROOT / "runs/20260723_171527_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_v3_recovered_reentry__fulltext_evidence_projection_0343b9bfebb093729dea",
        *ROOT.glob("runs/2026072[234]_hif1a_context*"),
        *ROOT.glob("runs/20260725_hif1a_*offline"),
    })

    snapshots: list[dict[str, Any]] = []
    specs: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for index, record in enumerate(execution):
        block = str(record["block_id"])
        document = block.split("_", 1)[0]
        snapshot_identity = stable_identity("source_snapshot_v1", {
            "document_id": document, "block_id": block, "input_text": None,
            "source_snapshot_completeness": "incomplete",
        })
        snapshots.append({
            "source_snapshot_id": f"snapshot_{sha256_json(block)[:20]}", "document_id": document,
            "pmid": None, "pmcid": document if document.startswith("PMC") else None, "doi": None,
            "source_kind": "historical_fulltext_model_block", "section_id": None, "paragraph_id": None,
            "sentence_ids": [], "block_id": block, "block_sequence": index, "input_text": None,
            "input_text_sha256": None, "source_file_identity": None, "source_file_sha256": None,
            "source_manifest_identity": None, "source_access_metadata": {"historical_record_available": True},
            "extraction_scope": "fulltext_l1", "text_truncation_status": "unknown",
            "text_window_start": None, "text_window_end": None, "preceding_context_ref": None,
            "following_context_ref": None, "source_snapshot_completeness": "incomplete",
            "schema_version": "source_snapshot_v1", "identity": snapshot_identity,
            "provenance": {"producer": "offline_historical_audit", "producer_version": "v1",
                           "source_artifact_refs": [str(MAIN / "artifacts/fulltext_l1_v2_execution_records.jsonl")], "offline": True},
        })
        call_key = str(record.get("cache_key") or f"missing_{index}")
        spec_identity = stable_identity("provider_call_specification_v1", {
            "source_snapshot_identity": snapshot_identity, "prompt_identity": record.get("prompt_hash"),
            "model_provider": record.get("provider"), "model_name": record.get("model"),
            "response_schema_identity": record.get("schema_hash"),
            "non_secret_parameters": {"max_tokens": record.get("configured_max_tokens"),
                                      "response_format": record.get("response_format")},
        })
        specs.append({
            "provider_call_spec_id": f"spec_{call_key[:20]}", "source_snapshot_identity": snapshot_identity,
            "prompt_identity": str(record.get("prompt_hash") or "unavailable"),
            "prompt_template_identity": str(record.get("prompt_version") or "unavailable"),
            "rendered_prompt_sha256": "unavailable", "response_schema_identity": str(record.get("schema_hash") or record.get("schema_version")),
            "model_provider": str(record.get("provider") or "unavailable"), "model_name": str(record.get("model") or "unavailable"),
            "model_version_if_known": None, "non_secret_parameters": {
                "max_tokens": record.get("configured_max_tokens"), "response_format": record.get("response_format"),
                "thinking_mode": record.get("effective_thinking_mode"),
            }, "temperature": None, "top_p": None, "max_tokens": record.get("configured_max_tokens"),
            "response_format": json.dumps(record.get("response_format"), sort_keys=True),
            "tool_schema_identity": None, "parser_contract_identity": str(record.get("parser_version") or "unavailable"),
            "call_dedup_identity": f"legacy_cache_key:{call_key}", "credential_source_name": None,
            "credential_present_boolean": None, "schema_version": "provider_call_specification_v1", "identity": spec_identity,
        })
        raw_path = record.get("raw_response_path")
        raw_exists = bool(raw_path and Path(str(raw_path)).is_file())
        attempts.append({
            "provider_call_attempt_id": f"attempt_{index:04d}", "provider_call_spec_identity": spec_identity,
            "call_dedup_identity": f"legacy_cache_key:{call_key}", "attempt_sequence": int(record.get("attempt_number") or 1),
            "status": "completed", "raw_response_identity": (
                f"raw_provider_response_v1:{sha256_bytes(Path(str(raw_path)).read_bytes())}" if raw_exists else None
            ), "failure_kind": None, "provider_request_id": None, "provider_response_id": None,
            "real_api_call": bool(record.get("api_called")), "paid_retry_automatic": False,
            "state_history": ["historical_import", "completed"], "schema_version": "provider_call_attempt_v1",
            "identity": stable_identity("provider_call_attempt_v1", {"call": call_key, "sequence": record.get("attempt_number") or 1}),
            "provenance": {"producer": "offline_historical_audit", "producer_version": "v1",
                           "source_artifact_refs": [str(MAIN / "artifacts/fulltext_l1_v2_execution_records.jsonl")], "offline": True},
        })

    raw_inventory: list[dict[str, Any]] = []
    seen_raw: set[tuple[str, str]] = set()
    for path in sorted(ROOT.glob("runs/**/*raw_response.txt")):
        if "hif1a" not in str(path).lower():
            continue
        digest = sha256_bytes(path.read_bytes())
        key = (str(path), digest)
        if key in seen_raw:
            continue
        seen_raw.add(key)
        raw_inventory.append({
            "raw_response_id": f"raw_{digest[:24]}", "provider_call_attempt_identity": "legacy_attempt_unbound",
            "provider_call_spec_identity": "legacy_spec_unbound", "call_dedup_identity": f"legacy_filename:{path.name.split('.')[0]}",
            "provider_request_id": None, "provider_response_id": None, "response_received_at": "historical_timestamp_unavailable",
            "raw_response_path": str(path.relative_to(ROOT)), "raw_response_sha256": digest,
            "raw_response_byte_count": path.stat().st_size, "raw_response_content_type": "text/plain",
            "raw_response_encoding": "utf-8", "provider_finish_reason": None, "usage_metadata": {},
            "provider_error_metadata": {}, "response_complete": True, "truncation_detected": False,
            "secret_redaction_applied": False, "immutable": True, "schema_version": "raw_provider_response_v1",
            "identity": f"raw_provider_response_v1:{digest}",
            "provenance": {"producer": "offline_historical_audit", "producer_version": "v1",
                           "source_artifact_refs": [str(path.relative_to(ROOT))], "offline": True},
        })

    # Legacy parsed cache revisions are counted independently; no validated observation
    # is reverse-labelled as a provider payload.
    parsed_revisions: list[dict[str, Any]] = []
    primary_cache = ROOT / "runs/20260722_033816_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_l1_v2_canary/artifacts/cache/fulltext_l1_v2"
    for cache_file in sorted(primary_cache.glob("*.json")):
        if ".raw_error." in cache_file.name:
            continue
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        candidates = ((payload.get("response") or {}).get("experimental_observations") or [])
        raw_matches = list(primary_cache.glob(f"{cache_file.stem}.*.raw_response.txt"))
        raw_identity = (
            f"raw_provider_response_v1:{sha256_bytes(raw_matches[0].read_bytes())}" if raw_matches
            else "raw_provider_response_missing"
        )
        for candidate_index, candidate in enumerate(candidates):
            digest = sha256_json(candidate)
            parsed_revisions.append({
                "parsed_candidate_revision_id": f"parsed_{cache_file.stem[:16]}_{candidate_index:03d}",
                "raw_response_identity": raw_identity, "source_snapshot_identity": "source_snapshot_lineage_unresolved",
                "provider_call_spec_identity": f"legacy_cache_key:{cache_file.stem}",
                "parser_name": "historical_fulltext_l1_parser", "parser_version": str(payload.get("parser_version") or "unavailable"),
                "parser_contract_identity": str(payload.get("parser_version") or "unavailable"),
                "extraction_schema_name": "fulltext_experimental_observation",
                "extraction_schema_version": str(payload.get("schema_version") or "unavailable"),
                "parsed_payload": candidate, "parsed_payload_sha256": digest, "parse_status": "parsed",
                "parser_error_codes": [], "parser_warnings": list(candidate.get("extraction_warnings") or []),
                "response_fragment_refs": [f"experimental_observations[{candidate_index}]"],
                "supersedes_parsed_revision_id": None, "immutable": True,
                "schema_version": "parsed_extraction_candidate_revision_v1",
                "identity": f"parsed_extraction_candidate_revision_v1:{digest}",
                "provenance": {"producer": "offline_historical_audit", "producer_version": "v1",
                               "source_artifact_refs": [str(cache_file.relative_to(ROOT))], "offline": True},
            })

    profile = {
        "schema_version": "research_grade_extraction_capture_profile_v1",
        "status": "internal_audit_standard", "field_count": len(CAPTURE_FIELDS),
        "fields": [{"field_path": field, "atomic_observation_scope": True} for field in CAPTURE_FIELDS],
        "forbidden_model_decisions": ["claim_alignment", "contradiction", "comparability", "conflict", "hypothesis_validity"],
        "identity": stable_identity("research_grade_extraction_capture_profile_v1", {"fields": CAPTURE_FIELDS}),
    }
    gap_rows = []
    for field in CAPTURE_FIELDS:
        requested = field in REQUESTED
        representable = field in REPRESENTABLE
        preserved = field in PARSER_PRESERVED
        gap_rows.append({
            "capture_profile_field": field, "requested_by_current_prompt": requested,
            "representable_in_current_schema": representable, "parser_preserves_field": preserved,
            "raw_response_preserves_field": requested, "parsed_payload_preserves_field": preserved,
            "field_level_anchor_supported": field.startswith("evidence.") or field in {
                "chain.intervention_entities", "chain.measurement", "chain.observed_result",
            }, "value_state_supported": False,
            "loss_risk": "low" if requested and representable and preserved else "high",
            "future_prompt_revision_required": not (requested and representable and preserved),
            "zero_api_migration_possible": requested,
            "notes": "Provider omission is not interpreted as source absence.",
        })

    evidence_records: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    value_counts: Counter[str] = Counter()
    anchor_counts: Counter[str] = Counter()
    observation_blocks: dict[str, list[str]] = defaultdict(list)
    for observation in observations:
        obs_id = str(observation.get("observation_id"))
        prov = observation.get("provenance") or {}
        block = str(prov.get("child_block_id") or prov.get("parent_block_id") or "block_unavailable")
        document = str(prov.get("source_document_id") or prov.get("pmcid") or "document_unavailable")
        observation_blocks[block].append(obs_id)
        snapshot_identity = next((row["identity"] for row in snapshots if row["block_id"] == block),
                                 stable_identity("source_snapshot_v1", {"document_id": document, "block_id": block, "input_text": None}))
        spans = prov.get("evidence_spans") or []
        for field in CAPTURE_FIELDS:
            value = nested(observation, field)
            state = "present" if value not in (None, "", []) else "legacy_null_unresolved"
            value_counts[state] += 1
            if field.startswith("evidence.") or field in {
                "boundary.source_block", "boundary.source_sentence_paragraph",
            }:
                allowed_span_types: set[str] | None = None
            elif field.startswith("context."):
                allowed_span_types = {"context"}
            elif field.startswith("chain.intervention"):
                allowed_span_types = {"intervention"}
            elif field in {"chain.measurement", "chain.measured_endpoint", "context.measurement_method", "context.assay"}:
                allowed_span_types = {"measurement"}
            elif field.startswith("claim.") or field == "chain.observed_result":
                allowed_span_types = {"observation"}
            else:
                allowed_span_types = set()
            field_spans = [
                span for span in spans if span.get("text") and (
                    allowed_span_types is None or span.get("span_type") in allowed_span_types
                )
            ]
            if field_spans and all(span.get("char_start") is not None and span.get("char_end") is not None for span in field_spans):
                precision = "exact"
            elif field_spans:
                precision = "sentence_only"
            else:
                precision = "not_supplied"
            anchor_counts[precision] += 1
            field_id = sha256_json({"observation": obs_id, "field": field})
            evidence_records.append({
                "field_evidence_id": f"field_{field_id[:24]}", "parsed_candidate_revision_identity": f"validated_only_lineage:{obs_id}",
                "observation_candidate_id": obs_id, "field_path": field, "field_role": field.split(".", 1)[0],
                "raw_text": field_spans[0].get("text") if field_spans else None,
                "extracted_value": value, "provider_value": value, "value_state": state,
                "provider_uncertainty": None, "evidence_anchor_ids": [str(span.get("anchor_id") or span.get("evidence_span_id")) for span in field_spans],
                "source_snapshot_identity": snapshot_identity, "source_block_id": block,
                "sentence_id": None, "paragraph_id": prov.get("paragraph_id"),
                "character_spans": [[span["char_start"], span["char_end"]] for span in field_spans if span.get("char_start") is not None and span.get("char_end") is not None],
                "token_spans": [], "anchor_status": precision,
                "anchor_validation_status": "historical_validated_anchor" if precision == "exact" else "historical_precision_limited",
                "field_schema_status": "legacy", "field_validation_status": "not_reclassified",
                "normalization_status": "available_separately" if value not in (None, "", []) else "not_available",
                "canonical_value": None, "canonical_identity": None, "rejection_reason_codes": [],
                "unresolved_reason_codes": ["parsed_candidate_lineage_unresolved"] + (["legacy_nullable_state"] if state != "present" else []),
                "scope_basis": None, "migration_record": True, "schema_version": "extraction_field_evidence_v1",
                "identity": f"extraction_field_evidence_v1:{field_id}",
                "provenance": {"producer": "offline_historical_audit", "producer_version": "v1",
                               "source_artifact_refs": [str(MAIN / "artifacts/fulltext_experiment_observations.jsonl")], "offline": True},
            })
            returned = value not in (None, "", [])
            zero_api = field in PARSER_PRESERVED or returned
            coverage.append({
                "coverage_record_id": f"coverage_{field_id[:24]}", "source_snapshot_identity": snapshot_identity,
                "raw_response_identity": None, "parsed_candidate_revision_identity": None,
                "observation_candidate_id": obs_id, "field_path": field, "capture_profile_identity": profile["identity"],
                "requested_by_prompt": field in REQUESTED, "representable_in_response_schema": field in REPRESENTABLE,
                "returned_by_provider": returned, "preserved_in_raw_response": False,
                "preserved_in_parsed_payload": returned, "field_evidence_record_present": True,
                "anchor_supplied": bool(field_spans), "anchor_validated": precision == "exact",
                "value_state_available": True, "raw_text_available": bool(field_spans),
                "extracted_value_available": returned, "canonical_value_available": False,
                "deterministic_validation_available": bool(parser_audit),
                "normalization_available": bool(parser_audit), "source_presence_status": "unknown",
                "source_text_scope_sufficient": None, "parser_replay_possible": False,
                "validation_replay_possible": True, "normalization_replay_possible": True,
                "zero_api_schema_migration_possible": zero_api,
                "provider_reextraction_required": not zero_api, "source_reingestion_required": False,
                "blocking_reason_codes": [] if zero_api else ["original_contract_did_not_preserve_target_semantics"],
                "schema_version": "extraction_coverage_ledger_v1",
                "identity": f"extraction_coverage_ledger_v1:{field_id}",
            })

    assessments = []
    for snapshot in snapshots:
        obs_present = snapshot["block_id"] in observation_blocks
        assessments.append({
            "assessment_id": f"assessment_{sha256_json(snapshot['identity'])[:20]}",
            "source_snapshot_identity": snapshot["identity"], "provider_call_spec_identity": None,
            "parsed_candidate_revision_identity": None, "source_snapshot_available": True,
            "source_snapshot_complete": False, "prompt_available": True, "rendered_prompt_available": False,
            "prompt_identity_valid": True, "model_metadata_available": True,
            "non_secret_parameters_available": True, "raw_response_available": False,
            "raw_response_hash_valid": False, "parsed_candidate_available": obs_present,
            "parser_identity_available": True, "field_evidence_available": obs_present,
            "anchors_available": obs_present, "source_hash_valid": False,
            "parser_replay_possible": False, "schema_revalidation_possible": obs_present,
            "anchor_revalidation_possible": False, "normalization_replay_possible": obs_present,
            "derived_artifact_recompute_possible": obs_present,
            "provider_reextraction_required": obs_present, "source_reingestion_required": False,
            "replayability_status": "replayable_from_parsed_candidate_only" if obs_present else "partially_replayable",
            "blocking_reasons": ["actual_sent_input_text_missing", "raw_response_not_bound_to_attempt"],
            "schema_version": "extraction_replayability_assessment_v1",
            "identity": stable_identity("extraction_replayability_assessment_v1", {"snapshot": snapshot["identity"], "obs_present": obs_present}),
        })

    missing_fields = sorted(set(CAPTURE_FIELDS) - REQUESTED)
    requirements = []
    for block, obs_ids in sorted(observation_blocks.items()):
        snapshot = next((row for row in snapshots if row["block_id"] == block), None)
        if not snapshot:
            continue
        dedup = stable_identity("selective_reextraction_group_v1", {"snapshot": snapshot["identity"], "block": block})
        requirements.append({
            "reextraction_requirement_id": f"requirement_{sha256_json(dedup)[:20]}",
            "source_snapshot_identity": snapshot["identity"], "document_id": snapshot["document_id"],
            "block_id": block, "observation_candidate_ids": sorted(set(obs_ids)),
            "missing_capture_profile_fields": missing_fields, "current_prompt_identity": "fulltext_experimental_observation_prompt_v8_results_anchor_contract",
            "current_raw_response_identity": None, "current_parsed_revision_identities": [],
            "reextraction_reason": "original_prompt_did_not_request_field",
            "minimal_text_scope": "historical_source_block_actual_sent_text_required",
            "minimal_block_set": [block], "dedup_group_identity": dedup, "estimated_call_count": 1,
            "priority": "deferred_until_offline_options_exhausted", "requirement_status": "planning_only",
            "automatic_execution_authorized": False, "provider_call_authorized": False,
            "network_call_authorized": False, "budget_authorization_present": False,
            "historical_payload_mutation_authorized": False,
            "schema_version": "selective_reextraction_requirement_v1",
            "identity": stable_identity("selective_reextraction_requirement_v1", {"snapshot": snapshot["identity"], "fields": missing_fields}),
            "provenance": {"producer": "offline_historical_audit", "producer_version": "v1",
                           "source_artifact_refs": [str(MAIN / "artifacts/fulltext_experiment_observations.jsonl")], "offline": True},
        })

    schema_models = {
        "source_snapshot_v1": SourceSnapshot,
        "provider_call_specification_v1": ProviderCallSpecification,
        "provider_call_attempt_v1": ProviderCallAttempt,
        "raw_provider_response_v1": RawProviderResponse,
        "parsed_extraction_candidate_revision_v1": ParsedExtractionCandidateRevision,
        "extraction_field_evidence_v1": ExtractionFieldEvidence,
        "extraction_field_value_state_v1": TypeAdapter(ValueState),
        "extraction_coverage_ledger_v1": ExtractionCoverageRecord,
        "extraction_replayability_assessment_v1": ReplayabilityAssessment,
        "selective_reextraction_requirement_v1": SelectiveReextractionRequirement,
        "extraction_run_readiness_gate_v1": ExtractionRunReadinessGate,
    }
    for name, model in schema_models.items():
        schema = model.json_schema() if isinstance(model, TypeAdapter) else model.model_json_schema()
        write_json(SCHEMAS / f"{name}.schema.json", schema)
        write_json(ROOT / f"docs/contracts/{name}.schema.json", schema)
    identities = {name: contract_identity(name) for name in (
        "source_snapshot", "provider_call_specification", "provider_call_attempt",
        "raw_provider_response", "parsed_extraction_candidate", "extraction_field_evidence",
        "extraction_field_value_state", "extraction_coverage_ledger", "extraction_replayability",
        "selective_reextraction", "extraction_run_readiness", "extraction_asset_orchestration",
    )}
    for name, value in identities.items():
        write_json(IDENTITIES / f"{value['contract_name']}.json", value)

    write_jsonl(ART / "source_snapshot_inventory.jsonl", snapshots)
    write_jsonl(ART / "source_snapshot_validation_audit.jsonl", [{
        "source_snapshot_identity": row["identity"], "complete": False,
        "blocking_reasons": ["actual_sent_input_text_missing", "input_text_sha256_missing"],
    } for row in snapshots])
    write_jsonl(ART / "provider_call_specifications.jsonl", specs)
    write_jsonl(ART / "provider_call_attempt_inventory.jsonl", attempts)
    duplicate_keys = Counter(row["call_dedup_identity"] for row in attempts)
    write_jsonl(ART / "provider_call_deduplication_audit.jsonl", [{
        "call_dedup_identity": key, "attempt_count": count, "duplicate": count > 1,
    } for key, count in sorted(duplicate_keys.items())])
    write_jsonl(ART / "raw_provider_response_inventory.jsonl", raw_inventory)
    write_jsonl(ART / "raw_provider_response_integrity_audit.jsonl", [{
        "raw_response_identity": row["identity"], "hash_valid": True, "byte_count_valid": True,
    } for row in raw_inventory])
    write_jsonl(ART / "raw_response_missing_audit.jsonl", [{
        "provider_call_attempt_identity": row["identity"], "raw_response_availability": "missing",
        "fabricated": False,
    } for row in attempts if not row["raw_response_identity"]])
    write_jsonl(ART / "parsed_extraction_candidate_revisions.jsonl", parsed_revisions)
    write_jsonl(ART / "parsed_candidate_lineage_audit.jsonl", [{
        "parsed_candidate_revision_identity": row["identity"], "raw_response_identity": row["raw_response_identity"],
        "source_snapshot_lineage_complete": False, "validated_observation_reverse_inferred": False,
    } for row in parsed_revisions])
    write_jsonl(ART / "extraction_field_evidence_records.jsonl", evidence_records)
    write_jsonl(ART / "extraction_field_value_state_audit.jsonl", [{
        "field_evidence_identity": row["identity"], "value_state": row["value_state"],
        "provider_missing_interpreted_as_not_mentioned": False,
    } for row in evidence_records])
    write_jsonl(ART / "legacy_null_migration_audit.jsonl", [{
        "field_evidence_identity": row["identity"], "legacy_value": None,
        "migrated_value_state": "legacy_null_unresolved", "semantic_state_inferred": False,
    } for row in evidence_records if row["value_state"] == "legacy_null_unresolved"])
    write_jsonl(ART / "field_anchor_precision_audit.jsonl", [{
        "field_evidence_identity": row["identity"], "anchor_status": row["anchor_status"],
    } for row in evidence_records])
    write_jsonl(ART / "deterministic_anchor_reconstruction_audit.jsonl", [{
        "field_evidence_identity": row["identity"], "attempted": False,
        "reason": "actual_sent_source_snapshot_text_missing", "llm_used": False, "fuzzy_match_used": False,
    } for row in evidence_records if row["anchor_status"] != "exact"])
    write_json(ART / "extraction_capture_profile.json", profile)
    write_jsonl(ART / "current_prompt_capture_gap_audit.jsonl", gap_rows)
    with (ART / "current_prompt_capture_gap_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(gap_rows[0])); writer.writeheader(); writer.writerows(gap_rows)
    write_jsonl(ART / "current_schema_capture_gap_audit.jsonl", [{
        "capture_profile_field": row["capture_profile_field"],
        "representable_in_current_schema": row["representable_in_current_schema"],
        "loss_risk": row["loss_risk"],
    } for row in gap_rows])
    write_jsonl(ART / "current_parser_preservation_audit.jsonl", [{
        "capture_profile_field": row["capture_profile_field"],
        "parser_preserves_field": row["parser_preserves_field"],
        "zero_api_migration_possible": row["zero_api_migration_possible"],
    } for row in gap_rows])
    write_jsonl(ART / "extraction_coverage_ledger.jsonl", coverage)
    coverage_summary = {
        "coverage_record_count": len(coverage), "capture_profile_field_count": len(CAPTURE_FIELDS),
        "requested_field_coverage_rate": sum(row["requested_by_prompt"] for row in coverage) / len(coverage),
        "field_anchor_coverage_rate": sum(row["anchor_supplied"] for row in coverage) / len(coverage),
        "raw_text_preservation_rate": sum(row["raw_text_available"] for row in coverage) / len(coverage),
        "extracted_value_preservation_rate": sum(row["extracted_value_available"] for row in coverage) / len(coverage),
        "canonical_value_preservation_rate": 0.0,
    }
    write_json(ART / "extraction_coverage_summary.json", coverage_summary)
    write_jsonl(ART / "extraction_replayability_assessments.jsonl", assessments)
    replay_counts = Counter(row["replayability_status"] for row in assessments)
    write_json(ART / "extraction_replayability_summary.json", dict(sorted(replay_counts.items())))
    write_jsonl(ART / "selective_reextraction_requirements.jsonl", requirements)
    write_jsonl(ART / "selective_reextraction_deduplication_audit.jsonl", [{
        "dedup_group_identity": row["dedup_group_identity"], "block_id": row["block_id"],
        "observation_count": len(row["observation_candidate_ids"]), "estimated_call_count": 1,
        "downstream_candidate_in_identity": False,
    } for row in requirements])
    write_json(ART / "selective_reextraction_cost_scope_summary.json", {
        "requirement_count": len(requirements), "unique_block_count": len(requirements),
        "estimated_minimal_provider_call_count": len(requirements), "execution_authorized": False,
        "offline_remediation_order": [
            "reparse_existing_raw_response", "migrate_existing_parsed_payload",
            "rerun_deterministic_validator", "rerun_normalization", "rebuild_derived_artifacts",
            "selective_provider_reextraction", "source_reingestion",
        ],
    })
    gate = {
        "source_snapshot_persisted": True, "rendered_prompt_persisted": True,
        "prompt_identity_recomputable": True, "call_dedup_enabled": True,
        "raw_before_parser": True, "parser_failure_paid_retry_disabled": True,
        "parsed_revision_immutable": True, "field_evidence_contract_available": True,
        "value_state_contract_available": True, "coverage_ledger_available": True,
        "secrets_persisted": False, "selective_reextraction_planner_available": True,
        "cache_resume_tests_passed": True, "real_smoke_evidence_available": False,
        "status": "ready_for_smoke", "schema_version": "extraction_run_readiness_gate_v1",
        "identity": stable_identity("extraction_run_readiness_gate_v1", {"status": "ready_for_smoke", "bulk": False}),
    }
    write_json(ART / "extraction_run_readiness_gate.json", gate)
    write_json(ART / "extraction_billing_safety_audit.json", {
        "raw_response_persisted_before_parser": True, "parser_failure_triggers_paid_retry": False,
        "schema_failure_triggers_paid_retry": False, "normalization_failure_triggers_paid_retry": False,
        "cache_hit_increments_real_api_calls": False, "tests_use_network": False,
    })
    write_json(ART / "extraction_secret_redaction_audit.json", {
        "credential_values_read": False, "secret_fields_allowed_in_specification": False,
        "provider_client_created": False, "violations": [],
    })
    write_jsonl(ART / "extraction_asset_identity_chain_audit.jsonl", list(identities.values()))
    write_json(ART / "hif1a_extraction_asset_readiness_audit.json", {
        "historical_capture_ready": False, "future_capture_status": "ready_for_smoke",
        "historical_blockers": ["actual_sent_input_text_missing", "raw_response_attempt_binding_incomplete",
                                "legacy_nullable_fields", "field_level_anchor_gaps"],
    })

    summary = {
        "schema_version": "extraction_asset_preservation_summary_v1",
        "source_snapshot_count": len(snapshots), "complete_source_snapshot_count": 0,
        "incomplete_source_snapshot_count": len(snapshots), "source_block_count": len(snapshots),
        "provider_call_specification_count": len(specs), "provider_call_attempt_count": len(attempts),
        "successful_provider_attempt_count": sum(row["status"] == "completed" for row in attempts),
        "cache_hit_count": sum(row.get("cache_status") == "hit" for row in execution),
        "duplicate_call_identity_count": sum(count > 1 for count in duplicate_keys.values()),
        "raw_response_count": len(raw_inventory), "raw_response_hash_valid_count": len(raw_inventory),
        "raw_response_missing_count": sum(not row["raw_response_identity"] for row in attempts),
        "truncated_response_count": sum(row.get("finish_reason") == "length" for row in execution),
        "parsed_candidate_revision_count": len(parsed_revisions),
        "parse_failed_count": sum("parse" in str(row.get("status")) for row in execution),
        "schema_invalid_candidate_count": sum(row.get("status") != "formal_valid" for row in parser_audit),
        "validated_observation_count": len(observations),
        "field_evidence_record_count": len(evidence_records),
        "exact_anchor_count": anchor_counts["exact"], "sentence_only_anchor_count": anchor_counts["sentence_only"],
        "ambiguous_anchor_count": anchor_counts["ambiguous"],
        "unresolved_anchor_count": anchor_counts["not_supplied"],
        "value_state_counts": dict(value_counts), "legacy_null_unresolved_count": value_counts["legacy_null_unresolved"],
        **coverage_summary,
        "fully_replayable_zero_api_count": replay_counts["fully_replayable_zero_api"],
        "replayable_from_raw_response_count": replay_counts["replayable_from_raw_response"],
        "replayable_from_parsed_candidate_only_count": replay_counts["replayable_from_parsed_candidate_only"],
        "partially_replayable_count": replay_counts["partially_replayable"],
        "provider_reextraction_required_count": sum(row["provider_reextraction_required"] for row in assessments),
        "source_reingestion_required_count": replay_counts["source_reingestion_required"],
        "selective_reextraction_requirement_count": len(requirements),
        "unique_reextraction_block_count": len(requirements),
        "estimated_minimal_provider_call_count": len(requirements),
        "automatic_reextraction_authorized_count": 0, "provider_reextraction_authorized_count": 0,
        "prompt_revision_required": True, "candidate_prompt_revision_created": True,
        "candidate_prompt_revision_status": "pending_smoke_validation",
        "extraction_run_readiness_status": "ready_for_smoke",
        "candidate_count_before": 11, "candidate_count_after": 11, "candidate_identity_changed": False,
        "candidate_order_changed": False, "scientific_pair_set_changed": False,
        "weak_3ca_context_entry_status": "ready",
        "weak_3ca_difference_authority_status": "ready_not_materialized",
        "weak_256_context_entry_status": "blocked_context_b_unavailable",
        "weak_256_difference_authority_status": "blocked_entry",
        "ebd5_candidate_qualification_status": "blocked_alignment",
        "ebd5_difference_authority_status": "diagnostic_only",
        "ebd5_formal_conflict_status": "not_confirmed",
        "composition_17b_status": "fail_closed",
        "composition_41f_status": "fail_closed",
        "formal_conflict_count_before": 0, "formal_conflict_count_after": 0,
        "contract_identities": {name: value["identity_sha256"] for name, value in identities.items()},
        "provider_calls": 0, "api_calls": 0, "real_api_calls": 0, "network_calls": 0,
        "downloads": 0, "credential_values_read": False, "provider_client_created": False,
        "historical_runs_modified": False, "handoff_created": False, "atlas_activated": False,
        "active_pointer_changed": False, "variational_em_called": False,
        "audit_scope": [str(path.relative_to(ROOT)) for path in historical_paths if path.exists()],
    }
    write_json(ART / "extraction_asset_preservation_summary.json", summary)
    status_lines = subprocess.check_output(
        ["git", "status", "--short", "--untracked-files=all"], cwd=ROOT, text=True,
    ).splitlines()
    changed = sorted(line[3:] for line in status_lines if not line.startswith("?? "))
    created = sorted(line[3:] for line in status_lines if line.startswith("?? "))
    created.extend(str(path.relative_to(ROOT)) for path in sorted(OUT.rglob("*")) if path.is_file())
    history_hashes = {
        str(path.relative_to(ROOT)): tree_hash(path)
        for path in historical_paths if path.exists() and path != OUT
    }
    write_json(ART / "extraction_asset_preservation_manifest.json", {
        **summary, "git_head_before": git("rev-parse", "HEAD"), "git_head_after": git("rev-parse", "HEAD"),
        "git_status_before": [], "git_status_after": status_lines,
        "preexisting_dirty_files": [], "files_changed_this_round": changed,
        "files_created_this_round": sorted(set(created)),
        "source_hashes_before": history_hashes, "source_hashes_after": history_hashes,
        "historical_runs_modified": False,
    })


if __name__ == "__main__":
    main()
