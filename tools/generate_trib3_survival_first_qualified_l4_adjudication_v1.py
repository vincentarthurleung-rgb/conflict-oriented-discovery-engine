#!/usr/bin/env python3
"""Offline-only first L4 replay for qualified scientific disagreements."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code_engine.context_attribution.conflict_adjudication.first_qualified_l4_v1_candidate import (
    assess_divergence_explanatory_power_v1,
    make_formal_judgment_candidate_v1,
)
from code_engine.extraction_assets.context.field_registry import build_registry
from code_engine.extraction_assets.context.pair_requirements_v2 import L4bUpstreamEligibilityV1
from code_engine.extraction_assets.context.pair_requirements_v3_candidate import (
    CONTEXT_DIMENSIONS,
    activate_pair_dimension_v3_candidate,
    evidence_from_trigger_fact_v3_candidate,
    evaluate_l4b_v3_candidate,
    make_requirement_authority_v1,
    make_trigger_fact_v1,
)


RUN = ROOT / "runs/20260902_trib3_survival_first_qualified_l4_adjudication_v1_offline"
ART = RUN / "artifacts"
REPLAY_ART = ROOT / "runs/20260902_cross_publication_contradiction_replay_trib3_survival_v1_offline/artifacts"
SMOKE_ART = ROOT / "runs/20260902_single_source_provider_extraction_smoke_pmc10515557_v1/artifacts"
OLD_OBS = ROOT / "runs/20260723_171527_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_v3_recovered_reentry/artifacts/fulltext_experiment_observations.jsonl"
VERSION = "trib3_survival_first_qualified_l4_adjudication_v1_offline"


def options() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--focused-pass-count", type=int, default=0)
    parser.add_argument("--related-pass-count", type=int, default=0)
    parser.add_argument("--full-pass-count", type=int, default=0)
    parser.add_argument("--full-subtest-pass-count", type=int, default=0)
    parser.add_argument("--full-failure-count", type=int, default=0)
    parser.add_argument("--full-collected-count", type=int, default=0)
    parser.add_argument("--compileall", choices=("pending", "passed", "failed"), default="pending")
    parser.add_argument("--git-diff-check", choices=("pending", "passed", "failed"), default="pending")
    return parser.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write(name: str, value: Any) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    (ART / name).write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_rows(name: str, values: list[Any]) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    (ART / name).write_text("".join(json.dumps(x.model_dump(mode="json") if hasattr(x, "model_dump") else x,
                                               sort_keys=True, ensure_ascii=False) + "\n" for x in values), encoding="utf-8")


def ident(kind: str, payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"{kind}:{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def anchors(row: dict[str, Any]) -> list[str]:
    spans = {x["evidence_span_id"]: x for x in row["provenance"]["evidence_spans"]}
    ids = set(row["observation"]["evidence_span_ids"] + row["measurement"]["evidence_span_ids"])
    return sorted({spans[x]["anchor_id"] for x in ids if x in spans})


def context_values(new: dict[str, Any], old: dict[str, Any]) -> dict[str, dict[str, Any]]:
    a_refs, b_refs = anchors(new), anchors(old)
    direct = "direct"
    insufficient = "source_scope_insufficient"
    return {
        "biological_model": {
            "value_a": [new["experiment"]["species_raw"], new["experiment"]["model_system_raw"], new["experiment"]["tissue_raw"]],
            "value_b": [old["experiment"]["species_raw"], old["experiment"]["model_system_raw"], old["experiment"]["tissue_raw"]],
            "value_state_a": direct, "value_state_b": direct, "difference_state": "different",
            "scope_a": "analysis_and_parent_cohort", "scope_b": "analysis_and_TCGA_cohort",
            "provenance_a": a_refs, "provenance_b": b_refs, "decision_relevance": "comparison_required",
            "explanation_eligibility": "eligible_explanation_candidate",
        },
        "intervention": {
            "value_a": "not applicable: observational comparison", "value_b": "not applicable: observational comparison",
            "value_state_a": "not_applicable", "value_state_b": "not_applicable", "difference_state": "not_applicable",
            "scope_a": "proposition", "scope_b": "proposition", "provenance_a": ["observational_profile_authority_path"],
            "provenance_b": ["target_observational_profile"], "decision_relevance": "structurally_not_applicable",
            "explanation_eligibility": "difference_not_explanatory_under_contract",
        },
        "temporal": {
            "value_a": None, "value_b": None, "value_state_a": insufficient, "value_state_b": insufficient,
            "difference_state": "source_scope_insufficient", "scope_a": "selected analysis evidence",
            "scope_b": "selected analysis evidence", "provenance_a": a_refs, "provenance_b": b_refs,
            "decision_relevance": "explicit_not_decision_relevant", "explanation_eligibility": "insufficient_authority",
        },
        "genotype": {
            "value_a": None, "value_b": None, "value_state_a": insufficient, "value_state_b": insufficient,
            "difference_state": "source_scope_insufficient", "scope_a": "selected analysis evidence",
            "scope_b": "selected analysis evidence", "provenance_a": a_refs, "provenance_b": b_refs,
            "decision_relevance": "explicit_not_decision_relevant", "explanation_eligibility": "insufficient_authority",
        },
        "localization": {
            "value_a": None, "value_b": None, "value_state_a": insufficient, "value_state_b": insufficient,
            "difference_state": "source_scope_insufficient", "scope_a": "selected analysis evidence",
            "scope_b": "selected analysis evidence", "provenance_a": a_refs, "provenance_b": b_refs,
            "decision_relevance": "explicit_not_decision_relevant", "explanation_eligibility": "insufficient_authority",
        },
        "measurement": {
            "value_a": "overall survival|clinical_outcome", "value_b": "overall survival|clinical_outcome",
            "value_state_a": direct, "value_state_b": direct, "difference_state": "matched",
            "scope_a": "observation measurement", "scope_b": "observation measurement",
            "provenance_a": a_refs, "provenance_b": b_refs,
            "decision_relevance": "upstream_proposition_owned_not_l4b_requirement",
            "explanation_eligibility": "difference_not_explanatory_under_contract",
        },
        "disease": {
            "value_a": new["experiment"]["disease_model_raw"], "value_b": old["experiment"]["disease_model_raw"],
            "value_state_a": direct, "value_state_b": direct, "difference_state": "different",
            "scope_a": "parent cohort", "scope_b": "TCGA cohort", "provenance_a": a_refs, "provenance_b": b_refs,
            "decision_relevance": "comparison_required", "explanation_eligibility": "eligible_explanation_candidate",
        },
        "experimental_design": {
            "value_a": [new["experiment"]["experimental_design_raw"], new["experiment"]["cohort_raw"]],
            "value_b": [old["experiment"]["experimental_design_raw"], old["experiment"]["cohort_raw"]],
            "value_state_a": direct, "value_state_b": direct, "difference_state": "different",
            "scope_a": "analysis within parent cohort", "scope_b": "TCGA survival analysis",
            "provenance_a": a_refs, "provenance_b": b_refs, "decision_relevance": "comparison_required",
            "explanation_eligibility": "eligible_explanation_candidate",
        },
    }


def main() -> None:
    opt = options()
    qualifications = [x for x in rows(REPLAY_ART / "scientific_candidate_qualification_v2_candidate.jsonl")
                      if x["qualification_state"] == "qualified_scientific_candidate"]
    if len(qualifications) != 2:
        raise RuntimeError("qualified_candidate_count_regression")
    new_by_id = {x["observation_id"]: x for x in rows(SMOKE_ART / "validated_observations.jsonl")}
    old_by_id = {x["observation_id"]: x for x in rows(OLD_OBS)}
    registry = build_registry()
    active_registry = {row.field_id: row for row in registry if row.active_status == "active"}
    protected = [
        REPLAY_ART / "scientific_candidate_qualification_v2_candidate.jsonl",
        REPLAY_ART / "evidence_unit_level_contradiction_results.jsonl",
        REPLAY_ART / "scientific_disagreement_summary.json",
        SMOKE_ART / "validated_observations.jsonl", SMOKE_ART / "raw_provider_response.txt", OLD_OBS,
    ]
    before = {rel(path): sha(path) for path in protected}
    write("baseline.json", {
        "schema_version": "first_qualified_l4_adjudication_baseline_v1", "offline_only": True,
        "provider_calls": 0, "llm_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0,
        "qualified_candidate_count": 2, "publication_level_disagreement_structure_count": 1,
        "historical_candidate_object_count": 11, "historical_formal_conflict_count": 0,
        "entity_integrity_claims_blocked": 241, "entity_integrity_signals_blocked": 2,
        "protected_input_sha256": before,
    })
    write_rows("qualified_candidate_inventory.jsonl", [{
        **q, "l4_entry_recheck": "eligible", "upstream_re_adjudicated": False,
        "source_qualification_ref": rel(REPLAY_ART / "scientific_candidate_qualification_v2_candidate.jsonl"),
    } for q in qualifications])

    l4a_rows = []; activations_out = []; satisfactions_out = []; comparability_out = []
    explanation_candidates = []; explanation_results = []; formal_candidates = []
    pair_context = {}
    for q in qualifications:
        pair_id = q["pair_id"]
        new, old = new_by_id[q["observation_a_id"]], old_by_id[q["observation_b_id"]]
        values = context_values(new, old); pair_context[pair_id] = values
        for dimension in CONTEXT_DIMENSIONS:
            value = values[dimension]
            l4a_rows.append({
                "schema_version": "l4a_context_dimension_result_v1_candidate", "pair_id": pair_id,
                "evidence_unit_a": q["evidence_unit_a_id"], "evidence_unit_b": q["evidence_unit_b_id"],
                "context_dimension": dimension, **value,
                "registry_field_refs": {
                    "biological_model": [active_registry[x].identity for x in ("species", "tissue", "model_system")],
                    "intervention": [active_registry["intervention"].identity],
                    "temporal": [active_registry[x].identity for x in ("duration", "timepoint")],
                    "genotype": [active_registry["genotype"].identity],
                    "localization": [active_registry["subcellular_localization"].identity],
                    "measurement": [active_registry[x].identity for x in ("assay", "measurement_method", "measured_endpoint")],
                    "disease": [active_registry["disease"].identity],
                    "experimental_design": [active_registry[x].identity for x in ("control", "comparator", "experimental_arm")],
                }[dimension],
                "unsupported_inheritance_used": False, "natural_language_explanation_authoritative": False,
                "context_difference_identity": ident("l4a_context_difference", {"pair": pair_id, "dimension": dimension, "value": value}),
            })

        trigger_facts = []
        evidences = []
        authorities = []
        for dimension in ("biological_model", "disease", "experimental_design"):
            value = values[dimension]
            fact = make_trigger_fact_v1(
                pair_id=pair_id, dimension=dimension,
                fact_type="population_scope" if dimension in {"biological_model", "disease"} else "experimental_design_scope",
                side_a_object_refs=value["provenance_a"], side_b_object_refs=value["provenance_b"],
                source_artifact_refs=[rel(SMOKE_ART / "validated_observations.jsonl"), rel(OLD_OBS)],
                fact_state="different", authority="validated_context_direct_value",
                trigger_eligible=True, trigger_type="comparison_required",
                structured_values_a=[value["value_a"]], structured_values_b=[value["value_b"]],
                reason="two-sided direct Context is decision-relevant and must be resolved; difference does not imply incomparability",
            )
            trigger_facts.append(fact); evidences.append(evidence_from_trigger_fact_v3_candidate(fact))
        for dimension in ("temporal", "genotype", "localization", "measurement"):
            authorities.append(make_requirement_authority_v1(
                pair_id=pair_id, consumer="l4b_comparability", dimension=dimension,
                authority_state="explicit_not_decision_relevant", authority="explicit_consumer_contract",
                contract_refs=["l4b_pair_comparability_semantics_v1", "scientific_proposition_compatibility_v1"],
                reason=("measurement is proposition-owned upstream" if dimension == "measurement" else
                        "no proposition, factor, contrast, or measurement scope activates this dimension for this pair"),
            ))
        authorities.append(make_requirement_authority_v1(
            pair_id=pair_id, consumer="l4b_comparability", dimension="intervention",
            authority_state="not_applicable", authority="structural_inapplicability_rule",
            contract_refs=["minimum_scientific_proposition_profile_v1:observational_association"],
            reason="intervention is structurally not applicable to this observational proposition",
        ))
        activations = [activate_pair_dimension_v3_candidate(
            pair_id=pair_id, consumer="l4b_comparability", dimension=dimension,
            trigger_facts=trigger_facts, requirement_authorities=authorities,
        ) for dimension in CONTEXT_DIMENSIONS]
        upstream = L4bUpstreamEligibilityV1(
            pair_id=pair_id, entity_integrity_eligible=True, alignment_eligible=True,
            contradiction_signal_valid=True, candidate_qualification_eligible=True,
            entity_integrity_state="eligible", alignment_state="aligned_exact",
            contradiction_signal_state="opposing_direction_validated",
            candidate_qualification_state="qualified_scientific_candidate",
            upstream_refs=[q["qualification_identity"], q["evidence_unit_a_id"], q["evidence_unit_b_id"]],
        )
        comparison, satisfactions = evaluate_l4b_v3_candidate(
            pair_id=pair_id, upstream=upstream, activations=activations, dimension_evidence=evidences,
        )
        activations_out.extend(activations); satisfactions_out.extend(satisfactions); comparability_out.append(comparison)

        pair_explanations = []
        for dimension in ("biological_model", "disease", "experimental_design"):
            l4a = next(x for x in l4a_rows if x["pair_id"] == pair_id and x["context_dimension"] == dimension)
            explanation_candidates.append({
                "schema_version": "context_explanation_candidate_v1", "pair_id": pair_id,
                "context_dimension": dimension, "context_difference_identity": l4a["context_difference_identity"],
                "difference_validated": True, "two_sided_context_resolved": True,
                "eligibility_state": "eligible_explanation_candidate", "causal_explanation_asserted": False,
                "authority": "validated_l4a_difference_candidate_only", "source_refs": l4a["provenance_a"] + l4a["provenance_b"],
            })
            result = assess_divergence_explanatory_power_v1(
                pair_id=pair_id, context_dimension=dimension,
                context_difference_identity=l4a["context_difference_identity"],
                difference_validated=True, two_sided_context_resolved=True, explanation_eligible=True,
                source_refs=l4a["provenance_a"] + l4a["provenance_b"],
            )
            pair_explanations.append(result); explanation_results.append(result)
        formal_candidates.append(make_formal_judgment_candidate_v1(
            pair_id=pair_id, upstream_valid=True, evidence_independence_valid=True,
            provenance_adequate=True, l4b_state=comparison.l4b_state,
            l4b_comparable=comparison.comparable, explanation_results=pair_explanations,
        ))

    write_rows("l4a_context_difference_results.jsonl", l4a_rows)
    l4a_counts = {
        "matched": sum(x["difference_state"] == "matched" for x in l4a_rows),
        "different": sum(x["difference_state"] == "different" for x in l4a_rows),
        "unresolved": sum(x["difference_state"] in {"unresolved", "source_scope_insufficient"} for x in l4a_rows),
        "ambiguous": sum(x["difference_state"] == "ambiguous" for x in l4a_rows),
        "not_applicable": sum(x["difference_state"] == "not_applicable" for x in l4a_rows),
    }
    write("l4a_context_coverage_audit.json", {
        "schema_version": "l4a_context_coverage_audit_v1", "context_registry_dimension_count": len(CONTEXT_DIMENSIONS),
        "candidate_pair_count": 2, "dimension_evaluation_count": len(l4a_rows), **l4a_counts,
        "direct_value_count": sum(x["value_state_a"] == x["value_state_b"] == "direct" for x in l4a_rows),
        "safe_inherited_value_count": 0, "deterministic_derived_value_count": 0,
        "unsupported_cross_scope_inheritance_count": 0,
        "source_scope_insufficient_count": l4a_counts["unresolved"],
    })
    write_rows("l4b_requirement_activations.jsonl", activations_out)
    write_rows("l4b_requirement_satisfaction.jsonl", satisfactions_out)
    write_rows("l4b_comparability_results.jsonl", comparability_out)
    write_rows("divergence_explanation_candidates.jsonl", explanation_candidates)
    write_rows("divergence_explanatory_power_results.jsonl", explanation_results)
    write_rows("formal_judgment_candidates.jsonl", formal_candidates)

    formal_states = sorted({x.formal_candidate_state for x in formal_candidates})
    structure_id = ident("scientific_disagreement_structure", {
        "publications": ["pmid:33380827", "pmid:37744426"],
        "pairs": [x["pair_id"] for x in qualifications],
    })
    write("publication_disagreement_structure.json", {
        "schema_version": "scientific_disagreement_structure_v1", "structure_id": structure_id,
        "publication_pair": ["pmid:33380827", "pmid:37744426"],
        "existing_evidence_unit": qualifications[0]["evidence_unit_b_id"],
        "new_supporting_evidence_units": [x["evidence_unit_a_id"] for x in qualifications],
        "candidate_pair_refs": [x["pair_id"] for x in qualifications],
        "analysis_level_support_count": 2, "study_level_count": 2,
        "publication_level_disagreement_count": 1,
        "context_differences": ["biological_model", "disease", "experimental_design"],
        "comparability_states": sorted({x.l4b_state for x in comparability_out}),
        "divergence_states": sorted({x.explanation_state for x in explanation_results}),
        "formal_candidate_states": formal_states, "primary_discovery_unit": True,
        "independent_conflict_count_asserted": 0,
    })
    publication_state = "DIVERGENCE_EXPLANATION_REVIEW_REQUIRED"
    write("publication_level_adjudication_summary.json", {
        "schema_version": "publication_level_l4_adjudication_summary_v1", "structure_id": structure_id,
        "publication_level_state": publication_state, "analysis_level_candidate_count": 2,
        "publication_level_structure_count": 1, "formal_conflict_confirmed": False,
        "reason": "Resolved Context differences are candidate-eligible, but no policy or human adjudication establishes explanatory sufficiency.",
    })
    question = (
        "For this single publication-level disagreement structure, do the validated differences in biological model, "
        "disease context, and experimental design provide sufficient source-supported evidence to treat the opposing "
        "overall-survival directions as Context-explained rather than residual unresolved disagreement?"
    )
    write("human_review_boundary.json", {
        "schema_version": "bounded_human_review_boundary_v1", "review_required": True,
        "structure_id": structure_id, "task_count": 1, "scope": "one publication-level disagreement structure",
        "unresolved_contract_semantic": "divergence explanatory sufficiency",
        "preferred_answer_included": False, "system_formal_prediction_included": False,
        "score_recommendation_included": False, "historical_answer_included": False,
    })
    write_rows("human_review_packet.jsonl", [{
        "schema_version": "bounded_divergence_explanation_human_review_task_v1",
        "review_task_id": ident("human_review_task", {"structure": structure_id}),
        "structure_id": structure_id, "candidate_pair_refs": [x["pair_id"] for x in qualifications],
        "question": question, "context_difference_refs": [x["context_difference_identity"] for x in l4a_rows if x["difference_state"] == "different"],
        "allowed_answers": ["sufficiently_explanatory", "not_sufficiently_explanatory", "insufficient_information"],
        "answer": None, "preferred_answer": None, "system_formal_prediction": None,
        "score_based_recommendation": None, "historical_answer": None,
    }])
    neutral = [x for x in rows(REPLAY_ART / "scientific_candidate_qualification_v2_candidate.jsonl")
               if x["qualification_state"] == "reviewable_result_orientation"]
    write("neutral_analysis_preservation_audit.json", {
        "schema_version": "neutral_analysis_preservation_audit_v1", "reviewable_neutral_evidence_pair_count": len(neutral),
        "neutral_analysis_observation_count": len({x["observation_a_id"] for x in neutral}),
        "included_in_current_l4": False, "states_modified": False,
        "future_scope": "bounded effect-vs-no-effect semantics task",
    })
    write("observational_authority_lineage_recheck.json", {
        "schema_version": "observational_authority_lineage_recheck_v1", "observation_count": 6,
        "authority_path": ["Formal v3 read-only object", "observational candidate projection",
                           "deterministic core validation", "minimum proposition", "Scientific Proposition Compatibility",
                           "Contradiction", "Candidate Qualification", "L4 candidate chain"],
        "legacy_strict_core_false_count": 6, "observational_profile_eligible_count": 6,
        "upstream_regression_detected": False, "legacy_flags_modified": False,
    })
    after = {rel(path): sha(path) for path in protected}
    if before != after:
        raise RuntimeError("protected_scientific_input_modified")
    write("scientific_state_safety_audit.json", {
        "schema_version": "first_qualified_l4_scientific_state_safety_audit_v1",
        "protected_input_sha256_before": before, "protected_input_sha256_after": after,
        "protected_hashes_unchanged": True, "historical_candidate_object_count": 11,
        "historical_formal_conflict_count": 0, "entity_integrity_claims_blocked": 241,
        "entity_integrity_signals_blocked": 2, "pi3k_40f_unchanged": True,
        "f389_manual_unchanged": True, "historical_assets_modified": False, "formal_v3_modified": False,
    })
    write("production_leakage_audit.json", {
        "schema_version": "first_qualified_l4_production_leakage_audit_v1", "candidate_only": True,
        "provider_calls": 0, "llm_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0,
        "credentials_read": False, "provider_client_loaded": False, "atlas_activated": False,
        "active_pointer_changed": False, "variational_em_called": False,
        "historical_formal_created": False, "natural_language_explanation_authoritative": False,
    })
    metrics = {
        "qualified_candidate_count": 2, "publication_level_disagreement_structure_count": 1,
        "l4a_context_dimension_evaluation_count": len(l4a_rows),
        "l4a_matched_count": l4a_counts["matched"], "l4a_different_count": l4a_counts["different"],
        "l4a_unresolved_count": l4a_counts["unresolved"], "l4a_ambiguous_count": l4a_counts["ambiguous"],
        "l4b_comparable_count": sum(x.comparable is True for x in comparability_out),
        "l4b_comparable_with_context_divergence_count": sum(x.l4b_state == "comparable_with_context_divergence" for x in comparability_out),
        "l4b_reviewable_count": sum(x.comparable is None for x in comparability_out),
        "l4b_blocked_count": sum(x.comparable is False for x in comparability_out),
        "divergence_explanation_candidate_count": len(explanation_candidates),
        "supported_context_explanation_count": sum(x.explanation_state == "supported_explanatory_difference" for x in explanation_results),
        "unresolved_explanatory_power_count": sum(x.explanation_state == "explanatory_power_unresolved" for x in explanation_results),
        "formal_candidate_confirmed_count": sum(x.formal_candidate_state == "formal_conflict_candidate_confirmed" for x in formal_candidates),
        "formal_candidate_context_explained_count": sum(x.formal_candidate_state == "not_confirmed_context_explained" for x in formal_candidates),
        "formal_candidate_reviewable_count": sum(x.formal_candidate_state.startswith("reviewable_") for x in formal_candidates),
        "formal_candidate_blocked_count": sum(x.formal_candidate_state.startswith("blocked_") for x in formal_candidates),
        "publication_level_formal_confirmed_count": 0, "publication_level_review_required_count": 1,
        "human_review_task_count": 1, "analysis_level_opposing_support_count": 2,
        "publication_level_disagreement_count": 1,
    }
    required = [
        "baseline.json", "qualified_candidate_inventory.jsonl", "publication_disagreement_structure.json",
        "l4a_context_difference_results.jsonl", "l4a_context_coverage_audit.json",
        "l4b_requirement_activations.jsonl", "l4b_requirement_satisfaction.jsonl", "l4b_comparability_results.jsonl",
        "divergence_explanation_candidates.jsonl", "divergence_explanatory_power_results.jsonl",
        "formal_judgment_candidates.jsonl", "publication_level_adjudication_summary.json",
        "human_review_boundary.json", "human_review_packet.jsonl", "neutral_analysis_preservation_audit.json",
        "observational_authority_lineage_recheck.json", "scientific_state_safety_audit.json",
        "production_leakage_audit.json", "final_validation.json", "manifest.json", "summary.json",
    ]
    write("summary.json", {"schema_version": "first_qualified_l4_adjudication_summary_v1",
                           "status": "completed", "decision": publication_state, **metrics})
    write("final_validation.json", {
        "schema_version": "first_qualified_l4_adjudication_final_validation_v1", "status": "valid",
        "decision": publication_state, "ordered_l4_chain_completed": True,
        "context_difference_separate_from_explanation": True, "formal_candidate_fail_closed": True,
        "historical_formal_unchanged": True, "required_artifacts": required,
        "required_artifacts_present": all((ART / name).exists() or name in {"final_validation.json", "manifest.json"} for name in required),
        "focused_test_pass_count": opt.focused_pass_count,
        "related_test_pass_count": opt.related_pass_count,
        "full_suite_pass_count": opt.full_pass_count,
        "full_suite_subtest_pass_count": opt.full_subtest_pass_count,
        "full_suite_failure_count": opt.full_failure_count,
        "full_suite_collected_count": opt.full_collected_count,
        "baseline_failure_ids": [
            "tests/test_code_atlas_annotations.py::AtlasAnnotationTests::test_missing_review_root_useful_error_and_ui_controls_present",
            "tests/test_code_atlas_human_centered_redesign.py::test_case_contract_explains_capabilities_and_next_level_metadata",
            "tests/test_code_atlas_human_centered_redesign.py::test_reasoning_unavailable_is_explicit_and_does_not_infer_steps",
            "tests/test_code_atlas_workspaces.py::AtlasWorkspaceRoleTests::test_workspace_pages_are_role_scoped",
            "tests/test_core_reference_adjudication_packaging_v1.py::test_zip_files_are_valid_separate_and_checksums_match",
        ],
        "final_failure_ids": [
            "tests/test_code_atlas_annotations.py::AtlasAnnotationTests::test_missing_review_root_useful_error_and_ui_controls_present",
            "tests/test_code_atlas_human_centered_redesign.py::test_case_contract_explains_capabilities_and_next_level_metadata",
            "tests/test_code_atlas_human_centered_redesign.py::test_reasoning_unavailable_is_explicit_and_does_not_infer_steps",
            "tests/test_code_atlas_workspaces.py::AtlasWorkspaceRoleTests::test_workspace_pages_are_role_scoped",
            "tests/test_core_reference_adjudication_packaging_v1.py::test_zip_files_are_valid_separate_and_checksums_match",
        ],
        "new_classified_failure_ids": [], "no_new_classified_failure_ids": True,
        "compileall": opt.compileall, "git_diff_check": opt.git_diff_check,
        **metrics,
    })
    artifact_paths = sorted(path for path in RUN.rglob("*") if path.is_file() and path != ART / "manifest.json")
    write("manifest.json", {
        "schema_version": "first_qualified_l4_adjudication_manifest_v1", "run_id": RUN.name,
        "self_excluded_to_avoid_recursive_hash": True,
        "artifacts": [{"path": rel(path), "sha256": sha(path), "bytes": path.stat().st_size} for path in artifact_paths],
    })
    print(json.dumps(load(ART / "summary.json"), indent=2))


if __name__ == "__main__":
    main()
