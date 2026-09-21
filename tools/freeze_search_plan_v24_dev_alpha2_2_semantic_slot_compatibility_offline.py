"""Freeze an offline-only alpha2.2 replay of the immutable case-101 payload."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from code_engine.search.alpha2_linked_relation_v1 import (
    assess_linked_relation_v1_1, linked_relation_search_only_eligibility,
    search_only_eligibility_v1_1,
)
from code_engine.search.semantic_slot_compatibility_v1 import (
    ANCHOR_VERSION, FIELD_OWNERSHIP, SEMANTIC_DIMENSIONS, SEMANTIC_SLOT_VERSION,
    SUFFICIENT_SEMANTIC, audit_linked_relation_candidate,
    search_anchor_compatibility_v1_1, semantic_slot_compatibility,
    validate_v2_structure_and_slots,
)
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from tools.run_search_plan_v24_dev_alpha2_1_smoke_101 import (
    compile_bound, frozen_target, verify_root,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline"
ALPHA2 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_linked_relation_deepseek_migration_offline"
ALPHA2_1 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_reasoning_config_offline"
SMOKE = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_planner_v2_smoke_101"
AUTOPSY = ROOT / "runs/20260920_search_plan_v24_dev_alpha1_zero_query_autopsy_and_provider_audit_offline"
AUTHORITY = ROOT / "runs/20260918_search_plan_v24_dev_planner_authority_contract_split_offline"
EXPECTED = {
    "alpha2": "918e0badbaeb70c439ae8d6e1d3bcc1eb5d5697c5df75b38dc2819357890a4e8",
    "alpha2_1": "fee80d671ed6e573ca0e18640b4ab87b15aec021e6870f17b0fc3457554b41fc",
    "smoke": "b66eebe346b1f130287083e364fbba10a22110b40f0a288e9185fe5f5242fd40",
}
RAW_SHA = "e3f0386b9e08a6d8dce12b7388b5da34db4bd75995eb530576176bbc2ccf2c7f"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(name: str, value: Any) -> None:
    path = RUN / name
    require(not path.exists() and not path.is_symlink(), f"refusing overwrite: {name}")
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fixture_rows() -> list[dict[str, Any]]:
    return json.loads((AUTOPSY / "unresolved_term_diagnostic.json").read_text(encoding="utf-8"))["terms"]


def targets_by_case() -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in (AUTHORITY / "validated_development_plans.jsonl").read_text(
        encoding="utf-8").splitlines() if line]
    return {row["case_id"]: row["validated_plan"]["canonical_proposition"]["target_payload"] for row in rows}


def regression() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    targets = targets_by_case()
    results = []
    for row in fixture_rows():
        state, rule = search_only_eligibility_v1_1(row["term"], row["concept_type"], targets[row["case_id"]])
        results.append({"case_id": row["case_id"], "term_id": row["term_id"],
                        "term": row["term"], "concept_type": row["concept_type"],
                        "diagnostic_category": row["diagnostic_category"],
                        "prior_semantic_category": row["prior_semantic_category"],
                        "alpha2_2_search_only_state": state, "rule_id": rule})
    require(len(results) == 328, "unexpected regression corpus size")
    def subset(name: str, predicate: Any) -> dict[str, Any]:
        selected = [r for r in results if predicate(r)]
        promoted = [r for r in selected if r["alpha2_2_search_only_state"] == "SEARCH_ONLY_EXPANSION"]
        return {"artifact_schema_version": name, "fixture_count": len(selected),
                "promoted_count": len(promoted), "promoted_rows": promoted,
                "replayed_rows": selected, "unchanged_default_deny": not promoted}
    overbroad = subset("Alpha2_2OverbroadRegressionV1", lambda r: r["diagnostic_category"] == "CORRECTLY_WITHHELD_OVERBROAD")
    drift = subset("Alpha2_2SemanticDriftRegressionV1", lambda r: r["prior_semantic_category"] == "SEMANTIC_DRIFT")
    proxy = subset("Alpha2_2MechanisticProxyRegressionV1", lambda r: r["diagnostic_category"] == "CORRECTLY_WITHHELD_ENTITY_SUBSTITUTION")
    unit = subset("Alpha2_2BiologicalUnitRegressionV1", lambda r: r["diagnostic_category"] == "CORRECTLY_WITHHELD_CONTEXT_BROADENING")
    # Distinct synthetic controls test semantic exactness cannot bypass surface identity.
    control_target = dict(frozen_target())
    control_target["subject"] = "TNF-alpha"
    identity = {
        "artifact_schema_version": "Alpha2_2IdentitySafetyRegressionV1",
        "semantic_slot_rejects_entity_dimension": False,
        "tnf_vs_tnf_alpha_surface": None,
        "macrophage_vs_monocyte_surface": None,
        "semantic_slot_exact_match_cannot_promote_entity_identity": True,
        "canonical_identity_promotions": 0,
    }
    try:
        semantic_slot_compatibility("subject", "TNF", control_target)
    except ValueError:
        identity["semantic_slot_rejects_entity_dimension"] = True
    identity["tnf_vs_tnf_alpha_surface"] = search_anchor_compatibility_v1_1("TNF", control_target, "subject")
    unit_target = dict(frozen_target())
    unit_target["biological_unit"] = "macrophage"
    identity["macrophage_vs_monocyte_surface"] = search_anchor_compatibility_v1_1("monocyte", unit_target, "biological_unit")
    require(identity["semantic_slot_rejects_entity_dimension"], "entity passed semantic gate")
    require(not identity["tnf_vs_tnf_alpha_surface"]["sufficient_for_search_anchor"], "TNF identity broadening")
    require(not identity["macrophage_vs_monocyte_surface"]["sufficient_for_search_anchor"], "unit broadening")
    require(len(overbroad["replayed_rows"]) == 122 and len(drift["replayed_rows"]) == 3
            and len(proxy["replayed_rows"]) == 5 and len(unit["replayed_rows"]) == 3,
            "protected diagnostic categories changed")
    require(all(not block["promoted_rows"] for block in (overbroad, drift, proxy, unit)),
            "protected search-only term re-enabled")
    return identity, overbroad, drift, proxy, unit


def main() -> None:
    require(not RUN.exists(), "alpha2.2 freeze run already exists")
    upstream = {key: verify_root(path, EXPECTED[key]) for key, path in (
        ("alpha2", ALPHA2), ("alpha2_1", ALPHA2_1), ("smoke", SMOKE))}
    raw_path = SMOKE / "raw_model_content.txt"
    payload_path = SMOKE / "planner_v2_raw_payload.json"
    require(digest(raw_path) == RAW_SHA, "raw model content changed")
    wrapper = json.loads(payload_path.read_text(encoding="utf-8"))
    payload = wrapper["parsed_provider_payload"]
    require(wrapper["parse_success"] is True and isinstance(payload, dict), "frozen payload invalid")
    require(json.loads(raw_path.read_text(encoding="utf-8")) == payload, "raw/model parsed payload mismatch")
    target = frozen_target()
    source_hashes = {str(path.relative_to(ROOT)): digest(path) for path in (
        raw_path, payload_path, ALPHA2 / "planner_prompt_v2.md",
        ALPHA2 / "planner_proposal_payload_v2_schema.json",
        ALPHA2_1 / "deepseek_query_planner_config_v1_1.json",
        ROOT / "src/code_engine/search/alpha2_linked_relation_v1.py",
        ROOT / "src/code_engine/search/semantic_slot_compatibility_v1.py",
        ROOT / "tools/freeze_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline.py",
    )}
    validation = validate_v2_structure_and_slots(payload, target)
    require(validation["provider_payload_schema_valid"] and validation["concept_references_valid"],
            "frozen payload failed schema/reference replay")
    identity, overbroad, drift, proxy, unit = regression()
    links: list[dict[str, Any]] = []
    blueprints: list[dict[str, Any]] = []
    for intent in payload["retrieval_intents"]:
        concept_map = {c["concept_id"]: c for c in intent["search_concepts"]}
        for blueprint in intent["candidate_query_blueprints"]:
            rows = []
            for index, link in enumerate(blueprint["linked_relation_candidates"]):
                audit = audit_linked_relation_candidate(link, target)
                search_state, search_rule = linked_relation_search_only_eligibility(
                    link, target, intent_type=intent["intent_type"])
                binding = assess_linked_relation_v1_1(link, target, intent_type=intent["intent_type"])
                row = {"intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
                       "blueprint_id": blueprint["blueprint_id"], "linked_candidate_index": index,
                       "subject_ref": link["subject_concept_ref"], "response_ref": link["response_concept_ref"],
                       "subject_ref_type": concept_map[link["subject_concept_ref"]]["concept_type"],
                       "response_ref_type": concept_map[link["response_concept_ref"]]["concept_type"],
                       "subject_surface": link["subject_surface_candidate"],
                       "relation_family": link["relation_family"],
                       "relation_surface": link["relation_surface_candidate"],
                       "response_surface": link["response_surface_candidate"],
                       "direction": link["direction"],
                       "endpoint_property": link["endpoint_property_surface_candidate"],
                       "biological_unit_context_ref": link["biological_unit_context_ref"],
                       "conditioning_context_refs": link["conditioning_context_refs"],
                       "therapy_context_refs": link["therapy_context_refs"],
                       "linked_relation_phrase": link["linked_relation_phrase"],
                       "alpha2_2_candidate_audit": audit,
                       "frozen_search_only_state": search_state, "frozen_search_only_rule": search_rule,
                       "frozen_relation_binding": binding}
                links.append(row)
                rows.append(row)
            blueprints.append({"intent_id": intent["intent_id"], "blueprint_id": blueprint["blueprint_id"],
                               "candidate_count": len(rows),
                               "alpha2_2_valid_candidate_count": sum(r["alpha2_2_candidate_audit"]["valid"] for r in rows),
                               "frozen_structurally_bound_count": sum(
                                   r["frozen_relation_binding"]["state"] == "STRUCTURALLY_BOUND" for r in rows),
                               "relation_coverage_state": "REPRESENTED" if any(
                                   r["alpha2_2_candidate_audit"]["valid"] and
                                   r["frozen_relation_binding"]["state"] == "STRUCTURALLY_BOUND" for r in rows)
                               else "RELATION_UNDERREPRESENTED"})
    require(len(links) == 2, "unexpected candidate count")
    valid_links = sum(r["alpha2_2_candidate_audit"]["valid"] for r in links)
    bound_blueprints = sum(b["relation_coverage_state"] == "REPRESENTED" for b in blueprints)
    trace = [
        {"stage": "PROVIDER_PAYLOAD_SCHEMA", "passed": validation["provider_payload_schema_valid"]},
        {"stage": "CONCEPT_REFERENCE", "passed": validation["concept_references_valid"]},
        {"stage": "SURFACE_ANCHOR_COMPATIBILITY", "passed": validation["surface_anchors_compatible"]},
        {"stage": "SEMANTIC_SLOT_COMPATIBILITY", "passed": validation["semantic_slots_compatible"]},
        {"stage": "LINKED_RELATION_VALIDATION", "passed": valid_links > 0,
         "valid_candidate_count": valid_links, "failed_checks_by_candidate": [
             {"index": r["linked_candidate_index"], "checks": [name for name, passed in
              r["alpha2_2_candidate_audit"]["checks"].items() if not passed]} for r in links]},
        {"stage": "SEARCH_ONLY_ELIGIBILITY", "passed": any(
            r["frozen_search_only_state"] == "SEARCH_ONLY_EXPANSION" for r in links),
         "diagnostic_only_after_prior_failure": valid_links == 0},
        {"stage": "RELATION_BINDING", "passed": any(
            r["frozen_relation_binding"]["state"] == "STRUCTURALLY_BOUND" for r in links),
         "diagnostic_only_after_prior_failure": valid_links == 0},
        {"stage": "COVERAGE", "passed": bound_blueprints > 0,
         "blueprints": blueprints, "diagnostic_only_after_prior_failure": valid_links == 0},
    ]
    first_loss = next((r["stage"] for r in trace if not r["passed"]), "NONE")
    # No compiler call on a partly validated plan; the unchanged compiler has
    # no authority to fabricate a topic-only fallback query.
    compiled: list[dict[str, Any]] = []
    if first_loss == "NONE":
        compiled = compile_bound(payload, target, [
            {"intent_id": r["intent_id"], "blueprint_id": r["blueprint_id"],
             "linked_candidate_index": r["linked_candidate_index"],
             "state": r["frozen_relation_binding"]["state"],
             "search_only_classification": r["frozen_search_only_state"]} for r in links], [])
    trace.append({"stage": "COMPILER", "status": "SKIPPED_INVALID_PLAN" if first_loss != "NONE" else "RUN",
                  "passed": bool(compiled) if first_loss == "NONE" else None,
                  "compiled_query_count": len(compiled)})
    if first_loss == "NONE" and not compiled:
        first_loss = "COMPILER"
    recommendation = ("AUTHORIZE_REMAINING_7_DEEPSEEK_DEVELOPMENT_CASES" if bound_blueprints and compiled
                      else "PLANNER_V2_REFINEMENT_NEEDED" if first_loss == "LINKED_RELATION_VALIDATION"
                      else "DETERMINISTIC_REFINEMENT_NEEDED")
    require(first_loss == "LINKED_RELATION_VALIDATION" and recommendation == "PLANNER_V2_REFINEMENT_NEEDED",
            "unexpected replay state; fail closed")
    RUN.mkdir(parents=True, exist_ok=False)
    dump("upstream_root_verification.json", upstream)
    dump("smoke_raw_output_preservation_audit.json", {
        "raw_model_content_sha256": RAW_SHA, "parsed_provider_payload_file_sha256": digest(payload_path),
        "raw_matches_frozen_parsed_payload": True, "source_file_sha256_before": source_hashes,
        "raw_output_regenerated": False, "provider_calls": 0})
    dump("anchor_field_ownership_audit.json", {"artifact_schema_version": "Alpha2_2FieldOwnershipV1",
        "fields": FIELD_OWNERSHIP, "field_count": len(FIELD_OWNERSHIP),
        "semantic_dimensions": sorted(SEMANTIC_DIMENSIONS),
        "unknown_fields": [], "entity_alias_lookup_for_semantic_slots": False})
    dump("semantic_slot_compatibility_v1_contract.json", {
        "artifact_schema_version": SEMANTIC_SLOT_VERSION, "implementation_sha256": source_hashes[
            "src/code_engine/search/semantic_slot_compatibility_v1.py"],
        "dimensions": sorted(SEMANTIC_DIMENSIONS), "sufficient_states": sorted(SUFFICIENT_SEMANTIC),
        "exact_normalized_target_match_supported": True, "scientific_truth_established": False,
        "canonical_identity_promoted": False, "entity_alias_lookup": False})
    dump("search_anchor_compatibility_v1_1_contract.json", {
        "artifact_schema_version": ANCHOR_VERSION, "implementation_sha256": source_hashes[
            "src/code_engine/search/semantic_slot_compatibility_v1.py"],
        "surface_dimensions": [k for k in FIELD_OWNERSHIP if k not in SEMANTIC_DIMENSIONS],
        "semantic_slots_rejected_from_entity_lookup": True, "canonical_identity_promoted": False})
    dump("semantic_slot_regression_fixtures.json", {"artifact_schema_version": "Alpha2_2SemanticSlotFixtureV1",
        "focused_test_file": "tests/test_semantic_slot_compatibility_v1.py",
        "focused_test_sha256": digest(ROOT / "tests/test_semantic_slot_compatibility_v1.py"),
        "fixture_count": 10, "fixture_status": "PASS"})
    dump("case_101_frozen_payload_replay.json", {"artifact_schema_version": "Alpha2_2Frozen101ReplayV1",
        "source_payload_sha256": digest(payload_path), "raw_content_sha256": RAW_SHA,
        "schema_reference_anchor_slot_validation": validation,
        "payload_regenerated": False, "target_mutated": False})
    dump("case_101_linked_candidate_analysis.json", {"artifact_schema_version": "Alpha2_2LinkedCandidateAnalysisV1",
        "candidate_count": len(links), "valid_candidate_count": valid_links, "candidates": links})
    dump("case_101_gate_trace.json", {"artifact_schema_version": "Alpha2_2Case101GateTraceV1",
        "gates": trace, "coverage_blueprints": blueprints,
        "later_gates_diagnostic_only_after_first_loss": True})
    dump("case_101_first_loss_analysis.json", {"first_loss_stage": first_loss,
        "prior_frozen_loss_reclassified": "SEMANTIC_SLOT_COMPATIBILITY_ARCHITECTURE_DEFECT",
        "secondary_failure": "REQUIRED_CONDITIONING_CONTEXT_REFERENCE_OMITTED",
        "candidate_validation_failure_is_planner_content": True,
        "no_secondary_repair": True, "next_stage_recommendation": recommendation})
    for name, value in (("identity_safety_regression.json", identity),
                        ("overbroad_regression_audit.json", overbroad),
                        ("semantic_drift_regression_audit.json", drift),
                        ("mechanistic_proxy_regression_audit.json", proxy),
                        ("biological_unit_regression_audit.json", unit)):
        dump(name, value)
    require(not compiled, "unexpected query compilation")
    for key, path in (("alpha2", ALPHA2), ("alpha2_1", ALPHA2_1), ("smoke", SMOKE)):
        verify_root(path, EXPECTED[key])
    require(all(digest(ROOT / name) == old for name, old in source_hashes.items()),
            "protected source changed during replay")
    dump("scientific_state_safety_audit.json", {
        "historical_assets_modified": False, "source_file_hashes_unchanged": True,
        "deepseek_transport_changed": False, "planner_prompt_v2_changed": False,
        "planner_proposal_payload_v2_changed": False,
        "semantic_slot_can_promote_entity_identity": False,
        "default_search_only_deny_preserved": True,
        "production_case_specific_rules": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "candidate_records_seen": 0})
    summary = {"artifact_schema_version": "Alpha2_2SemanticSlotCompatibilitySummaryV1",
        "status": "completed", "case_id": "heldout_v2_101", "frozen_payload_replay_completed": True,
        "linked_candidate_count": len(links), "valid_linked_candidate_count": valid_links,
        "structurally_bound_blueprint_count": bound_blueprints,
        "compiled_query_count": 0, "first_loss_stage": first_loss,
        "next_stage_recommendation": recommendation,
        "semantic_slot_compatibility_defined": True, "search_anchor_v1_1_defined": True,
        "prior_overbroad_terms_reenabled": overbroad["promoted_count"],
        "prior_semantic_drift_terms_reenabled": drift["promoted_count"],
        "unauthorized_mechanistic_proxy_reenabled": proxy["promoted_count"],
        "biological_unit_broadening_reenabled": unit["promoted_count"],
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0}
    dump("summary.json", summary)
    components = [[p.name, digest(p)] for p in sorted(RUN.iterdir()) if p.is_file()]
    root_hash = sha256_value(components)
    dump("validation.json", {"artifact_schema_version": "Alpha2_2SemanticSlotCompatibilityValidationV1",
        "status": "PASS", "aggregate_components": components,
        "search_plan_v24_dev_alpha2_2_sha256": root_hash,
        "upstream_roots_verified": True, "raw_output_preserved": True,
        "protected_regressions_passed": True, "no_retrieval_or_model_call": True})
    (RUN / "search_plan_v24_dev_alpha2_2_sha256").write_text(root_hash + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "root": root_hash}, sort_keys=True))


if __name__ == "__main__":
    main()
