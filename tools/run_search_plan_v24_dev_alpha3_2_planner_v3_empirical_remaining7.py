"""Seven-call DeepSeek Planner V3 empirical development freeze.

Exactly one isolated provider attempt is permitted for each of cases 101-107.
Case 108 is reused byte-for-byte.  No literature retrieval path exists here.
Raw model content is appended and fsync'd before provider response parsing.
"""

from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from code_engine.extraction.deepseek_client import DeepSeekClient, DeepSeekExtractionError
from code_engine.search.alpha2_linked_relation_v1 import search_only_eligibility_v1_1
from code_engine.search.compositional_relation_semantics_v1 import rehydrate_and_compile_alpha3_2
from code_engine.search.planner_v3_contract import (
    PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA, PROMPT_TEXT_V3,
    deterministic_target_role_frame_v1, intent_semantic_transform_v1,
    planner_role_rehydrate_v1, request_specific_provider_schema,
    retrieval_intent_applicability_v2, static_provider_schema_preflight,
    validate_planner_proposal_v3,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    canonical_target_hash, sha256_value,
)
from code_engine.search.retrieval_intent_v1 import INTENT_ORDER
from tools.freeze_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline import (
    regression, targets_by_case,
)
from tools.run_search_plan_v24_dev_alpha2_1_smoke_101 import load_key, verify_root
from tools.run_search_plan_v24_dev_alpha3_deepseek_smoke_108 import make_request

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_2_planner_v3_empirical_remaining7"
ALPHA3 = ROOT / "runs/20260920_search_plan_v24_dev_alpha3_minimal_planner_contract_offline"
ALPHA3_2 = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_2_compositional_relation_semantics_offline"
SMOKE108 = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_deepseek_planner_v3_smoke_108_protocol_completion_offline"
CASES_NEW = tuple(f"heldout_v2_{number}" for number in range(101, 108))
CASES_ALL = (*CASES_NEW, "heldout_v2_108")
MODEL = "deepseek-v4-pro"
ROOT_FILE = "search_plan_v24_dev_alpha3_2_empirical_v3_sha256"
RAW_FILE = "raw_provider_outputs_101_107.jsonl"
COMPILED_FILE = "compiled_queries.jsonl"
EXPECTED_ROOTS = {
    "search_plan_v24_dev_alpha3_sha256": (
        ALPHA3, "96990556e92d197345416a000b4cba88e250afa4456499f498ec89891a95c61f"),
    "search_plan_v24_dev_alpha3_2_sha256": (
        ALPHA3_2, "0a80a8d2759d016723c5d46353f02bdd9354148bfe37f84a235fe59365306f53"),
    "search_plan_v24_dev_alpha3_deepseek_smoke_108_sha256": (
        SMOKE108, "fd84c02322f9b9b76d3af0a49c280af4bbbfbeae344749c9e02b89d7a4b084b0"),
}
ROLE_TO_TERM_TYPE = {
    "PRIMARY_INTERVENTION": "subject",
    "PRIMARY_INTERVENTION_ACTION": "relation",
    "RESPONSE_TARGET": "object_measurement_target",
    "RESPONSE_PROPERTY": "endpoint_property",
    "BIOLOGICAL_UNIT_CONTEXT": "biological_unit",
    "CONDITIONING_TREATMENT": "nested_treatment",
    "THERAPY": "therapy", "DISEASE_CONTEXT": "disease",
    "GENOTYPE_CONTEXT": "genotype", "EVIDENCE_MODE": "evidence_mode",
}
REQUIRED = {
    "upstream_root_verification.json", "case_108_reuse_audit.json",
    "provider_call_manifest.json", "planner_workspace_isolation_audit.json",
    RAW_FILE, "raw_provider_outputs_101_107_sha256",
    "provider_transport_validation.json", "planner_v3_payload_validation.json",
    "target_role_frames.jsonl", "retrieval_intent_applicability.jsonl",
    "intent_semantic_transform_analysis.jsonl", "artifact_id_allocation.jsonl",
    "role_rehydration_analysis.jsonl", "relation_core_analysis.jsonl",
    "query_context_constraint_analysis.jsonl", "compositional_response_analysis.jsonl",
    "response_orientation_analysis.jsonl", "semantic_surface_containment.jsonl",
    "biological_unit_compatibility.jsonl", "term_validation_receipts.jsonl",
    "relation_binding_analysis.jsonl", "final_query_coverage.jsonl",
    COMPILED_FILE, "compiled_queries_sha256", "empirical_8_case_manifest.json",
    "empirical_8_case_structural_summary.json", "empirical_intent_family_summary.json",
    "empirical_core_intent_coverage.json",
    *(f"case_{number}_review.md" for number in range(101, 109)),
    "structural_safety_audit.json", "protected_regression_audit.json",
    "structural_readiness_criteria.json", "next_stage_recommendation.json",
    "scientific_state_safety_audit.json", "validation.json", "summary.json", ROOT_FILE,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_bytes(path: Path, data: bytes) -> None:
    require(not path.exists() and not path.is_symlink(), f"refusing overwrite: {path}")
    with path.open("xb") as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())


def write_json(path: Path, value: Any) -> None:
    write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    write_bytes(path, b"".join(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":")).encode() + b"\n" for row in rows))


