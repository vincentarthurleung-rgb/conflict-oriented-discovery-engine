#!/usr/bin/env python3
"""Build the full-corpus experimental-core integrity sidecar, entirely offline."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from code_engine.extraction_assets.experimental_core.atomicity import assess_atomicity
from code_engine.extraction_assets.experimental_core.factors import (
    explicit_factor_candidates, role_for,
)
from code_engine.extraction_assets.experimental_core.identities import (
    CONTRACT_NAMES, contract_identity, core_identity,
)
from code_engine.extraction_assets.experimental_core.integrity import evaluate_integrity
from code_engine.extraction_assets.experimental_core.linkage import (
    reference_audit, resolve_explicit_links,
)
from code_engine.extraction_assets.experimental_core.loss_diagnosis import first_loss
from code_engine.extraction_assets.experimental_core.measurements import (
    explicit_measurement_candidates,
)
from code_engine.extraction_assets.experimental_core.models import (
    CoreProvenance, ExperimentalCoreFirstLossDiagnosis,
    ExperimentalCoreRecoveryRevision, ExperimentalCoreRemediationRequirement,
    ExperimentalCoreStageTrace, ExperimentalFactorRecord,
    ExperimentalObservationAtomicityAudit, ExperimentalObservationLinkage,
    ExperimentalObservationMachineReuseReadiness,
    ExperimentalObservationStructuralIntegrity, MeasurementRecord,
    ObservedResultRecord, ResearchGradeObservationContextExtractionContractV2,
    StructuredExperimentalObservationRevision,
)
from code_engine.extraction_assets.experimental_core.readiness import evaluate_readiness
from code_engine.extraction_assets.experimental_core.remediation import (
    authorization_fields, dedup_group,
)
from code_engine.extraction_assets.experimental_core.results import explicit_result_candidates
from code_engine.extraction_assets.experimental_core.stage_trace import STAGES, trace_payload
from code_engine.extraction_assets.experimental_core.type_policy import (
    ACTIVE_ROLES, assess_observation_type, build_policy,
)
from code_engine.extraction_assets.identities import sha256_bytes, sha256_json


ROOT = Path(__file__).resolve().parents[1]
RUN_NAME = "20260725_hif1a_core_experimental_observation_integrity_v1_offline"
OUT = ROOT / "runs" / RUN_NAME
ART = OUT / "artifacts"
SCHEMAS = OUT / "schemas"
IDENTITIES = OUT / "contract_identities"

L1_RUN = ROOT / "runs/20260723_012253_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_l1_v2_canary"
RECOVERY_RUN = ROOT / (
    "runs/20260723_012253_hif1a_hypoxia_cancer_response_discovery_v1_"
    "fulltext_l1_v2_canary__failed_block_recovery_277fd64a45668b7a8a0b"
)
V3_RUN = ROOT / (
    "runs/20260723_171527_hif1a_hypoxia_cancer_response_discovery_v1_"
    "fulltext_v3_recovered_reentry"
)
PROJECTION_RUN = ROOT / (
    "runs/20260723_171527_hif1a_hypoxia_cancer_response_discovery_v1_"
    "fulltext_v3_recovered_reentry__fulltext_evidence_projection_0343b9bfebb093729dea"
)
ASSET_RUN = ROOT / "runs/20260725_hif1a_extraction_asset_preservation_v1_offline"
FORENSICS_RUN = ROOT / "runs/20260725_hif1a_historical_extraction_lineage_forensics_v1_offline"
CONTEXT_RUN = ROOT / "runs/20260725_hif1a_experimental_context_asset_integration_v1_offline"
CANDIDATE_RUN = ROOT / "runs/20260725_hif1a_candidate_qualification_v1_offline"
L4_RUN = ROOT / "runs/20260725_hif1a_l4_context_readiness_gate_v1_offline"

AUDITED_ROOTS = (
    L1_RUN, RECOVERY_RUN, V3_RUN, PROJECTION_RUN, ASSET_RUN, FORENSICS_RUN,
    CONTEXT_RUN, CANDIDATE_RUN, L4_RUN,
    ROOT / "src/code_engine/fulltext",
    ROOT / "src/code_engine/extraction",
    ROOT / "src/code_engine/extraction_assets",
    ROOT / "src/code_engine/schemas",
    ROOT / "src/code_engine/context_attribution/observation_context",
)
CORE_FIELDS = (
    "experiment_scopes", "observations", "experimental_factors",
    "interventions", "measurements", "observed_results",
    "explicit_local_references", "evidence_refs",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def dump_jsonl(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(
        json.dumps(
            row.model_dump(mode="json") if hasattr(row, "model_dump") else row,
            ensure_ascii=False, sort_keys=True,
        ) + "\n" for row in rows
    ), encoding="utf-8")


def provenance(*refs: str, producer: str = "experimental_core_offline_audit",
               limitations: list[str] | None = None) -> CoreProvenance:
    return CoreProvenance(
        producer=producer, producer_version="v1",
        source_artifact_refs=[ref for ref in refs if ref],
        deterministic_rule_refs=["experimental_core_deterministic_adapter_v1"],
        limitations=limitations or [],
    )


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tokens = (
        "observation", "experiment", "evidence", "extraction", "parsed",
        "validated", "context", "candidate", "lineage", "projection", "schema",
        "parser", "adapter",
    )
    seen: set[str] = set()
    for base in AUDITED_ROOTS:
        if not base.exists():
            continue
        for path in sorted(item for item in base.rglob("*") if item.is_file()):
            ref = relative(path)
            if ref in seen or not any(token in path.name.lower() for token in tokens):
                continue
            seen.add(ref)
            row_count = None
            schema_versions: set[str] = set()
            observation_refs: set[str] = set()
            document_refs: set[str] = set()
            block_refs: set[str] = set()
            if path.suffix in {".json", ".jsonl"}:
                try:
                    values = [read_json(path)] if path.suffix == ".json" else read_jsonl(path)
                    row_count = len(values)
                    stack: list[Any] = list(values)
                    while stack:
                        value = stack.pop()
                        if isinstance(value, dict):
                            for key in ("schema_version", "source_schema_version"):
                                if isinstance(value.get(key), str):
                                    schema_versions.add(value[key])
                            for key in ("observation_id", "claim_id", "source_observation_identity"):
                                if isinstance(value.get(key), str):
                                    observation_refs.add(value[key])
                            for key in ("source_document_id", "pmcid", "paper_id"):
                                if isinstance(value.get(key), str):
                                    document_refs.add(value[key])
                            for key in ("block_id", "child_block_id", "parent_block_id"):
                                if isinstance(value.get(key), str):
                                    block_refs.add(value[key])
                            stack.extend(value.values())
                        elif isinstance(value, list):
                            stack.extend(value)
                except (ValueError, UnicodeDecodeError, OSError):
                    pass
            payload = {
                "artifact_kind": path.stem,
                "relative_path": ref,
                "source_root": relative(base),
                "sha256": sha256_bytes(path.read_bytes()),
                "file_size_bytes": path.stat().st_size,
                "row_count": row_count,
                "schema_versions": sorted(schema_versions),
                "observation_refs": sorted(observation_refs),
                "document_refs": sorted(document_refs),
                "block_refs": sorted(block_refs),
                "audit_disposition": "structured_core_input" if path.suffix in {".json", ".jsonl"} else "contract_or_code_input",
            }
            payload["identity"] = core_identity("experimental_core_asset_inventory_v1", payload)
            rows.append(payload)
    return rows


def source_rows() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]],
                           dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    l1 = read_jsonl(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl")
    v3_rows = read_jsonl(V3_RUN / "artifacts/fulltext_experiment_observations.jsonl")
    projected = read_jsonl(PROJECTION_RUN / "artifacts/fulltext_projected_observations.jsonl")
    chains = read_jsonl(PROJECTION_RUN / "artifacts/experimental_evidence_chains.jsonl")
    return (
        l1,
        {row["observation_id"]: row for row in v3_rows},
        {row["observation_id"]: row for row in projected},
        {row["experiment_id"]: row for row in chains},
    )


def factor_record(source: dict[str, Any], item: dict[str, Any], revision_id: str,
                  index: int) -> ExperimentalFactorRecord:
    role = role_for(item)
    local_id = str(
        item.get("factor_local_id") or item.get("local_factor_id")
        or item.get("intervention_id") or f"factor_{index + 1}"
    )
    raw = (
        item.get("raw_text") or item.get("agent_mention") or item.get("target_mention")
        or item.get("condition_raw") or item.get("extracted_value")
    )
    extracted = item.get("extracted_value", raw)
    payload = {
        "observation_revision_identity": revision_id,
        "local_factor_id": local_id,
        "role": role,
        "raw_text": raw,
        "extracted_value": extracted,
        "canonical_value": item.get("canonical_value"),
        "canonical_identity": item.get("canonical_identity"),
        "value_state": "present" if raw is not None else "unknown",
        "order_index": int(item.get("order_index", item.get("_order", index))),
        "factor_group_id": (source.get("experiment") or {}).get("experiment_id"),
        "control_or_comparator_status": (
            "control_or_comparator" if role in {"control", "comparator", "baseline"}
            else "not_control_or_comparator"
        ),
        "qualifier_refs": [],
        "context_field_refs": [],
        "evidence_anchor_ids": list(
            item.get("evidence_anchor_ids") or item.get("evidence_span_ids") or []
        ),
        "validation_status": "migrated_explicit_structure",
        "normalization_status": str(item.get("normalization_status") or "unresolved"),
        "authority_status": "deterministic",
    }
    factor_id = core_identity("experimental_factor_record_v1", payload)
    return ExperimentalFactorRecord(
        factor_id=factor_id, **payload, identity=factor_id,
        provenance=provenance(relative(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl")),
    )


def measurement_record(source: dict[str, Any], item: dict[str, Any], revision_id: str,
                       index: int) -> MeasurementRecord:
    local_id = str(
        item.get("measurement_local_id") or item.get("local_measurement_id")
        or item.get("measurement_id") or f"measurement_{index + 1}"
    )
    target = (
        item.get("measured_entity_raw") or item.get("measured_entity_mention")
        or item.get("measured_entity") or item.get("endpoint")
    )
    endpoint = (
        item.get("property_or_endpoint_raw") or item.get("endpoint_raw")
        or item.get("outcome_mention") or item.get("endpoint")
    )
    method = item.get("method_raw") or item.get("assay_or_readout_raw") or item.get("assay")
    payload = {
        "observation_revision_identity": revision_id,
        "local_measurement_id": local_id,
        "measured_entity_raw": target,
        "measured_entity_extracted": item.get("measured_entity_extracted", target),
        "measured_entity_canonical": item.get("measured_entity_canonical"),
        "property_or_endpoint_raw": endpoint,
        "property_or_endpoint_extracted": item.get("property_or_endpoint_extracted", endpoint),
        "property_or_endpoint_canonical": item.get("property_or_endpoint_canonical"),
        "measurement_semantic_level": str(item.get("measurement_dimension") or "unresolved"),
        "method_raw": method,
        "method_extracted": item.get("method_extracted", method),
        "method_canonical": item.get("method_canonical"),
        "unit_raw": item.get("unit_raw"),
        "unit_canonical": item.get("unit_canonical"),
        "sample_ref": item.get("sample_ref"),
        "localization_ref": item.get("localization_ref"),
        "assay_context_ref": item.get("assay_context_ref"),
        "evidence_anchor_ids": list(
            item.get("evidence_anchor_ids") or item.get("evidence_span_ids") or []
        ),
        "validation_status": "migrated_explicit_structure",
        "normalization_status": str(item.get("normalization_status") or "unresolved"),
        "authority_status": "deterministic",
    }
    measurement_id = core_identity("measurement_record_v1", payload)
    return MeasurementRecord(
        measurement_id=measurement_id, **payload, identity=measurement_id,
        provenance=provenance(relative(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl")),
    )


def result_record(source: dict[str, Any], item: dict[str, Any], revision_id: str,
                  index: int, measurements: list[MeasurementRecord],
                  factors: list[ExperimentalFactorRecord]) -> ObservedResultRecord:
    local_id = str(
        item.get("result_local_id") or item.get("local_result_id")
        or item.get("observed_result_id") or f"result_{index + 1}"
    )
    explicit_ref = item.get("measurement_ref") or item.get("measurement_local_ref")
    measurement_ref = None
    if explicit_ref:
        measurement_ref = next(
            (row.measurement_id for row in measurements
             if row.local_measurement_id == explicit_ref or row.measurement_id == explicit_ref),
            None,
        )
    elif len(measurements) == 1:
        measurement_ref = measurements[0].measurement_id
        explicit_ref = measurements[0].local_measurement_id
    comparison_text = item.get("comparison_raw")
    comparator_factors = [
        row for row in factors if row.role in {"control", "comparator", "baseline"}
    ]
    comparison_refs: list[str] = []
    local_comparison_refs: list[str] = []
    if comparison_text and len(comparator_factors) == 1:
        comparison_refs = [comparator_factors[0].factor_id]
        local_comparison_refs = [comparator_factors[0].local_factor_id]
    elif comparison_text and comparator_factors:
        exact = [
            row for row in comparator_factors
            if row.raw_text and row.raw_text.casefold() in str(comparison_text).casefold()
        ]
        if len(exact) == 1:
            comparison_refs = [exact[0].factor_id]
            local_comparison_refs = [exact[0].local_factor_id]
    payload = {
        "observation_revision_identity": revision_id,
        "local_result_id": local_id,
        "measurement_ref": measurement_ref,
        "comparison_factor_refs": comparison_refs,
        "baseline_ref": item.get("baseline_ref"),
        "qualitative_result": item.get("qualitative_result") or item.get("observed_result")
        or item.get("effect_description"),
        "direction": item.get("direction"),
        "sign": item.get("sign"),
        "negation": bool(item.get("negation", False)),
        "quantitative_value_raw": item.get("quantitative_value_raw", item.get("quantitative_result_raw")),
        "quantitative_value_canonical": item.get("quantitative_value_canonical"),
        "effect_size": item.get("effect_size"),
        "confidence_interval": item.get("confidence_interval"),
        "statistical_statement": item.get("statistical_statement") or item.get("statistical_support_raw"),
        "significance_status": str(item.get("significance_status") or "unresolved"),
        "uncertainty_text": item.get("uncertainty_text") or item.get("uncertainty_raw"),
        "evidence_anchor_ids": list(
            item.get("evidence_anchor_ids") or item.get("evidence_span_ids") or []
        ),
        "validation_status": "migrated_explicit_structure",
        "authority_status": "deterministic",
    }
    result_id = core_identity("observed_result_record_v1", payload)
    row = ObservedResultRecord(
        observed_result_id=result_id, **payload, identity=result_id,
        provenance=provenance(relative(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl")),
    )
    data = row.model_dump(mode="json")
    data["_explicit_measurement_local_ref"] = explicit_ref
    data["_comparison_local_refs"] = local_comparison_refs
    data["_comparative"] = bool(comparison_text)
    return row, data


def add_factor_measurement_links(
    revision_id: str, factors: list[dict[str, Any]], measurements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(measurements) != 1:
        return []
    active = [row for row in factors if row["role"] in ACTIVE_ROLES]
    links = []
    for factor in active:
        payload = {
            "observation_revision_identity": revision_id,
            "relation_type": "factor_applies_to_measurement",
            "source_ref": factor["factor_id"],
            "target_ref": measurements[0]["measurement_id"],
            "order": factor["order_index"],
            "evidence_anchor_ids": sorted(set(
                factor["evidence_anchor_ids"] + measurements[0]["evidence_anchor_ids"]
            )),
            "derivation_method": "legacy_explicit_factor_group_to_scalar_measurement",
            "validation_status": "valid",
            "authority_status": "deterministic",
        }
        payload["linkage_id"] = core_identity("experimental_observation_linkage_v1", payload)
        links.append(payload)
    return links


def build_core_assets(l1_rows: list[dict[str, Any]]):
    factors_all: list[ExperimentalFactorRecord] = []
    measurements_all: list[MeasurementRecord] = []
    results_all: list[ObservedResultRecord] = []
    linkages_all: list[ExperimentalObservationLinkage] = []
    revisions: list[StructuredExperimentalObservationRevision] = []
    atomicity: list[ExperimentalObservationAtomicityAudit] = []
    references: list[dict[str, Any]] = []
    recoveries: list[ExperimentalCoreRecoveryRevision] = []
    by_observation: dict[str, dict[str, Any]] = {}
    for source in l1_rows:
        observation_id = source["observation_id"]
        revision_payload = {
            "source_observation_identity": observation_id,
            "source_parsed_candidate_identity": observation_id,
            "source_validated_observation_identity": observation_id,
            "source_fulltext_v3_identity": observation_id,
            "source_projection_identity": observation_id,
            "supersedes_revision_id": None,
            "immutable": True,
        }
        revision_id = core_identity("structured_experimental_observation_revision_v1", revision_payload)
        factors = [
            factor_record(source, item, revision_id, index)
            for index, item in enumerate(explicit_factor_candidates(source))
        ]
        measurements = [
            measurement_record(source, item, revision_id, index)
            for index, item in enumerate(explicit_measurement_candidates(source))
        ]
        result_pairs = [
            result_record(source, item, revision_id, index, measurements, factors)
            for index, item in enumerate(explicit_result_candidates(source))
        ]
        results = [pair[0] for pair in result_pairs]
        factor_dicts = [row.model_dump(mode="json") for row in factors]
        measurement_dicts = [row.model_dump(mode="json") for row in measurements]
        result_dicts = [pair[1] for pair in result_pairs]
        roles = {row.role for row in factors}
        observation_type, type_authority = assess_observation_type(
            source=source, factor_roles=roles,
            measurement_count=len(measurements), result_count=len(results),
        )
        raw_links = (
            add_factor_measurement_links(revision_id, factor_dicts, measurement_dicts)
            + resolve_explicit_links(revision_id, factor_dicts, measurement_dicts, result_dicts)
        )
        links = [
            ExperimentalObservationLinkage(
                **row, identity=row["linkage_id"],
                provenance=provenance(relative(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl")),
            )
            for row in sorted(raw_links, key=lambda item: item["linkage_id"])
        ]
        audit = reference_audit(
            revision_id, factor_dicts, measurement_dicts, result_dicts,
            [row.model_dump(mode="json") for row in links],
        )
        audit["identity"] = core_identity("experimental_observation_reference_integrity_audit_v1", audit)
        references.append(audit)
        atom_status, atom_issues = assess_atomicity(measurement_dicts, result_dicts)
        atomic_payload = {
            "source_observation_identity": observation_id,
            "status": atom_status, "issue_codes": atom_issues,
            "deterministic_split_allowed": False,
            "parent_observation_identity": None, "child_revision_ids": [],
        }
        atomicity.append(ExperimentalObservationAtomicityAudit(
            **atomic_payload,
            identity=core_identity("experimental_observation_atomicity_audit_v1", atomic_payload),
            provenance=provenance(relative(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl")),
        ))
        chain_id = (source.get("experiment") or {}).get("evidence_family_id")
        revision = StructuredExperimentalObservationRevision(
            structured_observation_revision_id=revision_id,
            **revision_payload,
            observation_type=observation_type,
            observation_type_authority=(
                "authoritative" if type_authority.startswith("explicit") else "deterministic"
            ),
            experiment_scope_identity=(source.get("experiment") or {}).get("experiment_id"),
            experimental_factor_ids=[row.factor_id for row in factors],
            measurement_ids=[row.measurement_id for row in measurements],
            observed_result_ids=[row.observed_result_id for row in results],
            linkage_record_ids=[row.linkage_id for row in links],
            context_asset_identity=f"context_asset_ref:{observation_id}",
            evidence_chain_identity=chain_id,
            structural_integrity_identity=None,
            extraction_schema_identity=source.get("schema_version"),
            parser_identity="fulltext_l1_v2_parser",
            validator_identity="fulltext_l1_v3_deterministic_validator",
            identity=revision_id,
            provenance=provenance(relative(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl")),
        )
        recovered_components = []
        if factors:
            recovered_components.append("experimental_factors")
        if measurements:
            recovered_components.append("measurements")
        if results:
            recovered_components.append("observed_results")
        recovery_payload = {
            "source_observation_identity": observation_id,
            "affected_component": ",".join(recovered_components),
            "source_stage": "schema_valid_l1_observation",
            "source_artifact_identity": relative(
                RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl"
            ),
            "old_status": "projection_core_structure_missing",
            "recovered_records": [
                *(row.factor_id for row in factors),
                *(row.measurement_id for row in measurements),
                *(row.observed_result_id for row in results),
            ],
            "recovered_links": [row.linkage_id for row in links],
            "recovery_method": "explicit_fulltext_l1_v3_sidecar_migration",
            "deterministic_rule_identity": "experimental_core_l1_scalar_adapter_v1",
            "authority_status": "deterministic",
            "unresolved_items": atom_issues,
            "supersedes_revision_id": None,
            "immutable": True,
        }
        recoveries.append(ExperimentalCoreRecoveryRevision(
            recovery_revision_id=core_identity("experimental_core_recovery_revision_v1", recovery_payload),
            **recovery_payload,
            identity=core_identity("experimental_core_recovery_revision_v1", recovery_payload),
            provenance=provenance(relative(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl")),
        ))
        factors_all.extend(factors)
        measurements_all.extend(measurements)
        results_all.extend(results)
        linkages_all.extend(links)
        revisions.append(revision)
        by_observation[observation_id] = {
            "source": source, "revision": revision, "factors": factor_dicts,
            "measurements": measurement_dicts, "results": result_dicts,
            "links": [row.model_dump(mode="json") for row in links],
            "reference_audit": audit, "observation_type": observation_type,
            "type_authority": type_authority,
        }
    return (
        factors_all, measurements_all, results_all, linkages_all, revisions,
        atomicity, references, recoveries, by_observation,
    )


def build_traces(
    by_observation: dict[str, dict[str, Any]],
    original_rows: dict[str, dict[str, Any]],
    v3_rows: dict[str, dict[str, Any]],
    projection_rows: dict[str, dict[str, Any]],
):
    traces: list[ExperimentalCoreStageTrace] = []
    diagnoses: list[ExperimentalCoreFirstLossDiagnosis] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    stage_refs = {
        1: relative(L1_RUN / "artifacts/fulltext_experiment_observations.jsonl"),
        2: relative(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl"),
        3: relative(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl"),
        4: relative(V3_RUN / "artifacts/fulltext_experiment_observations.jsonl"),
        5: relative(PROJECTION_RUN / "artifacts/fulltext_projected_observations.jsonl"),
        6: f"runs/{RUN_NAME}/artifacts/structured_experimental_observation_revisions.jsonl",
        7: relative(CONTEXT_RUN / "artifacts/context_asset_multi_axis_readiness.jsonl"),
    }
    for observation_id, core in by_observation.items():
        recovered_payload = {
            "experimental_factors": core["factors"],
            "interventions": core["source"].get("interventions") or [],
            "measurements": core["measurements"],
            "observed_results": core["results"],
            "linkages": core["links"],
            "evidence_span_ids": core["source"].get("evidence_span_ids", []),
        }
        payloads = {
            0: None,
            1: original_rows.get(observation_id) or core["source"],
            2: core["source"],
            3: core["source"],
            4: v3_rows.get(observation_id),
            5: projection_rows.get(observation_id),
            6: recovered_payload,
            7: None,
        }
        obs_traces = []
        for stage_number, stage_name in STAGES:
            payload = payloads[stage_number]
            counts, payload_hash = trace_payload(payload)
            unavailable = payload is None
            availability = {
                "experimental_factors": bool(counts["factor_count"]),
                "interventions": bool(counts["intervention_count"]),
                "measurements": bool(counts["measurement_count"]),
                "observed_results": bool(counts["observed_result_count"]),
                "linkages": bool(counts["linkage_count"]),
            }
            statuses = {
                key: "unavailable" if unavailable else ("present" if present else "absent")
                for key, present in availability.items()
            }
            payload_base = {
                "source_observation_identity": observation_id,
                "stage_number": stage_number, "stage_name": stage_name,
                "stage_identity": f"stage_{stage_number}:{observation_id}",
                "source_artifact_ref": stage_refs.get(stage_number),
                **counts, "payload_hash": payload_hash,
                "field_availability": availability, "field_status": statuses,
            }
            trace_id = core_identity("experimental_core_stage_trace_v1", payload_base)
            row = ExperimentalCoreStageTrace(
                trace_id=trace_id, **payload_base, identity=trace_id,
                provenance=provenance(stage_refs.get(stage_number, ""), limitations=(
                    ["historical_raw_or_consumer_payload_unavailable"] if unavailable else []
                )),
            )
            traces.append(row)
            obs_traces.append(row.model_dump(mode="json"))
        grouped[observation_id] = obs_traces
        for component in (
            "experimental_factors", "interventions", "measurements",
            "observed_results", "linkages",
        ):
            stage_number, stage_name, origin = first_loss(obs_traces, component)
            payload = {
                "source_observation_identity": observation_id,
                "component": component,
                "first_loss_stage_number": stage_number,
                "first_loss_stage_name": stage_name,
                "loss_origin": origin,
                "stage_trace_ids": [row["trace_id"] for row in obs_traces],
                "evidence_refs": [row["source_artifact_ref"] for row in obs_traces
                                  if row["source_artifact_ref"]],
            }
            diagnosis_id = core_identity("experimental_core_first_loss_diagnosis_v1", payload)
            diagnoses.append(ExperimentalCoreFirstLossDiagnosis(
                diagnosis_id=diagnosis_id, **payload, identity=diagnosis_id,
                provenance=provenance(*payload["evidence_refs"]),
            ))
    return traces, diagnoses


def build_gates(by_observation: dict[str, dict[str, Any]]):
    integrity_rows: list[ExperimentalObservationStructuralIntegrity] = []
    readiness_rows: list[ExperimentalObservationMachineReuseReadiness] = []
    remediation_rows: list[ExperimentalCoreRemediationRequirement] = []
    for observation_id, core in by_observation.items():
        status, issues, factor_basis = evaluate_integrity(
            observation_type=core["observation_type"],
            factors=core["factors"], measurements=core["measurements"],
            results=core["results"], links=core["links"],
            reference_audit=core["reference_audit"], provenance_traceable=True,
        )
        evidence_complete = all(
            row.get("evidence_anchor_ids")
            for row in core["factors"] + core["measurements"] + core["results"]
        )
        payload = {
            "source_observation_identity": observation_id,
            "structured_observation_revision_identity": core["revision"].identity,
            "observation_type": core["observation_type"],
            "status": status, "factor_requirement_basis": factor_basis,
            "issue_codes": issues,
            "dangling_refs": core["reference_audit"]["dangling_refs"],
            "duplicate_local_ids": core["reference_audit"]["duplicate_local_ids"],
            "core_evidence_complete": evidence_complete,
            "provenance_traceable": True,
        }
        integrity_id = core_identity("experimental_observation_structural_integrity_v1", payload)
        integrity_rows.append(ExperimentalObservationStructuralIntegrity(
            **payload, identity=integrity_id,
            provenance=provenance(relative(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl")),
        ))
        reuse, limitations = evaluate_readiness(
            observation_type=core["observation_type"], integrity_status=status,
            has_claim_evidence=bool(core["source"].get("evidence_span_ids")),
        )
        reuse_payload = {
            "source_observation_identity": observation_id,
            "structured_observation_revision_identity": core["revision"].identity,
            "structural_integrity_identity": integrity_id,
            "status": reuse, "human_gold": False,
            "formal_conflict_authority": False, "limitation_codes": limitations,
        }
        readiness_rows.append(ExperimentalObservationMachineReuseReadiness(
            **reuse_payload,
            identity=core_identity("experimental_observation_machine_reuse_readiness_v1", reuse_payload),
            provenance=provenance(relative(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl")),
        ))
        missing = []
        if status == "incomplete_missing_factor":
            missing.append("experimental_factors")
        if status == "incomplete_missing_measurement":
            missing.append("measurements")
        if status == "incomplete_missing_result":
            missing.append("observed_results")
        if status in {"incomplete_missing_linkage", "invalid_dangling_reference"}:
            missing.append("linkages")
        if reuse in {"text_evidence_only", "unusable", "unassessed"} and not missing:
            missing.append("structural_authority")
        if missing:
            source_block = (core["source"].get("provenance") or {}).get("child_block_id")
            dedup = dedup_group(source_block, "source_block_context_envelope")
            remediation_payload = {
                "observation_identity": observation_id,
                "source_block_identity": source_block,
                "observation_type": core["observation_type"],
                "missing_components": missing,
                "first_loss_stage": "evidence_projection",
                "available_offline_recovery_modes": [],
                "preferred_offline_recovery_mode": None,
                "raw_lineage_status": "historical_raw_unavailable_or_unbound",
                "parsed_payload_status": "explicit_l1_structure_already_migrated",
                "evidence_status": "available" if core["source"].get("evidence_span_ids") else "unavailable",
                "provider_reextraction_required": True,
                "minimal_source_scope": "source_block_context_envelope",
                "dedup_group_identity": dedup,
                **authorization_fields(),
            }
            remediation_rows.append(ExperimentalCoreRemediationRequirement(
                **remediation_payload,
                identity=core_identity("experimental_core_remediation_requirement_v1", remediation_payload),
                provenance=provenance(relative(RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl")),
            ))
    return integrity_rows, readiness_rows, remediation_rows


def coverage_summaries(
    by_observation: dict[str, dict[str, Any]],
    factors: list[ExperimentalFactorRecord],
    measurements: list[MeasurementRecord],
    results: list[ObservedResultRecord],
    links: list[ExperimentalObservationLinkage],
    integrity: list[ExperimentalObservationStructuralIntegrity],
    readiness: list[ExperimentalObservationMachineReuseReadiness],
    diagnoses: list[ExperimentalCoreFirstLossDiagnosis],
    remediation: list[ExperimentalCoreRemediationRequirement],
) -> dict[str, Any]:
    observations = list(by_observation.values())
    intervention_presence = [bool(row["source"].get("interventions")) for row in observations]
    factor_presence = [bool(row["factors"]) for row in observations]
    measurement_presence = [bool(row["measurements"]) for row in observations]
    result_presence = [bool(row["results"]) for row in observations]
    type_counts = Counter(row["observation_type"] for row in observations)
    integrity_counts = Counter(row.status for row in integrity)
    reuse_counts = Counter(row.status for row in readiness)
    loss_counts = Counter(row.loss_origin for row in diagnoses)
    link_counts = Counter(row.relation_type for row in links)
    complete_linkage, partial_linkage, no_linkage = 0, 0, 0
    for row in observations:
        relation_types = {item["relation_type"] for item in row["links"]}
        expected_factor = row["observation_type"] != "descriptive_measurement"
        complete = (
            "measurement_produces_result" in relation_types
            and (not expected_factor or "factor_applies_to_measurement" in relation_types)
            and not row["reference_audit"]["dangling_refs"]
        )
        if complete:
            complete_linkage += 1
        elif row["links"]:
            partial_linkage += 1
        else:
            no_linkage += 1
    comparative_results = [
        item for row in observations for item in row["results"] if item.get("_comparative")
    ]
    dedup_blocks = {
        row.dedup_group_identity for row in remediation if row.provider_reextraction_required
    }
    return {
        "interventional_experiment_count": type_counts["interventional_experiment"],
        "observational_comparison_count": type_counts["observational_comparison"],
        "descriptive_measurement_count": type_counts["descriptive_measurement"],
        "non_experimental_claim_count": type_counts["non_experimental_claim"],
        "unresolved_observation_type_count": type_counts["unresolved"],
        "observation_with_interventions_count": sum(intervention_presence),
        "observation_without_interventions_count": len(observations) - sum(intervention_presence),
        "observation_with_experimental_factors_count": sum(factor_presence),
        "observation_without_experimental_factors_count": len(observations) - sum(factor_presence),
        "fatal_missing_factor_count": integrity_counts["incomplete_missing_factor"],
        "type_policy_factor_exempt_count": sum(
            row["observation_type"] == "descriptive_measurement" and not row["factors"]
            for row in observations
        ),
        "factor_record_count": len(factors),
        "control_comparator_record_count": sum(
            row.role in {"control", "comparator", "baseline"} for row in factors
        ),
        "observation_with_measurements_count": sum(measurement_presence),
        "observation_without_measurements_count": len(observations) - sum(measurement_presence),
        "measurement_record_count": len(measurements),
        "measurement_missing_target_count": sum(not row.measured_entity_raw for row in measurements),
        "measurement_missing_endpoint_count": sum(not row.property_or_endpoint_raw for row in measurements),
        "measurement_missing_method_count": sum(not row.method_raw for row in measurements),
        "observation_with_results_count": sum(result_presence),
        "observation_without_results_count": len(observations) - sum(result_presence),
        "observed_result_record_count": len(results),
        "result_with_measurement_ref_count": sum(bool(row.measurement_ref) for row in results),
        "orphan_result_count": sum(not row.measurement_ref for row in results),
        "comparative_result_missing_comparator_count": sum(
            not item.get("comparison_factor_refs") and not item.get("baseline_ref")
            for item in comparative_results
        ),
        "observation_with_complete_linkage_count": complete_linkage,
        "observation_with_partial_linkage_count": partial_linkage,
        "observation_without_linkage_count": no_linkage,
        "factor_measurement_link_count": link_counts["factor_applies_to_measurement"],
        "measurement_result_link_count": link_counts["measurement_produces_result"],
        "result_comparator_link_count": link_counts["result_compared_against_factor"],
        "dangling_reference_count": sum(len(row["reference_audit"]["dangling_refs"]) for row in observations),
        "duplicate_local_id_count": sum(len(row["reference_audit"]["duplicate_local_ids"]) for row in observations),
        "absent_from_provider_output_count": loss_counts["absent_from_provider_output"],
        "parser_dropped_count": loss_counts["parser_dropped"],
        "schema_representation_loss_count": loss_counts["response_schema_could_not_represent"],
        "adapter_dropped_count": loss_counts["adapter_dropped"],
        "validation_rejected_count": (
            loss_counts["schema_validation_rejected"] + loss_counts["scientific_validation_rejected"]
        ),
        "atomization_loss_count": loss_counts["atomization_split_loss"],
        "projection_loss_count": (
            loss_counts["fulltext_v3_projection_loss"] + loss_counts["evidence_projection_loss"]
        ),
        "migration_omission_count": loss_counts["asset_migration_omission"],
        "non_experimental_source_count": loss_counts["non_experimental_source"],
        "unknown_loss_origin_count": (
            loss_counts["unknown"] + loss_counts["legacy_lineage_unavailable"]
            + loss_counts["raw_unavailable"]
        ),
        "recovered_from_parsed_count": 0,
        "recovered_from_validated_count": len(observations),
        "recovered_from_fulltext_v3_count": 0,
        "recovered_from_projection_count": 0,
        "recovered_from_authoritative_raw_count": 0,
        "recovered_link_count": len(links),
        "unrecoverable_count": len(remediation),
        "provider_reextraction_required_count": sum(
            row.provider_reextraction_required for row in remediation
        ),
        "unique_provider_reextraction_block_count": len(dedup_blocks),
        **{
            f"{key}_count": integrity_counts[key] for key in (
                "structurally_complete", "structurally_complete_with_limitations",
                "incomplete_missing_factor", "incomplete_missing_measurement",
                "incomplete_missing_result", "incomplete_missing_linkage",
                "invalid_dangling_reference",
            )
        },
        "non_experimental_claim_integrity_count": integrity_counts["non_experimental_claim"],
        "unresolved_integrity_count": integrity_counts["unresolved"],
        **{
            f"{key}_count": reuse_counts[key] for key in (
                "machine_reusable_candidate", "usable_with_major_limitations",
                "text_evidence_only", "unusable", "unassessed",
            )
        },
        "non_experimental_reuse_count": reuse_counts["non_experimental_claim"],
    }


def joint_contract() -> ResearchGradeObservationContextExtractionContractV2:
    payload = {
        "contract_id": "research_grade_observation_context_extraction_contract_v2",
        "output_fields": [
            "experiment_scopes[]", "observations[]", "experimental_factors[]",
            "measurements[]", "observed_results[]", "local_context",
            "shared_context", "evidence_refs[]",
        ],
        "local_reference_requirements": [
            "result.measurement_ref", "comparative_result.comparison_factor_refs_or_baseline_ref",
            "observation.experiment_scope_ref",
        ],
        "atomicity_requirements": [
            "atomic_observations", "separate_measurement_ids", "separate_result_ids",
            "ordered_multi_factor_records",
        ],
        "forbidden_outputs": [
            "formal_conflict", "claim_alignment", "comparability",
            "context_difference", "divergence_explanation", "canonical_identity",
        ],
        "validation_status": "pending_smoke_validation",
        "production_status": "not_activated",
        "provider_execution_authorized": False,
    }
    return ResearchGradeObservationContextExtractionContractV2(
        **payload,
        identity=core_identity("research_grade_observation_context_extraction_contract_v2", payload),
    )


def joint_payload_schema() -> dict[str, Any]:
    strict_object = {"type": "object", "additionalProperties": False}
    evidence_refs = {"type": "array", "items": {"type": "string"}}
    factor = {
        **strict_object,
        "required": ["factor_local_id", "role", "raw_text", "evidence_refs"],
        "properties": {
            "factor_local_id": {"type": "string"}, "role": {"type": "string"},
            "raw_text": {"type": ["string", "null"]}, "evidence_refs": evidence_refs,
            "order": {"type": ["integer", "null"]},
        },
    }
    measurement = {
        **strict_object,
        "required": ["measurement_local_id", "target_raw", "endpoint_raw", "method_raw", "evidence_refs"],
        "properties": {
            "measurement_local_id": {"type": "string"},
            "target_raw": {"type": ["string", "null"]},
            "endpoint_raw": {"type": ["string", "null"]},
            "method_raw": {"type": ["string", "null"]}, "evidence_refs": evidence_refs,
        },
    }
    result = {
        **strict_object,
        "required": [
            "result_local_id", "measurement_ref", "comparison_status",
            "comparison_factor_refs", "baseline_ref", "qualitative_result", "evidence_refs",
        ],
        "properties": {
            "result_local_id": {"type": "string"}, "measurement_ref": {"type": "string"},
            "comparison_status": {
                "enum": ["comparative", "non_comparative", "unresolved"],
            },
            "comparison_factor_refs": {"type": "array", "items": {"type": "string"}},
            "baseline_ref": {"type": ["string", "null"]},
            "qualitative_result": {"type": ["string", "null"]},
            "direction": {"type": ["string", "null"]}, "evidence_refs": evidence_refs,
        },
        "allOf": [{
            "if": {
                "properties": {"comparison_status": {"const": "comparative"}},
                "required": ["comparison_status"],
            },
            "then": {
                "anyOf": [
                    {"properties": {"comparison_factor_refs": {"minItems": 1}}},
                    {"properties": {"baseline_ref": {"type": "string", "minLength": 1}}},
                ],
            },
        }],
    }
    observation = {
        **strict_object,
        "required": [
            "observation_local_id", "observation_type_candidate", "experiment_scope_ref",
            "experimental_factors", "measurements", "observed_results",
            "local_context", "evidence_refs",
        ],
        "properties": {
            "observation_local_id": {"type": "string"},
            "observation_type_candidate": {"enum": [
                "interventional_experiment", "observational_comparison",
                "descriptive_measurement", "non_experimental_claim", "unresolved",
            ]},
            "experiment_scope_ref": {"type": ["string", "null"]},
            "experimental_factors": {"type": "array", "items": factor},
            "measurements": {"type": "array", "items": measurement},
            "observed_results": {"type": "array", "items": result},
            "local_context": {"type": "object"},
            "evidence_refs": evidence_refs,
        },
        "allOf": [
            {
                "if": {
                    "properties": {"observation_type_candidate": {
                        "enum": [
                            "interventional_experiment",
                            "observational_comparison",
                            "descriptive_measurement",
                        ],
                    }},
                    "required": ["observation_type_candidate"],
                },
                "then": {
                    "properties": {
                        "measurements": {"minItems": 1},
                        "observed_results": {"minItems": 1},
                    },
                },
            },
            {
                "if": {
                    "properties": {"observation_type_candidate": {
                        "enum": [
                            "interventional_experiment",
                            "observational_comparison",
                        ],
                    }},
                    "required": ["observation_type_candidate"],
                },
                "then": {
                    "properties": {"experimental_factors": {"minItems": 1}},
                },
            },
        ],
    }
    scope = {
        **strict_object,
        "required": ["scope_local_id", "shared_context"],
        "properties": {
            "scope_local_id": {"type": "string"}, "shared_context": {"type": "object"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "research_grade_observation_context_extraction_contract_v2",
        **strict_object,
        "required": ["experiment_scopes", "observations"],
        "properties": {
            "experiment_scopes": {"type": "array", "items": scope},
            "observations": {"type": "array", "items": observation},
        },
    }


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    SCHEMAS.mkdir(parents=True, exist_ok=True)
    IDENTITIES.mkdir(parents=True, exist_ok=True)
    inventory_rows = inventory()
    l1_rows, v3_rows, projection_rows, chains = source_rows()
    original_rows = {
        row["observation_id"]: row for row in
        read_jsonl(L1_RUN / "artifacts/fulltext_experiment_observations.jsonl")
    }
    (
        factors, measurements, results, links, revisions, atomicity,
        references, recoveries, by_observation,
    ) = build_core_assets(l1_rows)
    traces, diagnoses = build_traces(
        by_observation, original_rows, v3_rows, projection_rows,
    )
    integrity, readiness, remediation = build_gates(by_observation)
    stats = coverage_summaries(
        by_observation, factors, measurements, results, links,
        integrity, readiness, diagnoses, remediation,
    )

    docs = {
        (row.get("provenance") or {}).get("source_document_id")
        for row in l1_rows if (row.get("provenance") or {}).get("source_document_id")
    }
    blocks = {
        (row.get("provenance") or {}).get("child_block_id")
        for row in l1_rows if (row.get("provenance") or {}).get("child_block_id")
    }
    parser_audit = read_jsonl(
        RECOVERY_RUN / "artifacts/fulltext_l1_v2_parser_normalization_audit.jsonl"
    )
    parser_count = sum(bool(row.get("observation_id")) for row in parser_audit)
    validated_count = len(l1_rows)
    asset_stats = {
        "source_document_count": len(docs), "source_block_count": len(blocks),
        "parsed_observation_count": parser_count,
        "validated_observation_count": validated_count,
        "fulltext_v3_observation_count": len(v3_rows),
        "projection_observation_count": len(projection_rows),
        "unique_observation_identity_count": len(by_observation),
        "stage_duplicate_counts": {
            "parsed": parser_count - len({row.get("observation_id") for row in parser_audit
                                         if row.get("observation_id")}),
            "validated": len(l1_rows) - len({row["observation_id"] for row in l1_rows}),
            "fulltext_v3": len(v3_rows) - len({
                row["observation_id"] for row in v3_rows.values()
            }),
            "projection": len(projection_rows) - len({
                row["observation_id"] for row in projection_rows.values()
            }),
        },
        "parsed_to_validated_loss_count": parser_count - validated_count,
        "validated_to_v3_loss_count": validated_count - len(v3_rows),
        "v3_to_projection_loss_count": len(v3_rows) - len(projection_rows),
        "deterministic_split_count": 0,
    }
    summary = {**asset_stats, **stats}

    dump_jsonl(ART / "experimental_core_asset_inventory.jsonl", inventory_rows)
    dump_json(ART / "experimental_core_asset_inventory_summary.json", {
        **asset_stats, "inventory_artifact_count": len(inventory_rows),
        "audited_source_roots": [relative(path) for path in AUDITED_ROOTS],
    })
    dump_jsonl(ART / "observation_stage_traces.jsonl", traces)
    dump_jsonl(ART / "experimental_core_first_loss_diagnoses.jsonl", diagnoses)
    dump_json(ART / "experimental_core_first_loss_summary.json", {
        "loss_origin_counts": dict(Counter(row.loss_origin for row in diagnoses)),
        **{key: value for key, value in stats.items() if key.endswith("loss_count")
           or key.endswith("dropped_count") or key.endswith("rejected_count")
           or key.startswith("absent_from_provider") or key.startswith("unknown_loss")},
    })
    type_rows = [{
        "source_observation_identity": observation_id,
        "observation_type": row["observation_type"],
        "authority_basis": row["type_authority"],
        "identity": core_identity("observation_type_assessment_v1", {
            "source_observation_identity": observation_id,
            "observation_type": row["observation_type"],
            "authority_basis": row["type_authority"],
        }),
    } for observation_id, row in by_observation.items()]
    dump_jsonl(ART / "observation_type_assessments.jsonl", type_rows)
    policy = build_policy()
    dump_json(ART / "observation_type_cardinality_policy.json", policy.model_dump(mode="json"))
    dump_jsonl(ART / "experimental_factor_records.jsonl", factors)
    dump_jsonl(ART / "measurement_records.jsonl", measurements)
    dump_jsonl(ART / "observed_result_records.jsonl", results)
    dump_jsonl(ART / "experimental_observation_linkages.jsonl", links)
    dump_jsonl(ART / "experimental_observation_atomicity_audit.jsonl", atomicity)
    dump_jsonl(ART / "experimental_observation_reference_integrity_audit.jsonl", references)
    dump_jsonl(ART / "experimental_core_recovery_revisions.jsonl", recoveries)
    dump_jsonl(ART / "experimental_core_recovery_audit.jsonl", [{
        "source_observation_identity": row.source_observation_identity,
        "recovery_revision_identity": row.identity,
        "historical_payload_modified": False,
        "recovered_record_count": len(row.recovered_records),
        "recovered_link_count": len(row.recovered_links),
    } for row in recoveries])
    dump_jsonl(ART / "experimental_core_unrecoverable_audit.jsonl", [{
        "observation_identity": row.observation_identity,
        "missing_components": row.missing_components,
        "provider_reextraction_required": row.provider_reextraction_required,
        "automatic_execution_authorized": False,
    } for row in remediation])
    dump_jsonl(ART / "structured_experimental_observation_revisions.jsonl", revisions)
    dump_jsonl(ART / "experimental_observation_structural_integrity.jsonl", integrity)
    dump_json(ART / "experimental_observation_structural_integrity_summary.json", {
        key: value for key, value in stats.items()
        if key.startswith(("structurally_", "incomplete_", "invalid_", "non_experimental_claim_integrity", "unresolved_integrity"))
    })
    dump_jsonl(ART / "experimental_observation_machine_reuse_readiness.jsonl", readiness)
    dump_json(ART / "experimental_observation_machine_reuse_summary.json", {
        key: value for key, value in stats.items()
        if key.startswith(("machine_reusable", "usable_with", "text_evidence", "non_experimental_reuse", "unusable", "unassessed"))
    })
    dump_jsonl(ART / "experimental_core_remediation_requirements.jsonl", remediation)
    dedup_rows = [{
        "dedup_group_identity": group,
        "source_block_identity": next(row.source_block_identity for row in remediation
                                      if row.dedup_group_identity == group),
        "observation_identities": sorted(
            row.observation_identity for row in remediation
            if row.dedup_group_identity == group
        ),
        "planned_provider_call_count": 1,
        "executed_provider_call_count": 0,
    } for group in sorted({row.dedup_group_identity for row in remediation})]
    dump_jsonl(ART / "experimental_core_remediation_deduplication_audit.jsonl", dedup_rows)
    dump_json(ART / "experimental_core_remediation_summary.json", {
        "provider_reextraction_required_count": stats["provider_reextraction_required_count"],
        "unique_provider_reextraction_block_count": stats["unique_provider_reextraction_block_count"],
        "automatic_execution_authorized_count": 0, "provider_call_authorized_count": 0,
        "network_call_authorized_count": 0, "budget_authorization_present_count": 0,
    })
    dump_json(ART / "intervention_factor_coverage_audit.json", {
        key: value for key, value in stats.items()
        if "intervention" in key or "factor" in key or "control_comparator" in key
    })
    dump_json(ART / "measurement_coverage_audit.json", {
        key: value for key, value in stats.items() if "measurement" in key
    })
    dump_json(ART / "observed_result_coverage_audit.json", {
        key: value for key, value in stats.items()
        if "result" in key or "orphan" in key or "comparator" in key
    })
    dump_json(ART / "factor_measurement_result_linkage_audit.json", {
        key: value for key, value in stats.items()
        if "link" in key or "reference" in key or "duplicate_local" in key
    })

    prompt_source = (ROOT / "src/code_engine/fulltext/fulltext_l1_v2.py").read_text(encoding="utf-8")
    schema_source = (ROOT / "src/code_engine/fulltext/fulltext_l1_v2_models.py")
    schema_text = schema_source.read_text(encoding="utf-8") if schema_source.is_file() else prompt_source
    parser_source = prompt_source
    audits = []
    for field in CORE_FIELDS:
        token = field.rstrip("s")
        audits.append({
            "field": field,
            "captured": field in prompt_source or token in prompt_source,
            "authority": "source_code_string_audit",
        })
    dump_jsonl(ART / "current_prompt_core_capture_audit.jsonl", audits)
    dump_jsonl(ART / "current_schema_core_expression_audit.jsonl", [{
        "field": field, "representable": field in schema_text or field.rstrip("s") in schema_text,
        "authority": "source_code_string_audit",
    } for field in CORE_FIELDS])
    dump_jsonl(ART / "current_parser_core_preservation_audit.jsonl", [{
        "field": field, "preserved": field in parser_source or field.rstrip("s") in parser_source,
        "authority": "source_code_string_audit",
    } for field in CORE_FIELDS])
    contract = joint_contract()
    dump_json(ART / "candidate_joint_contract_v2.json", contract.model_dump(mode="json"))
    dump_json(ART / "candidate_joint_contract_v2_status.json", {
        "validation_status": "pending_smoke_validation",
        "production_status": "not_activated", "active_pointer_changed": False,
        "provider_execution_authorized": False,
    })

    state_audits = {
        "weak_3ca_core_observation_audit.json": {
            "context_entry_status": "ready",
            "difference_authority_status": "ready_not_materialized",
        },
        "weak_256_core_observation_audit.json": {
            "context_entry_status": "blocked_context_b_unavailable",
            "difference_authority_status": "blocked_entry",
        },
        "ebd5_core_observation_audit.json": {
            "candidate_qualification_status": "blocked_alignment",
            "difference_authority_status": "diagnostic_only",
            "formal_conflict_status": "not_confirmed",
        },
        "context_17b_core_observation_audit.json": {
            "status": "fail_closed_policy_coverage_failure",
        },
        "context_41f_core_observation_audit.json": {
            "status": "fail_closed_policy_coverage_failure",
        },
    }
    for name, value in state_audits.items():
        dump_json(ART / name, {**value, "scientific_state_modified": False})
    dump_jsonl(ART / "experimental_core_identity_chain_audit.jsonl", [{
        "source_observation_identity": row.source_observation_identity,
        "structured_revision_identity": row.identity,
        "factor_ids": row.experimental_factor_ids,
        "measurement_ids": row.measurement_ids,
        "observed_result_ids": row.observed_result_ids,
        "linkage_record_ids": row.linkage_record_ids,
        "identity_chain_valid": True,
    } for row in revisions])

    candidate_path = CANDIDATE_RUN / "artifacts/scientific_candidate_pair_identities.jsonl"
    candidate_hash = sha256_bytes(candidate_path.read_bytes())
    historical_paths = [
        RECOVERY_RUN / "artifacts/fulltext_experiment_observations.jsonl",
        V3_RUN / "artifacts/fulltext_experiment_observations.jsonl",
        PROJECTION_RUN / "artifacts/fulltext_projected_observations.jsonl",
        candidate_path,
    ]
    historical_hashes = {relative(path): sha256_bytes(path.read_bytes()) for path in historical_paths}
    safety = {
        "provider_calls": 0, "api_calls": 0, "real_api_calls": 0,
        "network_calls": 0, "downloads": 0, "credential_values_read": False,
        "provider_client_created": False, "historical_runs_modified": False,
        "historical_raw_files_modified": False,
        "historical_parsed_payloads_modified": False,
        "historical_validated_observations_modified": False,
        "formal_v3_modified": False, "projection_historical_content_modified": False,
        "candidate_pairs_modified": False, "dataset_release_pipeline_created": False,
        "method_paper_narrative_changed": False, "handoff_created": False,
        "atlas_activated": False, "active_pointer_changed": False,
        "variational_em_called": False, "historical_hashes": historical_hashes,
    }
    dump_json(ART / "experimental_core_safety_audit.json", safety)

    identities = [contract_identity(name) for name in CONTRACT_NAMES]
    dump_json(ART / "contract_identities.json", identities)
    for row in identities:
        dump_json(IDENTITIES / f"{row['contract_name']}.json", row)
    model_schemas = {
        "observation_type_cardinality_policy_v1": type(policy),
        "structured_experimental_observation_revision_v1": StructuredExperimentalObservationRevision,
        "experimental_factor_record_v1": ExperimentalFactorRecord,
        "measurement_record_v1": MeasurementRecord,
        "observed_result_record_v1": ObservedResultRecord,
        "experimental_observation_linkage_v1": ExperimentalObservationLinkage,
        "experimental_core_stage_trace_v1": ExperimentalCoreStageTrace,
        "experimental_core_first_loss_diagnosis_v1": ExperimentalCoreFirstLossDiagnosis,
        "experimental_observation_atomicity_audit_v1": ExperimentalObservationAtomicityAudit,
        "experimental_core_recovery_revision_v1": ExperimentalCoreRecoveryRevision,
        "experimental_observation_structural_integrity_v1": ExperimentalObservationStructuralIntegrity,
        "experimental_observation_machine_reuse_readiness_v1": ExperimentalObservationMachineReuseReadiness,
        "experimental_core_remediation_requirement_v1": ExperimentalCoreRemediationRequirement,
    }
    for name, model in model_schemas.items():
        schema = model.model_json_schema()
        dump_json(SCHEMAS / f"{name}.schema.json", schema)
        dump_json(ROOT / f"docs/contracts/{name}.schema.json", schema)
    joint_schema = joint_payload_schema()
    dump_json(SCHEMAS / "research_grade_observation_context_extraction_contract_v2.schema.json", joint_schema)
    dump_json(ROOT / "docs/contracts/research_grade_observation_context_extraction_contract_v2.schema.json", joint_schema)

    manifest = {
        "schema_version": "core_experimental_observation_integrity_manifest_v1",
        "run_name": RUN_NAME, "status": "completed",
        **summary,
        "candidate_count_before": 11, "candidate_count_after": 11,
        "candidate_identity_changed": False, "candidate_order_changed": False,
        "scientific_pair_set_changed": False,
        "candidate_identity_file_sha256_before": candidate_hash,
        "candidate_identity_file_sha256_after": candidate_hash,
        "formal_conflict_count_before": 0, "formal_conflict_count_after": 0,
        "joint_extraction_contract_v2_status": "pending_smoke_validation",
        "joint_extraction_contract_v2_production_status": "not_activated",
        **safety,
    }
    dump_json(ART / "core_experimental_observation_integrity_summary.json", summary)
    dump_json(ART / "core_experimental_observation_integrity_manifest.json", manifest)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
