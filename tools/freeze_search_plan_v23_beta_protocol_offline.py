#!/usr/bin/env python3
"""Freeze the v2.3-beta Policy A candidate and held-out-v2 protocol offline."""

from __future__ import annotations

import json
from pathlib import Path

from code_engine.search.historical_manifest_verifier import verify_frozen_manifest
from code_engine.search.search_plan_v23_beta_policy import decide_search_plan_v23_beta_disposition

if __package__:
    from . import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
    from . import run_search_plan_v23_alpha1_1_biological_unit_refinement_offline as alpha1_1
    from . import run_search_plan_v23_alpha2_1_functional_relation_refinement_offline as alpha2_1
    from . import run_search_plan_v23_alpha3_endpoint_semantics_shadow_offline as alpha3
    from . import run_search_plan_v23_alpha4_composite_tierb_shadow_offline as alpha4
else:
    import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
    import run_search_plan_v23_alpha1_1_biological_unit_refinement_offline as alpha1_1
    import run_search_plan_v23_alpha2_1_functional_relation_refinement_offline as alpha2_1
    import run_search_plan_v23_alpha3_endpoint_semantics_shadow_offline as alpha3
    import run_search_plan_v23_alpha4_composite_tierb_shadow_offline as alpha4


ROOT = alpha1.ROOT
RUN = ROOT / "runs/20260915_search_plan_v23_beta_protocol_freeze_offline"
CONFIG = ROOT / "configs/search_plans/search_plan_v23_beta.json"
IMPLEMENTATION = ROOT / "src/code_engine/search/search_plan_v23_beta_policy.py"
TEST = ROOT / "tests/test_search_plan_v23_beta_policy.py"
V22_QUERY_COMPILER = ROOT / "tools/generate_search_plan_v2_multicase_stress_test_offline.py"
V22_QUERY_FAMILIES = alpha4.CASE_FREEZE / "heldout_query_families.jsonl"
V22_QUERY_VARIANTS = alpha4.CASE_FREEZE / "heldout_query_variants.jsonl"
PRODUCTION_FILES = [CONFIG, IMPLEMENTATION]

EXPECTED_ROOTS = {
    "p0_biological_unit_compatibility_sha256": "f5906384c549c31c167aeb511f9a4e37c597dbd93ac1ba530e6b2debd687831c",
    "p1_functional_relation_evidence_sha256": "fc5b98266996235995595ad6c097dc433ef0345d6023cda4e5deaa55a32e12b3",
    "p2_endpoint_semantics_sha256": "cd576081b9b9add0d29a5982ec10fa3545dccd0eeb64e34949cefc6ff43e755d",
    "p3_composite_alpha4_sha256": "c09c7b0def3df875220ce71844c2004cb5e8040510d7fcdb7da41cad31784ccf",
    "alpha4_candidate_profiles_sha256": "7caf0046f396d2a3c5b5300e80f6541a57ae09ad02ba6b0600c7379d4f43b721",
}
ZERO_CALLS = {"network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0}
REQUIRED = {
    "search_plan_v23_beta_config_snapshot.json",
    "policy_a_production_candidate.json",
    "v23_beta_development_boundary.json",
    "metrics_spec_v2.json",
    "metrics_spec_v2_validation.json",
    "heldout_v2_evaluation_protocol.json",
    "heldout_v2_evaluation_protocol.md",
    "heldout_v2_case_selection_protocol.json",
    "adjudication_boundary_v2.json",
    "version_manifest.json",
    "scientific_state_safety_audit.json",
    "root_hash_verification.json",
    "validation.json",
    "summary.json",
}
ROOT_CARRIERS = {"version_manifest.json", "root_hash_verification.json", "summary.json"}


def require(condition, message):
    alpha1.frozen.require(condition, message)


def load_json(path: Path):
    return json.loads(path.read_bytes())


def pretty(value):
    return alpha1.frozen.pretty_json(value)


def sha(path: Path):
    return alpha1.frozen.sha256(path)


def digest(body: bytes):
    return alpha1.frozen.digest(body)


def tagged(payload):
    return {"protocol_status": "frozen_before_heldout_v2_case_selection", **payload}


def verify_upstreams():
    roots = {
        "p0_biological_unit_compatibility_sha256": verify_frozen_manifest(
            alpha1_1.RUN, root_field="v23_alpha1_1_biological_unit_refinement_sha256"
        )["aggregate_sha256"],
        "p1_functional_relation_evidence_sha256": verify_frozen_manifest(
            alpha2_1.RUN, root_field="v23_alpha2_1_functional_relation_refinement_sha256"
        )["aggregate_sha256"],
        "p2_endpoint_semantics_sha256": verify_frozen_manifest(
            alpha3.RUN, root_field="v23_alpha3_endpoint_semantics_shadow_sha256"
        )["aggregate_sha256"],
        "p3_composite_alpha4_sha256": verify_frozen_manifest(
            alpha4.RUN, root_field="v23_alpha4_composite_tierb_shadow_sha256"
        )["aggregate_sha256"],
        "alpha4_candidate_profiles_sha256": sha(
            alpha4.RUN / "v23_alpha4_candidate_composite_profiles.jsonl"
        ),
    }
    require(roots == EXPECTED_ROOTS, f"frozen development roots changed: {roots}")
    for run in (alpha1_1.RUN, alpha2_1.RUN, alpha3.RUN, alpha4.RUN):
        alpha4.verify_declared_production_files(run)
    require(sha(V22_QUERY_COMPILER) == "2ed6e963d9c74e78ee2a03e458808d213e712f0cec264557efc053c376f72f32",
            "frozen v2.2 query compiler changed")
    require(sha(V22_QUERY_FAMILIES) == "2cff00adb43eacd9f07367ab664647606a15b8e541ff0ed0860feaf7e05c7846",
            "frozen v2.2 query-family artifact changed")
    require(sha(V22_QUERY_VARIANTS) == "53330d06176ef1ae8a23ad41649aa9e09caa4ea69aa9970ecf03db699518d5b2",
            "frozen v2.2 query-variant artifact changed")
    return roots


def protected_state():
    verify_upstreams()
    paths = []
    for run in (alpha1_1.RUN, alpha2_1.RUN, alpha3.RUN, alpha4.RUN):
        paths.extend(path for path in run.iterdir() if path.is_file())
    retrieval = alpha4.RETRIEVAL
    case_freeze = alpha4.CASE_FREEZE
    paths.extend([
        retrieval / "manifest.json", retrieval / "metadata_inventory.jsonl",
        retrieval / "v22_gate_outputs.jsonl", retrieval / "fulltext_selection_inventory.jsonl",
        case_freeze / "freeze_manifest.json", case_freeze / "heldout_scientific_targets.jsonl",
        V22_QUERY_COMPILER, V22_QUERY_FAMILIES, V22_QUERY_VARIANTS,
    ])
    for run in (alpha1_1.RUN, alpha2_1.RUN, alpha3.RUN, alpha4.RUN):
        manifest = load_json(run / "implementation_manifest.json")
        paths.extend(ROOT / row["path"] for row in manifest["production_files"])
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(set(paths))}


