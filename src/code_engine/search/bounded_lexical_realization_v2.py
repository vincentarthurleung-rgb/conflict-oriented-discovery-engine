"""Offline, bounded lexical realization of frozen V3 retrieval-surface plans.

This module changes surface strings only. It does not read retrieved records,
infer entity aliases, or change SearchConstraintAllocationV1 role allocation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from code_engine.search.search_constraint_allocation_v1 import (
    VARIANT_PRIORITY, _root, allocation_for_plan, canonical, certificate_for_ast,
    compile_family, digest, serialize_validated_ast,
)


VERSION = "BoundedLexicalRealizationV2"
MAX_ALTERNATIVES_PER_ROLE = 4
MAX_MORPHOLOGY_VARIANTS_PER_BASE = 3
AUTHORITY_CLASSES = (
    "CANONICAL_SURFACE", "AUTHORIZED_ALIAS", "VALIDATED_PLANNER_SURFACE",
    "DETERMINISTIC_MORPHOLOGICAL_VARIANT", "FROZEN_RELATION_LEXICON",
    "FROZEN_ENDPOINT_LEXICON", "UNRESOLVED",
)

# Whitelist of grammatical realizations, not a stemmer or an inference rule.
# Each row is generic to the lexical class and independent of retrieved papers.
RELATION_LEXICON = {
    "INCREASE": {"increases": ("increase", "increased", "increasing")},
    "DECREASE": {
        "decreases": ("decrease", "decreased", "decreasing"),
        "reduces": ("reduce", "reduced", "reducing"),
    },
    "REQUIRE": {
        "required": ("require", "requires", "requiring"),
        "necessary": (),
    },
    "SENSITIZE": {"sensitizes": ("sensitize", "sensitized", "sensitizing")},
    "RESCUE": {"rescues": ("rescue", "rescued", "rescuing")},
    "STIMULATE": {"stimulates": ("stimulate", "stimulated", "stimulating")},
}
ACTION_MORPHOLOGY = {
    "activation": ("activate", "activated", "activating"),
    "inhibition": ("inhibit", "inhibited", "inhibiting"),
    "stimulation": ("stimulate", "stimulated", "stimulating"),
    "restoration": ("restore", "restored", "restoring"),
    "depletion": ("deplete", "depleted", "depleting"),
}
ENDPOINT_LEXICON = {
    "phosphorylation": ("phosphorylated",),
    "secretion": ("secreted",),
}


class LexicalRealizationError(ValueError):
    pass


def morphology_for(role: str, surface: str) -> tuple[str, ...]:
    if role == "RELATION_ORIENTATION":
        return next((variants for family in RELATION_LEXICON.values()
                     for base, variants in family.items() if base == surface), ())
    if role == "INTERVENTION_ACTION":
        return ACTION_MORPHOLOGY.get(surface, ())
    if role == "DEFINING_ENDPOINT_PROPERTY":
        return ENDPOINT_LEXICON.get(surface, ())
    return ()


def _base_class(surface: dict[str, Any]) -> str:
    if surface["origin"] == "CANONICAL_TARGET_SURFACE":
        return "CANONICAL_SURFACE"
    if surface["origin"] in {
        "VALIDATED_PLANNER_V3_LEXICAL_PROPOSAL", "VALIDATED_RELATION_CORE_EVIDENCE",
        "VALIDATED_EXTERNAL_CONTEXT",
    }:
        return "VALIDATED_PLANNER_SURFACE"
    raise LexicalRealizationError("surface has no authorized lexical class")


def alternatives_for(plan: dict[str, Any], role: str, surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    if not surfaces:
        raise LexicalRealizationError(f"empty role: {role}")
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for surface in surfaces:
        if surface.get("canonical_identity_promoted") is not False:
            raise LexicalRealizationError("source identity promotion")
        base = surface["text"]
        if base not in seen:
            accepted.append({
                "surface": base, "authority_class": _base_class(surface),
                "source_provenance": surface, "semantic_role": role,
                "canonical_target_link": plan["source_target_sha256"],
                "source_relation_core_sha256": plan["source_relation_core_sha256"],
                "safety_status": "AUTHORIZED_EXACT_SURFACE", "derived_from": None,
            })
            seen.add(base)
    if len(accepted) > MAX_ALTERNATIVES_PER_ROLE:
        raise LexicalRealizationError("frozen source exceeds lexical role budget")
    for surface in surfaces:
        variants = morphology_for(role, surface["text"])
        if len(variants) > MAX_MORPHOLOGY_VARIANTS_PER_BASE:
            raise LexicalRealizationError("morphology budget exceeded")
        for variant in variants:
            if variant in seen:
                continue
            item = {
                "surface": variant,
                "authority_class": "DETERMINISTIC_MORPHOLOGICAL_VARIANT",
                "source_provenance": surface, "semantic_role": role,
                "canonical_target_link": plan["source_target_sha256"],
                "source_relation_core_sha256": plan["source_relation_core_sha256"],
                "safety_status": "WHITELISTED_GRAMMATICAL_REALIZATION",
                "derived_from": surface["text"],
            }
            if len(accepted) < MAX_ALTERNATIVES_PER_ROLE:
                accepted.append(item)
                seen.add(variant)
            else:
                rejected.append({**item, "rejection_reason": "ROLE_BUDGET_EXCEEDED"})
    record = {
        "artifact_schema_version": "LexicalAlternativeSetV2",
        "case_id": plan["case_id"], "surface_plan_id": plan["surface_plan_id"],
        "semantic_role": role, "canonical_target_link": plan["source_target_sha256"],
        "alternatives": accepted, "rejected_alternatives": rejected,
        "max_alternatives_per_role": MAX_ALTERNATIVES_PER_ROLE,
    }
    record["lexical_alternative_set_id"] = "lasv2:" + digest(record)
    return record


def _lexical_surface(item: dict[str, Any]) -> dict[str, Any]:
    source = item["source_provenance"]
    return {
        **source, "text": item["surface"],
        "origin": (source["origin"] if item["derived_from"] is None
                   else "DETERMINISTIC_MORPHOLOGICAL_VARIANT"),
        "lexical_authority_class": item["authority_class"],
        "lexical_source_surface": source["text"],
    }


def lexicalize_family(plan: dict[str, Any]) -> dict[str, Any]:
    """Compile the same variant family with bounded alternatives per role."""
    baseline = compile_family(plan)
    allocation = allocation_for_plan(plan)
    role_sets: dict[str, dict[str, Any]] = {}
    lexical_plan = deepcopy(plan)
    for bucket in ("surface_roles", "external_contexts"):
        for role, surfaces in plan[bucket].items():
            if not surfaces:
                continue
            if role in role_sets:
                raise LexicalRealizationError("duplicate semantic role buckets")
            role_sets[role] = alternatives_for(plan, role, surfaces)
            lexical_plan[bucket][role] = [_lexical_surface(item) for item in role_sets[role]["alternatives"]]
    members = []
    for old in baseline["members"]:
        variant = old["variant_class"]
        ast = deepcopy(old["ast"])
        ast["root"] = _root(lexical_plan, variant)
        ast["lexical_realization_version"] = VERSION
        ast["lexical_alternative_set_ids"] = {r: s["lexical_alternative_set_id"] for r, s in sorted(role_sets.items())}
        ast["ast_sha256"] = digest({k: v for k, v in ast.items() if k != "ast_sha256"})
        # The source allocation's semantic roles are immutable. Only the
        # surface-hash allowlist is projected for lexical certificate checking.
        lexical_validation_allocation = deepcopy(allocation)
        lexical_validation_allocation["authorized_surface_sha256_by_role"] = {
            role: [digest(surface) for surface in surfaces]
            for role, surfaces in {**lexical_plan["surface_roles"], **lexical_plan["external_contexts"]}.items()
            if surfaces
        }
        query, cert = serialize_validated_ast(ast, lexical_validation_allocation)
        if {k: v for k, v in lexical_validation_allocation.items()
            if k != "authorized_surface_sha256_by_role"} != {
                k: v for k, v in allocation.items()
                if k != "authorized_surface_sha256_by_role"}:
            raise LexicalRealizationError("scientific allocation changed")
        if cert["search_required_roles"] != old["certificate"]["search_required_roles"] or \
                cert["relation_internal_roles"] != old["certificate"]["relation_internal_roles"] or \
                cert["deferred_validator_owners"] != old["certificate"]["deferred_validator_owners"]:
            raise LexicalRealizationError("relation or validator certificate changed")
        used_roles = sorted({role for node in ast["root"]["children"]
                             for role in _roles_for_node(node)})
        coverage = {
            "artifact_schema_version": "LexicalCoverageCertificateV2",
            "case_id": plan["case_id"], "surface_plan_id": plan["surface_plan_id"],
            "variant_class": variant, "query_ast_sha256": ast["ast_sha256"],
            "role_alternatives": {r: role_sets[r]["lexical_alternative_set_id"] for r in used_roles},
            "authority_sources": {r: sorted({i["authority_class"] for i in role_sets[r]["alternatives"]}) for r in used_roles},
            "morphology_derivations": {r: [{"surface": i["surface"], "base": i["derived_from"]} for i in role_sets[r]["alternatives"] if i["derived_from"]] for r in used_roles},
            "rejected_alternatives": {r: role_sets[r]["rejected_alternatives"] for r in used_roles},
            "identity_safety_result": "PASS", "semantic_broadening_result": "PASS",
            "minimum_relational_evidence_certificate": cert,
            "source_allocation_certificate_sha256": digest(allocation),
        }
        members.append({"variant_class": variant, "ast": ast, "query": query,
                        "certificate": cert, "lexical_coverage_certificate": coverage,
                        "lexical_validation_surface_hashes": lexical_validation_allocation["authorized_surface_sha256_by_role"]})
    if tuple(m["variant_class"] for m in members) != tuple(m["variant_class"] for m in baseline["members"]):
        raise LexicalRealizationError("query family variant changed")
    return {"case_id": plan["case_id"], "intent_type": plan["intent_type"],
            "surface_plan_id": plan["surface_plan_id"], "allocation": allocation,
            "role_sets": role_sets, "members": members,
            "baseline_members": baseline["members"]}


def _roles_for_node(node: dict[str, Any]) -> set[str]:
    if node["node_type"] in {"AND_GROUP", "OR_GROUP"}:
        return set().union(*(_roles_for_node(child) for child in node["children"]))
    return set(node.get("semantic_roles", []))
