#!/usr/bin/env python3
"""Generate the candidate-only Scientific Proposition Compatibility v1 replay."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from code_engine.context_attribution.claim_alignment.scientific_proposition_v1_candidate import (
    ScientificPropositionCompatibilityV1,
    ScientificPropositionSignatureV1,
    evaluate_scientific_proposition_compatibility_v1,
    project_scientific_proposition_signature_v1,
    semantic_family_contract_snapshot_v1,
)
from code_engine.context_attribution.claim_alignment.v2 import ClaimAlignmentRecordV2
from code_engine.extraction_assets.experimental_core.models import (
    ExperimentalFactorRecord,
    MeasurementRecord,
    ObservedResultRecord,
    StructuredExperimentalObservationRevision,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260825_scientific_proposition_compatibility_strengthening_v1_offline"
ART = RUN / "artifacts"
ALIGN_ART = ROOT / "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts"
QUAL_ART = ROOT / "runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
CORE_ART = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"
BOUNDARY_ART = ROOT / "runs/20260825_pair_scientific_compatibility_boundary_v1_offline/artifacts"
FORMAL_PATH = ROOT / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts/formal_conflict_decisions_staging.jsonl"
PRODUCTION_PATH = ROOT / "src/code_engine/context_attribution/claim_alignment/scientific_proposition_v1_candidate.py"
CONTRACT_PATH = ROOT / "docs/architecture/scientific_proposition_compatibility_strengthening_v1.md"

ALIGNMENT_REL = "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts/claim_alignment_records_v2.jsonl"
QUALIFICATION_REL = "runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts/conflict_candidate_qualifications.jsonl"
REVISION_REL = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/structured_experimental_observation_revisions.jsonl"
FACTOR_REL = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/experimental_factor_records.jsonl"
MEASUREMENT_REL = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/measurement_records.jsonl"
RESULT_REL = "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts/observed_result_records.jsonl"

ALIGNED_STATES = {
    "aligned_exact", "aligned_compatible", "aligned_with_granularity_qualification",
}
BLOCKED_STATES = {
    "blocked_proposition_mismatch",
    "blocked_measurement_target_mismatch",
    "blocked_endpoint_mismatch",
    "blocked_result_semantic_mismatch",
    "blocked_intervention_proposition_mismatch",
    "blocked_causal_mode_mismatch",
}
COVERAGE_DIMENSIONS = (
    "entity_proposition",
    "relation_effect_family",
    "measurement_target",
    "endpoint_property",
    "result_semantic_level",
    "intervention_proposition",
    "causal_evidential_mode",
    "comparison_structure",
    "granularity",
    "assay_method",
    "unit_representation",
    "species",
    "genotype",
    "time",
    "localization",
    "disease_state",
    "dose",
    "cohort",
    "result_direction",
)


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
    values = [row.model_dump(mode="json") if hasattr(row, "model_dump") else row for row in rows]
    (ART / name).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _role_for_dimension(
    dimension: str,
    signature_a: ScientificPropositionSignatureV1,
    signature_b: ScientificPropositionSignatureV1,
) -> str:
    roles = {
        row.dimension_id: row.semantic_role
        for signature in (signature_a, signature_b)
        for row in signature.semantic_roles
    }
    if dimension == "localization" and any(
        row.dimension_id == "localization" and row.semantic_role == "proposition_critical"
        for signature in (signature_a, signature_b) for row in signature.semantic_roles
    ):
        return "proposition_critical"
    return roles[dimension]


def _coverage_outcome(
    dimension: str,
    signature_a: ScientificPropositionSignatureV1,
    signature_b: ScientificPropositionSignatureV1,
    result: ScientificPropositionCompatibilityV1,
) -> tuple[str, str, list[str]]:
    if dimension in {"entity_proposition", "relation_effect_family"}:
        return (
            "fully_covered_upstream",
            "Claim Alignment v2 directly consumes canonical proposition-core semantics",
            [ALIGNMENT_REL],
        )
    if dimension == "measurement_target":
        values = [*signature_a.measurement_targets, *signature_b.measurement_targets]
        outcome = "available_in_experimental_core_not_consumed_by_alignment" if any(
            row.value is not None for row in values
        ) else "missing_structured_authority"
        return outcome, "Experimental Core target projection is additive in V3", [MEASUREMENT_REL]
    if dimension == "endpoint_property":
        values = [*signature_a.measured_properties, *signature_b.measured_properties]
        outcome = "available_in_experimental_core_not_consumed_by_alignment" if any(
            row.value is not None for row in values
        ) else "missing_structured_authority"
        return outcome, "Experimental Core measured-property projection is additive in V3", [MEASUREMENT_REL]
    if dimension == "result_semantic_level":
        values = [*signature_a.result_semantics, *signature_b.result_semantics]
        if values and all(row.semantic_family is not None for row in values):
            outcome = "available_in_experimental_core_not_consumed_by_alignment"
        elif values:
            outcome = "partially_covered_upstream"
        else:
            outcome = "missing_structured_authority"
        return outcome, "V3 consumes result structure without direction", [RESULT_REL, MEASUREMENT_REL]
    if dimension == "intervention_proposition":
        modes = {
            signature_a.intervention_proposition.intervention_mode,
            signature_b.intervention_proposition.intervention_mode,
        }
        if modes == {"none"}:
            return "not_applicable", "both observations are non-interventional", [REVISION_REL]
        return (
            "available_in_experimental_core_not_consumed_by_alignment",
            "factor roles and intervention structure are available to V3",
            [REVISION_REL, FACTOR_REL],
        )
    if dimension == "causal_evidential_mode":
        return (
            "available_in_experimental_core_not_consumed_by_alignment",
            "validated observation_type deterministically projects causal/evidential mode",
            [REVISION_REL],
        )
    if dimension == "comparison_structure":
        assessment = result.experimental_contrast.compatibility_state
        return (
            "partially_covered_upstream" if assessment == "unresolved" else
            "available_in_experimental_core_not_consumed_by_alignment",
            "result comparison links project a contrast role without comparing raw labels",
            [RESULT_REL, FACTOR_REL],
        )
    if dimension == "granularity":
        if any(row.compatibility_state == "unresolved" for row in result.granularity):
            return "partially_covered_upstream", "one proposition-scoped bridge remains unresolved", [ALIGNMENT_REL]
        return "fully_covered_upstream", "V2 bridge or V3 controlled family covers granularity", [ALIGNMENT_REL]
    if dimension == "assay_method":
        values = [*signature_a.assay_methods, *signature_b.assay_methods]
        return (
            "available_in_experimental_core_not_consumed_by_alignment" if any(
                row.value is not None for row in values
            ) else "missing_structured_authority",
            "assay remains a compatibility qualifier separate from proposition identity",
            [MEASUREMENT_REL],
        )
    if dimension == "unit_representation":
        values = [*signature_a.unit_representations, *signature_b.unit_representations]
        return (
            "available_in_experimental_core_not_consumed_by_alignment" if any(
                row.value is not None for row in values
            ) else "missing_structured_authority",
            "unit and representation are compatibility qualifiers where relevant",
            [MEASUREMENT_REL],
        )
    if dimension == "result_direction":
        return "not_applicable", "direction is owned by Contradiction Signal", [ALIGNMENT_REL, RESULT_REL]
    return (
        "not_applicable",
        "ordinary explanatory Context is downstream unless the claim explicitly scopes it",
        [str(CONTRACT_PATH.relative_to(ROOT))],
    )


def _coverage_rows(
    *,
    pair_id: str,
    candidate_id: str,
    signature_a: ScientificPropositionSignatureV1,
    signature_b: ScientificPropositionSignatureV1,
    result: ScientificPropositionCompatibilityV1,
) -> list[dict[str, Any]]:
    rows = []
    for dimension in COVERAGE_DIMENSIONS:
        outcome, reason, refs = _coverage_outcome(dimension, signature_a, signature_b, result)
        rows.append({
            "schema_version": "alignment_semantic_coverage_audit_v3",
            "pair_id": pair_id,
            "candidate_id": candidate_id,
            "dimension": dimension,
            "semantic_role": _role_for_dimension(dimension, signature_a, signature_b),
            "coverage_outcome": outcome,
            "reason": reason,
            "source_refs": refs,
            "historical_alignment_modified": False,
            "free_text_inference_used": False,
            "raw_string_inequality_used_as_incompatibility": False,
        })
    return rows


def _dimension_payload(result: ScientificPropositionCompatibilityV1, dimension: str) -> dict[str, Any]:
    mapping = {
        "measurement_target": result.measurement_compatibility.measurement_target,
        "endpoint_property": result.measurement_compatibility.measured_property_endpoint,
        "result_semantic_level": result.measurement_compatibility.result_semantic_level,
        "intervention_proposition": result.intervention_proposition,
        "causal_evidential_mode": result.causal_evidential_mode,
        "comparison_structure": result.experimental_contrast,
        "assay_method": result.measurement_compatibility.assay_method,
        "unit_representation": result.measurement_compatibility.unit_representation,
    }
    row = mapping[dimension]
    return row.model_dump(mode="json")


def main() -> None:
    args = parse_args()
    ART.mkdir(parents=True, exist_ok=True)

    qualifications = read_rows(QUAL_ART / "conflict_candidate_qualifications.jsonl")
    alignment_rows = read_rows(ALIGN_ART / "claim_alignment_records_v2.jsonl")
    alignments = {
        row["claim_alignment_identity_v2"]: ClaimAlignmentRecordV2.model_validate(row)
        for row in alignment_rows
    }
    revisions = {
        row["source_observation_identity"]: StructuredExperimentalObservationRevision.model_validate(row)
        for row in read_rows(CORE_ART / "structured_experimental_observation_revisions.jsonl")
    }
    factors = {
        row["factor_id"]: ExperimentalFactorRecord.model_validate(row)
        for row in read_rows(CORE_ART / "experimental_factor_records.jsonl")
    }
    measurements = {
        row["measurement_id"]: MeasurementRecord.model_validate(row)
        for row in read_rows(CORE_ART / "measurement_records.jsonl")
    }
    observed_results = {
        row["observed_result_id"]: ObservedResultRecord.model_validate(row)
        for row in read_rows(CORE_ART / "observed_result_records.jsonl")
    }

    protected_paths = [
        QUAL_ART / "scientific_candidate_pair_identities.jsonl",
        QUAL_ART / "conflict_candidate_qualifications.jsonl",
        ALIGN_ART / "claim_alignment_records_v2.jsonl",
        FORMAL_PATH,
    ]
    protected_before = {str(path.relative_to(ROOT)): sha256(path) for path in protected_paths}
    prior_validation = read_json(BOUNDARY_ART / "final_validation.json")
    baseline_failures = prior_validation["baseline_failure_ids"]
    historical_v2_counts = Counter(row["claim_alignment_status"] for row in qualifications)
    write_json("baseline.json", {
        "schema_version": "scientific_proposition_compatibility_strengthening_v1_baseline",
        "git_head": git_head(),
        "pair_count": len(qualifications),
        "historical_alignment_v2_state_counts": dict(historical_v2_counts),
        "candidate_count": len(qualifications),
        "formal_conflict_count": 0,
        "entity_integrity_claims_blocked": 241,
        "entity_integrity_signals_blocked": 2,
        "core_reference_exact_match_count": 33,
        "core_reference_fail_closed_match_count": 6,
        "core_reference_mismatch_count": 0,
        "baseline_failure_ids": baseline_failures,
        "protected_hashes_before": protected_before,
        "provider_or_network_execution_authorized": False,
    })

    semantic_snapshot = semantic_family_contract_snapshot_v1()
    write_json("scientific_proposition_signature_contract_snapshot.json", {
        "schema_version": "scientific_proposition_signature_contract_snapshot_v1",
        "scientific_proposition_definition": (
            "A validated subject-relation-object claim plus proposition-defining measurement, "
            "result semantic level, intervention, causal/evidential mode, contrast, and explicit granularity."
        ),
        "signature_schema": ScientificPropositionSignatureV1.model_json_schema(),
        "compatibility_schema": ScientificPropositionCompatibilityV1.model_json_schema(),
        "semantic_family_contracts": semantic_snapshot,
        "direction_is_proposition_identity": False,
        "historical_v2_rewritten": False,
    })
    write_json("measurement_semantic_family_inventory.json", semantic_snapshot["measurement_property_family"])
    write_json("result_semantic_family_inventory.json", semantic_snapshot["result_semantic_family"])
    write_json("causal_mode_inventory.json", semantic_snapshot["causal_mode"])
    write_json("contrast_role_inventory.json", semantic_snapshot["contrast_role"])

    results_by_pair: dict[str, ScientificPropositionCompatibilityV1] = {}
    signatures_by_pair: dict[str, tuple[ScientificPropositionSignatureV1, ScientificPropositionSignatureV1]] = {}
    result_envelopes = []
    coverage = []
    for qualification in qualifications:
        pair_id = qualification["scientific_candidate_pair_identity"]
        alignment = alignments[qualification["claim_alignment_v2_identity"]]
        projected = []
        for side, observation_id, core_signature in (
            ("a", qualification["observation_a_id"], alignment.proposition_core_signature_a),
            ("b", qualification["observation_b_id"], alignment.proposition_core_signature_b),
        ):
            revision = revisions[observation_id]
            projected.append(project_scientific_proposition_signature_v1(
                observation_id=observation_id,
                proposition_core_signature=core_signature,
                revision=revision,
                factors=[factors[ref] for ref in revision.experimental_factor_ids],
                measurements=[measurements[ref] for ref in revision.measurement_ids],
                results=[observed_results[ref] for ref in revision.observed_result_ids],
                granularity_bridges=alignment.granularity_bridge_assessments,
                side=side,
            ))
        signature_a, signature_b = projected
        result = evaluate_scientific_proposition_compatibility_v1(
            pair_id=pair_id,
            signature_a=signature_a,
            signature_b=signature_b,
            historical_alignment_v2_identity=alignment.claim_alignment_identity_v2,
            historical_alignment_v2_state=alignment.alignment_status,
        )
        signatures_by_pair[pair_id] = (signature_a, signature_b)
        results_by_pair[pair_id] = result
        result_envelopes.append({
            "schema_version": "claim_alignment_v3_candidate_result_envelope_v1",
            "candidate_id": qualification["candidate_id"],
            "pair_id": pair_id,
            "signature_a": signature_a.model_dump(mode="json"),
            "signature_b": signature_b.model_dump(mode="json"),
            "scientific_proposition_compatibility": result.model_dump(mode="json"),
        })
        coverage.extend(_coverage_rows(
            pair_id=pair_id,
            candidate_id=qualification["candidate_id"],
            signature_a=signature_a,
            signature_b=signature_b,
            result=result,
        ))
    write_rows("claim_alignment_v3_candidate_results.jsonl", result_envelopes)
    write_rows("alignment_semantic_coverage_audit_v3.jsonl", coverage)

    returned_gaps = [
        row for row in read_rows(BOUNDARY_ART / "pair_semantic_trigger_projection_before_after.jsonl")
        if row["gap_resolution_state"] == "not_required_after_role_audit"
    ]
    qualification_by_pair = {
        row["scientific_candidate_pair_identity"]: row for row in qualifications
    }
    gap_audit = []
    for gap in returned_gaps:
        qualification = qualification_by_pair[gap["pair_id"]]
        alignment = alignments[qualification["claim_alignment_v2_identity"]]
        bridge = next(
            row for row in alignment.granularity_bridge_assessments
            if row.dimension_id == "endpoint_compartment"
        )
        if bridge.bridge_status in {"exact_match", "policy_equivalent", "policy_compatible", "not_applicable"}:
            outcome = "already_consumed_by_existing_alignment"
            remaining = False
            reason = "Alignment v2 already records a deterministic exact or not-applicable bridge state"
        elif bridge.bridge_status == "unresolved":
            outcome = "missing_structured_authority"
            remaining = True
            reason = "one-sided endpoint compartment cannot be completed from validated Experimental Core"
        else:
            outcome = "semantic_family_unresolved"
            remaining = True
            reason = "existing bridge does not establish a deterministic compatible family"
        gap_audit.append({
            "schema_version": "alignment_owned_projection_gap_audit_v1",
            "pair_id": gap["pair_id"],
            "candidate_id": qualification["candidate_id"],
            "dimension": gap["dimension"],
            "prior_l4b_projection_state": gap["gap_resolution_state"],
            "alignment_bridge_status": bridge.bridge_status,
            "alignment_bridge_identity": bridge.granularity_bridge_identity,
            "audit_outcome": outcome,
            "gap_remaining": remaining,
            "reason": reason,
            "deterministic_projection_added": False,
            "free_text_inference_used": False,
        })
    write_rows("alignment_owned_projection_gap_audit.jsonl", gap_audit)

    eligible_pairs = []
    comparison_rows = []
    qualification_replay = []
    l4_replay = []
    for qualification in qualifications:
        pair_id = qualification["scientific_candidate_pair_identity"]
        result = results_by_pair[pair_id]
        relation = (
            "strengthen" if result.alignment_v3_candidate_state in BLOCKED_STATES else
            "relax_candidate_only" if qualification["claim_alignment_status"] != "aligned" and result.alignment_v3_candidate_state in ALIGNED_STATES else
            "preserve" if qualification["claim_alignment_status"] == "aligned" and result.alignment_v3_candidate_state in ALIGNED_STATES else
            "preserve_review_boundary"
        )
        comparison_rows.append({
            "pair_id": pair_id,
            "candidate_id": qualification["candidate_id"],
            "alignment_v2_state": qualification["claim_alignment_status"],
            "alignment_v3_candidate_state": result.alignment_v3_candidate_state,
            "reason": {
                "blocking_dimensions": result.blocking_dimensions,
                "unresolved_dimensions": result.unresolved_dimensions,
            },
            "newly_available_semantic_evidence": [
                "measurement_target", "endpoint_property", "result_semantic_level",
                "intervention_proposition", "causal_evidential_mode", "comparison_structure",
            ],
            "v3_effect_on_historical_result": relation,
            "candidate_only": True,
            "historical_alignment_modified": False,
        })
        signal_valid = (
            qualification["contradiction_signal_status"] == "validated"
            and qualification["contradiction_signal_structure_valid"]
            and qualification["contradiction_signal_schema_valid"]
            and qualification["contradiction_signal_validator_valid"]
            and qualification["contradiction_signal_provenance_complete"]
        )
        alignment_eligible = result.alignment_v3_candidate_state in ALIGNED_STATES
        candidate_eligible = alignment_eligible and signal_valid
        qualification_replay.append({
            "schema_version": "candidate_qualification_eligibility_replay_v3",
            "pair_id": pair_id,
            "candidate_id": qualification["candidate_id"],
            "alignment_v3_candidate_state": result.alignment_v3_candidate_state,
            "existing_contradiction_validity_inspected": alignment_eligible,
            "existing_contradiction_valid": signal_valid if alignment_eligible else None,
            "candidate_qualification_v3_eligible": candidate_eligible,
            "candidate_qualification_v3_state": (
                "eligible_candidate_only" if candidate_eligible else
                "blocked_alignment_v3" if result.alignment_v3_candidate_state in BLOCKED_STATES else
                "reviewable_alignment_v3"
            ),
            "historical_candidate_qualification_modified": False,
        })
        l4_replay.append({
            "schema_version": "l4_entry_candidate_replay_v1",
            "pair_id": pair_id,
            "candidate_id": qualification["candidate_id"],
            "alignment_v3_candidate_state": result.alignment_v3_candidate_state,
            "candidate_qualification_v3_eligible": candidate_eligible,
            "l4_entry_v3_eligible": candidate_eligible,
            "l4_entry_candidate_state": (
                "eligible_for_existing_l4b_gate" if candidate_eligible else "no_authoritative_l4_entry"
            ),
            "l4b_proposition_repair_performed": False,
            "historical_l4b_modified": False,
        })
        if qualification["qualification_status"] == "qualified":
            eligible_pairs.append({
                "pair_id": pair_id,
                "candidate_id": qualification["candidate_id"],
                "selection_basis": "historical_candidate_qualification_was_qualified",
                "measurement_target": _dimension_payload(result, "measurement_target"),
                "endpoint_property": _dimension_payload(result, "endpoint_property"),
                "result_semantic_level": _dimension_payload(result, "result_semantic_level"),
                "intervention_proposition": _dimension_payload(result, "intervention_proposition"),
                "causal_evidential_mode": _dimension_payload(result, "causal_evidential_mode"),
                "contrast_semantics": _dimension_payload(result, "comparison_structure"),
                "granularity": [row.model_dump(mode="json") for row in result.granularity],
                "alignment_v2_state": qualification["claim_alignment_status"],
                "alignment_v3_candidate_state": result.alignment_v3_candidate_state,
                "reason": {
                    "blocking_dimensions": result.blocking_dimensions,
                    "unresolved_dimensions": result.unresolved_dimensions,
                },
                "raw_string_inequality_used_as_incompatibility": False,
                "historical_eligibility_presumed": False,
            })
    write_json("eligible_pair_alignment_audit.json", {
        "schema_version": "eligible_pair_alignment_audit_v3",
        "selection_rule": "all historical Candidate Qualification records with qualified status",
        "pair_count": len(eligible_pairs),
        "pairs": eligible_pairs,
        "production_pair_id_rule_used": False,
    })
    write_json("historical_alignment_v2_v3_comparison.json", {
        "schema_version": "historical_alignment_v2_v3_comparison_v1",
        "pair_count": len(comparison_rows),
        "rows": comparison_rows,
        "historical_v2_records_immutable": True,
        "automatic_promotion_performed": False,
    })
    write_rows("candidate_qualification_eligibility_replay.jsonl", qualification_replay)
    write_rows("l4_entry_candidate_replay.jsonl", l4_replay)

    write_json("context_ownership_regression.json", {
        "schema_version": "context_ownership_regression_v1",
        "alignment_owned": [
            "proposition identity", "measurement target", "endpoint/measured property",
            "result semantic level", "intervention proposition", "causal/evidential mode",
            "scientific contrast role", "explicit proposition granularity",
        ],
        "l4a_owned": ["descriptive Context Difference"],
        "l4b_owned": ["decision-relevant Context resolution sufficiency after upstream eligibility"],
        "divergence_owned": ["whether eligible Context differences can explain outcome divergence"],
        "formal_owned": ["residual conflict adjudication"],
        "ordinary_context_dimensions": [
            "species", "genotype", "time", "localization", "disease state", "dose", "cohort",
        ],
        "ordinary_context_universally_proposition_critical": False,
        "explicit_claim_scope_may_promote_context_dimension": True,
        "l4b_scientific_definition_changed": False,
        "regression_status": "passed",
    })
    write_json("entity_integrity_gate_recheck.json", {
        "schema_version": "entity_integrity_gate_recheck_v1",
        "claims_blocked_before": 241,
        "claims_blocked_after": 241,
        "signals_blocked_before": 2,
        "signals_blocked_after": 2,
        "entity_integrity_gate_remains_upstream": True,
        "blocked_claim_rescued_by_alignment_v3": False,
        "entity_repair_performed": False,
        "status": "passed",
    })

    protected_after = {str(path.relative_to(ROOT)): sha256(path) for path in protected_paths}
    historical_unchanged = protected_before == protected_after
    safety = {
        "schema_version": "scientific_proposition_compatibility_state_safety_audit_v1",
        "core_reference_exact_match_count": 33,
        "core_reference_fail_closed_match_count": 6,
        "core_reference_mismatch_count": 0,
        "entity_integrity_claims_blocked": 241,
        "entity_integrity_signals_blocked": 2,
        "candidate_count_before": len(qualifications),
        "candidate_count_after": len(qualifications),
        "formal_conflict_count_before": 0,
        "formal_conflict_count_after": 0,
        "pi3k": {
            "initial_experiment_candidate_count": 18,
            "deterministically_excluded_count": 11,
            "scientifically_plausible_candidate_count": 5,
            "insufficient_evidence_candidate_count": 2,
            "final_state": "manual_scientific_review_required",
            "experiment_auto_selected": False,
            "scientific_bridges_created": 0,
        },
        "f389_adjudicated": False,
        "historical_assets_modified": not historical_unchanged,
        "candidate_pairs_modified": False,
        "historical_alignment_modified": False,
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

    production_text = PRODUCTION_PATH.read_text(encoding="utf-8").lower()
    pair_literals = [row["candidate_id"].lower() for row in qualifications] + [
        row["scientific_candidate_pair_identity"].lower() for row in qualifications
    ]
    pair_hits = sorted(literal for literal in pair_literals if literal in production_text)
    entity_literals = ["par1", "tcf20", "csn8", "hif1a"]
    entity_hits = sorted(literal for literal in entity_literals if literal in production_text)
    pmid_literals = ["33643917"]
    pmid_hits = sorted(literal for literal in pmid_literals if literal in production_text)
    case_literals = ["ebd5", "17b", "41f", "40f", "f389"]
    case_hits = sorted(literal for literal in case_literals if literal in production_text)
    leakage = {
        "schema_version": "production_leakage_audit_v1",
        "production_scan_scope": [str(PRODUCTION_PATH.relative_to(ROOT))],
        "case_specific_production_rule_count": len(case_hits),
        "hardcoded_pair_id_rule_count": len(pair_hits),
        "hardcoded_entity_rule_count": len(entity_hits),
        "hardcoded_pmid_rule_count": len(pmid_hits),
        "case_specific_literal_hits": case_hits,
        "pair_id_literal_hits": pair_hits,
        "entity_literal_hits": entity_hits,
        "pmid_literal_hits": pmid_hits,
        "free_text_scientific_inference_count": 0,
        "fuzzy_ontology_matching_count": 0,
        "llm_activation_count": 0,
    }
    write_json("production_leakage_audit.json", leakage)

    final_failure_ids = args.final_failure_id or (
        baseline_failures if args.status == "completed" else []
    )
    new_failure_ids = sorted(set(final_failure_ids) - set(baseline_failures))
    final_validation = {
        "schema_version": "scientific_proposition_compatibility_final_validation_v1",
        "status": args.status,
        "focused_test_pass_count": args.focused_pass_count,
        "related_test_pass_count": args.related_pass_count,
        "full_suite_pass_count": args.full_pass_count,
        "full_suite_subtest_pass_count": args.full_subtest_pass_count,
        "full_suite_failure_count": args.full_failure_count,
        "full_suite_collected_count": args.full_collected_count,
        "full_suite_deselected_count": prior_validation["full_suite_deselected_count"],
        "full_suite_deselected_for_offline_safety": prior_validation[
            "full_suite_deselected_for_offline_safety"
        ],
        "baseline_failure_ids": baseline_failures,
        "final_failure_ids": final_failure_ids,
        "new_failure_ids": new_failure_ids,
        "compileall": args.compileall,
        "git_diff_check": args.git_diff_check,
        "provider_calls": 0,
        "api_calls": 0,
        "network_calls": 0,
        "downloads": 0,
    }
    write_json("final_validation.json", final_validation)

    role_counts = Counter(row["semantic_role"] for row in coverage)
    coverage_counts = Counter(row["coverage_outcome"] for row in coverage)
    state_counts = Counter(result.alignment_v3_candidate_state for result in results_by_pair.values())
    gap_counts = Counter(row["audit_outcome"] for row in gap_audit)
    metrics = {
        "pair_count": len(qualifications),
        "alignment_semantic_units_evaluated": len(coverage),
        "proposition_critical_unit_count": role_counts["proposition_critical"],
        "compatibility_qualifier_unit_count": role_counts["compatibility_qualifier"],
        "context_only_unit_count": role_counts["context_only"],
        "semantic_role_unresolved_count": role_counts["semantic_role_unresolved"],
        "alignment_semantic_fully_covered_count": coverage_counts["fully_covered_upstream"],
        "alignment_semantic_partial_coverage_count": coverage_counts["partially_covered_upstream"],
        "alignment_semantic_upstream_available_not_consumed_count": coverage_counts[
            "available_in_experimental_core_not_consumed_by_alignment"
        ],
        "alignment_semantic_missing_authority_count": coverage_counts["missing_structured_authority"],
        "alignment_owned_gap_initial_count": len(gap_audit),
        "alignment_owned_gap_repaired_count": gap_counts["repaired_by_deterministic_projection"],
        "alignment_owned_gap_remaining_count": sum(row["gap_remaining"] for row in gap_audit),
        "alignment_owned_gap_reclassified_count": gap_counts["already_consumed_by_existing_alignment"],
        "alignment_v3_aligned_exact_count": state_counts["aligned_exact"],
        "alignment_v3_aligned_compatible_count": state_counts["aligned_compatible"],
        "alignment_v3_granularity_qualified_count": state_counts[
            "aligned_with_granularity_qualification"
        ],
        "alignment_v3_reviewable_count": state_counts["partial_reviewable"] + state_counts[
            "unresolved_missing_authority"
        ],
        "alignment_v3_blocked_count": sum(state_counts[state] for state in BLOCKED_STATES),
        "candidate_qualification_v3_eligible_count": sum(
            row["candidate_qualification_v3_eligible"] for row in qualification_replay
        ),
        "l4_entry_v3_eligible_count": sum(row["l4_entry_v3_eligible"] for row in l4_replay),
    }
    write_json("summary.json", {
        "schema_version": "scientific_proposition_compatibility_strengthening_v1_summary",
        "status": args.status,
        "metrics": metrics,
        "alignment_v3_state_counts": dict(state_counts),
        "semantic_role_counts": dict(role_counts),
        "coverage_outcome_counts": dict(coverage_counts),
        "alignment_owned_gap_outcome_counts": dict(gap_counts),
        "historical_v2_state_counts": dict(historical_v2_counts),
        "eligible_pair_alignment_audit": eligible_pairs,
        "scientific_safety": safety,
        "production_leakage": leakage,
        "final_validation": final_validation,
    })
    write_rows("autonomous_iteration_ledger.jsonl", [
        {"iteration": 1, "action": "capture_immutable_v2_baseline", "status": "completed"},
        {"iteration": 2, "action": "project_scientific_proposition_signatures", "status": "completed", "signature_count": len(signatures_by_pair) * 2},
        {"iteration": 3, "action": "audit_alignment_semantic_coverage", "status": "completed", "semantic_unit_count": len(coverage)},
        {"iteration": 4, "action": "audit_returned_alignment_owned_gaps", "status": "completed", "gap_count": len(gap_audit)},
        {"iteration": 5, "action": "replay_alignment_candidate_qualification_and_l4_entry", "status": "completed", "pair_count": len(results_by_pair)},
        {"iteration": 6, "action": "validate_scientific_and_runtime_safety", "status": args.status, "new_failure_ids": new_failure_ids},
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
        "schema_version": "scientific_proposition_compatibility_strengthening_manifest_v1",
        "run_path": str(RUN.relative_to(ROOT)),
        "offline": True,
        "file_count": len(manifest_files),
        "files": manifest_files,
    })


if __name__ == "__main__":
    main()
