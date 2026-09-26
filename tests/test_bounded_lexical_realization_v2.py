import json
from collections import defaultdict
from pathlib import Path

import pytest

from code_engine.search.bounded_lexical_realization_v2 import (
    LexicalRealizationError, alternatives_for, lexicalize_family, morphology_for,
)
from code_engine.search.search_constraint_allocation_v1 import compile_family
from scripts.search_plan_v24_alpha311_offline import reconcile, verify_roots


ROOT = Path(__file__).resolve().parents[1]
PLANS = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_6_retrieval_surface_compiler_v2_offline/empirical_v3_to_surface_plan.jsonl"


def plans():
    return [json.loads(line) for line in PLANS.read_text().splitlines()]


def test_frozen_source_and_projection_payloads_reconcile_without_content_review():
    assert len(verify_roots()) == 7
    audit, components, _, binding = reconcile()
    assert audit["scientific_payload_equivalent"]
    assert audit["raw_ncbi_response_count"] == 57
    assert all(item["equivalent"] for item in components["components"])
    assert binding["canonical_search_constraint_allocation_v1_scientific_corpus_sha256"]


def test_entity_identity_and_endpoint_distinctions_are_not_expanded():
    for role, surface in (
        ("ACTOR", "TNF"), ("RESPONSE_TARGET", "RPTOR"),
        ("DEFINING_ENDPOINT_PROPERTY", "autophagic flux"),
        ("DEFINING_ENDPOINT_PROPERTY", "cell-surface protein expression"),
        ("DEFINING_ENDPOINT_PROPERTY", "sensitivity to trametinib"),
    ):
        assert morphology_for(role, surface) == ()
    assert morphology_for("RELATION_ORIENTATION", "increases") == (
        "increase", "increased", "increasing")
    assert morphology_for("RELATION_ORIENTATION", "decreases") == (
        "decrease", "decreased", "decreasing")


def test_unknown_or_identity_promoting_surface_fails_closed():
    plan = plans()[0]
    bad = dict(plan["surface_roles"]["ACTOR"][0], origin="UNVALIDATED_ALIAS")
    with pytest.raises(LexicalRealizationError):
        alternatives_for(plan, "ACTOR", [bad])
    bad = dict(plan["surface_roles"]["ACTOR"][0], canonical_identity_promoted=True)
    with pytest.raises(LexicalRealizationError):
        alternatives_for(plan, "ACTOR", [bad])


def test_all_frozen_families_keep_semantic_roles_and_query_budget():
    per_case = defaultdict(set)
    contribution_count = 0
    for plan in plans():
        family = lexicalize_family(plan)
        old = compile_family(plan)
        assert family["allocation"] == old["allocation"]
        assert [m["variant_class"] for m in family["members"]] == [m["variant_class"] for m in old["members"]]
        for new, previous in zip(family["members"], old["members"]):
            contribution_count += 1
            per_case[plan["case_id"]].add(new["query"].encode())
            assert new["certificate"]["all_paths_certified"]
            assert new["certificate"]["search_required_roles"] == previous["certificate"]["search_required_roles"]
            assert new["certificate"]["relation_internal_roles"] == previous["certificate"]["relation_internal_roles"]
            assert new["lexical_coverage_certificate"]["identity_safety_result"] == "PASS"
            assert new["lexical_coverage_certificate"]["semantic_broadening_result"] == "PASS"
    assert contribution_count == 63
    assert sum(map(len, per_case.values())) == 55
    assert all(len(queries) <= 12 for queries in per_case.values())
