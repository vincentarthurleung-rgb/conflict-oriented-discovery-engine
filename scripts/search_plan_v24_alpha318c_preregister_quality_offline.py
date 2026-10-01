#!/usr/bin/env python3
"""Offline, fail-closed alpha3.18C Quality execution preregistration.

Historical B2 requests are verified, never rewritten. Only the provider-facing
model field is prospectively projected; the three scientific message payloads
remain byte-identical to their frozen B2 request values.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from scripts import search_plan_v24_alpha317d_preregister_quality_v2_offline as quality
from scripts import search_plan_v24_alpha318b_post_builder_prechecks as prechecks
from scripts import search_plan_v24_alpha318b_preregister_builder_execution_offline as prior


ROOT = Path(__file__).resolve().parents[1]
B2 = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18b2_builder_v3_execution"
A6 = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18a6_license_extraction_v2_offline_replay"
Q2 = quality.RUN
OUT = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18c_quality_execution_preregistration_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_18c_prereg_sha256"
B2_SHA = "0eea9667281b2548f1169e63e3983c4422a8036777b6604ab4918ef27533441e"
REQUEST_SHA = "728bea660a47be20ec0590a468c7b6d2700987de30a9f0a1527202cde93eebea"
QUALITY_SHA = "89009283963c1db3dd00d57917d932b4d0a542dcb27863ad071dc30f8c0cd751"
GROUNDING_SHA = "25d52f9ef10f3226e6003bcca46aa5d6a664b2b47bf7052db255a19da124e497"
SCHEMA_SHA = "092961a96fe2985633054b68760cd409780e7e44fbfb2c5cd14c12ed9a51e326"
MODEL = "deepseek-flash"
OLD_MODEL = "deepseek-v4-pro"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    values = []
    for line in raw.splitlines(keepends=True):
        if not line.endswith(b"\n"):
            raise RuntimeError("QUALITY_REQUEST_FREEZE_MISMATCH:truncated JSONL")
        obj = json.loads(line)
        if canonical(obj) + b"\n" != line:
            raise RuntimeError("QUALITY_REQUEST_FREEZE_MISMATCH:noncanonical JSONL")
        values.append(obj)
    return values


def root(directory: Path, marker: str) -> str:
    # Match the established frozen-root convention: top-level files only.
    return sha(canonical([[path.name, digest(path)]
        for path in sorted(directory.iterdir()) if path.is_file() and path.name != marker]))


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RuntimeError(code)


def ref(path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}


def write(name: str, value: Any) -> str:
    path = OUT / name
    if path.exists():
        raise RuntimeError("REFUSE_OVERWRITE:" + name)
    path.write_bytes(canonical(value) + b"\n")
    return digest(path)


def marker(name: str, value: str) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError("REFUSE_OVERWRITE:" + name)
    path.write_text(value + "\n", encoding="ascii")


def verify_upstream() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    require(root(B2, "search_plan_v24_dev_alpha3_18b2_sha256") == B2_SHA and
        (B2 / "search_plan_v24_dev_alpha3_18b2_sha256").read_text().strip() == B2_SHA,
        "ALPHA3_18B2_ROOT_MISMATCH")
    path = B2 / "proposition_quality_v2_request_manifest_v3.jsonl"
    require(digest(path) == REQUEST_SHA and
        (B2 / "proposition_quality_v2_request_manifest_v3_sha256").read_text().strip() == REQUEST_SHA,
        "QUALITY_REQUEST_FREEZE_MISMATCH")
    qroot = sha(canonical([[name, digest(Q2 / name)] for name in sorted(prior.QUALITY_PROTOCOL_FILES)]))
    require(qroot == QUALITY_SHA and
        (Q2 / "proposition_quality_adjudication_v2_protocol_sha256").read_text().strip() == QUALITY_SHA,
        "QUALITY_SCIENTIFIC_PROTOCOL_DRIFT")
    # The B2 run's preflight already binds these frozen Builder V3 roots; verify
    # them again from the B2 preflight record and their actual named artifacts.
    preflight = load(B2 / "builder_v3_execution_preflight.json")
    b1 = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18b1_grounding_contract_consistency_audit_offline"
    require(root(b1, "search_plan_v24_dev_alpha3_18b1_sha256") ==
        preflight["b1_root_sha256"] and
        digest(b1 / "builder_grounding_contract_v3.json") == GROUNDING_SHA and
        digest(b1 / "builder_output_schema_v3.json") == SCHEMA_SHA and
        (b1 / "builder_grounding_contract_v3_sha256").read_text().strip() == GROUNDING_SHA and
        (b1 / "builder_output_schema_v3_sha256").read_text().strip() == SCHEMA_SHA,
        "BUILDER_V3_CONTRACT_MISMATCH")
    require(preflight["v3_grounding_contract_sha256"] == GROUNDING_SHA and
        preflight["v3_schema_sha256"] == SCHEMA_SHA,
        "BUILDER_V3_CONTRACT_MISMATCH")
    candidates = rows(B2 / "builder_v3_prechecked_candidate_manifest.jsonl")
    groups = rows(B2 / "quality_v3_source_group_manifest.jsonl")
    requests = rows(path)
    require((len(candidates), len(groups), len(requests)) == (5, 3, 3),
        "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
    require(len({c["candidate_id"] for c in candidates}) == 5 and
        len({g["source_group_id"] for g in groups}) == 3,
        "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
    return candidates, groups, requests


def packets_from_frozen_request(request: dict[str, Any]) -> list[dict[str, Any]]:
    messages = request["messages"]
    require(len(messages) == 2 and messages[0]["role"] == "system" and
        messages[1]["role"] == "user", "QUALITY_REQUEST_FREEZE_MISMATCH")
    user = messages[1]["content"]
    prefix = "Candidate packets JSON (each candidate has its own evidence span and bounded context):\n"
    require(user.count(prefix) == 1 and user.count("\nOutput JSON schema:\n") == 1,
        "QUALITY_REQUEST_FREEZE_MISMATCH")
    data = user.split(prefix, 1)[1].split("\nOutput JSON schema:\n", 1)[0]
    packets = json.loads(data)
    require(canonical(packets).decode("utf-8") == data, "QUALITY_REQUEST_FREEZE_MISMATCH")
    return packets


def audit_active_names() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Classify every remaining repository occurrence; never edit frozen files."""
    historical: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    result = subprocess.run(["rg", "-l", "-0", "--hidden", "--no-ignore",
        "-g", "!.git/**", "-g", "!**/__pycache__/**", "-g", "!.venv/**",
        "-g", "!node_modules/**", "-g", "!runs/20261001_search_plan_v24_dev_alpha3_18c_quality_execution_preregistration_offline/**",
        OLD_MODEL, "."], cwd=ROOT, capture_output=True, check=False)
    require(result.returncode in (0, 1), "DEEPSEEK_ACTIVE_MODEL_AUDIT_FAILED")
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8").removeprefix("./")
        path = ROOT / rel
        require(path.is_file() and not path.is_symlink(), "DEEPSEEK_ACTIVE_MODEL_AUDIT_FAILED")
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeError, OSError):
            raise RuntimeError("DEEPSEEK_ACTIVE_MODEL_AUDIT_UNREADABLE:" + rel)
        historical_dir = rel.split("/", 1)[0] in {
            "runs", "data", "archived_experiments", "audit_reports", "batch_runs",
            "case_bundles", "preserved_case_bundles", "readiness_reports", "reports",
            "system_b_inputs"}
        historical_code = (
            rel.startswith("configs/generated_cases/") and path.name in
                {"search_plan.frozen.json", "readiness_report.json"} or
            rel.startswith("configs/search_plans/") and path.name.endswith(".frozen.json") or
            rel.startswith("scripts/") and re.search(r"alpha3|search_plan_v24", path.name) is not None or
            rel.startswith("tools/") and ("search_plan_v24" in path.name or
                path.name.startswith("run_single_source_provider_extraction_smoke_")) or
            rel.startswith("src/code_engine/search/") and path.name in
                {"deepseek_planner_transport_v1.py", "deepseek_planner_transport_v1_1.py",
                 "planner_v3_contract.py"} or
            rel.startswith("src/code_engine/fulltext/") and path.name in
                {"failed_block_recovery.py", "fulltext_l1_v2_smoke.py", "fulltext_l1_v3_smoke.py"} or
            rel.startswith("tests/") and (path.name.startswith("test_alpha2") or
                path.name.startswith("test_search_plan_v24_") or
                path.name in {"test_fulltext_l1_v2_provider_smoke.py",
                    "test_context_attribution_provider_execution_identity.py",
                    "test_evidence_grounded_context_attribution.py"} or
                rel.startswith("tests/fixtures/"))
        )
        is_history = historical_dir or historical_code
        line_refs = [[number, line.count(OLD_MODEL)] for number, line in enumerate(lines, 1)
            if OLD_MODEL in line]
        record = {"path": rel, "lines_and_occurrences": line_refs,
            "occurrence_count": sum(count for _, count in line_refs),
            "classification": "HISTORICAL_PROVENANCE_ALLOWED" if is_history else
                              "STALE_ACTIVE_REFERENCE_ERROR",
            "reason": "frozen_run_report_cache_or_versioned_protocol_test_vector" if is_history else
                      "prospective_or_unclassified_reference"}
        (historical if is_history else stale).append(record)
    historical.sort(key=lambda item: item["path"])
    stale.sort(key=lambda item: item["path"])
    return historical, stale


