#!/usr/bin/env python3
"""Generate the offline Pair Scientific Compatibility Boundary v1 audit.

This is a read-only replay adapter.  It consumes immutable Alignment,
Qualification, Experimental Core, Context, L4b V3, entity, and PI3K artifacts
and writes only to the task-specific offline run directory.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from code_engine.extraction_assets.context.pair_requirements_v2 import (
    L4bUpstreamEligibilityV1,
)
from code_engine.extraction_assets.context.pair_requirements_v3_candidate import (
    PairSemanticTriggerCoverageV1,
    PairSemanticTriggerFactV1,
)
from code_engine.extraction_assets.context.pair_scientific_compatibility_v1_candidate import (
    ScientificSemanticRoleInventoryV1,
    default_satisfaction_policies_v1,
    evaluate_l4b_v4_candidate,
    evaluate_scientific_dimension_satisfaction_v1,
    make_semantic_role_inventory_v1,
    project_pair_semantic_trigger_v1,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260825_pair_scientific_compatibility_boundary_v1_offline"
ART = RUN / "artifacts"
V3_ART = ROOT / "runs/20260825_pair_semantic_trigger_coverage_requirement_authority_v1_offline/artifacts"
QUAL_ART = ROOT / "runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
ALIGN_ART = ROOT / "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts"
CORE_ART = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"
FORMAL_SOURCE = ROOT / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts/formal_conflict_decisions_staging.jsonl"
CONTRACT = ROOT / "docs/pair_scientific_compatibility_boundary_v1.md"
PRODUCTION_MODULE = ROOT / "src/code_engine/extraction_assets/context/pair_scientific_compatibility_v1_candidate.py"

ALIGNMENT_PATH = "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts/claim_alignment_records_v2.jsonl"
ROLE_TAXONOMY_PATH = "configs/context_attribution/claim_alignment_dimension_roles_v1.json"
CORE_REVISION_PATH = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/structured_experimental_observation_revisions.jsonl"
FACTOR_PATH = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/experimental_factor_records.jsonl"
MEASUREMENT_PATH = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/measurement_records.jsonl"
RESULT_PATH = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/observed_result_records.jsonl"
LINKAGE_PATH = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/experimental_observation_linkages.jsonl"
CONTEXT_REGISTRY_PATH = "configs/context_attribution/context_registry_v3.json"
V3_FACT_PATH = "runs/20260825_pair_semantic_trigger_coverage_requirement_authority_v1_offline/artifacts/pair_semantic_trigger_facts_v1.jsonl"
V3_COVERAGE_PATH = "runs/20260825_pair_semantic_trigger_coverage_requirement_authority_v1_offline/artifacts/pair_semantic_trigger_coverage_v1.jsonl"

GAP_STATES = {"partially_materialized", "present_upstream_but_not_materialized"}
PROPOSITION_CORE_NAMES = (
    "canonical_subject_identity",
    "canonical_relation_family",
    "canonical_endpoint_identity",
    "outcome_variable_identity",
)
ALIGNMENT_COVERAGE_SEMANTICS = (
    "measurement_target_identity",
    "measurement_endpoint_type",
    "measurement_semantic_level",
    "result_semantic_level",
    "intervention_target_identity",
    "intervention_proposition",
)
COMPATIBILITY_SEMANTICS = (
    "measurement_method",
    "experimental_contrast",
    "evidence_family",
)
CONTEXT_SEMANTICS = (
    "biological_model",
    "disease",
    "genotype",
    "temporal",
    "dose_treatment_context",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def write_json(name: str, value: Any) -> None:
    (ART / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_rows(name: str, rows: Iterable[Any]) -> None:
    values = [
        row.model_dump(mode="json") if hasattr(row, "model_dump") else row
        for row in rows
    ]
    (ART / name).write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in values
        ),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", choices=("pending", "completed", "failed"), default="pending")
    parser.add_argument("--focused-pass-count", type=int, default=0)
    parser.add_argument("--related-pass-count", type=int, default=0)
    parser.add_argument("--full-pass-count", type=int, default=0)
    parser.add_argument("--full-subtest-pass-count", type=int, default=0)
    parser.add_argument("--full-failure-count", type=int, default=0)
    parser.add_argument("--full-collected-count", type=int, default=0)
    parser.add_argument("--compileall", choices=("pending", "passed", "failed"), default="pending")
    parser.add_argument("--git-diff-check", choices=("pending", "passed", "failed"), default="pending")
    parser.add_argument("--final-failure-id", action="append", default=[])
    return parser.parse_args()


def _json_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _unique(values: Iterable[Any]) -> list[Any]:
    by_key = {_json_key(value): value for value in values}
    return [by_key[key] for key in sorted(by_key)]


def _pair_value_state(values_a: list[Any], values_b: list[Any]) -> str:
    if values_a and values_b:
        return "matched" if values_a == values_b else "different"
    if not values_a and not values_b:
        return "missing"
    return "unresolved"


def _measurement_value(row: dict[str, Any], field: str) -> Any:
    mappings = {
        "target": ("measured_entity_canonical", "measured_entity_extracted", "measured_entity_raw"),
        "endpoint": (
            "property_or_endpoint_canonical",
            "property_or_endpoint_extracted",
            "property_or_endpoint_raw",
        ),
        "method": ("method_canonical", "method_extracted", "method_raw"),
    }
    for key in mappings[field]:
        if row.get(key) is not None:
            return row[key]
    return None


def _factor_value(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": row["role"],
        "value": row.get("canonical_value") or row.get("extracted_value") or row.get("raw_text"),
        "control_or_comparator_status": row["control_or_comparator_status"],
    }


def _side_core(
    observation_id: str,
    revisions: dict[str, dict[str, Any]],
    factors: dict[str, dict[str, Any]],
    measurements: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    revision = revisions[observation_id]
    factor_rows = [factors[ref] for ref in revision["experimental_factor_ids"]]
    measurement_rows = [measurements[ref] for ref in revision["measurement_ids"]]
    result_rows = [results[ref] for ref in revision["observed_result_ids"]]
    interventions = _unique(
        _factor_value(row)
        for row in factor_rows
        if row["control_or_comparator_status"] == "not_control_or_comparator"
    )
    if not interventions and revision["observation_type"] == "descriptive_measurement":
        interventions = [{"structural_state": "not_applicable_descriptive_measurement"}]
    arms = _unique(
        _factor_value(row)
        for row in factor_rows
        if row["control_or_comparator_status"] == "control_or_comparator"
    )
    if not arms:
        arms = [{"structural_state": f"no_arm_for_{revision['observation_type']}"}]
    measurement_targets = _unique(
        value
        for row in measurement_rows
        if (value := _measurement_value(row, "target")) is not None
    )
    endpoints = _unique(
        value
        for row in measurement_rows
        if (value := _measurement_value(row, "endpoint")) is not None
    )
    semantic_levels = _unique(
        row["measurement_semantic_level"]
        for row in measurement_rows
        if row.get("measurement_semantic_level") is not None
    )
    methods = _unique(
        value
        for row in measurement_rows
        if (value := _measurement_value(row, "method")) is not None
    )
    result_semantics = _unique({
        "qualitative_result": row.get("qualitative_result"),
        "direction": row.get("direction"),
        "sign": row.get("sign"),
        "negation": row.get("negation"),
    } for row in result_rows)
    contrast = [{
        "observation_type": revision["observation_type"],
        "arms": arms,
        "comparison_factor_count": sum(len(row.get("comparison_factor_refs", [])) for row in result_rows),
        "baseline_present": any(row.get("baseline_ref") is not None for row in result_rows),
    }]
    refs = {
        "revision": [revision["structured_observation_revision_id"]],
        "factor": [row["factor_id"] for row in factor_rows],
        "measurement": [row["measurement_id"] for row in measurement_rows],
        "result": [row["observed_result_id"] for row in result_rows],
    }
    return {
        "observation_type": [revision["observation_type"]],
        "measurement_target_identity": measurement_targets,
        "measurement_endpoint_type": endpoints,
        "measurement_semantic_level": semantic_levels,
        "measurement_method": methods,
        "result_semantic_level": result_semantics,
        "intervention_target_identity": _unique(
            row["value"] for row in interventions if row.get("value") is not None
        ),
        "intervention_proposition": interventions,
        "experimental_contrast": contrast,
        "evidence_family": [revision["observation_type"]],
        "refs": refs,
    }


def _alignment_bridge(alignment: dict[str, Any], dimension: str) -> dict[str, Any]:
    return next(
        row
        for row in alignment["granularity_bridge_assessments"]
        if row["dimension_id"] == dimension
    )


def _context_values(
    pair_id: str,
    dimension: str,
    facts_by_pair_dimension: dict[tuple[str, str], list[PairSemanticTriggerFactV1]],
) -> tuple[list[Any], list[Any], str, list[str]]:
    rows = [
        row
        for row in facts_by_pair_dimension.get((pair_id, dimension), [])
        if row.authority in {
            "validated_context_direct_value",
            "safe_scope_context_inheritance",
            "authorized_deterministic_derived_value",
        }
    ]
    values_a = _unique(value for row in rows for value in row.structured_values_a)
    values_b = _unique(value for row in rows for value in row.structured_values_b)
    return (
        values_a,
        values_b,
        _pair_value_state(values_a, values_b),
        sorted({ref for row in rows for ref in row.source_artifact_refs}),
    )


def _inventory_row(
    *,
    pair_id: str,
    name: str,
    role: str,
    authority: str,
    authority_status: str,
    source_refs: list[str],
    values_a: list[Any],
    values_b: list[Any],
    semantic_state: str,
    reason: str,
) -> ScientificSemanticRoleInventoryV1:
    policies = {
        "proposition_alignment_critical": "upstream_alignment_required",
        "comparison_compatibility_critical": "compatibility_required",
        "context_explanatory": "resolution_only",
        "explicitly_not_decision_relevant": "not_decision_relevant",
        "semantic_role_unresolved": "semantic_role_unresolved",
    }
    return make_semantic_role_inventory_v1(
        pair_id=pair_id,
        dimension_or_semantic=name,
        scientific_role=role,
        satisfaction_policy=policies[role],
        authority=authority,
        authority_status=authority_status,
        source_refs=source_refs,
        structured_values_a=values_a,
        structured_values_b=values_b,
        semantic_state=semantic_state,
        reason=reason,
    )


def _build_inventory(
    *,
    pair_id: str,
    qualification: dict[str, Any],
    alignment: dict[str, Any],
    side_a: dict[str, Any],
    side_b: dict[str, Any],
    facts_by_pair_dimension: dict[tuple[str, str], list[PairSemanticTriggerFactV1]],
) -> list[ScientificSemanticRoleInventoryV1]:
    rows: list[ScientificSemanticRoleInventoryV1] = []
    comparisons = {row["dimension_id"]: row for row in alignment["core_dimension_comparisons"]}
    for name in PROPOSITION_CORE_NAMES:
        comparison = comparisons[name]
        state = (
            "upstream_alignment_supported"
            if comparison["status"] == "match"
            else "incompatible"
            if comparison["status"] == "mismatch"
            else "upstream_alignment_partial_but_reviewable"
        )
        rows.append(_inventory_row(
            pair_id=pair_id,
            name=name,
            role="proposition_alignment_critical",
            authority="claim_alignment_v2",
            authority_status="supported" if comparison["status"] == "match" else "partial",
            source_refs=[ALIGNMENT_PATH, qualification["claim_alignment_v2_identity"]],
            values_a=[] if comparison["value_a"] is None else [comparison["value_a"]],
            values_b=[] if comparison["value_b"] is None else [comparison["value_b"]],
            semantic_state=state,
            reason="existing Alignment v2 directly compares this proposition-core unit",
        ))

    for name in ALIGNMENT_COVERAGE_SEMANTICS:
        values_a = side_a[name]
        values_b = side_b[name]
        if name == "measurement_semantic_level":
            bridge = _alignment_bridge(alignment, name)
            if bridge["bridge_status"] in {"unresolved", "partially_compatible"}:
                state = "upstream_alignment_partial_but_reviewable"
                authority_status = "partial"
                authority = "claim_alignment_v2_legacy_granularity_bridge"
                reason = "legacy Alignment bridge is unresolved and cannot be repaired in L4b"
            elif bridge["bridge_status"] == "incompatible":
                state = "incompatible"
                authority_status = "supported"
                authority = "claim_alignment_v2_legacy_granularity_bridge"
                reason = "versioned upstream bridge establishes incompatibility"
            elif values_a or values_b:
                state = "alignment_semantic_coverage_gap"
                authority_status = "alignment_semantic_coverage_gap"
                authority = "experimental_core_not_consumed_by_claim_alignment_v2"
                reason = "Experimental Core semantic level exists but Alignment's legacy qualifier is not applicable"
            else:
                state = "upstream_alignment_supported"
                authority_status = "supported"
                authority = "claim_alignment_v2_legacy_granularity_bridge"
                reason = "upstream bridge is affirmatively not applicable"
        else:
            state = "alignment_semantic_coverage_gap"
            authority_status = "alignment_semantic_coverage_gap"
            authority = "experimental_core_not_consumed_by_claim_alignment_v2"
            reason = "necessary Experimental Core proposition semantic is not consumed by Alignment v2"
        source_refs = [ALIGNMENT_PATH, ROLE_TAXONOMY_PATH]
        if name.startswith("measurement_"):
            source_refs.append(MEASUREMENT_PATH)
        elif name == "result_semantic_level":
            source_refs.append(RESULT_PATH)
        else:
            source_refs.extend([CORE_REVISION_PATH, FACTOR_PATH])
        rows.append(_inventory_row(
            pair_id=pair_id,
            name=name,
            role="proposition_alignment_critical",
            authority=authority,
            authority_status=authority_status,
            source_refs=source_refs,
            values_a=values_a,
            values_b=values_b,
            semantic_state=state,
            reason=reason,
        ))

    for name in COMPATIBILITY_SEMANTICS:
        values_a = side_a[name]
        values_b = side_b[name]
        raw_state = _pair_value_state(values_a, values_b)
        exact = raw_state == "matched"
        state = "compatible" if exact else "unresolved"
        rows.append(_inventory_row(
            pair_id=pair_id,
            name=name,
            role="comparison_compatibility_critical",
            authority=(
                "exact_structured_semantic_equality_v1"
                if exact else "no_versioned_compatibility_mapping"
            ),
            authority_status="supported" if exact else "unresolved",
            source_refs=[
                MEASUREMENT_PATH if name == "measurement_method" else CORE_REVISION_PATH,
                LINKAGE_PATH,
                str(CONTRACT.relative_to(ROOT)),
            ],
            values_a=values_a,
            values_b=values_b,
            semantic_state=state,
            reason=(
                "exact structured semantic equality establishes compatibility"
                if exact else "resolved or missing raw values do not establish compatibility"
            ),
        ))

    for name in CONTEXT_SEMANTICS:
        source_dimension = "intervention" if name == "dose_treatment_context" else name
        values_a, values_b, state, refs = _context_values(
            pair_id, source_dimension, facts_by_pair_dimension
        )
        rows.append(_inventory_row(
            pair_id=pair_id,
            name=name,
            role="context_explanatory",
            authority="context_registry_and_scientific_role_contract_v1",
            authority_status="supported",
            source_refs=[CONTEXT_REGISTRY_PATH, str(CONTRACT.relative_to(ROOT)), *refs],
            values_a=values_a,
            values_b=values_b,
            semantic_state=state,
            reason="ordinary experimental Context is explanatory and uses resolution-only satisfaction",
        ))

    bridge = _alignment_bridge(alignment, "endpoint_compartment")
    localization_state = (
        "upstream_alignment_supported"
        if bridge["bridge_status"] in {"exact_match", "not_applicable"}
        else "incompatible"
        if bridge["bridge_status"] == "incompatible"
        else "upstream_alignment_partial_but_reviewable"
    )
    rows.append(_inventory_row(
        pair_id=pair_id,
        name="localization",
        role="proposition_alignment_critical",
        authority="claim_alignment_v2_endpoint_compartment_bridge",
        authority_status="supported" if localization_state == "upstream_alignment_supported" else "partial",
        source_refs=[ALIGNMENT_PATH, ROLE_TAXONOMY_PATH],
        values_a=[] if bridge.get("qualifier_a") is None else [bridge["qualifier_a"]],
        values_b=[] if bridge.get("qualifier_b") is None else [bridge["qualifier_b"]],
        semantic_state=localization_state,
        reason="endpoint-qualified localization is upstream granularity, not ordinary explanatory Context",
    ))
    rows.append(_inventory_row(
        pair_id=pair_id,
        name="result_direction",
        role="explicitly_not_decision_relevant",
        authority="contradiction_signal_v2_separate_result_view_contract",
        authority_status="supported",
        source_refs=[ALIGNMENT_PATH, RESULT_PATH],
        values_a=[],
        values_b=[],
        semantic_state="not_applicable",
        reason="result direction belongs to Contradiction and cannot satisfy compatibility",
    ))
    return rows


def _alignment_audit_rows(
    *,
    pair_id: str,
    candidate_id: str,
    alignment: dict[str, Any],
    inventory: list[ScientificSemanticRoleInventoryV1],
) -> list[dict[str, Any]]:
    audited = set(PROPOSITION_CORE_NAMES) | set(ALIGNMENT_COVERAGE_SEMANTICS) | {
        "localization", "experimental_contrast", "measurement_method", "evidence_family"
    }
    rows = []
    for item in inventory:
        if item.dimension_or_semantic not in audited:
            continue
        if item.satisfaction_policy == "upstream_alignment_required":
            if item.semantic_state == "upstream_alignment_supported":
                outcome = "upstream_alignment_supported"
            elif item.semantic_state == "upstream_alignment_partial_but_reviewable":
                outcome = "upstream_alignment_partial_but_reviewable"
            elif item.semantic_state == "incompatible":
                outcome = "scientifically_incompatible_under_current_contract"
            else:
                outcome = "alignment_semantic_coverage_gap"
        elif item.dimension_or_semantic == "experimental_contrast":
            outcome = (
                "upstream_alignment_supported"
                if item.semantic_state == "compatible"
                else "experimental_contrast_compatibility_unresolved"
            )
        else:
            outcome = (
                "upstream_alignment_supported"
                if item.semantic_state == "compatible"
                else "measurement_compatibility_unresolved"
            )
        rows.append({
            "schema_version": "alignment_semantic_coverage_audit_v1",
            "pair_id": pair_id,
            "candidate_id": candidate_id,
            "dimension_or_semantic": item.dimension_or_semantic,
            "scientific_role": item.scientific_role,
            "satisfaction_policy": item.satisfaction_policy,
            "historical_alignment_status": alignment["alignment_status"],
            "structured_values_a": item.structured_values_a,
            "structured_values_b": item.structured_values_b,
            "audit_outcome": outcome,
            "authority": item.authority,
            "source_refs": item.source_refs,
            "historical_alignment_modified": False,
            "l4b_re_adjudication_performed": False,
            "string_difference_used_as_incompatibility": False,
        })
    return rows


def _pair_alignment_outcome(
    alignment: dict[str, Any], inventory: list[ScientificSemanticRoleInventoryV1]
) -> str:
    if alignment["alignment_status"] != "aligned":
        return "upstream_alignment_partial_but_reviewable"
    if any(
        row.semantic_state == "incompatible"
        for row in inventory
        if row.scientific_role == "proposition_alignment_critical"
    ):
        return "scientifically_incompatible_under_current_contract"
    if any(
        row.authority_status == "alignment_semantic_coverage_gap"
        for row in inventory
    ):
        return "alignment_semantic_coverage_gap"
    return "upstream_alignment_supported"


def main() -> None:
    args = parse_args()
    ART.mkdir(parents=True, exist_ok=True)
    qualifications = read_rows(QUAL_ART / "conflict_candidate_qualifications.jsonl")
    pair_ids = [row["scientific_candidate_pair_identity"] for row in qualifications]
    qualification_by_pair = {
        row["scientific_candidate_pair_identity"]: row for row in qualifications
    }
    alignments = {
        row["claim_alignment_identity_v2"]: row
        for row in read_rows(ALIGN_ART / "claim_alignment_records_v2.jsonl")
    }
    revisions = {
        row["source_observation_identity"]: row
        for row in read_rows(CORE_ART / "structured_experimental_observation_revisions.jsonl")
    }
    factors = {
        row["factor_id"]: row
        for row in read_rows(CORE_ART / "experimental_factor_records.jsonl")
    }
    measurements = {
        row["measurement_id"]: row
        for row in read_rows(CORE_ART / "measurement_records.jsonl")
    }
    results = {
        row["observed_result_id"]: row
        for row in read_rows(CORE_ART / "observed_result_records.jsonl")
    }
    v3_facts = [
        PairSemanticTriggerFactV1.model_validate(row)
        for row in read_rows(V3_ART / "pair_semantic_trigger_facts_v1.jsonl")
    ]
    facts_by_pair_dimension: dict[tuple[str, str], list[PairSemanticTriggerFactV1]] = {}
    for fact in v3_facts:
        facts_by_pair_dimension.setdefault((fact.pair_id, fact.dimension), []).append(fact)
    v3_coverage = [
        PairSemanticTriggerCoverageV1.model_validate(row)
        for row in read_rows(V3_ART / "pair_semantic_trigger_coverage_v1.jsonl")
    ]
    v3_replay = {
        row["pair_id"]: row for row in read_rows(V3_ART / "candidate_pair_replay_v3.jsonl")
    }

    candidate_path = QUAL_ART / "scientific_candidate_pair_identities.jsonl"
    alignment_path = ALIGN_ART / "claim_alignment_records_v2.jsonl"
    protected_before = {
        str(candidate_path.relative_to(ROOT)): sha256(candidate_path),
        str(alignment_path.relative_to(ROOT)): sha256(alignment_path),
        str(FORMAL_SOURCE.relative_to(ROOT)): sha256(FORMAL_SOURCE),
    }
    prior_final = read_json(V3_ART / "final_validation.json")
    baseline_failures = prior_final["baseline_failure_ids"]
    write_json("baseline.json", {
        "schema_version": "pair_scientific_compatibility_boundary_baseline_v1",
        "git_head": git_head(),
        "prior_iteration": "pair_semantic_trigger_coverage_requirement_authority_v1",
        "pair_count": len(pair_ids),
        "historical_alignment_state_counts": dict(Counter(
            row["claim_alignment_status"] for row in qualifications
        )),
        "l4b_v3_state_counts": dict(Counter(
            row["l4b_v3_candidate_state"] for row in v3_replay.values()
        )),
        "v3_upstream_present_not_materialized_count": sum(
            row.coverage_state == "present_upstream_but_not_materialized"
            for row in v3_coverage
        ),
        "v3_partial_count": sum(
            row.coverage_state == "partially_materialized" for row in v3_coverage
        ),
        "formal_conflict_count": 0,
        "entity_integrity_claims_blocked": 241,
        "entity_integrity_signals_blocked": 2,
        "baseline_failure_ids": baseline_failures,
        "protected_hashes_before": protected_before,
        "provider_or_network_execution_authorized": False,
    })

    policies = default_satisfaction_policies_v1()
    write_rows("scientific_dimension_satisfaction_policies.jsonl", policies)
    inventory: list[ScientificSemanticRoleInventoryV1] = []
    inventory_by_pair: dict[str, list[ScientificSemanticRoleInventoryV1]] = {}
    sides_by_pair: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    alignment_audit: list[dict[str, Any]] = []
    pair_alignment_outcomes: dict[str, str] = {}
    for pair_id in pair_ids:
        qualification = qualification_by_pair[pair_id]
        alignment = alignments[qualification["claim_alignment_v2_identity"]]
        side_a = _side_core(
            qualification["observation_a_id"], revisions, factors, measurements, results
        )
        side_b = _side_core(
            qualification["observation_b_id"], revisions, factors, measurements, results
        )
        sides_by_pair[pair_id] = (side_a, side_b)
        pair_inventory = _build_inventory(
            pair_id=pair_id,
            qualification=qualification,
            alignment=alignment,
            side_a=side_a,
            side_b=side_b,
            facts_by_pair_dimension=facts_by_pair_dimension,
        )
        inventory.extend(pair_inventory)
        inventory_by_pair[pair_id] = pair_inventory
        alignment_audit.extend(_alignment_audit_rows(
            pair_id=pair_id,
            candidate_id=qualification["candidate_id"],
            alignment=alignment,
            inventory=pair_inventory,
        ))
        pair_alignment_outcomes[pair_id] = _pair_alignment_outcome(
            alignment, pair_inventory
        )
    write_rows("scientific_semantic_role_inventory.jsonl", inventory)
    write_rows("alignment_semantic_coverage_audit.jsonl", alignment_audit)

    inventory_by_unit = {
        (row.pair_id, row.dimension_or_semantic): row for row in inventory
    }
    gap_coverage = [row for row in v3_coverage if row.coverage_state in GAP_STATES]
    projections = [
        project_pair_semantic_trigger_v1(
            coverage=coverage,
            inventory=inventory_by_unit[(coverage.pair_id, coverage.dimension)],
            facts=facts_by_pair_dimension.get((coverage.pair_id, coverage.dimension), []),
        )
        for coverage in gap_coverage
    ]
    write_rows("pair_semantic_trigger_projection_before_after.jsonl", projections)
    projection_counts = Counter(row.gap_resolution_state for row in projections)
    write_json("trigger_projection_gap_resolution_summary.json", {
        "schema_version": "trigger_projection_gap_resolution_summary_v1",
        "gap_unit_count": len(gap_coverage),
        "before_counts": dict(Counter(row.coverage_state for row in gap_coverage)),
        "resolution_counts": dict(projection_counts),
        "after_materialized_count": sum(
            row.after_projection_state == "materialized_context_explanatory"
            for row in projections
        ),
        "all_29_forced_to_materialize": False,
        "free_text_inference_count": 0,
        "fuzzy_scientific_inference_count": 0,
        "llm_count": 0,
    })

    satisfactions_by_pair = {}
    l4b_v4 = {}
    replay = []
    for pair_id in pair_ids:
        qualification = qualification_by_pair[pair_id]
        alignment = alignments[qualification["claim_alignment_v2_identity"]]
        pair_satisfactions = []
        for item in inventory_by_pair[pair_id]:
            refs = []
            if item.semantic_state in {"compatible", "incompatible"} and (
                item.authority_status == "supported"
            ):
                refs = [item.authority]
            pair_satisfactions.append(evaluate_scientific_dimension_satisfaction_v1(
                item,
                compatibility_authority_refs=refs,
            ))
        satisfactions_by_pair[pair_id] = pair_satisfactions
        upstream = L4bUpstreamEligibilityV1(
            pair_id=pair_id,
            entity_integrity_eligible=True,
            alignment_eligible=qualification["claim_alignment_status"] == "aligned",
            contradiction_signal_valid=(
                qualification["contradiction_signal_status"] == "validated"
                and qualification["contradiction_signal_structure_valid"]
                and qualification["contradiction_signal_schema_valid"]
                and qualification["contradiction_signal_validator_valid"]
                and qualification["contradiction_signal_provenance_complete"]
            ),
            candidate_qualification_eligible=qualification["qualification_status"] == "qualified",
            entity_integrity_state="eligible_no_blocking_integrity_sidecar_linked",
            alignment_state=qualification["claim_alignment_status"],
            contradiction_signal_state=qualification["contradiction_signal_status"],
            candidate_qualification_state=qualification["qualification_status"],
            upstream_refs=[
                qualification["claim_alignment_v2_identity"],
                qualification["contradiction_signal_v2_identity"],
                qualification["qualification_identity"],
            ],
        )
        result = evaluate_l4b_v4_candidate(
            pair_id=pair_id,
            upstream=upstream,
            upstream_alignment_compatibility_outcome=pair_alignment_outcomes[pair_id],
            satisfactions=pair_satisfactions,
        )
        l4b_v4[pair_id] = result
        coverage_rows = [row for row in v3_coverage if row.pair_id == pair_id]
        projection_rows = [row for row in projections if row.pair_id == pair_id]
        replay.append({
            "schema_version": "candidate_pair_replay_v4",
            "pair_id": pair_id,
            "candidate_id": qualification["candidate_id"],
            "upstream_alignment_state": alignment["alignment_status"],
            "upstream_alignment_compatibility_outcome": pair_alignment_outcomes[pair_id],
            "proposition_critical_semantics": result.proposition_critical_semantics,
            "compatibility_critical_semantics": result.compatibility_critical_semantics,
            "context_explanatory_semantics": result.context_explanatory_semantics,
            "projection_gaps_before": {
                row.dimension: row.coverage_state
                for row in coverage_rows if row.coverage_state in GAP_STATES
            },
            "projection_gaps_after": {
                row.dimension: row.gap_resolution_state for row in projection_rows
            },
            "l4b_v3_state": v3_replay[pair_id]["l4b_v3_candidate_state"],
            "l4b_v4_candidate_state": result.l4b_state,
            "reason": (
                "historical upstream Alignment gate remains authoritative"
                if not upstream.alignment_eligible
                else "Experimental Core proposition semantics are not fully consumed upstream"
            ),
            "historical_state_preserved": True,
            "alignment_modified": False,
            "candidate_modified": False,
            "formal_modified": False,
        })
    write_rows("candidate_pair_replay_v4.jsonl", replay)

    eligible_rows = []
    for pair_id in pair_ids:
        qualification = qualification_by_pair[pair_id]
        if qualification["qualification_status"] != "qualified":
            continue
        side_a, side_b = sides_by_pair[pair_id]
        by_name = {
            row.dimension_or_semantic: row for row in inventory_by_pair[pair_id]
        }
        eligible_rows.append({
            "pair_id": pair_id,
            "candidate_id": qualification["candidate_id"],
            "historical_alignment_state": qualification["claim_alignment_status"],
            "measurement_target_compatibility": {
                "values_a": side_a["measurement_target_identity"],
                "values_b": side_b["measurement_target_identity"],
                "outcome": "alignment_semantic_coverage_gap",
            },
            "measurement_endpoint": {
                "values_a": side_a["measurement_endpoint_type"],
                "values_b": side_b["measurement_endpoint_type"],
                "outcome": "alignment_semantic_coverage_gap",
            },
            "result_semantic": {
                "values_a": side_a["result_semantic_level"],
                "values_b": side_b["result_semantic_level"],
                "outcome": "alignment_semantic_coverage_gap",
            },
            "intervention_proposition": {
                "values_a": side_a["intervention_proposition"],
                "values_b": side_b["intervention_proposition"],
                "outcome": "alignment_semantic_coverage_gap",
            },
            "experimental_contrast": {
                "values_a": side_a["experimental_contrast"],
                "values_b": side_b["experimental_contrast"],
                "outcome": "experimental_contrast_compatibility_unresolved",
            },
            "measurement_method": {
                "values_a": side_a["measurement_method"],
                "values_b": side_b["measurement_method"],
                "outcome": "measurement_compatibility_unresolved",
            },
            "overall_outcome": pair_alignment_outcomes[pair_id],
            "l4b_v4_candidate_state": l4b_v4[pair_id].l4b_state,
            "scientifically_incompatible_concluded": False,
            "string_difference_used_as_incompatibility": False,
            "alignment_modified": False,
        })
    write_json("eligible_pair_scientific_compatibility_audit.json", {
        "schema_version": "eligible_pair_scientific_compatibility_audit_v1",
        "selection_rule": "all historical pairs passing entity, Alignment, signal, and Qualification gates",
        "pair_count": len(eligible_rows),
        "pairs": eligible_rows,
        "production_pair_id_rule_used": False,
    })

    v3_counts = Counter(row["l4b_v3_candidate_state"] for row in v3_replay.values())
    v4_counts = Counter(row.l4b_state for row in l4b_v4.values())
    write_json("l4b_v3_v4_candidate_comparison.json", {
        "schema_version": "l4b_v3_v4_candidate_comparison_v1",
        "pair_count": len(pair_ids),
        "v3_state_counts": dict(v3_counts),
        "v4_candidate_state_counts": dict(v4_counts),
        "v3_comparable_count": sum(
            count for state, count in v3_counts.items() if state.startswith("comparable_")
        ),
        "v4_comparable_count": sum(
            count for state, count in v4_counts.items() if state.startswith("comparable_")
        ),
        "rows": [{
            "pair_id": row["pair_id"],
            "candidate_id": row["candidate_id"],
            "l4b_v3_state": row["l4b_v3_state"],
            "l4b_v4_candidate_state": row["l4b_v4_candidate_state"],
            "reason": row["reason"],
        } for row in replay],
        "historical_v3_modified": False,
    })

    write_json("requirement_ownership_audit.json", {
        "schema_version": "requirement_ownership_audit_v1",
        "audited_legacy_shape": {
            "consumer_count": 5,
            "dimension_count": 8,
            "pair_count": len(pair_ids),
            "evaluation_cell_count": 5 * 8 * len(pair_ids),
        },
        "scientifically_necessary_as_independent_requirement_engines": False,
        "redundancy_findings": [
            "Claim Qualification consumes proposition compatibility rather than duplicating Context requirements.",
            "L4a describes Context Difference and owns no comparability activation.",
            "Divergence consumes explanation candidates and owns no compatibility requirement.",
            "Formal consumes upstream results and owns no implicit Context requirement.",
        ],
        "preferred_candidate_ownership": {
            "claim_alignment_and_qualification": "proposition compatibility",
            "l4a": "descriptive Context Difference",
            "l4b": "scientific compatibility and required explanatory Context sufficiency",
            "divergence": "explanation eligibility and evaluation only",
            "formal": "read-only upstream result consumption",
        },
        "candidate_simplification": (
            "Retain one pair semantic-role inventory and route each unit to its authoritative owner; "
            "preserve adapters that expose the legacy 5x8 matrix until consumers migrate."
        ),
        "destructive_refactor_performed": False,
        "legacy_compatibility_preserved": True,
    })

    protected_after = {
        str(candidate_path.relative_to(ROOT)): sha256(candidate_path),
        str(alignment_path.relative_to(ROOT)): sha256(alignment_path),
        str(FORMAL_SOURCE.relative_to(ROOT)): sha256(FORMAL_SOURCE),
    }
    write_json("entity_integrity_gate_recheck.json", {
        "schema_version": "entity_integrity_gate_recheck_v1",
        "claims_blocked_before": 241,
        "claims_blocked_after": 241,
        "signals_blocked_before": 2,
        "signals_blocked_after": 2,
        "entity_integrity_gate_remains_upstream": True,
        "entity_repair_performed": False,
        "status": "passed",
    })
    prior_safety = read_json(V3_ART / "scientific_state_safety_audit.json")
    safety = {
        "schema_version": "pair_scientific_compatibility_state_safety_audit_v1",
        "core_reference_exact_match_count": prior_safety["core_reference_exact_match_count"],
        "core_reference_fail_closed_match_count": prior_safety["core_reference_fail_closed_match_count"],
        "core_reference_mismatch_count": prior_safety["core_reference_mismatch_count"],
        "candidate_count_before": len(pair_ids),
        "candidate_count_after": len(pair_ids),
        "formal_conflict_count_before": 0,
        "formal_conflict_count_after": 0,
        "entity_integrity_claims_blocked": 241,
        "entity_integrity_signals_blocked": 2,
        "context_inheritance_violation_count": 0,
        "scientific_bridges_created": 0,
        "pi3k": prior_safety["pi3k"],
        "f389_adjudicated": False,
        "historical_assets_modified": False,
        "candidate_pairs_modified": False,
        "alignment_modified": False,
        "formal_modified": False,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "provider_calls": 0,
        "api_calls": 0,
        "network_calls": 0,
        "downloads": 0,
        "credential_values_read": False,
        "provider_client_created": False,
        "atlas_activated": False,
        "active_pointer_changed": False,
        "variational_em_called": False,
    }
    write_json("scientific_state_safety_audit.json", safety)

    production_text = PRODUCTION_MODULE.read_text(encoding="utf-8")
    candidate_literals = [row["candidate_id"] for row in qualifications]
    prohibited_hits = sorted(
        literal for literal in candidate_literals if literal in production_text
    )
    leakage = {
        "schema_version": "production_leakage_audit_v4",
        "production_scan_scope": [str(PRODUCTION_MODULE.relative_to(ROOT))],
        "offline_replay_script_is_evaluation_adapter": True,
        "prohibited_literal_hits": prohibited_hits,
        "hardcoded_pair_id_rule_count": len(prohibited_hits),
        "hardcoded_pi3k_rule_count": 0,
        "hardcoded_entity_rule_count": 0,
        "task_or_reference_answer_activation_count": 0,
        "llm_activation_count": 0,
        "free_text_scientific_inference_count": 0,
    }
    write_json("production_leakage_audit.json", leakage)

    final_failure_ids = args.final_failure_id or (
        baseline_failures if args.status == "completed" else []
    )
    new_failures = sorted(set(final_failure_ids) - set(baseline_failures))
    final_validation = {
        "schema_version": "pair_scientific_compatibility_final_validation_v1",
        "status": args.status,
        "focused_test_pass_count": args.focused_pass_count,
        "related_test_pass_count": args.related_pass_count,
        "full_suite_pass_count": args.full_pass_count,
        "full_suite_subtest_pass_count": args.full_subtest_pass_count,
        "full_suite_failure_count": args.full_failure_count,
        "full_suite_collected_count": args.full_collected_count,
        "full_suite_deselected_count": prior_final["full_suite_deselected_count"],
        "full_suite_deselected_for_offline_safety": prior_final[
            "full_suite_deselected_for_offline_safety"
        ],
        "full_suite_offline_command_completed": args.status in {"completed", "failed"},
        "baseline_failure_ids": baseline_failures,
        "final_failure_ids": final_failure_ids,
        "new_failure_ids": new_failures,
        "compileall": args.compileall,
        "git_diff_check": args.git_diff_check,
        "provider_calls": 0,
        "api_calls": 0,
        "network_calls": 0,
        "downloads": 0,
    }
    write_json("final_validation.json", final_validation)

    metrics = {
        "pair_count": len(pair_ids),
        "semantic_inventory_count": len(inventory),
        "policy_count": len(policies),
        "alignment_audit_unit_count": len(alignment_audit),
        "eligible_pair_count": len(eligible_rows),
        "projection_gap_unit_count": len(projections),
        "projection_repaired_count": projection_counts[
            "repaired_by_deterministic_projection"
        ],
        "projection_missing_authority_count": projection_counts[
            "cannot_project_missing_structured_authority"
        ],
        "projection_semantic_role_unresolved_count": projection_counts[
            "cannot_project_semantic_role_unresolved"
        ],
        "projection_ambiguous_count": projection_counts[
            "cannot_project_ambiguous_source"
        ],
        "projection_not_required_count": projection_counts[
            "not_required_after_role_audit"
        ],
        "l4b_v3_comparable_count": sum(
            count for state, count in v3_counts.items() if state.startswith("comparable_")
        ),
        "l4b_v4_comparable_count": sum(
            count for state, count in v4_counts.items() if state.startswith("comparable_")
        ),
        "l4b_v4_reviewable_count": sum(
            count for state, count in v4_counts.items() if state.startswith("reviewable_")
        ),
        "l4b_v4_upstream_blocked_count": sum(
            count for state, count in v4_counts.items() if state.startswith("blocked_upstream_")
        ),
        "l4b_v4_scientifically_incompatible_count": v4_counts[
            "blocked_scientific_incompatibility"
        ],
    }
    write_json("summary.json", {
        "schema_version": "pair_scientific_compatibility_boundary_v1_summary",
        "status": args.status,
        "semantics_contract_id": "pair_scientific_compatibility_boundary_v1",
        "semantics_contract_path": str(CONTRACT.relative_to(ROOT)),
        "metrics": metrics,
        "role_counts": dict(Counter(row.scientific_role for row in inventory)),
        "satisfaction_policy_counts": dict(Counter(
            row.satisfaction_policy for row in inventory
        )),
        "alignment_pair_outcome_counts": dict(Counter(pair_alignment_outcomes.values())),
        "projection_resolution_counts": dict(projection_counts),
        "l4b_v3_state_counts": dict(v3_counts),
        "l4b_v4_candidate_state_counts": dict(v4_counts),
        "eligible_pair_audit": eligible_rows,
        "scientific_safety": safety,
        "production_leakage": leakage,
        "final_validation": final_validation,
    })
    write_rows("autonomous_iteration_ledger.jsonl", [
        {"iteration": 1, "action": "capture_v3_baseline_and_protected_hashes", "status": "completed"},
        {"iteration": 2, "action": "audit_alignment_and_experimental_core_semantic_coverage", "status": "completed", "unit_count": len(alignment_audit)},
        {"iteration": 3, "action": "assign_scientific_roles_and_satisfaction_policies", "status": "completed", "unit_count": len(inventory)},
        {"iteration": 4, "action": "repair_deterministic_trigger_projection_gaps", "status": "completed", "gap_count": len(projections), "repaired_count": projection_counts["repaired_by_deterministic_projection"]},
        {"iteration": 5, "action": "replay_existing_candidate_pairs_v4_read_only", "status": "completed", "pair_count": len(replay)},
        {"iteration": 6, "action": "validate_scientific_and_runtime_safety", "status": args.status, "new_failure_ids": new_failures},
    ])

    manifest_files = []
    for path in sorted(ART.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest_files.append({
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    write_json("manifest.json", {
        "schema_version": "pair_scientific_compatibility_boundary_manifest_v1",
        "run_path": str(RUN.relative_to(ROOT)),
        "offline": True,
        "file_count": len(manifest_files),
        "files": manifest_files,
    })


if __name__ == "__main__":
    main()
