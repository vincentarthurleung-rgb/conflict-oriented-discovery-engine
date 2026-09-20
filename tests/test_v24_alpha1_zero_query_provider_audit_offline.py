"""Frozen output checks for the read-only alpha1 coverage/provider autopsy."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha1_zero_query_autopsy_and_provider_audit_offline"


def read(name: str):
    return json.loads((RUN / name).read_text())


def test_exact_output_membership_and_root():
    expected = {
        "upstream_root_verification.json", "alpha1_nonexecutable_blueprint_decomposition.jsonl",
        "alpha1_stage_attribution_summary.json", "unresolved_term_diagnostic.json",
        "unresolved_term_diagnostic_summary.json", "positive_case_control_analysis.json",
        "relation_binding_false_negative_audit.json", "search_only_eligibility_false_negative_audit.json",
        "next_component_recommendation.json", "llm_provider_callsite_inventory.json",
        "deepseek_provider_configuration_audit.json", "openai_to_deepseek_migration_plan.json",
        "historical_provider_provenance_audit.json", "heldout_specific_rule_audit.json",
        "scientific_state_safety_audit.json", "validation.json", "summary.json",
        "search_plan_v24_alpha1_zero_query_autopsy_sha256",
        *(f"case_{case}_zero_query_autopsy.md" for case in (101, 102, 103, 104, 106)),
    }
    assert {p.name for p in RUN.iterdir()} == expected
    manifest = read("validation.json")
    pairs = manifest["aggregate_components"]
    assert len(pairs) == 21
    assert all(hashlib.sha256((RUN / name).read_bytes()).hexdigest() == digest for name, digest in pairs)
    root = hashlib.sha256(json.dumps(pairs, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    assert root == manifest["search_plan_v24_alpha1_zero_query_autopsy_sha256"]
    assert root == (RUN / "search_plan_v24_alpha1_zero_query_autopsy_sha256").read_text().strip()


def test_stage_attribution_and_case_106_false_negative():
    rows = [json.loads(line) for line in (RUN / "alpha1_nonexecutable_blueprint_decomposition.jsonl").read_text().splitlines()]
    assert len(rows) == 17
    assert len({(x["case_id"], x["blueprint_id"]) for x in rows}) == 17
    assert Counter(x["first_loss_stage"] for x in rows) == {
        "PLANNER_DID_NOT_PROPOSE": 12,
        "PLANNER_PROPOSED_BUT_VALIDATOR_WITHHELD": 5,
    }
    case106 = [x for x in rows if x["case_id"] == "heldout_v2_106"]
    assert len(case106) == 4
    assert all(x["deterministic_post_planner_false_negative"] for x in case106)
    assert all(x["binding_predicates"]["nested_treatment_bound"] for x in case106)
    case105 = [x for x in rows if x["case_id"] == "heldout_v2_105"]
    assert len(case105) == 1
    assert not case105[0]["deterministic_post_planner_false_negative"]
    assert read("summary.json")["zero_query_case_count"] == 5


def test_unresolved_diagnostics_are_not_authority():
    report = read("unresolved_term_diagnostic.json")
    rows = report["terms"]
    assert len(rows) == 328
    assert all(x["alpha1_classification_unchanged"] == "UNRESOLVED" for x in rows)
    assert all(x["diagnostic_not_executable_authority"] for x in rows)
    summary = read("unresolved_term_diagnostic_summary.json")
    assert sum(summary["category_counts"].values()) == 328
    assert summary["plausible_missing_generic_eligibility_count"] == 89
    assert summary["correctly_withheld_term_count"] == 130


def test_provider_migration_is_plan_only_and_literature_api_is_separate():
    inventory = read("llm_provider_callsite_inventory.json")
    counts = Counter(x["classification"] for x in inventory["entries"])
    assert counts["OPENAI_REQUIRES_MIGRATION"] == 2
    assert counts["HISTORICAL_FROZEN_OPENAI_DO_NOT_MODIFY"] == 3
    assert counts["NON_LLM_EXTERNAL_API"] == 23
    assert inventory["tests_or_fixtures_with_openai_names"]
    assert read("openai_to_deepseek_migration_plan.json")["implementation_deferred"]
    assert not read("historical_provider_provenance_audit.json")["historical_provider_provenance_rewritten"]
    safety = read("scientific_state_safety_audit.json")
    assert safety["protected_hashes_before"] == safety["protected_hashes_after"]
    assert safety["provider_calls"] == safety["network_calls"] == 0
