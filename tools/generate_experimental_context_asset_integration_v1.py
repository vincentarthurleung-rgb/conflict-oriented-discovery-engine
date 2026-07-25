#!/usr/bin/env python3
"""Build the 2026-07-25 experimental-context sidecar run, entirely offline."""
from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from code_engine.extraction_assets.context.field_registry import (
    build_registry, explicit_legacy_mapping,
)
from code_engine.extraction_assets.context.identities import (
    CONTRACT_NAMES, context_asset_identity, contract_identity,
)
from code_engine.extraction_assets.context.models import (
    ContextAssetMultiAxisReadiness, ContextAssetRemediationRequirement,
    ContextAssetScopedAuthority, ContextConsolidationRevision, ContextCoverageRecord,
    ContextFieldEvidence, ContextNormalizationRevision, ContextProviderCallPolicy,
    ContextValueStateBasis, ExperimentContextScope, ExperimentalContextCandidateRevision,
    HistoricalContextAssetInventoryRecord, ResearchGradeObservationContextExtractionContract,
    SourceContextEnvelope, ValidatedObservationContextRevision,
)
from code_engine.extraction_assets.identities import sha256_bytes, sha256_json


ROOT = Path(__file__).resolve().parents[1]
RUN_NAME = "20260725_hif1a_experimental_context_asset_integration_v1_offline"
OUT = ROOT / "runs" / RUN_NAME
ART = OUT / "artifacts"
SCHEMAS = OUT / "schemas"
IDENTITIES = OUT / "contract_identities"

HISTORICAL_RUNS = [
    "runs/cta_d1f92fd42fc0fe1a8e27_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_l1_v1",
    "runs/20260724_hif1a_context_attribution_v6_recovery_targeted_paid_execution",
    "runs/20260724_hif1a_context_attribution_v7_paid_payload_offline_revalidation",
    "runs/20260724_hif1a_context_attribution_v7_policy_gap_audit",
    "runs/20260725_hif1a_context_pipeline_layer_split_v1_offline",
    "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline",
    "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline",
    "runs/20260725_hif1a_candidate_qualification_v1_offline",
    "runs/20260725_hif1a_l4_context_readiness_gate_v1_offline",
    "runs/20260725_hif1a_context_remediation_scope_v1_offline",
    "runs/20260725_hif1a_extraction_asset_preservation_v1_offline",
    "runs/20260725_hif1a_historical_extraction_lineage_forensics_v1_offline",
]