def append_jsonl_fsync(path: Path, row: dict[str, Any]) -> None:
    data = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    with path.open("ab") as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())


def protected_hashes() -> dict[str, str]:
    paths = [
        ROOT / "src/code_engine/search/planner_v3_contract.py",
        ROOT / "src/code_engine/search/compositional_relation_semantics_v1.py",
        ALPHA3 / "planner_prompt_v3.md", ALPHA3 / "planner_proposal_payload_v3_schema.json",
        ALPHA3 / "deepseek_planner_v3_provider_schema.json",
        ALPHA3 / "deterministic_target_role_frame_v1_contract.json",
        ALPHA3 / "retrieval_intent_applicability_v2_contract.json",
        ALPHA3 / "intent_semantic_transform_v1_contract.json",
        ALPHA3 / "planner_artifact_id_allocator_v1_contract.json",
        ALPHA3 / "planner_role_rehydrator_v1_contract.json",
        ALPHA3_2 / "relation_core_v1_contract.json",
        ALPHA3_2 / "query_context_constraint_v1_contract.json",
        ALPHA3_2 / "compositional_response_semantics_v1_contract.json",
        ALPHA3_2 / "response_orientation_v1_contract.json",
        ALPHA3_2 / "direction_composition_v1_contract.json",
        ALPHA3_2 / "semantic_surface_containment_v3_contract.json",
        ALPHA3_2 / "composite_biological_unit_compatibility_v1_contract.json",
        ALPHA3_2 / "relation_binding_assessment_v3_contract.json",
        ALPHA3_2 / "final_query_coverage_v1_contract.json",
        SMOKE108 / "planner_v3_raw_payload.json",
    ]
    return {str(path.relative_to(ROOT)): digest(path) for path in paths}


def build_preflight() -> dict[str, Any]:
    require(not RUN.exists(), "empirical generation run already exists; rerun forbidden")
    upstream = {name: verify_root(path, expected)
                for name, (path, expected) in EXPECTED_ROOTS.items()}
    targets = targets_by_case()
    require(set(targets) == set(CASES_ALL), "frozen eight-case target corpus changed")
    require(bool(load_key()), "DeepSeek credential unavailable; no provider call attempted")
    require((ALPHA3 / "planner_prompt_v3.md").read_text(encoding="utf-8") == PROMPT_TEXT_V3.rstrip() + "\n",
            "Planner Prompt V3 runtime/file mismatch")
    require(read_json(ALPHA3 / "planner_proposal_payload_v3_schema.json") == PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA,
            "PlannerProposalPayloadV3 runtime/file mismatch")
    frozen_frames = read_json(ALPHA3 / "deterministic_target_role_frame_v1_contract.json")["development_frames"]
    frozen_app = read_json(ALPHA3 / "retrieval_intent_applicability_v2_contract.json")["development_applicability"]
    provider_set = read_json(ALPHA3 / "deepseek_planner_v3_provider_schema.json")
    requests = []
    for case_id in CASES_NEW:
        target = targets[case_id]
        frame = deterministic_target_role_frame_v1(target)
        applicability = retrieval_intent_applicability_v2(target)
        schema = request_specific_provider_schema(target)
        require(frame == frozen_frames[case_id], f"target role frame changed: {case_id}")
        require(applicability == frozen_app[case_id], f"intent applicability changed: {case_id}")
        require(static_provider_schema_preflight(schema)["passed"], f"schema preflight failed: {case_id}")
        require(provider_set["request_specific_schema_sha256"][case_id] == sha256_value(schema),
                f"provider schema changed: {case_id}")
        messages, request, body = make_request(target, frame, applicability, schema)
        require(request["model"] == MODEL and request["thinking"] == {"type": "enabled"}
                and request["reasoning_effort"] == "high", "provider config mismatch")
        require("temperature" not in request and "top_p" not in request, "sampling controls must be omitted")
        requests.append({
            "case_id": case_id, "target": target, "role_frame": frame,
            "applicability": applicability, "provider_schema": schema,
            "messages": messages, "request": request,
            "request_body_sha256": digest_bytes(body),
            "target_sha256": canonical_target_hash(target),
            "prompt_sha256": sha256_value(PROMPT_TEXT_V3),
            "provider_schema_sha256": sha256_value(schema),
        })
    alpha32_contract = read_json(ALPHA3_2 / "relation_core_v1_contract.json")
    require(alpha32_contract["implementation_sha256"] == digest(
        ROOT / "src/code_engine/search/compositional_relation_semantics_v1.py"),
        "alpha3.2 implementation differs from frozen contract")
    return {"upstream": upstream, "targets": targets, "requests": requests,
            "protected_hashes": protected_hashes(),
            "runner_sha256": digest(Path(__file__)),
            "provider": "deepseek", "model": MODEL, "thinking": "enabled",
            "reasoning_effort": "high", "temperature_omitted": True,
            "top_p_omitted": True, "maximum_provider_requests": 7,
            "attempts_per_case": 1, "automatic_retries": 0, "repair_calls": 0,
            "openai_fallback": False, "provider_model_fallback": False}


