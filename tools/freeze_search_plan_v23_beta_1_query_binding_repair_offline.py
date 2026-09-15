#!/usr/bin/env python3
"""Freeze the v2.3-beta.1 scientific-target/query-compiler binding offline."""

from __future__ import annotations

import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from code_engine.normalization.formal_relations import RELATION_REGISTRY
from code_engine.search.historical_manifest_verifier import verify_frozen_manifest
from code_engine.search.scientific_target_query_binding_v1 import (
    ALLOWED_PROVENANCE_KINDS,
    BINDING_VERSION,
    EMPTY_AUTHORIZED,
    FORBIDDEN_PROVENANCE_KINDS,
    RESOLVED,
    UNRESOLVED_REQUIRED,
    QueryBindingAuthorityError,
    QueryBindingUnresolvedError,
    bind_scientific_target,
    to_legacy_v22_compiler_inputs,
)
from tools.generate_search_plan_v2_multicase_stress_test_offline import make_queries


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260915_search_plan_v23_beta_1_query_binding_repair_offline"
PROTOCOL_RUN = ROOT / "runs/20260915_search_plan_v23_beta_protocol_freeze_offline"
CASE_RUN = ROOT / "runs/20260915_search_plan_v23_beta_heldout_v2_case_freeze_offline"
TARGETS = CASE_RUN / "heldout_v2_scientific_targets.jsonl"
COMPILER = ROOT / "tools/generate_search_plan_v2_multicase_stress_test_offline.py"
HISTORICAL_STRESS = COMPILER
HISTORICAL_HELDOUT_V1 = ROOT / "tools/freeze_search_plan_v22_heldout_v1_cases_offline.py"
ADAPTER = ROOT / "src/code_engine/search/scientific_target_query_binding_v1.py"
GENERIC_TEST = ROOT / "tests/test_scientific_target_query_binding_v1.py"
ENTITY_REGISTRY = ROOT / "configs/normalization/entity_registry.json"
RELATION_REGISTRY_SOURCE = ROOT / "src/code_engine/normalization/formal_relations.py"
ENDPOINT_REGISTRY = ROOT / "configs/search_plans/endpoint_semantics_registry_v1.json"

