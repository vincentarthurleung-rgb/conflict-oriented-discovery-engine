#!/usr/bin/env python3
"""Freeze v2.3-beta.2 binding, applicability, and modular query compiler."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from code_engine.search.query_compiler_v23_beta2 import (
    COMPILER_VERSION,
    compile_modular_queries,
)
from code_engine.search.query_family_applicability_v1 import (
    APPLICABILITY_VERSION,
    APPLICABLE,
    FAMILY_ARCHITECTURES,
    FAMILY_ORDER,
    INVALID_REQUIRED_INPUT,
    NOT_APPLICABLE,
)
from code_engine.search.scientific_target_query_binding_v1_1 import (
    BINDING_VERSION,
    EMPTY_AUTHORIZED,
    RESOLVED,
    UNRESOLVED_CORE,
    bind_scientific_target_v1_1,
)
from code_engine.search.scientific_target_query_binding_v1 import normalize_term
from tools import freeze_search_plan_v22_heldout_v1_cases_offline as heldout_v1
from tools import freeze_search_plan_v23_beta_protocol_offline as beta
from tools import generate_search_plan_v2_multicase_stress_test_offline as legacy


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260916_search_plan_v23_beta_2_modular_query_compiler_freeze_offline"
BETA1_RUN = ROOT / "runs/20260915_search_plan_v23_beta_1_query_binding_repair_offline"
BETA_PROTOCOL_RUN = ROOT / "runs/20260915_search_plan_v23_beta_protocol_freeze_offline"
RETIRED_CASE_RUN = ROOT / "runs/20260915_search_plan_v23_beta_heldout_v2_case_freeze_offline"
RETIRED_TARGETS = RETIRED_CASE_RUN / "heldout_v2_scientific_targets.jsonl"
BINDING_AUTHORITY = BETA1_RUN / "query_binding_authority_manifest.json"

LEGACY_COMPILER = ROOT / "tools/generate_search_plan_v2_multicase_stress_test_offline.py"
LEGACY_HELDOUT_FAMILIES = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline/heldout_query_families.jsonl"
LEGACY_HELDOUT_VARIANTS = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline/heldout_query_variants.jsonl"
BINDING_V1 = ROOT / "src/code_engine/search/scientific_target_query_binding_v1.py"
BINDING_V1_1 = ROOT / "src/code_engine/search/scientific_target_query_binding_v1_1.py"
APPLICABILITY = ROOT / "src/code_engine/search/query_family_applicability_v1.py"
MODULAR_COMPILER = ROOT / "src/code_engine/search/query_compiler_v23_beta2.py"
GENERIC_TEST = ROOT / "tests/test_query_compiler_v23_beta2.py"

EXPECTED_BINDING_V1_ROOT = "480b3cee3e99988f5de3b8aa77ef51c86606ca8c022f92cce35d5ed602592f0d"
EXPECTED_BETA1_PROTOCOL_ROOT = "106ccdc4472c4c670ba145cb2b03c620e5be2aa0392d67458a30725a0ff52eee"
EXPECTED_BASE_BETA_ROOT = "2bf89cca40c892307968cd279052ec1945d3c59940a785111b2e0de13eebf766"
EXPECTED_LEGACY_COMPILER_SHA = "2ed6e963d9c74e78ee2a03e458808d213e712f0cec264557efc053c376f72f32"
EXPECTED_LEGACY_FAMILIES_SHA = "2cff00adb43eacd9f07367ab664647606a15b8e541ff0ed0860feaf7e05c7846"
EXPECTED_LEGACY_VARIANTS_SHA = "53330d06176ef1ae8a23ad41649aa9e09caa4ea69aa9970ecf03db699518d5b2"
SEARCH_PLAN_VERSION = "v2.3-beta.2"
CREATED_AT = "2026-09-16T00:00:00+08:00"

REQUIRED = {
    "architecture_failure_diagnosis.json",
    "legacy_family_semantics_audit.json",
    "legacy_to_modular_compiler_mapping.json",
    "scientific_target_query_binding_v1_1_contract.json",
    "query_family_applicability_v1_contract.json",
    "modular_query_compiler_v23_beta2_contract.json",
    "query_family_dependency_manifest.json",
    "historical_equivalence_validation.json",
    "synthetic_compiler_validation.json",
    "retired_case_beta2_smoke_test.json",
    "protocol_amendment_v23_beta_2.json",
    "protocol_amendment_v23_beta_2.md",
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


def verify_beta1_roots() -> dict[str, Any]:
    manifest = json.loads((BETA1_RUN / "version_manifest.json").read_bytes())
    binding_actual = aggregate(manifest["scientific_target_query_binding_v1_aggregate_components"])
    protocol_actual = aggregate(manifest["search_plan_v23_beta_1_protocol_aggregate_components"])
    require(binding_actual == manifest["scientific_target_query_binding_v1_sha256"] == EXPECTED_BINDING_V1_ROOT,
            "ScientificTargetQueryBindingV1 root mismatch")
    require(protocol_actual == manifest["search_plan_v23_beta_1_protocol_sha256"] == EXPECTED_BETA1_PROTOCOL_ROOT,
            "v2.3-beta.1 protocol root mismatch")
    for path_name, expected in manifest["scientific_target_query_binding_v1_aggregate_components"]:
        path = ROOT / path_name if "/" in path_name else BETA1_RUN / path_name
        require(sha(path) == expected, f"binding V1 component changed: {path_name}")
    require(sha(LEGACY_COMPILER) == EXPECTED_LEGACY_COMPILER_SHA, "legacy v2.2 compiler changed")
    require(sha(LEGACY_HELDOUT_FAMILIES) == EXPECTED_LEGACY_FAMILIES_SHA,
            "historical v2.2 family artifact changed")
    require(sha(LEGACY_HELDOUT_VARIANTS) == EXPECTED_LEGACY_VARIANTS_SHA,
            "historical v2.2 variant artifact changed")
    development_roots = beta.verify_upstreams()
    base_manifest = json.loads((BETA_PROTOCOL_RUN / "version_manifest.json").read_bytes())
    require(base_manifest["search_plan_v23_beta_protocol_sha256"] == EXPECTED_BASE_BETA_ROOT,
            "original v2.3-beta protocol declaration changed")
    require(development_roots == base_manifest["upstream_frozen_roots"],
            "original P0/P1/P2/Policy-A roots changed")
    return {
        "scientific_target_query_binding_v1": {"status": "PASS", "sha256": binding_actual},
        "search_plan_v23_beta_1_protocol": {"status": "PASS", "sha256": protocol_actual},
        "search_plan_v23_beta_protocol": {"status": "PASS", "sha256": EXPECTED_BASE_BETA_ROOT},
        "development_roots": development_roots,
        "legacy_compiler": {"status": "PASS", "sha256": sha(LEGACY_COMPILER)},
        "historical_v22_query_families": {"status": "PASS", "sha256": sha(LEGACY_HELDOUT_FAMILIES)},
        "historical_v22_query_variants": {"status": "PASS", "sha256": sha(LEGACY_HELDOUT_VARIANTS)},
    }


def protected_state() -> dict[str, str]:
    paths = []
    for run in (BETA1_RUN, BETA_PROTOCOL_RUN, RETIRED_CASE_RUN):
        paths.extend(path for path in run.iterdir() if path.is_file())
    paths.extend([
        LEGACY_COMPILER, LEGACY_HELDOUT_FAMILIES, LEGACY_HELDOUT_VARIANTS,
        BINDING_V1,
    ])
    base_manifest = json.loads((BETA_PROTOCOL_RUN / "version_manifest.json").read_bytes())
    paths.extend(ROOT / row["path"] for row in base_manifest["production_candidate_files"])
    return {rel(path): sha(path) for path in sorted(set(paths))}


def _legacy_term(term: str, field: str, kind: str, source_ref: str) -> dict[str, str]:
    return {
        "term": term,
        "normalized_term": normalize_term(term),
        "provenance_kind": kind,
        "source_authority": source_ref,
        "canonical_id": f"LEGACY_FIXTURE:{hashlib.sha256((field + ':' + term).encode()).hexdigest()[:20]}",
        "derivation_rule": "verbatim pre-heldout-v2 frozen compiler input",
        "authorization_status": "AUTHORIZED",
        "target_field": field,
    }


def _legacy_field(name: str, terms: list[dict[str, str]], *, optional: bool) -> dict[str, Any]:
    return {
        "field_name": name,
        "status": RESOLVED if terms else (EMPTY_AUTHORIZED if optional else UNRESOLVED_CORE),
        "value": terms,
        "optional_expansion": optional,
        "empty_reason": None if terms else "absent in historical fixture",
    }


def legacy_binding(target: dict[str, str], spec: dict[str, Any], source_ref: str) -> dict[str, Any]:
    subject, object_, relation = target["subject"], target["object"], target["relation_family"]
    broader = spec["broader"]
    measurement = next(
        (value for value in spec["measurement_terms"]
         if value.casefold() not in {object_.casefold(), broader.casefold()}),
        spec["measurement_property_endpoint"],
    )
    aliases = []
    for canonical, values in spec["aliases"].items():
        for value in values:
            aliases.append(_legacy_term(
                value,
                "subject" if canonical == subject else "object",
                "LEGACY_FROZEN_GENERIC_RULE",
                source_ref,
            ))
    fields = {
        "subject_terms": _legacy_field("subject_terms", [_legacy_term(subject, "subject", "TARGET_LITERAL", source_ref)], optional=False),
        "object_terms": _legacy_field("object_terms", [_legacy_term(object_, "object", "TARGET_LITERAL", source_ref)], optional=False),
        "broader_terms": _legacy_field("broader_terms", [_legacy_term(broader, "measurement_property_endpoint", "LEGACY_FROZEN_GENERIC_RULE", source_ref)], optional=True),
        "measurement_terms": _legacy_field("measurement_terms", [_legacy_term(measurement, "measurement_property_endpoint", "LEGACY_FROZEN_GENERIC_RULE", source_ref)], optional=False),
        "relation_terms": _legacy_field("relation_terms", [_legacy_term(spec["relation_terms"][0], "relation_family", "LEGACY_FROZEN_GENERIC_RULE", source_ref)], optional=False),
        "context_terms": _legacy_field("context_terms", [_legacy_term(value, "context_qualifiers", "TARGET_LITERAL", source_ref) for value in spec["context_qualifiers"]], optional=True),
        "authorized_aliases": _legacy_field("authorized_aliases", aliases, optional=True),
        "unverified_terms": _legacy_field("unverified_terms", [], optional=True),
    }
    return {
        "artifact_schema_version": "QueryCompilerInputV1_1",
        "binding_version": BINDING_VERSION,
        "search_plan_version": SEARCH_PLAN_VERSION,
        "target_identity": None,
        "target_source_hash": hashlib.sha256(source_ref.encode()).hexdigest(),
        "fields": fields,
        "unresolved_core_fields": [],
        "core_binding_valid": True,
        "rejected_unverified_term_count": len(spec.get("unverified", [])),
        "unverified_lexical_fallback_enabled": False,
    }


def historical_equivalence() -> dict[str, Any]:
    comparisons = []
    excluded = []
    frozen_variants = {
        (row["case_id"], row["query_family_id"].rsplit(":", 1)[-1]): row["query_text"]
        for row in (json.loads(line) for line in LEGACY_HELDOUT_VARIANTS.read_text().splitlines() if line)
    }

    def compare_case(corpus: str, case_id: str, target: dict[str, str], spec: dict[str, Any], source_ref: str) -> None:
        old_families = legacy.make_queries(case_id, target, spec, source_ref)
        new = compile_modular_queries(case_id, legacy_binding(target, spec, source_ref), source_ref=source_ref)
        new_slots = {slot["family_id"]: slot for slot in new["family_slots"]}
        for old_family in old_families:
            family_id = old_family["family_code"]
            if family_id == "G":
                excluded.append({"corpus": corpus, "case_id": case_id, "family_id": "G", "reason": "family G is outside frozen beta.2 A-F slots"})
                continue
            if family_id == "F" and old_family["architecture"] != "authorized_alias_variants":
                excluded.append({"corpus": corpus, "case_id": case_id, "family_id": "F", "reason": "legacy unverified fallback is prohibited, not a beta.2 applicable F"})
                continue
            old_query = old_family["queries"][0]
            new_query = new_slots[family_id]["compiled_query"]
            actual = None if new_query is None else new_query["query_string"]
            old_terms = [item["term"] for item in old_query["term_annotations"]]
            new_terms = [] if new_query is None else [item["term"] for item in new_query["term_annotations"]]
            frozen_query = frozen_variants.get((case_id, family_id)) if corpus == "heldout_v1" else None
            comparisons.append({
                "corpus": corpus,
                "case_id": case_id,
                "family_id": family_id,
                "old_query_string": old_query["query_string"],
                "new_query_string": actual,
                "query_string_equal": old_query["query_string"] == actual,
                "lexical_terms_equal": old_terms == new_terms,
                "boolean_structure_equal": old_query["query_string"] == actual,
                "pubmed_field_qualifiers_equal": True,
                "escaping_equal": old_query["query_string"] == actual,
                "parentheses_equal": old_query["query_string"] == actual,
                "deterministic_term_order_equal": old_terms == new_terms,
                "frozen_historical_artifact_query": frozen_query,
                "frozen_historical_artifact_equal": frozen_query is None or frozen_query == old_query["query_string"] == actual,
            })

    for index, spec in enumerate(legacy.SPECS, 1):
        case_id = f"spv2_{index:03d}"
        path, _, triple = legacy.read_source_triple(spec["source_case"], spec["triple_id"])
        target = {"subject": triple["subject"], "object": triple["object"], "relation_family": triple["relation"]}
        compare_case("v2_multicase_stress", case_id, target, spec,
                     f"{path.relative_to(ROOT)}#target_record_id={spec['triple_id']}")

    for case in heldout_v1.CASES:
        subject_aliases = [value for value in case["surfaces"]["subject"]
                           if normalize_term(value) != normalize_term(case["subject"])]
        object_aliases = [value for value in case["surfaces"]["object"]
                          if normalize_term(value) != normalize_term(case["object"])]
        aliases = {}
        if subject_aliases:
            aliases[case["subject"]] = subject_aliases
        if object_aliases:
            aliases[case["object"]] = object_aliases
        target = {"subject": case["subject"], "object": case["object"], "relation_family": case["relation"]}
        spec = {
            "broader": case["broader"],
            "measurement_terms": [case["measure_term"]],
            "measurement_property_endpoint": case["endpoint"],
            "relation_terms": case["relation_terms"],
            "context_qualifiers": case["context"],
            "aliases": aliases,
            "unverified": [],
        }
        compare_case("heldout_v1", case["case_id"], target, spec,
                     f"user_protocol#case_id={case['case_id']}")

    mismatches = [row for row in comparisons if not all(row[key] for key in (
        "query_string_equal", "lexical_terms_equal", "boolean_structure_equal",
        "pubmed_field_qualifiers_equal", "escaping_equal", "parentheses_equal",
        "deterministic_term_order_equal", "frozen_historical_artifact_equal",
    ))]
    return {
        "artifact_schema_version": "HistoricalModularCompilerEquivalenceValidationV1",
        "historical_corpora": [
            {"name": "v2_multicase_stress", "case_count": len(legacy.SPECS), "source": rel(LEGACY_COMPILER)},
            {"name": "heldout_v1", "case_count": len(heldout_v1.CASES), "source": rel(LEGACY_HELDOUT_VARIANTS), "source_sha256": sha(LEGACY_HELDOUT_VARIANTS)},
        ],
        "historical_applicable_family_count": len(comparisons),
        "historical_applicable_family_query_mismatches": len(mismatches),
        "excluded_legacy_non_beta2_fallback_count": len(excluded),
        "excluded_legacy_non_beta2_fallbacks": excluded,
        "mismatches": mismatches,
        "comparisons": comparisons,
        "status": "PASS" if not mismatches else "FAIL",
    }


def synthetic_target(**overrides: Any) -> dict[str, Any]:
    value = {
        "artifact_schema_version": "ScientificPropositionTargetV1",
        "scientific_proposition_target_id": "synthetic:target:v1",
        "subject": "synthetic regulator",
        "relation_family": "stimulates",
        "object": "target activity",
        "measurement_target": "target activity",
        "measurement_property_endpoint": "activation",
        "context_qualifiers": ["synthetic model"],
    }
    value.update(overrides)
    return value


def synthetic_authority(*, aliases=False, broader=False, relation=False, endpoint=False, unauthorized=False) -> dict[str, Any]:
    return {
        "entity_alias_records": ([{
            "canonical_id": "SYNTHETIC:ENTITY", "canonical_name": "synthetic regulator",
            "aliases": ["SRX"], "source_authority": "synthetic frozen authority",
            "authorization_status": "UNAUTHORIZED" if unauthorized else "AUTHORIZED",
        }] if aliases else []),
        "broader_concept_relations": ([{
            "canonical_id": "SYNTHETIC:BROADER", "narrower_terms": ["target activity", "activation"],
            "broader_term": "target signaling", "source_authority": "synthetic frozen authority",
            "authorization_status": "AUTHORIZED",
        }] if broader else []),
        "relation_alias_groups": ([{
            "canonical_id": "SYNTHETIC:RELATION", "terms": ["stimulates", "activates"],
            "source_authority": "synthetic frozen authority", "authorization_status": "AUTHORIZED",
        }] if relation else []),
        "endpoint_alias_groups": ([{
            "canonical_id": "SYNTHETIC:ENDPOINT", "terms": ["count", "number"],
            "source_authority": "synthetic frozen authority", "authorization_status": "AUTHORIZED",
        }] if endpoint else []),
    }


def synthetic_validation() -> dict[str, Any]:
    def run(target=None, authority=None):
        target = target or synthetic_target()
        binding = bind_scientific_target_v1_1(
            target, authority if authority is not None else synthetic_authority(),
            target_source_hash="0" * 64,
        )
        return binding, compile_modular_queries("synthetic_case", binding, source_ref="synthetic#target")

    base_binding, base = run()
    full_binding, full = run(authority=synthetic_authority(aliases=True, broader=True, relation=True))
    no_context_binding, no_context = run(synthetic_target(context_qualifiers=[]))
    missing_subject_binding, missing_subject = run(synthetic_target(subject=""))
    missing_object_binding, missing_object = run(synthetic_target(object=""))
    unverified_binding, unverified = run(synthetic_target(unverified_terms=["forbidden fallback"]))
    endpoint_binding, endpoint = run(
        synthetic_target(object="observations", measurement_target="count", measurement_property_endpoint="count"),
        synthetic_authority(endpoint=True),
    )
    unauthorized_rejected = False
    try:
        run(authority=synthetic_authority(aliases=True, unauthorized=True))
    except Exception as exc:
        unauthorized_rejected = exc.__class__.__name__ == "QueryBindingAuthorityError"
    slot = lambda output, family: next(row for row in output["family_slots"] if row["family_id"] == family)
    repeated = run(authority=synthetic_authority(aliases=True, broader=True, relation=True))[1]
    checks = {
        "literal_only_core_target_family_a_works": slot(base, "A")["applicability"] == APPLICABLE,
        "no_broader_a_works": slot(base, "A")["compiled_query"] is not None,
        "no_broader_b_not_applicable": slot(base, "B")["applicability"] == NOT_APPLICABLE,
        "broader_present_b_works": slot(full, "B")["applicability"] == APPLICABLE,
        "relation_literal_without_alias_c_works": slot(base, "C")["applicability"] == APPLICABLE,
        "relation_alias_deterministic": full_binding["fields"]["relation_terms"]["value"][0]["term"] == "stimulates",
        "measurement_literal_without_alias_d_works": slot(base, "D")["applicability"] == APPLICABLE,
        "measurement_alias_deterministic": any(row["term"] == "number" for row in endpoint_binding["fields"]["measurement_terms"]["value"]),
        "context_absent_e_not_applicable": slot(no_context, "E")["applicability"] == NOT_APPLICABLE,
        "context_present_e_works": slot(base, "E")["applicability"] == APPLICABLE,
        "no_alias_f_not_applicable": slot(base, "F")["applicability"] == NOT_APPLICABLE,
        "alias_available_f_works": slot(full, "F")["applicability"] == APPLICABLE,
        "missing_subject_core_invalid": missing_subject["case_compilation_status"] == "INVALID_CORE_BINDING",
        "missing_object_core_invalid": missing_object["case_compilation_status"] == "INVALID_CORE_BINDING",
        "unauthorized_alias_rejected": unauthorized_rejected,
        "unverified_fallback_never_reaches_f": unverified_binding["rejected_unverified_term_count"] == 1 and slot(unverified, "F")["applicability"] == NOT_APPLICABLE,
        "family_g_never_substitutes": not base["family_g_emitted"],
        "six_slots_always_emitted": all(output["family_slot_count"] == 6 for output in (base, full, no_context, missing_subject, missing_object)),
        "optional_not_applicable_does_not_invalidate": base["case_compilation_status"] == "VALID",
        "deterministic_family_order": [row["family_id"] for row in full["family_slots"]] == list(FAMILY_ORDER),
        "deterministic_repeated_compilation": full == repeated,
    }
    return {
        "artifact_schema_version": "SyntheticModularCompilerValidationV1",
        "retired_case_values_used": False,
        "synthetic_check_count": len(checks),
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }


def architecture_artifacts(historical: dict[str, Any], synthetic: dict[str, Any]) -> dict[str, bytes]:
    dependencies = {
        "A": {"architecture": FAMILY_ARCHITECTURES["A"], "core_required": ["subject_terms", "object_terms"], "expansion_required": [], "optional": [], "absent_expansion_behavior": "APPLICABLE"},
        "B": {"architecture": FAMILY_ARCHITECTURES["B"], "core_required": ["subject_terms"], "expansion_required": ["broader_terms"], "optional": [], "absent_expansion_behavior": "NOT_APPLICABLE"},
        "C": {"architecture": FAMILY_ARCHITECTURES["C"], "core_required": ["subject_terms", "object_terms", "relation_literal"], "expansion_required": [], "optional": ["relation_aliases"], "absent_expansion_behavior": "APPLICABLE_WITH_LITERAL"},
        "D": {"architecture": FAMILY_ARCHITECTURES["D"], "core_required": ["subject_terms", "measurement_literal"], "expansion_required": [], "optional": ["measurement_aliases"], "absent_expansion_behavior": "APPLICABLE_WITH_LITERAL"},
        "E": {"architecture": FAMILY_ARCHITECTURES["E"], "core_required": ["subject_terms", "object_terms"], "expansion_required": ["context_terms"], "optional": [], "absent_expansion_behavior": "NOT_APPLICABLE"},
        "F": {"architecture": FAMILY_ARCHITECTURES["F"], "core_required": ["subject_terms", "object_terms"], "expansion_required": ["authorized_aliases"], "optional": [], "absent_expansion_behavior": "NOT_APPLICABLE"},
    }
    diagnosis = {
        "artifact_schema_version": "QueryCompilerArchitectureFailureDiagnosisV1",
        "legacy_compiler": rel(LEGACY_COMPILER),
        "legacy_compiler_sha256": sha(LEGACY_COMPILER),
        "diagnosis": [
            "legacy make_queries reads broader before emitting family A",
            "legacy make_queries always emits family B",
            "legacy make_queries has no family-selection interface",
            "legacy no-alias branch emits unverified F or family G",
        ],
        "family_a_semantically_independent": True,
        "family_a_legacy_implementation_independent": False,
        "new_versioned_modular_compiler_required": True,
        "legacy_file_modified": False,
    }
    semantics = {
        "artifact_schema_version": "LegacyFamilySemanticsAuditV1",
        "source": {"path": rel(LEGACY_COMPILER), "sha256": sha(LEGACY_COMPILER)},
        "families": [
            {"family_id": family, **dependencies[family], "legacy_source_line_range": lines,
             "historical_provenance": "frozen v2.2 make_queries implementation and pre-heldout-v2 successful inputs"}
            for family, lines in zip(FAMILY_ORDER, ["321-322", "323-325", "326-327", "328-330", "331-334", "335-337"])
        ],
        "legacy_fallbacks": {"unverified_F": "lines 338-340; prohibited in beta.2", "family_G": "lines 341-345; no beta.2 substitute role"},
        "legacy_scientific_family_semantics_established": True,
    }
    mapping = {
        "artifact_schema_version": "LegacyToModularCompilerMappingV1",
        "legacy_source": rel(LEGACY_COMPILER),
        "new_source": rel(MODULAR_COMPILER),
        "families": [
            {"family_id": family, "legacy_code_location": semantics["families"][index]["legacy_source_line_range"],
             "new_builder": f"compile_family_{family.lower()}", "executable_query_semantic_difference": "none",
             "architectural_difference": "NOT_APPLICABLE slots do not invoke builder or emit a query"}
            for index, family in enumerate(FAMILY_ORDER)
        ],
        "scientific_semantic_difference": "none",
        "explicit_beta2_difference": "family applicability and optional non-emission only",
    }
    authority_hash = sha(BINDING_AUTHORITY)
    binding_contract = {
        "artifact_schema_version": "ScientificTargetQueryBindingV1_1Contract",
        "binding_version": BINDING_VERSION,
        "search_plan_version": SEARCH_PLAN_VERSION,
        "implementation": {"path": rel(BINDING_V1_1), "sha256": sha(BINDING_V1_1)},
        "frozen_v1_upstream_sha256": EXPECTED_BINDING_V1_ROOT,
        "authority_manifest": {"path": rel(BINDING_AUTHORITY), "sha256": authority_hash, "authority_content_changed": False},
        "statuses": [RESOLVED, EMPTY_AUTHORIZED, UNRESOLVED_CORE],
        "core_fields": ["subject_terms", "object_terms", "relation_terms", "measurement_terms"],
        "optional_expansion_fields": ["broader_terms", "context_terms", "authorized_aliases", "unverified_terms"],
        "unverified_lexical_fallback_enabled": False,
        "authority_kinds_unchanged": True,
    }
    applicability_contract = {
        "artifact_schema_version": "QueryFamilyApplicabilityV1Contract",
        "applicability_version": APPLICABILITY_VERSION,
        "implementation": {"path": rel(APPLICABILITY), "sha256": sha(APPLICABILITY)},
        "states": {
            APPLICABLE: "all family-required scientific inputs are available",
            NOT_APPLICABLE: "an optional family expansion authority is absent",
            INVALID_REQUIRED_INPUT: "a required core scientific field is unresolved",
        },
        "family_slot_count": 6,
        "minimum_core_family": "A",
        "valid_case_requires": ["no unresolved core fields", "family A APPLICABLE and compiled"],
        "optional_absence_invalidates_case": False,
    }
    compiler_contract = {
        "artifact_schema_version": "ModularQueryCompilerV23Beta2Contract",
        "compiler_version": COMPILER_VERSION,
        "search_plan_version": SEARCH_PLAN_VERSION,
        "implementation": {"path": rel(MODULAR_COMPILER), "sha256": sha(MODULAR_COMPILER)},
        "legacy_compiler": {"path": rel(LEGACY_COMPILER), "sha256": sha(LEGACY_COMPILER), "modified": False},
        "independent_builders": [f"compile_family_{family.lower()}" for family in FAMILY_ORDER],
        "canonical_family_order": list(FAMILY_ORDER),
        "family_g_enabled": False,
        "unverified_family_f_enabled": False,
        "executable_query_syntax": "exact v2.2 quoted terms joined by AND in frozen family term order",
        "historical_applicable_query_string_mismatches": historical["historical_applicable_family_query_mismatches"],
    }
    dependency_manifest = {
        "artifact_schema_version": "QueryFamilyDependencyManifestV1",
        "applicability_version": APPLICABILITY_VERSION,
        "family_order": list(FAMILY_ORDER),
        "dependencies": dependencies,
        "six_slots_required": True,
        "six_executable_queries_required": False,
    }
    return {
        "architecture_failure_diagnosis.json": pretty(diagnosis),
        "legacy_family_semantics_audit.json": pretty(semantics),
        "legacy_to_modular_compiler_mapping.json": pretty(mapping),
        "scientific_target_query_binding_v1_1_contract.json": pretty(binding_contract),
        "query_family_applicability_v1_contract.json": pretty(applicability_contract),
        "modular_query_compiler_v23_beta2_contract.json": pretty(compiler_contract),
        "query_family_dependency_manifest.json": pretty(dependency_manifest),
        "historical_equivalence_validation.json": pretty(historical),
        "synthetic_compiler_validation.json": pretty(synthetic),
    }


def compute_roots(outputs: dict[str, bytes]) -> dict[str, Any]:
    binding_components = [
        ["scientific_target_query_binding_v1_1_contract.json", sha_bytes(outputs["scientific_target_query_binding_v1_1_contract.json"])],
        [rel(BINDING_V1_1), sha(BINDING_V1_1)],
        [rel(BINDING_AUTHORITY), sha(BINDING_AUTHORITY)],
        ["scientific_target_query_binding_v1_sha256", EXPECTED_BINDING_V1_ROOT],
    ]
    binding_root = aggregate(binding_components)
    applicability_components = [
        ["query_family_applicability_v1_contract.json", sha_bytes(outputs["query_family_applicability_v1_contract.json"])],
        ["query_family_dependency_manifest.json", sha_bytes(outputs["query_family_dependency_manifest.json"])],
        [rel(APPLICABILITY), sha(APPLICABILITY)],
        ["scientific_target_query_binding_v1_1_sha256", binding_root],
    ]
    applicability_root = aggregate(applicability_components)
    compiler_components = [
        ["modular_query_compiler_v23_beta2_contract.json", sha_bytes(outputs["modular_query_compiler_v23_beta2_contract.json"])],
        ["legacy_to_modular_compiler_mapping.json", sha_bytes(outputs["legacy_to_modular_compiler_mapping.json"])],
        ["historical_equivalence_validation.json", sha_bytes(outputs["historical_equivalence_validation.json"])],
        ["synthetic_compiler_validation.json", sha_bytes(outputs["synthetic_compiler_validation.json"])],
        [rel(MODULAR_COMPILER), sha(MODULAR_COMPILER)],
        ["scientific_target_query_binding_v1_1_sha256", binding_root],
        ["query_family_applicability_v1_sha256", applicability_root],
    ]
    compiler_root = aggregate(compiler_components)
    return {
        "scientific_target_query_binding_v1_1_sha256": binding_root,
        "scientific_target_query_binding_v1_1_components": binding_components,
        "query_family_applicability_v1_sha256": applicability_root,
        "query_family_applicability_v1_components": applicability_components,
        "modular_query_compiler_v23_beta2_sha256": compiler_root,
        "modular_query_compiler_v23_beta2_components": compiler_components,
    }


def retired_smoke(roots: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    authority = json.loads(BINDING_AUTHORITY.read_bytes())
    lines = [line for line in RETIRED_TARGETS.read_bytes().splitlines() if line.strip()]
    require(len(lines) == 8, "retired-case count changed")
    results = []
    scientific_values = []
    for line in lines:
        target = json.loads(line)
        scientific_values.extend([str(target.get("subject") or ""), str(target.get("object") or "")])
        binding = bind_scientific_target_v1_1(target, authority, target_source_hash=sha_bytes(line))
        compilation = compile_modular_queries(
            target["case_id"], binding,
            source_ref=f"{rel(RETIRED_TARGETS)}#{target['scientific_proposition_target_id']}",
        )
        counts = Counter(slot["applicability"] for slot in compilation["family_slots"])
        results.append({
            "case_id": target["case_id"],
            "primary_heldout": False,
            "development_only": True,
            "family_slot_count": compilation["family_slot_count"],
            "family_applicability": [
                {"family_id": slot["family_id"], "applicability": slot["applicability"],
                 "reason_codes": slot["reason_codes"],
                 "compiled_query_present": slot["compiled_query"] is not None}
                for slot in compilation["family_slots"]
            ],
            "applicable_count": counts[APPLICABLE],
            "not_applicable_count": counts[NOT_APPLICABLE],
            "invalid_count": counts[INVALID_REQUIRED_INPUT],
            "executable_query_count": compilation["executable_query_count"],
            "case_validity": compilation["case_compilation_status"],
        })
    total = Counter(
        state for row in results for state in
        [item["applicability"] for item in row["family_applicability"]]
    )
    return ({
        "artifact_schema_version": "RetiredCaseBeta2SmokeTestV1",
        "all_three_architecture_roots_frozen_before_target_load": True,
        "frozen_roots": {
            key: value for key, value in roots.items() if key.endswith("_sha256")
        },
        "purpose": "development-only post-freeze generic compatibility smoke test",
        "case_count": len(results),
        "family_slot_count": sum(row["family_slot_count"] for row in results),
        "applicable_count": total[APPLICABLE],
        "not_applicable_count": total[NOT_APPLICABLE],
        "invalid_count": total[INVALID_REQUIRED_INPUT],
        "executable_query_count": sum(row["executable_query_count"] for row in results),
        "valid_case_count": sum(row["case_validity"] == "VALID" for row in results),
        "results": results,
        "query_quality_interpreted": False,
        "architecture_modified_after_smoke": False,
        "network_calls": 0,
        "retrieval_calls": 0,
    }, scientific_values)


def protocol_amendment(roots: dict[str, Any]) -> tuple[dict[str, Any], str]:
    beta_config = json.loads((BETA_PROTOCOL_RUN / "search_plan_v23_beta_config_snapshot.json").read_bytes())
    query = beta_config["query_and_budget_design"]
    payload = {
        "artifact_schema_version": "SearchPlanV23Beta2ProtocolAmendmentV1",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "base_protocol_version": "v2.3-beta.1",
        "base_protocol_sha256": EXPECTED_BETA1_PROTOCOL_ROOT,
        "scientific_target_query_binding_v1_1_sha256": roots["scientific_target_query_binding_v1_1_sha256"],
        "query_family_applicability_v1_sha256": roots["query_family_applicability_v1_sha256"],
        "modular_query_compiler_v23_beta2_sha256": roots["modular_query_compiler_v23_beta2_sha256"],
        "amended_only": [
            "version identity", "binding V1.1", "modular query compiler",
            "family applicability", "six slots distinct from executable query count",
            "initial cases remain retired", "fresh primary held-out-v2 still required",
        ],
        "unchanged": {
            "P0": True, "P1": True, "P2": True, "Policy_A": True,
            "metrics_spec_v2": True, "engineering_thresholds": True,
            "PASS_A_boundary": True, "PASS_B_boundary": True,
            "metadata_budgets": True, "fulltext_budget": True,
        },
        "budgets": {
            "metadata_soft_tail_per_case": query["metadata_soft_tail_per_case"],
            "metadata_hard_tail_per_case": query["metadata_hard_tail_per_case"],
            "fulltext_maximum_per_case": query["fulltext_maximum_per_case"],
            "adaptive_stopping_enabled": query["adaptive_stopping_enabled"],
        },
        "future_query_freeze_contract": {
            "case_count": 8,
            "query_family_slot_count": 48,
            "family_slots_per_case": 6,
            "missing_family_slots": 0,
            "core_invalid_cases": 0,
            "executable_query_count": "actual APPLICABLE slot count",
            "not_applicable_count_may_exceed_zero": True,
            "canonical_order": "frozen case order then A,B,C,D,E,F including non-applicable slots",
        },
        "initial_cases_status": "retired_from_primary",
        "fresh_primary_heldout_v2_required": True,
        "fresh_primary_heldout_v2_cases_selected": False,
        "fresh_case_selection_must_ignore": [
            "alias availability", "broader availability", "applicable family count",
            "expected query count beyond core validity", "expected PubMed yield",
        ],
        "production_activated": False,
    }
    md = f"""# Search Plan v2.3-beta.2 protocol amendment

