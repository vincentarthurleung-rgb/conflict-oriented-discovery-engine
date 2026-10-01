#!/usr/bin/env python3
"""Freeze architecture and audit fresh-heldout eligibility without retrieval."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_15_harmonized_results_interpretation_offline"
TARGET = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_16_architecture_freeze_fresh_heldout_v3_preregistration_offline"
STRESS = ROOT / "runs/20260906_search_plan_v2_multicase_stress_test_offline/case_inventory.jsonl"
V1 = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline/heldout_scientific_targets.jsonl"
V2_EARLIER = ROOT / "runs/20260915_search_plan_v23_beta_heldout_v2_case_freeze_offline/heldout_v2_scientific_targets.jsonl"
V2 = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_case_freeze_offline/primary_heldout_v2_scientific_targets.jsonl"
EXPECTED_PREVIOUS_ROOT = "6141129a66a96baa5a70564495de9c2b571c4ea9e123906d72f3322a74e3b9aa"
ARCHITECTURE_ROOTS = {
    "SearchConstraintAllocationV1": "runs/20260925_search_plan_v24_dev_alpha3_9_search_constraint_allocation_offline/search_plan_v24_dev_alpha3_9_sha256",
    "BoundedLexicalRealizationV2": "runs/20260925_search_plan_v24_dev_alpha3_11_bounded_lexical_realization_v2_offline/search_plan_v24_dev_alpha3_11_sha256",
    "LexicalV2ExecutionPolicy": "runs/20260925_search_plan_v24_dev_alpha3_12_bounded_lexical_realization_v2_retrieval_preregistration_offline/search_plan_v24_dev_alpha3_12_sha256",
    "HarmonizedScientificReviewRubric": "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_neutral_review_preregistration_offline/search_plan_v24_dev_alpha3_13_sha256",
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[Any]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(name: str, value: Any) -> None:
    path = TARGET / name
    body = canonical(value) + b"\n"
    if path.exists():
        require(path.read_bytes() == body, f"refusing different existing artifact: {name}")
        return
    path.write_bytes(body)


def write_lines(name: str, values: list[Any]) -> None:
    path = TARGET / name
    require(not path.exists(), f"refusing overwrite: {name}")
    path.write_bytes(b"".join(canonical(value) + b"\n" for value in values))


def root_from_flat_directory(directory: Path, root_file: str) -> str:
    pairs = [[path.name, sha(path)] for path in sorted(directory.iterdir())
             if path.is_file() and path.name != root_file]
    actual = digest(pairs)
    require(actual == (directory / root_file).read_text(encoding="utf-8").strip(), f"root drift: {directory}")
    return actual


def source_row(candidate_id: str, source: Path, classification: str, reason: str,
               source_kind: str, duplicate_of: str | None = None) -> dict[str, Any]:
    return {"candidate_id": candidate_id, "source_path": str(source.relative_to(ROOT)),
            "source_file_sha256": sha(source), "source_kind": source_kind,
            "eligibility_state": classification, "reason": reason,
            "duplicate_of": duplicate_of, "eligible_for_sampling": False,
            "paper_title_or_pmid_inspected": False}


def architecture_files() -> list[Path]:
    search_code = sorted((ROOT / "src/code_engine/search").glob("*.py"))
    allocation = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_9_search_constraint_allocation_offline"
    lexical = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_11_bounded_lexical_realization_v2_offline"
    execution = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_12_bounded_lexical_realization_v2_retrieval_preregistration_offline"
    review = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_neutral_review_preregistration_offline"
    named = [
        allocation / name for name in (
            "search_constraint_allocation_v1_contract.json", "relational_query_family_v3_contract.json",
            "query_family_variant_policy.json", "query_family_budget_policy.json",
            "generic_role_allocation_matrix.json", "downstream_validator_ownership_v2.json")
    ] + [lexical / name for name in (
        "bounded_lexical_realization_v2_contract.json", "lexical_authority_class_contract.json",
        "deterministic_morphology_contract.json", "relation_lexicon_v2.json",
        "endpoint_lexicon_v2.json", "lexical_budget_policy.json")
    ] + [execution / name for name in (
        "bounded_lexical_realization_v2_development_execution_manifest.json",
        "query_execution_policy.json", "tail_policy.json", "metadata_policy.json",
        "candidate_validation_policy.json", "oa_eligibility_policy.json",
        "selection_fulltext_policy.json", "technical_retry_policy.json",
        "technical_continuation_policy.json", "case_union_policy.json")
    ] + [review / name for name in (
        "neutral_review_prompt_template.txt", "neutral_review_output_schema.json",
        "neutral_review_metrics_plan.json", "neutral_review_failure_policy.json",
        "neutral_review_provider_config.json")]
    return sorted(set(search_code + named))


def main() -> None:
    require(not (TARGET / "search_plan_v24_dev_alpha3_16_sha256").exists(),
            "alpha3.16 root exists; never regenerate a frozen run")
    root = root_from_flat_directory(PREVIOUS, "search_plan_v24_dev_alpha3_15_sha256")
    require(root == EXPECTED_PREVIOUS_ROOT, "authoritative alpha3.15 root mismatch")
    require(load(PREVIOUS / "summary.json")["next_stage_recommendation"] ==
            "FREEZE_ARCHITECTURE_AND_TEST_FRESH_HELDOUT", "development conclusion drift")
    code_and_policy = architecture_files()
    require(code_and_policy and all(path.is_file() and not path.is_symlink() for path in code_and_policy),
            "architecture component missing or symlinked")
    architecture_components = [[str(path.relative_to(ROOT)), sha(path)] for path in code_and_policy]
    architecture_roots = {name: (ROOT / relative).read_text(encoding="utf-8").strip()
                          for name, relative in ARCHITECTURE_ROOTS.items()}
    architecture_freeze = digest({"component_hashes": architecture_components,
                                  "frozen_architecture_roots": architecture_roots,
                                  "alpha3_15_interpretation_root": root})

    stress = rows(STRESS)
    v1 = rows(V1)
    v2_earlier = rows(V2_EARLIER)
    v2 = rows(V2)
    require(len(stress) == 32 and len(v1) == len(v2_earlier) == len(v2) == 8,
            "prior proposition source count drift")
    used_seed_keys = {(row["source_case_id"], row["source_triple"]["triple_id"]) for row in stress}
    generated = sorted((ROOT / "configs/generated_cases").glob("*/semantic_intake.json"))
    profiles = sorted((ROOT / "configs/case_profiles").glob("*.case_profile.json"))
    benchmarks = ROOT / "tests/fixtures/validation_benchmark/benchmark_cases.jsonl"
    source_derived = sorted(path for path in (ROOT / "runs").glob("*/artifacts/*")
                            if path.is_file() and path.suffix in (".json", ".jsonl") and
                            ("proposition" in path.name or "claim" in path.name))
    search_plans = sorted((ROOT / "configs/search_plans").glob("*.json"))
    inventory: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []

    def add_family(name: str, paths: list[Path], count: int, state: str, note: str) -> None:
        inventory.append({"source_family": name, "source_file_count": len(paths),
                          "enumerated_entry_count": count,
                          "file_sha256": [[str(path.relative_to(ROOT)), sha(path)] for path in paths],
                          "default_eligibility_state": state, "reason": note,
                          "paper_titles_or_pmids_read": False})

    add_family("v2_multicase_planning_stress_test", [STRESS], len(stress), "SEEN_CALIBRATION",
               "Every entry was used in the prior 32-case planning stress test.")
    for item in stress:
        audit.append(source_row(item["case_id"], STRESS, "SEEN_CALIBRATION",
                                "Used in Search Plan v2 multicase stress test.", "scientific_proposition"))
    add_family("heldout_v1_frozen_targets", [V1], len(v1), "SEEN_DEVELOPMENT",
               "Prior held-out evaluation has already used these targets.")
    for item in v1:
        audit.append(source_row(item["case_id"], V1, "SEEN_DEVELOPMENT",
                                "Previously evaluated held-out v1 target.", "scientific_proposition"))
    add_family("earlier_heldout_v2_frozen_targets", [V2_EARLIER], len(v2_earlier), "SEEN_DEVELOPMENT",
               "Earlier held-out v2 cases 001-008 were previously used in development.")
    for item in v2_earlier:
        audit.append(source_row(item["case_id"], V2_EARLIER, "SEEN_DEVELOPMENT",
                                "Earlier held-out v2 target; not fresh for v3.", "scientific_proposition"))
    add_family("heldout_v2_frozen_targets", [V2], len(v2), "SEEN_DEVELOPMENT",
               "All eight targets are permanently seen development cases 101-108.")
    for item in v2:
        audit.append(source_row(item["case_id"], V2, "SEEN_DEVELOPMENT",
                                "Previously used held-out v2 target; now seen development.", "scientific_proposition"))

    seed_count = 0
    seed_seen_count = 0
    for path in generated:
        case = path.parent.name
        seeds = load(path).get("seed_triples", [])
        for seed in seeds:
            seed_count += 1
            key = (case, seed["triple_id"])
            seen = key in used_seed_keys
            seed_seen_count += seen
            audit.append(source_row(f"generated_seed:{case}:{seed['triple_id']}", path,
                                    "SEEN_CALIBRATION" if seen else "PROVENANCE_UNRESOLVED",
                                    "Exact seed used in 32-case stress test." if seen else
                                    "No complete cross-workflow certificate proves this seed was never used or manually inspected; its source case already has frozen search plans and prior runs.",
                                    "generated_seed_triple",
                                    duplicate_of=f"stress:{case}:{seed['triple_id']}" if seen else None))
    require(len(generated) == 11 and seed_count == 52 and seed_seen_count == 30,
            "generated seed provenance drift")
    add_family("generated_case_semantic_seed_triples", generated, seed_count, "PROVENANCE_UNRESOLVED",
               "30 exact seeds used in stress test; 22 lack a complete untouched-use certificate.")

    add_family("legacy_case_profiles", profiles, len(profiles), "SEEN_DEBUGGING",
               "Existing case profiles are tied to prior stress-test or case-specific testing workflows.")
    for path in profiles:
        case = path.name.removesuffix(".case_profile.json")
        state = "SEEN_CALIBRATION" if case == "metformin_ampk_cancer" else "SEEN_DEBUGGING"
        audit.append(source_row(f"profile:{case}", path, state,
                                "Prior stress test or test/search-plan workflow; not an untouched proposition.",
                                "legacy_case_profile"))
    add_family("validation_benchmark_fixture", [benchmarks], len(rows(benchmarks)), "SEEN_DEBUGGING",
               "Test fixture records are not certified scientific proposition targets.")
    for item in rows(benchmarks):
        audit.append(source_row(f"benchmark:{item['case_id']}", benchmarks, "SEEN_DEBUGGING",
                                "Validation benchmark fixture; not untouched target authority.",
                                "test_fixture"))
    add_family("source_derived_proposition_or_claim_artifacts", source_derived, len(source_derived),
               "PROVENANCE_UNRESOLVED",
               "Source-derived or audit artifacts lack a paper-blind, untouched proposition eligibility certificate; contents not inspected.")
    for path in source_derived:
        audit.append(source_row(f"source_artifact:{path.relative_to(ROOT)}", path,
                                "PROVENANCE_UNRESOLVED",
                                "Potentially paper-derived and no untouched provenance certificate; contents not inspected.",
                                "source_derived_file_not_certified_candidate"))
    add_family("existing_search_plan_configs", search_plans, len(search_plans), "SEEN_DEBUGGING",
               "Already compiled or reviewed search plans are not fresh proposition sources.")
    for path in search_plans:
        audit.append(source_row(f"search_plan_config:{path.name}", path, "SEEN_DEBUGGING",
                                "Existing search-plan artifact; prior query/debug exposure.",
                                "compiled_search_plan_not_certified_candidate"))
    require(not any(row["eligibility_state"] == "ELIGIBLE_UNTOUCHED" for row in audit),
            "unexpected eligible row requires independent audit")
    require(len({row["candidate_id"] for row in audit}) == len(audit), "inventory candidate identifier collision")

    TARGET.mkdir(exist_ok=True)
    write("alpha3_15_root_verification.json", {
        "status": "PASS", "expected_sha256": EXPECTED_PREVIOUS_ROOT,
        "actual_sha256": root, "development_conclusion": "FREEZE_ARCHITECTURE_AND_TEST_FRESH_HELDOUT"})
    write("architecture_freeze_manifest.json", {
        "status": "FROZEN_UNCHANGED", "components": architecture_components,
        "frozen_architecture_roots": architecture_roots,
        "includes": ["Planner V3", "RelationCore", "SearchConstraintAllocationV1",
                     "RelationalQueryFamilyV3", "BoundedLexicalRealizationV2", "lexical/morphology/endpoint/relation rules",
                     "query budgets and PubMed serialization", "P0 v1.1", "P1 v1.1", "P2 v1", "Policy A",
                     "tail/metadata/OA/ranking/selection/fulltext policy", "harmonized scientific review rubric"],
        "architecture_freeze_sha256": architecture_freeze,
        "no_component_modified": True})
    (TARGET / "architecture_freeze_sha256").write_text(architecture_freeze + "\n", encoding="utf-8")
    seen_cases = [f"heldout_v2_{i}" for i in range(101, 109)]
    require([row["case_id"] for row in v2] == seen_cases, "seen case identity drift")
    write("seen_development_case_registry.json", {
        "cases": [{"case_id": case, "status": "SEEN_DEVELOPMENT_CASES"} for case in seen_cases],
        "never_again_describe_as_heldout": True,
        "source_targets_sha256": sha(V2)})
    write("proposition_source_inventory.json", {
        "source_families": inventory, "inventory_row_count": len(audit),
        "generated_seed_count": seed_count, "generated_seeds_used_in_stress_test": seed_seen_count,
        "generated_seeds_without_untouched_certificate": seed_count - seed_seen_count,
        "paper_titles_or_pmids_read": False})
    write_lines("untouched_proposition_eligibility_audit.jsonl", audit)
    frame: list[Any] = []
    write_lines("fresh_heldout_sampling_frame.jsonl", frame)
    frame_hash = sha(TARGET / "fresh_heldout_sampling_frame.jsonl")
    (TARGET / "fresh_heldout_sampling_frame_sha256").write_text(frame_hash + "\n", encoding="utf-8")
    write("stratification_contract.json", {
        "status": "PREREGISTERED_NOT_APPLIED_EMPTY_FRAME",
        "architecture_independent_strata": ["difficulty LOW/MEDIUM/HIGH", "oncology/non-oncology",
                                             "direct signaling/therapy response", "activation/inhibition",
                                             "endpoint family", "cellular/tissue-compatible setting",
                                             "simple/nested conditioning", "broad biological domain"],
        "target_case_count_if_eligible_pool_suffices": "12-16",
        "do_not_force_case_count": True,
        "observed_alpha3_15_failure_frequencies_used": False})
    write("difficulty_definition.json", {
        "status": "FROZEN_GENERIC_NOT_APPLIED",
        "LOW": "One direct actor-action-endpoint proposition with one explicit biological unit and no nested conditioning.",
        "MEDIUM": "One scientifically intrinsic qualifier or therapy context, or a composite endpoint, while proposition remains directly falsifiable.",
        "HIGH": "Nested conditioning, multiple intrinsic context dimensions, or a therapy-response proposition requiring explicit role binding.",
        "defined_without_retrieval_hit_counts_or_review_labels": True,
        "target_balance_if_available": {"LOW": "approximately one third", "MEDIUM": "approximately one third", "HIGH": "approximately one third"}})
    seed_preimage = EXPECTED_PREVIOUS_ROOT + "|fresh-heldout-v3-selection-v1"
    write("sampling_seed_contract.json", {
        "seed_source": "immutable alpha3.15 interpretation root",
        "seed_derivation": "sha256(ASCII alpha3.15 root + '|fresh-heldout-v3-selection-v1')",
        "derived_seed_sha256": hashlib.sha256(seed_preimage.encode("ascii")).hexdigest(),
        "selection_executed": False,
        "reason_not_executed": "No certified eligible sampling frame.",
        "future_new_pool_requires_its_own_preselection_freeze": True})
    write("fresh_heldout_selection_audit.json", {
        "status": "NOT_PERFORMED_INSUFFICIENT_UNTOUCHED_POOL",
        "eligible_sampling_frame_frozen": True, "sampling_frame_sha256": frame_hash,
        "eligible_untouched_proposition_count": 0, "selected_indices": [],
        "selected_case_count": 0, "no_convenience_substitution": True,
        "selection_output_sha256": None})
    write_lines("fresh_heldout_v3_targets.jsonl", [])
    write("fresh_heldout_v3_target_manifest.json", {
        "status": "NOT_FROZEN_NO_ELIGIBLE_TARGETS",
        "selected_case_count": 0, "target_manifest_frozen": False,
        "scientific_target_entries": [],
        "not_a_valid_fresh_heldout_target_freeze": True})
    (TARGET / "fresh_heldout_v3_target_manifest_sha256").write_text("null\n", encoding="utf-8")
    write("known_paper_blindness_policy.json", {
        "known_pmid_checks": 0, "known_direct_paper_checks": 0,
        "paper_title_inspection": 0, "pubmed_hit_count_checks": 0,
        "no_case_removal_for_missing_known_answer": True,
        "future_selection_must_preserve_blindness": True})
    write("target_freeze_barrier.json", {
        "barrier_state": "NOT_CROSSED_NO_TARGET_MANIFEST",
        "sampling_frame_frozen": True, "target_manifest_frozen": False,
        "query_compilation_permitted": False,
        "target_modifications_after_freeze": 0})
    write("future_query_compilation_policy.json", {
        "status": "PREREGISTERED_NOT_EXECUTED",
        "precondition": "A nonempty, quality-gated target manifest must be frozen before compilation.",
        "use_architecture_sha256": architecture_freeze,
        "architecture_mutation_after_compile_failure": False,
        "deterministic_compile_failure_is_evaluation_outcome": True,
        "planner_or_provider_calls_require_separate_authorization": True,
        "queries_compiled_now": 0})
    write("future_retrieval_metrics_plan.json", {
        "layer": "LAYER_1_QUERY_AND_CANDIDATE_GENERATION",
        "metrics": ["queries_per_case", "nonzero_query_count", "cases_with_any_hit",
                    "unique_pmid_universe", "metadata_universe", "CORE_RELATION_success",
                    "variant_attribution"],
        "zero_case_state": "NO_CANDIDATES_FROM_RETRIEVAL",
        "not_a_scientific_negative": True})
    write("future_acquisition_metrics_plan.json", {
        "layer": "LAYER_2_DETERMINISTIC_VALIDATION_AND_ACQUISITION",
        "metrics": ["P0_states", "P1_states", "P2_states", "Policy_A_actions",
                    "Tier_A_B_counts", "PMCID_eligibility", "selected_units",
                    "successfully_acquired_fulltexts"],
        "no_review_units_state": "NO_REVIEW_UNITS_FROM_RETRIEVAL",
        "not_a_scientific_negative": True})
    write("future_scientific_review_metrics_plan.json", {
        "layer": "LAYER_3_ARM_BLINDED_SCIENTIFIC_REVIEW",
        "metrics": ["Pass_A_acquisition_state", "Pass_B_relevance_state",
                    "contaminant_class", "DIRECT_count", "review_denominator", "case_coverage"],
        "not_precision_or_recall": True,
        "do_not_define_success_as_beating_seen_development_results": True,
        "review_rubric_architecture_frozen_sha256": architecture_roots["HarmonizedScientificReviewRubric"]})
    write("development_label_nonuse_audit.json", {
        "individual_alpha3_15_failure_labels_read_for_selection": False,
        "individual_retrieved_pmids_read_for_selection": False,
        "individual_historical_labels_read_for_selection": False,
        "alpha3_15_root_and_next_stage_enum_only": True,
        "development_labels_used_for_case_selection": False,
        "selected_case_count": 0})
    write("overfitting_control_audit.json", {
        "cases_101_108_permanently_seen": True,
        "current_architecture_frozen": True,
        "no_case_specific_rules": True,
        "no_query_or_lexical_tuning": True,
        "untouched_pool_required_before_selection": True,
        "current_pool_certified_eligible_count": 0})
    write("scientific_state_safety_audit.json", {
        "historical_assets_modified": False,
        "query_modifications": 0, "lexical_changes": 0, "validator_changes": 0,
        "selection_policy_changes": 0, "target_modifications_after_freeze": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0,
        "known_pmid_checks": 0, "pubmed_hit_count_checks": 0,
        "retrieval_output_used_for_selection": False,
        "scientific_adjudication_calls": 0})
    write("validation.json", {
        "status": "FAILED_CLOSED_INSUFFICIENT_UNTOUCHED_POOL",
        "current_architecture_frozen": True, "cases_101_108_marked_seen": True,
        "development_labels_used_for_case_selection": False,
        "eligible_sampling_frame_frozen": True,
        "eligible_untouched_proposition_count": 0,
        "target_manifest_frozen": False,
        "no_target_or_query_fabrication": True,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0})
    write("summary.json", {
        "status": "failed", "reason": "No proposition in the repository can currently be certified ELIGIBLE_UNTOUCHED under the required provenance rules.",
        "architecture_freeze_sha256": architecture_freeze,
        "seen_development_case_count": 8,
        "eligible_untouched_proposition_count": 0,
        "fresh_heldout_v3_case_count": 0,
        "target_manifest_frozen": False,
        "next_stage_recommendation": "CONSTRUCT_NEW_PROPOSITION_POOL_UNDER_BLINDED_PROTOCOL",
        "historical_assets_modified": False})
    paths = [path for path in sorted(TARGET.iterdir()) if path.is_file() and
             path.name != "search_plan_v24_dev_alpha3_16_sha256"]
    pairs = [[path.name, sha(path)] for path in paths]
    run_root = digest(pairs)
    (TARGET / "search_plan_v24_dev_alpha3_16_sha256").write_text(run_root + "\n", encoding="utf-8")
    require(all(sha(TARGET / name) == checksum for name, checksum in pairs), "run component drift")
    print(json.dumps({"status": "failed_insufficient_untouched_pool",
                      "architecture_freeze_sha256": architecture_freeze,
                      "eligible_untouched_proposition_count": 0,
                      "root": run_root}, sort_keys=True))


if __name__ == "__main__":
    main()