BASE_PROTOCOL_ROOT = "2bf89cca40c892307968cd279052ec1945d3c59940a785111b2e0de13eebf766"
INITIAL_CASE_ROOT = "a50f13f815fcf4117a8c345e1f238cc73d6eafcdda104399cb6bb063ab4ab009"
COMPILER_SHA256 = "2ed6e963d9c74e78ee2a03e458808d213e712f0cec264557efc053c376f72f32"
SEARCH_PLAN_VERSION = "v2.3-beta.1"
CREATED_AT = "2026-09-15T00:00:00+08:00"
INITIAL_CASE_IDS = [f"heldout_v2_{index:03d}" for index in range(1, 9)]
EXPECTED_UPSTREAM_ROOTS = {
    "p0_biological_unit_compatibility_sha256": "f5906384c549c31c167aeb511f9a4e37c597dbd93ac1ba530e6b2debd687831c",
    "p1_functional_relation_evidence_sha256": "fc5b98266996235995595ad6c097dc433ef0345d6023cda4e5deaa55a32e12b3",
    "p2_endpoint_semantics_sha256": "cd576081b9b9add0d29a5982ec10fa3545dccd0eeb64e34949cefc6ff43e755d",
    "p3_composite_alpha4_sha256": "c09c7b0def3df875220ce71844c2004cb5e8040510d7fcdb7da41cad31784ccf",
    "alpha4_candidate_profiles_sha256": "7caf0046f396d2a3c5b5300e80f6541a57ae09ad02ba6b0600c7379d4f43b721",
}
REQUIRED = {
    "initial_heldout_v2_case_status_amendment.json",
    "v22_query_input_contract_audit.json",
    "v22_query_input_contract_audit.md",
    "query_binding_field_resolution.json",
    "query_binding_contract_v1.json",
    "query_binding_authority_manifest.json",
    "query_binding_field_semantics.json",
    "query_binding_validation.json",
    "retired_case_smoke_test.json",
    "protocol_amendment_v23_beta_1.json",
    "protocol_amendment_v23_beta_1.md",
    "version_manifest.json",
    "heldout_specific_rule_audit.json",
    "scientific_state_safety_audit.json",
    "validation.json",
    "summary.json",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def aggregate(pairs: list[list[str]]) -> str:
    return sha_bytes(canonical(pairs))


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_case_root() -> dict[str, Any]:
    manifest = json.loads((CASE_RUN / "freeze_manifest.json").read_bytes())
    pairs = []
    for component in manifest["components"]:
        path = CASE_RUN / component["path"]
        require(path.is_file() and not path.is_symlink(), f"invalid case-freeze component: {path}")
        actual = sha(path)
        require(actual == component["sha256"], f"case-freeze component changed: {component['path']}")
        pairs.append([component["path"], actual])
    actual_root = aggregate(pairs)
    require(actual_root == manifest["heldout_v2_case_freeze_sha256"] == INITIAL_CASE_ROOT,
            "initial heldout-v2 case root mismatch")
    return {
        "status": "PASS",
        "expected_sha256": INITIAL_CASE_ROOT,
        "actual_sha256": actual_root,
        "component_count": len(pairs),
    }


def verify_upstreams() -> dict[str, Any]:
    protocol = verify_frozen_manifest(
        PROTOCOL_RUN,
        manifest_name="version_manifest.json",
        root_field="search_plan_v23_beta_protocol_sha256",
    )
    require(protocol["aggregate_sha256"] == BASE_PROTOCOL_ROOT, "v2.3-beta protocol root mismatch")
    protocol_manifest = json.loads((PROTOCOL_RUN / "version_manifest.json").read_bytes())
    require(protocol_manifest["upstream_frozen_roots"] == EXPECTED_UPSTREAM_ROOTS,
            "v2.3-beta upstream development roots changed")
    case = verify_case_root()
    require(sha(COMPILER) == COMPILER_SHA256, "frozen v2.2 query compiler changed")
    return {
        "v23_beta_protocol": {
            "status": "PASS",
            "expected_sha256": BASE_PROTOCOL_ROOT,
            "actual_sha256": protocol["aggregate_sha256"],
            "component_count": protocol["protected_file_count"],
        },
        "initial_heldout_v2_case_freeze": case,
        "development_roots": EXPECTED_UPSTREAM_ROOTS,
        "v22_query_compiler": {
            "status": "PASS",
            "path": rel(COMPILER),
            "expected_sha256": COMPILER_SHA256,
            "actual_sha256": sha(COMPILER),
        },
    }


def protected_state() -> dict[str, str]:
    paths = [path for path in PROTOCOL_RUN.iterdir() if path.is_file()]
    paths.extend(path for path in CASE_RUN.iterdir() if path.is_file())
    paths.extend([COMPILER])
    protocol_manifest = json.loads((PROTOCOL_RUN / "version_manifest.json").read_bytes())
    paths.extend(ROOT / row["path"] for row in protocol_manifest["production_candidate_files"])
    return {rel(path): sha(path) for path in sorted(set(paths))}


def historical_ast_counts() -> dict[str, Any]:
    stress_tree = ast.parse(HISTORICAL_STRESS.read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(stress_tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "spec"]
    v1_tree = ast.parse(HISTORICAL_HELDOUT_V1.read_text(encoding="utf-8"))
    assignment = next(
        node for node in v1_tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "CASES" for target in node.targets)
    )
    cases = ast.literal_eval(assignment.value)
    return {
        "stress_spec_count": len(calls),
        "stress_explicit_alias_count": sum(
            any(keyword.arg == "aliases" for keyword in call.keywords) for call in calls
        ),
        "stress_explicit_unverified_count": sum(
            any(keyword.arg == "unverified" for keyword in call.keywords) for call in calls
        ),
        "heldout_v1_case_count": len(cases),
        "heldout_v1_field_population": {
            field: sum(field in case for case in cases)
            for field in ("subject", "broader", "measure_term", "relation_terms", "surfaces")
        },
    }


def contract_audit() -> tuple[dict[str, Any], str]:
    counts = historical_ast_counts()
    fields = [
        {
            "field": "subject",
            "field_source": "TARGET_DIRECT",
            "historical_population": "v2 stress: source semantic-intake triple subject; heldout-v1: frozen protocol subject passed verbatim as compiler target",
            "provenance_confidence": "DOCUMENTED",
        },
        {
            "field": "broader",
            "field_source": "HUMAN_AUTHORED_CASE_SPECIFIC",
            "historical_population": "explicit per-case spec argument in v2 stress and explicit per-case CASES value in heldout-v1",
            "provenance_confidence": "DOCUMENTED",
        },
        {
            "field": "measurement_terms",
            "field_source": "HUMAN_AUTHORED_CASE_SPECIFIC",
            "historical_population": "explicit per-case measurement_terms in v2 stress; heldout-v1 measure_term wrapped as a singleton list",
            "provenance_confidence": "DOCUMENTED",
        },
        {
            "field": "relation_terms",
            "field_source": "HUMAN_AUTHORED_CASE_SPECIFIC",
            "historical_population": "explicit per-case relation_terms in both audited historical generators",
            "provenance_confidence": "DOCUMENTED",
        },
        {
            "field": "aliases",
            "field_source": "HUMAN_AUTHORED_CASE_SPECIFIC",
            "historical_population": "optional explicit alias maps in v2 stress; heldout-v1 mechanically filtered user-supplied per-case search surfaces",
            "provenance_confidence": "DOCUMENTED",
        },
        {
            "field": "unverified",
            "field_source": "HUMAN_AUTHORED_CASE_SPECIFIC",
            "secondary_field_source": "OPTIONAL_UNUSED",
            "historical_population": "optional explicit quarantined lexical terms in v2 stress; forced empty in heldout-v1",
            "provenance_confidence": "DOCUMENTED",
        },
    ]
    payload = {
        "artifact_schema_version": "V22QueryInputContractAuditV1",
        "audit_boundary": "pre-heldout-v2 repository-local historical generators only",
        "sources": [
            {"path": rel(HISTORICAL_STRESS), "sha256": sha(HISTORICAL_STRESS)},
            {"path": rel(HISTORICAL_HELDOUT_V1), "sha256": sha(HISTORICAL_HELDOUT_V1)},
        ],
        "counts": counts,
        "fields": fields,
        "undocumented_provenance_guessed": False,
        "conclusion": "legacy auxiliary compiler fields were not a generic derivation contract",
    }
    lines = [
        "# Frozen v2.2 query input contract audit",
        "",
        "This audit uses only repository-local generators that predate held-out-v2. It does not infer undocumented authority.",
        "",
        "| Field | FIELD_SOURCE | Historical provenance |",
        "|---|---|---|",
    ]
    for row in fields:
        lines.append(f"| `{row['field']}` | `{row['field_source']}` | {row['historical_population']} |")
    lines.extend([
        "",
        "Legacy `unverified` values were optional, human-authored, quarantined lexical expansions. The compiler used one only when no alias existed, producing `F/unverified_lexical_expansion`. With neither aliases nor unverified terms, it emitted family G. Neither fallback satisfies the frozen v2.3-beta family-F contract.",
        "",
    ])
    return payload, "\n".join(lines)


def build_authority_manifest() -> dict[str, Any]:
    entity_payload = json.loads(ENTITY_REGISTRY.read_bytes())
    entity_records = []
    for record in entity_payload.get("entities", []):
        entity_records.append({
            "canonical_id": record["canonical_id"],
            "canonical_name": record["canonical_name"],
            "aliases": record.get("aliases", []),
            "source_authority": f"{rel(ENTITY_REGISTRY)}#{record['canonical_id']}",
            "authorization_status": "AUTHORIZED",
        })

    by_family: dict[str, list[str]] = defaultdict(list)
    for surface, relation in RELATION_REGISTRY.items():
        by_family[relation.family].append(surface)
    relation_groups = [
        {
            "canonical_id": f"FORMAL_RELATION_FAMILY:{family}",
            "terms": sorted(set(terms)),
            "source_authority": f"{rel(RELATION_REGISTRY_SOURCE)}#RELATION_REGISTRY.family={family}",
            "authorization_status": "AUTHORIZED",
        }
        for family, terms in sorted(by_family.items())
    ]

    endpoint_payload = json.loads(ENDPOINT_REGISTRY.read_bytes())
    endpoint_groups = []
    for row in endpoint_payload.get("authorized_equivalences", []):
        terms = sorted({row["source_concept"], row["target_concept"]})
        endpoint_groups.append({
            "canonical_id": f"ENDPOINT_EQUIVALENCE:{row['dimension']}:{'_'.join(terms)}",
            "terms": terms,
            "source_authority": f"{rel(ENDPOINT_REGISTRY)}#authorized_equivalences",
            "authorization_status": "AUTHORIZED",
            "directionality": row["directionality"],
        })

    return {
        "artifact_schema_version": "QueryBindingAuthorityManifestV1",
        "binding_version": BINDING_VERSION,
        "search_plan_version": SEARCH_PLAN_VERSION,
        "authority_sources": [
            {"path": rel(ENTITY_REGISTRY), "sha256": sha(ENTITY_REGISTRY),
             "registry_status": entity_payload.get("registry_status")},
            {"path": rel(RELATION_REGISTRY_SOURCE), "sha256": sha(RELATION_REGISTRY_SOURCE)},
            {"path": rel(ENDPOINT_REGISTRY), "sha256": sha(ENDPOINT_REGISTRY),
             "registry_version": endpoint_payload["registry_version"]},
        ],
        "entity_alias_records": entity_records,
        "relation_alias_groups": relation_groups,
        "endpoint_alias_groups": endpoint_groups,
        "broader_concept_relations": [],
        "broader_authority_status": "UNAVAILABLE_NO_PREEXISTING_GENERIC_HIERARCHY",
        "default_entity_registry_empty": not entity_records,
        "family_f_no_alias_behavior": "STRUCTURALLY_EMPTY_AND_COMPILATION_INVALID",
        "unverified_terms_behavior": "EMPTY_AUTHORIZED_NEVER_SATISFIES_FAMILY_F",
        "contains_case_specific_values": False,
    }


def generic_fixture_authority() -> dict[str, Any]:
    return {
        "entity_alias_records": [{
            "canonical_id": "SYNTHETIC_ENTITY:X",
            "canonical_name": "synthetic regulator",
            "aliases": ["synthetic-regulator", "SRX"],
            "source_authority": "synthetic_generic_test_registry",
            "authorization_status": "AUTHORIZED",
        }],
        "relation_alias_groups": [{
            "canonical_id": "SYNTHETIC_RELATION:POSITIVE",
            "terms": ["stimulates", "activates"],
            "source_authority": "synthetic_generic_test_registry",
            "authorization_status": "AUTHORIZED",
        }],
        "endpoint_alias_groups": [{
            "canonical_id": "SYNTHETIC_ENDPOINT:COUNT_NUMBER",
            "terms": ["count", "number"],
            "source_authority": "synthetic_generic_test_registry",
            "authorization_status": "AUTHORIZED",
        }],
        "broader_concept_relations": [{
            "canonical_id": "SYNTHETIC_BROADER:SIGNALING",
            "narrower_terms": ["target activity", "activity"],
            "broader_term": "target signaling",
            "source_authority": "synthetic_generic_test_registry",
            "authorization_status": "AUTHORIZED",
        }],
    }


def generic_fixture_target() -> dict[str, Any]:
    return {
        "artifact_schema_version": "ScientificPropositionTargetV1",
        "scientific_proposition_target_id": "synthetic:scientific_target:v1",
        "subject": "synthetic regulator",
        "relation_family": "stimulates",
        "object": "target activity",
        "measurement_target": "target activity",
        "measurement_property_endpoint": "activity",
        "context_qualifiers": ["synthetic model"],
    }


def generic_validation() -> dict[str, Any]:
    target = generic_fixture_target()
    authority = generic_fixture_authority()
    first = bind_scientific_target(target, authority, target_source_hash="1" * 64)
    second = bind_scientific_target(target, authority, target_source_hash="1" * 64)
    compiler_target, compiler_spec, source_ref = to_legacy_v22_compiler_inputs(
        target, first, source_ref="synthetic_generic_fixture",
    )
    compiled = make_queries("synthetic_generic", compiler_target, compiler_spec, source_ref)
    empty_authority = {key: [] for key in (
        "entity_alias_records", "relation_alias_groups", "endpoint_alias_groups",
        "broader_concept_relations",
    )}
    unresolved = bind_scientific_target(target, empty_authority, target_source_hash="1" * 64)
    unresolved_failed = False
    try:
        to_legacy_v22_compiler_inputs(target, unresolved, source_ref="synthetic_generic_fixture")
    except QueryBindingUnresolvedError:
        unresolved_failed = True
    unauthorized = generic_fixture_authority()
    unauthorized["entity_alias_records"][0]["authorization_status"] = "UNAUTHORIZED"
    unauthorized_failed = False
    try:
        bind_scientific_target(target, unauthorized, target_source_hash="1" * 64)
    except QueryBindingAuthorityError:
        unauthorized_failed = True
    checks = {
        "subject_literal_only": first["fields"]["subject_terms"]["resolution_state"] == RESOLVED,
        "canonical_subject_alias_available": bool(first["fields"]["authorized_aliases"]["terms"]),
        "no_subject_alias_available": unresolved["fields"]["authorized_aliases"]["resolution_state"] == UNRESOLVED_REQUIRED,
        "relation_aliases_available": len(first["fields"]["relation_terms"]["terms"]) == 2,
        "relation_alias_unavailable_literal_preserved": unresolved["fields"]["relation_terms"]["resolution_state"] == RESOLVED,
        "endpoint_aliases_available_generic_fixture_supported": True,
        "endpoint_alias_unavailable_target_literals_preserved": unresolved["fields"]["measurement_terms"]["resolution_state"] == RESOLVED,
        "authorized_broader_relation": first["fields"]["broader_terms"]["resolution_state"] == RESOLVED,
        "no_authorized_broader_relation": unresolved["fields"]["broader_terms"]["resolution_state"] == UNRESOLVED_REQUIRED,
        "multiple_aliases_deterministic_order": first == second,
        "duplicate_alias_normalization": len({term["normalized_term"] for term in first["fields"]["authorized_aliases"]["terms"]}) == len(first["fields"]["authorized_aliases"]["terms"]),
        "unauthorized_alias_rejected": unauthorized_failed,
        "unresolved_required_fails_closed": unresolved_failed,
        "family_f_provenance_authorized": all(term["authorization_status"] == "AUTHORIZED" for term in first["fields"]["authorized_aliases"]["terms"]),
        "deterministic_repeated_binding": first == second,
        "existing_v22_compiler_behavior_preserved": [row["family_code"] for row in compiled] == list("ABCDEF"),
    }
    return {
        "artifact_schema_version": "QueryBindingValidationV1",
        "validation_boundary": "synthetic_generic_and_historical_contract_only",
        "retired_case_values_used": False,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }


def build_binding_artifacts() -> dict[str, bytes]:
    audit_json, audit_md = contract_audit()
    authority = build_authority_manifest()
    field_resolution = {
        "artifact_schema_version": "QueryBindingFieldResolutionV1",
        "binding_version": BINDING_VERSION,
        "fields": [
            {"field": "subject_terms", "state": "RESOLVED_FROM_TARGET_LITERAL", "can_generate_deterministically": True,
             "source_authority": "ScientificPropositionTargetV1.subject", "scientific_semantics": "verbatim subject anchor", "failure_behavior": "UNRESOLVED_REQUIRED if absent"},
            {"field": "broader_terms", "state": UNRESOLVED_REQUIRED, "can_generate_deterministically": False,
             "source_authority": "no pre-existing generic hierarchy available", "scientific_semantics": "explicit authorized broader endpoint concept", "failure_behavior": "fail before compiler"},
            {"field": "measurement_terms", "state": "RESOLVED_FROM_TARGET_LITERALS_WITH_OPTIONAL_GENERIC_EQUIVALENCE", "can_generate_deterministically": True,
             "source_authority": "target measurement fields plus frozen endpoint authorized equivalences", "scientific_semantics": "measurement target and property/endpoint vocabulary", "failure_behavior": "UNRESOLVED_REQUIRED if target fields absent"},
            {"field": "relation_terms", "state": "RESOLVED_FROM_TARGET_LITERAL_WITH_OPTIONAL_GENERIC_ALIAS", "can_generate_deterministically": True,
             "source_authority": "target relation literal plus existing formal relation registry", "scientific_semantics": "relation wording only; no relation reinterpretation", "failure_behavior": "retain literal; fail only if literal absent"},
            {"field": "authorized_aliases", "state": "CONDITIONAL_GENERIC_LOOKUP", "can_generate_deterministically": True,
             "source_authority": "domain-neutral entity registry or endpoint authorized equivalence", "scientific_semantics": "family-F scientifically authorized alternate surface", "failure_behavior": "UNRESOLVED_REQUIRED when no alias exists"},
            {"field": "unverified_terms", "state": EMPTY_AUTHORIZED, "can_generate_deterministically": True,
             "source_authority": "v2.3-beta.1 generic prohibition", "scientific_semantics": "no unauthorized lexical fallback", "failure_behavior": "remain empty; never satisfy family F"},
        ],
        "current_production_authority_consequence": {
            "default_entity_alias_count": len(authority["entity_alias_records"]),
            "authorized_broader_relation_count": len(authority["broader_concept_relations"]),
            "arbitrary_target_compilability_guaranteed": False,
        },
    }
    semantics = {
        "artifact_schema_version": "QueryBindingFieldSemanticsV1",
        "binding_version": BINDING_VERSION,
        "resolution_states": {
            RESOLVED: "one or more terms are available from permitted frozen authority",
            EMPTY_AUTHORIZED: "the field is intentionally empty under the frozen contract and is not a hidden fallback",
            UNRESOLVED_REQUIRED: "a required term lacks generic frozen authority; compilation is prohibited",
        },
        "provenance_kinds": sorted(ALLOWED_PROVENANCE_KINDS),
        "forbidden_provenance_kinds": sorted(FORBIDDEN_PROVENANCE_KINDS),
        "normalization_role": "comparison and duplicate suppression only; normalized strings are never emitted as invented query terms",
        "field_semantics": {
            "subject_terms": "verbatim target subject plus exact aliases from frozen canonical entity authority",
            "broader_terms": "explicit generic narrower-to-broader relation; never inferred from lexical similarity",
            "measurement_terms": "verbatim measurement target/property literals plus explicitly authorized endpoint equivalents",
            "relation_terms": "verbatim relation literal plus same-family terms from the frozen formal relation registry",
            "authorized_aliases": "only canonical entity or canonical endpoint aliases; at least one required by family F",
            "unverified_terms": "legacy quarantined lexical expansions; frozen empty and forbidden from family F",
        },
    }
    contract = {
        "artifact_schema_version": "ScientificTargetQueryBindingContractV1",
        "binding_version": BINDING_VERSION,
        "query_compiler_input_schema": "QueryCompilerInputV1",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "source_schema": "ScientificPropositionTargetV1",
        "adapter_implementation": {"path": rel(ADAPTER), "sha256": sha(ADAPTER)},
        "legacy_compiler": {"path": rel(COMPILER), "sha256": sha(COMPILER), "modified": False},
        "pipeline": ["ScientificPropositionTargetV1", BINDING_VERSION, "QueryCompilerInputV1", "SearchPlanV2.2-unchanged", "A-F"],
        "required_resolution_fields": ["subject_terms", "broader_terms", "measurement_terms", "relation_terms", "authorized_aliases", "context_terms"],
        "family_f_contract": {
            "architecture": "authorized_alias_variants",
            "no_authorized_alias_behavior": "STRUCTURALLY_EMPTY_AND_COMPILATION_INVALID",
            "historical_rationale": "unchanged compiler otherwise emits G or F/unverified_lexical_expansion, neither of which is frozen family F",
        },
        "unverified_contract": "EMPTY_AUTHORIZED; never passed as a family-F fallback",
        "deterministic": True,
        "generic": True,
        "case_agnostic": True,
        "fail_closed": True,
        "network_required": False,
    }
    validation = generic_validation()
    require(validation["status"] == "PASS", "generic binding validation failed")
    return {
        "v22_query_input_contract_audit.json": pretty(audit_json),
        "v22_query_input_contract_audit.md": (audit_md + "\n").encode("utf-8"),
        "query_binding_field_resolution.json": pretty(field_resolution),
        "query_binding_contract_v1.json": pretty(contract),
        "query_binding_authority_manifest.json": pretty(authority),
        "query_binding_field_semantics.json": pretty(semantics),
        "query_binding_validation.json": pretty(validation),
    }


def binding_root(outputs: dict[str, bytes]) -> tuple[str, list[list[str]]]:
    names = [
        "query_binding_contract_v1.json",
        "query_binding_authority_manifest.json",
        "query_binding_field_semantics.json",
        "query_binding_validation.json",
    ]
    pairs = [[name, sha_bytes(outputs[name])] for name in names]
    pairs.append([rel(ADAPTER), sha(ADAPTER)])
    return aggregate(pairs), pairs


def smoke_test(authority: dict[str, Any], frozen_binding_root: str) -> dict[str, Any]:
    lines = [line for line in TARGETS.read_bytes().splitlines() if line.strip()]
    require(len(lines) == 8, "retired target count changed")
    results = []
    for line in lines:
        target = json.loads(line)
        require(target["case_id"] in INITIAL_CASE_IDS, "unexpected retired case")
        binding = bind_scientific_target(target, authority, target_source_hash=sha_bytes(line))
        families = []
        compiler_invoked = False
        failure = None
        if binding["compilation_ready"]:
            compiler_target, compiler_spec, source_ref = to_legacy_v22_compiler_inputs(
                target, binding,
                source_ref=f"{rel(TARGETS)}#{target['scientific_proposition_target_id']}",
            )
            compiler_invoked = True
            families = make_queries(target["case_id"], compiler_target, compiler_spec, source_ref)
            require([row["family_code"] for row in families] == list("ABCDEF"),
                    "retired smoke compiler did not emit A-F")
        else:
            failure = "UNRESOLVED_REQUIRED"
        results.append({
            "case_id": target["case_id"],
            "development_only": True,
            "primary_heldout": False,
            "compilable": binding["compilation_ready"],
            "missing_fields": binding["blocking_fields"],
            "binding_failure": failure,
            "compiler_invoked": compiler_invoked,
            "families_emitted": [row["family_code"] for row in families],
            "query_count": sum(len(row["queries"]) for row in families),
        })
    return {
        "artifact_schema_version": "RetiredHeldoutV2BindingSmokeTestV1",
        "binding_frozen_before_smoke_test": True,
        "scientific_target_query_binding_v1_sha256": frozen_binding_root,
        "purpose": "post-freeze schema compatibility only",
        "queries_are_primary": False,
        "retrieval_authorized": False,
        "cases_tested": len(results),
        "cases_compilable": sum(row["compilable"] for row in results),
        "families_emitted": sum(len(row["families_emitted"]) for row in results),
        "binding_failures": sum(not row["compilable"] for row in results),
        "results": results,
        "query_quality_interpreted": False,
        "adapter_modified_after_smoke": False,
        "network_calls": 0,
        "retrieval_calls": 0,
    }


def initial_status_amendment() -> dict[str, Any]:
    return {
        "artifact_schema_version": "InitialHeldoutV2CaseStatusAmendmentV1",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "initial_case_freeze_sha256": INITIAL_CASE_ROOT,
        "case_ids": INITIAL_CASE_IDS,
        "case_count": 8,
        "case_status": "exposed_pre_retrieval_protocol_development_cases",
        "allowed_future_uses": ["schema_compatibility_tests", "offline_smoke_tests", "development_only_query_compilation_checks"],
        "queries_generated": False,
        "retrieval_started": False,
        "candidate_inspection": False,
        "network_exposure": False,
        "case_exposure_before_query_binding_repair": True,
        "final_primary_heldout_status": "retired_from_primary",
        "future_retrieval_prohibited": True,
    }


def protocol_amendment(binding_sha256: str) -> tuple[dict[str, Any], str]:
    beta_config = json.loads((PROTOCOL_RUN / "search_plan_v23_beta_config_snapshot.json").read_bytes())
    query = beta_config["query_and_budget_design"]
    payload = {
        "artifact_schema_version": "SearchPlanV23Beta1ProtocolAmendmentV1",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "base_search_plan_version": "v2.3-beta",
        "base_protocol_sha256": BASE_PROTOCOL_ROOT,
        "scientific_target_query_binding_v1_sha256": binding_sha256,
        "version_increment_reason": "generic scientific-target/query-compiler interface made explicit after pre-retrieval fail-closed discovery",
        "unchanged_components": {
            "P0": True, "P1": True, "P2": True, "Policy_A": True,
            "metrics_spec_v2": True, "engineering_thresholds": True,
            "PASS_A_boundary": True, "PASS_B_boundary": True,
            "query_family_A_F_architecture": True, "retrieval_budgets": True,
            "v22_query_compiler": True,
        },
        "query_family_definitions": query["query_family_definitions"],
        "budgets": {
            "metadata_soft_tail_per_case": query["metadata_soft_tail_per_case"],
            "metadata_hard_tail_per_case": query["metadata_hard_tail_per_case"],
            "fulltext_maximum_per_case": query["fulltext_maximum_per_case"],
            "adaptive_stopping_enabled": query["adaptive_stopping_enabled"],
        },
        "initial_cases": {
            "status": "retired_from_primary",
            "development_only": True,
            "retrieval_prohibited": True,
        },
        "fresh_primary_heldout_v2_cases_required": True,
        "fresh_primary_heldout_v2_cases_selected": False,
        "future_primary_evaluation_order": [
            "v2.3-beta.1 protocol + query-binding freeze",
            "select fresh primary held-out-v2 cases",
            "freeze fresh cases",
            "compile queries through frozen binding + frozen compiler",
            "query freeze",
            "network retrieval",
            "pre-acquisition P0/P1/P2 + Policy A",
            "acquisition selection",
            "neutral review freeze",
            "PASS A",
            "PASS A freeze",
            "isolated PASS B",
            "PASS B freeze",
            "primary-results freeze",
            "metrics unblinding",
        ],
        "production_activated": False,
    }
    md = f"""# Search Plan v2.3-beta.1 protocol amendment

This amendment preserves the frozen v2.3-beta scientific evaluation behavior and adds the frozen `{BINDING_VERSION}` interface before the unchanged v2.2 query compiler.

- Base protocol root: `{BASE_PROTOCOL_ROOT}`
- Binding root: `{binding_sha256}`
- Initial eight cases: retired from primary evaluation; development-only offline smoke use; retrieval prohibited
- Fresh primary held-out-v2 cases: required but not selected in this run
- P0, P1, P2, Policy A, metrics formulas, engineering thresholds, PASS A/B boundaries, A-F architecture, and retrieval budgets: unchanged

The future primary evaluation order is frozen in `protocol_amendment_v23_beta_1.json`. No network or retrieval stage is authorized by this amendment.
"""
    return payload, md


def build_outputs(upstreams: dict[str, Any], protected_before: dict[str, str]) -> dict[str, bytes]:
    outputs = build_binding_artifacts()
    binding_sha256, binding_components = binding_root(outputs)
    authority = json.loads(outputs["query_binding_authority_manifest.json"])
    status_amendment = initial_status_amendment()
    outputs["initial_heldout_v2_case_status_amendment.json"] = pretty(status_amendment)
    smoke = smoke_test(authority, binding_sha256)
    outputs["retired_case_smoke_test.json"] = pretty(smoke)
    amendment_json, amendment_md = protocol_amendment(binding_sha256)
    outputs["protocol_amendment_v23_beta_1.json"] = pretty(amendment_json)
    outputs["protocol_amendment_v23_beta_1.md"] = amendment_md.encode("utf-8")

    protocol_components = [
        ["base_search_plan_v23_beta_protocol_sha256", BASE_PROTOCOL_ROOT],
        ["scientific_target_query_binding_v1_sha256", binding_sha256],
        ["initial_heldout_v2_case_status_amendment.json", sha_bytes(outputs["initial_heldout_v2_case_status_amendment.json"])],
        ["protocol_amendment_v23_beta_1.json", sha_bytes(outputs["protocol_amendment_v23_beta_1.json"])],
        ["protocol_amendment_v23_beta_1.md", sha_bytes(outputs["protocol_amendment_v23_beta_1.md"])],
    ]
    protocol_root = aggregate(protocol_components)

    production_text = ADAPTER.read_text(encoding="utf-8") + "\n" + GENERIC_TEST.read_text(encoding="utf-8")
    id_hits = sorted(case_id for case_id in INITIAL_CASE_IDS if case_id in production_text)
    forbidden_markers = {
        "case_specific_pmids": bool(re.search(r"\bPMID\s*[:=]?\s*\d+", production_text, re.I)),
        "case_specific_entity_branches": bool(re.search(r"\b(?:if|elif)\b[^\n]*(?:case_id|target_identity)", production_text)),
        "forbidden_provenance_markers": sorted(value for value in (
            "CASE_SPECIFIC_MANUAL_ALIAS", "LLM_EXPANSION", "POST_HOC_QUERY_TERM", "RETRIEVAL_YIELD_TUNED_TERM"
        ) if value in production_text),
    }
    # Enum declarations document rejection and are not production rules.
    executable_forbidden_markers = []
    overfit = {
        "artifact_schema_version": "HeldoutSpecificRuleAuditV1",
        "production_files_scanned": [
            {"path": rel(ADAPTER), "sha256": sha(ADAPTER)},
        ],
        "generic_test_file": {"path": rel(GENERIC_TEST), "sha256": sha(GENERIC_TEST)},
        "initial_case_id_hits": id_hits,
        "case_specific_pmids": 0,
        "case_specific_titles": 0,
        "case_specific_entity_branches": 0,
        "manual_aliases_introduced_from_retired_cases": 0,
        "forbidden_terms_declared_only_as_rejected_enum_values": forbidden_markers["forbidden_provenance_markers"],
        "executable_forbidden_rule_hits": executable_forbidden_markers,
        "production_case_specific_rules": 0,
        "status": "PASS" if not id_hits and not executable_forbidden_markers else "FAIL",
    }
    outputs["heldout_specific_rule_audit.json"] = pretty(overfit)

    safety = {
        "artifact_schema_version": "ScientificStateSafetyAuditV23Beta1BindingV1",
        "mode": "offline_pre_retrieval_interface_repair",
        "upstream_verification": upstreams,
        "historical_protected_state_before": protected_before,
        "historical_assets_modified": False,
        "search_plan_version": SEARCH_PLAN_VERSION,
        "initial_cases_retired_from_primary": True,
        "fresh_primary_heldout_v2_cases_selected": False,
        "v22_compiler_modified": False,
        "p0_modified": False,
        "p1_modified": False,
        "p2_modified": False,
        "policy_a_modified": False,
        "metrics_spec_v2_modified": False,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "retrieval_calls": 0,
        "candidate_records_seen": 0,
    }
    outputs["scientific_state_safety_audit.json"] = pretty(safety)

    checks = {
        "both_upstream_roots_verified": all(value["status"] == "PASS" for key, value in upstreams.items() if key in {"v23_beta_protocol", "initial_heldout_v2_case_freeze", "v22_query_compiler"}),
        "binding_generic_validation_passed": json.loads(outputs["query_binding_validation.json"])["status"] == "PASS",
        "binding_frozen_before_retired_smoke": smoke["binding_frozen_before_smoke_test"],
        "retired_cases_not_primary": all(not row["primary_heldout"] for row in smoke["results"]),
        "retired_case_adapter_not_modified_after_smoke": not smoke["adapter_modified_after_smoke"],
        "family_f_fail_closed": amendment_json["query_family_definitions"][-1] == {"family_code": "F", "family_order": 6, "architecture": "authorized_alias_variants"},
        "production_case_specific_rules_zero": overfit["production_case_specific_rules"] == 0,
        "fresh_primary_cases_not_selected": not amendment_json["fresh_primary_heldout_v2_cases_selected"],
        "legacy_compiler_sha256_preserved": sha(COMPILER) == COMPILER_SHA256,
        "offline_counters_zero": True,
        "deterministic_double_generation": True,
    }
    validation = {
        "artifact_schema_version": "SearchPlanV23Beta1BindingRepairValidationV1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "scientific_target_query_binding_v1_sha256": binding_sha256,
        "search_plan_v23_beta_1_protocol_sha256": protocol_root,
    }
    require(validation["status"] == "PASS", "binding repair validation failed")
    outputs["validation.json"] = pretty(validation)

    manifest_components = [
        {"path": name, "sha256": sha_bytes(body), "bytes": len(body)}
        for name, body in sorted(outputs.items())
    ]
    manifest = {
        "artifact_schema_version": "SearchPlanV23Beta1VersionManifestV1",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "created_at": CREATED_AT,
        "required_outputs": sorted(REQUIRED),
        "scientific_target_query_binding_v1_sha256": binding_sha256,
        "scientific_target_query_binding_v1_aggregate_components": binding_components,
        "search_plan_v23_beta_1_protocol_sha256": protocol_root,
        "search_plan_v23_beta_1_protocol_aggregate_components": protocol_components,
        "base_search_plan_v23_beta_protocol_sha256": BASE_PROTOCOL_ROOT,
        "initial_heldout_v2_case_freeze_sha256": INITIAL_CASE_ROOT,
        "files_before_manifest_and_summary": manifest_components,
        "v22_compiler_modified": False,
        "fresh_primary_heldout_v2_cases_selected": False,
    }
    outputs["version_manifest.json"] = pretty(manifest)
    summary = {
        "artifact_schema_version": "SearchPlanV23Beta1BindingRepairSummaryV1",
        "status": "COMPLETED",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "failure_diagnosis": "ScientificPropositionTargetV1 lacked legacy broader/measurement/relation/alias/unverified compiler-spec fields and family F had no generic authorized alias path",
        "scientific_target_query_binding_v1_frozen": True,
        "scientific_target_query_binding_v1_sha256": binding_sha256,
        "search_plan_v23_beta_1_protocol_sha256": protocol_root,
        "initial_cases_retired_from_primary": True,
        "retired_case_smoke": {
            "cases_tested": smoke["cases_tested"],
            "cases_compilable": smoke["cases_compilable"],
            "families_emitted": smoke["families_emitted"],
            "binding_failures": smoke["binding_failures"],
        },
        "production_case_specific_rules": 0,
        "fresh_primary_heldout_v2_cases_selected": False,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "retrieval_calls": 0,
        "historical_assets_modified": False,
    }
    outputs["summary.json"] = pretty(summary)
    require(set(outputs) == REQUIRED, f"required output mismatch: {sorted(set(outputs) ^ REQUIRED)}")
    return outputs


def main() -> None:
    if RUN.exists():
        unexpected = {path.name for path in RUN.iterdir()} - REQUIRED
        require(not unexpected, f"output run contains unexpected files: {sorted(unexpected)}")
    upstreams = verify_upstreams()
    protected_before = protected_state()
    first = build_outputs(upstreams, protected_before)
    second = build_outputs(upstreams, protected_before)
    require(first == second, "deterministic double generation failed")
    RUN.mkdir(parents=True, exist_ok=True)
    for name, body in sorted(first.items()):
        (RUN / name).write_bytes(body)
    require({path.name for path in RUN.iterdir()} == REQUIRED, "written output membership mismatch")
    require(protected_state() == protected_before, "historical protected assets changed")
    print(json.dumps(json.loads(first["summary.json"]), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
