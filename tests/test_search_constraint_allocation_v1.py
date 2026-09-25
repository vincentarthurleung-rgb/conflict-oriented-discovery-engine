import copy
import json
from pathlib import Path

import pytest

from code_engine.search.search_constraint_allocation_v1 import (
    AllocationError, burden, certificate_for_ast, compile_family, digest,
    serialize_validated_ast,
)
from code_engine.search.retrieval_surface_compiler_v2 import _field_scoped


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_6_retrieval_surface_compiler_v2_offline/empirical_v3_to_surface_plan.jsonl"
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_9_search_constraint_allocation_offline"


def plans():
    return [json.loads(line) for line in SOURCE.read_text().splitlines()]


def test_all_frozen_intents_have_safe_context_free_core_and_bounded_family():
    families = [compile_family(p) for p in plans()]
    assert len(families) == 29
    assert len({f["case_id"] for f in families}) == 8
    per_case = {}
    for family in families:
        assert 1 <= len(family["members"]) <= 3
        assert family["members"][0]["variant_class"] == "CORE_RELATION"
        assert burden(family["members"][0]["ast"])["mandatory_external_context_roles"] == []
        assert family["allocation"]["unowned_deferred_roles"] == []
        for member in family["members"]:
            assert member["certificate"]["all_paths_certified"]
            assert member["certificate"]["search_relation_evidence_is_scientific_proof"] is False
            assert serialize_validated_ast(member["ast"], family["allocation"])[0] == member["query"]
            per_case.setdefault(family["case_id"], set()).add(member["query"].encode())
    assert all(len(queries) <= 12 for queries in per_case.values())


def test_internal_roles_cannot_be_removed():
    for plan in plans():
        family = compile_family(plan)
        required = family["allocation"]["relation_internal_roles"]
        for role in required:
            assert role in family["members"][0]["certificate"]["search_required_roles"]
        if plan["requirements"]["therapy_required"]:
            assert "THERAPY" in required
        if plan["requirements"]["conditioning_required"]:
            assert "CONDITIONING_TREATMENT" in required
        assert "DEFINING_ENDPOINT_PROPERTY" in required


def test_topic_intersection_and_tampered_ast_fail_closed():
    family = compile_family(plans()[0])
    ast = family["members"][0]["ast"]
    allocation = family["allocation"]
    for delete_index in (0, 1):
        bad = copy.deepcopy(ast)
        del bad["root"]["children"][delete_index]
        bad["ast_sha256"] = digest({k: v for k, v in bad.items() if k != "ast_sha256"})
        with pytest.raises(AllocationError):
            certificate_for_ast(bad, allocation)
    bad = copy.deepcopy(ast)
    bad["root"]["children"][1]["edge_type"] = "RELATION_RESPONSE"
    bad["root"]["children"][1]["anchors"][0]["surface"] = "invented"
    bad["ast_sha256"] = digest({k: v for k, v in bad.items() if k != "ast_sha256"})
    with pytest.raises(AllocationError):
        serialize_validated_ast(bad, allocation)
    # Even every required word as a top-level topic intersection is insufficient.
    plan = plans()[0]
    bad = copy.deepcopy(ast)
    bad["root"]["children"] = [_field_scoped(plan["surface_roles"][role][0], role) for role in allocation["search_required_roles"]]
    bad["ast_sha256"] = digest({k: v for k, v in bad.items() if k != "ast_sha256"})
    with pytest.raises(AllocationError, match="topic intersection"):
        certificate_for_ast(bad, allocation)


def test_frozen_query_set_matches_recompilation():
    frozen = [json.loads(line) for line in (RUN / "search_plan_v24_dev_search_constraint_allocation_v1_query_set.jsonl").read_text().splitlines()]
    generated = {}
    for plan in plans():
        family = compile_family(plan)
        for member in family["members"]:
            generated.setdefault(plan["case_id"], set()).add(member["query"])
    assert len(frozen) == 55
    assert {(r["case_id"], r["query"]) for r in frozen} == {(case, query) for case, queries in generated.items() for query in queries}