def main() -> None:
    require(not OUT.exists(), "ALPHA3_18C_PREREG_ALREADY_EXISTS")
    candidates, groups, requests = verify_upstream()
    group_by_id = {row["source_group_id"]: row for row in groups}
    candidate_by_id = {row["candidate_id"]: row for row in candidates}
    source_rows = rows(A6 / "construction_source_manifest_v4.jsonl")
    source_by_token = {row["source_token"]: row for row in source_rows}
    historical, stale = audit_active_names()
    require(not stale, "DEEPSEEK_ACTIVE_MODEL_MIGRATION_INCOMPLETE")
    # No frozen request is changed. Projection is performed only for the future
    # outbound provider serialization; its altered request hash is committed here.
    membership = []
    projected = []
    evidence_checks = []
    order = []
    for index, row in enumerate(requests, 1):
        gid = row["source_group_id"]
        require(gid in group_by_id, "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
        group = group_by_id[gid]
        ids = row["candidate_ids"]
        require(row["ordinal"] == group["ordinal"] and
            set(ids) == set(group["candidate_ids"]) and len(ids) == group["candidate_count"] and
            len(set(ids)) == len(ids), "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
        frozen = row["request"]
        require(sha(canonical(frozen)) == row["request_sha256"] and
            frozen["model"] == OLD_MODEL and frozen["thinking"] == {"type": "enabled"} and
            frozen["reasoning_effort"] == "high" and
            frozen["response_format"] == {"type": "json_object"} and
            frozen["stream"] is False and set(frozen) ==
            {"model", "thinking", "reasoning_effort", "response_format", "stream", "messages"},
            "QUALITY_REQUEST_FREEZE_MISMATCH")
        packets = packets_from_frozen_request(frozen)
        require({p["candidate_id"] for p in packets} == set(ids) and len(packets) == len(ids),
            "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
        source = source_by_token[group["private_source_token"]]
        document_path = A6 / source["document_path"]
        require(digest(document_path) == source["document_sha256"],
            "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
        document = load(document_path)
        require(quality.source_group_id(group["private_source_token"]) == gid,
            "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
        packet_hashes = []
        context_hashes = []
        for packet in packets:
            candidate_id = packet["candidate_id"]
            require(candidate_id in candidate_by_id, "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
            item = candidate_by_id[candidate_id]
            c = item["candidate"]
            require(item["source_token"] == group["private_source_token"] and
                item["ordinal"] == row["ordinal"] and
                packet["neutral_proposition"] == c["neutral_proposition"] and
                packet["scientific_fields"] == {key: c[key] for key in prechecks.SCIENTIFIC_FIELDS},
                "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
            span = c["construction_evidence_span"]
            require(span["source_field"] == "body", "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
            expected_evidence = quality.evidence_packet(document["body_text"],
                span["start_offset"], span["end_offset"], span["exact_text"])
            require(packet["evidence"] == expected_evidence,
                "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
            packet_hashes.append({"candidate_id": candidate_id,
                "packet_sha256": sha(canonical(packet)),
                "evidence_sha256": sha(canonical(packet["evidence"]))})
            context_hashes.append({"candidate_id": candidate_id,
                "bounded_context_sha256": sha(packet["evidence"]["bounded_local_context"].encode("utf-8"))})
        membership.append({"order_index": index, "source_group_id": gid,
            "candidate_ids_sorted": sorted(ids), "candidate_count": len(ids),
            "frozen_request_sha256": row["request_sha256"],
            "evidence_packets": sorted(packet_hashes, key=lambda x: x["candidate_id"]),
            "bounded_contexts": sorted(context_hashes, key=lambda x: x["candidate_id"])})
        evidence_checks.append({"source_group_id": gid,
            "source_document_sha256": source["document_sha256"],
            "candidate_specific_body_spans_reverified": len(ids),
            "evidence_packet_hashes": sorted(packet_hashes, key=lambda x: x["candidate_id"]),
            "bounded_context_hashes": sorted(context_hashes, key=lambda x: x["candidate_id"])})
        new = copy.deepcopy(frozen)
        new["model"] = MODEL
        require(new["messages"] == frozen["messages"] and
            {key: value for key, value in new.items() if key != "model"} ==
            {key: value for key, value in frozen.items() if key != "model"},
            "QUALITY_SCIENTIFIC_PROTOCOL_DRIFT")
        projected.append({"order_index": index, "source_group_id": gid,
            "frozen_request_sha256": row["request_sha256"],
            "provider_serialized_request_sha256": sha(canonical(new)),
            "messages_sha256": sha(canonical(frozen["messages"])),
            "projection_delta": {"model": MODEL}})
        order.append({"order_index": index, "source_group_id": gid,
            "frozen_source_ordinal": row["ordinal"],
            "frozen_request_sha256": row["request_sha256"],
            "provider_serialized_request_sha256": sha(canonical(new))})
    require({x["candidate_id"] for x in candidates} ==
        {cid for row in membership for cid in row["candidate_ids_sorted"]},
        "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
    provider_old = load(Q2 / "quality_provider_config.json")
    require(provider_old["provider"] == "DeepSeek" and provider_old["model"] == OLD_MODEL and
        provider_old["thinking"] == {"type": "enabled"} and
        provider_old["reasoning_effort"] == "high" and
        provider_old["temperature"] == provider_old["top_p"] == "omitted" and
        provider_old["automatic_retry"] is False,
        "QUALITY_PROVIDER_CONFIG_UNRESOLVED")
    provider_new = {**provider_old, "model": MODEL}
    # This is an offline preregistration, not a provider compatibility check.
    OUT.mkdir()
    write("root_verification.json", {"status": "PASS", "B2": B2_SHA,
        "QualityV2": QUALITY_SHA, "BuilderGroundingV3": GROUNDING_SHA,
        "BuilderSchemaV3": SCHEMA_SHA})
    write("alpha3_18b2_verification.json", {"root": ref(B2 / "search_plan_v24_dev_alpha3_18b2_sha256"),
        "actual_root_sha256": B2_SHA, "historical_builder_v2_inferences": 28,
        "builder_v3_inferences": 28, "cumulative_builder_inference_events": 56,
        "b2_summary": ref(B2 / "summary.json")})
    write("quality_request_manifest_verification.json", {"manifest": ref(B2 /
        "proposition_quality_v2_request_manifest_v3.jsonl"), "request_count": 3,
        "every_frozen_request_hash_verified": True, "every_JSONL_record_byte_canonical": True,
        "original_requests_rewritten": False, "model_projection_only_at_provider_serialization": projected})
    write("quality_candidate_membership_freeze.json", {"source": ref(B2 /
        "builder_v3_prechecked_candidate_manifest.jsonl"), "candidate_count": 5,
        "source_group_count": 3, "order_insensitive_id_set_binding": True,
        "source_groups": membership})
    write("quality_evidence_packet_verification.json", {"status": "PASS",
        "frozen_body_evidence_and_bounded_context_match_source_documents": True,
        "records": evidence_checks})
    write("quality_v2_scientific_protocol_verification.json", {"root_sha256": QUALITY_SHA,
        "criterion_contract": ref(Q2 / "quality_criteria_contract.json"),
        "schema": ref(Q2 / "proposition_quality_adjudication_v2_schema.json"),
        "system_prompt": ref(Q2 / "quality_adjudicator_system_prompt.txt"),
        "user_template": ref(Q2 / "quality_adjudicator_user_prompt_template.txt"),
        "scientific_protocol_changed": False,
        "criterion_count": len(quality.CRITERIA), "role": "proposition_quality_adjudicator"})
    binding_name = "quality_execution_provider_binding_v2_1.json"
    binding_sha = write(binding_name, {"schema_version": "QualityExecutionProviderBindingV2_1",
        "status": "PROSPECTIVE_OPERATIONAL_MODEL_IDENTIFIER_MIGRATION",
        "scientific_protocol_sha256": QUALITY_SHA,
        "frozen_B2_request_manifest_sha256": REQUEST_SHA,
        "provider_configuration": provider_new,
        "request_projection": "copy each frozen request; replace only top-level model at outbound serialization",
        "projected_requests": projected,
        "historical_model_outputs_equivalent": False,
        "remote_model_acceptance_verified": False,
        "candidate_evidence_or_criteria_changed": False})
    marker("quality_execution_provider_binding_v2_1_sha256", binding_sha)
    write("deepseek_active_model_migration_audit.json", {"prospective_deepseek_model": MODEL,
        "active_defaults": [".env", ".env.example", "src/code_engine/extraction/policy.py",
            "src/code_engine/extraction/deepseek_client.py", "src/code_engine/validation/readiness.py",
            "src/code_engine/cli/print_env_template.py", "src/code_engine/query/prompt_compatibility.py"],
        "historical_references_preserved": True, "new_active_deepseek_v4_pro_references": 0,
        "stale_active_reference_count": len(stale), "network_compatibility_checked": False})
    write("deepseek_historical_reference_allowlist.json", {"classification":
        "HISTORICAL_PROVENANCE_ALLOWED", "file_count": len(historical),
        "occurrence_count": sum(item["occurrence_count"] for item in historical),
        "occurrences": historical, "historical_artifacts_not_rewritten": True})
    write("deepseek_stale_active_reference_audit.json", {"stale_active_reference_count": len(stale),
        "occurrences": stale, "status": "PASS" if not stale else "FAIL"})
    write("quality_provider_config_verification.json", {"provider": "DeepSeek", "model": MODEL,
        "thinking": {"type": "enabled"}, "reasoning_effort": "high",
        "temperature": "omitted", "top_p": "omitted",
        "frozen_quality_v2_provider_configuration_sha256": digest(Q2 / "quality_provider_config.json"),
        "binding_sha256": binding_sha, "runtime_model_choice_unresolved": False,
        "remote_model_acceptance_verified": False})
    write("quality_execution_order_contract.json", {"order": order,
        "source": ref(B2 / "proposition_quality_v2_request_manifest_v3.jsonl"),
        "fresh_independent_context_per_source_group": True,
        "cross_group_results_visible": False, "outcome_based_reordering": False})
    ambiguity = load(Q2 / "provider_execution_ambiguity_policy.json")
    invalid = load(Q2 / "quality_invalid_response_policy.json")
    write("quality_transport_retry_contract.json", {"source": ref(Q2 /
        "provider_execution_ambiguity_policy.json"), "automatic_retry": False,
        "known_no_inference_transport_retry": ambiguity["known_no_inference_transport_retry"],
        "scientific_inference_attempts_per_group": 1,
        "no_retry_for_scientific_outcome": True, "no_model_repair": True})
    write("quality_provider_ambiguity_policy.json", {"source": ref(Q2 /
        "provider_execution_ambiguity_policy.json"),
        "state": "QUALITY_PROVIDER_EXECUTION_AMBIGUOUS", "stop_entire_quality_stage": True,
        "no_retry_or_remaining_groups": True,
        "schema_invalid_completed_response_policy": invalid["behavior"],
        "stricter_frozen_quality_v2_invalid_response_policy_applies": True})
    write("quality_response_identity_binding_contract.json", {"source": ref(Q2 /
        "quality_response_identity_binding_contract.json"),
        "validator_function": "quality.validate_response", "expected_candidate_id_set_from_frozen_manifest": True,
        "response_array_order_semantically_irrelevant": True,
        "canonical_order": "ascending candidate_id", "duplicate_missing_extra_unknown_fail_closed": True})
    write("quality_response_schema_contract.json", {"source": ref(Q2 /
        "proposition_quality_adjudication_v2_schema.json"),
        "machine_output": ref(Q2 / "quality_machine_output_contract.json"),
        "schema_version": quality.QUALITY_VERSION, "schema_invalid_no_reinference": True})
    write("quality_enum_domain_contract.json", {"source": ref(Q2 /
        "criterion_state_contract.json"), "criteria": quality.CRITERIA,
        "states": quality.STATES, "near_alias_normalization": False,
        "cross_field_taxonomy_substitution": False})
    write("quality_candidate_decision_contract.json", {"source": ref(Q2 /
        "overall_quality_eligibility_rule.json"),
        "QUALITY_PASS": "all ten criteria exactly PASS",
        "QUALITY_FAIL": "one or more criteria FAIL, regardless of other UNRESOLVED criteria",
        "QUALITY_UNRESOLVED": "no FAIL and one or more UNRESOLVED",
        "eligibility": "QUALITY_PASS only", "ranking_or_score": False,
        "controller_scientific_reinterpretation": False})
    write("quality_output_freeze_barrier.json", {"all_three_source_group_outputs_and_candidate_states_before_post_quality": True,
        "raw_provider_responses_preserved_before_validation": True,
        "identity_join_or_pool_processing_before_barrier": False})
    write("post_quality_processing_boundary.json", {"allowed_after_output_barrier": [
        "quality_pass_candidate_manifest", "quality_fail_candidate_manifest",
        "quality_unresolved_candidate_manifest", "per_source_quality_pass_multiplicity"],
        "fresh_heldout_sampling": False, "source_topup": False,
        "quality_to_duplicate_to_one_per_source_to_pool_order": True})
    write("pool_finalization_dependency_audit.json", {"source": ref(Q2 /
        "duplicate_selection_order_authority_audit.json"),
        "cross_source_semantic_near_duplicate_review_is_not_fully_executable_from_frozen_artifacts": True,
        "one_per_source_selector_source": ref(Q2 / "deterministic_one_per_source_selector.json"),
        "after_quality_outcome_freeze": "PREREGISTER_ALPHA3_18D_POOL_FINALIZATION",
        "final_pool_in_alpha3_18c": False})
    manifest_name = "alpha3_18c_quality_execution_manifest.json"
    manifest_sha = write(manifest_name, {"schema_version": "Alpha3_18CQualityExecutionManifestV1",
        "B2_root_sha256": B2_SHA, "frozen_quality_request_manifest_sha256": REQUEST_SHA,
        "quality_candidate_membership": ref(OUT / "quality_candidate_membership_freeze.json"),
        "quality_evidence_verification": ref(OUT / "quality_evidence_packet_verification.json"),
        "quality_v2_scientific_protocol_sha256": QUALITY_SHA,
        "quality_provider_binding": ref(OUT / binding_name),
        "provider": "DeepSeek", "model": MODEL, "reviewer_role": "proposition_quality_adjudicator",
        "execution_order": order, "planned_source_groups": 3,
        "maximum_scientific_inferences": 3, "fresh_independent_context_per_group": True,
        "transport_retry_contract": ref(OUT / "quality_transport_retry_contract.json"),
        "ambiguity_policy": ref(OUT / "quality_provider_ambiguity_policy.json"),
        "response_identity_binding": ref(OUT / "quality_response_identity_binding_contract.json"),
        "response_schema": ref(OUT / "quality_response_schema_contract.json"),
        "enum_domain": ref(OUT / "quality_enum_domain_contract.json"),
        "criterion_aggregation": ref(OUT / "quality_candidate_decision_contract.json"),
        "all_output_barrier": ref(OUT / "quality_output_freeze_barrier.json"),
        "post_quality_boundary": ref(OUT / "post_quality_processing_boundary.json"),
        "next_stage": "AUTHORIZE_EXACT_3_ALPHA3_18C_QUALITY_CALLS"})
    marker("alpha3_18c_quality_execution_manifest_sha256", manifest_sha)
    require(root(B2, "search_plan_v24_dev_alpha3_18b2_sha256") == B2_SHA and
        digest(B2 / "proposition_quality_v2_request_manifest_v3.jsonl") == REQUEST_SHA,
        "HISTORICAL_ASSET_MUTATION_DETECTED")
    write("scientific_state_safety_audit.json", {"provider_calls": 0, "llm_calls": 0,
        "network_calls": 0, "builder_reruns": 0, "quality_calls": 0,
        "candidate_or_evidence_rewrites": 0, "source_topups": 0,
        "heldout_sampling": False})
    write("historical_preservation_audit.json", {"B2_root_still_verified": True,
        "B2_quality_manifest_still_verified": True,
        "Quality_V2_protocol_still_verified": True,
        "historical_deepseek_v4_pro_references_preserved": True,
        "historical_artifacts_modified": False})
    write("validation.json", {"status": "PASS", "quality_request_count": 3,
        "quality_input_candidate_count": 5, "quality_source_group_count": 3,
        "candidate_membership_frozen": True, "quality_evidence_packets_frozen": True,
        "quality_scientific_protocol_changed": False,
        "quality_provider_binding_prospectively_amended": True,
        "stale_active_reference_count": 0, "provider_calls": 0, "llm_calls": 0,
        "network_calls": 0})
    write("summary.json", {"status": "completed", "quality_request_count": 3,
        "quality_input_candidate_count": 5, "quality_source_group_count": 3,
        "quality_provider": "DeepSeek", "quality_model": MODEL,
        "quality_execution_provider_binding_v2_1_sha256": binding_sha,
        "alpha3_18c_quality_execution_manifest_sha256": manifest_sha,
        "next_stage_recommendation": "AUTHORIZE_EXACT_3_ALPHA3_18C_QUALITY_CALLS"})
    root_sha = root(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root_sha)
    print(json.dumps({"status": "completed", "root_sha256": root_sha,
        "quality_request_count": 3, "candidate_count": 5, "source_group_count": 3,
        "binding_sha256": binding_sha, "execution_manifest_sha256": manifest_sha}, sort_keys=True))


if __name__ == "__main__":
    main()