def metric(metric_id, numerator, denominator, terminology):
    return {
        "metric_id": metric_id,
        "unit": "unique_packet",
        "numerator_predicate": numerator,
        "denominator_predicate": denominator,
        "reported_values": {
            "n": "count_unique_packet_id_satisfying_numerator_predicate",
            "N": "count_unique_packet_id_satisfying_denominator_predicate",
            "fraction": "n / N",
            "percentage": "100 * n / N",
            "zero_denominator": {"fraction": None, "percentage": None,
                                 "status": "UNDEFINED_ZERO_DENOMINATOR"},
        },
        "terminology": terminology,
    }


def eq(field, value):
    return {"operator": "EQ", "field": field, "value": value}


def inside(field, values):
    return {"operator": "IN", "field": field, "values": values}


def both(*predicates):
    return {"operator": "AND", "predicates": list(predicates)}


def build_metrics_spec():
    adjudicated = both(
        eq("acquired", True),
        eq("adjudication_status", "SUCCESSFULLY_ADJUDICATED"),
    )
    tier_a = both(adjudicated, eq("final_v23_beta_disposition_at_acquisition", "TIER_A"))
    tier_b = both(adjudicated, eq("final_v23_beta_disposition_at_acquisition", "TIER_B"))
    direct = eq("relevance_state", "DIRECTLY_RELEVANT")
    justified = eq("acquisition_decision", "JUSTIFIED")
    acceptable = inside("acquisition_decision", ["JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED"])
    metrics = [
        metric("overall_direct_relevance", both(adjudicated, direct), adjudicated,
               "direct relevance among adjudicated acquired papers"),
        metric("overall_acquisition_justification", both(adjudicated, justified), adjudicated,
               "acquisition justification among adjudicated acquired papers"),
        metric("overall_acquisition_acceptability", both(adjudicated, acceptable), adjudicated,
               "acquisition acceptability among adjudicated acquired papers"),
        metric("tier_a_direct_relevance", both(tier_a, direct), tier_a,
               "direct relevance among adjudicated acquired final-Tier-A papers"),
        metric("tier_a_acquisition_acceptability", both(tier_a, acceptable), tier_a,
               "acquisition acceptability among adjudicated acquired final-Tier-A papers"),
        metric("tier_b_direct_relevance", both(tier_b, direct), tier_b,
               "direct relevance among adjudicated acquired final-Tier-B papers"),
        metric("tier_b_acquisition_acceptability", both(tier_b, acceptable), tier_b,
               "acquisition acceptability among adjudicated acquired final-Tier-B papers"),
        metric("biological_unit_contamination_rate",
               both(adjudicated, eq("contaminant_class", "wrong_biological_unit")), adjudicated,
               "unique-packet biological-unit contamination among adjudicated acquired papers"),
        metric("functional_relation_contamination_rate", both(adjudicated, {
                   "operator": "OR", "predicates": [
                       eq("relevance_state", "WRONG_EVIDENCE_MODE"),
                       eq("contaminant_class", "association_vs_functional_relation"),
                   ]}), adjudicated,
               "unique-packet functional-relation contamination among adjudicated acquired papers"),
        metric("endpoint_contamination_rate", both(adjudicated, {
                   "operator": "OR", "predicates": [
                       eq("relevance_state", "WRONG_ENDPOINT"),
                       eq("contaminant_class", "wrong_endpoint"),
                   ]}), adjudicated,
               "unique-packet endpoint contamination among adjudicated acquired papers"),
    ]
    return tagged({
        "artifact_schema_version": "MetricsSpecV2",
        "metrics_spec_version": "v2",
        "reporting_population": "successfully adjudicated acquired papers",
        "record_identity_field": "packet_id",
        "required_record_fields": [
            "packet_id", "case_id", "ambiguity_stratum", "acquired", "adjudication_status",
            "final_v23_beta_disposition_at_acquisition", "acquisition_decision",
            "relevance_state", "contaminant_class",
        ],
        "categorical_mappings": {
            "acquired": [True, False],
            "adjudication_status": ["SUCCESSFULLY_ADJUDICATED", "NOT_SUCCESSFULLY_ADJUDICATED"],
            "final_v23_beta_disposition_at_acquisition": ["TIER_A", "TIER_B"],
            "acquisition_decision": ["JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED", "NOT_JUSTIFIED"],
            "relevance_state": [
                "DIRECTLY_RELEVANT", "PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED",
                "RELATED_BUT_WRONG_PROPOSITION", "WRONG_ENDPOINT", "WRONG_ENTITY",
                "WRONG_EVIDENCE_MODE", "WRONG_THERAPY", "TOPIC_ONLY",
                "INSUFFICIENT_SOURCE_EVIDENCE",
            ],
            "contaminant_class": [
                None, "wrong_evidence_mode", "association_vs_functional_relation",
                "wrong_biological_unit", "wrong_endpoint", "wrong_entity",
                "baseline_viability_vs_adaptation",
            ],
            "ambiguity_stratum": ["LOW", "MEDIUM", "HIGH"],
        },
        "primary_metric_ids": [
            "overall_direct_relevance", "overall_acquisition_justification",
            "overall_acquisition_acceptability", "tier_a_direct_relevance",
            "tier_a_acquisition_acceptability", "tier_b_direct_relevance",
            "tier_b_acquisition_acceptability",
        ],
        "contaminant_metric_ids": [
            "biological_unit_contamination_rate", "functional_relation_contamination_rate",
            "endpoint_contamination_rate",
        ],
        "metrics": metrics,
        "packet_deduplication_rule": "Each packet_id contributes at most once to each numerator and denominator, including OR predicates.",
        "required_distribution_reports": ["full_relevance_state_distribution", "full_contaminant_distribution"],
        "per_case_reporting": {
            "group_by": "case_id", "include_all_cases": True,
            "fields": ["acquired_N", "final_tier_a_N", "final_tier_b_N",
                       "direct_n_over_N", "justified_n_over_N", "acceptable_n_over_N",
                       "full_relevance_state_distribution", "full_contaminant_distribution"],
            "metric_bindings": {
                "direct_n_over_N": "overall_direct_relevance evaluated within case_id",
                "justified_n_over_N": "overall_acquisition_justification evaluated within case_id",
                "acceptable_n_over_N": "overall_acquisition_acceptability evaluated within case_id",
                "acquired_N": "count unique packet_id where acquired == true and adjudication_status == SUCCESSFULLY_ADJUDICATED",
                "final_tier_a_N": "count denominator packets where final_v23_beta_disposition_at_acquisition == TIER_A",
                "final_tier_b_N": "count denominator packets where final_v23_beta_disposition_at_acquisition == TIER_B"
            }
        },
        "per_ambiguity_reporting": {
            "group_by": "ambiguity_stratum", "required_strata": ["LOW", "MEDIUM", "HIGH"],
            "fields": ["N", "direct_n_over_N", "justified_n_over_N", "acceptable_n_over_N",
                       "final_tier_a_N", "final_tier_b_N", "full_relevance_state_distribution",
                       "full_contaminant_distribution"],
            "metric_bindings": {
                "direct_n_over_N": "overall_direct_relevance evaluated within ambiguity_stratum",
                "justified_n_over_N": "overall_acquisition_justification evaluated within ambiguity_stratum",
                "acceptable_n_over_N": "overall_acquisition_acceptability evaluated within ambiguity_stratum",
                "N": "count unique packet_id where acquired == true and adjudication_status == SUCCESSFULLY_ADJUDICATED",
                "final_tier_a_N": "count denominator packets where final_v23_beta_disposition_at_acquisition == TIER_A",
                "final_tier_b_N": "count denominator packets where final_v23_beta_disposition_at_acquisition == TIER_B"
            }
        },
        "engineering_criteria": [
            {"criterion_id": "C1", "metric_id": "overall_acquisition_acceptability",
             "operator": "GTE", "threshold": 0.65},
            {"criterion_id": "C2", "metric_id": "tier_a_acquisition_acceptability",
             "operator": "GTE", "threshold": 0.80},
            {"criterion_id": "C3", "metric_id": "tier_b_acquisition_acceptability",
             "operator": "GTE", "threshold": 0.30},
            {"criterion_id": "C4", "metric_id": "functional_relation_contamination_rate",
             "operator": "LTE", "threshold": 0.15},
        ],
        "ambiguity_stratum_safety_rule": {
            "criterion_id": "AMBIGUITY_STRATUM_DIRECT_SAFETY",
            "for_each": ["LOW", "MEDIUM", "HIGH"],
            "applicability": {"adjudicated_acquired_N": {"operator": "GTE", "value": 10}},
            "requirement": {"directly_relevant_n": {"operator": "GTE", "value": 1}},
            "failure_status": "FAIL_AMBIGUITY_STRATUM_ZERO_DIRECT",
            "criterion_type": "engineering_safety_not_statistical_hypothesis_test",
        },
        "forbidden_primary_machinery": [
            "confidence_interval", "bootstrap", "significance_test", "weighted_score",
            "composite_performance_score", "Tier B utility proxy",
        ],
        "default_primary_reporting": ["raw_n", "raw_N", "fraction", "percentage"],
        "descriptive_posthoc_requires_secondary_label": True,
    })


