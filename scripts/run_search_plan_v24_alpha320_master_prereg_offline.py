#!/usr/bin/env python3
"""Freeze the seen-data alpha3.20 development master, without model execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
OUT = RUNS / "20261002_search_plan_v24_dev_alpha3_20_post_alpha3_19_development_master_preregistration_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_20_master_prereg_sha256"
NEXT = "PREREGISTER_ALPHA3_20A_EVIDENCE_REFERENCE_V4_OFFLINE_VALIDATION"

MASTER = RUNS / "20261001_search_plan_v24_dev_alpha3_19_fresh_heldout_attempt2_master_preregistration_offline"
E = RUNS / "20261002_search_plan_v24_dev_alpha3_19e_construction_document_anchor_builder_freeze_offline"
F = RUNS / "20261002_search_plan_v24_dev_alpha3_19f_builder_v3_execution"
F1 = RUNS / "20261002_search_plan_v24_dev_alpha3_19f1_zero_quality_input_gate_audit_offline"
G = RUNS / "20261002_search_plan_v24_dev_alpha3_19g_primary_attempt_closure_offline"
HISTORICAL_ROOTS = [
    (MASTER, "search_plan_v24_dev_alpha3_19_master_prereg_sha256",
     "1cf1d29d67474996a6ee87b518af0f09456e3572a3969b5a5f1b6021009ed73b"),
    (E, "search_plan_v24_dev_alpha3_19e_sha256",
     "afcc320cc2e0e352d77fdc4370b87f146b63e7f089663b60dac80c570c87bb87"),
    (F, "search_plan_v24_dev_alpha3_19f_sha256",
     "e1aad29348c72d323221e799b0c9d897aeae336df753f2e761aa98ea4a993549"),
    (F1, "search_plan_v24_dev_alpha3_19f1_sha256",
     "090dd53981166a3a64f46af34376a72fe926d6844dfe85f0d8bd52a7263cfeb3"),
    (G, "search_plan_v24_dev_alpha3_19g_sha256",
     "de6567e7dba0b4f42f936f9e8a5a15f01a09346526bb64f8359b394e769e5da5"),
]
REQUEST_MANIFEST_SHA = "1a3988750d91d1cf2288445e5536c67745612a01f5409d4037a93f7eed2a77d3"
CONSTRUCTION_DOCUMENT_MANIFEST_SHA = "324da514cbe3308932b3722afc8a4c3c203c20dccfd093f0e25d75801483268b"
QUALITY_ENVELOPE_SHA = "25ad0b448a6d7fd9f6598841824c19cab33ba4b40eb92e2c2260d871d06e4a1d"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line]


def reference(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes())}


def root_hash(directory: Path, marker: str) -> str:
    require(not any(path.is_symlink() for path in directory.rglob("*")),
            "SYMLINK_IN_FROZEN_ROOT:" + directory.name)
    files = sorted(path for path in directory.rglob("*")
                   if path.is_file() and path.name != marker)
    return sha(canonical([[str(path.relative_to(directory)), sha(path.read_bytes())]
                          for path in files]))


def verify_historical_roots() -> list[dict]:
    verified = []
    for directory, marker, expected in HISTORICAL_ROOTS:
        require((directory / marker).read_text().strip() == expected
                and root_hash(directory, marker) == expected,
                "HISTORICAL_ROOT_MISMATCH:" + directory.name)
        verified.append({"path": str(directory.relative_to(ROOT)),
                         "root_marker": marker, "sha256": expected, "verified": True})
    return verified


def put(name: str, value: object) -> str:
    raw = canonical(value) + b"\n"
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
    return sha(raw)


def put_rows(name: str, values: list[dict]) -> str:
    raw = b"".join(canonical(value) + b"\n" for value in values)
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
    return sha(raw)


def hash_marker(name: str, value: str) -> None:
    with (OUT / name).open("xb") as handle:
        handle.write((value + "\n").encode("ascii"))


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA320_MASTER_ALREADY_EXISTS_NO_REWRITE")
    historical_roots = verify_historical_roots()
    closure = read_json(G / "validation.json")
    audit = read_json(F1 / "validation.json")
    e_validation = read_json(E / "validation.json")
    f_validation = read_json(F / "validation.json")
    require(closure["alpha3_19_primary_attempt_closed"] is True
            and closure["alpha3_19_terminal_state"] ==
            "TERMINATED_WITH_ZERO_QUALITY_INPUT_UNDER_CONSISTENT_FROZEN_GATES"
            and closure["quality_executed"] is False
            and closure["eligible_proposition_pool_derived"] is False
            and closure["fresh_heldout_selected"] is False
            and closure["historical_alpha3_19_builder_inference_events"] == 14
            and closure["historical_alpha3_19_quality_inference_events"] == 0
            and audit["grounding_primary_classification"] ==
            "GROUNDING_CONTRACT_CONSISTENT_MODEL_NONCONFORMANCE"
            and audit["leakage_primary_classification"] ==
            "LEAKAGE_CONTRACT_CONSISTENT_ZERO_SURVIVORS"
            and audit["reproduced_grounding_failure_count"] == 29
            and audit["reproduced_grounding_pass_count"] == 6
            and audit["reproduced_leakage_failure_count"] == 6
            and audit["failed_by_8_token_rule_only"] == 4
            and audit["failed_by_jaccard_only"] == 0
            and audit["failed_by_both"] == 2
            and audit["passed_both"] == 0
            and f_validation["builder_raw_candidate_count"] == 35,
            "ALPHA319_CLOSURE_OR_F1_AUDIT_MISMATCH")
    request_path = E / "alpha3_19_builder_v3_request_manifest.jsonl"
    document_manifest_path = E / "construction_document_manifest.jsonl"
    require(sha(request_path.read_bytes()) == REQUEST_MANIFEST_SHA
            and sha(document_manifest_path.read_bytes()) ==
            CONSTRUCTION_DOCUMENT_MANIFEST_SHA
            and (MASTER / "quality_response_envelope_v3_sha256").read_text().strip() ==
            QUALITY_ENVELOPE_SHA
            and e_validation["construction_documents_valid"] == 14
            and e_validation["builder_request_count"] == 14,
            "FROZEN_SEEN_CORPUS_INPUT_MISMATCH")
    requests = rows(request_path)
    documents = {row["source_token"]: row for row in rows(document_manifest_path)}
    visibility = read_json(F1 / "builder_request_body_visibility_audit.json")
    require(len(requests) == 14 and len({row["source_token"] for row in requests}) == 14
            and len({row["request_sha256"] for row in requests}) == 14
            and visibility["requests_with_required_body_surface_available"] == 14
            and visibility["requests_without_required_body_surface_available"] == 0
            and all(row["source_token"] in documents for row in requests),
            "SEEN_CORPUS_BODY_VISIBILITY_OR_IDENTITY_MISMATCH")
    corpus = [{"ordinal": row["ordinal"], "source_record_token": row["source_token"],
               "request_sha256": row["request_sha256"],
               "construction_document_sha256": documents[row["source_token"]]["document_sha256"]}
              for row in requests]

    registry_paths = {
        "alpha3_18_sources": MASTER / "alpha3_18_seen_source_registry.jsonl",
        "alpha3_18_candidates": MASTER / "alpha3_18_seen_candidate_registry.jsonl",
        "alpha3_18_quality_groups": MASTER / "alpha3_18_seen_quality_group_registry.jsonl",
        "alpha3_19_sources": G / "alpha3_19_seen_source_registry.jsonl",
        "alpha3_19_candidates": G / "alpha3_19_seen_candidate_registry.jsonl",
    }
    registries = {name: rows(path) for name, path in registry_paths.items()}
    require(len(registries["alpha3_18_sources"]) == 1041
            and len(registries["alpha3_18_candidates"]) == 110
            and len(registries["alpha3_18_quality_groups"]) == 3
            and len(registries["alpha3_19_sources"]) == 1379
            and len(registries["alpha3_19_candidates"]) == 35,
            "SEEN_REGISTRY_CARDINALITY_MISMATCH")
    source_by_pmid: dict[str, set[str]] = {}
    for generation in ("alpha3_18", "alpha3_19"):
        for row in registries[generation + "_sources"]:
            source_by_pmid.setdefault(row["pmid"], set()).add(generation)
    candidate_by_id: dict[str, dict] = {}
    for generation in ("alpha3_18", "alpha3_19"):
        for row in registries[generation + "_candidates"]:
            candidate_id = row["candidate_id"]
            require(candidate_id not in candidate_by_id,
                    "CROSS_HISTORY_CANDIDATE_ID_COLLISION")
            candidate_by_id[candidate_id] = {
                "candidate_id": candidate_id,
                "candidate_payload_sha256": row["candidate_payload_sha256"],
                "seen_generation": generation,
                "historical_role": "SEEN_DEVELOPMENT_HISTORY",
                "future_primary_fresh_heldout_reuse_prohibited": True,
            }
    require(len(source_by_pmid) == 2420 and len(candidate_by_id) == 145
            and all(len(generations) == 1 for generations in source_by_pmid.values()),
            "COMBINED_SEEN_IDENTITY_ACCOUNTING_MISMATCH")
    combined_sources = [{"pmid": pmid, "seen_generations": sorted(generations),
                         "historical_role": "SEEN_DEVELOPMENT_HISTORY",
                         "future_primary_fresh_heldout_reuse_prohibited": True}
                        for pmid, generations in sorted(source_by_pmid.items(),
                                                         key=lambda item: int(item[0]))]
    combined_candidates = [candidate_by_id[key] for key in sorted(candidate_by_id)]
    combined_quality_groups = [{"source_group_id": row["source_group_id"],
                                "request_sha256": row["request_sha256"],
                                "seen_generation": "alpha3_18",
                                "historical_role": "SEEN_DEVELOPMENT_HISTORY",
                                "future_primary_fresh_heldout_reuse_prohibited": True}
                               for row in registries["alpha3_18_quality_groups"]]
    return locals()


def freeze(state: dict) -> None:
    OUT.mkdir()
    roots = state["historical_roots"]
    put("alpha3_19_closure_verification.json", {
        "alpha3_19g_root_sha256": HISTORICAL_ROOTS[-1][2],
        "alpha3_19f1_root_sha256": HISTORICAL_ROOTS[-2][2],
        "both_roots_verified": True,
        "primary_attempt_terminal_state":
            "TERMINATED_WITH_ZERO_QUALITY_INPUT_UNDER_CONSISTENT_FROZEN_GATES",
        "historical_builder_scientific_inference_events": 14,
        "historical_quality_scientific_inference_events": 0,
        "eligible_proposition_pool_state": "NOT_DERIVED"})
    put("alpha3_20_development_identity.json", {
        "namespace": "alpha3.20",
        "classification": "POST_ALPHA3_19_SEEN_DATA_DEVELOPMENT",
        "development_only": True,
        "not": ["PRIMARY_HELDOUT", "FRESH_HELDOUT", "INDEPENDENT_EVALUATION",
                "CONTINUATION_OF_ALPHA3_19_PRIMARY_ATTEMPT"],
        "tracks": ["EVIDENCE_GROUNDING_OWNERSHIP", "PROPOSITION_ABSTRACTION"],
        "fresh_attempt_started": False})
    put("seen_development_asset_boundary.json", {
        "allowed_scientific_material": ["frozen alpha3.18 seen development assets",
                                        "frozen alpha3.19 seen development assets"],
        "new_scientific_sources_used": False,
        "all_alpha3_20_touched_assets_historical_role": "SEEN_DEVELOPMENT_HISTORY",
        "future_primary_fresh_heldout_reuse_prohibited": True,
        "no_alpha3_20_output_may_be_relabelled_primary_fresh": True})
    source_sha = put_rows("alpha3_20_combined_seen_source_registry.jsonl",
                          state["combined_sources"])
    candidate_sha = put_rows("alpha3_20_combined_seen_candidate_registry.jsonl",
                             state["combined_candidates"])
    group_sha = put_rows("alpha3_20_combined_seen_quality_group_registry.jsonl",
                         state["combined_quality_groups"])
    put("development_contamination_registry_binding.json", {
        "input_registries": {name: reference(path)
                             for name, path in state["registry_paths"].items()},
        "combined_source_registry": {"path": "alpha3_20_combined_seen_source_registry.jsonl",
                                     "sha256": source_sha, "unique_pmid_count": 2420},
        "combined_candidate_registry": {"path": "alpha3_20_combined_seen_candidate_registry.jsonl",
                                        "sha256": candidate_sha, "candidate_count": 145},
        "combined_quality_group_registry": {"path": "alpha3_20_combined_seen_quality_group_registry.jsonl",
                                            "sha256": group_sha, "quality_group_count": 3},
        "future_primary_exclusion_required": True,
        "alpha3_20_new_outputs_must_be_appended_to_seen_history": True})
    put("alpha3_19_failure_mode_binding.json", {
        "raw_builder_candidates": 35,
        "offset_mismatch_with_unique_exact_body_quote": 29,
        "body_grounding_passes": 6,
        "lexical_leakage_failures_among_body_grounded": 6,
        "quality_input_candidates": 0,
        "quality_executed": False,
        "grounding_classification":
            "GROUNDING_CONTRACT_CONSISTENT_MODEL_NONCONFORMANCE",
        "leakage_classification": "LEAKAGE_CONTRACT_CONSISTENT_ZERO_SURVIVORS",
        "historical_states_reinterpreted_or_changed": False})
    put("grounding_ownership_problem_definition.json", {
        "track": "EVIDENCE_GROUNDING_OWNERSHIP",
        "sole_alpha3_19_observation": "29 exact unique BODY quotes failed only because model-authored offsets were incorrect.",
        "model_scientific_responsibility": "select and quote exact BODY evidence",
        "controller_deterministic_responsibility":
            "locate unique exact quote and derive paragraph, character offsets, and anchor identity",
        "controller_scientific_judgment_allowed": False,
        "track_a_success_on_seen_data":
            "exact unique quotations receive correct deterministic coordinates without model-authored offsets",
        "does_not_claim_quality_or_leakage_improvement": True,
        "alpha3_19_counterfactual_replay_only_development_diagnostic": True})

    evidence_contract = {
        "schema_version": "EvidenceReferenceContractV4",
        "status": "PROSPECTIVE_DEVELOPMENT_DESIGN_NOT_ACTIVE_IN_ALPHA3_19",
        "scientific_evidence_surface": "frozen canonical ConstructionEvidenceDocument body_text only",
        "canonical_body_normalization":
            "Unicode NFKC; whitespace collapsed within paragraphs; two LF between paragraphs, as already frozen in ConstructionEvidenceDocumentV1",
        "model_owned_fields": ["exact_text"],
        "model_exact_text_rule": "nonempty verbatim substring of permitted canonical BODY; no paraphrase",
        "response_binding_handle": "opaque nonsemantic source_record_token only if required",
        "controller_owned_reference_fields": ["source_field=body", "paragraph ordinal",
                                              "zero-based start_offset", "zero-based end_offset",
                                              "EvidenceSpanAnchorV1 span_id"],
        "model_supplied_offsets_or_paragraph_or_anchor_ids": False,
        "post_response_matching_representation":
            "exact Unicode code-point string equality against already-canonicalized body_text; no additional quote or BODY normalization",
        "zero_match_state": "GROUNDING_TEXT_NOT_FOUND",
        "one_match_action": "derive code-point offsets and require containment in exactly one canonical BODY paragraph",
        "multiple_match_state": "GROUNDING_TEXT_NONUNIQUE",
        "cross_paragraph_state": "GROUNDING_PARAGRAPH_BOUNDARY_INVALID",
        "abstract_bibliography_back_matter_or_other_document_search": False,
        "semantic_or_fuzzy_localization": False,
        "new_normalization_inferred_from_alpha3_19_examples": False,
        "historical_alpha3_19_grounding_states_changed": False,
    }
    evidence_sha = put("evidence_reference_contract_v4.json", evidence_contract)
    hash_marker("evidence_reference_contract_v4_sha256", evidence_sha)
    put("controller_unique_localization_contract.json", {
        "input": ["model exact_text", "same request's frozen canonical body_text",
                  "same ConstructionEvidenceDocument paragraph intervals"],
        "operation_order": [
            "reject empty exact_text",
            "count all exact non-overlapping and overlapping substring occurrences in canonical BODY",
            "zero occurrences -> GROUNDING_TEXT_NOT_FOUND",
            "more than one occurrence -> GROUNDING_TEXT_NONUNIQUE",
            "one occurrence -> derive zero-based Unicode code-point [start,end) offsets",
            "require exactly one canonical paragraph contains [start,end)",
            "derive frozen paragraph anchor identity from that paragraph"],
        "paragraph_failure_state": "GROUNDING_PARAGRAPH_BOUNDARY_INVALID",
        "no_model_or_semantic_choice_between_matches": True,
        "no_edit_distance_embedding_fuzzy_match_or_llm_reanchoring": True,
        "normalization": "none after canonical ConstructionEvidenceDocument body_text generation",
        "implementation_and_synthetic_replay_gate": "alpha3.20A must freeze and validate before any model calls"})
    put("grounding_model_controller_ownership_matrix.json", {
        "model_owned": ["scientific evidence selection", "exact BODY evidence quote",
                        "neutral proposition", "scientific relation components"],
        "controller_owned": ["permitted BODY surface", "source_field constant body",
                             "exact-match occurrence count", "paragraph resolution",
                             "zero-based character offsets", "anchor identity",
                             "opaque request and output provenance"],
        "model_generated_offsets_requested": False,
        "controller_semantic_evidence_selection": False})

    put("proposition_abstraction_problem_definition.json", {
        "track": "PROPOSITION_ABSTRACTION",
        "alpha3_19_body_grounded_candidates": 6,
        "frozen_leakage_failures": 6,
        "eight_token_only": 4, "jaccard_only": 0, "both": 2, "passed": 0,
        "development_question":
            "Can source-faithful, directionally explicit neutral propositions be expressed without unnecessary source-specific phrasing?",
        "candidate_repair_or_historical_reclassification": False})
    abstraction_contract = {
        "schema_version": "PropositionAbstractionContractV1",
        "status": "SEEN_DATA_DEVELOPMENT_ONLY_NOT_ACTIVE_IN_ALPHA3_19",
        "distinct_model_fields": ["exact_evidence_quote", "neutral_proposition",
                                  "actor_or_intervention", "response", "direction",
                                  "essential_biological_context"],
        "exact_evidence_quote": "verbatim source BODY evidence, never concatenated into the neutral proposition by controller",
        "neutral_proposition":
            "one neutral, testable, directionally explicit statement of the source-supported experimental relation in normalized scientific language",
        "must_preserve": ["actor or intervention", "observed response", "direction",
                          "essential biological context", "source-supported qualifiers"],
        "must_not": ["drop actor or response", "flip direction", "invent mechanism",
                     "broaden context", "generalize beyond evidence",
                     "copy unnecessary source-specific wording"],
        "scientific_fidelity_precedence_over_lexical_novelty": True,
        "prompt_must_not_mention_detector_thresholds_or_beating_leakage": True,
        "structural_nonempty_fields_do_not_establish_scientific_truth": True,
        "future_semantic_comparison_requires_separate_independent_development_adjudication_if_unresolved": True,
    }
    abstraction_sha = put("proposition_abstraction_contract_v1.json", abstraction_contract)
    hash_marker("proposition_abstraction_contract_v1_sha256", abstraction_sha)
    put("leakage_policy_preservation.json", {
        "source_authority": reference(F1 / "leakage_authority_timeline.json"),
        "candidate_side": "neutral_proposition only",
        "source_side": ["private source title", "containing evidence sentence with frozen ambiguity fallback"],
        "tokenization": "Unicode NFKC, lowercase, maximal Unicode-alphanumeric spans",
        "eight_consecutive_shared_token_failure_threshold": 8,
        "qualifying_token_jaccard_failure_threshold": 0.80,
        "combination": "OR",
        "comparison_policy_changed": False,
        "thresholds_changed": False,
        "zero_alpha3_19_survivors_sufficient_justification_for_change": False})
    put("builder_v4_design_constraints.json", {
        "prospective_version_family": ["BuilderGroundingContractV4",
                                       "BuilderOutputSchemaV4",
                                       "EvidenceReferenceContractV4",
                                       "PropositionAbstractionContractV1"],
        "historical_v3_overwrite": False,
        "model_generated_scientific_fields": ["exact evidence quote", "neutral proposition",
                                             "relation components"],
        "controller_generated_deterministic_fields": ["source_field body",
                                                    "paragraph and offsets", "anchor identity",
                                                    "provenance and cache identity"],
        "candidate_cardinality_per_request": {"minimum": 0, "maximum": 3},
        "opaque_nonsemantic_source_record_token_allowed_for_binding": True,
        "identifiable_source_metadata_exposure_allowed": False,
        "provider": "DeepSeek", "model": "deepseek-flash",
        "thinking_enabled": True, "reasoning_effort": "high",
        "this_master_authorizes_provider_calls": False})

    common = {
        "same_scientific_task": True, "same_canonical_body_evidence_input": True,
        "same_exact_evidence_quote_requirement": True,
        "same_candidate_cardinality_0_to_3": True,
        "same_provider_model_and_grounding_contract": True,
        "same_lexical_leakage_gate": True,
        "only_variable": "proposition-abstraction instruction text",
    }
    variants = [
        ("ABSTRACTION_V1_RELATION_SENTENCE",
         "State the source-supported experimental relation as a neutral, testable sentence. Retain the actor or intervention, observed response, direction, and essential biological context. Use normalized scientific terminology and omit incidental narrative wording."),
        ("ABSTRACTION_V2_RELATION_FRAME",
         "Express the source-supported actor or intervention, response, direction, and essential biological context as a coherent scientific relation, then verbalize it as one neutral, testable proposition. Retain qualifiers needed for the finding and omit incidental narrative wording."),
        ("ABSTRACTION_V3_CONTEXT_FIRST",
         "Write a concise neutral, testable proposition that first identifies the essential biological context and then states the source-supported actor or intervention and directional response. Preserve necessary specificity while omitting incidental narrative wording."),
    ]
    put("bounded_prompt_variant_policy.json", {
        "maximum_prospective_scientific_prompt_variants": 3,
        "all_three_variant_instructions_defined_before_model_execution": True,
        "variant_definition_status": "FROZEN_IN_MASTER_BEFORE_ALPHA3_20C",
        "full_request_template_assembly_and_hash_freeze_stage": "alpha3.20B",
        "no_adaptive_fourth_or_fifth_variant": True,
        "source_specific_customization_allowed": False,
        "common_invariants": common,
        "variants": [{"variant_id": ident, "abstraction_instruction": instruction,
                      "instruction_sha256": sha(instruction.encode("utf-8"))}
                     for ident, instruction in variants],
        "instructions_do_not_mention_leakage_detector_thresholds": True,
        "no_model_calls_authorized_by_variant_freeze": True})
    put("development_corpus_selection_contract.json", {
        "identity": "ALL_ALPHA3_19E_FROZEN_VALID_BODY_BUILDER_REQUESTS",
        "selection_rule": "all 14 frozen alpha3.19E request identities with valid canonical BODY, in frozen manifest order; no outcome-based filtering",
        "selection_based_on_candidate_quality_or_leakage": False,
        "historical_request_manifest": reference(E / "alpha3_19_builder_v3_request_manifest.jsonl"),
        "historical_construction_document_manifest":
            reference(E / "construction_document_manifest.jsonl"),
        "f1_body_visibility_audit": reference(F1 / "builder_request_body_visibility_audit.json"),
        "request_count": 14,
        "selected_request_identities": state["corpus"],
        "selected_request_identity_set_sha256": sha(canonical(state["corpus"])),
        "source_cohort_seen_development_history": True,
        "new_source_acquisition": False,
        "same_corpus_for_all_three_variants": True,
        "model_calls_before_corpus_freeze": 0})
    put("development_evaluation_dimensions.json", {
        "fixed_request_denominator": 14,
        "dimensions_reported_separately": [
            {"name": "BUILDER_RESPONSE_VALIDITY",
             "states": ["SCHEMA_VALID_NONZERO", "SCHEMA_VALID_ZERO", "INVALID_COMPLETED", "TRANSPORT_UNCERTAIN_OR_FAILED"]},
            {"name": "EXACT_EVIDENCE_QUOTE_AVAILABILITY",
             "states": ["EXACT_QUOTE_NOT_FOUND", "EXACT_QUOTE_UNIQUE", "EXACT_QUOTE_NONUNIQUE"]},
            {"name": "CONTROLLER_LOCALIZATION",
             "states": ["UNIQUE_AND_ONE_PARAGRAPH", "NOT_FOUND", "NONUNIQUE", "PARAGRAPH_BOUNDARY_INVALID"]},
            {"name": "PROPOSITION_LEAKAGE",
             "states": ["PASS", "FAIL_8_TOKEN", "FAIL_JACCARD", "FAIL_BOTH", "NOT_EVALUATED"]},
            {"name": "SCIENTIFIC_STRUCTURE_COMPLETENESS",
             "mechanical_checks": ["nonempty actor/intervention", "nonempty response",
                                   "explicit direction field", "nonempty essential biological context"],
             "scientific_truth_established_by_mechanical_checks": False}],
        "candidate_counts_and_request_level_any_pass_reported": True,
        "invalid_or_zero_response_not_silently_removed_from_denominator": True,
        "weighted_composite_score": None,
        "semantic_scientific_assessment_if_needed": "separate alpha3.20E development Quality preregistration"})
    put("prompt_variant_selection_rule.json", {
        "status": "PROSPECTIVE_RULE_FROZEN_BEFORE_ALPHA3_20C",
        "same_14_request_corpus_required": True,
        "baseline_variant_id": variants[0][0],
        "eligibility_precedence": [
            "response and scientific-structure completeness must not regress against baseline on per-request coverage or total complete-candidate count",
            "unique exact BODY grounding must not regress against baseline on per-request coverage or total grounded-candidate count",
            "scientific semantic fidelity must be independently resolved before final selection if structural checks cannot establish it",
            "only then compare frozen leakage pass performance"],
        "per_request_nonregression":
            "for every request where baseline has at least one complete or uniquely grounded candidate, variant must retain at least one respectively",
        "aggregate_nonregression":
            "candidate count satisfying each prerequisite must be no lower than baseline across the fixed 14 requests",
        "leakage_comparison":
            "maximize number of fixed requests with at least one candidate passing all prerequisite gates and frozen leakage gate; missing or invalid responses count as zero",
        "tie_break_order": [item[0] for item in variants],
        "semantic_fidelity_unresolved_action": "NO_FINAL_VARIANT_SELECTION; preregister independent alpha3.20E development adjudication",
        "no_eligible_variant_action": "NO_FINAL_VARIANT_SELECTION",
        "subjective_looks_better_selection": False,
        "weighted_composite_score": False,
        "no_result_driven_prompt_rerun": True})
    put("future_quality_development_boundary.json", {
        "this_stage_quality_scientific_calls": 0,
        "mechanical_structure_presence_is_not_scientific_truth": True,
        "if_semantic_variant_comparison_needed":
            "separately preregister independent alpha3.20E development Quality rubric, blinding, call budget, failure policy, and freeze",
        "historical_alpha3_19_quality_calls": 0,
        "quality_response_envelope_v3_remains_bound_for_future_use": True,
        "quality_response_envelope_v3_sha256": QUALITY_ENVELOPE_SHA,
        "future_quality_calls_authorized_here": False})
    put("deepseek_flash_binding.json", {
        "future_prospective_provider": "DeepSeek",
        "future_prospective_model": "deepseek-flash",
        "thinking_enabled": True,
        "reasoning_effort": "high",
        "deepseek_v4_pro_prospective_fallback_allowed": False,
        "historical_model_provenance_unchanged": True,
        "this_stage_model_calls": 0})
    put("future_fresh_attempt_readiness_contract.json", {
        "new_fresh_attempt_started": False,
        "quality_response_envelope_v3_sha256": QUALITY_ENVELOPE_SHA,
        "all_required_before_future_primary_cohort": [
            "EvidenceReferenceContractV4 frozen and implementation validated",
            "controller exact unique localization implementation frozen",
            "Builder V4 scientific interface and output schema frozen",
            "PropositionAbstractionContractV1 frozen",
            "lexical leakage policy frozen prospectively",
            "QualityResponseEnvelopeV3 hardened and bound",
            "provider and model deepseek-flash frozen",
            "all development model-call history preserved",
            "combined alpha3.18/alpha3.19/alpha3.20 contamination boundary frozen",
            "separate new primary fresh-cohort preregistration and authorization"],
        "alpha3_21_automatically_designated": False})
    phases = [
        {"phase": "alpha3.20A", "purpose": "EvidenceReferenceContractV4 offline implementation and replay validation", "model_calls_authorized_by_master": 0},
        {"phase": "alpha3.20B", "purpose": "assemble and freeze all three full proposition-abstraction prompt variants and fixed corpus", "model_calls_authorized_by_master": 0},
        {"phase": "alpha3.20C", "purpose": "seen-development Builder execution, separately authorized", "model_calls_authorized_by_master": 0},
        {"phase": "alpha3.20D", "purpose": "frozen deterministic grounding and leakage evaluation", "model_calls_authorized_by_master": 0},
        {"phase": "alpha3.20E", "purpose": "optional, separately preregistered independent development semantic adjudication if needed", "model_calls_authorized_by_master": 0},
        {"phase": "alpha3.20F", "purpose": "final Builder V4 contract selection or explicit no-selection freeze", "model_calls_authorized_by_master": 0},
    ]
    put("alpha3_20_phase_barriers.json", {
        "ordered_phases": phases,
        "no_alpha3_20_model_call_before_v4_localization_and_three_prompt_variants_frozen": True,
        "all_alpha3_20_scientific_material_seen_development_history": True,
        "only_after_alpha3_20f": "design a separately preregistered next fresh primary attempt",
        "no_phase_execution_authorized_by_this_master": True})
    execution_plan = {
        "identity": "ALPHA3_20_POST_ALPHA3_19_SEEN_DATA_DEVELOPMENT_MASTER",
        "development_only": True,
        "historical_closure_root_sha256": HISTORICAL_ROOTS[-1][2],
        "historical_f1_audit_root_sha256": HISTORICAL_ROOTS[-2][2],
        "track_a": "EVIDENCE_GROUNDING_OWNERSHIP",
        "track_b": "PROPOSITION_ABSTRACTION",
        "evidence_reference_contract_v4_sha256": evidence_sha,
        "proposition_abstraction_contract_v1_sha256": abstraction_sha,
        "fixed_seen_request_count": 14,
        "fixed_seen_request_identity_set_sha256": sha(canonical(state["corpus"])),
        "maximum_prompt_variants": 3,
        "phases": phases,
        "future_builder_provider": "DeepSeek",
        "future_builder_model": "deepseek-flash",
        "future_builder_thinking": "enabled",
        "future_builder_reasoning_effort": "high",
        "potential_one_call_per_request_per_variant_count_not_authorized": 42,
        "future_call_budget_and_transport_policy_require_separate_freeze_and_authorization": True,
        "provider_calls_authorized_now": 0,
        "llm_calls_authorized_now": 0,
        "network_calls_authorized_now": 0,
        "future_primary_attempt_designated": False,
    }
    plan_sha = put("alpha3_20_master_execution_plan.json", execution_plan)
    hash_marker("alpha3_20_master_execution_plan_sha256", plan_sha)
    require(verify_historical_roots() == roots,
            "HISTORICAL_ROOTS_CHANGED_DURING_ALPHA320_FREEZE")
    put("historical_preservation_audit.json", {
        "historical_roots_verified_before_and_after": True,
        "historical_roots": roots,
        "historical_primary_results_modified": False,
        "alpha3_19_candidate_states_replayed_or_rewritten": False,
        "new_scientific_sources_acquired": False})
    put("scientific_state_safety_audit.json", {
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "deepseek_calls": 0, "builder_calls": 0, "quality_calls": 0,
        "scientific_extraction_calls": 0,
        "new_scientific_sources_used": False,
        "fresh_attempt_started": False,
        "historical_assets_modified": False,
        "leakage_thresholds_changed": False,
        "leakage_comparison_policy_changed": False})
    validation = {
        "status": "completed",
        "alpha3_19_closure_verified": True,
        "alpha3_20_is_development_only": True,
        "new_scientific_sources_used": False,
        "historical_primary_results_modified": False,
        "grounding_offset_model_owned": False,
        "grounding_exact_quote_model_owned": True,
        "grounding_coordinates_controller_owned": True,
        "controller_localization_exact_match_only": True,
        "fuzzy_grounding_allowed": False,
        "leakage_thresholds_changed": False,
        "leakage_comparison_policy_changed": False,
        "proposition_abstraction_development_allowed": True,
        "max_prompt_variants": 3,
        "prompt_variants_must_be_frozen_before_calls": True,
        "prompt_variants_frozen_before_calls": True,
        "future_builder_model": "deepseek-flash",
        "new_fresh_attempt_started": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "fixed_seen_development_corpus_request_count": 14,
        "combined_seen_source_pmid_count": 2420,
        "combined_seen_candidate_count": 145,
        "evidence_reference_contract_v4_sha256": evidence_sha,
        "proposition_abstraction_contract_v1_sha256": abstraction_sha,
        "alpha3_20_master_execution_plan_sha256": plan_sha,
        "next_stage_recommendation": NEXT,
        "historical_assets_modified": False,
    }
    put("validation.json", validation)
    put("summary.json", {
        "status": "completed",
        "identity": "POST_ALPHA3_19_SEEN_DATA_DEVELOPMENT",
        "tracks": ["EVIDENCE_GROUNDING_OWNERSHIP", "PROPOSITION_ABSTRACTION"],
        "fixed_seen_request_count": 14,
        "prompt_variant_count": 3,
        "model_calls": 0,
        "new_fresh_attempt_started": False,
        "next_stage_recommendation": NEXT})
    root = root_hash(OUT, ROOT_MARKER)
    hash_marker(ROOT_MARKER, root)
    require(root_hash(OUT, ROOT_MARKER) == root,
            "ALPHA320_MASTER_ROOT_VERIFY_FAILED")
    print(json.dumps({"status": "completed", "root_sha256": root,
                      "evidence_reference_contract_v4_sha256": evidence_sha,
                      "proposition_abstraction_contract_v1_sha256": abstraction_sha,
                      "alpha3_20_master_execution_plan_sha256": plan_sha}, sort_keys=True))


def main() -> None:
    state = preflight()
    freeze(state)


if __name__ == "__main__":
    main()
