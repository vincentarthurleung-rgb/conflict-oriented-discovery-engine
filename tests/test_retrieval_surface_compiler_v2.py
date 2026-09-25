from copy import deepcopy

import pytest

from code_engine.search.retrieval_surface_compiler_v2 import (
    RetrievalSurfaceCompilerError, build_retrieval_surface_plan,
    compile_surface_plan, lint_query_serialization, serialize_pubmed_query,
)


def frame(*, therapy=False, conditioning=False):
    return {
        "target_sha256": "target-hash",
        "therapy_applicability": "REQUIRED" if therapy else "NOT_APPLICABLE",
        "conditioning_treatment_applicability": (
            "REQUIRED" if conditioning else "NOT_APPLICABLE"),
        "role_surfaces": {
            "PRIMARY_INTERVENTION": ["TARGET"],
            "PRIMARY_INTERVENTION_ACTION": ["TARGET inhibition"],
            "RESPONSE_TARGET": ["RESPONSE"],
            "RESPONSE_PROPERTY": ["measured endpoint"],
            "THERAPY": ["DRUG"] if therapy else [],
            "CONDITIONING_TREATMENT": ["CONDITION"] if conditioning else [],
            "BIOLOGICAL_UNIT_CONTEXT": ["test cell"],
            "DISEASE_CONTEXT": [],
            "GENOTYPE_CONTEXT": [],
        },
    }


def link(*, therapy=False, conditioning=False):
    return {
        "subject_surface": "TARGET inhibition",
        "subject_action_surface": "inhibits TARGET",
        "relation_surface": "increases",
        "direction": "INCREASE",
        "response_surface": "RESPONSE",
        "endpoint_property_surface": "measured endpoint",
        "therapy_surface": "DRUG" if therapy else None,
        "conditioning_treatment_surface": "CONDITION" if conditioning else None,
    }


def binding():
    return {
        "state": "STRUCTURALLY_BOUND",
        "canonical_identity_promoted": False,
        "relation_core": {
            "state": "VALID",
            "response_orientation_evidence": {
                "typed_direction": "INCREASE",
                "response_relation_evidence": [{
                    "token": "increases", "normalized_semantic": "UP",
                    "source_field": "relation_surface",
                }],
            },
        },
        "query_context_constraints": {
            "constraints": [{
                "role": "BIOLOGICAL_UNIT_CONTEXT", "required": True,
                "state": "COMPATIBLE", "surface": "test cell",
            }],
        },
    }


def compiled(*, therapy=False, conditioning=False):
    plan = build_retrieval_surface_plan(
        case_id="fixture", intent_type="DIRECT_PERTURBATION",
        source_link_sha256="relation-hash", link=link(therapy=therapy, conditioning=conditioning),
        binding=binding(), target_role_frame=frame(therapy=therapy, conditioning=conditioning))
    return compile_surface_plan(plan)


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)
    if "child" in node:
        yield from walk(node["child"])
    for anchor in node.get("anchors", []):
        yield from walk(anchor)


def test_relation_is_decomposed_into_small_proximity_edges():
    result = compiled()
    query = result["serialized_query"]
    assert "complete scientific proposition" not in query
    assert "[Title/Abstract:~5]" in query
    assert '"test cell"[Title/Abstract:~0]' in query
    proximity = [node for node in walk(result["ast"]["root"])
                 if node.get("node_type") == "PROXIMITY"]
    assert {node["edge_type"] for node in proximity} == {
        "ACTOR_ACTION_RELATION", "RELATION_RESPONSE", "RESPONSE_ENDPOINT"}
    assert max(len(node["semantic_roles"]) for node in proximity) == 3
    assert result["certificate"]["state"] == "CERTIFIED"
    assert result["linter"]["state"] == "PASS"


def test_identical_plan_serializes_byte_identically():
    first = compiled()
    second = compiled()
    assert first["ast"] == second["ast"]
    assert first["serialized_query"].encode() == second["serialized_query"].encode()
    assert first["query_sha256"] == second["query_sha256"]


def test_therapy_and_conditioning_remain_internal_edges():
    result = compiled(therapy=True, conditioning=True)
    edge_types = {edge["edge_type"] for edge in result["relation_edges"]}
    assert "THERAPY_RESPONSE_PROPERTY" in edge_types
    assert "CONDITIONING_NESTED_RESPONSE" in edge_types
    assert result["coverage"]["flags"]["therapy_covered_when_required"]
    assert result["coverage"]["flags"]["conditioning_covered_when_required"]


def test_serializer_rejects_relation_core_or_raw_text():
    with pytest.raises(RetrievalSurfaceCompilerError):
        serialize_pubmed_query({"state": "VALID", "linked_relation_phrase": "raw text"})


def test_linter_rejects_more_than_three_roles_in_proximity():
    result = compiled()
    ast = deepcopy(result["ast"])
    node = next(node for node in walk(ast["root"])
                if node.get("node_type") == "PROXIMITY")
    node["semantic_roles"].extend(["THERAPY", "CONTEXT"])
    audit = lint_query_serialization(ast, result["surface_plan"], result["certificate"])
    assert audit["state"] == "REJECT"
    assert "PROXIMITY_ROLE_COUNT_EXCEEDED" in audit["errors"]


def test_linter_rejects_wildcard_inside_proximity():
    result = compiled()
    ast = deepcopy(result["ast"])
    node = next(node for node in walk(ast["root"])
                if node.get("node_type") == "PROXIMITY")
    node["anchors"][0]["surface"] += "*"
    audit = lint_query_serialization(ast, result["surface_plan"], result["certificate"])
    assert audit["state"] == "REJECT"
    assert "WILDCARD_INSIDE_PROXIMITY" in audit["errors"]


def test_topic_bag_without_relation_edge_is_non_executable():
    result = compiled()
    ast = deepcopy(result["ast"])
    for node in walk(ast["root"]):
        if node.get("node_type") == "PROXIMITY":
            node["edge_type"] = "TOPIC_BAG"
    audit = lint_query_serialization(ast, result["surface_plan"], result["certificate"])
    assert audit["state"] == "REJECT"
    assert "CONTEXT_ONLY_OR_TOPIC_BAG_QUERY" in audit["errors"]


def test_missing_required_therapy_fails_closed():
    value = frame(therapy=True)
    value["role_surfaces"]["THERAPY"] = []
    value_link = link(therapy=True)
    value_link["therapy_surface"] = None
    with pytest.raises(RetrievalSurfaceCompilerError, match="therapy"):
        build_retrieval_surface_plan(
            case_id="fixture", intent_type="THERAPY_SENSITIZATION",
            source_link_sha256="relation-hash", link=value_link,
            binding=binding(), target_role_frame=value)


def test_intent_specific_endpoint_does_not_merge_opposite_target_alternative():
    value_frame = frame()
    value_frame["role_surfaces"]["RESPONSE_PROPERTY"] = ["opposite orientation"]
    value_link = link()
    value_link["endpoint_property_surface"] = "intent specific endpoint"
    plan = build_retrieval_surface_plan(
        case_id="fixture", intent_type="NECESSITY",
        source_link_sha256="relation-hash", link=value_link,
        binding=binding(), target_role_frame=value_frame)
    assert [row["text"] for row in plan["surface_roles"]["DEFINING_ENDPOINT_PROPERTY"]] == [
        "intent specific endpoint"]