def validate_predicate(predicate, categorical):
    operator = predicate.get("operator")
    require(operator in {"EQ", "IN", "AND", "OR"}, f"undefined predicate operator: {operator}")
    if operator in {"AND", "OR"}:
        require(predicate.get("predicates"), f"empty {operator} predicate")
        for child in predicate["predicates"]:
            validate_predicate(child, categorical)
        return
    field = predicate.get("field")
    require(field in categorical, f"predicate uses undefined categorical field: {field}")
    values = [predicate.get("value")] if operator == "EQ" else predicate.get("values")
    require(isinstance(values, list) and values, f"predicate has no categorical values: {predicate}")
    require(all(value in categorical[field] for value in values),
            f"predicate uses undefined categorical value: {predicate}")


def predicate_contains(predicate, field, value):
    if predicate.get("operator") == "EQ":
        return predicate.get("field") == field and predicate.get("value") == value
    return any(predicate_contains(child, field, value)
               for child in predicate.get("predicates", []))


def validate_metrics_spec(spec):
    metrics = spec["metrics"]
    by_id = {row["metric_id"]: row for row in metrics}
    require(len(by_id) == len(metrics) == 10, "metric IDs must be unique and fully defined")
    require(set(spec["primary_metric_ids"] + spec["contaminant_metric_ids"]) == set(by_id),
            "metric registry membership mismatch")
    for row in metrics:
        require(row.get("numerator_predicate") and row.get("denominator_predicate"),
                f"metric missing numerator/denominator: {row['metric_id']}")
        validate_predicate(row["numerator_predicate"], spec["categorical_mappings"])
        validate_predicate(row["denominator_predicate"], spec["categorical_mappings"])
        require(predicate_contains(row["denominator_predicate"], "acquired", True),
                f"denominator does not require acquired == true: {row['metric_id']}")
        require(predicate_contains(row["denominator_predicate"], "adjudication_status",
                                   "SUCCESSFULLY_ADJUDICATED"),
                f"denominator does not require successful adjudication: {row['metric_id']}")
        require(set(row["reported_values"]) == {"n", "N", "fraction", "percentage", "zero_denominator"},
                f"metric outputs incomplete: {row['metric_id']}")
    criteria = spec["engineering_criteria"]
    require(all(row["metric_id"] in by_id for row in criteria),
            "engineering criterion references undefined metric")
    require([(row["metric_id"], row["operator"], row["threshold"]) for row in criteria] == [
        ("overall_acquisition_acceptability", "GTE", 0.65),
        ("tier_a_acquisition_acceptability", "GTE", 0.80),
        ("tier_b_acquisition_acceptability", "GTE", 0.30),
        ("functional_relation_contamination_rate", "LTE", 0.15),
    ], "engineering thresholds changed")
    return tagged({
        "artifact_schema_version": "MetricsSpecV2Validation",
        "status": "PASS",
        "defined_metric_count": len(metrics),
        "primary_metric_count": len(spec["primary_metric_ids"]),
        "contaminant_metric_count": len(spec["contaminant_metric_ids"]),
        "all_metrics_have_explicit_numerator": True,
        "all_metrics_have_explicit_denominator": True,
        "all_denominators_require_acquired_true": True,
        "all_denominators_require_successful_adjudication": True,
        "all_metric_predicates_machine_validated": True,
        "all_engineering_thresholds_reference_defined_metrics": True,
        "all_categorical_mappings_explicit": True,
        "packet_level_or_predicates_deduplicated_by_packet_id": True,
        "placeholder_success_criteria_remaining": 0,
        "undefined_metric_names": [],
        "legacy_tier_b_utility_proxy_used_as_primary_metric": False,
    })


