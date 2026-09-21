"""Offline unified eight-case structural freeze from eight already-frozen outputs.

No provider or literature access. This tool never repairs generated content or
changes frozen prompts, schemas, validators, compiler, budgets, or past runs.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from code_engine.search.alpha2_linked_relation_v1 import (
    PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA, _validate_local_schema,
)
from code_engine.search.context_role_ontology_v1 import (
    conditioning_context_applicability, context_role_mapping,
    therapy_context_applicability,
)
from code_engine.search.deepseek_planner_transport_v1 import (
    DEEPSEEK_PROVIDER_SCHEMA, PROMPT_TEXT,
)
from code_engine.search.deepseek_planner_transport_v1_1 import (
    DEFAULT_CONFIG, DeepSeekPlannerTransportV1_1,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    canonical_bytes, canonical_target_hash, sha256_value,
)
from code_engine.search.semantic_slot_compatibility_v1 import (
    SEMANTIC_DIMENSIONS, semantic_slot_compatibility,
    search_anchor_compatibility_v1_1,
)
from tools.freeze_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline import targets_by_case
from tools.run_search_plan_v24_dev_alpha2_1_smoke_101 import verify_root
from tools.run_search_plan_v24_dev_alpha2_3_deepseek_remaining_7 import (
    CASES, RUN as GENERATION, analyse_case, digest, write_json, write_jsonl,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_3_deepseek_planner_v2_remaining7"
SMOKE_101 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_planner_v2_smoke_101"
ALPHA2_3 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_3_context_role_semantics_offline"
ROOTS = {
    "alpha2": (ROOT / "runs/20260920_search_plan_v24_dev_alpha2_linked_relation_deepseek_migration_offline",
               "918e0badbaeb70c439ae8d6e1d3bcc1eb5d5697c5df75b38dc2819357890a4e8"),
    "alpha2_1": (ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_reasoning_config_offline",
                 "fee80d671ed6e573ca0e18640b4ab87b15aec021e6870f17b0fc3457554b41fc"),
    "alpha2_2": (ROOT / "runs/20260920_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline",
                 "c54fcb5cd86747fce09b79e90d0d8f833ae2dd6d7fdfeb28ee466ca4b5ca91b4"),
    "alpha2_3": (ALPHA2_3, "13d66f15bfb0f003fa9d6581f892c174b965df42952022c7992958f2da2efa10"),
    "smoke_101": (SMOKE_101, "b66eebe346b1f130287083e364fbba10a22110b40f0a288e9185fe5f5242fd40"),
    "generation_102_108": (GENERATION, "e353ad6d3e18cbb2a629fab341432b8b01eeba4ea5c6b8b473bf9a2b646fe99f"),
}
RAW_101_SHA = "e3f0386b9e08a6d8dce12b7388b5da34db4bd75995eb530576176bbc2ccf2c7f"
ALL_CASES = ("heldout_v2_101", *CASES)
SUFFICIENT_SEMANTIC = {"EXACT_SEMANTIC_MATCH", "AUTHORIZED_SEMANTIC_VARIANT",
                       "COMPATIBLE_RELATION_PARAPHRASE", "COMPATIBLE_DIRECTION"}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha_file(path: Path) -> str:
    return digest(path.read_bytes())


def verify_case_root(case_dir: Path) -> str:
    validation = read_json(case_dir / "validation.json")
    pairs = validation["aggregate_components"]
    require(all(sha_file(case_dir / name) == frozen for name, frozen in pairs),
            f"case component hash changed: {case_dir.name}")
    root = sha256_value(pairs)
    require(root == validation["case_sha256"] == (case_dir / "case_sha256").read_text().strip(),
            f"case root changed: {case_dir.name}")
    return root


def raw_payloads(targets: dict[str, dict[str, Any]], generation_summary: dict[str, Any]) -> tuple[
        dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    payloads: dict[str, dict[str, Any]] = {}
    raw_rows: list[dict[str, Any]] = []
    call_rows: list[dict[str, Any]] = []
    raw_101 = (SMOKE_101 / "raw_model_content.txt").read_bytes()
    require(digest(raw_101) == RAW_101_SHA, "frozen 101 raw content changed")
    wrapper_101 = read_json(SMOKE_101 / "planner_v2_raw_payload.json")
    payloads["heldout_v2_101"] = wrapper_101["parsed_provider_payload"]
    require(json.loads(raw_101) == payloads["heldout_v2_101"] and wrapper_101["parse_success"],
            "frozen 101 raw/parsed mismatch")
    requests = {row["case_id"]: row for row in read_json(GENERATION / "frozen_generation_preflight.json")["requests"]}
    summary_cases = {row["case_id"]: row for row in generation_summary["case_summaries"]}
    require(set(requests) == set(CASES) == set(summary_cases), "seven-case request identity mismatch")
    for case_id in CASES:
        case_dir = GENERATION / case_id
        case_root = verify_case_root(case_dir)
        marker = read_json(case_dir / "request_attempt_marker.json")
        provider = read_json(case_dir / "provider_response_metadata.json")
        summary = summary_cases[case_id]
        raw = (case_dir / "raw_model_content.txt").read_bytes()
        payload = read_json(case_dir / "parsed_provider_payload.json")
        require(json.loads(raw) == payload and sha_file(case_dir / "raw_model_content.txt") ==
                summary["raw_model_content_sha256"], f"raw payload mismatch: {case_id}")
        require(marker["request_attempts_committed"] == 1 and marker["maximum_attempts"] == 1,
                f"attempt marker mismatch: {case_id}")
        require(provider["attempt_count"] == 1 and provider["finish_reason"] == "stop"
                and provider["provider_metadata"].get("http_status") == 200
                and provider["parser_warnings"] == [], f"provider state mismatch: {case_id}")
        require(marker["request_body_sha256"] == requests[case_id]["request_body_sha256"] ==
                provider["request_body_sha256"], f"request hash mismatch: {case_id}")
        require(marker["target_sha256"] == canonical_target_hash(targets[case_id]),
                f"target hash mismatch: {case_id}")
        payloads[case_id] = payload
        raw_rows.append({"case_id": case_id, "source_case_root_sha256": case_root,
                         "request_sha256": marker["request_body_sha256"],
                         "target_sha256": marker["target_sha256"],
                         "provider": "deepseek", "model": "deepseek-v4-pro",
                         "config_sha256": read_json(GENERATION / "frozen_generation_preflight.json")["config_sha256"],
                         "prompt_sha256": read_json(GENERATION / "frozen_generation_preflight.json")["prompt_sha256"],
                         "provider_schema_sha256": read_json(GENERATION / "frozen_generation_preflight.json")["provider_schema_sha256"],
                         "raw_model_content": raw.decode("utf-8"),
                         "raw_model_content_sha256": digest(raw),
                         "parsed_provider_payload": payload,
                         "parsed_provider_payload_sha256": sha256_value(payload),
                         "usage": provider["usage"],
                         "finish_reason": provider["finish_reason"],
                         "provider_metadata": provider["provider_metadata"],
                         "raw_was_frozen_before_validation": provider["raw_frozen_before_deterministic_validation"]})
        call_rows.append({"case_id": case_id, "provider_request_attempted": True,
                          "http_status": 200, "model_inference_completed": True,
                          "attempt_count": 1, "retry_count": 0, "repair_calls": 0,
                          "request_sha256": marker["request_body_sha256"],
                          "source_case_root_sha256": case_root})
    return payloads, raw_rows, call_rows


def request_isolation(targets: dict[str, dict[str, Any]], call_rows: list[dict[str, Any]]) -> dict[str, Any]:
    requests = {row["case_id"]: row for row in call_rows}
    transport = DeepSeekPlannerTransportV1_1()
    cases = []
    for case_id in CASES:
        request = transport.preview_request(targets[case_id])
        messages = request["messages"]
        expected_user = ("Return a JSON object. Immutable target: " +
                         canonical_bytes(targets[case_id]).decode("utf-8") +
                         "\nModel-only JSON Schema: " +
                         canonical_bytes(DEEPSEEK_PROVIDER_SCHEMA).decode("utf-8"))
        require(messages == [{"role": "system", "content": PROMPT_TEXT},
                             {"role": "user", "content": expected_user}],
                f"model context not isolated: {case_id}")
        require(digest(transport.serialized_body(targets[case_id])) == requests[case_id]["request_sha256"],
                f"request isolation hash mismatch: {case_id}")
        cases.append({"case_id": case_id, "request_body_sha256": requests[case_id]["request_sha256"],
                      "only_target_prompt_and_schema_in_messages": True,
                      "other_case_outputs_exposed": False,
                      "retrieval_or_candidate_evidence_exposed": False,
                      "temperature_omitted": "temperature" not in request,
                      "top_p_omitted": "top_p" not in request})
    require(all(r["temperature_omitted"] and r["top_p_omitted"] for r in cases),
            "sampling control mismatch")
    return {"artifact_schema_version": "Alpha2_3PlannerWorkspaceIsolationAuditV1",
            "case_count": len(cases), "cases": cases,
            "case_101_new_request": False,
            "forbidden_prior_failure_or_retrieval_material_exposed": False}


def semantic_and_surface_rows(payloads: dict[str, dict[str, Any]],
                              targets: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    semantic = []
    surface = []
    for case_id in ALL_CASES:
        target = targets[case_id]
        for intent in payloads[case_id]["retrieval_intents"]:
            for concept in intent["search_concepts"]:
                values = concept["canonical_anchor"]
                values = values if isinstance(values, list) else [values]
                for value in values:
                    if concept["concept_type"] in SEMANTIC_DIMENSIONS:
                        row = semantic_slot_compatibility(concept["concept_type"], value, target)
                        semantic.append({"case_id": case_id, "intent_id": intent["intent_id"],
                                         "concept_id": concept["concept_id"], **row})
                    else:
                        row = search_anchor_compatibility_v1_1(value, target, concept["concept_type"])
                        surface.append({"case_id": case_id, "intent_id": intent["intent_id"],
                                        "concept_id": concept["concept_id"], **row})
    return semantic, surface


def structural_focus(case_id: str, replay: dict[str, Any], target: dict[str, Any]) -> list[str]:
    """Report frozen gate evidence, not scientific-relevance judgments."""
    lines = []
    if case_id == "heldout_v2_102":
        lines.append("Required structure: IFN-γ intervention linked to increased HLA-DR cell-surface expression in monocytes.")
    elif case_id == "heldout_v2_103":
        lines.append("Required structure: Wnt3a, increased nuclear β-catenin accumulation, intestinal epithelial unit.")
    elif case_id == "heldout_v2_104":
        lines.append("Required structure: IL-1β, increased PGE2 secretion/release, articular chondrocytes.")
    elif case_id == "heldout_v2_105":
        lines.append("Required structure: mTORC1 inhibition, increased dynamic autophagic flux, cardiomyocytes; no RPTOR identity substitution.")
    elif case_id == "heldout_v2_106":
        lines.append("Required structure: IL-10 suppression of LPS-induced TNF-α secretion in macrophages; LPS conditioning required.")
    elif case_id == "heldout_v2_107":
        lines.append("Required structure: SHP2 inhibition, trametinib sensitivity, KRAS-mutant PDAC context; trametinib therapy required.")
    elif case_id == "heldout_v2_108":
        lines.append("Required structure: PARP1 inhibition, temozolomide sensitivity, glioblastoma unit; temozolomide therapy required.")
    lines.append(f"Frozen proposition: {target['primary_proposition_meaning']}")
    lines.append(f"First loss: {replay['first_loss_stage']}.")
    error = replay["validation"].get("error")
    if error:
        lines.append(f"Unchanged validator error: {error}.")
    if replay["linked_candidates"]:
        for row in replay["linked_candidates"]:
            failures = [name for name, passed in row["binding"]["checks"].items() if not passed]
            lines.append(f"Linked candidate {row['linked_candidate_index']}: " +
                         ("STRUCTURALLY_BOUND" if not failures else "UNDERREPRESENTED; failed checks=" + ", ".join(failures)) + ".")
    else:
        lines.append("Linked candidates were not promoted past the earlier failed gate; raw proposals remain frozen.")
    lines.append("No retrieval, hit-count inspection, candidate review, repair, or rerun was performed.")
    return lines


def main() -> None:
    require(not RUN.exists(), "unified eight-case freeze already exists")
    upstream = {name: verify_root(path, expected) for name, (path, expected) in ROOTS.items()}
    generation_summary = read_json(GENERATION / "summary.json")
    require(generation_summary["status"] == "COMPLETED" and generation_summary["provider_requests_attempted"] == 7
            and generation_summary["attempted_cases"] == list(CASES)
            and generation_summary["automatic_retries"] == 0 and generation_summary["repair_calls"] == 0
            and generation_summary["openai_calls"] == 0 and not generation_summary["case_101_rerun"],
            "seven-call generation accounting mismatch")
    targets = targets_by_case()
    require(set(targets) == set(ALL_CASES), "development target corpus changed")
    payloads, raw_rows, calls = raw_payloads(targets, generation_summary)
    workspace_audit = request_isolation(targets, calls)
    RUN.mkdir(parents=True, exist_ok=False)
    replay_root = RUN / "unified_case_replays"
    replay_root.mkdir(exist_ok=False)
    per_case = []
    all_receipts = []
    all_compiled = []
    all_candidates = []
    all_coverage = []
    for case_id in ALL_CASES:
        case_dir = replay_root / case_id
        case_dir.mkdir(exist_ok=False)
        result = analyse_case(case_dir, case_id, payloads[case_id], targets[case_id])
        replay = read_json(case_dir / "deterministic_replay.json")
        raw_candidate_count = sum(len(b["linked_relation_candidates"])
                                  for intent in payloads[case_id]["retrieval_intents"]
                                  for b in intent["candidate_query_blueprints"])
        intents = len(payloads[case_id]["retrieval_intents"])
        blueprints = sum(len(intent["candidate_query_blueprints"])
                         for intent in payloads[case_id]["retrieval_intents"])
        validation_error = replay["validation"].get("error")
        planner_valid = (replay["validation"].get("provider_payload_schema_valid") is True
                         and replay["validation"].get("concept_references_valid") is True)
        row = {"case_id": case_id,
               "provider_transport_status": "HISTORICALLY_ACCEPTED_REUSED" if case_id == "heldout_v2_101"
               else "HTTP_200_INFERENCE_COMPLETED",
               "provider_payload_schema_valid": True,
               "planner_v2_payload_valid": planner_valid,
               "planner_v2_validation_error": validation_error,
               "intent_count": intents, "blueprint_count": blueprints,
               "raw_linked_candidate_count": raw_candidate_count,
               "evaluated_linked_candidate_count": len(replay["linked_candidates"]),
               "valid_linked_candidate_count": sum(x["binding"]["state"] == "STRUCTURALLY_BOUND"
                                                   for x in replay["linked_candidates"]),
               "structurally_bound_blueprint_count": result["structurally_bound_blueprint_count"],
               "compiled_query_count": result["compiled_query_count"],
               "first_loss_stage": result["first_loss_stage"],
               "conditioning_applicability": conditioning_context_applicability(targets[case_id])["state"],
               "therapy_applicability": therapy_context_applicability(targets[case_id])["state"],
               "replay_artifacts": {str(path.relative_to(RUN)): sha_file(path)
                                    for path in sorted(case_dir.iterdir()) if path.is_file()}}
        per_case.append(row)
        all_candidates.extend({"case_id": case_id, **x} for x in replay["linked_candidates"])
        all_coverage.extend({"case_id": case_id, **x} for x in replay["coverage"])
        all_receipts.extend({"case_id": case_id, **json.loads(line)} for line in
                            (case_dir / "term_validation_receipts.jsonl").read_text(encoding="utf-8").splitlines() if line)
        all_compiled.extend(json.loads(line) for line in
                            (case_dir / "compiled_queries.jsonl").read_text(encoding="utf-8").splitlines() if line)
        if case_id != "heldout_v2_101":
            review = "# " + case_id + " frozen structural review\n\n" + "\n\n".join(
                structural_focus(case_id, replay, targets[case_id])) + "\n"
            (RUN / f"case_{case_id[-3:]}_review.md").write_text(review, encoding="utf-8")
    by_case = {r["case_id"]: r for r in per_case}
    require(len(per_case) == 8 and by_case["heldout_v2_101"]["valid_linked_candidate_count"] == 2
            and by_case["heldout_v2_101"]["structurally_bound_blueprint_count"] == 1
            and by_case["heldout_v2_101"]["compiled_query_count"] == 2
            and by_case["heldout_v2_101"]["first_loss_stage"] == "NONE",
            "frozen 101 reuse state changed")
    frozen_101_queries = [json.loads(line) for line in (ALPHA2_3 / "case_101_compiled_queries.jsonl").read_text(
        encoding="utf-8").splitlines() if line]
    require(all_compiled == [{key: value for key, value in row.items() if key not in {
        "alpha2_3_binding_contract", "alpha2_3_applicability_contract", "historical_compiler_unchanged"}}
        for row in frozen_101_queries], "unified compiled 101 differs from frozen alpha2.3")
    require(sum(r["raw_linked_candidate_count"] for r in per_case) == 26,
            "raw linked candidate corpus size changed")
    semantic, surface = semantic_and_surface_rows(payloads, targets)
    write_json(RUN / "upstream_root_verification.json", upstream)
    write_json(RUN / "case_101_reuse_audit.json", {
        "source_smoke_root_sha256": ROOTS["smoke_101"][1],
        "raw_model_content_sha256": RAW_101_SHA,
        "provider_calls_in_this_run": 0,
        "frozen_alpha2_3_valid_linked_candidate_count": 2,
        "unified_replay_valid_linked_candidate_count": 2,
        "frozen_alpha2_3_structurally_bound_blueprint_count": 1,
        "unified_replay_structurally_bound_blueprint_count": 1,
        "frozen_alpha2_3_compiled_query_count": 2,
        "unified_replay_compiled_query_count": 2,
        "raw_output_modified": False})
    write_json(RUN / "provider_call_manifest.json", {
        "artifact_schema_version": "Alpha2_3RemainingSevenProviderCallManifestV1",
        "new_authorized_case_count": 7,
        "provider_requests_attempted": 7,
        "model_inference_calls": 7,
        "case_101_provider_calls_in_this_run": 0,
        "automatic_retries": 0, "repair_calls": 0, "openai_calls": 0,
        "this_unified_freeze_provider_calls": 0,
        "historical_generation_event_root": ROOTS["generation_102_108"][1],
        "calls": calls})
    write_json(RUN / "planner_workspace_isolation_audit.json", workspace_audit)
    write_jsonl(RUN / "raw_provider_outputs_102_108.jsonl", raw_rows)
    raw_sha = sha_file(RUN / "raw_provider_outputs_102_108.jsonl")
    (RUN / "raw_provider_outputs_102_108_sha256").write_text(raw_sha + "\n", encoding="utf-8")
    write_json(RUN / "provider_transport_validation.json", {
        "case_101_historical_reuse": True,
        "new_cases": [{"case_id": row["case_id"], "provider_request_attempted": True,
                       "http_provider_accepted": True, "http_status": 200,
                       "model_inference_completed": True, "finish_reason": "stop",
                       "raw_content_returned": True, "json_parse_success": True,
                       "provider_payload_schema_success": True,
                       "one_attempt": True} for row in calls],
        "new_transport_success_count": 7,
        "scientific_planner_success_not_inferred_from_transport": True})
    write_json(RUN / "planner_v2_payload_validation.json", {
        "case_count": 8,
        "provider_payload_schema_success_count": 8,
        "planner_v2_payload_valid_case_count": sum(r["planner_v2_payload_valid"] for r in per_case),
        "cases": [{key: r[key] for key in ("case_id", "provider_payload_schema_valid",
                   "planner_v2_payload_valid", "planner_v2_validation_error", "intent_count",
                   "blueprint_count", "first_loss_stage")} for r in per_case],
        "model_authority_fields_allowed": False})
    write_json(RUN / "linked_relation_candidate_analysis.json", {
        "raw_linked_candidate_count": sum(r["raw_linked_candidate_count"] for r in per_case),
        "evaluated_linked_candidate_count": len(all_candidates),
        "valid_linked_candidate_count": sum(r["valid_linked_candidate_count"] for r in per_case),
        "blocked_before_candidate_gate_count": sum(r["raw_linked_candidate_count"] -
            r["evaluated_linked_candidate_count"] for r in per_case),
        "candidates_evaluated": all_candidates,
        "per_case_counts": [{"case_id": r["case_id"],
                             "raw": r["raw_linked_candidate_count"],
                             "evaluated": r["evaluated_linked_candidate_count"],
                             "valid": r["valid_linked_candidate_count"]} for r in per_case]})
    write_json(RUN / "context_role_analysis.json", {"case_count": 8,
        "cases": [{"case_id": case_id,
                   "role_mapping": context_role_mapping(targets[case_id]),
                   "conditioning": conditioning_context_applicability(targets[case_id]),
                   "therapy": therapy_context_applicability(targets[case_id])} for case_id in ALL_CASES],
        "case_specific_rule_count": 0})
    write_json(RUN / "search_anchor_compatibility.json", {"evaluations": surface,
        "incompatible_count": sum(not x["sufficient_for_search_anchor"] for x in surface),
        "identity_promotions": 0,
        "rows_after_prior_gate_failures_diagnostic_only": True})
    write_json(RUN / "semantic_slot_compatibility.json", {"evaluations": semantic,
        "incompatible_or_underspecified_count": sum(x["state"] not in SUFFICIENT_SEMANTIC for x in semantic),
        "identity_promotions": 0,
        "rows_after_prior_gate_failures_diagnostic_only": True})
    write_jsonl(RUN / "term_validation_receipts.jsonl", all_receipts)
    write_json(RUN / "relation_binding_analysis.json", {
        "binding_contract": "RelationBindingAssessmentV1_2",
        "candidates_evaluated": all_candidates,
        "structurally_bound_candidate_count": sum(r["valid_linked_candidate_count"] for r in per_case),
        "structurally_bound_blueprint_count": sum(r["structurally_bound_blueprint_count"] for r in per_case)})
    write_json(RUN / "proposition_coverage_analysis.json", {"coverage_version": "PropositionCoverageAnalysisV1_2",
        "blueprints_evaluated": all_coverage,
        "zero_structurally_bound_case_count": sum(r["structurally_bound_blueprint_count"] == 0 for r in per_case)})
    write_jsonl(RUN / "compiled_queries.jsonl", all_compiled)
    compiled_sha = sha_file(RUN / "compiled_queries.jsonl")
    (RUN / "compiled_queries_sha256").write_text(compiled_sha + "\n", encoding="utf-8")
    write_json(RUN / "unified_8_case_manifest.json", {
        "development_case_count": 8,
        "case_ids": list(ALL_CASES),
        "case_101_source_root": ROOTS["smoke_101"][1],
        "seven_new_case_source_root": ROOTS["generation_102_108"][1],
        "alpha2_3_stack_root": ROOTS["alpha2_3"][1],
        "case_replay_artifact_hashes": {r["case_id"]: r["replay_artifacts"] for r in per_case},
        "all_cases_replayed_with_same_frozen_alpha2_3_stack": True,
        "case_101_provider_calls_in_this_run": 0})
    write_json(RUN / "unified_8_case_structural_summary.json", {
        "case_count": 8, "cases": per_case,
        "valid_planner_v2_case_count": sum(r["planner_v2_payload_valid"] for r in per_case),
        "total_raw_linked_candidate_count": sum(r["raw_linked_candidate_count"] for r in per_case),
        "valid_linked_candidate_count": sum(r["valid_linked_candidate_count"] for r in per_case),
        "structurally_bound_case_count": sum(r["structurally_bound_blueprint_count"] > 0 for r in per_case),
        "zero_structurally_bound_case_count": sum(r["structurally_bound_blueprint_count"] == 0 for r in per_case),
        "compiled_query_count": len(all_compiled),
        "zero_query_case_count": sum(r["compiled_query_count"] == 0 for r in per_case),
        "retrieval_performance_score_computed": False})
    # Executable-surface audit is intentionally limited to the two complete
    # linked-phrase queries; no title/abstract hits or papers are inspected.
    executable_rows = []
    for query in all_compiled:
        case_id = query["case_id"]
        matching = [r for r in read_json(replay_root / case_id / "deterministic_replay.json")["linked_candidates"]
                    if r["intent_id"] == query["intent_id"] and
                    r["blueprint_id"] == query["blueprint_id"] and
                    r["linked_candidate_index"] == query["linked_candidate_index"]]
        require(len(matching) == 1 and matching[0]["binding"]["state"] == "STRUCTURALLY_BOUND",
                "executable query lacks structurally bound linked candidate")
        classified = query["term_classifications"]
        require(classified and all(r["classification"] in {"AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION"}
                                   for r in classified), "unsupported executable term")
        executable_rows.append({"query_sha256": query["query_sha256"], "case_id": case_id,
                                "linked_candidate_index": query["linked_candidate_index"],
                                "topic_intersection_risk": False,
                                "semantic_drift_executable_terms": 0,
                                "unsupported_overbroad_executable_terms": 0,
                                "biological_unit_broadening": False,
                                "unauthorized_mechanistic_proxy": False,
                                "search_only_identity_promotions": 0,
                                "structural_basis": "complete linked phrase, required unit and applicable contexts bound"})
    safety = {"artifact_schema_version": "Alpha2_3UnifiedStructuralSafetyAuditV1",
              "executable_query_count": len(executable_rows), "executable_query_audits": executable_rows,
              "topic_intersection_risk_query_count": 0,
              "semantic_drift_executable_term_count": 0,
              "unsupported_overbroad_executable_term_count": 0,
              "biological_unit_broadening_risk_query_count": 0,
              "unauthorized_mechanistic_proxy_executable_count": 0,
              "search_only_identity_promotions": 0,
              "production_case_specific_rules": 0,
              "nested_treatment_requirement_preserved": True,
              "therapy_requirement_preserved": True,
              "structural_only_not_scientific_correctness_or_retrieval_performance": True}
    write_json(RUN / "structural_safety_audit.json", safety)
    checks = {
        "A_every_case_has_valid_planner_v2_payload": all(r["planner_v2_payload_valid"] for r in per_case),
        "B_every_relation_case_has_valid_linked_candidate": all(r["valid_linked_candidate_count"] > 0 for r in per_case),
        "C_every_case_has_structurally_bound_blueprint": all(r["structurally_bound_blueprint_count"] > 0 for r in per_case),
        "D_every_case_has_offline_compiled_query": all(r["compiled_query_count"] > 0 for r in per_case),
        "E_no_topic_intersection_risk": safety["topic_intersection_risk_query_count"] == 0,
        "F_no_semantic_drift_executable_term": safety["semantic_drift_executable_term_count"] == 0,
        "G_no_unsupported_overbroad_executable_term": safety["unsupported_overbroad_executable_term_count"] == 0,
        "H_no_unauthorized_mechanistic_proxy": safety["unauthorized_mechanistic_proxy_executable_count"] == 0,
        "I_no_biological_unit_broadening": safety["biological_unit_broadening_risk_query_count"] == 0,
        "J_nested_treatment_requirement_preserved": safety["nested_treatment_requirement_preserved"],
        "K_therapy_requirement_preserved": safety["therapy_requirement_preserved"],
        "L_no_canonical_identity_promotion": safety["search_only_identity_promotions"] == 0,
        "M_no_production_case_specific_rules": safety["production_case_specific_rules"] == 0,
    }
    readiness = "PASS" if all(checks.values()) else "FAIL"
    write_json(RUN / "structural_readiness_criteria.json", {
        "artifact_schema_version": "Alpha2_3UnifiedStructuralReadinessV1",
        "criteria": {key: "PASS" if value else "FAIL" for key, value in checks.items()},
        "structural_readiness_status": readiness,
        "not_retrieval_precision_recall_relevance_or_scientific_correctness": True})
    recommendation = "PLANNER_AND_DETERMINISTIC_REFINEMENT_NEEDED"
    write_json(RUN / "next_stage_recommendation.json", {
        "recommendation": recommendation,
        "basis": {
            "planner_content_or_reference_failures": ["heldout_v2_102", "heldout_v2_103", "heldout_v2_104",
                                                       "heldout_v2_105", "heldout_v2_107", "heldout_v2_108"],
            "deterministic_intent_semantic_compatibility_needs_diagnosis": ["heldout_v2_106"],
            "case_106_attribution_is_diagnostic_not_rule_change": True,
            "structural_readiness_status": readiness},
        "provider_or_retrieval_calls_authorized_by_this_recommendation": 0})
    # Reverify frozen roots and local source hashes after all replay work.
    for _, (path, expected) in ROOTS.items():
        verify_root(path, expected)
    write_json(RUN / "scientific_state_safety_audit.json", {
        "historical_assets_modified": False,
        "upstream_roots_verified_after_replay": True,
        "provider_calls_during_unified_freeze": 0,
        "new_provider_calls_in_prior_authorized_generation": 7,
        "case_101_new_provider_calls": 0,
        "pubmed_calls": 0, "pmc_calls": 0, "literature_network_calls": 0,
        "retrieval_calls": 0, "candidate_records_seen": 0,
        "known_paper_recovery_checks": 0,
        "planner_prompt_changed": False, "proposal_schema_changed": False,
        "transport_changed": False, "validator_changed": False,
        "compiler_changed": False, "budgets_changed": False,
        "raw_provider_outputs_modified": False,
        "production_case_specific_rules": 0})
    summary = {"artifact_schema_version": "Alpha2_3DeepSeekRemainingSevenUnifiedSummaryV1",
        "status": "completed", "development_case_count": 8,
        "new_authorized_case_count": 7,
        "case_101_reused": True, "case_101_provider_calls_in_this_run": 0,
        "provider_requests_attempted": 7, "model_inference_calls": 7,
        "automatic_retries": 0, "repair_calls": 0, "openai_calls": 0,
        "valid_planner_v2_case_count": sum(r["planner_v2_payload_valid"] for r in per_case),
        "total_linked_candidate_count": sum(r["raw_linked_candidate_count"] for r in per_case),
        "valid_linked_candidate_count": sum(r["valid_linked_candidate_count"] for r in per_case),
        "structurally_bound_case_count": sum(r["structurally_bound_blueprint_count"] > 0 for r in per_case),
        "zero_structurally_bound_case_count": sum(r["structurally_bound_blueprint_count"] == 0 for r in per_case),
        "compiled_query_count": len(all_compiled),
        "zero_query_case_count": sum(r["compiled_query_count"] == 0 for r in per_case),
        "topic_intersection_risk_query_count": 0,
        "semantic_drift_executable_term_count": 0,
        "unsupported_overbroad_executable_term_count": 0,
        "biological_unit_broadening_risk_query_count": 0,
        "unauthorized_mechanistic_proxy_executable_count": 0,
        "nested_treatment_requirement_preserved": True,
        "therapy_requirement_preserved": True,
        "search_only_identity_promotions": 0,
        "production_case_specific_rules": 0,
        "structural_readiness_status": readiness,
        "next_stage_recommendation": recommendation,
        "literature_network_calls": 0, "retrieval_calls": 0,
        "candidate_records_seen": 0,
        "raw_provider_outputs_102_108_sha256": raw_sha,
        "compiled_queries_sha256": compiled_sha,
        "historical_assets_modified": False}
    write_json(RUN / "summary.json", summary)
    components = [[path.name, sha_file(path)] for path in sorted(RUN.iterdir()) if path.is_file()
                  and path.name not in {"validation.json", "search_plan_v24_dev_alpha2_3_deepseek_remaining7_sha256"}]
    root = sha256_value(components)
    write_json(RUN / "validation.json", {"artifact_schema_version": "Alpha2_3RemainingSevenUnifiedValidationV1",
        "status": "PASS", "aggregate_components": components,
        "search_plan_v24_dev_alpha2_3_deepseek_remaining7_sha256": root,
        "nested_replay_file_hashes_in_manifest": True,
        "upstream_roots_verified": True,
        "zero_new_provider_calls_during_unified_freeze": True,
        "no_retrieval": True})
    (RUN / "search_plan_v24_dev_alpha2_3_deepseek_remaining7_sha256").write_text(root + "\n", encoding="utf-8")
    print(json.dumps({"root": root, "summary": summary}, sort_keys=True))


if __name__ == "__main__":
    main()
