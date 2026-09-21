"""Generic, offline role applicability for frozen scientific targets.

This is a versioned interpretation of target fields for retrieval binding. It
neither changes ScientificPropositionTargetV1 nor grants scientific identity.
"""

from __future__ import annotations

from typing import Any

from code_engine.search.alpha1_relation_searchonly_v1 import _anchors, alternatives, normalize
from code_engine.search.alpha2_linked_relation_v1 import _contains_surface, _unsafe
from code_engine.search.semantic_slot_compatibility_v1 import audit_linked_relation_candidate

ONTOLOGY_VERSION = "ContextRoleOntologyV1"
CONDITIONING_VERSION = "ConditioningContextApplicabilityV1"
THERAPY_VERSION = "TherapyContextApplicabilityV1"
LINK_VERSION = "LinkedRelationCandidateV1_1"
BINDING_VERSION = "RelationBindingAssessmentV1_2"
ROLES = (
    "PRIMARY_INTERVENTION", "PRIMARY_INTERVENTION_ACTION", "RESPONSE_TARGET",
    "RESPONSE_PROPERTY", "CONDITIONING_TREATMENT", "THERAPY",
    "DISEASE_CONTEXT", "GENOTYPE_CONTEXT", "BIOLOGICAL_UNIT_CONTEXT",
    "LOCALIZATION_CONTEXT", "TIME_CONTEXT", "OTHER_EXPERIMENTAL_CONTEXT",
)
APPLICABILITY_STATES = ("REQUIRED", "NOT_APPLICABLE", "UNRESOLVED")


def _values(value: Any) -> list[str]:
    return alternatives(value)


def _same_primary_action(surface: str, target: dict[str, Any]) -> bool:
    """Require full treatment surface inside frozen primary intervention.

    A shared entity token alone never establishes action equivalence.
    """
    subject = target.get("subject") or target.get("canonical_subject") or ""
    intervention = target.get("subject_intervention") or ""
    return bool(subject and intervention and _contains_surface(surface, subject)
                and _contains_surface(intervention, surface))


def _same_therapy(surface: str, target: dict[str, Any]) -> bool:
    therapy = target.get("therapy")
    return bool(therapy and normalize(surface) == normalize(str(therapy)))


def context_role_mapping(target: dict[str, Any]) -> dict[str, Any]:
    """Interpret target source fields; ambiguous treatment roles fail closed."""
    if target.get("artifact_schema_version") != "ScientificPropositionTargetV1":
        raise ValueError("frozen ScientificPropositionTargetV1 required")
    context = target.get("context_qualifier_dimensions") or {}
    rows: list[dict[str, Any]] = []

    def add(path: str, value: Any, role: str, rule: str) -> None:
        for surface in _values(value):
            rows.append({"source_path": path, "surface": surface, "role": role,
                         "rule_id": rule, "identity_promoted": False})

    add("/subject", target.get("subject"), "PRIMARY_INTERVENTION", "FROZEN_PRIMARY_ACTOR")
    add("/subject_intervention", target.get("subject_intervention"), "PRIMARY_INTERVENTION_ACTION",
        "FROZEN_PRIMARY_MANIPULATION")
    add("/measurement_target", target.get("measurement_target"), "RESPONSE_TARGET", "FROZEN_MEASURED_RESPONSE")
    add("/measurement_property_endpoint", target.get("measurement_property_endpoint"),
        "RESPONSE_PROPERTY", "FROZEN_MEASURED_PROPERTY")
    for name, role in (("biological_unit", "BIOLOGICAL_UNIT_CONTEXT"),
                       ("disease_context", "DISEASE_CONTEXT"), ("disease", "DISEASE_CONTEXT"),
                       ("genotype_context", "GENOTYPE_CONTEXT"), ("genotype", "GENOTYPE_CONTEXT"),
                       ("localization", "LOCALIZATION_CONTEXT"), ("time", "TIME_CONTEXT")):
        add(f"/context_qualifier_dimensions/{name}", context.get(name), role, "EXPLICIT_FROZEN_CONTEXT_FIELD")
    add("/therapy", target.get("therapy"), "THERAPY", "EXPLICIT_THERAPY_RESPONSE_FIELD")
    add("/context_qualifier_dimensions/therapy", context.get("therapy"), "THERAPY",
        "EXPLICIT_THERAPY_RESPONSE_FIELD")
    for key in ("treatment", "treatment_context"):
        for surface in _values(context.get(key)):
            if _same_therapy(surface, target):
                role, rule = "THERAPY", "THERAPY_IDENTITY_NOT_GENERIC_CONDITIONING"
            elif _same_primary_action(surface, target):
                role, rule = "PRIMARY_INTERVENTION_ACTION", "FULL_SURFACE_MATCH_TO_FROZEN_PRIMARY_ACTION"
            elif target.get("subject") and _contains_surface(surface, str(target["subject"])):
                role, rule = "OTHER_EXPERIMENTAL_CONTEXT", "SAME_ACTOR_DIFFERENT_ACTION_UNRESOLVED"
            else:
                role, rule = "CONDITIONING_TREATMENT", "DISTINCT_EXPLICIT_TREATMENT_CONTEXT"
            rows.append({"source_path": f"/context_qualifier_dimensions/{key}",
                         "surface": surface, "role": role, "rule_id": rule,
                         "identity_promoted": False})
    known = {"biological_unit", "disease_context", "disease", "genotype_context", "genotype",
             "localization", "time", "treatment", "treatment_context", "therapy"}
    for key in sorted(set(context) - known):
        add(f"/context_qualifier_dimensions/{key}", context[key],
            "OTHER_EXPERIMENTAL_CONTEXT", "UNMAPPED_FROZEN_CONTEXT_FIELD")
    return {"artifact_schema_version": ONTOLOGY_VERSION, "target_id": target.get("scientific_proposition_target_id"),
            "roles": rows, "role_set": list(ROLES), "target_mutated": False}