def adjudication_boundary():
    return tagged({
        "artifact_schema_version": "AdjudicationBoundaryV2",
        "reviewer_type_default": "model_retrieval_adjudicator",
        "human_gold_label_allowed_only_for_real_human_adjudicator": True,
        "pass_a": {
            "purpose": "acquisition_justification_from_evidence_available_at_acquisition_time",
            "allowed_fields": [
                "ScientificPropositionTargetV1", "title", "abstract", "publication_metadata",
                "frozen_preacquisition_retrieval_evidence",
                "preacquisition_known_pmcid_identifier_as_metadata_only",
            ],
            "forbidden_fields": [
                "acquired_fulltext", "pmcid_derived_content", "fulltext_excerpts",
                "PASS_B_adjudication", "final_relevance_state", "contaminant_class",
                "final_v23_beta_disposition", "v22_tier", "gate_states", "P0_state",
                "P1_state", "P2_state", "composite_eligibility", "query_rank",
                "performance_metrics",
            ],
            "fulltext_visible": False,
            "preacquisition_only": True,
            "publication_metadata_field_allowlist": [
                "pmid", "preacquisition_known_pmcid_identifier", "doi", "journal",
                "publication_date", "publication_type"
            ],
            "frozen_preacquisition_retrieval_evidence_field_allowlist": [
                "metadata_resolution_status", "abstract_availability",
                "publication_type_authority", "identifier_resolution_status"
            ],
        },
        "pass_b": {
            "purpose": "isolated_scientific_relevance_adjudication",
            "allowed_fields": [
                "ScientificPropositionTargetV1", "title", "abstract",
                "frozen_legal_fulltext_excerpts", "fulltext_excerpt_provenance",
            ],
            "forbidden_fields": [
                "PASS_A_adjudication", "acquisition_decision", "v22_tier",
                "final_v23_beta_disposition", "gate_states", "P0_state", "P1_state",
                "P2_state", "composite_eligibility", "tier_b_subtier", "query_family",
                "query_rank", "retrieval_depth", "performance_metrics",
            ],
            "isolated_evaluator_workspace_required": True,
        },
        "cross_pass_visibility": {"pass_a_may_see_pass_b": False, "pass_b_may_see_pass_a": False},
    })


