"""Exactly-one-call DeepSeek Planner V2 development smoke for heldout_v2_101.

The frozen provider request is checked before access. Raw model content is
fsync'd before parsing. No retrieval is performed. Reruns fail closed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from code_engine.extraction.deepseek_client import DeepSeekExtractionError
from code_engine.search.alpha1_relation_searchonly_v1 import _anchors, _qualified, normalize
from code_engine.search.alpha2_linked_relation_v1 import (
    Alpha2ContractError, PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA,
    assess_linked_relation_v1_1, linked_relation_search_only_eligibility,
    search_anchor_compatibility, search_only_eligibility_v1_1,
    validate_planner_proposal_v2,
)
from code_engine.search.deepseek_planner_transport_v1 import (
    DEEPSEEK_PROVIDER_SCHEMA, PROMPT_TEXT, static_schema_preflight,
)
from code_engine.search.deepseek_planner_transport_v1_1 import (
    DEFAULT_CONFIG, DeepSeekPlannerTransportV1_1,
)
from code_engine.search.planner_authority_contract_split_v1 import _normalize, _target_authorities
from code_engine.search.proposition_aware_query_planner_v1 import canonical_target_hash, sha256_value
from code_engine.search.query_compiler_v24_dev import DEFAULT_DEVELOPMENT_BUDGETS

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_planner_v2_smoke_101"
ALPHA2 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_linked_relation_deepseek_migration_offline"
AMENDMENT = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_reasoning_config_offline"
AUTHORITY = ROOT / "runs/20260918_search_plan_v24_dev_planner_authority_contract_split_offline"
ROOTS = {
    "alpha2": "918e0badbaeb70c439ae8d6e1d3bcc1eb5d5697c5df75b38dc2819357890a4e8",
    "alpha2_1": "fee80d671ed6e573ca0e18640b4ab87b15aec021e6870f17b0fc3457554b41fc",
}
FIRST_LOSS = ("PLANNER_MISSING_LINKED_RELATION", "PLANNER_INVALID_CONCEPT_REF",
              "SEARCH_ANCHOR_UNRESOLVED", "SEARCH_ONLY_ELIGIBILITY_BLOCK",
              "RELATION_BINDING_FAILURE", "COMPILER_FAILURE")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_json(name: str, value: Any) -> None:
    path = RUN / name
    require(not path.exists() and not path.is_symlink(), f"refusing to overwrite {name}")
    path.write_bytes(json_bytes(value))


def write_text(name: str, value: str) -> None:
    path = RUN / name
    require(not path.exists() and not path.is_symlink(), f"refusing to overwrite {name}")
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def write_lines(name: str, rows: list[dict[str, Any]]) -> None:
    path = RUN / name
    require(not path.exists() and not path.is_symlink(), f"refusing to overwrite {name}")
    path.write_bytes(b"".join(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":")).encode("utf-8") + b"\n"
                              for row in rows))


def verify_root(path: Path, expected: str) -> dict[str, Any]:
    validation = json.loads((path / "validation.json").read_text(encoding="utf-8"))
    pairs = validation["aggregate_components"]
    for name, frozen in pairs:
        require(digest((path / name).read_bytes()) == frozen, f"protected component changed: {name}")
    require(sha256_value(pairs) == expected, f"protected root changed: {path.name}")
    return {"root_sha256": expected, "component_count": len(pairs), "verified": True}


def load_key() -> str | None:
    key = os.getenv("DEEPSEEK_API_KEY")
    if key:
        return key
    path = ROOT / ".env"
    if not path.is_file():
        return None
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if raw.startswith("export "):
            raw = raw[7:]
        if raw.startswith("DEEPSEEK_API_KEY="):
            candidate = raw.split("=", 1)[1].strip().strip('"\'')
            if candidate and not candidate.startswith("<"):
                values.append(candidate)
    require(len(values) <= 1, "multiple DeepSeek credentials in .env")
    return values[0] if values else None


def frozen_target() -> dict[str, Any]:
    rows = [json.loads(line) for line in
            (AUTHORITY / "validated_development_plans.jsonl").read_text(encoding="utf-8").splitlines()
            if line]
    matches = [row["validated_plan"]["canonical_proposition"]["target_payload"]
               for row in rows if row["case_id"] == "heldout_v2_101"]
    require(len(matches) == 1 and matches[0]["case_id"] == "heldout_v2_101", "case-101 target unavailable")
    require("EGF increases ERK1/2 phosphorylation" in matches[0]["primary_proposition_meaning"],
            "unexpected case-101 proposition")
    return matches[0]


def preflight() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    upstream = {name: verify_root(path, ROOTS[name])
                for name, path in (("alpha2", ALPHA2), ("alpha2_1", AMENDMENT))}
    config = json.loads((AMENDMENT / "deepseek_query_planner_config_v1_1.json").read_text(encoding="utf-8"))
    require(config == DEFAULT_CONFIG.to_dict(), "frozen alpha2.1 config differs from runtime")
    fixture = json.loads((AMENDMENT / "heldout_v2_101_offline_request_fixture.json").read_text(encoding="utf-8"))
    schema = json.loads((ALPHA2 / "planner_proposal_payload_v2_schema.json").read_text(encoding="utf-8"))
    provider_schema = json.loads((ALPHA2 / "deepseek_provider_schema.json").read_text(encoding="utf-8"))
    require(sha256_value(schema) == sha256_value(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA), "planner schema changed")
    require(sha256_value(provider_schema) == sha256_value(DEEPSEEK_PROVIDER_SCHEMA), "provider schema changed")
    require((ALPHA2 / "planner_prompt_v2.md").read_text(encoding="utf-8") == PROMPT_TEXT,
            "Planner Prompt V2 changed")
    amendment_audit = json.loads((AMENDMENT / "deepseek_request_parameter_audit.json").read_text(encoding="utf-8"))
    for name, frozen_hash in amendment_audit["implementation_source_sha256"].items():
        require(digest((ROOT / name).read_bytes()) == frozen_hash, f"amended transport source changed: {name}")
    target = frozen_target()
    transport = DeepSeekPlannerTransportV1_1()
    body = transport.serialized_body(target)
    require(digest(body) == fixture["request_body_sha256"], "request differs from frozen fixture")
    require(json.loads(body)["thinking"] == {"type": "enabled"}
            and json.loads(body)["reasoning_effort"] == "high", "reasoning controls changed")
    require("temperature" not in json.loads(body) and "top_p" not in json.loads(body),
            "sampling controls unexpectedly present")
    local = static_schema_preflight()
    require(local["passed"], "frozen local schema preflight failed")
    return upstream, target, fixture, digest(body)


def classify_terms(payload: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    authority = _target_authorities(target)
    rows = []
    for intent in payload["retrieval_intents"]:
        for concept in intent["search_concepts"]:
            for term in concept["proposed_terms"]:
                exact_ref = authority.get((concept["concept_type"],
                                           _normalize(term["term"])))
                if exact_ref:
                    state, rule = "AUTHORIZED_EQUIVALENT", "IMMUTABLE_TARGET_EXACT_AUTHORITY"
                else:
                    state, rule = search_only_eligibility_v1_1(term["term"], concept["concept_type"], target)
                row = {"artifact_schema_version": "Alpha2V2TermValidationReceiptV1",
                       "intent_id": intent["intent_id"], "concept_id": concept["concept_id"],
                       "concept_type": concept["concept_type"], "term_id": term["term_id"],
                       "term": term["term"], "final_authority_classification": state,
                       "eligibility_rule_id": rule, "authority_reference": exact_ref}
                row["receipt_sha256"] = sha256_value(row)
                rows.append(row)
        for blueprint in intent["candidate_query_blueprints"]:
            for index, link in enumerate(blueprint["linked_relation_candidates"]):
                state, rule = linked_relation_search_only_eligibility(
                    link, target, intent_type=intent["intent_type"])
                row = {"artifact_schema_version": "Alpha2V2TermValidationReceiptV1",
                       "intent_id": intent["intent_id"], "blueprint_id": blueprint["blueprint_id"],
                       "concept_id": None, "concept_type": "linked_relation",
                       "term_id": f"{blueprint['blueprint_id']}:linked:{index}",
                       "term": link["linked_relation_phrase"],
                       "final_authority_classification": state,
                       "eligibility_rule_id": rule, "authority_reference": None}
                row["receipt_sha256"] = sha256_value(row)
                rows.append(row)
    return rows


def analyse_links(payload: dict[str, Any], target: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    anchors = []
    bindings = []
    coverage = []
    for intent in payload["retrieval_intents"]:
        for blueprint in intent["candidate_query_blueprints"]:
            link_rows = []
            for index, link in enumerate(blueprint["linked_relation_candidates"]):
                states = {}
                for role, field, dimension in (
                    ("subject", "subject_surface_candidate", "subject"),
                    ("response", "response_surface_candidate", "object_measurement_target"),
                    ("endpoint", "endpoint_property_surface_candidate", "endpoint_property"),
                ):
                    states[role] = search_anchor_compatibility(link[field], _anchors(target, dimension))
                assessment = assess_linked_relation_v1_1(link, target, intent_type=intent["intent_type"])
                decision, rule = linked_relation_search_only_eligibility(link, target,
                                                                         intent_type=intent["intent_type"])
                anchors.append({"intent_id": intent["intent_id"], "blueprint_id": blueprint["blueprint_id"],
                                "linked_candidate_index": index, "states": states,
                                "canonical_identity_promoted": False})
                row = {"intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
                       "blueprint_id": blueprint["blueprint_id"], "linked_candidate_index": index,
                       "linked_relation_phrase": link["linked_relation_phrase"],
                       "state": assessment["state"], "checks": assessment["checks"],
                       "search_only_classification": decision, "eligibility_rule_id": rule,
                       "model_asserts_scientific_truth": False}
                bindings.append(row)
                link_rows.append(row)
            coverage.append({"intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
                             "blueprint_id": blueprint["blueprint_id"],
                             "linked_relation_candidate_count": len(link_rows),
                             "structurally_bound_candidate_count": sum(r["state"] == "STRUCTURALLY_BOUND"
                                                               for r in link_rows),
                             "relation_coverage_state": "REPRESENTED" if any(
                                 r["state"] == "STRUCTURALLY_BOUND" for r in link_rows)
                             else "RELATION_UNDERREPRESENTED"})
    return anchors, bindings, coverage


def compile_bound(payload: dict[str, Any], target: dict[str, Any],
                  bindings: list[dict[str, Any]], receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Frozen qualifier/budgets applied to V2 linked phrases; no query fallback."""
    bound = {(row["intent_id"], row["blueprint_id"], row["linked_candidate_index"]): row
             for row in bindings if row["state"] == "STRUCTURALLY_BOUND"
             and row["search_only_classification"] == "SEARCH_ONLY_EXPANSION"}
    if not bound:
        return []
    usable = {"AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION"}
    receipt_by_term = {(row["intent_id"], row["concept_id"], row["term_id"]): row for row in receipts}
    rows = []
    applicable = [intent for intent in payload["retrieval_intents"] if intent["applicability"] == "APPLICABLE"]
    require(len(applicable) <= DEFAULT_DEVELOPMENT_BUDGETS.max_intents_per_target, "intent budget exceeded")
    for intent in applicable:
        require(len(intent["candidate_query_blueprints"]) <=
                DEFAULT_DEVELOPMENT_BUDGETS.max_blueprints_per_intent, "blueprint budget exceeded")
        concepts = {c["concept_id"]: c for c in intent["search_concepts"]}
        for blueprint in intent["candidate_query_blueprints"]:
            for index, link in enumerate(blueprint["linked_relation_candidates"]):
                binding = bound.get((intent["intent_id"], blueprint["blueprint_id"], index))
                if binding is None:
                    continue
                fragments = [_qualified(link["linked_relation_phrase"])]
                term_classes = [{"term": link["linked_relation_phrase"],
                                 "classification": "SEARCH_ONLY_EXPANSION"}]
                for cid in (link["biological_unit_context_ref"], *link["conditioning_context_refs"],
                            *link["therapy_context_refs"]):
                    if not cid:
                        continue
                    concept = concepts[cid]
                    selected = []
                    for term in concept["proposed_terms"]:
                        receipt = receipt_by_term[(intent["intent_id"], cid, term["term_id"])]
                        if receipt["final_authority_classification"] in usable:
                            selected.append((term["term"], receipt["final_authority_classification"]))
                    if not selected:
                        raise ValueError(f"required context lacks usable term: {cid}")
                    selected.sort(key=lambda item: normalize(item[0]))
                    chosen = selected[0]
                    fragments.append(_qualified(chosen[0]))
                    term_classes.append({"term": chosen[0], "classification": chosen[1]})
                query = " AND ".join(fragments)
                material = {"case_id": "heldout_v2_101", "intent_id": intent["intent_id"],
                            "blueprint_id": blueprint["blueprint_id"], "linked_candidate_index": index,
                            "target_sha256": canonical_target_hash(target), "query_string": query,
                            "term_classifications": term_classes,
                            "budget_sha256": sha256_value(DEFAULT_DEVELOPMENT_BUDGETS.to_dict())}
                rows.append({**material, "artifact_schema_version": "Alpha2V2OfflineCompiledQueryV1",
                             "query_sha256": sha256_value(material),
                             "execution_status": "NOT_EXECUTED_DEVELOPMENT_SMOKE",
                             "subject_anchor": link["subject_surface_candidate"],
                             "response_anchor": link["response_surface_candidate"],
                             "endpoint_property": link["endpoint_property_surface_candidate"],
                             "direction": link["direction"],
                             "biological_unit": _anchors(target, "biological_unit"),
                             "linked_relation": link["linked_relation_phrase"]})
    require(len(rows) <= DEFAULT_DEVELOPMENT_BUDGETS.max_queries_per_target, "query budget exceeded")
    return rows