def conditioning_context_applicability(target: dict[str, Any]) -> dict[str, Any]:
    roles = context_role_mapping(target)["roles"]
    treatment = [r for r in roles if r["source_path"] in {
        "/context_qualifier_dimensions/treatment", "/context_qualifier_dimensions/treatment_context"}]
    required = [r for r in treatment if r["role"] == "CONDITIONING_TREATMENT"]
    unresolved = [r for r in treatment if r["rule_id"] == "SAME_ACTOR_DIFFERENT_ACTION_UNRESOLVED"]
    state = "UNRESOLVED" if unresolved else "REQUIRED" if required else "NOT_APPLICABLE"
    return {"artifact_schema_version": CONDITIONING_VERSION, "state": state,
            "required_surfaces": [r["surface"] for r in required],
            "source_rows": treatment, "generic_rule": "ROLE_OF_FROZEN_TREATMENT_SURFACE",
            "canonical_identity_promoted": False}


def therapy_context_applicability(target: dict[str, Any]) -> dict[str, Any]:
    roles = context_role_mapping(target)["roles"]
    therapies = [r for r in roles if r["role"] == "THERAPY"]
    surfaces = list(dict.fromkeys(r["surface"] for r in therapies))
    endpoint = normalize(str(target.get("measurement_property_endpoint") or ""))
    response_requires_therapy = any(part in endpoint for part in ("sensitiv", "resistan", "therapy response"))
    state = "REQUIRED" if surfaces else "UNRESOLVED" if response_requires_therapy else "NOT_APPLICABLE"
    return {"artifact_schema_version": THERAPY_VERSION, "state": state,
            "required_surfaces": surfaces, "source_rows": therapies,
            "generic_rule": "EXPLICIT_THERAPY_AND_RESPONSE_PROPERTY",
            "canonical_identity_promoted": False}