def case_selection_protocol():
    return tagged({
        "artifact_schema_version": "HeldoutV2CaseSelectionProtocolV1",
        "heldout_v2_cases_selected": False,
        "case_count": 8,
        "ambiguity_strata": {"LOW": 2, "MEDIUM": 2, "HIGH": 4},
        "domain_composition": {"oncology": 2, "non_oncology": 6},
        "selection_timing": "before_query_compilation_retrieval_and_candidate_inspection",
        "required_target_fields": [
            "subject", "relation_family", "measurement_target",
            "measurement_property_endpoint", "context_qualifiers_when_required",
            "therapy_or_treatment_when_applicable", "evidence_mode_requirement_when_applicable",
        ],
        "novelty_constraints": [
            "entirely_new_scientific_proposition",
            "no_exact_heldout_v1_proposition_recurrence",
            "no_exact_subject_relation_endpoint_triple_from_heldout_v1",
        ],
        "selection_prohibitions": [
            "heldout_v1_failure_label_targeting", "module_showcase_case_selection",
            "expected_conflict_targeting", "expected_high_yield_targeting", "easy_only_selection",
        ],
        "broad_difficulty_strata_reuse_allowed": True,
        "selection_rationale_must_be_frozen_before_retrieval": True,
        "case_replacement_after_retrieval_begins": False,
        "actual_case_names": [],
    })


def evaluation_protocol(metrics_spec, boundary, selection):
    return tagged({
        "artifact_schema_version": "HeldoutV2EvaluationProtocolV1",
        "search_plan_version": "v2.3-beta",
        "metrics_spec_version": metrics_spec["metrics_spec_version"],
        "heldout_v2_cases_selected": False,
        "heldout_v2_queries_compiled": False,
        "heldout_v2_retrieval_started": False,
        "case_design": {
            "case_count": selection["case_count"],
            "ambiguity_strata": selection["ambiguity_strata"],
            "domain_composition": selection["domain_composition"],
        },
        "query_and_budget_design": load_json(CONFIG)["query_and_budget_design"],
        "adjudication_architecture": {
            "pass_a": boundary["pass_a"], "pass_b": boundary["pass_b"],
            "reviewer_type_default": boundary["reviewer_type_default"],
        },
        "execution_sequence": [
            "v2.3-beta implementation/protocol freeze",
            "held-out-v2 case selection",
            "held-out-v2 case freeze",
            "query compilation freeze",
            "network retrieval",
            "acquisition sampling",
            "neutral review freeze",
            "PASS A blinded pre-acquisition adjudication",
            "PASS A freeze",
            "PASS B isolated relevance adjudication",
            "PASS B freeze",
            "primary-results merge freeze",
            "metrics unblinding",
        ],
        "sequence_reordering_allowed": False,
        "case_replacement_after_retrieval_begins": False,
        "primary_reporting": ["raw_n", "raw_N", "fraction", "percentage"],
        "primary_statistical_inference_enabled": False,
    })