def finish(*, upstream: dict[str, Any], target: dict[str, Any], fixture: dict[str, Any],
           request_hash: str, call_status: dict[str, Any], raw_result: dict[str, Any],
           parsed: dict[str, Any] | None, parse_success: bool) -> dict[str, Any]:
    write_json("upstream_root_verification.json", upstream)
    write_json("deepseek_config_verification.json", {
        "config": DEFAULT_CONFIG.to_dict(), "config_sha256": sha256_value(DEFAULT_CONFIG.to_dict()),
        "request_fixture_sha256": fixture["request_body_sha256"],
        "provider_schema_sha256": sha256_value(DEEPSEEK_PROVIDER_SCHEMA),
        "prompt_sha256": sha256_value(PROMPT_TEXT), "target_sha256": canonical_target_hash(target),
        "all_frozen_components_verified": True})
    write_json("deepseek_request_manifest.json", {
        "case_id": "heldout_v2_101", "api_surface": "CHAT_COMPLETIONS_API",
        "endpoint": fixture["endpoint"], "method": "POST",
        "request_body_sha256": request_hash,
        "provider_schema_sha256": sha256_value(DEEPSEEK_PROVIDER_SCHEMA),
        "prompt_sha256": sha256_value(PROMPT_TEXT), "target_sha256": canonical_target_hash(target),
        "input_isolation": "immutable_target_prompt_v2_provider_schema_only"})
    write_json("provider_call_manifest.json", call_status)
    write_json("raw_provider_response.json", raw_result)
    write_json("planner_v2_raw_payload.json", {
        "case_id": "heldout_v2_101", "parsed_provider_payload": parsed,
        "parse_success": parse_success, "provider_output_mutated": False})
    payload_hash = digest(raw_result.get("raw_model_content", "").encode("utf-8"))
    write_text("planner_v2_raw_payload_sha256", payload_hash)
    transport_success = bool(call_status["http_request_accepted"] and call_status["model_inference_calls"] == 1)
    write_json("provider_transport_validation.json", {
        "http_provider_request_accepted": call_status["http_request_accepted"],
        "model_inference_completed": call_status["model_inference_calls"] == 1,
        "valid_json_returned": parse_success,
        "parse_success": parse_success,
        "finish_reason": raw_result.get("finish_reason"),
        "provider_transport_success": transport_success,
        "raw_model_content_sha256": payload_hash})

    planner_valid = False
    schema_error = None
    anchors: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    compiled: list[dict[str, Any]] = []
    first_loss = "NONE"
    link_diagnostic = "OTHER"
    compiler_error = None
    if parse_success and parsed is not None and raw_result.get("finish_reason") == "stop":
        try:
            validate_planner_proposal_v2(parsed, target=target)
            planner_valid = True
        except (Alpha2ContractError, KeyError, TypeError, ValueError) as exc:
            schema_error = str(exc)
            if "linked candidate" in schema_error:
                first_loss = "PLANNER_MISSING_LINKED_RELATION"
                link_diagnostic = "KEYWORD_BAG_ONLY"
            elif "concept" in schema_error or "ref" in schema_error:
                first_loss = "PLANNER_INVALID_CONCEPT_REF"
                link_diagnostic = "INVALID_CONCEPT_REFERENCE"
            else:
                first_loss = "PLANNER_MISSING_LINKED_RELATION"
    elif transport_success:
        first_loss = "PLANNER_MISSING_LINKED_RELATION"

    if planner_valid and parsed is not None:
        receipts = classify_terms(parsed, target)
        anchors, bindings, coverage = analyse_links(parsed, target)
        if any(row["state"] == "STRUCTURALLY_BOUND" for row in bindings):
            link_diagnostic = "VALID_LINKED_RELATION"
        elif not bindings:
            first_loss = "PLANNER_MISSING_LINKED_RELATION"
            link_diagnostic = "KEYWORD_BAG_ONLY"
        else:
            failed = {name for row in bindings for name, passed in row["checks"].items() if not passed}
            if "response" in failed:
                link_diagnostic = "MISSING_RESPONSE_BINDING"
                first_loss = "SEARCH_ANCHOR_UNRESOLVED"
            elif "endpoint" in failed:
                link_diagnostic = "MISSING_ENDPOINT_PROPERTY"
                first_loss = "SEARCH_ANCHOR_UNRESOLVED"
            elif "direction" in failed:
                link_diagnostic = "MISSING_DIRECTION_BINDING"
                first_loss = "RELATION_BINDING_FAILURE"
            else:
                link_diagnostic = "OTHER"
                first_loss = "RELATION_BINDING_FAILURE"
        if any(row["state"] == "STRUCTURALLY_BOUND" for row in bindings):
            if not any(row["search_only_classification"] == "SEARCH_ONLY_EXPANSION"
                       for row in bindings if row["state"] == "STRUCTURALLY_BOUND"):
                first_loss = "SEARCH_ONLY_ELIGIBILITY_BLOCK"
            else:
                try:
                    compiled = compile_bound(parsed, target, bindings, receipts)
                    if not compiled:
                        first_loss = "COMPILER_FAILURE"
                except (ValueError, KeyError) as exc:
                    compiler_error = str(exc)
                    first_loss = "COMPILER_FAILURE"
    if first_loss != "NONE":
        require(first_loss in FIRST_LOSS, "invalid first-loss classification")
    write_json("planner_v2_schema_validation.json", {
        "planner_v2_payload_valid": planner_valid,
        "error": schema_error, "scientific_truth_inferred": False})
    write_json("linked_relation_candidate_validation.json", {
        "linked_relation_candidate_valid": planner_valid and bool(bindings),
        "diagnostic": link_diagnostic,
        "relation_applicable_blueprints": len(coverage),
        "linked_candidates": len(bindings)})
    write_json("search_anchor_compatibility.json", {"candidate_anchor_states": anchors,
                                                        "identity_promotions": 0})
    write_lines("term_validation_receipts.jsonl", receipts)
    write_json("relation_binding_analysis.json", {"assessments": bindings,
                                                   "structurally_bound_blueprint_count": len({
                                                       (r["intent_id"], r["blueprint_id"]) for r in bindings
                                                       if r["state"] == "STRUCTURALLY_BOUND"})})
    write_json("proposition_coverage_analysis.json", {"blueprints": coverage,
                                                       "coverage_is_deterministic": True})
    if compiled:
        write_lines("compiled_queries.jsonl", compiled)
        write_text("compiled_queries_sha256", sha256_value(compiled))
    write_json("first_loss_analysis.json", {
        "first_loss_stage": first_loss, "compiler_error": compiler_error,
        "no_fallback_query_created": True})
    bound_count = len({(r["intent_id"], r["blueprint_id"]) for r in bindings
                       if r["state"] == "STRUCTURALLY_BOUND"})
    smoke_success = bool(transport_success and parse_success and planner_valid
                         and bound_count >= 1 and compiled and first_loss == "NONE")
    if smoke_success:
        recommendation = "AUTHORIZE_REMAINING_7_DEVELOPMENT_CASES"
    elif not transport_success or not parse_success:
        recommendation = "DEEPSEEK_TRANSPORT_REFINEMENT_NEEDED"
    elif not planner_valid or bound_count == 0:
        recommendation = "PLANNER_V2_REFINEMENT_NEEDED"
    else:
        recommendation = "DETERMINISTIC_REFINEMENT_NEEDED"
    write_json("scientific_state_safety_audit.json", {
        "authority_boundary_violations": 0, "search_only_identity_promotions": 0,
        "production_case_specific_rules": 0,
        "literature_network_calls": 0, "retrieval_calls": 0,
        "candidate_records_seen": 0, "known_pmid_checks": 0,
        "queries_executed": 0, "historical_assets_modified": False})
    summary = {"artifact_schema_version": "Alpha2_1DeepSeekPlannerV2Smoke101SummaryV1",
               "status": "completed" if smoke_success else "failed",
               "case_id": "heldout_v2_101", "provider": "deepseek", "model": "deepseek-v4-pro",
               "thinking_enabled": True, "reasoning_effort": "high",
               "provider_requests_attempted": call_status["provider_requests_attempted"],
               "model_inference_calls": call_status["model_inference_calls"],
               "provider_transport_success": transport_success,
               "provider_payload_parse_success": parse_success,
               "planner_v2_payload_valid": planner_valid,
               "linked_relation_candidate_valid": planner_valid and bool(bindings),
               "structurally_bound_blueprint_count": bound_count,
               "compiled_query_count": len(compiled),
               "authority_boundary_violations": 0, "search_only_identity_promotions": 0,
               "first_loss_stage": first_loss,
               "next_stage_recommendation": recommendation,
               "literature_network_calls": 0, "retrieval_calls": 0,
               "candidate_records_seen": 0,
               "remote_provider_schema_acceptance_verified": False}
    write_json("summary.json", summary)
    components = [[path.name, digest(path.read_bytes())] for path in sorted(RUN.iterdir())
                  if path.is_file() and path.name not in {"validation.json",
                                                       "search_plan_v24_dev_alpha2_1_deepseek_smoke_101_sha256"}]
    root = sha256_value(components)
    write_json("validation.json", {"artifact_schema_version": "Alpha2_1DeepSeekPlannerV2Smoke101ValidationV1",
                                   "status": "PASS" if smoke_success else "FAIL",
                                   "aggregate_components": components,
                                   "search_plan_v24_dev_alpha2_1_deepseek_smoke_101_sha256": root,
                                   "upstream_roots_verified": True,
                                   "raw_content_frozen_before_semantic_analysis": True,
                                   "no_retrieval": True})
    write_text("search_plan_v24_dev_alpha2_1_deepseek_smoke_101_sha256", root)
    return {"summary": summary, "root": root}


