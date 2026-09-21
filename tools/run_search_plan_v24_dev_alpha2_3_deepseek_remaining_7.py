"""Seven-attempt maximum DeepSeek development generation, with no retrieval.

All request bodies and deterministic adapters are fixed and preflighted before
the first call. Each case has an exclusive attempt marker and durable raw sink.
Provider/config/schema failures stop the run; scientific proposal failures do
not trigger reruns and do not consume another case's authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from code_engine.extraction.deepseek_client import DeepSeekExtractionError
from code_engine.search.alpha2_linked_relation_v1 import (
    PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA, _validate_local_schema,
)
from code_engine.search.context_role_ontology_v1 import (
    BINDING_VERSION, assess_linked_relation_v1_2,
    conditioning_context_applicability, context_role_mapping,
    linked_relation_search_only_eligibility_v1_2, therapy_context_applicability,
)
from code_engine.search.deepseek_planner_transport_v1 import (
    DEEPSEEK_PROVIDER_SCHEMA, PROMPT_TEXT, static_schema_preflight,
)
from code_engine.search.deepseek_planner_transport_v1_1 import (
    DEFAULT_CONFIG, DeepSeekPlannerTransportV1_1,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    canonical_target_hash, sha256_value,
)
from code_engine.search.semantic_slot_compatibility_v1 import validate_v2_structure_and_slots
from tools.freeze_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline import targets_by_case
from tools.run_search_plan_v24_dev_alpha2_1_smoke_101 import (
    classify_terms, compile_bound, load_key, verify_root,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_3_deepseek_remaining_7_generation"
CASES = tuple(f"heldout_v2_{number}" for number in range(102, 109))
ALPHA2 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_linked_relation_deepseek_migration_offline"
ALPHA2_1 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_reasoning_config_offline"
ALPHA2_3 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_3_context_role_semantics_offline"
SMOKE_101 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_planner_v2_smoke_101"
ROOTS = {
    "alpha2": (ALPHA2, "918e0badbaeb70c439ae8d6e1d3bcc1eb5d5697c5df75b38dc2819357890a4e8"),
    "alpha2_1": (ALPHA2_1, "fee80d671ed6e573ca0e18640b4ab87b15aec021e6870f17b0fc3457554b41fc"),
    "alpha2_3": (ALPHA2_3, "13d66f15bfb0f003fa9d6581f892c174b965df42952022c7992958f2da2efa10"),
    "smoke_101": (SMOKE_101, "b66eebe346b1f130287083e364fbba10a22110b40f0a288e9185fe5f5242fd40"),
}


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: Any) -> None:
    require(not path.exists() and not path.is_symlink(), f"refusing overwrite: {path}")
    data = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    require(not path.exists() and not path.is_symlink(), f"refusing overwrite: {path}")
    with path.open("xb") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8") + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def freeze_root(path: Path, root_name: str, *, status: str) -> str:
    components = [[child.name, digest(child.read_bytes())] for child in sorted(path.iterdir())
                  if child.is_file() and child.name not in {"validation.json", root_name}]
    value = sha256_value(components)
    write_json(path / "validation.json", {"artifact_schema_version": "Alpha2_3DeepSeekGenerationValidationV1",
              "status": status, "aggregate_components": components, root_name: value,
              "network_literature_calls": 0, "retrieval_calls": 0})
    with (path / root_name).open("x", encoding="utf-8") as handle:
        handle.write(value + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return value


def compile_with_case_identity(payload: dict[str, Any], target: dict[str, Any],
                               bindings: list[dict[str, Any]], receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Frozen 101 compiler; replace only its hard-coded case identity/hash.

    Query text, selection, budget, qualifiers, and validation are unchanged.
    The adapter is fixed before any of the seven calls and must be exact on 101.
    """
    rows = compile_bound(payload, target, bindings, receipts)
    case_id = target["case_id"]
    result = []
    for old in rows:
        material = {key: old[key] for key in (
            "intent_id", "blueprint_id", "linked_candidate_index", "target_sha256",
            "query_string", "term_classifications", "budget_sha256")}
        material["case_id"] = case_id
        new = {**old, "case_id": case_id, "query_sha256": sha256_value(material)}
        result.append(new)
    return result