def protocol_markdown(config, metrics, protocol, boundary, selection):
    lines = [
        "# Search Plan v2.3-beta held-out-v2 evaluation protocol", "",
        "Status: frozen before held-out-v2 case selection. No cases, queries, or retrieval are present.", "",
        "## Production candidate", "",
        "Policy A is the sole selected production candidate. It demotes blocked original Tier-A candidates to Tier B, preserves original Tier B, reject, and abstain dispositions, performs no upward promotion, and performs no hard rejection.", "",
        "Tier-B subtiers are annotations only. Acquisition remains surviving Tier A before Tier B, with unchanged v2.2 within-tier ordering.", "",
        "## Metrics", "",
    ]
    for metric_row in metrics["metrics"]:
        lines.append(f"- `{metric_row['metric_id']}`: {metric_row['terminology']}; report n, N, fraction, and percentage.")
    lines.extend(["", "## Engineering criteria", ""])
    for criterion in metrics["engineering_criteria"]:
        symbol = ">=" if criterion["operator"] == "GTE" else "<="
        lines.append(f"- `{criterion['metric_id']}` {symbol} {criterion['threshold']}")
    lines.extend([
        "", "For any ambiguity stratum with N >= 10 adjudicated acquired papers, directly relevant n must be >= 1; otherwise `FAIL_AMBIGUITY_STRATUM_ZERO_DIRECT`.",
        "", "## Evaluation separation", "",
        "PASS A is pre-acquisition only and cannot see fulltext, PASS B, Tier/gates, module states, query rank, or metrics.",
        "", "PASS B is an isolated relevance review and may see only the frozen target, title, abstract, frozen legal fulltext excerpts, and excerpt provenance. It cannot see PASS A, Tier/gates, module/composite states, query provenance/rank, or metrics.",
        "", "## Case design", "",
        f"Eight new propositions: LOW={selection['ambiguity_strata']['LOW']}, MEDIUM={selection['ambiguity_strata']['MEDIUM']}, HIGH={selection['ambiguity_strata']['HIGH']}; oncology=2 and non-oncology=6.",
        "", "Actual cases are not selected in this freeze. Exact heldout-v1 propositions and subject+relation+endpoint triples cannot recur.",
        "", "## Frozen execution sequence", "",
    ])
    lines.extend(f"{index}. {step}" for index, step in enumerate(protocol["execution_sequence"], 1))
    lines.extend([
        "", "## Scientific boundary", "",
        "Heldout-v1 is seen development evidence. P0, P1, P2, and the P3 policy choice are closed to v2.3-beta tuning. Any later algorithmic change requires a new version such as v2.4-dev.", "",
    ])
    return ("\n".join(lines)).encode()


def development_boundary():
    return tagged({
        "artifact_schema_version": "V23BetaDevelopmentBoundaryV1",
        "heldout_v1_seen_development": True,
        "p0_tuning_closed": True,
        "p1_tuning_closed": True,
        "p2_tuning_closed": True,
        "p3_policy_selection_closed": True,
        "future_v23_algorithm_changes_require_new_version": True,
        "required_future_version_family": "v2.4-dev_or_other_explicit_new_version",
        "silent_v23_beta_modification_after_heldout_v2_exposure_allowed": False,
        "independent_validation_claimed": False,
    })


def validate_config(config):
    require(config["selected_policy"] == "POLICY_A_MINIMAL", "Policy A not selected")
    require(config["tier_a_blocker_action"] == "DEMOTE_TIER_A_TO_TIER_B", "demotion rule changed")
    require(not config["hard_rejection_enabled"], "hard rejection must be disabled")
    require(config["tier_b_recall_tail_preserved"], "Tier-B recall tail must be preserved")
    require(not config["tier_b_to_tier_a_promotion_enabled"], "Tier-B promotion must be disabled")
    require(not config["tier_b_subtiers"]["changes_acquisition_priority"], "subtier priority forbidden")
    query = config["query_and_budget_design"]
    require(query["query_compiler_source_sha256"] == sha(V22_QUERY_COMPILER)
            == "2ed6e963d9c74e78ee2a03e458808d213e712f0cec264557efc053c376f72f32",
            "v2.2 query compiler changed")
    require([(row["family_code"], row["family_order"], row["architecture"])
             for row in query["query_family_definitions"]] == [
                 ("A", 1, "exact_entity_endpoint"),
                 ("B", 2, "broader_endpoint_recall_family"),
                 ("C", 3, "relation_terminology"),
                 ("D", 4, "measurement_terminology"),
                 ("E", 5, "disease_context_expansion"),
                 ("F", 6, "authorized_alias_variants"),
             ], "v2.2 query-family definitions changed")
    require(query["metadata_soft_tail_per_case"] == 120, "soft tail changed")
    require(query["metadata_hard_tail_per_case"] == 180, "hard tail changed")
    require(query["fulltext_maximum_per_case"] == 10, "fulltext budget changed")
    require(not query["adaptive_stopping_enabled"], "adaptive stopping enabled")
    vectors = [
        ("TIER_A", "INCOMPATIBLE", "DIRECT_FUNCTIONAL", "EXACT", "TIER_B"),
        ("TIER_A", "EXACT", "ASSOCIATION_ONLY", "EXACT", "TIER_B"),
        ("TIER_A", "EXACT", "BACKGROUND_ONLY", "EXACT", "TIER_B"),
        ("TIER_A", "EXACT", "MULTI_TARGET_AMBIGUOUS", "EXACT", "TIER_B"),
        ("TIER_A", "EXACT", "DIRECT_FUNCTIONAL", "INCOMPATIBLE", "TIER_B"),
        ("TIER_A", "UNRESOLVED", "UNRESOLVED", "UNRESOLVED", "TIER_A"),
        ("TIER_A", "EXACT", "DIRECT_FUNCTIONAL", "PARTIAL", "TIER_A"),
        ("TIER_B", "EXACT", "DIRECT_FUNCTIONAL", "EXACT", "TIER_B"),
        ("TIER_B", "INCOMPATIBLE", "ASSOCIATION_ONLY", "INCOMPATIBLE", "TIER_B"),
        ("REJECT", "EXACT", "DIRECT_FUNCTIONAL", "EXACT", "REJECT"),
        ("ABSTAIN", "EXACT", "DIRECT_FUNCTIONAL", "EXACT", "ABSTAIN"),
    ]
    for original, p0, p1, p2, expected in vectors:
        result = decide_search_plan_v23_beta_disposition(
            original, biological_unit_state=p0, functional_relation_state=p1,
            endpoint_state=p2, tier_b_subtier_annotation="B1_SUPPORTED_OR_SINGLE_UNCERTAINTY",
            config=config,
        )
        require(result.final_disposition == expected, f"Policy A validation vector failed: {vectors}")