def main() -> None:
    require(not RUN.exists(), "one-call run directory already exists; rerun prohibited")
    upstream, target, fixture, request_hash = preflight()
    key = load_key()
    require(bool(key), "DeepSeek credential unavailable; no provider request attempted")
    RUN.mkdir(parents=True, exist_ok=False)
    # This marker is committed before the single permitted attempt. A crash
    # cannot silently permit an outcome-informed rerun.
    write_json("request_attempt_marker.json", {"case_id": "heldout_v2_101",
                                               "provider_requests_attempted": 1,
                                               "request_body_sha256": request_hash,
                                               "maximum_attempts": 1})
    raw_path = RUN / "raw_model_content.txt"

    def freeze_raw(raw: bytes) -> None:
        with raw_path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())

    call_status = {"provider_requests_attempted": 1, "model_inference_calls": 0,
                   "http_request_accepted": False, "provider_error": None,
                   "retry_count": 0, "provider_fallback": False}
    parsed = None
    parse_success = False
    raw_result: dict[str, Any] = {"raw_model_content": "", "raw_http_body_available": False,
                                  "raw_http_body_policy": "frozen DeepSeek adapter exposes content and sanitized metadata",
                                  "provider": "deepseek", "model": "deepseek-v4-pro",
                                  "request_body_sha256": request_hash,
                                  "prompt_sha256": sha256_value(PROMPT_TEXT),
                                  "provider_schema_sha256": sha256_value(DEEPSEEK_PROVIDER_SCHEMA),
                                  "target_sha256": canonical_target_hash(target),
                                  "finish_reason": None, "usage": {}, "provider_metadata": {}}
    try:
        response = DeepSeekPlannerTransportV1_1().execute_result(
            target=target, api_key=key, raw_response_sink=freeze_raw,
            explicitly_authorized=True)
        call_status["http_request_accepted"] = True
        call_status["model_inference_calls"] = 1
        raw_result.update({"raw_model_content": response.raw_response,
                           "finish_reason": response.finish_reason,
                           "usage": response.usage,
                           "provider_metadata": response.provider_metadata,
                           "parser_warnings": response.warnings,
                           "attempt_count": response.attempt_count})
        require(raw_path.is_file() and raw_path.read_bytes() == response.raw_response.encode("utf-8"),
                "raw provider content not frozen exactly")
        parse_success = isinstance(response.payload, dict) and not response.warnings
        if parse_success:
            parsed = response.payload
    except DeepSeekExtractionError as exc:
        call_status["provider_error"] = {"error_kind": exc.error_kind,
                                         "message": str(exc).replace(key, "[REDACTED]"),
                                         "status_code": exc.status_code,
                                         "attempts": exc.attempts}
        http_status = exc.status_code or exc.provider_metadata.get("http_status")
        call_status["http_request_accepted"] = bool(http_status and 200 <= http_status < 300)
        raw_result.update({"raw_model_content": (raw_path.read_text(encoding="utf-8")
                                                 if raw_path.is_file() else str(exc.raw_response or "")),
                           "finish_reason": exc.finish_reason,
                           "usage": exc.usage,
                           "provider_metadata": exc.provider_metadata,
                           "transport_error": call_status["provider_error"]})
    outcome = finish(upstream=upstream, target=target, fixture=fixture,
                     request_hash=request_hash, call_status=call_status,
                     raw_result=raw_result, parsed=parsed, parse_success=parse_success)
    print(json.dumps(outcome, sort_keys=True))


if __name__ == "__main__":
    main()
