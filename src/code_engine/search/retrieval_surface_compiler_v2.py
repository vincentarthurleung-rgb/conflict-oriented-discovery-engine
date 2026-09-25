"""Deterministic retrieval-surface planning and PubMed AST serialization.

This module deliberately sits downstream of validated Planner V3 relation
bindings.  It cannot validate scientific identity and it never accepts a raw
natural-language proposition at the serializer boundary.
"""

from __future__ import annotations

from itertools import product
import hashlib
import json
import re
from typing import Any, Iterable


SURFACE_PLAN_VERSION = "RetrievalSurfacePlanV1"
RELATION_EDGE_VERSION = "RelationEdgeV1"
COVERAGE_VERSION = "RetrievalSurfaceCoverageV1"
CERTIFICATE_VERSION = "RelationSerializationCertificateV1"
AST_VERSION = "PubMedQueryASTV1"
SYNTAX_VERSION = "PubMedSyntaxContractV1"
SERIALIZER_VERSION = "PubMedQuerySerializerV2"
LINTER_VERSION = "QuerySerializationSafetyLinterV1"

COMPACT_CONCEPT_WINDOW_N = 0
RELATION_EDGE_WINDOW_N = 5
MAX_PROXIMITY_ROLE_ANCHORS = 3
MAX_SURFACE_ALTERNATIVES_PER_ROLE = 2
MAX_SURFACE_VARIANTS_PER_VALIDATED_INTENT = 2
MAX_QUERIES_PER_TARGET = 12

_INVALID_SURFACE = re.compile(r'["\[\]*]')
_MULTISPACE = re.compile(r"\s+")
_ALTERNATIVE = re.compile(r"\s+(?:or)\s+|\s+/\s+", re.I)
_TOKEN = re.compile(r"[A-Za-z0-9α-ωΑ-Ω]+(?:[-/][A-Za-z0-9α-ωΑ-Ω]+)*")