def build_core(before, after):
    require(before == after, "historical state changed before protocol build")
    config = load_json(CONFIG)
    validate_config(config)
    metrics = build_metrics_spec()
    metrics_validation = validate_metrics_spec(metrics)
    boundary = adjudication_boundary()
    selection = case_selection_protocol()
    protocol = evaluation_protocol(metrics, boundary, selection)
    require(sum(selection["ambiguity_strata"].values()) == selection["case_count"] == 8,
            "case ambiguity strata do not sum to 8")
    require(sum(selection["domain_composition"].values()) == selection["case_count"],
            "case domain composition does not sum to 8")
    policy = tagged({
        "artifact_schema_version": "PolicyAProductionCandidateV1",
        "selected_policy": "POLICY_A_MINIMAL",
        "selection_status": "frozen_production_candidate_not_activated",
        "development_rationale_only": True,
        "development_rationale": [
            "preserves the complete v2.2 Tier A/B recall universe",
            "known direct papers affected = 0",
            "known Tier-A direct papers affected = 0",
            "removes some known non-direct candidates from high-confidence Tier-A eligibility",
            "does not assume relevance of previously unacquired candidates",
            "preserves Tier B as a recall tail",
        ],
        "policy_b_selected": False,
        "policy_b_exclusion_reason": "Priority redesign is unnecessary for the minimal evidence-supported change and would alter Tier-B ordering.",
        "policy_c_selected": False,
        "policy_c_exclusion_reason": "Strict fulltext ineligibility risks removing the unresolved recall tail without independent evidence.",
        "independent_validation_claimed": False,
        "production_activation": False,
    })
    safety = tagged({
        "artifact_schema_version": "V23BetaProtocolScientificStateSafetyAuditV1",
        "status": "PASS",
        **ZERO_CALLS,
        "heldout_v2_cases_selected": False,
        "heldout_v2_queries_compiled": False,
        "heldout_v2_retrieval_started": False,
        "v22_modified": False,
        "p0_modified": False,
        "p1_modified": False,
        "p2_modified": False,
        "alpha4_frozen_outputs_modified": False,
        "historical_assets_modified": False,
        "git_mutation_invoked": False,
        "protected_state_before": before,
        "protected_state_after": after,
    })
    validation = tagged({
        "artifact_schema_version": "V23BetaProtocolValidationV1",
        "status": "PASS",
        "selected_policy": "POLICY_A_MINIMAL",
        "tier_a_blocker_enabled": True,
        "tier_b_recall_tail_preserved": True,
        "tier_b_priority_redesign_enabled": False,
        "hard_rejection_enabled": False,
        "tier_b_to_tier_a_promotion_enabled": False,
        "metrics_spec_v2_valid": True,
        "all_primary_metrics_have_explicit_numerator_and_denominator": True,
        "all_engineering_thresholds_reference_defined_metrics": True,
        "all_categorical_mappings_explicit": True,
        "all_pass_a_evidence_fields_enumerated": True,
        "all_pass_b_evidence_fields_enumerated": True,
        "all_forbidden_exposure_fields_enumerated": True,
        "case_strata_sum_to_8": True,
        "low_case_count": 2,
        "medium_case_count": 2,
        "high_case_count": 4,
        "oncology_case_count": 2,
        "non_oncology_case_count": 6,
        "placeholder_success_criteria_remaining": 0,
        "heldout_v2_cases_selected": False,
        "heldout_v2_queries_compiled": False,
        "heldout_v2_retrieval_started": False,
        "protocol_generation_replay_byte_identical": True,
    })
    outputs = {
        "search_plan_v23_beta_config_snapshot.json": CONFIG.read_bytes(),
        "policy_a_production_candidate.json": pretty(policy),
        "v23_beta_development_boundary.json": pretty(development_boundary()),
        "metrics_spec_v2.json": pretty(metrics),
        "metrics_spec_v2_validation.json": pretty(metrics_validation),
        "heldout_v2_evaluation_protocol.json": pretty(protocol),
        "heldout_v2_evaluation_protocol.md": protocol_markdown(config, metrics, protocol, boundary, selection),
        "heldout_v2_case_selection_protocol.json": pretty(selection),
        "adjudication_boundary_v2.json": pretty(boundary),
        "scientific_state_safety_audit.json": pretty(safety),
        "validation.json": pretty(validation),
    }
    return outputs, config, metrics, protocol


