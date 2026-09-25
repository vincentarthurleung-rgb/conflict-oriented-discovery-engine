"""Offline, deterministic search-constraint allocation for validated V3 surfaces.

This compiler creates candidate-generation queries, not scientific judgments.
It never reads retrieval results or creates lexical surfaces.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from itertools import product
from typing import Any

from code_engine.search.retrieval_surface_compiler_v2 import _context_node, _edge_node, _field_scoped, _serialize


class AllocationError(ValueError):
    pass


VERSION = "SearchConstraintAllocationV1"
AST_VERSION = "PubMedQueryASTV2"
CERT_VERSION = "MinimumRelationalRetrievalEvidenceV1"
FAMILY_VERSION = "RelationalQueryFamilyV3"
ALLOCATION = {
    "ACTOR": "SEARCH_INTRINSIC",
    "INTERVENTION_ACTION": "RELATION_INTERNAL_MANDATORY",
    "RELATION_ORIENTATION": "SEARCH_INTRINSIC",
    "RESPONSE_TARGET": "SEARCH_INTRINSIC",
    "DEFINING_ENDPOINT_PROPERTY": "RELATION_INTERNAL_MANDATORY",
    "THERAPY": "RELATION_INTERNAL_MANDATORY",
    "CONDITIONING_TREATMENT": "RELATION_INTERNAL_MANDATORY",
    "BIOLOGICAL_UNIT_CONTEXT": "POST_RETRIEVAL_VALIDATION",
    "ANATOMICAL_REGION_CONTEXT": "POST_RETRIEVAL_VALIDATION",
    "DISEASE_CONTEXT": "POST_RETRIEVAL_VALIDATION",
    "GENOTYPE_CONTEXT": "POST_RETRIEVAL_VALIDATION",
    "SPECIES_CONTEXT": "POST_RETRIEVAL_VALIDATION",
    "TIME_CONTEXT": "POST_RETRIEVAL_VALIDATION",
    "LOCALIZATION_CONTEXT": "POST_RETRIEVAL_VALIDATION",
}
VALIDATOR = {
    "BIOLOGICAL_UNIT_CONTEXT": "P0_BIOLOGICAL_UNIT_COMPATIBILITY",
    "ANATOMICAL_REGION_CONTEXT": "P0_ANATOMICAL_COMPATIBILITY",
    "DISEASE_CONTEXT": "NEUTRAL_FULLTEXT_REVIEW",
    "GENOTYPE_CONTEXT": "NEUTRAL_FULLTEXT_REVIEW",
    "SPECIES_CONTEXT": "NEUTRAL_FULLTEXT_REVIEW",
    "TIME_CONTEXT": "NEUTRAL_FULLTEXT_REVIEW",
    "LOCALIZATION_CONTEXT": "NEUTRAL_FULLTEXT_REVIEW",
}
VARIANT_PRIORITY = ("CORE_RELATION", "ENDPOINT_RELATION_FOCUSED", "CORE_RELATION_PLUS_CONTEXT")
_WORD = re.compile(r"[\w]+(?:[-/][\w]+)*", re.UNICODE)


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _roles(node: dict[str, Any]) -> list[str]:
    kind = node["node_type"]
    if kind in {"AND_GROUP", "OR_GROUP"}:
        return sorted({role for child in node["children"] for role in _roles(child)})
    return list(node.get("semantic_roles", []))


def _walk(node: dict[str, Any]):
    yield node
    if node["node_type"] in {"AND_GROUP", "OR_GROUP"}:
        for child in node["children"]:
            yield from _walk(child)
    elif node["node_type"] == "FIELD_SCOPE":
        yield from _walk(node["child"])
    elif node["node_type"] == "PROXIMITY":
        for anchor in node["anchors"]:
            yield anchor


def _group(role: str, surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    if not surfaces:
        raise AllocationError(f"missing mandatory role {role}")
    nodes = [_field_scoped(surface, role) for surface in surfaces]
    return nodes[0] if len(nodes) == 1 else {
        "node_type": "OR_GROUP", "children": nodes, "semantic_roles": [role]}


def _edge(roles: dict[str, list[dict[str, Any]]], names: tuple[str, ...], edge_type: str) -> dict[str, Any]:
    if any(not roles.get(name) for name in names):
        raise AllocationError(f"missing role in {edge_type}")
    # Existing frozen V2 edge builder preserves surface provenance and its
    # field/window policy. No synonym, query text, or identity is invented.
    return _edge_node([(name, roles[name]) for name in names], edge_type)


def allocation_for_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("artifact_schema_version") != "RetrievalSurfacePlanV1" or plan.get("source_relation_core_state") != "VALID":
        raise AllocationError("requires validated RetrievalSurfacePlanV1")
    roles = plan["surface_roles"]
    required = ["ACTOR", "INTERVENTION_ACTION", "RELATION_ORIENTATION", "RESPONSE_TARGET", "DEFINING_ENDPOINT_PROPERTY"]
    if plan["requirements"]["therapy_required"]:
        required.append("THERAPY")
    if plan["requirements"]["conditioning_required"]:
        required.append("CONDITIONING_TREATMENT")
    if any(not roles.get(role) for role in required):
        raise AllocationError("missing relation-internal or intrinsic role")
    if any(role not in ALLOCATION for role in plan["external_contexts"]):
        raise AllocationError("unresolved external context role")
    if any(not VALIDATOR.get(role) for role in plan["external_contexts"]):
        raise AllocationError("unowned deferred context role")
    deferred = sorted(plan["external_contexts"])
    return {
        "artifact_schema_version": VERSION,
        "source_surface_plan_id": plan["surface_plan_id"],
        "source_relation_core_sha256": plan["source_relation_core_sha256"],
        "source_target_sha256": plan["source_target_sha256"],
        "case_id": plan["case_id"],
        "intent_type": plan["intent_type"],
        "search_required_roles": required,
        "relation_internal_roles": [r for r in required if ALLOCATION[r] == "RELATION_INTERNAL_MANDATORY"],
        "deferred_roles": deferred,
        "variant_eligible_roles": deferred,
        "deferred_validator_owners": {r: VALIDATOR[r] for r in deferred},
        "unowned_deferred_roles": [],
        "role_allocations": {r: ALLOCATION[r] for r in required + deferred},
        "authorized_surface_sha256_by_role": {r: [digest(s) for s in surfaces] for r, surfaces in {**roles, **plan["external_contexts"]}.items() if surfaces},
    }


def _root(plan: dict[str, Any], variant: str) -> dict[str, Any]:
    roles = plan["surface_roles"]
    # One orientation-response relation edge is the search-stage relational
    # evidence. Actor/action is bounded to avoid conflating interventions.
    children = [
        _edge(roles, ("ACTOR", "INTERVENTION_ACTION"), "ACTOR_ACTION"),
        _edge(roles, ("RELATION_ORIENTATION", "RESPONSE_TARGET"), "RELATION_RESPONSE"),
        _group("DEFINING_ENDPOINT_PROPERTY", roles["DEFINING_ENDPOINT_PROPERTY"]),
    ]
    if plan["requirements"]["therapy_required"]:
        children.append(_group("THERAPY", roles["THERAPY"]))
    if plan["requirements"]["conditioning_required"]:
        children.append(_group("CONDITIONING_TREATMENT", roles["CONDITIONING_TREATMENT"]))
    if variant == "ENDPOINT_RELATION_FOCUSED":
        children[1] = _edge(roles, ("RELATION_ORIENTATION", "DEFINING_ENDPOINT_PROPERTY"), "RELATION_ENDPOINT")
        children[2] = _group("RESPONSE_TARGET", roles["RESPONSE_TARGET"])
    if variant == "CORE_RELATION_PLUS_CONTEXT":
        for role, surfaces in sorted(plan["external_contexts"].items()):
            children.append(_context_node(role, surfaces))
    return {"node_type": "AND_GROUP", "children": children}


def _mandatory_sets(root: dict[str, Any]) -> list[list[dict[str, Any]]]:
    """Flatten AND paths while keeping OR alternatives distinct."""
    kind = root["node_type"]
    if kind == "AND_GROUP":
        paths = [[]]
        for child in root["children"]:
            paths = [a + b for a, b in product(paths, _mandatory_sets(child))]
        return paths
    if kind == "OR_GROUP":
        return [p for child in root["children"] for p in _mandatory_sets(child)]
    return [[root]]


def certificate_for_ast(ast: dict[str, Any], allocation: dict[str, Any]) -> dict[str, Any]:
    if ast.get("artifact_schema_version") != AST_VERSION or not ast.get("source_validated"):
        raise AllocationError("unvalidated query-family AST")
    if ast.get("source_surface_plan_id") != allocation["source_surface_plan_id"]:
        raise AllocationError("allocation/AST provenance mismatch")
    if ast.get("source_relation_core_sha256") != allocation["source_relation_core_sha256"]:
        raise AllocationError("relation-core provenance mismatch")
    if ast.get("deferred_validation_roles") != allocation["deferred_roles"] or ast.get("deferred_validator_owners") != allocation["deferred_validator_owners"]:
        raise AllocationError("deferred-role ownership mismatch")
    if ast.get("raw_planner_text_accepted_by_serializer") or ast.get("ast_sha256") != digest({k: v for k, v in ast.items() if k != "ast_sha256"}):
        raise AllocationError("AST integrity failure")
    if ast.get("variant_class") not in VARIANT_PRIORITY or ast["root"].get("node_type") != "AND_GROUP":
        raise AllocationError("invalid query-family variant or root")
    allowed_refs = ast.get("role_provenance", {})
    for node in _walk(ast["root"]):
        kind = node.get("node_type")
        if kind == "PROXIMITY":
            if node.get("window_n") != 5 or node.get("field") != "Title/Abstract" or not node.get("anchors"):
                raise AllocationError("invalid bounded relation edge")
            actual_roles = sorted({r for anchor in node["anchors"] for r in anchor.get("semantic_roles", [])})
            if sorted(node.get("semantic_roles", [])) != actual_roles:
                raise AllocationError("fabricated proximity role labels")
            if node.get("edge_type") == "ACTOR_ACTION" and actual_roles != ["ACTOR", "INTERVENTION_ACTION"]:
                raise AllocationError("invalid actor/action edge")
            if node.get("edge_type") == "RELATION_RESPONSE" and actual_roles != ["RELATION_ORIENTATION", "RESPONSE_TARGET"]:
                raise AllocationError("invalid relation/response edge")
            if node.get("edge_type") == "RELATION_ENDPOINT" and actual_roles != ["DEFINING_ENDPOINT_PROPERTY", "RELATION_ORIENTATION"]:
                raise AllocationError("invalid relation/endpoint edge")
        elif kind in {"TERM", "COMPACT_CONCEPT"}:
            prov = node.get("surface_provenance", {})
            if prov.get("text") != node.get("surface") or prov.get("canonical_identity_promoted") is not False:
                raise AllocationError("invalid anchor provenance")
            if any(prov.get("source_ref") not in allowed_refs.get(role, []) for role in node.get("semantic_roles", [])):
                raise AllocationError("unapproved anchor source reference")
            if any(digest(prov) not in allocation["authorized_surface_sha256_by_role"].get(role, []) for role in node.get("semantic_roles", [])):
                raise AllocationError("anchor surface differs from frozen plan")
    paths = _mandatory_sets(ast["root"])
    if not paths:
        raise AllocationError("empty query")
    required = set(allocation["search_required_roles"])
    for path in paths:
        roles = {role for node in path for role in _roles(node)}
        if not required.issubset(roles):
            raise AllocationError(f"missing mandatory roles {sorted(required - roles)}")
        relation = [n for n in path if n["node_type"] == "PROXIMITY" and n.get("edge_type") in {"RELATION_RESPONSE", "RELATION_ENDPOINT"}]
        if not relation or not all("RELATION_ORIENTATION" in _roles(n) for n in relation):
            raise AllocationError("topic intersection without relation-bearing constraint")
        actor_action = [n for n in path if n["node_type"] == "PROXIMITY" and n.get("edge_type") == "ACTOR_ACTION"]
        if not actor_action or not all({"ACTOR", "INTERVENTION_ACTION"}.issubset(_roles(n)) for n in actor_action):
            raise AllocationError("actor/action not structurally bound")
    return {
        "artifact_schema_version": CERT_VERSION,
        "query_ast_sha256": ast["ast_sha256"],
        "source_surface_plan_id": ast["source_surface_plan_id"],
        "all_paths_certified": True,
        "relation_mechanism": "BOUNDED_ORIENTATION_RESPONSE_OR_ENDPOINT_PROXIMITY",
        "search_required_roles": allocation["search_required_roles"],
        "relation_internal_roles": allocation["relation_internal_roles"],
        "deferred_validator_owners": allocation["deferred_validator_owners"],
        "unowned_deferred_scientific_role_count": 0,
        "search_relation_evidence_is_scientific_proof": False,
    }


def serialize_validated_ast(ast: dict[str, Any], allocation: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    cert = certificate_for_ast(ast, allocation)
    query = _serialize(ast["root"], root=True)
    if not query:
        raise AllocationError("empty serialization")
    return query, cert


def compile_family(plan: dict[str, Any]) -> dict[str, Any]:
    allocation = allocation_for_plan(plan)
    variants = ["CORE_RELATION"]
    if plan["intent_type"] == "ENDPOINT_SPECIFIC":
        variants.append("ENDPOINT_RELATION_FOCUSED")
    if plan["external_contexts"]:
        variants.append("CORE_RELATION_PLUS_CONTEXT")
    variants.sort(key=VARIANT_PRIORITY.index)
    if len(variants) > 3:
        raise AllocationError("family budget exceeded")
    members = []
    for variant in variants:
        ast = {
            "artifact_schema_version": AST_VERSION,
            "family_version": FAMILY_VERSION,
            "variant_class": variant,
            "root": _root(plan, variant),
            "source_surface_plan_id": plan["surface_plan_id"],
            "source_relation_core_sha256": plan["source_relation_core_sha256"],
            "source_validated": True,
            "raw_planner_text_accepted_by_serializer": False,
            "role_provenance": {r: [s["source_ref"] for s in surfaces] for r, surfaces in {**plan["surface_roles"], **plan["external_contexts"]}.items() if surfaces},
            "deferred_validation_roles": allocation["deferred_roles"],
            "deferred_validator_owners": allocation["deferred_validator_owners"],
        }
        ast["ast_sha256"] = digest(ast)
        query, cert = serialize_validated_ast(ast, allocation)
        members.append({"variant_class": variant, "ast": ast, "query": query, "certificate": cert})
    return {"artifact_schema_version": FAMILY_VERSION, "case_id": plan["case_id"], "intent_type": plan["intent_type"], "surface_plan_id": plan["surface_plan_id"], "allocation": allocation, "members": members}


def burden(ast: dict[str, Any]) -> dict[str, Any]:
    paths = _mandatory_sets(ast["root"])
    path_atoms = []
    path_counts = []
    for path in paths:
        anchors = [a for node in path for a in _walk(node) if a["node_type"] in {"TERM", "COMPACT_CONCEPT"}]
        path_atoms.append({t.lower() for a in anchors for t in _WORD.findall(a["surface"])})
        path_counts.append(Counter(role for a in anchors for role in a["semantic_roles"]))
    lexical_atoms = set.intersection(*path_atoms)
    counts = Counter({role: min(c[role] for c in path_counts) for role in set().union(*(set(c) for c in path_counts))})
    counts = +counts
    external = set(ast["deferred_validation_roles"])
    return {
        "mandatory_unique_lexical_atom_count": len(lexical_atoms),
        "mandatory_semantic_role_count": len(counts),
        "top_level_and_child_count": len(ast["root"]["children"]),
        "repeated_mandatory_roles": sorted(r for r, n in counts.items() if n > 1),
        "mandatory_external_context_roles": sorted(external & set(counts)),
        "relation_bearing": True,
    }