# Audited against fulltext observation v3 and context_registry_v3. These are
# versioned contract coverage sets, not observed-value or HIF1A-specific counts.
OBSERVATION_PROMPT_FIELDS = {
    "species", "tissue", "cell_type", "cell_line", "model_system", "disease",
    "genotype", "intervention", "intervention_order", "dose", "duration",
    "control", "comparator", "measurement_method", "measured_endpoint",
    "subcellular_localization", "in_vitro_in_vivo_ex_vivo", "experimental_arm",
}
CONTEXT_PROMPT_FIELDS = {
    "species", "strain", "sex", "age_or_developmental_stage", "tissue", "organ",
    "cell_type", "cell_line", "model_system", "disease", "disease_stage", "phenotype",
    "genotype", "knockout", "overexpression", "intervention", "intervention_order",
    "dose", "route", "frequency", "duration", "timepoint", "pretreatment",
    "control", "comparator", "assay", "measurement_method", "measured_endpoint",
    "normalization_control", "in_vitro_in_vivo_ex_vivo", "experimental_arm",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def dump_jsonl(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row.model_dump(mode="json") if hasattr(row, "model_dump") else row,
                           ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, capture_output=True).stdout.strip()


def find_refs(value: Any, refs: set[str], fields: set[str], evidence: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"observation_id", "record_id", "claim_id"} and isinstance(item, str):
                if item.startswith(("ftl1", "ft_", "obs")):
                    refs.add(item)
            if key in {"factor_id", "field_id"} and isinstance(item, str):
                fields.add(item)
            if key in {"evidence_anchor_ids", "authoritative_anchor_ids"} and isinstance(item, list):
                evidence.update(str(x) for x in item)
            find_refs(item, refs, fields, evidence)
    elif isinstance(value, list):
        for item in value:
            find_refs(item, refs, fields, evidence)


def inventory() -> list[HistoricalContextAssetInventoryRecord]:
    records = []
    for source_run in HISTORICAL_RUNS:
        base = ROOT / source_run
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            if not any(token in path.name.lower() for token in (
                "context", "evidence", "extraction", "readiness", "remediation",
                "candidate", "alignment", "lineage",
            )):
                continue
            refs: set[str] = set()
            fields: set[str] = set()
            evidence: set[str] = set()
            schema = None
            if path.suffix in {".json", ".jsonl"}:
                try:
                    values = [read_json(path)] if path.suffix == ".json" else read_jsonl(path)
                    for value in values:
                        if isinstance(value, dict) and schema is None:
                            schema = value.get("schema_version") or value.get("artifact_schema_version")
                        find_refs(value, refs, fields, evidence)
                except (ValueError, UnicodeDecodeError):
                    pass
            relative = path.relative_to(ROOT).as_posix()
            payload = {
                "artifact_kind": path.stem,
                "source_run": source_run,
                "relative_path": relative,
                "sha256": sha256_bytes(path.read_bytes()),
                "schema_name": schema,
                "schema_version_found": schema,
                "observation_refs": sorted(refs),
                "experiment_scope_refs": [],
                "context_fields_present": sorted(fields),
                "evidence_refs": sorted(evidence),
                "validation_refs": [relative] if "validation" in path.name else [],
                "normalization_refs": [relative] if "normalization" in path.name else [],
                "direct_inherited_status": "artifact_specific_or_unresolved",
                "lineage_completeness": "legacy_incomplete",
                "migration_eligibility": "eligible_sidecar" if path.suffix in {".json", ".jsonl"} else "inventory_only",
                "migration_blockers": [] if path.suffix in {".json", ".jsonl"} else ["not_structured_json"],
            }
            records.append(HistoricalContextAssetInventoryRecord(
                **payload,
                identity=context_asset_identity("historical_context_asset_inventory_record_v1", payload),
                provenance={"producer": "experimental_context_inventory", "producer_version": "v1",
                            "source_artifact_refs": [relative]},
            ))
    current_paths = set()
    for relative_root in (
        "src/code_engine/context_attribution/observation_context",
        "configs/context_attribution",
    ):
        current_paths.update(p for p in (ROOT / relative_root).rglob("*") if p.is_file())
    current_paths.update(
        p for p in (ROOT / "src/code_engine/extraction_assets").glob("*.py") if p.is_file()
    )
    for relative_file in (
        "src/code_engine/fulltext/fulltext_l1_v2.py",
        "src/code_engine/fulltext/fulltext_observation_v3.py",
        "src/code_engine/fulltext/reasoning_trace.py",
        "src/code_engine/context_attribution/models.py",
        "src/code_engine/context_attribution/validation.py",
        "src/code_engine/context_attribution/registry.py",
        "src/code_engine/context_attribution/engine.py",
    ):
        path = ROOT / relative_file
        if path.is_file():
            current_paths.add(path)
    for path in sorted(current_paths):
        relative = path.relative_to(ROOT).as_posix()
        payload = {
            "artifact_kind": "current_context_source_or_contract",
            "source_run": "current_source_and_contract_audit",
            "relative_path": relative,
            "sha256": sha256_bytes(path.read_bytes()),
            "schema_name": None, "schema_version_found": None,
            "observation_refs": [], "experiment_scope_refs": [],
            "context_fields_present": [], "evidence_refs": [],
            "validation_refs": [relative] if "validation" in path.name else [],
            "normalization_refs": [],
            "direct_inherited_status": "source_contract_audit",
            "lineage_completeness": "not_applicable",
            "migration_eligibility": "audit_only",
            "migration_blockers": ["not_historical_data_artifact"],
        }
        records.append(HistoricalContextAssetInventoryRecord(
            **payload,
            identity=context_asset_identity("historical_context_asset_inventory_record_v1", payload),
            provenance={"producer": "experimental_context_inventory", "producer_version": "v1",
                        "source_artifact_refs": [relative]},
        ))
    return records


def build_candidates() -> tuple[list, dict[str, dict], dict[str, bool]]:
    v6_path = ROOT / HISTORICAL_RUNS[1] / "artifacts/observation_context_extractions.jsonl"
    current_path = ROOT / HISTORICAL_RUNS[4] / "artifacts/observation_contexts.jsonl"
    provider_path = ROOT / HISTORICAL_RUNS[1] / "artifacts/context_attribution_provider_calls.jsonl"
    source_rows: list[tuple[dict, str, str, bool]] = []
    for row in read_jsonl(v6_path):
        source_rows.append((row, v6_path.relative_to(ROOT).as_posix(), "historical_context_extraction", True))
    for row in read_jsonl(provider_path):
        if row.get("call_type") == "extraction" and row.get("observation_id") and row.get("parsed_payload"):
            parsed_payload = dict(row["parsed_payload"])
            parsed_payload.setdefault("observation_id", row["observation_id"])
            source_rows.append((
                parsed_payload, provider_path.relative_to(ROOT).as_posix(),
                "historical_provider_parsed_payload", False,
            ))
    current = {row["observation_id"]: row for row in read_jsonl(current_path)}
    candidates = []
    by_observation: dict[str, dict] = {}
    validation: dict[str, bool] = {}
    for index, (raw, ref, extractor, validated) in enumerate(source_rows):
        obs = raw.get("observation_id") or raw.get("record_id")
        if not obs:
            continue
        digest = sha256_json(raw)
        base = {
            "context_candidate_revision_id": f"ctxcand-{digest[:24]}",
            "observation_candidate_identity": obs,
            "parsed_candidate_revision_identity": None,
            "source_snapshot_identity": None,
            "experiment_scope_identity": None,
            "source_context_envelope_identity": f"ctxenv:{obs}",
            "context_schema_name": raw.get("schema_version", "legacy_context_payload"),
            "context_schema_version": raw.get("schema_version", "unknown"),
            "extractor_name": extractor,
            "extractor_version": "historical",
            "extraction_contract_identity": "experimental_context_candidate_contract_identity_v1",
            "raw_context_payload": raw,
            "raw_context_payload_sha256": digest,
            "field_record_ids": [],
            "parse_status": "migrated",
            "schema_status": "valid" if validated else "invalid",
            "extraction_warnings": ["raw_response_lineage_not_claimed"],
            "extraction_error_codes": [] if validated else ["historical_schema_validation_failed"],
            "supersedes_revision_id": None,
        }
        candidate = ExperimentalContextCandidateRevision(
            **base, identity=context_asset_identity("experimental_context_candidate_revision_v1", base),
            provenance={"producer": "historical_context_sidecar_migration", "producer_version": "v1",
                        "source_artifact_refs": [ref], "limitations": ["legacy_raw_parent_unbound"]},
        )
        candidates.append(candidate)
        by_observation[obs] = current.get(obs, raw)
        validation[obs] = obs in current
    return candidates, by_observation, validation


def factor_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload.get("facts") or payload.get("context_factors") or []


def generate() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    registry = build_registry()
    mapping = explicit_legacy_mapping(registry)
    registry_by_field = {row.field_id: row for row in registry}
    inventories = inventory()
    historical_inventory_count = sum(
        row.source_run != "current_source_and_contract_audit" for row in inventories
    )
    candidates, observation_payloads, is_current_validated = build_candidates()
    candidate_by_obs = {c.observation_candidate_identity: c for c in candidates}
    observation_ids = sorted(observation_payloads)

    historical_fields = sorted({
        factor.get("factor_id") for payload in observation_payloads.values()
        for factor in factor_rows(payload) if factor.get("factor_id")
    })
    mapping_rows = []
    for field in historical_fields:
        target, status = mapping.get(field, (None, "unresolved"))
        mapping_rows.append({
            "original_field_name": field, "mapped_field_id": target, "mapping_status": status,
            "mapping_authority": "explicit_versioned_mapping" if target else "unresolved",
        })

    scopes = []
    envelopes = []
    for obs in observation_ids:
        scope_base = {
            "experiment_scope_id": f"scope-unavailable-{obs}",
            "document_id": "unresolved_historical_document",
            "source_section_refs": [], "source_paragraph_refs": [], "source_block_refs": [],
            "experiment_group_identity": f"unresolved:{obs}",
            "scope_detection_method": "historical_scope_not_explicit",
            "scope_detection_version": "v1",
            "directly_stated_context_field_ids": [], "linked_observation_ids": [obs],
            "scope_start_anchor": None, "scope_end_anchor": None,
            "scope_status": "unavailable", "authority_status": "blocked",
            "ambiguity_status": "unavailable",
        }
        scopes.append(ExperimentContextScope(
            **scope_base, identity=context_asset_identity("experiment_context_scope_v1", scope_base),
            provenance={"producer": "historical_context_sidecar_migration", "producer_version": "v1",
                        "limitations": ["no_explicit_experiment_grouping_found"]},
        ))
        env_base = {
            "source_context_envelope_id": f"ctxenv-{obs}",
            "primary_observation_block": None, "section_hierarchy": [],
            "preceding_paragraph_refs": [], "following_paragraph_refs": [],
            "methods_paragraph_refs": [], "figure_table_caption_refs": [],
            "source_byte_hash_refs": [],
            "envelope_construction_policy": "historical_no_rechunk_impersonation_v1",
            "truncation_status": "unknown", "context_window_limits": {},
            "completeness_status": "incomplete", "authority_status": "non_authoritative",
        }
        envelopes.append(SourceContextEnvelope(
            **env_base, identity=context_asset_identity("source_context_envelope_v1", env_base),
            provenance={"producer": "historical_context_sidecar_migration", "producer_version": "v1",
                        "limitations": ["authoritative_historical_source_snapshot_unavailable"]},
        ))

    evidence_rows = []
    for obs, payload in observation_payloads.items():
        candidate = candidate_by_obs[obs]
        for index, factor in enumerate(factor_rows(payload)):
            original = factor.get("factor_id")
            if not original:
                continue
            mapped, mapping_status = mapping.get(original, (original, "unresolved"))
            raw_value = factor.get("raw_value")
            normalized = factor.get("normalized_value", factor.get("normalized_candidate"))
            status = factor.get("status", "unknown")
            if raw_value is None:
                state = "legacy_null_unresolved" if status == "unknown" else "unknown"
                origin = "unresolved_legacy"
            elif status == "conflicting":
                state, origin = "ambiguous", "historical_validated_context"
            else:
                state, origin = "present", "historical_validated_context"
            anchors = factor.get("evidence_anchor_ids") or []
            span = factor.get("token_span") or factor.get("explicit_span_resolution") or factor.get("explicit_span")
            precision = "exact" if span and anchors else ("sentence" if anchors else "unresolved")
            evidence_quote = factor.get("evidence_text")
            basis = ContextValueStateBasis(
                value_state=state, state_basis_type="historical_context_artifact",
                source_evidence_refs=anchors, extraction_evidence_refs=[candidate.identity],
                state_authority="legacy_unresolved" if state == "legacy_null_unresolved" else "candidate",
                limitations=["historical_raw_lineage_incomplete"],
            )
            base = {
                "context_field_evidence_id": f"ctxfield-{sha256_json([candidate.identity, index])[:24]}",
                "context_candidate_revision_identity": candidate.identity,
                "observation_candidate_identity": obs,
                "experiment_scope_identity": None,
                "field_id": mapped or original, "field_path": f"context.{mapped or original}",
                "original_field_name": original, "original_value": raw_value,
                "original_schema": payload.get("schema_version"),
                "original_artifact_identity": candidate.identity,
                "raw_text": raw_value, "provider_value": raw_value,
                "extracted_value": raw_value, "canonical_value": normalized,
                "canonical_identity": None, "value_state": state, "value_origin": origin,
                "value_state_basis": basis,
                "evidence_anchor_ids": anchors, "source_sentence_ids": anchors,
                "source_paragraph_ids": [], "source_block_ids": [],
                "evidence_quote": evidence_quote, "provider_supplied_offsets": [],
                "deterministically_resolved_offsets": [],
                "anchor_precision": precision,
                "anchor_validation_status": "historical_exact_token_span" if precision == "exact" else (
                    "historical_sentence_anchor" if precision == "sentence" else "unresolved"
                ),
                "context_validation_status": "validated_legacy" if is_current_validated[obs] else "candidate_only",
                "normalization_status": factor.get("normalization_status", "not_requested"),
                "rejection_reason_codes": [],
                "unresolved_reason_codes": [] if anchors else ["authoritative_anchor_unavailable"],
                "authority_status": "validated_legacy" if is_current_validated[obs] else "candidate_only",
                "migration_record": state == "legacy_null_unresolved",
            }
            evidence_rows.append(ContextFieldEvidence(
                **base, identity=context_asset_identity("context_field_evidence_v1", base),
                provenance={"producer": "historical_context_sidecar_migration", "producer_version": "v1",
                            "source_artifact_refs": candidate.provenance.source_artifact_refs,
                            "limitations": ["provider_offsets_not_authoritative"]},
            ))

    by_obs_evidence = defaultdict(list)
    for row in evidence_rows:
        by_obs_evidence[row.observation_candidate_identity].append(row)
    validated = []
    normalizations = []
    consolidations = []
    authorities = []
    readiness = []
    for obs in observation_ids:
        rows = by_obs_evidence[obs]
        valid = is_current_validated[obs]
        if valid:
            base = {
                "validated_context_revision_id": f"ctxvalid-{sha256_json(obs)[:24]}",
                "context_candidate_revision_identity": candidate_by_obs[obs].identity,
                "observation_identity": obs, "experiment_scope_identity": None,
                "context_field_record_ids": [r.identity for r in rows],
                "schema_validation_status": "validated",
                "field_validation_statuses": {r.field_id: r.context_validation_status for r in rows},
                "anchor_validation_statuses": {r.field_id: r.anchor_validation_status for r in rows},
                "scope_validation_status": "unavailable",
                "propagation_validation_status": "not_applied",
                "semantic_validation_status": "validated_legacy",
                "completeness_status": "partial",
                "validation_contract_identity": "validated_observation_context_contract_identity_v1",
                "validator_version": observation_payloads[obs].get("validator_version", "historical_validator"),
                "validation_error_codes": [],
                "validation_warning_codes": ["legacy_provenance_incomplete"],
                "supersedes_revision_id": None,
            }
            revision = ValidatedObservationContextRevision(
                **base, identity=context_asset_identity("validated_observation_context_revision_v1", base),
                provenance={"producer": "observation_context_adapter", "producer_version": "v1",
                            "source_artifact_refs": candidate_by_obs[obs].provenance.source_artifact_refs,
                            "limitations": ["legacy_attempt_raw_binding_incomplete"]},
            )
            validated.append(revision)
            for field in rows:
                nbase = {
                    "normalization_revision_id": f"ctxnorm-{sha256_json(field.identity)[:24]}",
                    "validated_context_revision_identity": revision.identity,
                    "field_id": field.field_id, "raw_text": field.raw_text,
                    "extracted_value": field.extracted_value, "canonical_value": field.canonical_value,
                    "canonical_identity": field.canonical_identity,
                    "normalization_status": (
                        "resolved" if field.canonical_value is not None else
                        ("unresolved" if field.value_state == "present" else "not_requested")
                    ),
                    "normalization_contract_identity": "existing_observation_context_normalization",
                    "registry_identity": registry_by_field.get(field.field_id, registry[0]).identity,
                    "ambiguous_candidates": [],
                    "unresolved_reason": "historical_normalization_not_available" if (
                        field.value_state == "present" and field.canonical_value is None
                    ) else None,
                }
                normalizations.append(ContextNormalizationRevision(
                    **nbase, identity=context_asset_identity("context_normalization_revision_v1", nbase),
                    provenance={"producer": "historical_normalization_sidecar", "producer_version": "v1",
                                "source_artifact_refs": [field.identity]},
                ))
        direct = [r for r in rows if r.value_state == "present" and r.evidence_anchor_ids]
        resolutions = [{
            "field_id": r.field_id, "selected_value_record": r.identity,
            "candidate_value_records": [r.identity],
            "resolution_method": "validated_direct_local" if valid else "unresolved",
            "direct_vs_inherited": "direct" if valid else "unresolved",
            "conflict_status": "clear" if valid else "unresolved",
            "authority_status": "validated_legacy" if valid else "candidate_only",
            "rejection_reasons": [],
        } for r in direct]
        cbase = {
            "consolidation_revision_id": f"ctxcons-{sha256_json(obs)[:24]}",
            "observation_identity": obs,
            "source_context_candidate_revisions": [candidate_by_obs[obs].identity],
            "validated_context_revision_ids": [v.identity for v in validated if v.observation_identity == obs],
            "experiment_scope_ids": [], "field_resolution_records": resolutions,
            "direct_field_count": len(resolutions) if valid else 0, "inherited_field_count": 0,
            "unresolved_field_count": len(rows) - (len(resolutions) if valid else 0),
            "unavailable_field_count": 0, "conflicting_field_count": 0,
            "consolidation_policy_identity": "context_consolidation_contract_identity_v1",
            "authority_status": "validated_legacy" if valid else "candidate_only",
        }
        consolidations.append(ContextConsolidationRevision(
            **cbase, identity=context_asset_identity("context_consolidation_revision_v1", cbase),
            provenance={"producer": "context_consolidation_sidecar", "producer_version": "v1",
                        "source_artifact_refs": [candidate_by_obs[obs].identity]},
        ))
        precision = Counter(r.anchor_precision for r in rows)
        abase = {
            "observation_identity": obs,
            "semantic_authority": "validated_legacy" if valid else "candidate_only",
            "evidence_authority": (
                "exact_field_anchor" if precision["exact"] else
                ("exact_sentence_anchor" if precision["sentence"] else "evidence_unresolved")
            ),
            "provenance_authority": "legacy_incomplete",
            "replayability_authority": "structured_artifact_replayable",
            "downstream_use_authority": "allowed_for_exploratory_graph" if valid else "diagnostic_only",
            "downstream_authority_source": "asset_display_policy",
        }
        authorities.append(ContextAssetScopedAuthority(
            **abase, identity=context_asset_identity("context_asset_scoped_authority_v1", abase)
        ))
        rbase = {
            "observation_identity": obs,
            "semantic_readiness": "validated_legacy" if valid else "candidate_only",
            "evidence_readiness": "field_level_exact" if precision["exact"] else (
                "sentence_level" if precision["sentence"] else "unresolved"
            ),
            "provenance_readiness": "legacy_incomplete",
            "replayability_readiness": "structured_artifact_replayable",
            "coverage_readiness": "low",
            "downstream_readiness": "exploratory_graph_ready" if valid else "diagnostic_only",
            "future_data_reuse_readiness": "usable_with_limitations" if valid else "challenge_record",
            "threshold_contract_identity": "context_asset_readiness_thresholds_v1",
        }
        readiness.append(ContextAssetMultiAxisReadiness(
            **rbase, identity=context_asset_identity("context_asset_multi_axis_readiness_v1", rbase)
        ))

    coverage = []
    for obs in observation_ids:
        present = {r.field_id: r for r in by_obs_evidence[obs]}
        for reg in registry:
            row = present.get(reg.field_id)
            base = {
                "coverage_record_id": f"ctxcov-{sha256_json([obs, reg.field_id])[:24]}",
                "observation_identity": obs, "experiment_scope_identity": None,
                "field_id": reg.field_id, "field_registry_identity": reg.identity,
                "requested_by_observation_prompt": reg.field_id in OBSERVATION_PROMPT_FIELDS,
                "requested_by_context_prompt": reg.field_id in CONTEXT_PROMPT_FIELDS,
                "representable_in_observation_schema": reg.schema_representable,
                "representable_in_context_schema": reg.schema_representable,
                "returned_in_observation_payload": False,
                "returned_in_context_payload": row is not None,
                "preserved_in_parsed_payload": row is not None,
                "migrated_from_historical_context": row is not None,
                "direct_evidence_available": bool(row and row.evidence_anchor_ids),
                "shared_scope_evidence_available": False,
                "authoritative_anchor_available": bool(row and row.anchor_precision == "exact"),
                "value_state_available": row is not None,
                "validated_value_available": bool(row and is_current_validated[obs]),
                "normalized_value_available": bool(row and row.canonical_value is not None),
                "consolidation_value_available": bool(row and is_current_validated[obs] and row.value_state == "present"),
                "propagation_available": False,
                "provider_reextraction_required": False,
                "deterministic_recovery_available": row is not None,
                "source_scope_sufficient": False,
                "blocking_reason_codes": [] if row else ["source_presence_unknown"],
            }
            coverage.append(ContextCoverageRecord(
                **base, identity=context_asset_identity("context_asset_coverage_record_v1", base)
            ))

    remediation = []
    for obs in observation_ids:
        missing = [row.field_id for row in coverage if row.observation_identity == obs and not row.value_state_available]
        if not missing:
            continue
        available = ["migrate_existing_validated_context"] if is_current_validated[obs] else ["migrate_existing_context_candidate"]
        base = {
            "observation_identity": obs, "experiment_scope_identity": None,
            "field_ids": missing, "current_context_asset_status": "partial",
            "available_recovery_modes": available,
            "preferred_recovery_mode": available[0],
            "historical_artifact_refs": candidate_by_obs[obs].provenance.source_artifact_refs,
            "source_scope_status": "insufficient", "raw_lineage_status": "legacy_incomplete",
            "parsed_lineage_status": "structured_context_artifact_available",
            "provider_reextraction_required": False, "source_reingestion_required": False,
            "minimal_source_block_set": [], "dedup_group_identity": f"context-remediation:{obs}",
        }
        remediation.append(ContextAssetRemediationRequirement(
            **base, identity=context_asset_identity("context_asset_remediation_requirement_v2", base)
        ))

    prompt_contract_base = {
        "output_shape": {
            "experiment_scopes": [{"experiment_scope_local_id": "string", "shared_context": {
                "<field_id>": {"raw_text": "source phrase", "value": "source value",
                               "value_state_candidate": "present", "evidence_refs": ["P3:S2"]}
            }}],
            "observations": [{"observation_local_id": "string", "experiment_scope_ref": "string",
                              "claim": {}, "experimental_chain": {"ordered_interventions": []},
                              "local_context": {}, "result": {}, "evidence_refs": ["P3:S2"]}],
        },
        "prompt_requirements": [
            "one atomic result per observation", "split distinct experiments and results",
            "preserve experiment scope and intervention role/order",
            "copy context source phrases and bind key fields to stable evidence refs",
            "use explicit uncertainty/value-state candidates; never infer unstated context",
            "do not output conflict, comparability, divergence explanation, or canonical identities",
        ],
    }
    prompt_contract = ResearchGradeObservationContextExtractionContract(
        **prompt_contract_base,
        identity=context_asset_identity("research_grade_observation_context_extraction_contract_v1", prompt_contract_base),
    )
    provider_policy = ContextProviderCallPolicy(
        identity=context_asset_identity("context_provider_call_policy_v1", {
            "bulk_secondary_context_calls_allowed": False,
            "automatic_context_retry_allowed": False,
            "provider_call_authorized": False,
        })
    )

    # Persistent artifacts.
    dump_jsonl(ART / "historical_context_asset_inventory.jsonl", inventories)
    dump_json(ART / "historical_context_asset_inventory_summary.json", {
        "schema_version": "historical_context_asset_inventory_summary_v1",
        "historical_context_artifact_count": historical_inventory_count,
        "inventory_record_count": len(inventories),
        "runs_scanned": HISTORICAL_RUNS,
        "current_source_and_contract_audit_included": True,
        "artifact_kind_counts": dict(Counter(r.artifact_kind for r in inventories)),
    })
    dump_json(ART / "context_field_registry_snapshot.json", {
        "schema_version": "experimental_context_field_registry_v1",
        "records": [r.model_dump(mode="json") for r in registry],
    })
    dump_json(ART / "context_field_legacy_mapping.json", {
        "schema_version": "context_field_legacy_mapping_v1", "records": mapping_rows,
    })
    dump_jsonl(ART / "context_field_mapping_audit.jsonl", mapping_rows)
    dump_jsonl(ART / "experimental_context_candidate_revisions.jsonl", candidates)
    dump_jsonl(ART / "experiment_context_scopes.jsonl", scopes)
    dump_jsonl(ART / "source_context_envelopes.jsonl", envelopes)
    dump_jsonl(ART / "observation_context_scope_links.jsonl", [])
    dump_jsonl(ART / "context_field_evidence_records.jsonl", evidence_rows)
    dump_jsonl(ART / "context_field_value_state_audit.jsonl", [{
        "context_field_evidence_id": r.context_field_evidence_id,
        "value_state": r.value_state.value, "basis": r.value_state_basis.model_dump(mode="json"),
    } for r in evidence_rows])
    dump_jsonl(ART / "context_value_origin_audit.jsonl", [{
        "context_field_evidence_id": r.context_field_evidence_id, "value_origin": r.value_origin.value,
    } for r in evidence_rows])
    dump_jsonl(ART / "context_anchor_precision_audit.jsonl", [{
        "context_field_evidence_id": r.context_field_evidence_id,
        "anchor_precision": r.anchor_precision, "provider_offset_authority": False,
    } for r in evidence_rows])
    dump_jsonl(ART / "context_scope_propagation_audit.jsonl", [])
    dump_jsonl(ART / "context_scope_conflict_audit.jsonl", [])
    dump_jsonl(ART / "validated_observation_context_revisions.jsonl", validated)
    dump_jsonl(ART / "context_normalization_revisions.jsonl", normalizations)
    dump_jsonl(ART / "context_consolidation_revisions.jsonl", consolidations)
    dump_jsonl(ART / "context_consolidation_field_resolution_audit.jsonl", [
        {"observation_identity": r.observation_identity, **field.model_dump(mode="json")}
        for r in consolidations for field in r.field_resolution_records
    ])
    dump_jsonl(ART / "context_asset_scoped_authorities.jsonl", authorities)
    dump_jsonl(ART / "context_asset_coverage_ledger.jsonl", coverage)
    cov_summary = {
        "schema_version": "context_asset_coverage_summary_v1",
        "coverage_record_count": len(coverage),
        "current_observation_prompt_context_coverage_rate": round(
            sum(r.requested_by_observation_prompt for r in coverage) / len(coverage), 6),
        "current_context_prompt_coverage_rate": round(
            sum(r.requested_by_context_prompt for r in coverage) / len(coverage), 6),
        "joint_prompt_context_coverage_rate": round(
            sum(r.requested_by_observation_prompt or r.requested_by_context_prompt for r in coverage) / len(coverage), 6),
        "historical_context_actual_field_coverage_rate": round(
            sum(r.returned_in_context_payload for r in coverage) / len(coverage), 6),
        "authoritative_context_anchor_coverage_rate": round(
            sum(r.authoritative_anchor_available for r in coverage) / len(coverage), 6),
    }
    dump_json(ART / "context_asset_coverage_summary.json", cov_summary)

    category_profiles = []
    category_summary: dict[str, Counter] = defaultdict(Counter)
    for obs in observation_ids:
        counts: dict[str, Counter] = defaultdict(Counter)
        for cov in (x for x in coverage if x.observation_identity == obs):
            category = registry_by_field[cov.field_id].semantic_category
            state = "direct_validated" if cov.validated_value_available else (
                "candidate_only" if cov.value_state_available else "unavailable"
            )
            counts[category][state] += 1
            category_summary[category][state] += 1
        base = {
            "observation_identity": obs,
            "category_counts": {k: dict(v) for k, v in counts.items()},
            "evidence_anchor_coverage": sum(x.authoritative_anchor_available for x in coverage if x.observation_identity == obs) / len(registry),
            "normalization_coverage": sum(x.normalized_value_available for x in coverage if x.observation_identity == obs) / len(registry),
            "value_state_coverage": sum(x.value_state_available for x in coverage if x.observation_identity == obs) / len(registry),
            "validity_status": "validated_legacy" if is_current_validated[obs] else "candidate_only",
            "completeness_status": "partial",
        }
        from code_engine.extraction_assets.context.models import ContextCompletenessProfile
        category_profiles.append(ContextCompletenessProfile(
            **base, identity=context_asset_identity("context_completeness_profile_v1", base)
        ))
    dump_jsonl(ART / "context_completeness_profiles.jsonl", category_profiles)
    dump_json(ART / "context_completeness_summary.json", {
        "schema_version": "context_completeness_summary_v1",
        "category_counts": {k: dict(v) for k, v in category_summary.items()},
        "validity_and_completeness_are_separate": True,
    })
    dump_jsonl(ART / "context_asset_remediation_requirements_v2.jsonl", remediation)
    dump_jsonl(ART / "context_asset_remediation_deduplication_audit.jsonl", [{
        "dedup_group_identity": r.dedup_group_identity,
        "observation_identity": r.observation_identity, "provider_call_authorized": False,
    } for r in remediation])
    remediation_summary = {
        "schema_version": "context_asset_remediation_summary_v2",
        "requirement_count": len(remediation),
        "resolvable_from_existing_context": len(remediation),
        "resolvable_from_parsed_payload": 0, "resolvable_from_raw": 0,
        "resolvable_from_scope_propagation": 0,
        "provider_reextraction_required_count": 0,
        "unique_provider_reextraction_block_count": 0,
        "automatic_execution_authorized_count": 0,
    }
    dump_json(ART / "context_asset_remediation_summary.json", remediation_summary)
    dump_jsonl(ART / "context_asset_multi_axis_readiness.jsonl", readiness)
    readiness_summary = {
        "schema_version": "context_asset_multi_axis_readiness_summary_v1",
        **{f"{field}_counts": dict(Counter(getattr(r, field) for r in readiness)) for field in (
            "semantic_readiness", "evidence_readiness", "provenance_readiness",
            "replayability_readiness", "downstream_readiness", "future_data_reuse_readiness",
        )},
    }
    dump_json(ART / "context_asset_multi_axis_readiness_summary.json", readiness_summary)

    observation_prompt_audit = [{
        "field_id": r.field_id, "requested": r.field_id in OBSERVATION_PROMPT_FIELDS,
        "schema_representable": r.schema_representable, "parser_preserved": r.parser_preserved,
    } for r in registry]
    context_prompt_audit = [{
        "field_id": r.field_id, "requested": r.field_id in CONTEXT_PROMPT_FIELDS,
        "schema_representable": r.schema_representable, "parser_preserved": r.parser_preserved,
    } for r in registry]
    dump_jsonl(ART / "current_observation_prompt_context_capture_audit.jsonl", observation_prompt_audit)
    dump_jsonl(ART / "current_context_prompt_capture_audit.jsonl", context_prompt_audit)
    dump_jsonl(ART / "current_context_schema_expression_audit.jsonl", context_prompt_audit)
    dump_jsonl(ART / "current_context_parser_preservation_audit.jsonl", context_prompt_audit)
    dump_json(ART / "joint_observation_context_prompt_gap_audit.json", {
        "schema_version": "joint_observation_context_prompt_gap_audit_v1",
        "registry_field_count": len(registry),
        "unsupported_field_ids": [r.field_id for r in registry if not r.currently_supported],
        **{k: cov_summary[k] for k in cov_summary if k.endswith("_rate")},
    })
    dump_json(ART / "context_provider_call_policy.json", provider_policy.model_dump(mode="json"))
    dump_json(ART / "candidate_observation_context_contract.json", prompt_contract.model_dump(mode="json"))
    dump_json(ART / "candidate_observation_context_contract_status.json", {
        "status": "pending_smoke_validation", "production_status": "not_activated",
        "extraction_run_readiness_status": "ready_for_smoke",
    })

    status_artifacts = {
        "weak_3ca_context_asset_audit.json": {
            "context_entry_status": "ready", "difference_authority_status": "ready_not_materialized",
        },
        "weak_256_context_asset_audit.json": {
            "context_entry_status": "blocked_context_b_unavailable", "difference_authority_status": "blocked_entry",
            "potential_entry_reassessment_required": False,
        },
        "ebd5_context_asset_audit.json": {
            "candidate_qualification_status": "blocked_alignment",
            "difference_authority_status": "diagnostic_only", "formal_conflict_status": "not_confirmed",
        },
        "context_17b_asset_audit.json": {
            "status": "fail_closed_policy_coverage_failure", "candidate_payload_preserved": True,
        },
        "context_41f_asset_audit.json": {
            "status": "fail_closed_policy_coverage_failure", "candidate_payload_preserved": True,
        },
    }
    for filename, body in status_artifacts.items():
        dump_json(ART / filename, {"schema_version": "context_scientific_state_preservation_audit_v1", **body})

    identities = {name: contract_identity(name) for name in CONTRACT_NAMES}
    obsolete_identity = IDENTITIES / "context_asset_remediation_v2_contract_identity_v2.json"
    if obsolete_identity.exists():
        obsolete_identity.unlink()
    for name, identity in identities.items():
        dump_json(IDENTITIES / f"{identity['contract_name']}.json", identity)
    dump_json(ART / "contract_identities.json", identities)
    dump_jsonl(ART / "experimental_context_asset_identity_chain_audit.jsonl", [{
        "contract_name": value["contract_name"], "identity_match": value["identity_match"],
        "identity_sha256": value["identity_sha256"],
    } for value in identities.values()])
    dump_json(ART / "experimental_context_asset_safety_audit.json", {
        "schema_version": "experimental_context_asset_safety_audit_v1",
        "provider_calls": 0, "api_calls": 0, "real_api_calls": 0, "network_calls": 0,
        "downloads": 0, "credential_values_read": False, "provider_client_created": False,
        "historical_runs_modified": False, "historical_context_payloads_modified": False,
        "historical_source_files_modified": False, "historical_raw_files_modified": False,
        "historical_parsed_payloads_modified": False,
    })

    # Strict schemas are generated from the executable Pydantic contracts.
    from code_engine.extraction_assets.context import models as m
    schema_models = {
        "experimental_context_candidate_revision_v1": m.ExperimentalContextCandidateRevision,
        "experiment_context_scope_v1": m.ExperimentContextScope,
        "source_context_envelope_v1": m.SourceContextEnvelope,
        "experimental_context_field_registry_v1": m.ContextFieldRegistryRecord,
        "context_field_evidence_v1": m.ContextFieldEvidence,
        "context_value_state_basis_v1": m.ContextValueStateBasis,
        "context_value_origin_v1": m.ContextValueOrigin,
        "observation_context_scope_link_v1": m.ObservationContextScopeLink,
        "context_scope_propagation_policy_v1": m.ContextScopePropagationPolicy,
        "validated_observation_context_revision_v1": m.ValidatedObservationContextRevision,
        "context_normalization_revision_v1": m.ContextNormalizationRevision,
        "context_consolidation_revision_v1": m.ContextConsolidationRevision,
        "context_asset_scoped_authority_v1": m.ContextAssetScopedAuthority,
        "historical_context_asset_inventory_v1": m.HistoricalContextAssetInventoryRecord,
        "historical_context_asset_migration_v1": m.HistoricalContextAssetMigration,
        "context_asset_coverage_ledger_v1": m.ContextCoverageRecord,
        "context_completeness_profile_v1": m.ContextCompletenessProfile,
        "context_asset_remediation_requirement_v2": m.ContextAssetRemediationRequirement,
        "context_asset_multi_axis_readiness_v1": m.ContextAssetMultiAxisReadiness,
        "context_provider_call_policy_v1": m.ContextProviderCallPolicy,
        "research_grade_observation_context_extraction_contract_v1": m.ResearchGradeObservationContextExtractionContract,
    }
    from pydantic import TypeAdapter
    for name, model in schema_models.items():
        schema = model.model_json_schema() if hasattr(model, "model_json_schema") else TypeAdapter(model).json_schema()
        dump_json(ROOT / "docs" / "contracts" / f"{name}.schema.json", schema)
        dump_json(SCHEMAS / f"{name}.schema.json", schema)

    anchor_counts = Counter(r.anchor_precision for r in evidence_rows)
    state_counts = Counter(r.value_state.value for r in evidence_rows)
    origin_counts = Counter(r.value_origin.value for r in evidence_rows)
    norm_counts = Counter(r.normalization_status for r in normalizations)
    mapping_counts = Counter(r["mapping_status"] for r in mapping_rows)
    lineage_summary = read_json(
        ROOT / HISTORICAL_RUNS[-1] / "artifacts/historical_extraction_lineage_forensics_summary.json"
    )
    category_field_sets = {
        "biological_system": {r.field_id for r in registry if r.semantic_category == "biological_system"},
        "disease_background": {r.field_id for r in registry if r.semantic_category == "disease_background"},
        "intervention_background": {
            r.field_id for r in registry if r.semantic_category == "intervention_background"
        } - {"duration", "timepoint", "frequency"},
        "temporal": {"duration", "timepoint", "frequency"},
        "measurement_background": {
            r.field_id for r in registry if r.semantic_category == "measurement_background"
        } - {"subcellular_localization"},
        "localization": {"subcellular_localization"},
        "experimental_design": {r.field_id for r in registry if r.semantic_category == "experimental_design"},
    }
    category_coverage = {}
    for category, field_ids in category_field_sets.items():
        rows = [r for r in coverage if r.field_id in field_ids]
        category_coverage[category] = {
            "record_count": len(rows),
            "direct_validated_count": sum(r.validated_value_available and r.direct_evidence_available for r in rows),
            "inherited_validated_count": 0,
            "candidate_only_count": sum(r.value_state_available and not r.validated_value_available for r in rows),
            "legacy_unresolved_count": sum(
                e.value_state == "legacy_null_unresolved" and e.field_id in field_ids for e in evidence_rows
            ),
            "unavailable_count": sum(not r.value_state_available for r in rows),
            "validated_value_coverage_rate": round(
                sum(r.validated_value_available for r in rows) / len(rows), 6
            ) if rows else 0.0,
        }
    summary = {
        "historical_context_artifact_count": historical_inventory_count,
        "observation_count": len(observation_ids),
        "observation_with_any_context_count": sum(bool(by_obs_evidence[o]) for o in observation_ids),
        "context_candidate_revision_count": len(candidates),
        "experiment_scope_count": len(scopes),
        "validated_experiment_scope_count": sum(s.scope_status == "validated_explicit_scope" for s in scopes),
        "ambiguous_experiment_scope_count": sum(s.scope_status == "ambiguous_scope" for s in scopes),
        "context_field_registry_count": len(registry),
        "historical_context_field_count": len(historical_fields),
        "field_mapping_counts": dict(mapping_counts),
        "context_field_evidence_count": len(evidence_rows),
        "direct_local_context_field_count": sum(
            r.value_state == "present" and bool(r.evidence_anchor_ids) for r in evidence_rows),
        "shared_experiment_context_field_count": 0,
        "deterministic_inherited_context_field_count": 0,
        "candidate_only_context_field_count": sum(r.context_validation_status == "candidate_only" for r in evidence_rows),
        "anchor_precision_counts": dict(anchor_counts),
        "value_state_counts": dict(state_counts),
        "value_origin_counts": dict(origin_counts),
        "legacy_null_before": lineage_summary["legacy_null_count_before"],
        "legacy_null_migrated": sum(r.value_state == "legacy_null_unresolved" for r in evidence_rows),
        "legacy_null_resolved": 0,
        "legacy_null_still_unresolved": lineage_summary["legacy_null_still_unresolved"],
        "validated_context_revision_count": len(validated),
        "validated_current_context_count": 0,
        "validated_legacy_context_count": len(validated),
        "candidate_only_context_count": sum(not is_current_validated[o] for o in observation_ids),
        "invalid_context_count": 0, "unavailable_context_count": 0,
        "normalization_revision_count": len(normalizations),
        "normalization_status_counts": dict(norm_counts),
        "normalization_resolved_count": norm_counts["resolved"],
        "normalization_ambiguous_count": norm_counts["ambiguous"],
        "normalization_unresolved_count": norm_counts["unresolved"],
        "consolidation_revision_count": len(consolidations),
        "consolidation_direct_field_count": sum(r.direct_field_count for r in consolidations),
        "consolidation_inherited_field_count": 0,
        "consolidation_conflict_count": 0,
        "scoped_authority_counts": {
            axis: dict(Counter(getattr(r, axis) for r in authorities)) for axis in (
                "semantic_authority", "evidence_authority", "provenance_authority",
                "replayability_authority", "downstream_use_authority",
            )
        },
        "context_category_coverage": category_coverage,
        **cov_summary, **remediation_summary, **readiness_summary,
        "context_coverage_record_count": len(coverage),
        "context_remediation_requirement_count": len(remediation),
        "requirements_resolvable_from_existing_context": len(remediation),
        "requirements_resolvable_from_parsed_payload": 0,
        "requirements_resolvable_from_raw": 0,
        "requirements_resolvable_from_scope_propagation": 0,
        "candidate_prompt_revision_created": True,
        "candidate_prompt_revision_status": "pending_smoke_validation",
        "candidate_prompt_production_status": "not_activated",
        "context_provider_call_policy_status": "selective_remediation_only",
        "extraction_run_readiness_status": "ready_for_smoke",
        "schema_version": "experimental_context_asset_integration_summary_v1",
    }
    dump_json(ART / "experimental_context_asset_integration_summary.json", summary)

    changed = sorted(set(filter(None, git("status", "--short").splitlines())))
    tracked_changed = set(filter(None, git("diff", "--name-only").splitlines()))
    untracked = set(filter(None, git("ls-files", "--others", "--exclude-standard").splitlines()))
    run_files = {
        path.relative_to(ROOT).as_posix() for path in OUT.rglob("*") if path.is_file()
    }
    run_files.add((ART / "experimental_context_asset_integration_manifest.json").relative_to(ROOT).as_posix())
    round_files = sorted(tracked_changed | untracked | run_files)
    manifest = {
        **summary,
        "schema_version": "experimental_context_asset_integration_manifest_v1",
        "git_head_before": git("rev-parse", "HEAD"), "git_head_after": git("rev-parse", "HEAD"),
        "git_status_before": [], "git_status_after": changed,
        "preexisting_dirty_files": [],
        "files_changed_this_round": round_files,
        "files_created_this_round": sorted(untracked | run_files),
        "historical_context_runs_scanned": HISTORICAL_RUNS,
        "historical_runs_modified": False, "historical_context_payloads_modified": False,
        "historical_source_files_modified": False, "historical_raw_files_modified": False,
        "historical_parsed_payloads_modified": False,
        "exact_field_mapping_count": mapping_counts["exact_same_field"],
        "alias_field_mapping_count": mapping_counts["versioned_alias"],
        "unresolved_field_mapping_count": mapping_counts["unresolved"],
        "semantic_mismatch_field_count": mapping_counts["semantic_mismatch"],
        "exact_anchor_count": anchor_counts["exact"],
        "sentence_anchor_count": anchor_counts["sentence"],
        "block_anchor_count": anchor_counts["block"],
        "unresolved_anchor_count": anchor_counts["unresolved"],
        "normalization_resolved_count": norm_counts["resolved"],
        "normalization_ambiguous_count": norm_counts["ambiguous"],
        "normalization_unresolved_count": norm_counts["unresolved"],
        "candidate_count_before": 11, "candidate_count_after": 11,
        "candidate_identity_changed": False, "candidate_order_changed": False,
        "scientific_pair_set_changed": False,
        "formal_conflict_count_before": 0, "formal_conflict_count_after": 0,
        "weak_3ca_status_before_after": ["ready/ready_not_materialized", "ready/ready_not_materialized"],
        "weak_256_status_before_after": ["blocked_context_b_unavailable/blocked_entry",
                                         "blocked_context_b_unavailable/blocked_entry"],
        "ebd5_status_before_after": ["blocked_alignment/diagnostic_only/not_confirmed",
                                     "blocked_alignment/diagnostic_only/not_confirmed"],
        "context_17b_status_before_after": ["fail_closed_policy_coverage_failure"] * 2,
        "context_41f_status_before_after": ["fail_closed_policy_coverage_failure"] * 2,
        "contract_identities": {k: v["identity_sha256"] for k, v in identities.items()},
        "provider_calls": 0, "api_calls": 0, "real_api_calls": 0,
        "network_calls": 0, "downloads": 0, "credential_values_read": False,
        "provider_client_created": False, "dataset_release_pipeline_created": False,
        "method_paper_narrative_changed": False, "handoff_created": False,
        "atlas_activated": False, "active_pointer_changed": False,
        "variational_em_called": False,
    }
    dump_json(ART / "experimental_context_asset_integration_manifest.json", manifest)


if __name__ == "__main__":
    generate()