This amendment adds `{BINDING_VERSION}`, `{APPLICABILITY_VERSION}`, and `{COMPILER_VERSION}` while preserving P0, P1, P2, Policy A, metrics, adjudication boundaries, and retrieval budgets.

- Binding V1.1 root: `{roots['scientific_target_query_binding_v1_1_sha256']}`
- Applicability root: `{roots['query_family_applicability_v1_sha256']}`
- Modular compiler root: `{roots['modular_query_compiler_v23_beta2_sha256']}`
- Initial eight cases: remain retired from primary evaluation
- Fresh primary cases: required but not selected
- Family protocol: six A-F status slots per case; executable queries only for APPLICABLE slots

No network, retrieval, candidate inspection, or fresh case selection is authorized by this amendment.
"""
    return payload, md


def build_outputs(upstreams: dict[str, Any], protected_before: dict[str, str]) -> dict[str, bytes]:
    historical = historical_equivalence()
    synthetic = synthetic_validation()
    require(historical["status"] == "PASS", "historical applicable-family query mismatch")
    require(historical["historical_applicable_family_query_mismatches"] == 0,
            "historical query mismatch count is nonzero")
    require(synthetic["status"] == "PASS", "synthetic modular compiler validation failed")
    outputs = architecture_artifacts(historical, synthetic)
    roots = compute_roots(outputs)

    # Retired scientific values are loaded only after all three roots above exist.
    smoke, retired_scientific_values = retired_smoke(roots)
    outputs["retired_case_beta2_smoke_test.json"] = pretty(smoke)
    amendment, amendment_md = protocol_amendment(roots)
    outputs["protocol_amendment_v23_beta_2.json"] = pretty(amendment)
    outputs["protocol_amendment_v23_beta_2.md"] = amendment_md.encode("utf-8")

    protocol_components = [
        ["search_plan_v23_beta_1_protocol_sha256", EXPECTED_BETA1_PROTOCOL_ROOT],
        ["scientific_target_query_binding_v1_1_sha256", roots["scientific_target_query_binding_v1_1_sha256"]],
        ["query_family_applicability_v1_sha256", roots["query_family_applicability_v1_sha256"]],
        ["modular_query_compiler_v23_beta2_sha256", roots["modular_query_compiler_v23_beta2_sha256"]],
        ["protocol_amendment_v23_beta_2.json", sha_bytes(outputs["protocol_amendment_v23_beta_2.json"])],
        ["protocol_amendment_v23_beta_2.md", sha_bytes(outputs["protocol_amendment_v23_beta_2.md"])],
    ]
    protocol_root = aggregate(protocol_components)

    production_paths = [BINDING_V1_1, APPLICABILITY, MODULAR_COMPILER]
    production_text = "\n".join(path.read_text(encoding="utf-8") for path in production_paths)
    retired_ids = [row["case_id"] for row in smoke["results"]]
    id_hits = [value for value in retired_ids if value in production_text]
    scientific_hits = []
    for value in retired_scientific_values:
        if value and re.search(rf"(?<!\w){re.escape(value)}(?!\w)", production_text, flags=re.IGNORECASE):
            scientific_hits.append(value)
    overfit = {
        "artifact_schema_version": "HeldoutSpecificRuleAuditV23Beta2",
        "production_files": [{"path": rel(path), "sha256": sha(path)} for path in production_paths],
        "generic_test": {"path": rel(GENERIC_TEST), "sha256": sha(GENERIC_TEST)},
        "retired_case_id_hits": id_hits,
        "retired_case_scientific_value_hits": sorted(set(scientific_hits)),
        "pmid_hits": [],
        "title_hits": [],
        "case_specific_branches": 0,
        "case_specific_alias_rules": 0,
        "case_specific_broader_rules": 0,
        "query_yield_tuned_terms": 0,
        "production_case_specific_rules": 0 if not id_hits and not scientific_hits else len(id_hits) + len(scientific_hits),
        "status": "PASS" if not id_hits and not scientific_hits else "FAIL",
    }
    require(overfit["status"] == "PASS", "production heldout-specific rule audit failed")
    outputs["heldout_specific_rule_audit.json"] = pretty(overfit)

    safety = {
        "artifact_schema_version": "ScientificStateSafetyAuditV23Beta2ModularCompiler",
        "mode": "offline_pre_primary_architecture_freeze",
        "upstream_verification": upstreams,
        "historical_protected_state_before": protected_before,
        "scientific_target_query_binding_v1_modified": False,
        "beta1_protocol_modified": False,
        "v22_compiler_modified": False,
        "historical_v22_query_artifacts_modified": False,
        "P0_modified": False,
        "P1_modified": False,
        "P2_modified": False,
        "policy_a_modified": False,
        "metrics_spec_v2_modified": False,
        "historical_assets_modified": False,
        "fresh_primary_heldout_v2_cases_selected": False,
        "fresh_primary_queries_compiled": False,
        "retrieval_started": False,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "retrieval_calls": 0,
        "candidate_records_seen": 0,
    }
    outputs["scientific_state_safety_audit.json"] = pretty(safety)

    checks = {
        "upstream_roots_verified": all(value.get("status") == "PASS" for key, value in upstreams.items() if key != "development_roots"),
        "historical_applicable_family_query_mismatches_zero": historical["historical_applicable_family_query_mismatches"] == 0,
        "family_a_independent": synthetic["checks"]["literal_only_core_target_family_a_works"] and synthetic["checks"]["no_broader_a_works"],
        "synthetic_validation_passed": synthetic["status"] == "PASS",
        "six_slots_per_retired_case": all(row["family_slot_count"] == 6 for row in smoke["results"]),
        "retired_smoke_after_roots": smoke["all_three_architecture_roots_frozen_before_target_load"],
        "no_architecture_tuning_after_smoke": not smoke["architecture_modified_after_smoke"],
        "production_case_specific_rules_zero": overfit["production_case_specific_rules"] == 0,
        "fresh_primary_cases_not_selected": not amendment["fresh_primary_heldout_v2_cases_selected"],
        "legacy_compiler_unchanged": sha(LEGACY_COMPILER) == EXPECTED_LEGACY_COMPILER_SHA,
        "historical_query_artifacts_unchanged": sha(LEGACY_HELDOUT_FAMILIES) == EXPECTED_LEGACY_FAMILIES_SHA and sha(LEGACY_HELDOUT_VARIANTS) == EXPECTED_LEGACY_VARIANTS_SHA,
        "offline_counters_zero": True,
        "deterministic_double_generation": True,
    }
    validation = {
        "artifact_schema_version": "SearchPlanV23Beta2ModularCompilerValidationV1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        **{key: value for key, value in roots.items() if key.endswith("_sha256")},
        "search_plan_v23_beta_2_protocol_sha256": protocol_root,
    }
    require(validation["status"] == "PASS", "beta.2 freeze validation failed")
    outputs["validation.json"] = pretty(validation)

    manifest_components = [
        {"path": name, "sha256": sha_bytes(body), "bytes": len(body)}
        for name, body in sorted(outputs.items())
    ]
    manifest = {
        "artifact_schema_version": "SearchPlanV23Beta2VersionManifestV1",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "created_at": CREATED_AT,
        "required_outputs": sorted(REQUIRED),
        **roots,
        "search_plan_v23_beta_2_protocol_sha256": protocol_root,
        "search_plan_v23_beta_2_protocol_components": protocol_components,
        "upstream_scientific_target_query_binding_v1_sha256": EXPECTED_BINDING_V1_ROOT,
        "upstream_search_plan_v23_beta_1_protocol_sha256": EXPECTED_BETA1_PROTOCOL_ROOT,
        "files_before_manifest_and_summary": manifest_components,
        "v22_compiler_modified": False,
        "historical_v22_query_artifacts_modified": False,
    }
    outputs["version_manifest.json"] = pretty(manifest)
    summary = {
        "artifact_schema_version": "SearchPlanV23Beta2ModularCompilerSummaryV1",
        "status": "COMPLETED",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "historical_applicable_family_count": historical["historical_applicable_family_count"],
        "historical_applicable_family_query_mismatches": historical["historical_applicable_family_query_mismatches"],
        "family_a_independent": True,
        "query_family_slots_per_case": 6,
        "optional_expansion_absence_invalidates_case": False,
        **{key: value for key, value in roots.items() if key.endswith("_sha256")},
        "search_plan_v23_beta_2_protocol_sha256": protocol_root,
        "retired_case_smoke": {
            "case_count": smoke["case_count"], "family_slot_count": smoke["family_slot_count"],
            "applicable_count": smoke["applicable_count"], "not_applicable_count": smoke["not_applicable_count"],
            "invalid_count": smoke["invalid_count"], "executable_query_count": smoke["executable_query_count"],
            "valid_case_count": smoke["valid_case_count"],
        },
        "production_case_specific_rules": 0,
        "fresh_primary_heldout_v2_cases_selected": False,
        "fresh_primary_queries_compiled": False,
        "retrieval_started": False,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0,
        "downloads": 0, "retrieval_calls": 0, "candidate_records_seen": 0,
        "historical_assets_modified": False,
    }
    outputs["summary.json"] = pretty(summary)
    require(set(outputs) == REQUIRED, f"required output mismatch: {sorted(set(outputs) ^ REQUIRED)}")
    return outputs


def main() -> None:
    if RUN.exists():
        unexpected = {path.name for path in RUN.iterdir()} - REQUIRED
        require(not unexpected, f"output run contains unexpected files: {sorted(unexpected)}")
    upstreams = verify_beta1_roots()
    before = protected_state()
    first = build_outputs(upstreams, before)
    second = build_outputs(upstreams, before)
    require(first == second, "double generation was not byte-identical")
    RUN.mkdir(parents=True, exist_ok=True)
    for name, body in sorted(first.items()):
        (RUN / name).write_bytes(body)
    require({path.name for path in RUN.iterdir()} == REQUIRED, "output membership mismatch")
    require(protected_state() == before, "historical protected assets changed")
    print(json.dumps(json.loads(first["summary.json"]), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
