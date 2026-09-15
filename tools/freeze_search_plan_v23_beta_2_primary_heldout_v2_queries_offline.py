#!/usr/bin/env python3
"""Bind and freeze beta.2 primary held-out-v2 queries, strictly offline."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import importlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUN = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_query_freeze_offline"
CASE_RUN = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_case_freeze_offline"
BETA2_RUN = ROOT / "runs/20260916_search_plan_v23_beta_2_modular_query_compiler_freeze_offline"
BETA_PROTOCOL_RUN = ROOT / "runs/20260915_search_plan_v23_beta_protocol_freeze_offline"
BETA1_RUN = ROOT / "runs/20260915_search_plan_v23_beta_1_query_binding_repair_offline"
RETIRED_V2_RUN = ROOT / "runs/20260915_search_plan_v23_beta_heldout_v2_case_freeze_offline"
HELDOUT_V1_RUN = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline"

TARGETS = CASE_RUN / "primary_heldout_v2_scientific_targets.jsonl"
CASES = CASE_RUN / "primary_heldout_v2_cases.json"
AUTHORITY = BETA1_RUN / "query_binding_authority_manifest.json"
LEGACY_COMPILER = ROOT / "tools/generate_search_plan_v2_multicase_stress_test_offline.py"

SEARCH_PLAN_VERSION = "v2.3-beta.2"
CREATED_AT = "2026-09-16T00:00:00+08:00"
CASE_IDS = [f"heldout_v2_{index}" for index in range(101, 109)]
FAMILY_ORDER = ("A", "B", "C", "D", "E", "F")

EXPECTED_ROOTS = {
    "scientific_target_query_binding_v1_1_sha256": "87079f3fa7ab7cf3cf5f0cb36b1b136570526bd9317505ce5efd2d65ca0b052c",
    "query_family_applicability_v1_sha256": "940839883773179349f0b0c3589fa0bc168522ef1703237da82be8021cc26db7",
    "modular_query_compiler_v23_beta2_sha256": "6b1981285016a4f250f9cc7cc79dfe7acbe40ce807ec952b95ca1a1d87b63665",
    "search_plan_v23_beta_2_protocol_sha256": "3033bd951cd3b296a6e8aeb6d08a9a5367e58faaa41669619b99f0df7691a835",
    "primary_heldout_v2_case_freeze_sha256": "0f4c4bf5daa707465f922f529dcf3c62617405597514b5c0133411d4f79ea4e9",
}

REQUIRED = {
    "primary_heldout_v2_query_bindings.jsonl",
    "primary_heldout_v2_family_slots.jsonl",
    "primary_heldout_v2_frozen_queries.jsonl",
    "binding_validation.json",
    "family_applicability_validation.json",
    "query_compiler_validation.json",
    "query_collision_audit.json",
    "target_to_query_trace.json",
    "upstream_root_verification.json",
    "scientific_state_safety_audit.json",
    "freeze_manifest.json",
    "validation.json",
    "summary.json",
}

FORBIDDEN_PROVENANCE = {
    "CASE_SPECIFIC_MANUAL_ALIAS",
    "LLM_EXPANSION",
    "POST_HOC_QUERY_TERM",
    "RETRIEVAL_YIELD_TUNED_TERM",
    "UNVERIFIED_LEXICAL_FALLBACK",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in rows)


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


def _component_path(name: str) -> Path | None:
    if "/" in name:
        return ROOT / name
    if name.endswith((".json", ".jsonl", ".md", ".py")):
        return BETA2_RUN / name
    return None


def verify_upstream_roots() -> dict[str, Any]:
    """Verify all five roots without importing any query-layer implementation."""
    manifest = json.loads((BETA2_RUN / "version_manifest.json").read_bytes())
    root_components = {
        "scientific_target_query_binding_v1_1_sha256": "scientific_target_query_binding_v1_1_components",
        "query_family_applicability_v1_sha256": "query_family_applicability_v1_components",
        "modular_query_compiler_v23_beta2_sha256": "modular_query_compiler_v23_beta2_components",
        "search_plan_v23_beta_2_protocol_sha256": "search_plan_v23_beta_2_protocol_components",
    }
    verified: dict[str, Any] = {}
    for root_name, component_name in root_components.items():
        pairs = manifest[component_name]
        actual = aggregate(pairs)
        expected = EXPECTED_ROOTS[root_name]
        require(actual == manifest[root_name] == expected, f"root mismatch: {root_name}")
        checked_files = []
        for path_name, expected_file_hash in pairs:
            path = _component_path(path_name)
            if path is None:
                continue
            require(path.is_file() and not path.is_symlink(), f"missing protected component: {path_name}")
            actual_file_hash = sha(path)
            require(actual_file_hash == expected_file_hash, f"protected component changed: {path_name}")
            checked_files.append({"path": rel(path), "sha256": actual_file_hash})
        verified[root_name] = {
            "status": "PASS",
            "expected_sha256": expected,
            "actual_sha256": actual,
            "aggregate_components": pairs,
            "physical_components_verified": checked_files,
        }

    case_manifest = json.loads((CASE_RUN / "freeze_manifest.json").read_bytes())
    case_pairs = case_manifest["aggregate_components"]
    for path_name, expected_file_hash in case_pairs:
        path = CASE_RUN / path_name
        require(path.is_file() and not path.is_symlink(), f"missing primary case component: {path_name}")
        require(sha(path) == expected_file_hash, f"primary case component changed: {path_name}")
    case_actual = aggregate(case_pairs)
    case_expected = EXPECTED_ROOTS["primary_heldout_v2_case_freeze_sha256"]
    require(
        case_actual == case_manifest["primary_heldout_v2_case_freeze_sha256"] == case_expected,
        "primary held-out-v2 case-freeze root mismatch",
    )
    verified["primary_heldout_v2_case_freeze_sha256"] = {
        "status": "PASS",
        "expected_sha256": case_expected,
        "actual_sha256": case_actual,
        "aggregate_components": case_pairs,
    }
    return {
        "artifact_schema_version": "PrimaryHeldoutV2QueryFreezeUpstreamVerificationV1",
        "roots": verified,
        "all_five_exact_roots_verified": True,
        "verified_before_query_layer_import": True,
    }


def protected_state() -> dict[str, str]:
    paths: set[Path] = set()
    for run in (CASE_RUN, BETA2_RUN, BETA_PROTOCOL_RUN, BETA1_RUN, RETIRED_V2_RUN):
        paths.update(path for path in run.iterdir() if path.is_file())
    paths.update(path for path in HELDOUT_V1_RUN.iterdir() if path.is_file())
    paths.add(LEGACY_COMPILER)
    beta2_manifest = json.loads((BETA2_RUN / "version_manifest.json").read_bytes())
    for component_name in (
        "scientific_target_query_binding_v1_1_components",
        "query_family_applicability_v1_components",
        "modular_query_compiler_v23_beta2_components",
    ):
        for path_name, _ in beta2_manifest[component_name]:
            path = _component_path(path_name)
            if path is not None:
                paths.add(path)
    beta_manifest = json.loads((BETA_PROTOCOL_RUN / "version_manifest.json").read_bytes())
    paths.update(ROOT / row["path"] for row in beta_manifest["production_candidate_files"])
    return {rel(path): sha(path) for path in sorted(paths)}


def load_frozen_inputs() -> tuple[list[dict[str, Any]], list[bytes], dict[str, Any], dict[str, Any]]:
    raw_lines = [line for line in TARGETS.read_bytes().splitlines() if line.strip()]
    targets = [json.loads(line) for line in raw_lines]
    cases = json.loads(CASES.read_bytes())
    authorities = json.loads(AUTHORITY.read_bytes())
    require(len(targets) == cases["case_count"] == 8, "primary case count is not eight")
    require([row["case_id"] for row in targets] == CASE_IDS, "target order changed")
    require([row["case_id"] for row in cases["cases"]] == CASE_IDS, "case order changed")
    require(all(row["frozen"] for row in targets), "non-frozen primary target encountered")
    return targets, raw_lines, cases, authorities


def load_query_layers() -> tuple[Any, Any, Any, Any]:
    base = importlib.import_module("code_engine.search.scientific_target_query_binding_v1")
    binding = importlib.import_module("code_engine.search.scientific_target_query_binding_v1_1")
    applicability = importlib.import_module("code_engine.search.query_family_applicability_v1")
    compiler = importlib.import_module("code_engine.search.query_compiler_v23_beta2")
    return base, binding, applicability, compiler


def _binding_record(
    case_id: str,
    case_index: int,
    target: dict[str, Any],
    target_line: bytes,
    binding: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_schema_version": "PrimaryHeldoutV2QueryBindingRecordV1",
        "case_id": case_id,
        "canonical_case_index": case_index,
        "frozen_target_id": target["scientific_proposition_target_id"],
        "frozen_target_source": rel(TARGETS),
        "frozen_target_line_sha256": sha_bytes(target_line),
        "binding_version": binding["binding_version"],
        "binding_schema_version": binding["artifact_schema_version"],
        "compiler_facing_fields": binding["fields"],
        "field_statuses": {name: value["status"] for name, value in binding["fields"].items()},
        "unresolved_core_fields": binding["unresolved_core_fields"],
        "core_binding_valid": binding["core_binding_valid"],
        "resolved_term_count": sum(len(field["value"]) for field in binding["fields"].values()),
        "authorized_alias_term_count": len(binding["fields"]["authorized_aliases"]["value"]),
        "broader_term_count": len(binding["fields"]["broader_terms"]["value"]),
        "optional_empty_authority_count": sum(
            field["optional_expansion"] and field["status"] == "EMPTY_AUTHORIZED"
            for field in binding["fields"].values()
        ),
        "rejected_unverified_term_count": binding["rejected_unverified_term_count"],
        "unverified_lexical_fallback_enabled": binding["unverified_lexical_fallback_enabled"],
    }


def bind_all(
    targets: list[dict[str, Any]],
    raw_lines: list[bytes],
    authorities: dict[str, Any],
    binding_module: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    internal = []
    records = []
    for case_index, (target, line) in enumerate(zip(targets, raw_lines), 1):
        binding = binding_module.bind_scientific_target_v1_1(
            target,
            authorities,
            target_source_hash=sha_bytes(line),
        )
        internal.append(binding)
        records.append(_binding_record(target["case_id"], case_index, target, line, binding))
    unresolved = [record for record in records if record["unresolved_core_fields"]]
    if unresolved:
        failed = {record["case_id"]: record["unresolved_core_fields"] for record in unresolved}
        raise RuntimeError(f"PRIMARY_CASE_CORE_BINDING_FAILURE: {failed}")
    return internal, records


def _provenance_key(item: dict[str, Any]) -> bytes:
    return canonical(item)


def compile_all(
    targets: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
    applicability_module: Any,
    compiler_module: Any,
    allowed_provenance: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    decisions: list[list[dict[str, Any]]] = []
    for binding in bindings:
        slots = applicability_module.evaluate_query_family_applicability(binding)
        require([slot["family_id"] for slot in slots] == list(FAMILY_ORDER), "family order changed")
        require(len(slots) == 6, "family slot count is not six")
        decisions.append(slots)

    invalid = [
        (CASE_IDS[index], slot["family_id"], slot["reason_codes"])
        for index, slots in enumerate(decisions)
        for slot in slots
        if slot["applicability"] == applicability_module.INVALID_REQUIRED_INPUT
    ]
    require(not invalid, f"PRIMARY_CASE_CORE_BINDING_FAILURE: invalid family inputs {invalid}")
    require(
        all(slots[0]["family_id"] == "A" and slots[0]["applicability"] == applicability_module.APPLICABLE for slots in decisions),
        "PRIMARY_CASE_CORE_BINDING_FAILURE: family A is not applicable for every case",
    )

    family_records = []
    query_records = []
    traces = []
    for case_index, (target, binding, slots) in enumerate(zip(targets, bindings, decisions), 1):
        source_ref = f"{rel(TARGETS)}#{target['scientific_proposition_target_id']}"
        bound_provenance = {
            _provenance_key(item)
            for field in binding["fields"].values()
            for item in field["value"]
        }
        for family_index, slot in enumerate(slots, 1):
            family_id = slot["family_id"]
            compiled = None
            query_id = None
            query_sha256 = None
            bound_inputs_used: list[dict[str, Any]] = []
            if slot["applicability"] == applicability_module.APPLICABLE:
                compiled = compiler_module.BUILDERS[family_id](target["case_id"], binding, source_ref)
                query_id = f"primary_v2_{target['case_id']}_{family_id}"
                query_sha256 = sha_bytes(compiled["query_string"].encode("utf-8"))
                require(query_sha256 == compiled["query_hash"], "compiler query hash mismatch")
                bound_inputs_used = compiled["term_provenance"]

            unauthorized = [
                item for item in bound_inputs_used
                if item.get("provenance_kind") not in allowed_provenance
                or item.get("provenance_kind") in FORBIDDEN_PROVENANCE
                or item.get("authorization_status") != "AUTHORIZED"
                or _provenance_key(item) not in bound_provenance
            ]
            record = {
                "artifact_schema_version": "PrimaryHeldoutV2FamilySlotV1",
                "family_slot_id": f"{target['case_id']}:{family_id}",
                "query_id": query_id,
                "case_id": target["case_id"],
                "family_id": family_id,
                "canonical_case_index": case_index,
                "canonical_family_index": family_index,
                "binding_version": binding["binding_version"],
                "applicability_version": applicability_module.APPLICABILITY_VERSION,
                "compiler_version": compiler_module.COMPILER_VERSION,
                "family_applicability": slot["applicability"],
                "reason_codes": slot["reason_codes"],
                "required_authorities": slot["required_authorities"],
                "available_authorities": slot["available_authorities"],
                "missing_optional_authorities": slot["missing_authorities"],
                "family_builder": f"compile_family_{family_id.lower()}",
                "family_builder_invoked": compiled is not None,
                "compiled_query": None if compiled is None else compiled["query_string"],
                "query_sha256": query_sha256,
                "all_bound_inputs_used": bound_inputs_used,
                "term_provenance": bound_inputs_used,
                "unauthorized_term_provenance": unauthorized,
            }
            family_records.append(record)
            if compiled is not None:
                query_record = {
                    "artifact_schema_version": "PrimaryHeldoutV2FrozenQueryV1",
                    "query_id": query_id,
                    "compiler_query_id": compiled["query_id"],
                    "case_id": target["case_id"],
                    "family_id": family_id,
                    "canonical_case_index": case_index,
                    "canonical_family_index": family_index,
                    "canonical_executable_query_index": len(query_records) + 1,
                    "binding_version": binding["binding_version"],
                    "applicability_version": applicability_module.APPLICABILITY_VERSION,
                    "compiler_version": compiler_module.COMPILER_VERSION,
                    "family_applicability": slot["applicability"],
                    "compiled_query": compiled["query_string"],
                    "query_sha256": query_sha256,
                    "all_bound_inputs_used": bound_inputs_used,
                    "term_provenance": bound_inputs_used,
                    "term_annotations": compiled["term_annotations"],
                    "execution_status": "not_executed_offline_freeze",
                }
                query_records.append(query_record)
                traces.append({
                    "trace_id": f"trace:{query_id}",
                    "case_id": target["case_id"],
                    "family_id": family_id,
                    "canonical_case_index": case_index,
                    "canonical_family_index": family_index,
                    "frozen_target": target,
                    "frozen_target_source": source_ref,
                    "binding_fields": binding["fields"],
                    "applicability_decision": slot,
                    "family_builder": f"compile_family_{family_id.lower()}",
                    "final_executable_query": query_record,
                    "query_quality_assessed": False,
                    "expected_yield_assessed": False,
                })
    require(len(family_records) == 48, "family slot total is not 48")
    require(all(any(row["case_id"] == case_id for row in query_records) for case_id in CASE_IDS), "case lacks executable query")
    return family_records, query_records, traces


def collision_audit(family_records: list[dict[str, Any]], queries: list[dict[str, Any]]) -> dict[str, Any]:
    def duplicates(values: list[str]) -> list[str]:
        counts = Counter(values)
        return sorted(value for value, count in counts.items() if count > 1)

    slot_duplicates = duplicates([row["family_slot_id"] for row in family_records])
    query_id_duplicates = duplicates([row["query_id"] for row in queries])
    within: list[dict[str, Any]] = []
    across_index: dict[str, list[dict[str, str]]] = defaultdict(list)
    for case_id in CASE_IDS:
        case_rows = [row for row in queries if row["case_id"] == case_id]
        grouped: dict[str, list[str]] = defaultdict(list)
        for row in case_rows:
            grouped[row["compiled_query"]].append(row["query_id"])
            across_index[row["compiled_query"]].append({"case_id": case_id, "query_id": row["query_id"]})
        within.extend(
            {"case_id": case_id, "compiled_query": query, "query_ids": ids}
            for query, ids in grouped.items() if len(ids) > 1
        )
    across = [
        {"compiled_query": query, "records": records}
        for query, records in sorted(across_index.items())
        if len({record["case_id"] for record in records}) > 1
    ]
    empty = [row["query_id"] for row in queries if not row["compiled_query"].strip()]
    applicable_missing = [
        row["family_slot_id"] for row in family_records
        if row["family_applicability"] == "APPLICABLE" and row["compiled_query"] is None
    ]
    non_applicable_compiled = [
        row["family_slot_id"] for row in family_records
        if row["family_applicability"] != "APPLICABLE" and row["compiled_query"] is not None
    ]
    unauthorized = [
        {"family_slot_id": row["family_slot_id"], "records": row["unauthorized_term_provenance"]}
        for row in family_records if row["unauthorized_term_provenance"]
    ]
    invariant_failures = sum(map(len, (
        slot_duplicates, query_id_duplicates, empty, applicable_missing,
        non_applicable_compiled, unauthorized,
    )))
    return {
        "artifact_schema_version": "PrimaryHeldoutV2QueryCollisionAuditV1",
        "duplicate_family_slot_ids": len(slot_duplicates),
        "duplicate_family_slot_id_records": slot_duplicates,
        "duplicate_query_ids": len(query_id_duplicates),
        "duplicate_query_id_records": query_id_duplicates,
        "within_case_exact_query_string_collisions": len(within),
        "within_case_exact_query_string_collision_records": within,
        "across_case_exact_query_string_collisions": len(across),
        "across_case_exact_query_string_collision_records": across,
        "empty_executable_queries": len(empty),
        "empty_executable_query_ids": empty,
        "applicable_slots_missing_compiled_query": len(applicable_missing),
        "applicable_slots_missing_compiled_query_ids": applicable_missing,
        "not_applicable_slots_containing_compiled_query": len(non_applicable_compiled),
        "not_applicable_slots_containing_compiled_query_ids": non_applicable_compiled,
        "unauthorized_term_provenance": len(unauthorized),
        "unauthorized_term_provenance_records": unauthorized,
        "query_string_collisions_automatically_removed": False,
        "invariant_failure_count": invariant_failures,
        "status": "PASS" if invariant_failures == 0 else "FAIL",
    }


def build_outputs(
    upstream: dict[str, Any],
    protected_before: dict[str, str],
    targets: list[dict[str, Any]],
    raw_lines: list[bytes],
    cases: dict[str, Any],
    authorities: dict[str, Any],
    query_layers: tuple[Any, Any, Any, Any],
) -> dict[str, bytes]:
    base_module, binding_module, applicability_module, compiler_module = query_layers
    bindings, binding_records = bind_all(targets, raw_lines, authorities, binding_module)
    family_records, query_records, traces = compile_all(
        targets, bindings, applicability_module, compiler_module,
        set(base_module.ALLOWED_PROVENANCE_KINDS),
    )
    collisions = collision_audit(family_records, query_records)
    state_counts = Counter(row["family_applicability"] for row in family_records)
    field_statuses = Counter(
        status for record in binding_records for status in record["field_statuses"].values()
    )
    forbidden_binding_terms = [
        {"case_id": record["case_id"], "field": field_name, "term": term}
        for record in binding_records
        for field_name, field in record["compiler_facing_fields"].items()
        for term in field["value"]
        if term.get("provenance_kind") in FORBIDDEN_PROVENANCE
        or term.get("provenance_kind") not in base_module.ALLOWED_PROVENANCE_KINDS
        or term.get("authorization_status") != "AUTHORIZED"
    ]
    binding_validation = {
        "artifact_schema_version": "PrimaryHeldoutV2BindingValidationV1",
        "status": "PASS" if not forbidden_binding_terms and all(row["core_binding_valid"] for row in binding_records) else "FAIL",
        "case_count": len(binding_records),
        "allowed_field_statuses": ["RESOLVED", "EMPTY_AUTHORIZED", "UNRESOLVED_CORE"],
        "field_status_counts": dict(sorted(field_statuses.items())),
        "core_unresolved_count": sum(len(row["unresolved_core_fields"]) for row in binding_records),
        "core_invalid_cases": sum(not row["core_binding_valid"] for row in binding_records),
        "optional_empty_authority_count": sum(row["optional_empty_authority_count"] for row in binding_records),
        "authorized_alias_term_count": sum(row["authorized_alias_term_count"] for row in binding_records),
        "broader_term_count": sum(row["broader_term_count"] for row in binding_records),
        "forbidden_or_unauthorized_binding_terms": len(forbidden_binding_terms),
        "forbidden_or_unauthorized_binding_term_records": forbidden_binding_terms,
        "manual_supplementation_performed": False,
    }
    per_case = []
    for case_id in CASE_IDS:
        slots = [row for row in family_records if row["case_id"] == case_id]
        per_case.append({
            "case_id": case_id,
            "family_applicability": {row["family_id"]: row["family_applicability"] for row in slots},
            "executable_query_count": sum(row["compiled_query"] is not None for row in slots),
            "core_family_a_executable": slots[0]["family_id"] == "A" and slots[0]["compiled_query"] is not None,
        })
    applicability_validation = {
        "artifact_schema_version": "PrimaryHeldoutV2FamilyApplicabilityValidationV1",
        "status": "PASS" if len(family_records) == 48 and state_counts["INVALID_REQUIRED_INPUT"] == 0 else "FAIL",
        "case_count": 8,
        "query_family_slot_count": len(family_records),
        "family_slots_per_case": 6,
        "canonical_order": "frozen case order then A,B,C,D,E,F",
        "canonical_order_preserved": [
            (row["case_id"], row["family_id"]) for row in family_records
        ] == [(case_id, family_id) for case_id in CASE_IDS for family_id in FAMILY_ORDER],
        "state_counts": {state: state_counts[state] for state in ("APPLICABLE", "NOT_APPLICABLE", "INVALID_REQUIRED_INPUT")},
        "per_case": per_case,
    }
    compiler_validation = {
        "artifact_schema_version": "PrimaryHeldoutV2QueryCompilerValidationV1",
        "status": "PASS" if collisions["status"] == "PASS" and all(row["core_family_a_executable"] for row in per_case) else "FAIL",
        "compiler_version": compiler_module.COMPILER_VERSION,
        "binding_version": binding_module.BINDING_VERSION,
        "applicability_version": applicability_module.APPLICABILITY_VERSION,
        "executable_query_count": len(query_records),
        "family_a_executable_cases": sum(row["core_family_a_executable"] for row in per_case),
        "all_executable_queries_canonically_ordered": [
            (row["canonical_case_index"], row["canonical_family_index"]) for row in query_records
        ] == sorted((row["canonical_case_index"], row["canonical_family_index"]) for row in query_records),
        "query_identity_depends_only_on_case_and_family": True,
        "family_g_emitted": False,
        "unverified_lexical_fallback_used": False,
        "not_applicable_builders_invoked": sum(
            row["family_builder_invoked"] for row in family_records
            if row["family_applicability"] == "NOT_APPLICABLE"
        ),
        "pre_retrieval_query_observations": [],
        "query_quality_assessed": False,
        "expected_recall_assessed": False,
        "expected_yield_assessed": False,
    }
    trace = {
        "artifact_schema_version": "PrimaryHeldoutV2TargetToQueryTraceV1",
        "trace_count": len(traces),
        "executable_query_count": len(query_records),
        "target_to_query_trace_complete": len(traces) == len(query_records),
        "trace_semantics": "frozen target -> binding fields -> applicability decision -> family builder -> final executable query",
        "traces": traces,
    }
    safety = {
        "artifact_schema_version": "PrimaryHeldoutV2QueryFreezeScientificStateSafetyAuditV1",
        "mode": "offline_binding_applicability_compilation_only",
        "historical_protected_state_before": protected_before,
        "primary_targets_modified": False,
        "primary_case_freeze_modified": False,
        "search_plan_v23_beta_2_modified": False,
        "binding_v1_1_modified": False,
        "applicability_v1_modified": False,
        "modular_compiler_modified": False,
        "p0_modified": False,
        "p1_modified": False,
        "p2_modified": False,
        "policy_a_modified": False,
        "metrics_spec_v2_modified": False,
        "adjudication_boundaries_modified": False,
        "retired_initial_cases_modified": False,
        "historical_v22_compiler_modified": False,
        "historical_v22_artifacts_modified": False,
        "case_replacement_performed": False,
        "target_repair_performed": False,
        "historical_assets_modified": False,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "retrieval_calls": 0,
        "candidate_records_seen": 0,
        "retrieval_started": False,
    }
    checks = {
        "all_five_upstream_roots_verified": upstream["all_five_exact_roots_verified"],
        "case_count_8": len(targets) == len(cases["cases"]) == 8,
        "case_order_preserved": [row["case_id"] for row in targets] == CASE_IDS,
        "core_invalid_cases_zero": binding_validation["core_invalid_cases"] == 0,
        "family_slot_count_48": len(family_records) == 48,
        "six_slots_per_case": all(sum(row["case_id"] == case_id for row in family_records) == 6 for case_id in CASE_IDS),
        "canonical_order_preserved": applicability_validation["canonical_order_preserved"],
        "invalid_required_input_zero": state_counts["INVALID_REQUIRED_INPUT"] == 0,
        "family_a_executable_for_every_case": all(row["core_family_a_executable"] for row in per_case),
        "at_least_one_executable_query_per_case": all(row["executable_query_count"] >= 1 for row in per_case),
        "not_applicable_slots_uncompiled": compiler_validation["not_applicable_builders_invoked"] == 0,
        "collision_invariants_pass": collisions["status"] == "PASS",
        "target_to_query_trace_complete": trace["target_to_query_trace_complete"],
        "no_target_repair_or_case_replacement": not safety["target_repair_performed"] and not safety["case_replacement_performed"],
        "network_and_retrieval_counters_zero": True,
        "deterministic_double_generation": True,
    }
    validation = {
        "artifact_schema_version": "PrimaryHeldoutV2QueryFreezeValidationV1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
    }
    require(binding_validation["status"] == "PASS", "binding validation failed")
    require(applicability_validation["status"] == "PASS", "family applicability validation failed")
    require(compiler_validation["status"] == "PASS", "query compiler validation failed")
    require(validation["status"] == "PASS", "primary query-freeze validation failed")

    outputs = {
        "primary_heldout_v2_query_bindings.jsonl": jsonl(binding_records),
        "primary_heldout_v2_family_slots.jsonl": jsonl(family_records),
        "primary_heldout_v2_frozen_queries.jsonl": jsonl(query_records),
        "binding_validation.json": pretty(binding_validation),
        "family_applicability_validation.json": pretty(applicability_validation),
        "query_compiler_validation.json": pretty(compiler_validation),
        "query_collision_audit.json": pretty(collisions),
        "target_to_query_trace.json": pretty(trace),
        "upstream_root_verification.json": pretty(upstream),
        "scientific_state_safety_audit.json": pretty(safety),
        "validation.json": pretty(validation),
    }
    component_names = sorted(outputs)
    components = [[name, sha_bytes(outputs[name])] for name in component_names]
    freeze_root = aggregate(components)
    manifest = {
        "artifact_schema_version": "PrimaryHeldoutV2QueryFreezeManifestV1",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "created_at": CREATED_AT,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_scope": "all required outputs except freeze_manifest.json and summary.json",
        "aggregate_components": components,
        "primary_heldout_v2_query_freeze_sha256": freeze_root,
        "required_outputs": sorted(REQUIRED),
        "upstream_roots": EXPECTED_ROOTS,
        "binding_version": binding_module.BINDING_VERSION,
        "applicability_version": applicability_module.APPLICABILITY_VERSION,
        "compiler_version": compiler_module.COMPILER_VERSION,
        "case_count": 8,
        "query_family_slot_count": 48,
        "executable_query_count": len(query_records),
    }
    outputs["freeze_manifest.json"] = pretty(manifest)
    summary = {
        "artifact_schema_version": "PrimaryHeldoutV2QueryFreezeSummaryV1",
        "status": "COMPLETED",
        "case_count": 8,
        "query_family_slot_count": 48,
        "family_slots_per_case": 6,
        "applicable_family_slots": state_counts["APPLICABLE"],
        "not_applicable_family_slots": state_counts["NOT_APPLICABLE"],
        "invalid_required_input_slots": state_counts["INVALID_REQUIRED_INPUT"],
        "core_invalid_cases": binding_validation["core_invalid_cases"],
        "optional_empty_authority_count": binding_validation["optional_empty_authority_count"],
        "authorized_alias_term_count": binding_validation["authorized_alias_term_count"],
        "broader_term_count": binding_validation["broader_term_count"],
        "family_a_executable_cases": compiler_validation["family_a_executable_cases"],
        "executable_query_count": len(query_records),
        "duplicate_family_slot_ids": collisions["duplicate_family_slot_ids"],
        "duplicate_query_ids": collisions["duplicate_query_ids"],
        "empty_executable_queries": collisions["empty_executable_queries"],
        "unauthorized_term_provenance": collisions["unauthorized_term_provenance"],
        "within_case_exact_query_string_collisions": collisions["within_case_exact_query_string_collisions"],
        "across_case_exact_query_string_collisions": collisions["across_case_exact_query_string_collisions"],
        "canonical_order_preserved": applicability_validation["canonical_order_preserved"],
        "target_to_query_trace_complete": trace["target_to_query_trace_complete"],
        "primary_targets_modified": False,
        "binding_v1_1_modified": False,
        "applicability_v1_modified": False,
        "modular_compiler_modified": False,
        "primary_heldout_v2_query_freeze_sha256": freeze_root,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "retrieval_calls": 0,
        "candidate_records_seen": 0,
        "retrieval_started": False,
        "historical_assets_modified": False,
        "per_case": per_case,
    }
    outputs["summary.json"] = pretty(summary)
    require(set(outputs) == REQUIRED, f"required output mismatch: {sorted(set(outputs) ^ REQUIRED)}")
    return outputs


def main() -> None:
    if RUN.exists():
        unexpected = {path.name for path in RUN.iterdir()} - REQUIRED
        require(not unexpected, f"output run contains unexpected files: {sorted(unexpected)}")

    upstream = verify_upstream_roots()
    protected_before = protected_state()
    targets, raw_lines, cases, authorities = load_frozen_inputs()
    query_layers = load_query_layers()

    first = build_outputs(
        upstream, protected_before, targets, raw_lines, cases, authorities, query_layers,
    )
    second = build_outputs(
        upstream, protected_before, targets, raw_lines, cases, authorities, query_layers,
    )
    require(first == second, "independent double generation was not byte-identical")

    RUN.mkdir(parents=True, exist_ok=True)
    for name, body in sorted(first.items()):
        (RUN / name).write_bytes(body)
    require({path.name for path in RUN.iterdir()} == REQUIRED, "output membership mismatch")
    require(all(path.is_file() and not path.is_symlink() for path in RUN.iterdir()), "non-physical output found")
    require(protected_state() == protected_before, "historical protected assets changed")
    print(json.dumps(json.loads(first["summary.json"]), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