def project_linked_relation_candidate_v1_1(link: dict[str, Any], target: dict[str, Any],
                                             concepts: dict[str, Any],
                                             blueprint_concept_ids: list[str] | None = None) -> dict[str, Any]:
    """Non-mutating V1 adapter, with explicit independently typed role refs."""
    conditioning = conditioning_context_applicability(target)
    therapy = therapy_context_applicability(target)
    subject_ref = link["subject_concept_ref"]
    response_ref = link["response_concept_ref"]
    unit_ref = link["biological_unit_context_ref"]
    context_refs = list(link["conditioning_context_refs"])
    therapy_refs = list(link["therapy_context_refs"])
    def concept_type(ref: str) -> str | None:
        item = concepts.get(ref)
        return item.get("concept_type") if isinstance(item, dict) else item if isinstance(item, str) else None

    def canonical_values(ref: str) -> list[str]:
        item = concepts.get(ref)
        if not isinstance(item, dict):
            return []
        return _values(item.get("canonical_anchor"))

    other_refs = {ref: concept_type(ref) for ref in (blueprint_concept_ids or [])
                  if concept_type(ref) in {"disease", "genotype"}}
    conditioning_surfaces = set(normalize(s) for s in conditioning["required_surfaces"])
    therapy_surfaces = set(normalize(s) for s in therapy["required_surfaces"])
    context_ref_anchors_valid = (not context_refs if conditioning["state"] == "NOT_APPLICABLE"
                                 else all(any(normalize(v) in conditioning_surfaces for v in canonical_values(ref))
                                          for ref in context_refs))
    therapy_ref_anchors_valid = (not therapy_refs if therapy["state"] == "NOT_APPLICABLE"
                                 else all(any(normalize(v) in therapy_surfaces for v in canonical_values(ref))
                                          for ref in therapy_refs))
    roles_valid = (concept_type(subject_ref) == "subject"
                   and concept_type(response_ref) == "object_measurement_target"
                   and (unit_ref is None or concept_type(unit_ref) == "biological_unit")
                   and all(concept_type(ref) == "nested_treatment" for ref in context_refs)
                   and all(concept_type(ref) == "therapy" for ref in therapy_refs)
                   and context_ref_anchors_valid and therapy_ref_anchors_valid)
    return {"artifact_schema_version": LINK_VERSION,
            "source_candidate_version": "LinkedRelationCandidateV1", "source_candidate_mutated": False,
            "primary_intervention_ref": subject_ref,
            "primary_intervention_action_surface": link["subject_surface_candidate"],
            "response_target_ref": response_ref,
            "response_property_surface": link["endpoint_property_surface_candidate"],
            "conditioning_treatment_refs": context_refs, "therapy_refs": therapy_refs,
            "biological_unit_ref": unit_ref, "other_context_refs": other_refs,
            "conditioning_applicability": conditioning["state"],
            "therapy_applicability": therapy["state"],
            "reference_roles_valid": roles_valid,
            "conditioning_reference_anchors_valid": context_ref_anchors_valid,
            "therapy_reference_anchors_valid": therapy_ref_anchors_valid,
            "canonical_identity_promoted": False}


def assess_linked_relation_v1_2(link: dict[str, Any], target: dict[str, Any],
                                concepts: dict[str, Any],
                                blueprint_concept_ids: list[str] | None = None) -> dict[str, Any]:
    """Versioned binder: all semantic/anchor checks plus role applicability."""
    projection = project_linked_relation_candidate_v1_1(link, target, concepts, blueprint_concept_ids)
    old_audit = audit_linked_relation_candidate(link, target)
    checks = dict(old_audit["checks"])
    conditioning = conditioning_context_applicability(target)
    therapy = therapy_context_applicability(target)
    phrase = link["linked_relation_phrase"]
    if conditioning["state"] == "NOT_APPLICABLE":
        checks["required_conditioning_context"] = not link["conditioning_context_refs"]
    elif conditioning["state"] == "REQUIRED":
        checks["required_conditioning_context"] = bool(link["conditioning_context_refs"]) and all(
            _contains_surface(phrase, surface) for surface in conditioning["required_surfaces"])
    else:
        checks["required_conditioning_context"] = False
    if therapy["state"] == "NOT_APPLICABLE":
        checks["required_therapy_context"] = not link["therapy_context_refs"]
    elif therapy["state"] == "REQUIRED":
        checks["required_therapy_context"] = bool(link["therapy_context_refs"]) and all(
            _contains_surface(phrase, surface) for surface in therapy["required_surfaces"])
    else:
        checks["required_therapy_context"] = False
    checks["reference_roles"] = projection["reference_roles_valid"]
    checks["primary_intervention_distinct_from_therapy"] = (
        projection["primary_intervention_ref"] not in projection["therapy_refs"])
    checks["primary_intervention_distinct_from_conditioning"] = (
        projection["primary_intervention_ref"] not in projection["conditioning_treatment_refs"])
    return {"artifact_schema_version": BINDING_VERSION,
            "state": "STRUCTURALLY_BOUND" if all(checks.values()) else "UNDERREPRESENTED",
            "checks": checks, "candidate_projection": projection,
            "conditioning_applicability": conditioning,
            "therapy_applicability": therapy,
            "canonical_identity_promoted": False}


def linked_relation_search_only_eligibility_v1_2(link: dict[str, Any], target: dict[str, Any],
                                                   concepts: dict[str, Any],
                                                   blueprint_concept_ids: list[str] | None = None) -> tuple[str, str]:
    """Default-deny search-only phrase eligibility after V1.2 binding only."""
    if _unsafe(link["linked_relation_phrase"]):
        return "REJECTED", "LEXICAL_SAFETY_REJECTION"
    binding = assess_linked_relation_v1_2(link, target, concepts, blueprint_concept_ids)
    if binding["state"] == "STRUCTURALLY_BOUND":
        return "SEARCH_ONLY_EXPANSION", "LINKED_RELATION_V1_2_ALL_APPLICABLE_ROLES_BOUND"
    return "UNRESOLVED", "LINKED_RELATION_V1_2_MANDATORY_ROLE_UNDERREPRESENTED"