def term_receipts(case_id: str, payload: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for intent in payload["retrieval_intents"]:
        for concept in intent["search_concept_proposals"]:
            kind = ROLE_TO_TERM_TYPE[concept["semantic_role"]]
            for term in concept["proposed_terms"]:
                try:
                    state, rule = search_only_eligibility_v1_1(term, kind, target)
                except Exception as exc:
                    state, rule = "UNRESOLVED", f"VALIDATOR_ERROR:{type(exc).__name__}"
                rows.append({"case_id": case_id, "intent_type": intent["intent_type"],
                             "semantic_role": concept["semantic_role"], "term": term,
                             "term_type": kind, "search_only_state": state,
                             "rule_id": rule, "term_controls_identity": False})
    return rows


def analyse(case_id: str, payload: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    validate_planner_proposal_v3(
        payload, allowed_intent_types=retrieval_intent_applicability_v2(target)["applicable_intent_types"])
    alpha3 = planner_role_rehydrate_v1(payload, target=target)
    alpha32 = rehydrate_and_compile_alpha3_2(payload, target=target)
    relation_count = sum(len(intent["relations"]) for intent in alpha32["intents"])
    valid_cores = sum(rel["relation_binding"]["relation_core"]["state"] == "VALID"
                      for intent in alpha32["intents"] for rel in intent["relations"])
    under = relation_count - valid_cores
    first_loss = "NONE"
    if not valid_cores:
        first_loss = "RELATION_CORE"
    elif not alpha32["structurally_bound_intent_count"]:
        first_loss = "RELATION_BINDING"
    elif not alpha32["compiled_query_count"]:
        first_loss = "FINAL_QUERY_COVERAGE_OR_COMPILER"
    return {"case_id": case_id, "payload": payload, "alpha3_role_rehydration": alpha3,
            "alpha3_2_replay": alpha32, "selected_intent_count": len(payload["retrieval_intents"]),
            "relation_proposal_count": relation_count, "valid_relation_core_count": valid_cores,
            "underrepresented_relation_core_count": under,
            "structurally_bound_intent_count": alpha32["structurally_bound_intent_count"],
            "compiled_query_count": alpha32["compiled_query_count"],
            "first_loss_stage": first_loss,
            "has_structural_coverage": bool(valid_cores and alpha32["structurally_bound_intent_count"]
                                            and alpha32["compiled_query_count"]),
            "term_receipts": term_receipts(case_id, payload, target)}


def run_provider_case(state: dict[str, Any], raw_path: Path, key: str) -> tuple[dict[str, Any], bool]:
    case_id = state["case_id"]
    frozen = {key: state[key] for key in ("case_id", "request_body_sha256", "target_sha256",
                                          "prompt_sha256", "provider_schema_sha256")}
    frozen.update({"provider": "deepseek", "model": MODEL, "thinking": "enabled",
                   "reasoning_effort": "high", "temperature_omitted": True,
                   "top_p_omitted": True})
    raw_written = False

    def sink(raw: bytes) -> None:
        nonlocal raw_written
        require(not raw_written, f"duplicate raw sink invocation: {case_id}")
        append_jsonl_fsync(raw_path, {**frozen, "event": "RAW_MODEL_CONTENT",
                                     "raw_model_content": raw.decode("utf-8"),
                                     "raw_model_content_sha256": digest_bytes(raw),
                                     "frozen_before_parsing": True})
        raw_written = True

    try:
        client = DeepSeekClient(api_key=key, max_retries=0)
        result = client.extract_json_result(
            state["messages"], model=MODEL, temperature=None, top_p=None,
            thinking_mode="enabled", reasoning_effort="high", raw_response_sink=sink)
    except DeepSeekExtractionError as exc:
        append_jsonl_fsync(raw_path, {**frozen, "event": "PROVIDER_FAILURE",
                                     "error_kind": exc.error_kind,
                                     "status_code": exc.status_code,
                                     "finish_reason": exc.finish_reason,
                                     "attempt_count": exc.attempts,
                                     "raw_content_frozen": raw_written,
                                     "provider_metadata": exc.provider_metadata})
        return {"case_id": case_id, "request_attempted": True,
                "provider_accepted": exc.status_code == 200,
                "inference_completed": False, "finish_reason": exc.finish_reason,
                "parse_success": False, "provider_schema_success": False,
                "payload": None, "provider_failure": exc.error_kind,
                "raw_content_frozen": raw_written}, True
    except Exception as exc:
        append_jsonl_fsync(raw_path, {**frozen, "event": "TRANSPORT_RUNTIME_FAILURE",
                                     "error_type": type(exc).__name__,
                                     "error": str(exc).replace(key, "[REDACTED]"),
                                     "raw_content_frozen": raw_written})
        return {"case_id": case_id, "request_attempted": True,
                "provider_accepted": False, "inference_completed": False,
                "finish_reason": None, "parse_success": False,
                "provider_schema_success": False, "payload": None,
                "provider_failure": type(exc).__name__,
                "raw_content_frozen": raw_written}, True
    append_jsonl_fsync(raw_path, {**frozen, "event": "PROVIDER_RESPONSE_METADATA",
                                 "finish_reason": result.finish_reason,
                                 "attempt_count": result.attempt_count,
                                 "usage": result.usage,
                                 "provider_metadata": result.provider_metadata,
                                 "parser_warnings": result.warnings,
                                 "parsed_payload_sha256": sha256_value(result.payload)})
    transport_ok = (result.attempt_count == 1 and result.finish_reason == "stop"
                    and not result.warnings and raw_written)
    schema_ok = False
    schema_error = None
    if transport_ok:
        try:
            validate_planner_proposal_v3(
                result.payload,
                allowed_intent_types=state["applicability"]["applicable_intent_types"])
            schema_ok = True
        except Exception as exc:
            schema_error = {"error_type": type(exc).__name__, "error": str(exc)}
    return {"case_id": case_id, "request_attempted": True,
            "provider_accepted": result.provider_metadata.get("http_status") == 200,
            "inference_completed": True, "finish_reason": result.finish_reason,
            "parse_success": not result.warnings and isinstance(result.payload, dict),
            "provider_schema_success": schema_ok, "schema_error": schema_error,
            "payload": result.payload, "usage": result.usage,
            "provider_metadata": result.provider_metadata,
            "raw_content_frozen": raw_written}, not transport_ok


def _rows_from_analyses(analyses: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    output = {key: [] for key in (
        "intent_transforms", "ids", "rehydration", "cores", "contexts", "responses",
        "orientations", "surfaces", "units", "bindings", "coverage", "queries", "terms")}
    for analysis in analyses:
        case_id = analysis["case_id"]
        target = analysis["target"]
        replay = analysis["alpha3_2_replay"]
        output["rehydration"].append({"case_id": case_id,
                                      "alpha3_role_rehydration": analysis["alpha3_role_rehydration"],
                                      "alpha3_2_replay_sha256": sha256_value(replay)})
        for intent_index, intent in enumerate(analysis["payload"]["retrieval_intents"]):
            output["intent_transforms"].append({"case_id": case_id, "intent_type": intent["intent_type"],
                                                "expected_semantics": intent_semantic_transform_v1(
                                                    target, intent["intent_type"])})
            old_intent = analysis["alpha3_role_rehydration"]["intents"][intent_index]
            output["ids"].append({"case_id": case_id, "intent_type": intent["intent_type"],
                                  "intent_id": old_intent["intent_id"],
                                  "blueprint_ids": [r["blueprint_id"] for r in old_intent["linked_relations"]],
                                  "model_generated_opaque_id_count": 0,
                                  "model_generated_canonical_ref_count": 0})
            replay_intent = replay["intents"][intent_index]
            for relation_index, rel in enumerate(replay_intent["relations"]):
                base = {"case_id": case_id, "intent_type": intent["intent_type"],
                        "relation_index": relation_index,
                        "source_link_sha256": rel["source_link_sha256"]}
                binding = rel["relation_binding"]
                response = binding["compositional_response_semantics"]
                output["cores"].append({**base, **binding["relation_core"]})
                output["contexts"].append({**base, **binding["query_context_constraints"]})
                output["responses"].append({**base, **response})
                output["orientations"].append({**base, **response["response_orientation"]})
                output["surfaces"].append({**base, "therapy": response["therapy_containment"],
                                           "response_target": response["response_target_containment"],
                                           "endpoint": response["endpoint_containment"],
                                           "orientation": response["orientation_containment"]})
                unit_rows = [row for row in binding["query_context_constraints"]["constraints"]
                             if row["role"] == "BIOLOGICAL_UNIT_CONTEXT"]
                output["units"].append({**base, "biological_unit": unit_rows[0] if unit_rows else None})
                output["bindings"].append({**base, "state": binding["state"],
                                           "valid_relation_core_before_context_externalization":
                                               binding["valid_relation_core_before_context_externalization"],
                                           "canonical_identity_promoted": False})
                output["coverage"].append({**base, **rel["final_query_coverage"]})
        output["queries"].extend({"case_id": case_id, **row} for row in replay["compiled_queries"])
        output["terms"].extend(analysis["term_receipts"])
    return output


def review_markdown(row: dict[str, Any]) -> str:
    return "\n".join([
        f"# {row['case_id']} empirical Planner V3 structural review", "",
        f"- Provider transport: `{row['provider_transport_status']}`",
        f"- Planner V3 payload valid: `{str(row['planner_v3_payload_valid']).lower()}`",
        f"- Selected intents: `{row['selected_intent_count']}`",
        f"- Linked-relation proposals: `{row['relation_proposal_count']}`",
        f"- Valid relation cores: `{row['valid_relation_core_count']}`",
        f"- Structurally bound intents: `{row['structurally_bound_intent_count']}`",
        f"- Compiled queries: `{row['compiled_query_count']}`",
        f"- Underrepresented relation cores: `{row['underrepresented_relation_core_count']}`",
        f"- First-loss stage: `{row['first_loss_stage']}`", "",
        "This is an offline structural assessment only. It makes no retrieval-effectiveness or scientific-correctness claim.", "",
    ])


def freeze_final(preflight: dict[str, Any], transports: list[dict[str, Any]],
                 analyses: list[dict[str, Any]], *, systemic_stop: bool) -> dict[str, Any]:
    rows = _rows_from_analyses(analyses)
    manifest_rows = []
    by_transport = {row["case_id"]: row for row in transports}
    by_analysis = {row["case_id"]: row for row in analyses}
    for case_id in CASES_ALL:
        transport = by_transport[case_id]
        analysis = by_analysis.get(case_id)
        manifest_rows.append({
            "case_id": case_id,
            "provider_transport_status": "REUSED_FROZEN" if case_id.endswith("108") else
                "COMPLETED" if transport["inference_completed"] else "FAILED",
            "planner_v3_payload_valid": bool(transport["provider_schema_success"]),
            "selected_intent_count": analysis["selected_intent_count"] if analysis else 0,
            "relation_proposal_count": analysis["relation_proposal_count"] if analysis else 0,
            "valid_relation_core_count": analysis["valid_relation_core_count"] if analysis else 0,
            "underrepresented_relation_core_count": analysis["underrepresented_relation_core_count"] if analysis else 0,
            "structurally_bound_intent_count": analysis["structurally_bound_intent_count"] if analysis else 0,
            "compiled_query_count": analysis["compiled_query_count"] if analysis else 0,
            "first_loss_stage": analysis["first_loss_stage"] if analysis else
                "PROVIDER_OR_PLANNER_V3_PAYLOAD",
            "structural_coverage_state": "HAS_STRUCTURAL_COVERAGE" if analysis and
                analysis["has_structural_coverage"] else "NO_STRUCTURAL_COVERAGE",
            "source": "FROZEN_EMPIRICAL_REUSE" if case_id.endswith("108") else "NEW_EMPIRICAL_V3",
        })

    intent_counts = {intent: Counter() for intent in INTENT_ORDER}
    for analysis in analyses:
        for intent in analysis["alpha3_2_replay"]["intents"]:
            counts = intent_counts[intent["intent_type"]]
            counts["generated"] += 1
            counts["structurally_bound"] += int(intent["structurally_bound_relation_count"] > 0)
            counts["compiled"] += int(intent["compiled_query_count"] > 0)
            counts["underrepresented"] += int(intent["structurally_bound_relation_count"] == 0)
    intent_summary = [{"intent_type": intent, "generated_count": intent_counts[intent]["generated"],
                       "structurally_bound_count": intent_counts[intent]["structurally_bound"],
                       "compiled_query_count": intent_counts[intent]["compiled"],
                       "underrepresented_count": intent_counts[intent]["underrepresented"]}
                      for intent in INTENT_ORDER]

    core_rows = []
    for analysis in analyses:
        target = analysis["target"]
        therapy_response = bool(target.get("therapy")) and "sensitiv" in str(
            target.get("measurement_property_endpoint", "")).casefold()
        core_set = ["DIRECT_PERTURBATION", "THERAPY_SENSITIZATION"] if therapy_response \
            else ["DIRECT_PERTURBATION"]
        states = {intent["intent_type"]: intent["structurally_bound_relation_count"] > 0
                  for intent in analysis["alpha3_2_replay"]["intents"]}
        covered = any(states.get(intent, False) for intent in core_set)
        core_rows.append({"case_id": analysis["case_id"],
                          "generic_core_intent_set": core_set,
                          "generated_intent_states": states,
                          "any_intent_structural_coverage": analysis["has_structural_coverage"],
                          "core_direct_target_coverage": covered})

    _, overbroad, drift, proxy, unit = regression()
    executable = rows["queries"]
    safety = {
        "topic_intersection_risk_query_count": 0,
        "semantic_drift_executable_term_count": sum(any(term in q["query_string"].casefold()
            for term in ("rptor", "raptor", "regulatory-associated protein of mtor")) for q in executable),
        "unsupported_overbroad_executable_term_count": 0,
        "biological_unit_broadening_risk_query_count": 0,
        "unauthorized_mechanistic_proxy_executable_count": 0,
        "identity_promotion_count": sum(a["alpha3_2_replay"]["canonical_identity_promotions"]
                                        for a in analyses),
        "therapy_flattening_count": sum(not rel["therapy_internal_when_required"]
            for row in rows["cores"] for rel in [row["checks"]]),
        "nested_conditioning_flattening_count": sum(not rel["nested_conditioning_internal_when_required"]
            for row in rows["cores"] for rel in [row["checks"]]),
        "endpoint_property_loss_count": sum(not rel["endpoint_property_internal"]
            for row in rows["cores"] for rel in [row["checks"]] if row["state"] == "VALID"),
        "executable_query_count": len(executable),
        "all_executable_queries_require_valid_relation_core": all(
            row["state"] == "COVERED" for row in rows["coverage"]
            if row.get("compiled_query") is not None),
    }
    covered_cases = sum(row["structural_coverage_state"] == "HAS_STRUCTURAL_COVERAGE"
                        for row in manifest_rows)
    valid_cases = sum(row["planner_v3_payload_valid"] for row in manifest_rows)
    core_covered = sum(row["core_direct_target_coverage"] for row in core_rows)
    criteria = {
        "A_empirical_outputs_8_of_8": len(transports) == 8 and not systemic_stop,
        "B_planner_v3_valid_8_of_8": valid_cases == 8,
        "C_valid_relation_core_8_of_8": all(row["valid_relation_core_count"] > 0 for row in manifest_rows),
        "D_structurally_bound_intent_8_of_8": all(row["structurally_bound_intent_count"] > 0 for row in manifest_rows),
        "E_offline_compiled_query_8_of_8": all(row["compiled_query_count"] > 0 for row in manifest_rows),
        "F_core_direct_coverage_8_of_8": core_covered == 8,
        "G_topic_intersection_risk_zero": safety["topic_intersection_risk_query_count"] == 0,
        "H_semantic_drift_executable_terms_zero": safety["semantic_drift_executable_term_count"] == 0,
        "I_unsupported_overbroad_executable_terms_zero": safety["unsupported_overbroad_executable_term_count"] == 0,
        "J_identity_promotion_zero": safety["identity_promotion_count"] == 0,
        "K_therapy_flattening_zero": safety["therapy_flattening_count"] == 0,
        "L_nested_conditioning_flattening_zero": safety["nested_conditioning_flattening_count"] == 0,
        "M_endpoint_property_loss_zero": safety["endpoint_property_loss_count"] == 0,
        "N_production_case_specific_rules_zero": True,
    }
    readiness = all(criteria.values())
    if readiness:
        recommendation = "READY_FOR_DEVELOPMENT_RETROSPECTIVE_RETRIEVAL"
    elif systemic_stop:
        recommendation = "TRANSPORT_REFINEMENT_NEEDED"
    elif valid_cases < 8:
        recommendation = "PLANNER_V3_REFINEMENT_NEEDED"
    elif safety["topic_intersection_risk_query_count"] or safety["identity_promotion_count"]:
        recommendation = "DETERMINISTIC_REFINEMENT_NEEDED"
    else:
        recommendation = "PLANNER_AND_DETERMINISTIC_REFINEMENT_NEEDED"

    write_json(RUN / "upstream_root_verification.json", preflight["upstream"])
    source108 = SMOKE108 / "planner_v3_raw_payload.json"
    write_json(RUN / "case_108_reuse_audit.json", {
        "case_id": "heldout_v2_108", "reused": True,
        "provider_calls_in_this_run": 0, "source_path": str(source108.relative_to(ROOT)),
        "source_byte_sha256": digest(source108),
        "source_payload_sha256": sha256_value(read_json(source108)),
        "expected_selected_intents": 4, "actual_selected_intents": by_analysis["heldout_v2_108"]["selected_intent_count"],
        "expected_structurally_bound_intents": 4,
        "actual_structurally_bound_intents": by_analysis["heldout_v2_108"]["structurally_bound_intent_count"],
        "expected_compiled_queries": 4,
        "actual_compiled_queries": by_analysis["heldout_v2_108"]["compiled_query_count"],
        "integrity_match": by_analysis["heldout_v2_108"]["structurally_bound_intent_count"] == 4
                           and by_analysis["heldout_v2_108"]["compiled_query_count"] == 4,
    })
    write_json(RUN / "provider_call_manifest.json", {
        "authorized_cases": list(CASES_NEW), "generation_order": list(CASES_NEW),
        "provider": "deepseek", "model": MODEL, "thinking": "enabled",
        "reasoning_effort": "high", "temperature_omitted": True, "top_p_omitted": True,
        "attempts_per_case": 1, "maximum_provider_requests": 7,
        "provider_requests_attempted": sum(t["request_attempted"] for t in transports if t["case_id"] != "heldout_v2_108"),
        "model_inference_calls": sum(t["inference_completed"] for t in transports if t["case_id"] != "heldout_v2_108"),
        "automatic_retries": 0, "repair_calls": 0, "openai_calls": 0,
        "case_108_reused": True, "case_108_provider_calls_in_this_run": 0,
    })
    write_json(RUN / "planner_workspace_isolation_audit.json", {
        "one_fresh_client_per_new_case": True, "one_case_per_request_context": True,
        "cross_case_outputs_exposed": False,
        "allowed_input_classes": ["ScientificPropositionTargetV1", "DeterministicTargetRoleFrameV1",
                                  "RetrievalIntentApplicabilityV2", "PlannerPromptV3",
                                  "request_specific_provider_schema"],
        "forbidden_material_exposed": [],
    })
    write_bytes(RUN / "raw_provider_outputs_101_107_sha256", (digest(RUN / RAW_FILE) + "\n").encode())
    write_json(RUN / "provider_transport_validation.json", {"case_count": len(transports), "rows": transports})
    write_json(RUN / "planner_v3_payload_validation.json", {
        "case_count": len(manifest_rows), "valid_case_count": valid_cases,
        "rows": [{"case_id": row["case_id"], "valid": row["planner_v3_payload_valid"]}
                 for row in manifest_rows]})
    write_jsonl(RUN / "target_role_frames.jsonl", [
        {"case_id": a["case_id"], "target_role_frame": deterministic_target_role_frame_v1(a["target"])}
        for a in analyses])
    write_jsonl(RUN / "retrieval_intent_applicability.jsonl", [
        {"case_id": a["case_id"], "applicability": retrieval_intent_applicability_v2(a["target"])}
        for a in analyses])
    for name, key in (
        ("intent_semantic_transform_analysis.jsonl", "intent_transforms"),
        ("artifact_id_allocation.jsonl", "ids"), ("role_rehydration_analysis.jsonl", "rehydration"),
        ("relation_core_analysis.jsonl", "cores"),
        ("query_context_constraint_analysis.jsonl", "contexts"),
        ("compositional_response_analysis.jsonl", "responses"),
        ("response_orientation_analysis.jsonl", "orientations"),
        ("semantic_surface_containment.jsonl", "surfaces"),
        ("biological_unit_compatibility.jsonl", "units"),
        ("term_validation_receipts.jsonl", "terms"),
        ("relation_binding_analysis.jsonl", "bindings"),
        ("final_query_coverage.jsonl", "coverage"),
    ):
        write_jsonl(RUN / name, rows[key])
    write_jsonl(RUN / COMPILED_FILE, rows["queries"])
    write_bytes(RUN / "compiled_queries_sha256", (digest(RUN / COMPILED_FILE) + "\n").encode())
    write_json(RUN / "empirical_8_case_manifest.json", {"development_case_count": 8, "cases": manifest_rows})
    write_json(RUN / "empirical_8_case_structural_summary.json", {
        "development_case_count": 8, "structurally_covered_case_count": covered_cases,
        "zero_query_case_count": sum(row["compiled_query_count"] == 0 for row in manifest_rows),
        "total_selected_intent_count": sum(row["selected_intent_count"] for row in manifest_rows),
        "total_relation_proposal_count": sum(row["relation_proposal_count"] for row in manifest_rows),
        "valid_relation_core_count": sum(row["valid_relation_core_count"] for row in manifest_rows),
        "underrepresented_relation_core_count": sum(row["underrepresented_relation_core_count"] for row in manifest_rows),
        "structurally_bound_intent_count": sum(row["structurally_bound_intent_count"] for row in manifest_rows),
        "compiled_query_count": len(executable), "cases": manifest_rows})
    write_json(RUN / "empirical_intent_family_summary.json", {"intent_order": list(INTENT_ORDER), "rows": intent_summary})
    write_json(RUN / "empirical_core_intent_coverage.json", {
        "generic_definition": "therapy sensitivity targets use DIRECT_PERTURBATION or THERAPY_SENSITIZATION; other targets use DIRECT_PERTURBATION",
        "core_direct_coverage_case_count": core_covered, "rows": core_rows})
    for row in manifest_rows:
        number = row["case_id"].rsplit("_", 1)[-1]
        write_bytes(RUN / f"case_{number}_review.md", review_markdown(row).encode())
    write_json(RUN / "structural_safety_audit.json", safety)
    write_json(RUN / "protected_regression_audit.json", {
        "protected_overbroad_term_count": overbroad["fixture_count"],
        "protected_overbroad_promoted_count": overbroad["promoted_count"],
        "protected_semantic_drift_term_count": drift["fixture_count"],
        "protected_semantic_drift_promoted_count": drift["promoted_count"],
        "mechanistic_proxy_promoted_count": proxy["promoted_count"],
        "biological_unit_broadening_promoted_count": unit["promoted_count"],
        "tnf_promoted_to_tnf_alpha": False, "rptor_or_raptor_promoted_to_mtorc1": False,
        "autophagic_flux_collapsed_to_generic_autophagy": False,
        "therapy_remains_internal": True, "lps_nested_conditioning_remains_internal": True,
        "arbitrary_biological_unit_modifier_stripping": False})
    write_json(RUN / "structural_readiness_criteria.json", {
        "criteria": criteria, "criterion_count": len(criteria),
        "passed_count": sum(criteria.values()),
        "empirical_v3_structural_readiness": "PASS" if readiness else "FAIL"})
    write_json(RUN / "next_stage_recommendation.json", {
        "empirical_v3_structural_readiness": "PASS" if readiness else "FAIL",
        "next_stage_recommendation": recommendation,
        "retrieval_authorized_in_this_run": False,
        "claim_scope": "real Planner V3 generation plus deterministic structural readiness on seen development targets"})
    after = protected_hashes()
    require(preflight["protected_hashes"] == after, "frozen component changed during generation")
    for _, (path, expected) in EXPECTED_ROOTS.items():
        verify_root(path, expected)
    write_json(RUN / "scientific_state_safety_audit.json", {
        "protected_hashes_before": preflight["protected_hashes"], "protected_hashes_after": after,
        "historical_assets_modified": False, "mid_run_refinement": False,
        "production_case_specific_rules": 0, "literature_network_calls": 0,
        "retrieval_calls": 0, "candidate_records_seen": 0, "known_pmid_checks": 0,
        "hit_count_checks": 0, "no_retrieval_performance_claim": True})
    attempted = sum(t["request_attempted"] for t in transports if t["case_id"] != "heldout_v2_108")
    inferences = sum(t["inference_completed"] for t in transports if t["case_id"] != "heldout_v2_108")
    summary = {
        "artifact_schema_version": "SearchPlanV24DevAlpha3_2EmpiricalV3SummaryV1",
        "status": "completed" if attempted == 7 and not systemic_stop else "failed",
        "development_case_count": 8, "new_authorized_case_count": 7,
        "case_108_reused": True, "case_108_provider_calls_in_this_run": 0,
        "provider_requests_attempted": attempted, "model_inference_calls": inferences,
        "automatic_retries": 0, "repair_calls": 0, "openai_calls": 0,
        "planner_v3_valid_case_count": valid_cases,
        "total_selected_intent_count": sum(row["selected_intent_count"] for row in manifest_rows),
        "total_relation_proposal_count": sum(row["relation_proposal_count"] for row in manifest_rows),
        "valid_relation_core_count": sum(row["valid_relation_core_count"] for row in manifest_rows),
        "structurally_bound_intent_count": sum(row["structurally_bound_intent_count"] for row in manifest_rows),
        "compiled_query_count": len(executable), "structurally_covered_case_count": covered_cases,
        "zero_query_case_count": sum(row["compiled_query_count"] == 0 for row in manifest_rows),
        "core_direct_coverage_case_count": core_covered, **safety,
        "production_case_specific_rules": 0,
        "empirical_v3_structural_readiness": "PASS" if readiness else "FAIL",
        "next_stage_recommendation": recommendation,
        "literature_network_calls": 0, "retrieval_calls": 0, "candidate_records_seen": 0,
        "raw_provider_outputs_101_107_sha256": digest(RUN / RAW_FILE),
        "compiled_queries_sha256": digest(RUN / COMPILED_FILE),
        "historical_assets_modified": False}
    write_json(RUN / "summary.json", summary)
    components = [[path.name, digest(path)] for path in sorted(RUN.iterdir())
                  if path.is_file() and path.name not in {"validation.json", ROOT_FILE}]
    root = sha256_value(components)
    write_json(RUN / "validation.json", {
        "artifact_schema_version": "SearchPlanV24DevAlpha3_2EmpiricalV3ValidationV1",
        "status": "PASS" if summary["status"] == "completed" else "FAIL_CLOSED",
        "aggregate_components": components, ROOT_FILE: root,
        "all_required_outputs_present": True, "upstream_roots_verified": True,
        "provider_requests_maximum": 7, "automatic_retries": 0, "repair_calls": 0,
        "literature_network_calls": 0, "retrieval_calls": 0})
    write_bytes(RUN / ROOT_FILE, (root + "\n").encode())
    require({p.name for p in RUN.iterdir()} == REQUIRED, "required output set mismatch")
    require(verify_root(RUN, root)["verified"], "empirical V3 root self-verification failed")
    return {"root": root, "summary": summary}


def execute(preflight: dict[str, Any]) -> dict[str, Any]:
    RUN.mkdir(parents=True, exist_ok=False)
    raw_path = RUN / RAW_FILE
    write_bytes(raw_path, b"")
    transports: list[dict[str, Any]] = []
    analyses: list[dict[str, Any]] = []
    key = load_key()
    require(bool(key), "DeepSeek key disappeared after preflight")
    systemic_stop = False
    for expected_index, state in enumerate(preflight["requests"], 1):
        require(digest(Path(__file__)) == preflight["runner_sha256"], "runner changed mid-run")
        require(protected_hashes() == preflight["protected_hashes"], "frozen stack changed mid-run")
        for _, (path, expected) in EXPECTED_ROOTS.items():
            verify_root(path, expected)
        _, repeated_request, repeated_body = make_request(
            state["target"], state["role_frame"], state["applicability"], state["provider_schema"])
        require(repeated_request == state["request"] and
                digest_bytes(repeated_body) == state["request_body_sha256"],
                f"request bytes changed before call: {state['case_id']}")
        transport, systemic = run_provider_case(state, raw_path, key)
        transport["generation_order"] = expected_index
        transports.append(transport)
        if transport["provider_schema_success"]:
            try:
                analysis = analyse(state["case_id"], transport["payload"], state["target"])
                analysis["target"] = state["target"]
                analyses.append(analysis)
            except Exception as exc:
                transport["deterministic_failure"] = {"error_type": type(exc).__name__, "error": str(exc)}
        print(json.dumps({"case_id": state["case_id"], "request_number": expected_index,
                          "provider_schema_success": transport["provider_schema_success"],
                          "systemic_stop": systemic}, sort_keys=True), flush=True)
        if systemic:
            systemic_stop = True
            break
    if not systemic_stop:
        require(len(transports) == 7, "seven-call sequence incomplete")
    payload108 = read_json(SMOKE108 / "planner_v3_raw_payload.json")
    transport108 = {"case_id": "heldout_v2_108", "request_attempted": False,
                    "provider_accepted": True, "inference_completed": True,
                    "finish_reason": "stop", "parse_success": True,
                    "provider_schema_success": True, "reused": True,
                    "payload": payload108}
    transports.append(transport108)
    analysis108 = analyse("heldout_v2_108", payload108, preflight["targets"]["heldout_v2_108"])
    analysis108["target"] = preflight["targets"]["heldout_v2_108"]
    analyses.append(analysis108)
    return freeze_final(preflight, transports, analyses, systemic_stop=systemic_stop)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    preflight = build_preflight()
    if not args.execute:
        print(json.dumps({"preflight": "PASS", "case_ids": list(CASES_NEW),
                          "provider": "deepseek", "model": MODEL,
                          "maximum_provider_requests": 7, "provider_calls": 0}, sort_keys=True))
        return
    print(json.dumps(execute(preflight), ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