def frozen_101_adapter_equivalence(targets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = json.loads((SMOKE_101 / "planner_v2_raw_payload.json").read_text(encoding="utf-8"))[
        "parsed_provider_payload"]
    target = targets["heldout_v2_101"]
    rows = []
    for intent in payload["retrieval_intents"]:
        concepts = {c["concept_id"]: c for c in intent["search_concepts"]}
        for blueprint in intent["candidate_query_blueprints"]:
            for index, link in enumerate(blueprint["linked_relation_candidates"]):
                binding = assess_linked_relation_v1_2(link, target, concepts, blueprint["concept_ids"])
                state, _ = linked_relation_search_only_eligibility_v1_2(
                    link, target, concepts, blueprint["concept_ids"])
                rows.append({"intent_id": intent["intent_id"], "blueprint_id": blueprint["blueprint_id"],
                             "linked_candidate_index": index, "state": binding["state"],
                             "search_only_classification": state})
    compiled = compile_with_case_identity(payload, target, rows, classify_terms(payload, target))
    expected = [json.loads(line) for line in (ALPHA2_3 / "case_101_compiled_queries.jsonl").read_text(
        encoding="utf-8").splitlines() if line]
    expected_base = [{key: value for key, value in row.items() if key not in {
        "alpha2_3_binding_contract", "alpha2_3_applicability_contract", "historical_compiler_unchanged"}}
        for row in expected]
    require(compiled == expected_base and len(compiled) == 2,
            "case-identity adapter not equivalent to frozen 101 compilation")
    return {"case_101_equivalence": True, "query_count": len(compiled),
            "adapter_changes_only_case_id_and_derived_query_sha256": True,
            "frozen_alpha2_3_queries_sha256": digest((ALPHA2_3 / "case_101_compiled_queries.jsonl").read_bytes())}


def preflight() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    require(not RUN.exists(), "generation run already exists; no rerun or repair allowed")
    upstream = {name: verify_root(path, expected) for name, (path, expected) in ROOTS.items()}
    config = json.loads((ALPHA2_1 / "deepseek_query_planner_config_v1_1.json").read_text(encoding="utf-8"))
    require(config == DEFAULT_CONFIG.to_dict(), "frozen DeepSeek configuration mismatch")
    schema = json.loads((ALPHA2 / "planner_proposal_payload_v2_schema.json").read_text(encoding="utf-8"))
    provider_schema = json.loads((ALPHA2 / "deepseek_provider_schema.json").read_text(encoding="utf-8"))
    require(sha256_value(schema) == sha256_value(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA),
            "PlannerProposalPayloadV2 schema changed")
    require(sha256_value(provider_schema) == sha256_value(DEEPSEEK_PROVIDER_SCHEMA),
            "DeepSeek provider schema changed")
    require((ALPHA2 / "planner_prompt_v2.md").read_text(encoding="utf-8") == PROMPT_TEXT,
            "Planner Prompt V2 changed")
    require(static_schema_preflight()["passed"], "frozen local provider schema preflight failed")
    amendment_audit = json.loads((ALPHA2_1 / "deepseek_request_parameter_audit.json").read_text(
        encoding="utf-8"))
    for name, expected in amendment_audit["implementation_source_sha256"].items():
        require(digest((ROOT / name).read_bytes()) == expected, f"frozen transport source changed: {name}")
    alpha2_3_audit = json.loads((ALPHA2_3 / "scientific_state_safety_audit.json").read_text(
        encoding="utf-8"))
    for name in ("src/code_engine/search/context_role_ontology_v1.py",
                 "src/code_engine/search/semantic_slot_compatibility_v1.py"):
        require(digest((ROOT / name).read_bytes()) == alpha2_3_audit["protected_file_hashes"][name],
                f"frozen alpha2.3 validator changed: {name}")
    require(bool(load_key()), "DeepSeek credential unavailable; no call attempted")
    targets = targets_by_case()
    require(set(targets) == {"heldout_v2_101", *CASES}, "frozen development cases changed")
    transport = DeepSeekPlannerTransportV1_1()
    requests = []
    for case_id in CASES:
        target = targets[case_id]
        request = transport.preview_request(target)
        require(request["model"] == "deepseek-v4-pro" and request["thinking"] == {"type": "enabled"}
                and request["reasoning_effort"] == "high" and "temperature" not in request
                and "top_p" not in request, "provider parameter mismatch")
        requests.append({"case_id": case_id, "target_sha256": canonical_target_hash(target),
                         "request_body_sha256": digest(transport.serialized_body(target)),
                         "endpoint": transport.endpoint, "provider": "deepseek",
                         "model": "deepseek-v4-pro", "api_surface": "CHAT_COMPLETIONS_API",
                         "thinking": "enabled", "reasoning_effort": "high",
                         "temperature_omitted": True, "top_p_omitted": True})
    adapter = frozen_101_adapter_equivalence(targets)
    return upstream, targets, {"requests": requests, "compiler_adapter": adapter,
                               "config_sha256": sha256_value(config),
                               "prompt_sha256": sha256_value(PROMPT_TEXT),
                               "proposal_schema_sha256": sha256_value(schema),
                               "provider_schema_sha256": sha256_value(provider_schema),
                               "alpha2_3_stack_sha256": ROOTS["alpha2_3"][1],
                               "generation_runner_sha256": digest(Path(__file__).read_bytes())}


def analyse_case(case_dir: Path, case_id: str, payload: dict[str, Any],
                 target: dict[str, Any]) -> dict[str, Any]:
    """Scientific/planner failures stop this case only; no provider rerun."""
    trace: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    compiled: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    failure: str | None = None
    try:
        validation = validate_v2_structure_and_slots(payload, target)
        trace.extend({"stage": stage, "passed": validation[key]} for stage, key in (
            ("CONCEPT_REFERENCE", "concept_references_valid"),
            ("SURFACE_ANCHOR_COMPATIBILITY", "surface_anchors_compatible"),
            ("SEMANTIC_SLOT_COMPATIBILITY", "semantic_slots_compatible")))
        if not validation["surface_anchors_compatible"]:
            failure = "SURFACE_ANCHOR_COMPATIBILITY"
        elif not validation["semantic_slots_compatible"]:
            failure = "SEMANTIC_SLOT_COMPATIBILITY"
    except (ValueError, KeyError, TypeError) as exc:
        validation = {"error_type": type(exc).__name__, "error": str(exc),
                      "provider_payload_schema_prevalidated": True}
        failure = "CONCEPT_REFERENCE_OR_PLANNER_STRUCTURE"
        trace.append({"stage": failure, "passed": False, "error_type": type(exc).__name__})
    if failure is None:
        condition = conditioning_context_applicability(target)
        therapy = therapy_context_applicability(target)
        roles = context_role_mapping(target)
        trace.append({"stage": "CONTEXT_ROLE_APPLICABILITY", "passed":
                      condition["state"] != "UNRESOLVED" and therapy["state"] != "UNRESOLVED",
                      "conditioning_state": condition["state"], "therapy_state": therapy["state"]})
        if condition["state"] == "UNRESOLVED" or therapy["state"] == "UNRESOLVED":
            failure = "CONTEXT_ROLE_APPLICABILITY"
    else:
        condition = therapy = roles = None
    if failure is None:
        receipts = classify_terms(payload, target)
        binder_inputs = []
        for intent in payload["retrieval_intents"]:
            concepts = {c["concept_id"]: c for c in intent["search_concepts"]}
            for blueprint in intent["candidate_query_blueprints"]:
                selected = []
                for index, link in enumerate(blueprint["linked_relation_candidates"]):
                    binding = assess_linked_relation_v1_2(link, target, concepts, blueprint["concept_ids"])
                    search_state, search_rule = linked_relation_search_only_eligibility_v1_2(
                        link, target, concepts, blueprint["concept_ids"])
                    row = {"intent_id": intent["intent_id"], "blueprint_id": blueprint["blueprint_id"],
                           "linked_candidate_index": index, "candidate_sha256": sha256_value(link),
                           "binding": binding, "search_only_state": search_state,
                           "search_only_rule": search_rule}
                    links.append(row)
                    selected.append(row)
                    binder_inputs.append({"intent_id": intent["intent_id"],
                                          "blueprint_id": blueprint["blueprint_id"],
                                          "linked_candidate_index": index, "state": binding["state"],
                                          "search_only_classification": search_state})
                coverage.append({"intent_id": intent["intent_id"], "blueprint_id": blueprint["blueprint_id"],
                                 "candidate_count": len(selected),
                                 "structurally_bound_candidate_count": sum(
                                     r["binding"]["state"] == "STRUCTURALLY_BOUND" for r in selected),
                                 "relation_coverage_state": "REPRESENTED" if any(
                                     r["binding"]["state"] == "STRUCTURALLY_BOUND" for r in selected)
                                 else "RELATION_UNDERREPRESENTED"})
        valid = [r for r in links if r["binding"]["state"] == "STRUCTURALLY_BOUND"]
        trace.extend((
            {"stage": "LINKED_RELATION_VALIDATION", "passed": bool(valid),
             "valid_candidate_count": len(valid)},
            {"stage": "SEARCH_ONLY_ELIGIBILITY", "passed": any(
                r["search_only_state"] == "SEARCH_ONLY_EXPANSION" for r in valid)},
            {"stage": "RELATION_BINDING", "passed": bool(valid)},
            {"stage": "COVERAGE", "passed": any(r["relation_coverage_state"] == "REPRESENTED" for r in coverage)},
        ))
        failure = next((row["stage"] for row in trace if not row["passed"]), None)
        if failure is None:
            try:
                compiled = compile_with_case_identity(payload, target, binder_inputs, receipts)
                trace.append({"stage": "COMPILER", "passed": bool(compiled),
                              "compiled_query_count": len(compiled)})
                if not compiled:
                    failure = "COMPILER"
            except (ValueError, KeyError, TypeError) as exc:
                trace.append({"stage": "COMPILER", "passed": False,
                              "error_type": type(exc).__name__, "error": str(exc)})
                failure = "COMPILER"
        else:
            trace.append({"stage": "COMPILER", "status": "SKIPPED_INVALID_PLAN",
                          "compiled_query_count": 0})
    write_json(case_dir / "deterministic_replay.json", {
        "case_id": case_id, "validation": validation, "context_roles": roles,
        "conditioning_applicability": condition, "therapy_applicability": therapy,
        "linked_candidates": links, "coverage": coverage, "gate_trace": trace,
        "first_loss_stage": failure or "NONE", "source_payload_mutated": False})
    write_jsonl(case_dir / "term_validation_receipts.jsonl", receipts)
    write_jsonl(case_dir / "compiled_queries.jsonl", compiled)
    return {"case_id": case_id, "status": "DETERMINISTIC_PASS" if failure is None else "SCIENTIFIC_PLANNER_FAIL_CLOSED",
            "first_loss_stage": failure or "NONE", "linked_candidate_count": len(links),
            "structurally_bound_candidate_count": sum(r["binding"]["state"] == "STRUCTURALLY_BOUND" for r in links),
            "structurally_bound_blueprint_count": sum(r["relation_coverage_state"] == "REPRESENTED" for r in coverage),
            "compiled_query_count": len(compiled), "rerun_count": 0}


def run_one(case_id: str, target: dict[str, Any], request: dict[str, Any], key: str) -> tuple[dict[str, Any], bool]:
    case_dir = RUN / case_id
    case_dir.mkdir(exist_ok=False)
    write_json(case_dir / "request_attempt_marker.json", {
        "case_id": case_id, "provider": "deepseek", "model": "deepseek-v4-pro",
        "maximum_attempts": 1, "request_attempts_committed": 1,
        "request_body_sha256": request["request_body_sha256"],
        "target_sha256": request["target_sha256"],
        "no_automatic_retry": True, "no_provider_fallback": True})
    raw_path = case_dir / "raw_model_content.txt"

    def freeze_raw(raw: bytes) -> None:
        with raw_path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())

    try:
        # New transport object and one one-attempt DeepSeekClient per target.
        result = DeepSeekPlannerTransportV1_1().execute_result(
            target=target, api_key=key, raw_response_sink=freeze_raw,
            explicitly_authorized=True)
    except DeepSeekExtractionError as exc:
        write_json(case_dir / "provider_failure.json", {
            "case_id": case_id, "error_kind": exc.error_kind,
            "status_code": exc.status_code, "attempts": exc.attempts,
            "finish_reason": exc.finish_reason,
            "raw_model_content_frozen": raw_path.is_file(),
            "raw_model_content_sha256": digest(raw_path.read_bytes()) if raw_path.is_file() else None,
            "provider_metadata": exc.provider_metadata,
            "error_message_redacted": str(exc).replace(key, "[REDACTED]"),
            "systemic_stop": True, "retry_count": 0})
        summary = {"case_id": case_id, "status": "SYSTEMIC_PROVIDER_FAILURE_STOP",
                   "provider_requests_attempted": 1, "inference_attempts": 1,
                   "raw_model_content_frozen": raw_path.is_file(), "rerun_count": 0}
        write_json(case_dir / "case_summary.json", summary)
        freeze_root(case_dir, "case_sha256", status="FAIL_CLOSED")
        return summary, True
    except Exception as exc:
        write_json(case_dir / "transport_runtime_failure.json", {
            "case_id": case_id, "error_type": type(exc).__name__,
            "error_message_redacted": str(exc).replace(key, "[REDACTED]"),
            "raw_model_content_frozen": raw_path.is_file(),
            "raw_model_content_sha256": digest(raw_path.read_bytes()) if raw_path.is_file() else None,
            "systemic_stop": True, "retry_count": 0})
        summary = {"case_id": case_id, "status": "SYSTEMIC_TRANSPORT_RUNTIME_STOP",
                   "provider_requests_attempted": 1, "inference_attempts_maximum": 1,
                   "raw_model_content_frozen": raw_path.is_file(), "rerun_count": 0}
        write_json(case_dir / "case_summary.json", summary)
        freeze_root(case_dir, "case_sha256", status="FAIL_CLOSED")
        return summary, True
    require(raw_path.is_file() and raw_path.read_bytes() == result.raw_response.encode("utf-8"),
            "raw response sink mismatch; systemic stop required")
    write_json(case_dir / "provider_response_metadata.json", {
        "case_id": case_id, "provider": "deepseek", "model": "deepseek-v4-pro",
        "finish_reason": result.finish_reason, "attempt_count": result.attempt_count,
        "raw_model_content_sha256": digest(raw_path.read_bytes()),
        "usage": result.usage, "provider_metadata": result.provider_metadata,
        "parser_warnings": result.warnings,
        "request_body_sha256": request["request_body_sha256"],
        "raw_frozen_before_deterministic_validation": True})
    if result.attempt_count != 1 or result.finish_reason != "stop" or result.warnings or not isinstance(result.payload, dict):
        summary = {"case_id": case_id, "status": "SYSTEMIC_PROVIDER_OUTPUT_STOP",
                   "provider_requests_attempted": 1, "inference_attempts": 1,
                   "raw_model_content_frozen": True, "rerun_count": 0}
        write_json(case_dir / "case_summary.json", summary)
        freeze_root(case_dir, "case_sha256", status="FAIL_CLOSED")
        return summary, True
    write_json(case_dir / "parsed_provider_payload.json", result.payload)
    try:
        _validate_local_schema(result.payload, PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA)
    except (ValueError, KeyError, TypeError) as exc:
        write_json(case_dir / "provider_schema_incompatibility.json", {
            "error_type": type(exc).__name__, "error": str(exc),
            "systemic_stop": True, "raw_output_preserved": True})
        summary = {"case_id": case_id, "status": "SYSTEMIC_SCHEMA_INCOMPATIBILITY_STOP",
                   "provider_requests_attempted": 1, "inference_attempts": 1,
                   "raw_model_content_frozen": True, "rerun_count": 0}
        write_json(case_dir / "case_summary.json", summary)
        freeze_root(case_dir, "case_sha256", status="FAIL_CLOSED")
        return summary, True
    try:
        summary = analyse_case(case_dir, case_id, result.payload, target)
    except Exception as exc:
        write_json(case_dir / "deterministic_runtime_failure.json", {
            "case_id": case_id, "error_type": type(exc).__name__,
            "error": str(exc), "systemic_stop": True,
            "raw_output_preserved": True, "retry_count": 0})
        summary = {"case_id": case_id, "status": "SYSTEMIC_DETERMINISTIC_RUNTIME_STOP",
                   "provider_requests_attempted": 1, "inference_attempts": 1,
                   "raw_model_content_frozen": True, "rerun_count": 0}
        write_json(case_dir / "case_summary.json", summary)
        freeze_root(case_dir, "case_sha256", status="FAIL_CLOSED")
        return summary, True
    summary.update({"provider_requests_attempted": 1, "inference_attempts": 1,
                    "raw_model_content_frozen": True,
                    "raw_model_content_sha256": digest(raw_path.read_bytes()),
                    "provider_payload_schema_valid": True})
    write_json(case_dir / "case_summary.json", summary)
    freeze_root(case_dir, "case_sha256", status="PASS" if summary["status"] == "DETERMINISTIC_PASS"
                else "FAIL_CLOSED")
    return summary, False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="consume at most seven explicitly authorized calls")
    args = parser.parse_args()
    upstream, targets, preflight_info = preflight()
    if not args.execute:
        print(json.dumps({"preflight": "PASS", "case_ids": CASES,
                          "request_count_maximum": 7, "provider_calls": 0,
                          "compiler_adapter": preflight_info["compiler_adapter"]}, sort_keys=True))
        return
    key = load_key()
    require(bool(key), "DeepSeek key disappeared after preflight")
    RUN.mkdir(parents=True, exist_ok=False)
    write_json(RUN / "upstream_root_verification.json", upstream)
    write_json(RUN / "frozen_generation_preflight.json", preflight_info)
    summaries = []
    systemic_stop = False
    for request in preflight_info["requests"]:
        case_id = request["case_id"]
        # No script/config/prompt/validator/compiler changes are allowed after
        # any call. Recheck immutable request bytes and roots before next call.
        require(digest(Path(__file__).read_bytes()) == preflight_info["generation_runner_sha256"],
                "runner changed during generation; stop before next call")
        for _, (path, root) in ROOTS.items():
            verify_root(path, root)
        require(digest(DeepSeekPlannerTransportV1_1().serialized_body(targets[case_id])) ==
                request["request_body_sha256"], "frozen request changed; stop before next call")
        summary, systemic_stop = run_one(case_id, targets[case_id], request, key)
        summaries.append(summary)
        print(json.dumps({"case_id": case_id, "status": summary["status"],
                          "requests_consumed": len(summaries),
                          "systemic_stop": systemic_stop}, sort_keys=True), flush=True)
        if systemic_stop:
            break
    total = len(summaries)
    require(total <= 7 and len({s["case_id"] for s in summaries}) == total, "attempt budget violation")
    final = {"artifact_schema_version": "Alpha2_3DeepSeekRemaining7GenerationSummaryV1",
             "status": "STOPPED_SYSTEMIC" if systemic_stop else "COMPLETED",
             "authorized_cases": list(CASES), "attempted_cases": [s["case_id"] for s in summaries],
             "unattempted_cases": [case for case in CASES if case not in {s["case_id"] for s in summaries}],
             "case_summaries": summaries, "provider_requests_attempted": total,
             "inference_attempts_maximum": total, "maximum_authorized_requests": 7,
             "case_101_rerun": False, "automatic_retries": 0, "repair_calls": 0,
             "openai_calls": 0, "network_literature_calls": 0,
             "retrieval_calls": 0, "candidate_records_seen": 0,
             "prompt_changed": False, "schema_changed": False,
             "deterministic_stack_changed_during_generation": False,
             "historical_assets_modified": False}
    write_json(RUN / "summary.json", final)
    root = freeze_root(RUN, "search_plan_v24_dev_alpha2_3_deepseek_remaining_7_sha256",
                       status="PASS" if not systemic_stop else "FAIL_CLOSED")
    print(json.dumps({"root": root, "summary": final}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