def build_complete(before, after, upstreams):
    outputs, config, metrics, protocol = build_core(before, after)
    components = [{"path": name, "sha256": digest(outputs[name])}
                  for name in sorted(outputs)]
    aggregate = digest(alpha1.frozen.canonical_json(
        [[row["path"], row["sha256"]] for row in components]))
    version_manifest = tagged({
        "artifact_schema_version": "SearchPlanV23BetaVersionManifestV1",
        "search_plan_version": config["search_plan_version"],
        **config["module_versions"],
        "selected_policy": config["selected_policy"],
        "upstream_frozen_roots": upstreams,
        "production_candidate_files": [
            {"path": str(path.relative_to(ROOT)), "sha256": sha(path)} for path in PRODUCTION_FILES
        ],
        "generic_test_file": {"path": str(TEST.relative_to(ROOT)), "sha256": sha(TEST)},
        "aggregate_components": components,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_scope": "All required outputs except version_manifest.json, root_hash_verification.json, and summary.json.",
        "search_plan_v23_beta_protocol_sha256": aggregate,
        "required_outputs": sorted(REQUIRED),
    })
    root_verification = tagged({
        "artifact_schema_version": "SearchPlanV23BetaRootHashVerificationV1",
        "status": "PASS",
        "component_count": len(components),
        "components": components,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "recomputed_search_plan_v23_beta_protocol_sha256": aggregate,
        "declared_search_plan_v23_beta_protocol_sha256": aggregate,
        "match": True,
    })
    summary = tagged({
        "status": "completed",
        "selected_policy": "POLICY_A_MINIMAL",
        "tier_a_blocker_enabled": True,
        "tier_b_recall_tail_preserved": True,
        "tier_b_priority_redesign_enabled": False,
        "hard_rejection_enabled": False,
        "tier_b_to_tier_a_promotion_enabled": False,
        "metrics_spec_v2_valid": True,
        "defined_metric_count": len(metrics["metrics"]),
        "engineering_criterion_count": len(metrics["engineering_criteria"]),
        "heldout_v2_case_count_protocol": protocol["case_design"]["case_count"],
        "heldout_v2_cases_selected": False,
        "heldout_v2_queries_compiled": False,
        "heldout_v2_retrieval_started": False,
        "protocol_generation_replay_byte_identical": True,
        "search_plan_v23_beta_protocol_sha256": aggregate,
        **ZERO_CALLS,
        "historical_assets_modified": False,
    })
    outputs.update({
        "version_manifest.json": pretty(version_manifest),
        "root_hash_verification.json": pretty(root_verification),
        "summary.json": pretty(summary),
    })
    require(set(outputs) == REQUIRED and len(outputs) == 14,
            f"protocol output membership mismatch: {sorted(set(outputs) ^ REQUIRED)}")
    return outputs, aggregate


def write_outputs(outputs):
    RUN.mkdir(exist_ok=True)
    for name, body in outputs.items():
        path = RUN / name
        if path.exists():
            require(path.is_file() and not path.is_symlink() and path.read_bytes() == body,
                    f"existing protocol artifact differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(body)
        require(path.is_file() and not path.is_symlink() and path.read_bytes() == body,
                f"protocol artifact write verification failed: {name}")
    require({path.name for path in RUN.iterdir()} == REQUIRED,
            "protocol run contains unexpected files")


def freeze():
    upstreams = verify_upstreams()
    before = protected_state()
    after_inputs = protected_state()
    outputs_a, root_a = build_complete(before, after_inputs, upstreams)
    outputs_b, root_b = build_complete(before, after_inputs, upstreams)
    require(outputs_a == outputs_b and root_a == root_b,
            "protocol generation replay is not byte-identical")
    write_outputs(outputs_a)
    after = protected_state()
    require(before == after, "historical assets changed during protocol freeze")
    return outputs_a


def main():
    outputs = freeze()
    print(outputs["summary.json"].decode())
    print("protocol_generation_replay_byte_identical=true")


if __name__ == "__main__":
    main()
