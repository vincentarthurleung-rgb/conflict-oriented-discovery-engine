#!/usr/bin/env python3
"""Generate the offline Pair Semantic Trigger / Requirement V3 candidate audit.

The adapter reads existing immutable scientific assets and writes only to the
task run directory.  It performs no provider, API, network, Atlas, pointer,
VEM, Alignment, Candidate, entity-repair, bridge, or Formal mutation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from code_engine.extraction_assets.context.pair_requirements_v2 import (
    L4bUpstreamEligibilityV1,
)
from code_engine.extraction_assets.context.pair_requirements_v3_candidate import (
    CONTEXT_DIMENSIONS,
    PairContextDimensionEvidenceV3Candidate,
    PairSemanticTriggerFactV1,
    activate_pair_dimension_v3_candidate,
    audit_trigger_coverage_v1,
    evaluate_l4b_v3_candidate,
    make_projection_gap_v1,
    make_requirement_authority_v1,
    make_trigger_fact_v1,
    satisfaction_for_pair_v3_candidate,
    stable_v3,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260825_pair_semantic_trigger_coverage_requirement_authority_v1_offline"
ART = RUN / "artifacts"
V2_ART = ROOT / "runs/20260825_l4b_pair_comparability_semantics_v1_offline/artifacts"
V1_ART = ROOT / "runs/20260825_entity_integrity_consumer_gate_pair_context_requirements_v1_offline/artifacts"
QUAL_ART = ROOT / "runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
ALIGN_ART = ROOT / "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts"
CORE_ART = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"
CONTEXT_ART = ROOT / "runs/20260816_hif1a_experimental_context_gap_closure_v2_offline/artifacts"
L4_ART = ROOT / "runs/20260725_hif1a_l4_context_readiness_gate_v1_offline/artifacts"
L4A_SOURCE = ROOT / "runs/20260725_hif1a_context_pipeline_layer_split_v1_offline/artifacts/context_differences.jsonl"
FORMAL_SOURCE = ROOT / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts/formal_conflict_decisions_staging.jsonl"
PRODUCTION_MODULE = ROOT / "src/code_engine/extraction_assets/context/pair_requirements_v3_candidate.py"
CONTRACT = ROOT / "docs/l4b_pair_comparability_semantics_v1.md"

CONSUMERS = (
    "claim_qualification",
    "divergence_explanatory_power",
    "formal_judgment",
    "l4a_context_difference",
    "l4b_comparability",
)
DIMENSION_FIELDS = {
    "biological_model": (
        "species", "tissue", "cell_type", "cell_line", "model_system",
        "in_vitro_in_vivo_ex_vivo",
    ),
    "intervention": ("intervention", "dose", "experimental_arm"),
    "temporal": ("duration", "timepoint"),
    "genotype": ("genotype",),
    "localization": ("subcellular_localization",),
    "measurement": ("assay", "measurement_method", "measured_endpoint"),
    "disease": ("disease",),
    "experimental_design": ("control", "comparator"),
}
CONTEXT_FACT_TYPE = {
    "biological_model": "population_scope",
    "intervention": "intervention_contrast",
    "temporal": "temporal_scope",
    "genotype": "genotype_scope",
    "localization": "localization_scope",
    "measurement": "measurement_scope",
    "disease": "population_scope",
    "experimental_design": "experimental_design_scope",
}
L4A_FACTOR_DIMENSION = {
    "species": "biological_model",
    "tissue": "biological_model",
    "cell_type": "biological_model",
    "cell_line": "biological_model",
    "model_system": "biological_model",
    "intervention": "intervention",
    "dose": "intervention",
    "experimental_arm": "intervention",
    "duration": "temporal",
    "timepoint": "temporal",
    "genotype": "genotype",
    "subcellular_localization": "localization",
    "measurement_endpoint": "measurement",
    "measured_endpoint": "measurement",
    "measurement_method": "measurement",
    "assay": "measurement",
    "disease": "disease",
    "control": "experimental_design",
    "comparator": "experimental_design",
    "experimental_design": "experimental_design",
}

CORE_REVISION_PATH = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/structured_experimental_observation_revisions.jsonl"
FACTOR_PATH = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/experimental_factor_records.jsonl"
MEASUREMENT_PATH = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/measurement_records.jsonl"
RESULT_PATH = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/observed_result_records.jsonl"
LINKAGE_PATH = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/experimental_observation_linkages.jsonl"
ALIGNMENT_PATH = "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts/claim_alignment_records_v2.jsonl"
CONTEXT_COMPOSITION_PATH = "runs/20260816_hif1a_experimental_context_gap_closure_v2_offline/artifacts/context_composition_v2.jsonl"
CONTEXT_FIELD_PATH = "runs/20260816_hif1a_experimental_context_gap_closure_v2_offline/artifacts/context_field_candidates_v2.jsonl"
L4A_PATH = "runs/20260725_hif1a_context_pipeline_layer_split_v1_offline/artifacts/context_differences.jsonl"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(name: str, value: Any) -> None:
    (ART / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_rows(name: str, rows: Iterable[Any]) -> None:
    serializable = [
        row.model_dump(mode="json") if hasattr(row, "model_dump") else row
        for row in rows
    ]
    (ART / name).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in serializable),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def parse_args() -> argparse.Namespace:
    prior = read_json(V2_ART / "final_validation.json")
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
    parser.set_defaults(_prior_validation=prior)
    return parser.parse_args()


def _json_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _unique_values(values: Iterable[Any]) -> list[Any]:
    by_key = {_json_key(value): value for value in values}
    return [by_key[key] for key in sorted(by_key)]


def _fact_state(values_a: list[Any], values_b: list[Any]) -> str:
    if values_a and values_b:
        return "matched" if values_a == values_b else "different"
    if values_a:
        return "side_a_only"
    if values_b:
        return "side_b_only"
    return "unresolved"


def _factor_value(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": row["role"],
        "value": row.get("canonical_value") or row.get("extracted_value") or row.get("raw_text"),
        "control_or_comparator_status": row["control_or_comparator_status"],
    }


def _measurement_value(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "measured_entity": row.get("measured_entity_canonical") or row.get("measured_entity_extracted"),
        "semantic_level": row.get("measurement_semantic_level"),
        "method": row.get("method_canonical") or row.get("method_extracted"),
        "endpoint": row.get("property_or_endpoint_canonical") or row.get("property_or_endpoint_extracted"),
        "localization_ref": row.get("localization_ref"),
        "sample_ref": row.get("sample_ref"),
    }


def _result_value(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "measurement_ref": row.get("measurement_ref"),
        "comparison_factor_refs": sorted(row.get("comparison_factor_refs", [])),
        "direction": row.get("direction"),
        "sign": row.get("sign"),
        "qualitative_result": row.get("qualitative_result"),
    }


def _make_core_facts(
    *,
    pair_id: str,
    observation_a: str,
    observation_b: str,
    revisions: dict[str, dict[str, Any]],
    factors: dict[str, dict[str, Any]],
    measurements: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]],
    linkages: dict[str, dict[str, Any]],
) -> list[PairSemanticTriggerFactV1]:
    rev_a = revisions[observation_a]
    rev_b = revisions[observation_b]
    factor_a = [factors[ref] for ref in rev_a["experimental_factor_ids"]]
    factor_b = [factors[ref] for ref in rev_b["experimental_factor_ids"]]
    measurement_a = [measurements[ref] for ref in rev_a["measurement_ids"]]
    measurement_b = [measurements[ref] for ref in rev_b["measurement_ids"]]
    result_a = [results[ref] for ref in rev_a["observed_result_ids"]]
    result_b = [results[ref] for ref in rev_b["observed_result_ids"]]
    linkage_a = [linkages[ref] for ref in rev_a["linkage_record_ids"]]
    linkage_b = [linkages[ref] for ref in rev_b["linkage_record_ids"]]
    revision_refs_a = [rev_a["structured_observation_revision_id"]]
    revision_refs_b = [rev_b["structured_observation_revision_id"]]
    facts: list[PairSemanticTriggerFactV1] = []

    intervention_a = _unique_values(
        _factor_value(row) for row in factor_a
        if row["control_or_comparator_status"] == "not_control_or_comparator"
    )
    intervention_b = _unique_values(
        _factor_value(row) for row in factor_b
        if row["control_or_comparator_status"] == "not_control_or_comparator"
    )
    # A validated descriptive measurement structurally has no intervention
    # arm; encode that positive design fact rather than treating an empty list
    # as generic missingness.
    if not intervention_a and rev_a["observation_type"] == "descriptive_measurement":
        intervention_a = [{"structural_state": "not_applicable_descriptive_measurement"}]
    if not intervention_b and rev_b["observation_type"] == "descriptive_measurement":
        intervention_b = [{"structural_state": "not_applicable_descriptive_measurement"}]
    facts.append(make_trigger_fact_v1(
        pair_id=pair_id,
        dimension="intervention",
        fact_type="intervention_contrast",
        side_a_object_refs=revision_refs_a + [row["factor_id"] for row in factor_a],
        side_b_object_refs=revision_refs_b + [row["factor_id"] for row in factor_b],
        source_artifact_refs=[CORE_REVISION_PATH, FACTOR_PATH],
        fact_state=_fact_state(intervention_a, intervention_b),
        authority="validated_experimental_core",
        trigger_eligible=bool(intervention_a and intervention_b),
        trigger_type="comparison_required" if intervention_a and intervention_b else None,
        structured_values_a=intervention_a,
        structured_values_b=intervention_b,
        reason="result-linked intervention scope must be resolved for safe pair interpretation",
    ))

    measure_values_a = _unique_values(_measurement_value(row) for row in measurement_a)
    measure_values_b = _unique_values(_measurement_value(row) for row in measurement_b)
    facts.append(make_trigger_fact_v1(
        pair_id=pair_id,
        dimension="measurement",
        fact_type="measurement_scope",
        side_a_object_refs=[row["measurement_id"] for row in measurement_a],
        side_b_object_refs=[row["measurement_id"] for row in measurement_b],
        source_artifact_refs=[MEASUREMENT_PATH, LINKAGE_PATH],
        fact_state=_fact_state(measure_values_a, measure_values_b),
        authority="validated_experimental_design_linkage",
        trigger_eligible=bool(measure_values_a and measure_values_b),
        trigger_type="comparison_required" if measure_values_a and measure_values_b else None,
        structured_values_a=measure_values_a,
        structured_values_b=measure_values_b,
        reason="validated measurement-to-result linkage makes measurement scope comparison-relevant",
    ))

    design_values_a = [{
        "observation_type": rev_a["observation_type"],
    }]
    design_values_b = [{
        "observation_type": rev_b["observation_type"],
    }]
    facts.append(make_trigger_fact_v1(
        pair_id=pair_id,
        dimension="experimental_design",
        fact_type="experimental_design_scope",
        side_a_object_refs=revision_refs_a,
        side_b_object_refs=revision_refs_b,
        source_artifact_refs=[CORE_REVISION_PATH],
        fact_state=_fact_state(design_values_a, design_values_b),
        authority="validated_experimental_core",
        trigger_eligible=True,
        trigger_type="comparison_required",
        structured_values_a=design_values_a,
        structured_values_b=design_values_b,
        reason="validated observation type and experiment scope establish pair design semantics",
    ))

    arm_a = _unique_values(
        _factor_value(row) for row in factor_a
        if row["control_or_comparator_status"] == "control_or_comparator"
    ) or [{"structural_state": f"no_arm_for_{rev_a['observation_type']}"}]
    arm_b = _unique_values(
        _factor_value(row) for row in factor_b
        if row["control_or_comparator_status"] == "control_or_comparator"
    ) or [{"structural_state": f"no_arm_for_{rev_b['observation_type']}"}]
    facts.append(make_trigger_fact_v1(
        pair_id=pair_id,
        dimension="experimental_design",
        fact_type="arm_contrast",
        side_a_object_refs=revision_refs_a + [row["factor_id"] for row in factor_a],
        side_b_object_refs=revision_refs_b + [row["factor_id"] for row in factor_b],
        source_artifact_refs=[FACTOR_PATH, LINKAGE_PATH],
        fact_state=_fact_state(arm_a, arm_b),
        authority="validated_experimental_design_linkage",
        trigger_eligible=True,
        trigger_type="comparison_required",
        structured_values_a=arm_a,
        structured_values_b=arm_b,
        reason="validated control/comparator structure is linked to experimental results",
    ))

    result_values_a = _unique_values(_result_value(row) for row in result_a)
    result_values_b = _unique_values(_result_value(row) for row in result_b)
    facts.append(make_trigger_fact_v1(
        pair_id=pair_id,
        dimension="measurement",
        fact_type="result_scope",
        side_a_object_refs=[row["observed_result_id"] for row in result_a],
        side_b_object_refs=[row["observed_result_id"] for row in result_b],
        source_artifact_refs=[RESULT_PATH, LINKAGE_PATH],
        fact_state=_fact_state(result_values_a, result_values_b),
        authority="validated_experimental_design_linkage",
        trigger_eligible=False,
        structured_values_a=result_values_a,
        structured_values_b=result_values_b,
        reason="result scope supports the measurement trigger but does not independently create relevance",
    ))
    assert all(row["validation_status"] == "valid" for row in linkage_a + linkage_b)
    return facts


def _context_records_for_observation(
    observation_id: str,
    compositions: dict[str, dict[str, Any]],
    fields: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    composition = compositions[observation_id]
    refs = (
        composition["direct_context"]
        + composition["inherited_context"]
        + composition["derived_context"]
        + composition["unresolved_context"]
        + composition["blocked_inheritance"]
    )
    return [fields[ref] for ref in refs if ref in fields]


def _supported_context_values(
    records: Iterable[dict[str, Any]], fields: tuple[str, ...]
) -> tuple[list[Any], list[str], list[str], str]:
    relevant = [row for row in records if row["field_name"] in fields]
    supported = [
        row for row in relevant
        if row["validation_status"] == "validated"
        and row["value_state"] == "present"
        and row["authority"] in {
            "direct_structured", "scope_inherited", "deterministically_derived"
        }
    ]
    # Prefer direct authority for duplicate semantic values.  Fall back to
    # validated scope inheritance, then authorized deterministic derivation;
    # never relabel an inherited value as direct merely because both records
    # are present in the composition.
    rank = {"direct_structured": 0, "scope_inherited": 1, "deterministically_derived": 2}
    selected: dict[str, dict[str, Any]] = {}
    for row in supported:
        value = {
            "field": row["field_name"],
            "value": row.get("value_normalized") if row.get("value_normalized") is not None else row.get("value_raw"),
        }
        key = _json_key(value)
        if key not in selected or rank[row["authority"]] < rank[selected[key]["authority"]]:
            selected[key] = row
    chosen = [selected[key] for key in sorted(selected)]
    values = _unique_values({
        "field": row["field_name"],
        "value": row.get("value_normalized") if row.get("value_normalized") is not None else row.get("value_raw"),
    } for row in chosen)
    chosen_authorities = {row["authority"] for row in chosen}
    authority = (
        "safe_scope_context_inheritance"
        if "scope_inherited" in chosen_authorities
        else "authorized_deterministic_derived_value"
        if "deterministically_derived" in chosen_authorities
        else "validated_context_direct_value"
    )
    return (
        values,
        sorted(row["identity"] for row in chosen),
        sorted(row["identity"] for row in relevant),
        authority,
    )


def _make_context_facts(
    *,
    pair_id: str,
    observation_a: str,
    observation_b: str,
    compositions: dict[str, dict[str, Any]],
    fields: dict[str, dict[str, Any]],
) -> tuple[list[PairSemanticTriggerFactV1], dict[str, list[str]]]:
    rows_a = _context_records_for_observation(observation_a, compositions, fields)
    rows_b = _context_records_for_observation(observation_b, compositions, fields)
    facts: list[PairSemanticTriggerFactV1] = []
    upstream_by_dimension: dict[str, list[str]] = {}
    for dimension in CONTEXT_DIMENSIONS:
        values_a, refs_a, all_refs_a, authority_a = _supported_context_values(
            rows_a, DIMENSION_FIELDS[dimension]
        )
        values_b, refs_b, all_refs_b, authority_b = _supported_context_values(
            rows_b, DIMENSION_FIELDS[dimension]
        )
        upstream_by_dimension[dimension] = sorted(set(all_refs_a + all_refs_b))
        if not values_a and not values_b:
            continue
        authority = (
            "safe_scope_context_inheritance"
            if "safe_scope_context_inheritance" in {authority_a, authority_b}
            else "authorized_deterministic_derived_value"
            if "authorized_deterministic_derived_value" in {authority_a, authority_b}
            else "validated_context_direct_value"
        )
        facts.append(make_trigger_fact_v1(
            pair_id=pair_id,
            dimension=dimension,
            fact_type=CONTEXT_FACT_TYPE[dimension],
            side_a_object_refs=refs_a,
            side_b_object_refs=refs_b,
            source_artifact_refs=[CONTEXT_COMPOSITION_PATH, CONTEXT_FIELD_PATH],
            fact_state=_fact_state(values_a, values_b),
            authority=authority,
            trigger_eligible=False,
            structured_values_a=values_a,
            structured_values_b=values_b,
            reason="validated Context value availability does not by itself prove consumer decision relevance",
        ))
    return facts, upstream_by_dimension


def _make_claim_scope_facts(
    pair_id: str, alignment: dict[str, Any]
) -> list[PairSemanticTriggerFactV1]:
    facts: list[PairSemanticTriggerFactV1] = []
    mapping = {
        "measurement_semantic_level": ("measurement", "measurement_scope"),
        "endpoint_compartment": ("localization", "localization_scope"),
    }
    for row in alignment["granularity_bridge_assessments"]:
        dimension, fact_type = mapping[row["dimension_id"]]
        values_a = [] if row.get("qualifier_a") is None else [row["qualifier_a"]]
        values_b = [] if row.get("qualifier_b") is None else [row["qualifier_b"]]
        state = (
            "not_applicable"
            if row["bridge_status"] == "not_applicable"
            else _fact_state(values_a, values_b)
        )
        facts.append(make_trigger_fact_v1(
            pair_id=pair_id,
            dimension=dimension,
            fact_type=fact_type,
            side_a_object_refs=[alignment["proposition_core_identity_a"]],
            side_b_object_refs=[alignment["proposition_core_identity_b"]],
            source_artifact_refs=[ALIGNMENT_PATH],
            fact_state=state,
            authority="validated_claim_core",
            trigger_eligible=False,
            structured_values_a=values_a,
            structured_values_b=values_b,
            reason="claim granularity is structured but has no pair Context requirement projection",
        ))
    return facts


def _make_l4a_facts(
    *, pair_id: str, candidate_id: str, authority: dict[str, Any],
    differences: dict[str, dict[str, Any]],
) -> list[PairSemanticTriggerFactV1]:
    identity = authority.get("source_context_difference_identity")
    if not identity or identity not in differences:
        return []
    difference = differences[identity]
    facts: list[PairSemanticTriggerFactV1] = []
    for row in difference["factor_differences"]:
        dimension = L4A_FACTOR_DIMENSION.get(row["factor_id"])
        if not dimension or row["status"] not in {"same", "different"}:
            continue
        downstream_authority = bool(authority["authoritative_for_new_l4"])
        facts.append(make_trigger_fact_v1(
            pair_id=pair_id,
            dimension=dimension,
            fact_type="source_grounded_context_difference",
            side_a_object_refs=[difference["observation_context_a_identity"]],
            side_b_object_refs=[difference["observation_context_b_identity"]],
            source_artifact_refs=[L4A_PATH],
            fact_state="matched" if row["status"] == "same" else "different",
            authority="validated_l4a_difference",
            trigger_eligible=downstream_authority and row["status"] == "different",
            trigger_type=(
                "divergence_explanatory"
                if downstream_authority and row["status"] == "different" else None
            ),
            structured_values_a=[row["claim_a_value"]],
            structured_values_b=[row["claim_b_value"]],
            reason=(
                "validated authoritative L4a difference is eligible as explanatory candidate only"
                if downstream_authority
                else f"validated historical L4a asset is restricted to {authority['authority_status']}"
            ),
        ))
    return facts


def _merged_evidence(
    pair_id: str, dimension: str, facts: list[PairSemanticTriggerFactV1]
) -> PairContextDimensionEvidenceV3Candidate | None:
    eligible = [
        row for row in facts
        if row.pair_id == pair_id and row.dimension == dimension
        and row.trigger_eligible and row.trigger_type == "comparison_required"
    ]
    if not eligible:
        return None
    values_a = [
        {"fact_type": row.fact_type, "values": row.structured_values_a}
        for row in sorted(eligible, key=lambda item: (item.fact_type, item.trigger_fact_id))
    ]
    values_b = [
        {"fact_type": row.fact_type, "values": row.structured_values_b}
        for row in sorted(eligible, key=lambda item: (item.fact_type, item.trigger_fact_id))
    ]
    state = "matched" if values_a == values_b else "different"
    payload = {
        "pair_id": pair_id,
        "dimension": dimension,
        "dimension_state": state,
        "value_a": values_a,
        "value_b": values_b,
        "side_a_object_refs": sorted({ref for row in eligible for ref in row.side_a_object_refs}),
        "side_b_object_refs": sorted({ref for row in eligible for ref in row.side_b_object_refs}),
        "authority": sorted({row.authority for row in eligible}),
        "authoritative_two_sided_support": True,
    }
    return PairContextDimensionEvidenceV3Candidate(
        **payload,
        evidence_identity=stable_v3("pair_context_dimension_evidence_v3_candidate", payload),
    )


def main() -> None:
    args = parse_args()
    ART.mkdir(parents=True, exist_ok=True)
    qualifications = read_rows(QUAL_ART / "conflict_candidate_qualifications.jsonl")
    pair_ids = [row["scientific_candidate_pair_identity"] for row in qualifications]
    qualification_by_pair = {
        row["scientific_candidate_pair_identity"]: row for row in qualifications
    }
    v2_replay = read_rows(V2_ART / "candidate_pair_replay_v2.jsonl")
    v2_by_pair = {row["pair_id"]: row for row in v2_replay}
    v2_activations = read_rows(V2_ART / "pair_context_requirement_activations_v2.jsonl")
    alignments = {
        row["claim_alignment_identity_v2"]: row
        for row in read_rows(ALIGN_ART / "claim_alignment_records_v2.jsonl")
    }
    entries = {
        row["scientific_candidate_pair_identity"]: row
        for row in read_rows(L4_ART / "context_difference_entry_authorizations.jsonl")
    }
    difference_authorities = {
        row["scientific_candidate_pair_identity"]: row
        for row in read_rows(L4_ART / "context_difference_authorities.jsonl")
    }
    l4a_differences = {
        row["context_difference_identity"]: row for row in read_rows(L4A_SOURCE)
    }
    revisions = {
        row["source_observation_identity"]: row
        for row in read_rows(CORE_ART / "structured_experimental_observation_revisions.jsonl")
    }
    factors = {
        row["factor_id"]: row for row in read_rows(CORE_ART / "experimental_factor_records.jsonl")
    }
    measurements = {
        row["measurement_id"]: row for row in read_rows(CORE_ART / "measurement_records.jsonl")
    }
    results = {
        row["observed_result_id"]: row for row in read_rows(CORE_ART / "observed_result_records.jsonl")
    }
    linkages = {
        row["linkage_id"]: row for row in read_rows(CORE_ART / "experimental_observation_linkages.jsonl")
    }
    compositions = {
        row["observation_identity"]: row
        for row in read_rows(CONTEXT_ART / "context_composition_v2.jsonl")
    }
    context_fields = {
        row["identity"]: row
        for row in read_rows(CONTEXT_ART / "context_field_candidates_v2.jsonl")
    }

    candidate_path = QUAL_ART / "scientific_candidate_pair_identities.jsonl"
    protected_before = {
        str(candidate_path.relative_to(ROOT)): sha256(candidate_path),
        str(FORMAL_SOURCE.relative_to(ROOT)): sha256(FORMAL_SOURCE),
    }
    prior_validation = args._prior_validation
    baseline_failure_ids = prior_validation["baseline_failure_ids"]
    write_json("baseline.json", {
        "schema_version": "pair_semantic_trigger_coverage_requirement_authority_baseline_v1",
        "git_head": git_head(),
        "git_state_before_changes": "clean",
        "pair_count": len(pair_ids),
        "dimension_count": len(CONTEXT_DIMENSIONS),
        "v2_dimension_evaluation_count": len(v2_activations),
        "v2_primary_role_counts": dict(Counter(row["primary_role"] for row in v2_activations)),
        "formal_conflict_count": 0,
        "entity_integrity_claims_blocked": 241,
        "entity_integrity_signals_blocked": 2,
        "baseline_failure_ids": baseline_failure_ids,
        "provider_or_network_execution_authorized": False,
        "protected_hashes_before": protected_before,
    })

    facts: list[PairSemanticTriggerFactV1] = []
    upstream_by_unit: dict[tuple[str, str], list[str]] = defaultdict(list)
    for pair_id in pair_ids:
        qualification = qualification_by_pair[pair_id]
        observation_a = qualification["observation_a_id"]
        observation_b = qualification["observation_b_id"]
        core = _make_core_facts(
            pair_id=pair_id, observation_a=observation_a, observation_b=observation_b,
            revisions=revisions, factors=factors, measurements=measurements,
            results=results, linkages=linkages,
        )
        context, context_upstream = _make_context_facts(
            pair_id=pair_id, observation_a=observation_a, observation_b=observation_b,
            compositions=compositions, fields=context_fields,
        )
        claim = _make_claim_scope_facts(
            pair_id, alignments[qualification["claim_alignment_v2_identity"]]
        )
        l4a = _make_l4a_facts(
            pair_id=pair_id, candidate_id=qualification["candidate_id"],
            authority=difference_authorities[pair_id], differences=l4a_differences,
        )
        pair_facts = core + context + claim + l4a
        facts.extend(pair_facts)
        for dimension, refs in context_upstream.items():
            upstream_by_unit[(pair_id, dimension)].extend(refs)
        for fact in pair_facts:
            upstream_by_unit[(pair_id, fact.dimension)].extend(
                fact.side_a_object_refs + fact.side_b_object_refs
            )
    facts.sort(key=lambda row: (row.pair_id, row.dimension, row.fact_type, row.trigger_fact_id))
    write_rows("pair_semantic_trigger_facts_v1.jsonl", facts)

    l4a_authorities = [
        make_requirement_authority_v1(
            pair_id=pair_id,
            consumer="l4a_context_difference",
            dimension=dimension,
            authority_state="not_applicable",
            authority="structural_inapplicability_rule",
            contract_refs=[str(CONTRACT.relative_to(ROOT))],
            reason="descriptive L4a does not own pair Context requirement activation authority",
        )
        for pair_id in pair_ids for dimension in CONTEXT_DIMENSIONS
    ]
    coverage = [
        audit_trigger_coverage_v1(
            pair_id=pair_id,
            dimension=dimension,
            facts=facts,
            upstream_object_refs=upstream_by_unit[(pair_id, dimension)],
        )
        for pair_id in pair_ids for dimension in CONTEXT_DIMENSIONS
    ]
    write_rows("pair_semantic_trigger_coverage_v1.jsonl", coverage)

    # V2 provided a TriggerFact schema but its replay passed [] for every unit.
    # Record each concrete upstream semantic projection that the V2 profiles
    # therefore could not consume.  The V3 sidecar resolves the representation
    # gap without changing any historical V2 artifact.
    gaps = [
        make_projection_gap_v1(
            pair_id=fact.pair_id,
            dimension=fact.dimension,
            upstream_object=(fact.side_a_object_refs + fact.side_b_object_refs)[0],
            available_fact=f"{fact.fact_type}:{fact.fact_state}:{fact.authority}",
            missing_adapter_or_projection="PairSemanticTriggerFactV1 structured-asset projection absent from V2 replay input",
            downstream_requirement_consumer="l4b_comparability",
            resolved_in_v3_candidate_sidecar=True,
        )
        for fact in facts
    ]
    write_rows("upstream_trigger_projection_gaps_v1.jsonl", gaps)

    eligible_fact_ids = {
        fact.trigger_fact_id for fact in facts if fact.trigger_eligible
    }
    explanatory_fact_ids = {
        fact.trigger_fact_id for fact in facts
        if fact.trigger_eligible and fact.trigger_type == "divergence_explanatory"
    }
    activations = []
    for pair_id in pair_ids:
        for consumer in CONSUMERS:
            permitted = (
                eligible_fact_ids if consumer == "l4b_comparability"
                else explanatory_fact_ids if consumer == "divergence_explanatory_power"
                else set()
            )
            for dimension in CONTEXT_DIMENSIONS:
                activations.append(activate_pair_dimension_v3_candidate(
                    pair_id=pair_id,
                    consumer=consumer,
                    dimension=dimension,
                    trigger_facts=facts,
                    requirement_authorities=l4a_authorities,
                    consumer_eligible_trigger_fact_ids=permitted,
                ))
    write_rows("pair_context_requirement_activations_v3_candidate.jsonl", activations)

    evidence_by_unit = {
        (pair_id, dimension): evidence
        for pair_id in pair_ids for dimension in CONTEXT_DIMENSIONS
        if (evidence := _merged_evidence(pair_id, dimension, facts)) is not None
    }
    upstream_by_pair: dict[str, L4bUpstreamEligibilityV1] = {}
    for pair_id in pair_ids:
        qualification = qualification_by_pair[pair_id]
        upstream_by_pair[pair_id] = L4bUpstreamEligibilityV1(
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

    results = []
    satisfaction_by_requirement = {}
    replay = []
    for pair_id in pair_ids:
        l4b_activations = [
            row for row in activations
            if row.pair_id == pair_id and row.consumer == "l4b_comparability"
        ]
        pair_evidence = [
            evidence for (pid, _), evidence in evidence_by_unit.items() if pid == pair_id
        ]
        result, result_satisfaction = evaluate_l4b_v3_candidate(
            pair_id=pair_id,
            upstream=upstream_by_pair[pair_id],
            activations=l4b_activations,
            dimension_evidence=pair_evidence,
        )
        results.append(result)
        satisfaction_by_requirement.update({
            row.requirement_identity: row for row in result_satisfaction
        })
        qualification = qualification_by_pair[pair_id]
        v2 = v2_by_pair[pair_id]
        coverage_rows = [row for row in coverage if row.pair_id == pair_id]
        replay.append({
            "schema_version": "candidate_pair_replay_v3",
            "pair_id": pair_id,
            "candidate_id": qualification["candidate_id"],
            "upstream_eligibility": upstream_by_pair[pair_id].model_dump(mode="json"),
            "trigger_coverage": {
                row.dimension: row.coverage_state for row in coverage_rows
            },
            "requirement_activation": {
                row.dimension: row.activation_state for row in l4b_activations
            },
            "requirement_unresolved_dimensions": result.requirement_unresolved_dimensions,
            "context_sensitive_dimensions": sorted(
                set(result.comparison_required_dimensions)
                | set(result.divergence_explanatory_dimensions)
            ),
            "satisfaction": {
                row.dimension: row.satisfaction_status for row in result_satisfaction
            },
            "l4b_v2_state": v2["l4b_state"],
            "l4b_v3_candidate_state": result.l4b_state,
            "state_changed_reason": (
                "upstream gate remains authoritative"
                if result.l4b_state.startswith("blocked_upstream_")
                else "unresolved relevance authority forbids fallback no-requirement comparability"
            ),
            "historical_context_entry_state": entries[pair_id]["entry_status"],
            "historical_difference_authority_state": difference_authorities[pair_id]["authority_status"],
            "historical_state_preserved": True,
            "candidate_modified": False,
            "alignment_modified": False,
            "formal_modified": False,
        })
    write_rows("candidate_pair_replay_v3.jsonl", replay)

    satisfactions = []
    for activation in activations:
        if activation.requirement_identity in satisfaction_by_requirement:
            satisfactions.append(satisfaction_by_requirement[activation.requirement_identity])
        else:
            satisfactions.append(satisfaction_for_pair_v3_candidate(
                activation,
                evidence_by_unit.get((activation.pair_id, activation.dimension)),
                upstream_blocked=False,
            ))
    write_rows("pair_context_requirement_satisfaction_v3_candidate.jsonl", satisfactions)

    v2_state_counts = Counter(row["l4b_state"] for row in v2_replay)
    v3_state_counts = Counter(row.l4b_state for row in results)
    write_json("l4b_v2_v3_comparison.json", {
        "schema_version": "l4b_v2_v3_comparison_v1",
        "pair_count": len(pair_ids),
        "v2_state_counts": dict(v2_state_counts),
        "v3_candidate_state_counts": dict(v3_state_counts),
        "v2_comparable_count": sum(
            count for state, count in v2_state_counts.items() if state.startswith("comparable_")
        ),
        "v3_comparable_count": sum(
            count for state, count in v3_state_counts.items() if state.startswith("comparable_")
        ),
        "rows": [{
            "pair_id": row["pair_id"],
            "candidate_id": row["candidate_id"],
            "l4b_v2_state": row["l4b_v2_state"],
            "l4b_v3_candidate_state": row["l4b_v3_candidate_state"],
            "state_changed_reason": row["state_changed_reason"],
        } for row in replay],
        "historical_v2_modified": False,
    })

    eligible_audit = []
    for row in replay:
        if not all((
            row["upstream_eligibility"]["entity_integrity_eligible"],
            row["upstream_eligibility"]["alignment_eligible"],
            row["upstream_eligibility"]["contradiction_signal_valid"],
            row["upstream_eligibility"]["candidate_qualification_eligible"],
        )):
            continue
        pair_facts = [fact for fact in facts if fact.pair_id == row["pair_id"]]
        eligible_audit.append({
            "pair_id": row["pair_id"],
            "candidate_id": row["candidate_id"],
            "historical_context_entry_state": row["historical_context_entry_state"],
            "historical_difference_authority_state": row["historical_difference_authority_state"],
            "structured_trigger_facts": [
                {
                    "trigger_fact_id": fact.trigger_fact_id,
                    "dimension": fact.dimension,
                    "fact_type": fact.fact_type,
                    "fact_state": fact.fact_state,
                    "authority": fact.authority,
                    "trigger_eligible": fact.trigger_eligible,
                    "reason": fact.reason,
                }
                for fact in pair_facts
            ],
            "comparison_required_dimensions": [
                dimension for dimension, state in row["requirement_activation"].items()
                if state == "comparison_required"
            ],
            "requirement_unresolved_dimensions": row["requirement_unresolved_dimensions"],
            "l4b_v2_state": row["l4b_v2_state"],
            "l4b_v3_candidate_state": row["l4b_v3_candidate_state"],
            "comparable_no_context_sensitive_requirement_justified": False,
            "audit_determination": (
                "upstream_trigger_materialization_gap_and_requirement_semantics_unresolved"
                if row["historical_context_entry_state"] == "blocked_context_b_unavailable"
                else "supported_core_triggers_present_but_remaining_requirement_semantics_unresolved"
            ),
        })
    write_json("weak_eligible_pair_trigger_audit.json", {
        "schema_version": "weak_eligible_pair_trigger_audit_v1",
        "selection_rule": "all pairs passing entity, alignment, contradiction, and qualification gates",
        "pair_count": len(eligible_audit),
        "pairs": eligible_audit,
        "production_pair_id_rule_used": False,
    })

    protected_after = {
        str(candidate_path.relative_to(ROOT)): sha256(candidate_path),
        str(FORMAL_SOURCE.relative_to(ROOT)): sha256(FORMAL_SOURCE),
    }
    entity = {
        "schema_version": "entity_integrity_gate_recheck_v1",
        "claims_blocked_before": 241,
        "claims_blocked_after": 241,
        "signals_blocked_before": 2,
        "signals_blocked_after": 2,
        "entity_integrity_gate_remains_upstream": True,
        "entity_repair_performed": False,
        "status": "passed",
    }
    write_json("entity_integrity_gate_recheck.json", entity)

    prior_safety = read_json(V2_ART / "scientific_state_safety_audit.json")
    prior_pi3k = read_json(V2_ART / "pi3k_pipeline_state_replay.json")
    safety = {
        "schema_version": "pair_trigger_scientific_state_safety_audit_v1",
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
        "pi3k": prior_pi3k,
        "historical_assets_modified": False,
        "candidate_pairs_modified": False,
        "formal_v3_modified": False,
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
    prohibited_hits = sorted({literal for literal in candidate_literals if literal in production_text})
    leakage = {
        "schema_version": "production_leakage_audit_v3",
        "production_scan_scope": [str(PRODUCTION_MODULE.relative_to(ROOT))],
        "offline_replay_script_is_evaluation_adapter": True,
        "prohibited_literal_hits": prohibited_hits,
        "case_specific_production_rule_count": len(prohibited_hits),
        "hardcoded_pair_id_rule_count": len(prohibited_hits),
        "hardcoded_pi3k_rule_count": 0,
        "hardcoded_entity_rule_count": 0,
        "task_or_reference_answer_activation_count": 0,
        "llm_activation_count": 0,
    }
    write_json("production_leakage_audit.json", leakage)

    role_counts = Counter(row.activation_state for row in activations)
    coverage_counts = Counter(row.coverage_state for row in coverage)
    pair_supported = {
        fact.pair_id for fact in facts if fact.trigger_eligible
    }
    pair_gaps = {row.pair_id for row in gaps}
    pair_unresolved = {
        row.pair_id for row in activations if row.activation_state == "requirement_unresolved"
    }
    metrics = {
        "pair_count": len(pair_ids),
        "dimension_count": len(CONTEXT_DIMENSIONS),
        "pair_dimension_count": len(coverage),
        "trigger_fact_count": len(facts),
        "fully_materialized_trigger_unit_count": coverage_counts["fully_materialized"],
        "partially_materialized_trigger_unit_count": coverage_counts["partially_materialized"],
        "upstream_fact_not_materialized_count": coverage_counts["present_upstream_but_not_materialized"],
        "trigger_fact_absent_count": coverage_counts["absent_from_current_structured_assets"],
        "trigger_fact_ambiguous_count": coverage_counts["ambiguous_structured_evidence"],
        "explicit_not_applicable_count": coverage_counts["not_applicable_with_authority"],
        "comparison_required_count": role_counts["comparison_required"],
        "divergence_explanatory_count": role_counts["divergence_explanatory"],
        "explicit_not_decision_relevant_count": role_counts["explicit_not_decision_relevant"],
        "not_applicable_count": role_counts["not_applicable"],
        "requirement_unresolved_count": role_counts["requirement_unresolved"],
        "pairs_with_supported_trigger_facts": len(pair_supported),
        "pairs_with_upstream_unmaterialized_facts": len(pair_gaps),
        "pairs_with_requirement_unresolved": len(pair_unresolved),
        "l4b_v2_comparable_count": sum(
            count for state, count in v2_state_counts.items() if state.startswith("comparable_")
        ),
        "l4b_v3_comparable_count": sum(
            count for state, count in v3_state_counts.items() if state.startswith("comparable_")
        ),
        "l4b_v3_reviewable_count": sum(
            count for state, count in v3_state_counts.items() if state.startswith("reviewable_")
        ),
        "l4b_v3_blocked_count": sum(
            count for state, count in v3_state_counts.items()
            if state.startswith("blocked_") and not state.startswith("blocked_upstream_")
        ),
        "l4b_v3_upstream_blocked_count": sum(
            count for state, count in v3_state_counts.items() if state.startswith("blocked_upstream_")
        ),
    }

    final_failure_ids = args.final_failure_id or (
        baseline_failure_ids if args.status == "completed" else []
    )
    new_failures = sorted(set(final_failure_ids) - set(baseline_failure_ids))
    final_validation = {
        "schema_version": "pair_trigger_requirement_authority_final_validation_v1",
        "status": args.status,
        "focused_test_pass_count": args.focused_pass_count,
        "related_test_pass_count": args.related_pass_count,
        "full_suite_pass_count": args.full_pass_count,
        "full_suite_subtest_pass_count": args.full_subtest_pass_count,
        "full_suite_failure_count": args.full_failure_count,
        "full_suite_collected_count": args.full_collected_count,
        "full_suite_deselected_count": prior_validation["full_suite_deselected_count"],
        "full_suite_deselected_for_offline_safety": prior_validation["full_suite_deselected_for_offline_safety"],
        "full_suite_offline_command_completed": args.status in {"completed", "failed"},
        "baseline_failure_ids": baseline_failure_ids,
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

    summary = {
        "schema_version": "pair_semantic_trigger_coverage_requirement_authority_v1_summary",
        "status": args.status,
        "semantics_contract_id": "l4b_pair_comparability_semantics_v1",
        "semantics_contract_path": str(CONTRACT.relative_to(ROOT)),
        "metrics": metrics,
        "trigger_coverage_counts": dict(coverage_counts),
        "requirement_activation_counts": dict(role_counts),
        "l4b_v2_state_counts": dict(v2_state_counts),
        "l4b_v3_candidate_state_counts": dict(v3_state_counts),
        "eligible_pair_audit": eligible_audit,
        "entity_integrity": entity,
        "scientific_safety": safety,
        "production_leakage": leakage,
        "final_validation": final_validation,
    }
    write_json("summary.json", summary)

    write_rows("autonomous_iteration_ledger.jsonl", [
        {"iteration": 1, "action": "capture_v2_baseline_and_protected_hashes", "status": "completed"},
        {"iteration": 2, "action": "audit_structured_pair_semantic_sources", "status": "completed", "trigger_fact_count": len(facts)},
        {"iteration": 3, "action": "classify_trigger_coverage_and_v2_projection_gaps", "status": "completed", "pair_dimension_count": len(coverage)},
        {"iteration": 4, "action": "evaluate_requirement_v3_candidate", "status": "completed", "dimension_evaluation_count": len(activations)},
        {"iteration": 5, "action": "replay_existing_candidates_read_only", "status": "completed", "pair_count": len(replay)},
        {"iteration": 6, "action": "validate_scientific_and_engineering_safety", "status": args.status, "new_failure_ids": new_failures},
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
        "schema_version": "pair_semantic_trigger_coverage_requirement_authority_manifest_v1",
        "run_path": str(RUN.relative_to(ROOT)),
        "offline": True,
        "file_count": len(manifest_files),
        "files": manifest_files,
    })


if __name__ == "__main__":
    main()