class RetrievalSurfaceCompilerError(ValueError):
    """Raised when a validated relation cannot be serialized safely."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def value_sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for raw in values:
        value = _MULTISPACE.sub(" ", str(raw).strip().strip(".,;:"))
        if not value or value.casefold() in seen:
            continue
        if _INVALID_SURFACE.search(value):
            raise RetrievalSurfaceCompilerError(f"unsafe lexical surface: {value!r}")
        seen.add(value.casefold())
        result.append(value)
    return result


def _split_surface(value: str | None) -> list[str]:
    if not value:
        return []
    return _unique(_ALTERNATIVE.split(value))


def _contains_actor(surface: str, actor: str) -> bool:
    return actor.casefold() in surface.casefold()


def _elide_actor(surface: str, actors: list[str]) -> str:
    result = surface
    for actor in sorted(actors, key=len, reverse=True):
        result = re.sub(re.escape(actor), " ", result, flags=re.I)
    return _MULTISPACE.sub(" ", result).strip(" -.,;:")


def _surface(text: str, role: str, *, origin: str, authority: str,
             source_ref: str, retrieval_only: bool) -> dict[str, Any]:
    if not text or _INVALID_SURFACE.search(text):
        raise RetrievalSurfaceCompilerError(f"invalid {role} surface")
    return {
        "text": text,
        "semantic_role": role,
        "origin": origin,
        "authority": authority,
        "source_ref": source_ref,
        "retrieval_only": retrieval_only,
        "canonical_identity_promoted": False,
    }


def _canonical_surfaces(frame: dict[str, Any], role: str, source_ref: str) -> list[dict[str, Any]]:
    values = _unique(frame["role_surfaces"].get(role, []))[:MAX_SURFACE_ALTERNATIVES_PER_ROLE]
    return [_surface(value, role, origin="CANONICAL_TARGET_SURFACE",
                     authority="IMMUTABLE_SCIENTIFIC_PROPOSITION_TARGET",
                     source_ref=source_ref, retrieval_only=False) for value in values]


def _relation_terms(binding: dict[str, Any], source_ref: str) -> list[dict[str, Any]]:
    core = binding["relation_core"]
    evidence = core["response_orientation_evidence"]
    typed = evidence["typed_direction"]
    rows = evidence["response_relation_evidence"]
    preferred = [row for row in rows if row["normalized_semantic"] == typed]
    if not preferred:
        preferred = [row for row in rows if row.get("source_field") == "subject_action_surface"]
    if not preferred:
        preferred = rows
    terms = _unique(row["token"] for row in preferred)[:MAX_SURFACE_ALTERNATIVES_PER_ROLE]
    if not terms:
        raise RetrievalSurfaceCompilerError("validated relation has no relation lexical evidence")
    return [_surface(term, "RELATION_ORIENTATION",
                     origin="VALIDATED_RELATION_CORE_EVIDENCE",
                     authority="RELATION_CORE_VALIDATION",
                     source_ref=source_ref, retrieval_only=True) for term in terms]


def _action_surfaces(link: dict[str, Any], actors: list[str],
                     frame: dict[str, Any], source_ref: str) -> list[dict[str, Any]]:
    subject = link["subject_surface"]
    primary_actor = actors[0]
    candidate = ""
    if _contains_actor(subject, primary_actor):
        remainder = _elide_actor(subject, actors)
        if remainder:
            candidate = remainder
    if not candidate:
        candidate = _elide_actor(link["subject_action_surface"], actors)
    # A Planner action contaminated with external/nested context falls back to
    # the frozen target action surface.  This is role isolation, not synonymy.
    context_markers = (" under ", " in ")
    if any(marker in f" {candidate.casefold()} " for marker in context_markers):
        canonical_actions = frame["role_surfaces"].get("PRIMARY_INTERVENTION_ACTION", [])
        if canonical_actions:
            candidate = _elide_actor(canonical_actions[0], actors)
    alternatives = _split_surface(candidate)[:MAX_SURFACE_ALTERNATIVES_PER_ROLE]
    if not alternatives:
        raise RetrievalSurfaceCompilerError("validated relation has no action surface")
    return [_surface(value, "INTERVENTION_ACTION",
                     origin="VALIDATED_PLANNER_V3_LEXICAL_PROPOSAL",
                     authority="STRUCTURALLY_BOUND_RELATION",
                     source_ref=source_ref, retrieval_only=True) for value in alternatives]


def _validated_link_surfaces(value: str | None, role: str, source_ref: str,
                             *, fallbacks: list[str] | None = None) -> list[dict[str, Any]]:
    values = _split_surface(value)
    values.extend(fallbacks or [])
    values = _unique(values)[:MAX_SURFACE_ALTERNATIVES_PER_ROLE]
    if not values:
        return []
    return [_surface(item, role, origin="VALIDATED_PLANNER_V3_LEXICAL_PROPOSAL",
                     authority="STRUCTURALLY_BOUND_RELATION",
                     source_ref=source_ref, retrieval_only=True) for item in values]


def build_retrieval_surface_plan(*, case_id: str, intent_type: str,
                                 source_link_sha256: str, link: dict[str, Any],
                                 binding: dict[str, Any],
                                 target_role_frame: dict[str, Any]) -> dict[str, Any]:
    """Create one database-neutral plan from a frozen validated relation."""
    if binding.get("state") != "STRUCTURALLY_BOUND":
        raise RetrievalSurfaceCompilerError("relation is not structurally bound")
    if binding["relation_core"].get("state") != "VALID":
        raise RetrievalSurfaceCompilerError("relation core is not valid")
    if binding.get("canonical_identity_promoted"):
        raise RetrievalSurfaceCompilerError("identity promotion is forbidden")

    frame = target_role_frame
    frame_ref = frame["target_sha256"]
    actors = _canonical_surfaces(frame, "PRIMARY_INTERVENTION", frame_ref)
    if not actors:
        raise RetrievalSurfaceCompilerError("missing canonical actor")
    actor_texts = [row["text"] for row in actors]
    actions = _action_surfaces(link, actor_texts, frame, source_link_sha256)
    relations = _relation_terms(binding, source_link_sha256)
    responses = _canonical_surfaces(frame, "RESPONSE_TARGET", frame_ref)
    if not responses:
        responses = _validated_link_surfaces(
            link["response_surface"], "RESPONSE_TARGET", source_link_sha256)
    # Endpoint orientation is intent-conditioned.  Do not merge target-level
    # alternatives that may describe the opposite transformed intent.
    endpoints = _validated_link_surfaces(
        link["endpoint_property_surface"], "DEFINING_ENDPOINT_PROPERTY", source_link_sha256)
    if not endpoints:
        raise RetrievalSurfaceCompilerError("missing defining endpoint")

    therapy_required = frame["therapy_applicability"] == "REQUIRED"
    conditioning_required = frame["conditioning_treatment_applicability"] == "REQUIRED"
    therapies = _canonical_surfaces(frame, "THERAPY", frame_ref)
    if therapy_required and not therapies:
        therapies = _validated_link_surfaces(link.get("therapy_surface"), "THERAPY", source_link_sha256)
    conditioning = _canonical_surfaces(frame, "CONDITIONING_TREATMENT", frame_ref)
    if conditioning_required and not conditioning:
        conditioning = _validated_link_surfaces(
            link.get("conditioning_treatment_surface"), "CONDITIONING_TREATMENT", source_link_sha256)
    if therapy_required and not therapies:
        raise RetrievalSurfaceCompilerError("missing required therapy")
    if conditioning_required and not conditioning:
        raise RetrievalSurfaceCompilerError("missing required conditioning treatment")

    contexts: dict[str, list[dict[str, Any]]] = {}
    for row in binding["query_context_constraints"]["constraints"]:
        if not row["required"]:
            continue
        if row["state"] != "COMPATIBLE" or not row["surface"]:
            raise RetrievalSurfaceCompilerError(f"invalid required context: {row['role']}")
        context_values = _unique(
            [row["surface"], *frame["role_surfaces"].get(row["role"], [])]
        )[:MAX_SURFACE_ALTERNATIVES_PER_ROLE]
        contexts[row["role"]] = [
            _surface(item, row["role"], origin="VALIDATED_EXTERNAL_CONTEXT",
                     authority="QUERY_CONTEXT_CONSTRAINT_V1", source_ref=source_link_sha256,
                     retrieval_only=item not in frame["role_surfaces"].get(row["role"], []))
            for item in context_values
        ]

    plan = {
        "artifact_schema_version": SURFACE_PLAN_VERSION,
        "case_id": case_id,
        "intent_type": intent_type,
        "source_relation_core_sha256": source_link_sha256,
        "source_relation_core_state": "VALID",
        "source_target_sha256": frame_ref,
        "surface_roles": {
            "ACTOR": actors,
            "INTERVENTION_ACTION": actions,
            "RELATION_ORIENTATION": relations,
            "RESPONSE_TARGET": responses,
            "DEFINING_ENDPOINT_PROPERTY": endpoints,
            "THERAPY": therapies,
            "CONDITIONING_TREATMENT": conditioning,
        },
        "external_contexts": contexts,
        "requirements": {
            "therapy_required": therapy_required,
            "conditioning_required": conditioning_required,
            "defining_endpoint_required": True,
            "valid_relation_core_required": True,
        },
        "surface_ownership": {
            "allowed_origins_only": True,
            "new_scientific_identity_created": False,
            "search_only_surfaces_retrieval_only": True,
        },
        "variant_policy": {
            "variant_index": 0,
            "surface_variant_count": 1,
            "maximum": MAX_SURFACE_VARIANTS_PER_VALIDATED_INTENT,
        },
    }
    plan["surface_plan_id"] = "rspv1:" + value_sha256(plan)
    return plan


def _term_count(surface: str) -> int:
    return len(_TOKEN.findall(surface))


def _anchor(surface: dict[str, Any], roles: list[str]) -> dict[str, Any]:
    node_type = "TERM" if _term_count(surface["text"]) == 1 else "COMPACT_CONCEPT"
    node = {
        "node_type": node_type,
        "surface": surface["text"],
        "semantic_roles": roles,
        "surface_provenance": surface,
    }
    if node_type == "COMPACT_CONCEPT":
        node["window_n"] = COMPACT_CONCEPT_WINDOW_N
    return node


def _proximity(anchors: list[dict[str, Any]], edge_type: str) -> dict[str, Any]:
    roles = sorted({role for anchor in anchors for role in anchor["semantic_roles"]})
    if len(roles) > MAX_PROXIMITY_ROLE_ANCHORS:
        raise RetrievalSurfaceCompilerError("proximity role-count limit exceeded")
    return {
        "node_type": "PROXIMITY",
        "window_n": RELATION_EDGE_WINDOW_N,
        "field": "Title/Abstract",
        "edge_type": edge_type,
        "semantic_roles": roles,
        "anchors": anchors,
    }


def _edge_node(role_groups: list[tuple[str, list[dict[str, Any]]]],
               edge_type: str) -> dict[str, Any]:
    choices = []
    for role, surfaces in role_groups:
        if not surfaces:
            raise RetrievalSurfaceCompilerError(f"empty edge role: {role}")
        choices.append([_anchor(surface, [role]) for surface in surfaces])
    nodes = [_proximity(list(combo), edge_type) for combo in product(*choices)]
    if len(nodes) == 1:
        return nodes[0]
    return {"node_type": "OR_GROUP", "children": nodes, "semantic_roles": sorted(
        {role for node in nodes for role in node["semantic_roles"]})}


def _field_scoped(surface: dict[str, Any], role: str) -> dict[str, Any]:
    return {
        "node_type": "FIELD_SCOPE",
        "field": "Title/Abstract",
        "child": _anchor(surface, [role]),
        "semantic_roles": [role],
    }


def _context_node(role: str, surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [_field_scoped(surface, role) for surface in surfaces]
    if len(nodes) == 1:
        return nodes[0]
    return {"node_type": "OR_GROUP", "children": nodes, "semantic_roles": [role]}


def build_pubmed_query_ast(plan: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if plan.get("artifact_schema_version") != SURFACE_PLAN_VERSION:
        raise RetrievalSurfaceCompilerError("serializer pipeline requires RetrievalSurfacePlanV1")
    roles = plan["surface_roles"]
    edges = [
        {"edge_type": "ACTOR_ACTION_RELATION", "roles": ["ACTOR", "INTERVENTION_ACTION", "RELATION_ORIENTATION"]},
        {"edge_type": "RELATION_RESPONSE", "roles": ["RELATION_ORIENTATION", "RESPONSE_TARGET"]},
        {"edge_type": "RESPONSE_ENDPOINT", "roles": ["RESPONSE_TARGET", "DEFINING_ENDPOINT_PROPERTY"]},
    ]
    if plan["requirements"]["therapy_required"]:
        edges.append({"edge_type": "THERAPY_RESPONSE_PROPERTY",
                      "roles": ["THERAPY", "DEFINING_ENDPOINT_PROPERTY"]})
    if plan["requirements"]["conditioning_required"]:
        edges.append({"edge_type": "CONDITIONING_NESTED_RESPONSE",
                      "roles": ["CONDITIONING_TREATMENT", "RESPONSE_TARGET", "DEFINING_ENDPOINT_PROPERTY"]})
    children = [_edge_node([(role, roles[role]) for role in edge["roles"]], edge["edge_type"])
                for edge in edges]
    children.extend(_context_node(role, surfaces)
                    for role, surfaces in sorted(plan["external_contexts"].items()))
    ast = {
        "artifact_schema_version": AST_VERSION,
        "root": {"node_type": "AND_GROUP", "children": children},
        "source_surface_plan_id": plan["surface_plan_id"],
        "source_relation_core_sha256": plan["source_relation_core_sha256"],
        "source_validated": True,
        "raw_planner_text_accepted_by_serializer": False,
    }
    ast["ast_sha256"] = value_sha256(ast)
    relation_edges = []
    for edge in edges:
        relation_edges.append({
            "artifact_schema_version": RELATION_EDGE_VERSION,
            "edge_type": edge["edge_type"],
            "semantic_roles": edge["roles"],
            "window_n": RELATION_EDGE_WINDOW_N,
            "source_relation_core_sha256": plan["source_relation_core_sha256"],
        })
    return ast, relation_edges


def _serialize_anchor(anchor: dict[str, Any]) -> str:
    return anchor["surface"]


def _serialize(node: dict[str, Any], *, root: bool = False) -> str:
    kind = node.get("node_type")
    if kind == "TERM":
        if _term_count(node["surface"]) != 1:
            raise RetrievalSurfaceCompilerError("multiword TERM is forbidden")
        return node["surface"]
    if kind == "COMPACT_CONCEPT":
        if _term_count(node["surface"]) < 2:
            raise RetrievalSurfaceCompilerError("single-token COMPACT_CONCEPT")
        return f'"{node["surface"]}"[Title/Abstract:~{COMPACT_CONCEPT_WINDOW_N}]'
    if kind == "FIELD_SCOPE":
        child = node["child"]
        if child["node_type"] == "TERM":
            return f'{_serialize(child)}[Title/Abstract]'
        if child["node_type"] == "COMPACT_CONCEPT":
            return _serialize(child)
        raise RetrievalSurfaceCompilerError("FIELD_SCOPE child must be TERM or COMPACT_CONCEPT")
    if kind == "PROXIMITY":
        if any("*" in anchor["surface"] for anchor in node["anchors"]):
            raise RetrievalSurfaceCompilerError("wildcard inside proximity")
        terms = " ".join(_serialize_anchor(anchor) for anchor in node["anchors"])
        return f'"{terms}"[Title/Abstract:~{node["window_n"]}]'
    if kind in {"OR_GROUP", "AND_GROUP"}:
        children = node.get("children", [])
        if not children:
            raise RetrievalSurfaceCompilerError(f"empty {kind}")
        operator = " OR " if kind == "OR_GROUP" else " AND "
        body = operator.join(_serialize(child) for child in children)
        return body if root and kind == "AND_GROUP" else f"({body})"
    raise RetrievalSurfaceCompilerError(f"unsupported AST node: {kind!r}")


def serialize_pubmed_query(ast: dict[str, Any]) -> str:
    """Serialize only a validated PubMedQueryASTV1, never a RelationCore."""
    if not isinstance(ast, dict) or ast.get("artifact_schema_version") != AST_VERSION:
        raise RetrievalSurfaceCompilerError("PubMedQuerySerializerV2 accepts PubMedQueryASTV1 only")
    if not ast.get("source_validated") or ast.get("raw_planner_text_accepted_by_serializer"):
        raise RetrievalSurfaceCompilerError("raw or unvalidated planner text cannot enter serializer")
    return _serialize(ast["root"], root=True)


def _walk(node: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield node
    if node.get("node_type") in {"AND_GROUP", "OR_GROUP"}:
        for child in node.get("children", []):
            yield from _walk(child)
    elif node.get("node_type") == "FIELD_SCOPE":
        yield from _walk(node["child"])
    elif node.get("node_type") == "PROXIMITY":
        for anchor in node.get("anchors", []):
            yield from _walk(anchor)


def coverage_for_ast(ast: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    roles = {role for node in _walk(ast["root"]) for role in node.get("semantic_roles", [])}
    external = sorted(plan["external_contexts"])
    flags = {
        "actor_covered": "ACTOR" in roles,
        "action_covered": "INTERVENTION_ACTION" in roles,
        "relation_orientation_covered": "RELATION_ORIENTATION" in roles,
        "response_covered": "RESPONSE_TARGET" in roles,
        "endpoint_covered": "DEFINING_ENDPOINT_PROPERTY" in roles,
        "therapy_covered_when_required": (
            not plan["requirements"]["therapy_required"] or "THERAPY" in roles),
        "conditioning_covered_when_required": (
            not plan["requirements"]["conditioning_required"] or
            "CONDITIONING_TREATMENT" in roles),
        "external_contexts_covered": all(role in roles for role in external),
    }
    return {
        "artifact_schema_version": COVERAGE_VERSION,
        "flags": flags,
        "covered_roles": sorted(roles),
        "external_context_roles": external,
        "state": "COVERED" if all(flags.values()) else "INCOMPLETE",
    }


def relation_serialization_certificate(ast: dict[str, Any], plan: dict[str, Any],
                                       edges: list[dict[str, Any]],
                                       coverage: dict[str, Any]) -> dict[str, Any]:
    edge_types = {edge["edge_type"] for edge in edges}
    required = {"ACTOR_ACTION_RELATION", "RELATION_RESPONSE", "RESPONSE_ENDPOINT"}
    if plan["requirements"]["therapy_required"]:
        required.add("THERAPY_RESPONSE_PROPERTY")
    if plan["requirements"]["conditioning_required"]:
        required.add("CONDITIONING_NESTED_RESPONSE")
    checks = {
        "source_relation_core_valid": plan["source_relation_core_state"] == "VALID",
        "required_internal_roles_represented": coverage["state"] == "COVERED",
        "required_relation_edges_represented": required <= edge_types,
        "endpoint_retained": coverage["flags"]["endpoint_covered"],
        "therapy_internality_preserved": (
            not plan["requirements"]["therapy_required"] or
            "THERAPY_RESPONSE_PROPERTY" in edge_types),
        "conditioning_internality_preserved": (
            not plan["requirements"]["conditioning_required"] or
            "CONDITIONING_NESTED_RESPONSE" in edge_types),
        "context_only_query_created": False,
    }
    return {
        "artifact_schema_version": CERTIFICATE_VERSION,
        "ast_sha256": ast["ast_sha256"],
        "surface_plan_id": plan["surface_plan_id"],
        "source_relation_core_sha256": plan["source_relation_core_sha256"],
        "required_edge_types": sorted(required),
        "represented_edge_types": sorted(edge_types),
        "checks": checks,
        "state": "CERTIFIED" if all(value is True for key, value in checks.items()
                                        if key != "context_only_query_created")
                 and checks["context_only_query_created"] is False else "REJECTED",
    }


def lint_query_serialization(ast: dict[str, Any], plan: dict[str, Any],
                             certificate: dict[str, Any]) -> dict[str, Any]:
    errors = []
    nodes = list(_walk(ast["root"]))
    allowed = {"TERM", "COMPACT_CONCEPT", "OR_GROUP", "AND_GROUP", "PROXIMITY", "FIELD_SCOPE"}
    if any(node.get("node_type") not in allowed for node in nodes):
        errors.append("UNKNOWN_OR_FREE_FORM_NODE")
    proximity = [node for node in nodes if node.get("node_type") == "PROXIMITY"]
    if any(len(node.get("semantic_roles", [])) > MAX_PROXIMITY_ROLE_ANCHORS for node in proximity):
        errors.append("PROXIMITY_ROLE_COUNT_EXCEEDED")
    if any("*" in anchor.get("surface", "") for node in proximity for anchor in node.get("anchors", [])):
        errors.append("WILDCARD_INSIDE_PROXIMITY")
    if any(node.get("node_type") == "TERM" and _term_count(node.get("surface", "")) != 1
           for node in nodes):
        errors.append("UNSCOPED_MULTIWORD_TERM")
    if any(node.get("node_type") in {"AND_GROUP", "OR_GROUP"} and not node.get("children")
           for node in nodes):
        errors.append("EMPTY_BOOLEAN_GROUP")
    if not ast.get("source_validated") or ast.get("raw_planner_text_accepted_by_serializer"):
        errors.append("RAW_UNVALIDATED_PLANNER_TEXT")
    if certificate["state"] != "CERTIFIED":
        errors.append("RELATION_CERTIFICATE_REJECTED")
    if not any(node.get("edge_type") == "ACTOR_ACTION_RELATION" for node in proximity):
        errors.append("CONTEXT_ONLY_OR_TOPIC_BAG_QUERY")
    if not any(node.get("edge_type") == "RESPONSE_ENDPOINT" for node in proximity):
        errors.append("MISSING_DEFINING_ENDPOINT")
    if plan["requirements"]["therapy_required"] and not any(
            node.get("edge_type") == "THERAPY_RESPONSE_PROPERTY" for node in proximity):
        errors.append("MISSING_REQUIRED_THERAPY_EDGE")
    if plan["requirements"]["conditioning_required"] and not any(
            node.get("edge_type") == "CONDITIONING_NESTED_RESPONSE" for node in proximity):
        errors.append("MISSING_REQUIRED_CONDITIONING_EDGE")
    try:
        query = serialize_pubmed_query(ast)
    except RetrievalSurfaceCompilerError as exc:
        errors.append(f"SERIALIZATION_ERROR:{exc}")
        query = None
    if query is not None:
        if query.count("(") != query.count(")"):
            errors.append("UNBALANCED_PARENTHESES")
        if query.count('"') % 2:
            errors.append("UNBALANCED_QUOTES")
        quoted = list(re.finditer(r'"([^"]*)"', query))
        invalid_quoted = [match.group(0) for match in quoted
                          if not re.match(r"\[Title/Abstract:~\d+\]", query[match.end():])]
        if invalid_quoted:
            errors.append("EXACT_PHRASE_OR_INVALID_PROXIMITY")
    return {
        "artifact_schema_version": LINTER_VERSION,
        "state": "PASS" if not errors else "REJECT",
        "errors": errors,
        "full_proposition_exact_phrase": False,
        "semantic_overpacking": any(
            len(node.get("semantic_roles", [])) > MAX_PROXIMITY_ROLE_ANCHORS for node in proximity),
        "raw_unvalidated_planner_text_entered_serializer": False,
        "serialized_query": query,
    }


def compile_surface_plan(plan: dict[str, Any]) -> dict[str, Any]:
    ast, edges = build_pubmed_query_ast(plan)
    coverage = coverage_for_ast(ast, plan)
    certificate = relation_serialization_certificate(ast, plan, edges, coverage)
    linter = lint_query_serialization(ast, plan, certificate)
    if linter["state"] != "PASS":
        raise RetrievalSurfaceCompilerError(f"query safety linter rejected: {linter['errors']}")
    query = linter["serialized_query"]
    return {
        "surface_plan": plan,
        "ast": ast,
        "relation_edges": edges,
        "coverage": coverage,
        "certificate": certificate,
        "linter": linter,
        "serialized_query": query,
        "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
        "provenance": {
            "ast_sha256": ast["ast_sha256"],
            "serializer_version": SERIALIZER_VERSION,
            "syntax_contract_version": SYNTAX_VERSION,
            "surface_plan_sha256": value_sha256(plan),
            "relation_core_sha256": plan["source_relation_core_sha256"],
        },
    }


__all__ = [
    "AST_VERSION", "CERTIFICATE_VERSION", "COMPACT_CONCEPT_WINDOW_N",
    "COVERAGE_VERSION", "LINTER_VERSION", "MAX_PROXIMITY_ROLE_ANCHORS",
    "MAX_QUERIES_PER_TARGET", "MAX_SURFACE_VARIANTS_PER_VALIDATED_INTENT",
    "RELATION_EDGE_VERSION", "RELATION_EDGE_WINDOW_N", "SERIALIZER_VERSION",
    "SURFACE_PLAN_VERSION", "SYNTAX_VERSION", "RetrievalSurfaceCompilerError",
    "build_pubmed_query_ast", "build_retrieval_surface_plan", "canonical",
    "compile_surface_plan", "coverage_for_ast", "lint_query_serialization",
    "relation_serialization_certificate", "serialize_pubmed_query", "value_sha256",
]
