"""Offline safety and deterministic replay checks for v2.4-dev alpha1."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

import pytest

from code_engine.search.alpha1_relation_searchonly_v1 import (
    Alpha1BoundaryError, alpha1_receipts, compile_alpha1,
    relation_event_and_binding, semantic_eligibility,
)
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value

ROOT = Path(__file__).resolve().parents[1]
PLANS = ROOT / "runs/20260918_search_plan_v24_dev_planner_authority_contract_split_offline/validated_development_plans.jsonl"
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha1_relation_searchonly_refinement_offline"


def plans():
    return {row["case_id"]: row["validated_plan"] for row in
            (json.loads(line) for line in PLANS.read_text().splitlines() if line)}


def replay(plan):
    receipts = alpha1_receipts(plan)
    events, binding, coverage = relation_event_and_binding(plan, receipts)
    queries = compile_alpha1(plan, receipts, binding, coverage)
    return receipts, events, binding, coverage, queries


def test_exact_frozen_corpus_and_transition():
    all_plans = plans()
    assert len(all_plans) == 8
    old = Counter()
    new = Counter()
    for plan in all_plans.values():
        receipts, _, _, _, _ = replay(plan)
        old.update(r["deterministic_classification"] for r in plan["term_validation_receipts"])
        new.update(r["final_authority_classification"] for r in receipts)
        assert [r["term_id"] for r in receipts] == [r["term_id"] for r in plan["term_validation_receipts"]]
        assert all(r["old_receipt_sha256"] == o["receipt_sha256"] for r, o in zip(receipts, plan["term_validation_receipts"]))
    assert old == {"AUTHORIZED_EQUIVALENT": 105, "SEARCH_ONLY_EXPANSION": 469}
    assert new == {"AUTHORIZED_EQUIVALENT": 105, "SEARCH_ONLY_EXPANSION": 141, "UNRESOLVED": 328}


def test_generic_default_deny_entity_and_biological_broadening():
    all_plans = plans()
    t101 = all_plans["heldout_v2_101"]["canonical_proposition"]["target_payload"]
    t103 = all_plans["heldout_v2_103"]["canonical_proposition"]["target_payload"]
    t105 = all_plans["heldout_v2_105"]["canonical_proposition"]["target_payload"]
    assert semantic_eligibility("keratinocytes", "biological_unit", t101)[0] == "DENIED"
    assert semantic_eligibility("intestinal crypt", "biological_unit", t103)[0] == "DENIED"
    assert semantic_eligibility("RPTOR", "subject", t105)[0] == "DENIED"
    assert semantic_eligibility("mTORC1 component depletion enhances autophagic flux", "relation", t105)[0] == "DENIED"
    assert semantic_eligibility("unrelated safe-looking pathway", "subject", t101)[0] == "DENIED"
    assert semantic_eligibility("EGF increases ERK phosphorylation", "relation", t101)[0] == "DENIED"
    assert semantic_eligibility("increases", "relation", t101)[0] == "DENIED"


def test_nested_treatment_and_dynamic_endpoint_event_frame():
    all_plans = plans()
    _, events106, binding106, _, queries106 = replay(all_plans["heldout_v2_106"])
    assert all(e["nested_treatment_context"] for e in events106)
    assert all(e["semantic_roles"]["CONDITIONING_CONTEXT"] for e in events106)
    assert all(e["subject_concept_id"] and e["measurement_target_concept_id"] for e in events106)
    assert not queries106
    assert all(b["compiler_action"] == "NON_EXECUTABLE_RELATION_UNDERREPRESENTED" for b in binding106)
    _, events105, binding105, _, queries105 = replay(all_plans["heldout_v2_105"])
    assert len(queries105) == 2
    assert all(e["endpoint_property"] == "dynamic autophagic degradation / flux" for e in events105)
    assert all(b["dynamic_endpoint_bound"] for b in binding105)
    assert any(b["compiler_action"] == "NON_EXECUTABLE_RELATION_UNDERREPRESENTED" for b in binding105)


def test_therapy_binding_and_coverage_v1_1():
    for case in ("heldout_v2_107", "heldout_v2_108"):
        _, events, binding, coverage, queries = replay(plans()[case])
        assert queries
        assert all(e["response_role"] == "THERAPY_RESPONSE" for e in events)
        assert all(e["therapy_context"] for e in events)
        assert all(b["therapy_response_bound"] for b in binding)
        by_id = {x["blueprint_id"]: x for x in binding}
        for c in coverage:
            relation = next(x for x in c["dimension_coverage"] if x["dimension"] == "relation")
            assert (relation["coverage_state"] == "REPRESENTED") == (by_id[c["blueprint_id"]]["state"] == "STRUCTURALLY_BOUND")


def test_compiler_fail_closed_and_executable_term_boundary():
    plan = plans()["heldout_v2_107"]
    receipts, _, binding, coverage, queries = replay(plan)
    assert queries
    for q in queries:
        assert q["relation_binding_state"] == "STRUCTURALLY_BOUND"
        assert q["execution_status"] == "NOT_EXECUTED_DEVELOPMENT_ALPHA1"
        for group in q["ordered_term_groups"]:
            assert all(t["classification"] in {"AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION"} for t in group["terms"])
            assert all(t["eligibility_rule_id"] for t in group["terms"])
    bad = [dict(x) for x in receipts]
    bad[0]["final_authority_classification"] = "REJECTED"
    with pytest.raises(Alpha1BoundaryError):
        compile_alpha1(plan, bad, binding, coverage)


def test_frozen_run_reproducible_and_no_topic_only_queries():
    run_summary = json.loads((RUN / "summary.json").read_text())
    stored = [json.loads(line) for line in (RUN / "alpha1_compiled_queries.jsonl").read_text().splitlines()]
    current = []
    for case, plan in plans().items():
        current.extend({"case_id": case, **q} for q in replay(plan)[4])
    assert sha256_value(current) == sha256_value(stored)
    assert len(stored) == run_summary["alpha1_compiled_query_count"] == 9
    assert run_summary["topic_intersection_risk_query_count"] == 0
    assert run_summary["provider_calls"] == run_summary["retrieval_calls"] == 0
