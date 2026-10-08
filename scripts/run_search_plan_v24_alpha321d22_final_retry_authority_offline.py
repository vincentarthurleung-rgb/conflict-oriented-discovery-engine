#!/usr/bin/env python3
"""Final pre-D2 retry-authority archaeology, offline and append-only.

No transport client is constructed, no original XML is parsed, and no recovery
is performed. Old contracts/code/tests/logs may establish semantics; D2/D2.1
only establish the frozen incident/preservation state. Missing provenance is
never repaired by post-outcome synthetic behavior.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

from scripts import run_search_plan_v24_alpha321d21_runtime_failure_audit_offline as prior


ROOT, d2 = prior.ROOT, prior.d2
OUT = ROOT / "runs/20261007_search_plan_v24_primary_alpha3_21d22_final_retry_policy_authority_audit_offline"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21d22_sha256"
D21_SHA = "6671492806a7179cb5ba45f208469a7ed6436ffe6a5ec819dddd0102321dd271"
STAGE = "FRESH_PRIMARY_ALPHA3_21_FINAL_RETRY_POLICY_AUTHORITY_AUDIT"
CLASS_A = "BODY_READ_INTERRUPTION_ALREADY_COVERED_BY_PREEXISTING_FROZEN_TRANSPORT_RETRY_AUTHORITY"
CLASS_B = "BODY_READ_INTERRUPTION_EXCLUDED_BY_PREEXISTING_FROZEN_RETRY_AUTHORITY"
CLASS_C = "BODY_READ_INTERRUPTION_PREEXISTING_RETRY_AUTHORITY_REMAINS_UNRESOLVED"
CLASS_INTEGRITY = "FINAL_RETRY_AUTHORITY_AUDIT_BLOCKED_BY_INTEGRITY_FAILURE"
NEXT_C = "CLOSE_ALPHA3_21_PRIMARY_INCOMPLETE_AT_D2_RUNTIME_AUTHORITY_GAP"
NEXT_B = "CLOSE_ALPHA3_21_PRIMARY_INCOMPLETE_AT_D2_RUNTIME_FAILURE"
NEXT_INTEGRITY = "CLOSE_ALPHA3_21_PRIMARY_INCOMPLETE_DUE_TO_D2_ARTIFACT_AUTHORITY_FAILURE"
NO_CALLS = dict(prior.NO_CALLS)
canonical, sha, digest, obj, rows, ref, root_hash, require = (
    prior.canonical, prior.sha, prior.digest, prior.obj, prior.rows, prior.ref, prior.root_hash, prior.require)
REQUIRED = (
    "alpha3_21d21_root_verification", "alpha3_21d2_root_verification", "alpha3_21d1_root_verification",
    "alpha3_21d_root_verification", "pre_d2_authority_evidence_cutoff", "retry_authority_evidence_tier_contract",
    "frozen_retry_artifact_inventory", "frozen_retry_contract_exact_text_evidence",
    "retry_closed_vs_semantic_class_audit", "pre_d2_retry_test_inventory",
    "pre_d2_historical_transport_failure_inventory", "historical_body_read_interruption_equivalence_audit",
    "bound_transport_control_flow_audit", "pre_d2_git_history_retry_semantics_audit",
    "actual_exception_identity_limitation", "positive_retry_authority_test", "positive_retry_exclusion_test",
    "final_body_read_retry_authority_classification", "d2_continuation_eligibility", "d2_attempt_budget_audit",
    "oa_immutability_audit", "successful_jats_immutability_audit", "activation_manifest_immutability_audit",
    "partial_response_quarantine_audit", "partial_handoff_nonfinal_audit",
    "fresh_attempt_exposure_preservation_audit", "same_attempt_finality_rule",
    "known_preexisting_test_environment_issue", "scientific_policy_nonadaptation_audit",
    "historical_preservation_audit", "scientific_state_safety_audit", "validation", "summary",
)
A_ONLY = ("pmc_jats_retry_runtime_overlay_v2.json", "pmc_jats_retry_runtime_overlay_v2_sha256",
          "alpha3_21d2r_preregistration_handoff.json")
INCLUSION_KINDS = {
    "EXPLICIT_FROZEN_BODY_READ_RETRY_TEXT", "BOUND_FULL_BODY_COMPLETION_RETRY_STATE",
    "PRE_D2_EQUIVALENT_MID_BODY_RETRY_TEST", "PRE_D2_EQUIVALENT_HISTORICAL_BODY_RETRY",
    "COMPARABLY_EXPLICIT_PREEXISTING_BODY_RETRY_AUTHORITY",
}


def classify_evidence(evidence):
    """Offline proof evaluator. This is NOT a runtime retry predicate."""
    decisions = []
    for item in evidence:
        require(item["tier"] in range(1, 6), "INVALID_EVIDENCE_TIER")
        eligible = (item["pre_d2_proven"] is True and item["same_PMC_JATS_authority"] is True
                    and item.get("forbidden_authority", False) is False)
        kind = item["kind"]
        positive = eligible and kind in INCLUSION_KINDS and item.get("positive_proof", False) is True
        if kind in {"PRE_D2_EQUIVALENT_MID_BODY_RETRY_TEST", "PRE_D2_EQUIVALENT_HISTORICAL_BODY_RETRY"}:
            positive = positive and item.get("equivalent_mid_body_mechanics", False) is True
        if kind == "BOUND_FULL_BODY_COMPLETION_RETRY_STATE":
            positive = positive and item.get("broader_frozen_semantic_contract_bound", False) is True
        negative = (eligible and kind == "EXPLICIT_CLOSED_BODY_INTERRUPTION_EXCLUSION"
                    and item.get("closed_domain_positive_proof", False) is True
                    and item.get("body_interruption_exclusion_positive_proof", False) is True)
        decisions.append({"evidence_id": item["evidence_id"], "tier": item["tier"], "eligible": eligible,
                          "positive_inclusion": positive, "positive_exclusion": negative, "kind": kind})
    includes = [d for d in decisions if d["positive_inclusion"]]
    excludes = [d for d in decisions if d["positive_exclusion"]]
    conflict = False
    if includes and excludes:
        include_tier = min(d["tier"] for d in includes)
        exclude_tier = min(d["tier"] for d in excludes)
        conflict = include_tier == exclude_tier
        if include_tier < exclude_tier:
            excludes = []
        elif exclude_tier < include_tier:
            includes = []
    classification = CLASS_C if conflict or not includes and not excludes else CLASS_A if includes else CLASS_B
    return {
        "classification": classification, "primary_classification_count": 1, "decisions": decisions,
        "positive_retry_authority_established": bool(includes) and not conflict,
        "positive_retry_exclusion_established": bool(excludes) and not conflict,
        "body_read_interruption_covered_by_preexisting_retry_authority":
            True if classification == CLASS_A else False if classification == CLASS_B else None,
        "same_tier_positive_evidence_conflict": conflict,
        "runtime_recovery_within_same_primary_attempt_allowed": classification == CLASS_A,
        "runtime_behavior_label": "IMPLEMENTATION_COVERAGE_DEFECT" if classification == CLASS_A else
            "RUNTIME_FAILURE_WITH_UNRESOLVED_RETRY_AUTHORITY" if classification == CLASS_C else
            "RUNTIME_FAILURE_OUTSIDE_FROZEN_RETRY_AUTHORITY",
    }


def git_read(args):
    require(args[0] in {"log", "show", "blame", "rev-parse"}, "MUTATING_GIT_COMMAND_FORBIDDEN")
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)
    require(result.returncode == 0, "READ_ONLY_GIT_EVIDENCE_FAILURE:" + result.stderr.decode())
    return result.stdout


def git_temporal_proof(path, cutoff):
    relative = str(path.relative_to(ROOT))
    arguments = ["log", "--follow", "--format=%H|%aI|%cI", "--", relative]
    log = git_read(arguments).decode()
    snapshots = []
    for line in log.splitlines():
        commit, author_date, committer_date = line.split("|")
        predates = datetime.fromisoformat(author_date) < cutoff and datetime.fromisoformat(committer_date) < cutoff
        raw = git_read(["show", commit + ":" + relative])
        snapshots.append({"commit": commit, "author_date": author_date, "committer_date": committer_date,
                          "predates_cutoff": predates, "git_file_sha256": sha(raw),
                          "matches_current_frozen_bytes": sha(raw) == digest(path)})
    return {"file": ref(path, "read_only_git_snapshot_comparison"), "log_command": ["git", *arguments],
            "exact_log_text": log, "snapshots": snapshots,
            "current_bytes_proven_pre_D2_by_git": any(r["predates_cutoff"] and r["matches_current_frozen_bytes"] for r in snapshots),
            "untracked_files_not_claimed_git_proven": not bool(snapshots)}


def exact_document(path, tier, role, temporal_basis, same_authority=True):
    raw = path.read_bytes()
    return {"document": ref(path, role), "tier": tier, "exact_UTF8_text": raw.decode(),
            "exact_text_bytes_sha256": sha(raw), "temporal_basis": temporal_basis,
            "same_PMC_JATS_authority": same_authority,
            "not_paraphrased_before_preservation": True}


def historical_logs(cutoff):
    candidates = sorted(p for pattern in ("*/ncbi_transport_attempts*.jsonl", "*/pmc_request_attempts.jsonl")
                        for p in (ROOT / "runs").glob(pattern)
                        if re.search(r"alpha3_(18|19|20)(?:[a-z_])", p.parent.name))
    inventories, failures = [], []
    total_pmc, total_jats = 0, 0
    for path in candidates:
        records = rows(path)
        require(all(datetime.fromisoformat(r["timestamp_utc"]) < cutoff for r in records),
                "HISTORICAL_LOG_CROSSES_PRE_D2_CUTOFF")
        markers = list(path.parent.glob("search_plan*_sha256"))
        require(len(markers) == 1, "HISTORICAL_ROOT_MARKER_AMBIGUOUS")
        marker = markers[0]
        prior.root_check(path.parent, marker.name, marker.read_text().strip())
        pmc = [r for r in records if r.get("stage", "").startswith("PMC_")]
        require(not any(r.get("parameters", {}).get("db") == "pmc" and r not in pmc for r in records),
                "UNCLASSIFIED_HISTORICAL_PMC_STAGE")
        jats = [r for r in pmc if r["stage"].startswith("PMC_JATS")]
        total_pmc += len(pmc)
        total_jats += len(jats)
        bad = []
        for r in pmc:
            status = r.get("http_status", r.get("status"))
            error = r.get("transport_error", r.get("error"))
            if status == 200 and error is None:
                continue
            key = r.get("pmid", r.get("request_key"))
            history = [a for a in pmc if (a["stage"], a.get("pmid", a.get("request_key"))) == (r["stage"], key)]
            after = [a for a in history if a["attempt"] > r["attempt"]]
            row = {"log": ref(path, "historical_transport_only_no_article_content"),
                   "stage": r["stage"], "request_key": key, "attempt": r["attempt"],
                   "http_status": status, "transport_error": error, "raw_bytes": r["raw_bytes"],
                   "timestamp_utc": r["timestamp_utc"], "later_attempts_recorded": len(after),
                   "same_logical_request_total_attempts": len(history),
                   "raw_artifact": ref(path.parent / r["raw_path"], "hash_only_no_XML_inspection")}
            require(digest(path.parent / r["raw_path"]) == r["raw_sha256"], "HISTORICAL_RAW_HASH_MISMATCH")
            row["mechanics_assessment"] = "READ_TIMEOUT_AFTER_HTTP_STATUS_NO_RETRY" if status == 200 and error and error.startswith("TimeoutError:") else "CONNECTION_RESET_PHASE_NOT_ESTABLISHED" if error and "Connection reset" in error else "OTHER_TRANSPORT_OR_STATUS_FAILURE"
            row["equivalent_mid_body_retry_positive_proof"] = False
            row["equivalence_limitation"] = "No partial body/read-progress provenance; cannot equate a connection failure or timeout with demonstrated mid-body truncation"
            bad.append(row)
            failures.append(row)
        inventories.append({"log": ref(path, "pre_D2_historical_attempt_inventory"),
                            "root_marker": ref(marker, "verified_historical_frozen_root"),
                            "root_sha256": marker.read_text().strip(), "root_verified": True,
                            "all_transport_record_count": len(records), "PMC_record_count": len(pmc),
                            "missing_stage_non_PMC_record_count": sum("stage" not in r for r in records),
                            "JATS_record_count": len(jats), "PMC_failure_count": len(bad),
                            "maximum_timestamp_utc": max((r["timestamp_utc"] for r in records), default=None)})
    return {"logs": inventories, "failures": failures, "PMC_attempt_count": total_pmc,
            "JATS_attempt_count": total_jats,
            "all_inventoried_transport_record_count": sum(r["all_transport_record_count"] for r in inventories),
            "equivalent_historical_body_interruption_retry_count": 0,
            "IncompleteRead_label_count": sum("IncompleteRead" in (r["transport_error"] or "") for r in failures),
            "demonstrated_partial_body_or_stream_truncation_failure_count": 0,
            "alpha3_20_NCBI_PMC_log_count": sum("alpha3_20" in p.parent.name for p in candidates),
            "alpha3_20_provider_Builder_Quality_semantic_logs_excluded": True,
            "search_scope": "All alpha3.18/19/20 ncbi_transport_attempts*.jsonl and pmc_request_attempts.jsonl",
            "actual_article_XML_not_parsed_or_read_as_semantic_evidence": True}


def test_inventory(cutoff):
    names = (
        "test_search_plan_v24_alpha318a_ncbi_source_executor.py",
        "test_search_plan_v24_alpha318a_v2_source_executor_offline.py",
        "test_search_plan_v24_alpha318a_v3_post_metadata_preflight.py",
        "test_search_plan_v24_alpha318a_v3_post_metadata_frozen_run.py",
        "test_run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility.py",
        "test_search_plan_v24_alpha321d_prereg_offline.py",
        "test_search_plan_v24_alpha321d1_identity_authority_offline.py",
        "test_search_plan_v24_alpha321d2_pmc_execution.py",
        "test_search_plan_v24_alpha319a1_esearch_response_validity_v2_1.py",
    )
    entries = []
    bound_tests = {
        "test_search_plan_v24_alpha321d_prereg_offline.py": d2.D / "focused_test_implementation_binding.json",
        "test_search_plan_v24_alpha321d1_identity_authority_offline.py": d2.D1 / "focused_test_implementation_binding.json",
        "test_search_plan_v24_alpha321d2_pmc_execution.py": d2.OUT / "focused_test_implementation_binding.json",
    }
    for name in names:
        path = ROOT / "tests" / name
        proof = git_temporal_proof(path, cutoff)
        bound = bound_tests.get(name)
        if bound is not None:
            require(obj(bound)["sha256"] == digest(path), "PRE_D2_TEST_BINDING_MISMATCH")
        pre_d2 = proof["current_bytes_proven_pre_D2_by_git"] or bound is not None
        text = path.read_text()
        functions = []
        for node in ast.parse(text).body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            categories = ["other_non_retry_test"]
            if name.endswith("alpha321d2_pmc_execution.py"):
                if "complete_two_phase" in node.name:
                    categories = ["status_code_HTTP_502_retry"]
                elif "per_source_failures" in node.name:
                    categories = ["status_code_HTTP_502_exhaustion", "parser_failure"]
                elif "unhandled_frozen_client" in node.name:
                    categories = ["other_redirect_rejection_at_open_not_mid_body", "fail_closed_no_retry"]
                elif "pre_network" in node.name:
                    categories = ["integrity_preflight"]
            elif "esearch_response_validity" in name:
                categories = ["out_of_scope_PubMed_ESearch_response_state_test"]
            elif "parse" in node.name or "identity" in node.name or "article" in node.name:
                categories = ["parser_or_identity_not_transport_retry"]
            functions.append({"test_name": node.name, "line_start": node.lineno, "line_end": node.end_lineno,
                              "source_sha256": sha(ast.get_source_segment(text, node).encode()),
                              "failure_categories": categories, "equivalent_mid_body_retry_expected": False})
        entries.append({"file": ref(path, "pre_D2_test_inventory_read_only"), "git_temporal_proof": proof,
                        "pre_D2_bound_test_artifact": ref(bound, "frozen_before_D2_network_barrier") if bound else None,
                        "pre_d2_proven": pre_d2, "test_functions": functions,
                        "positive_mid_body_retry_test_found": False,
                        "same_PMC_JATS_authority": "esearch_response_validity" not in name})
    excluded = ROOT / "tests/test_search_plan_v24_alpha321d21_runtime_failure_audit_offline.py"
    return {"files": entries, "equivalent_pre_D2_retry_test_count": 0,
            "search_scope": "PMCTransport and inherited alpha318a Transport plus D/D1/D2 frozen tests; ESearch comparator explicitly excluded",
            "excluded_post_D2_synthetic_tests": [ref(excluded, "post_failure_not_retry_authority")],
            "new_D22_tests_are_proof_evaluator_tests_not_pre_D2_authority": True,
            "test_content_used_as_fresh_scientific_outcome_evidence": False}


def collect_audit():
    artifacts = {}
    roots = (("alpha3_21d21", prior.OUT, prior.ROOT_MARKER, D21_SHA),
             ("alpha3_21d2", d2.OUT, d2.ROOT_MARKER, prior.D2_SHA),
             ("alpha3_21d1", d2.D1, d2.d1.ROOT_MARKER, d2.D1_SHA),
             ("alpha3_21d", d2.D, d2.d1.d.ROOT_MARKER, d2.d1.D_SHA))
    for stem, directory, marker, expected in roots:
        artifacts[stem + "_root_verification"] = prior.root_check(directory, marker, expected)
    state = d2.preflight()
    for directory in (prior.OUT, d2.OUT):
        for p in sorted(directory.glob("*.json")):
            d2.d1.d.checked_tree(obj(p))
    old_summary = obj(prior.OUT / "summary.json")
    require(old_summary["status"] == "completed" and old_summary["alpha3_21d21_classification"] == prior.CLASS_C,
            "D21_FROZEN_CLASSIFICATION_MISMATCH")
    require(obj(d2.OUT / "summary.json")["alpha3_21d2_classification"] == d2.CLASS_FAIL,
            "D2_FROZEN_FAILURE_CLASSIFICATION_MISMATCH")
    barrier_path = d2.OUT / "d2_pre_network_integrity_barrier.json"
    cutoff = datetime.fromisoformat(obj(barrier_path)["timestamp_utc"])
    attempts_path = d2.OUT / "jats_request_attempt_log.jsonl"
    attempts, structural = rows(attempts_path), rows(d2.OUT / "jats_structural_states.jsonl")
    activation_path = d2.OUT / "alpha3_21d2_jats_activation_manifest.json"
    rec = prior.reconstruct(obj(activation_path)["requests"], state["requests"], attempts, structural, 4)
    require(rec["failed"]["pmid"] == "42731998" and len(rec["failed_attempts"]) == 1,
            "FAILED_REQUEST_STATE_CHANGED")
    attempt = rec["failed_attempts"][0]
    require(cutoff < datetime.fromisoformat(attempt["timestamp_utc"]), "PRE_D2_CUTOFF_NOT_BEFORE_FAILURE")
    artifacts["pre_d2_authority_evidence_cutoff"] = {
        "enforced": True, "conservative_authority_cutoff_utc": cutoff.isoformat(),
        "basis": ref(barrier_path, "pre_first_D2_network_request_barrier"),
        "failure_observed_utc": attempt["timestamp_utc"],
        "failure_timestamp_is_observation_not_reconstructed_request_start": True,
        "eligible_authority": "Only pre-barrier frozen authority or byte-identical pre-cutoff git snapshots",
        "D2_D21_incident_and_preservation_evidence_only": True,
        "post_D2_tests_synthetic_behavior_fresh_yield_generic_web_advice_not_authority": True,
        "file_mtime_alone_not_temporal_proof": True,
    }
    artifacts["retry_authority_evidence_tier_contract"] = {
        "tiers": {"1": "Explicit frozen preregistration/contract language",
                  "2": "Pre-D2 code/runtime policy explicitly bound by contracts",
                  "3": "Pre-D2 equivalent transport-state tests", "4": "Pre-D2 equivalent historical handling",
                  "5": "Read-only pre-D2 git design/semantic evidence"},
        "higher_tier_explicit_authority_dominates_lower_tier": True,
        "positive_inclusion_required": True, "positive_exclusion_requires_closed_domain_and_explicit_exclusion": True,
        "catch_omission_does_not_establish_semantic_exclusion_or_inclusion": True,
    }
    policy_path = d2.D / "alpha3_21d_technical_retry_policy.json"
    require(digest(policy_path) == prior.RETRY_SHA, "D_RETRY_AUTHORITY_HASH_MISMATCH")
    policy = obj(policy_path)
    failure_path = state["failure_path"]
    docs = [(policy_path, 1, "frozen_D_retry_contract", "D.1 composite authority frozen before D2 barrier", True),
            (failure_path, 1, "inherited_PMC_failure_policy", "D retry.source and historical JATS.failure_policy", True),
            (state["jats_path"], 1, "historical_JATS_acquisition_contract", "D.1 and D historical route binding", True),
            (failure_path.parent / "construction_fulltext_acquisition_policy.json", 1, "historical_fulltext_route_policy", "bound historical JATS acquisition_policy", True),
            (d2.D1 / "alpha321_pmc_jats_execution_authority_v2.json", 1, "pre_D2_composite_execution_authority", "D1 root verified before first D2 request", True),
            (d2.D / "pmc_acquisition_client_authority.json", 2, "explicit_frozen_client_binding", "frozen D and inherited D1 client authority", True),
            (d2.D / "alpha3_21d_raw_response_preservation_contract.json", 1, "raw_preservation_not_body_failure_retry_assignment", "D1.raw_preservation bound before D2", True),
            (d2.D / "alpha3_21d_source_state_contract.json", 1, "per_dimension_source_state_not_transport_retry_taxonomy", "D1.source_state bound before D2", True),
            (d2.D / "pmc_jats_response_validity_contract.json", 1, "post_transport_structural_parser_guards_not_retry_domain", "D1.JATS_structure historical_contract bound before D2", True),
            (d2.D / "alpha3_21d_terminal_reason_contract.json", 1, "source_reporting_precedence_not_transport_retry_authority", "frozen D before D1 and D2", True),
            (d2.D / "alpha3_21d_execution_order.json", 1, "two_phase_request_order_not_body_retry_abstraction", "D1.request_order bound before D2", True),
            (ROOT / "runs/20260927_search_plan_v24_dev_alpha3_18a2_rebuilt_source_acquisition_preregistration_offline/pmc_jats_acquisition_contract.json", 1, "older_PMC_contract_same_failure_policy", "historical preregistration dependencies predating D2", True),
            (failure_path.parent / "source_execution_policy.json", 2, "historical_alpha318_transport_status_policy", "historical alpha318 PMC client uses this policy; not direct D retry authority", False)]
    documents = [exact_document(*values) for values in docs]
    for document in documents:
        d2.d1.d.checked_tree(obj(ROOT / document["document"]["artifact_path"]))
    artifacts["frozen_retry_contract_exact_text_evidence"] = {"documents": documents,
        "full_exact_JSON_text_stored_before_analysis": True, "body_read_retry_clause_found": False}
    artifacts["frozen_retry_artifact_inventory"] = {
        "documents": [{k: v for k, v in r.items() if k != "exact_UTF8_text"} for r in documents],
        "relevance_boundary": "Direct D/D1 retry/client dependency closure and historical PMC/JATS policy lineage",
        "out_of_scope_prior_retry_documents": [ref(ROOT / name, "not_PMC_JATS_retry_authority") for name in (
            "runs/20260928_search_plan_v24_dev_alpha3_18a4_pubmed_query_runtime_validation_amendment_offline/query_semantic_retry_policy.json",
            "runs/20261002_search_plan_v24_dev_alpha3_19a1_ncbi_esearch_backend_failure_audit_offline/alpha3_19a2_retry_policy.json",
            "runs/20261001_search_plan_v24_dev_alpha3_18b_builder_execution_preregistration_offline/builder_transport_retry_contract.json",
            "runs/20261001_search_plan_v24_dev_alpha3_18c_quality_execution_preregistration_offline/quality_transport_retry_contract.json",
            "runs/20261004_search_plan_v24_dev_alpha3_20f_final_builder_v4_contract_freeze_offline/final_builder_v4_retry_policy.json")],
        "unrelated_provider_or_ESearch_semantics_imported": False,
    }
    git_paths = [ROOT / "scripts/run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility.py",
                 ROOT / "scripts/search_plan_v24_alpha318a_execute_ncbi_source_acquisition.py",
                 ROOT / "scripts/search_plan_v24_alpha318a_v3_post_metadata_ncbi_continuation.py"]
    git_proofs = [git_temporal_proof(path, cutoff) for path in git_paths]
    require(all(r["current_bytes_proven_pre_D2_by_git"] for r in git_proofs), "BOUND_CODE_PRE_D2_TEMPORAL_PROOF_MISSING")
    client_binding = prior.code_binding(d2.legacy.PMCTransport.fetch)
    require(client_binding["sha256"] == policy["client"]["sha256"]
            and client_binding["entrypoint_source_sha256"] == policy["client"]["entrypoint_source_sha256"],
            "BOUND_TRANSPORT_CODE_CHANGED")
    source_lines, start = inspect.getsourcelines(d2.legacy.PMCTransport.fetch)
    exact_source = "".join(source_lines)
    artifacts["bound_transport_control_flow_audit"] = {
        "binding": client_binding, "exact_source": exact_source, "line_start": start,
        "line_end": start + len(source_lines) - 1,
        "ordered_flow": ["request start/counter", "response open", "status receipt", "response.read full return",
                         "raw persistence", "attempt persistence", "success/retry predicate", "caller parser after fetch return"],
        "body_read_inside_transport_operation": True,
        "successful_normal_transport_requires_read_return": True,
        "incomplete_read_completion_automatically_classified_retryable": False,
        "normal_read_inside_try": True, "HTTPError_handler_read_outside_sibling_exception_protection": True,
        "mapped_exception_tuple": ["urllib.error.HTTPError", "urllib.error.URLError", "TimeoutError", "OSError"],
        "exact_success_predicate": "status == 200 and error is None",
        "exact_retry_predicate": "status is None or status in {408, 429, 500, 502, 503, 504}",
        "closed_status_predicate_not_complete_body_failure_semantic_taxonomy": True,
        "bound_broader_full_body_failure_retry_abstraction_found": False,
        "read_inside_try_not_used_as_positive_retry_authority": True,
        "implementation_omission_not_called_coverage_defect_without_A": True,
    }
    artifacts["pre_d2_git_history_retry_semantics_audit"] = {
        "files": git_proofs, "commands_are_read_only": True,
        "bound_client_bytes_match_pre_D2_commit": True,
        "additional_explicit_body_read_retry_design_intent_found": False,
        "post_D2_commits_or_comments_used_as_authority": False,
    }
    tests = test_inventory(cutoff)
    history = historical_logs(cutoff)
    artifacts["pre_d2_retry_test_inventory"] = tests
    artifacts["pre_d2_historical_transport_failure_inventory"] = history
    timeout_doc = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19d_transport_timeout_audit_offline/audit.json"
    require(digest(timeout_doc) == (timeout_doc.parent / "audit_sha256").read_text().strip(), "HISTORICAL_TIMEOUT_AUDIT_HASH_MISMATCH")
    artifacts["historical_body_read_interruption_equivalence_audit"] = {
        "failures": history["failures"], "equivalent_retry_found": False,
        "connection_reset_without_read_progress_not_equivalent": True,
        "HTTP_200_read_TimeoutError_was_not_retried": True,
        "TimeoutError_without_partial_progress_not_upgraded_to_demonstrated_mid_body_truncation": True,
        "auxiliary_historical_timeout_audit": exact_document(timeout_doc, 4, "historical_timeout_diagnostic", "Dated auxiliary audit, not independently bound as pre-D2 semantic authority", False),
        "auxiliary_audit_not_used_for_positive_authority_without_temporal_binding": True,
        "absence_of_observed_equivalent_retry_is_not_positive_exclusion": True,
    }
    limitation = obj(prior.OUT / "failed_attempt_exception_chain.json")
    require(limitation["observed_qualified_exception_class"] is None and limitation["actual_HTTP_response_status"] is None,
            "ACTUAL_EXCEPTION_PROVENANCE_LIMITATION_CHANGED")
    artifacts["actual_exception_identity_limitation"] = {
        "D21_exception_reconstruction": ref(prior.OUT / "failed_attempt_exception_chain.json", "incident_not_retry_authority"),
        "observed_exception_name": limitation["observed_exception_name"], "actual_exception_qualified_class_known": False,
        "traceback_cause_context_known": False, "trustworthy_HTTP_response_status_known": False,
        "synthetic_candidate_not_promoted_to_observed_identity": True,
        "state_based_authority_could_resolve_without_class_if_positively_established": True,
    }
    # All entries below have explicit source bindings. These are audit findings,
    # not inferred authority merely from generic vocabulary or exception names.
    evidence = [
        {"evidence_id": "frozen_contract_text", "tier": 1, "pre_d2_proven": True, "same_PMC_JATS_authority": True,
         "kind": "STATUS_BUDGET_CONTRACT_NO_BODY_FAILURE_DOMAIN", "source": ref(policy_path, "exact_contract_evidence")},
        {"evidence_id": "bound_runtime_status_predicate", "tier": 2, "pre_d2_proven": True, "same_PMC_JATS_authority": True,
         "kind": "CLOSED_STATUS_PREDICATE_NOT_BODY_STATE_DOMAIN", "source": client_binding},
        {"evidence_id": "pre_D2_tests", "tier": 3, "pre_d2_proven": True, "same_PMC_JATS_authority": True,
         "kind": "NO_EQUIVALENT_MID_BODY_RETRY_TEST", "file_count": len(tests["files"])},
        {"evidence_id": "historical_HTTP200_read_timeout", "tier": 4, "pre_d2_proven": True, "same_PMC_JATS_authority": True,
         "kind": "HISTORICAL_READ_TIMEOUT_NO_RETRY_NOT_UNIVERSAL_EXCLUSION", "source": ref(d2.legacy.OUT / "pmc_request_attempts.jsonl", "pre_D2_observed_behavior")},
        {"evidence_id": "historical_connection_reset_retry", "tier": 4, "pre_d2_proven": True, "same_PMC_JATS_authority": False,
         "kind": "CONNECTION_RESET_PHASE_UNKNOWN_NOT_BODY_EQUIVALENCE", "equivalent_mid_body_mechanics": False},
        {"evidence_id": "pre_D2_git_snapshot", "tier": 5, "pre_d2_proven": True, "same_PMC_JATS_authority": True,
         "kind": "SAME_STATUS_BASED_CODE_NO_BROADER_EXPLICIT_SEMANTICS"},
    ]
    decision = classify_evidence(evidence)
    require(decision["classification"] == CLASS_C, "AUDITED_IMMUTABLE_EVIDENCE_ASSESSMENT_CHANGED")
    artifacts["positive_retry_authority_test"] = {
        "evidence": evidence, "positive_retry_authority_established": decision["positive_retry_authority_established"],
        "explicit_body_read_retry_text_found": False, "bound_state_abstraction_covers_incomplete_body_transfer": False,
        "pre_d2_equivalent_retry_test_found": False, "pre_d2_equivalent_historical_retry_found": False,
        "comparably_explicit_preexisting_artifact_found": False, "decision_trace": decision["decisions"],
        "weak_transport_timeout_5xx_or_synthetic_evidence_cannot_satisfy_threshold": True,
    }
    artifacts["positive_retry_exclusion_test"] = {
        "positive_retry_exclusion_established": decision["positive_retry_exclusion_established"],
        "closed_status_layer_known": True, "body_read_failure_domain_positively_closed_and_excluding": False,
        "missing_inclusion_evidence_not_treated_as_exclusion": True,
        "missing_actual_status_not_substituted_by_adapter_null": True,
    }
    artifacts["retry_closed_vs_semantic_class_audit"] = {
        "retry_authority_model": "UNRESOLVED",
        "layers": {"status_retry_predicate": "CLOSED_STATUS_SET_PLUS_NO_STATUS",
                   "exception_mapping": "CONCRETE_CODE_TUPLE_NOT_DECLARED_SEMANTIC_CLOSURE",
                   "incomplete_body_failure_semantic_domain": "UNRESOLVED"},
        "word_transport_alone_does_not_define_open_semantic_class": True,
        "incomplete_body_retry_inclusion_or_exclusion_not_uniquely_established": True,
        "reason": "A body read is within transport control flow, but its interruption is not positively assigned "
                  "to a retryable semantic state. Status-based limits do not establish universal exclusion of "
                  "body interruptions, and the incident's true status/class is unavailable.",
    }
    artifacts["final_body_read_retry_authority_classification"] = {
        **decision, "retry_authority_model": "UNRESOLVED", "final_same_attempt_authority_audit": True,
        "retry_policy_semantics_changed": False, "scientific_policy_changed": False,
        "post_outcome_retry_expansion": False, "fresh_scientific_outcomes_used": False,
        "next_stage_recommendation": NEXT_C,
    }
    consumed, remaining = len(rec["failed_attempts"]), rec["remaining_attempts"]
    old_transport_count = len(rows(d2.OUT / "oa_request_attempt_log.jsonl")) + len(attempts)
    conditional = remaining + len(rec["untouched"]) * policy["maximum_attempts_per_request"]
    require((consumed, remaining, len(rec["active"]), len(structural), len(rec["untouched"]), old_transport_count)
            == (1, 3, 47, 9, 37, 66), "D2_BUDGET_PARTITION_MISMATCH")
    artifacts["d2_attempt_budget_audit"] = {
        "failed_logical_request_id": rec["failed"]["logical_request_id"], "maximum_attempts": 4,
        "attempts_consumed": consumed, "remaining_attempts": remaining, "numbering_reset_allowed": False,
        "hypothetical_next_ordinal_if_A": consumed + 1, "original_remaining_order_ids": [r["logical_request_id"] for r in rec["untouched"]],
        "historical_transport_attempts": old_transport_count,
        "conditional_arithmetic_additional_ceiling_if_A": conditional,
        "conditional_arithmetic_cumulative_ceiling_if_A": old_transport_count + conditional,
        "maximum_additional_transport_attempts": None, "maximum_final_cumulative_transport_attempts": None,
        "conditional_arithmetic_not_execution_authority": True,
    }
    artifacts["d2_continuation_eligibility"] = {
        "eligible": False, "executable": False, "network_authorized": False,
        "runtime_recovery_within_same_primary_attempt_allowed": False,
        "reason": CLASS_C, "new_request_universe_created": False, "no_retry_no_continuation_no_21E": True,
        "hypothetical_preservation_constraints_not_an_execution_plan": True,
    }
    for name, old_name in (("oa_immutability_audit", "oa_phase_immutability_audit"),
                           ("successful_jats_immutability_audit", "successful_jats_immutability_audit"),
                           ("activation_manifest_immutability_audit", "jats_activation_manifest_immutability_audit"),
                           ("partial_response_quarantine_audit", "incomplete_read_partial_response_audit"),
                           ("partial_handoff_nonfinal_audit", "partial_construction_handoff_semantics_audit")):
        old_path = prior.OUT / (old_name + ".json")
        artifacts[name] = {"D21_preservation_audit": ref(old_path, "preserved_incident_state_not_retry_semantics"),
                           "preserved_state": obj(old_path), "originals_unchanged": True}
    exposure = obj(d2.OUT / "alpha3_21_current_attempt_fulltext_exposure_registry.json")
    require(exposure["authoritative_exposure_count"] == 9 and exposure["untrusted_observation_count"] == 1
            and exposure["current_exclusion_authority"] is False, "EXPOSURE_REGISTRY_BOUNDARY_MISMATCH")
    artifacts["fresh_attempt_exposure_preservation_audit"] = {
        "fulltext_registry": ref(d2.OUT / "alpha3_21_current_attempt_fulltext_exposure_registry.json", "unchanged_future_history"),
        "metadata_registry": ref(d2.C2 / "alpha3_21_current_attempt_metadata_identity_exposure_registry.json", "unchanged_current_attempt_history"),
        "current_authoritative_fulltext_exposure_count": 9, "current_partial_non_authoritative_observation_count": 1,
        "current_attempt_self_exclusion_allowed": False, "registry_mutated": False,
        "return_exposed_assets_to_fresh_after_failure_allowed": False,
        "partial_non_authoritative_identity_not_promoted": True,
        "future_attempt_seen_handling": "Preserve existing authority distinctions and all exposed assets as history; failure does not restore freshness",
    }
    artifacts["same_attempt_finality_rule"] = {
        "this_is_last_same_attempt_retry_authority_audit": True, "further_same_attempt_authority_audit_allowed": False,
        "authority_development_within_current_attempt_allowed": False,
        "terminal_disposition": "PRIMARY_ATTEMPT_INCOMPLETE_AT_D2_RUNTIME_AUTHORITY_GAP",
        "primary_attempt_must_close_incomplete": True, "partial_six_sources_not_final_cohort": True,
        "Builder_Quality_retrieval_evaluation_allowed": False, "next_stage_recommendation": NEXT_C,
    }
    artifacts["known_preexisting_test_environment_issue"] = {
        "preserved_issue": obj(prior.OUT / "known_preexisting_test_environment_issue.json"),
        "related_to_body_read_retry_authority": False, "historical_directory_deleted": False,
        "test_weakened_or_claimed_fixed": False,
    }
    artifacts["scientific_policy_nonadaptation_audit"] = {
        **d2.UNCHANGED, "retry_policy_semantics_changed": False, "post_outcome_retry_expansion": False,
        "runtime_overlay_created": False, "successful_responses_refreshed": False,
        "six_usable_sources_used_as_continuation_justification": False,
    }
    artifacts["scientific_state_safety_audit"] = {
        **NO_CALLS, "fresh_XML_observed": False, "actual_JATS_parsing_performed": False,
        "ConstructionEvidenceDocument_generated": False, "span_anchors_generated": 0,
        "Builder_or_Quality_requests_constructed": 0, "21E_started": False,
        "retrieval_evaluation_started": False, "retry_or_continuation_executed": False,
    }
    for _, directory, marker, expected in roots:
        prior.root_check(directory, marker, expected)
    d2.preflight()
    # Reverify every inspected document/log/code/test byte binding after processing.
    for artifact in artifacts.values():
        d2.d1.d.checked_tree(artifact)
    artifacts["historical_preservation_audit"] = {
        "D21_D2_D1_D_C2_master_inherited_roots_reverified": True,
        "D2_failed_status_and_D21_unresolved_classification_preserved": True,
        "all_inspected_document_log_code_test_references_reverified": True,
        "historical_assets_modified": False, "historical_exposure_registries_unchanged": True,
    }
    result = {
        "status": "completed", "stage_identity": STAGE, "alpha3_21d22_classification": CLASS_C,
        "primary_classification_count": 1,
        **{stem + "_root_verified": True for stem, *_ in roots},
        "pre_d2_authority_cutoff_enforced": True, "retry_authority_model": "UNRESOLVED",
        "explicit_body_read_retry_text_found": False, "pre_d2_equivalent_retry_test_found": False,
        "pre_d2_equivalent_historical_retry_found": False,
        "bound_state_abstraction_covers_incomplete_body_transfer": False,
        "actual_exception_qualified_class_known": False,
        "positive_retry_authority_established": False, "positive_retry_exclusion_established": False,
        "body_read_interruption_covered_by_preexisting_retry_authority": None,
        "runtime_recovery_within_same_primary_attempt_allowed": False,
        "failed_jats_pmid": rec["failed"]["pmid"], "failed_jats_attempts_consumed": consumed,
        "failed_jats_remaining_attempts": remaining, "oa_phase_reexecution_allowed": False,
        "successful_jats_refresh_allowed": False, "activated_jats_request_count": len(rec["active"]),
        "completed_valid_jats_count": len(structural), "pending_interrupted_jats_count": 1,
        "not_executed_after_abort_count": len(rec["untouched"]), "partial_construction_source_count": 6,
        "final_construction_source_count_derived": False, "final_construction_source_count": "NOT_DERIVED",
        "construction_source_handoff_complete": False, "alpha3_21e_handoff_eligible": False,
        "current_authoritative_fulltext_exposure_count": 9, "current_partial_non_authoritative_observation_count": 1,
        "maximum_additional_transport_attempts": None, "maximum_final_cumulative_transport_attempts": None,
        "retry_policy_semantics_changed": False, "scientific_policy_changed": False,
        "runtime_behavior_label": decision["runtime_behavior_label"], "post_outcome_retry_expansion": False,
        "further_same_attempt_authority_audit_allowed": False, "primary_attempt_must_close_incomplete": True,
        **NO_CALLS, "next_stage_recommendation": NEXT_C, "historical_assets_modified": False,
    }
    artifacts["validation"] = {**result, "integrity_and_preservation_checks_passed": True,
                               "positive_authority_threshold_applied": True, "no_A_only_artifacts": True}
    artifacts["summary"] = result
    require(set(artifacts) == set(REQUIRED), "REQUIRED_ARTIFACT_MEMBERSHIP_MISMATCH")
    return artifacts


def put_bytes(name, raw):
    path = OUT / name
    require(path.parent == OUT and not path.is_symlink(), "OUTPUT_PATH_ESCAPE_OR_SYMLINK")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def run(verification=None):
    require(not OUT.exists(), "D22_OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    if verification is not None:
        require(verification["implementation_sha256"] == digest(Path(__file__))
                and verification["test_implementation_sha256"] == digest(
                    ROOT / "tests/test_search_plan_v24_alpha321d22_final_retry_authority_offline.py")
                and verification["checks"] and all(c["check_passed"] is True for c in verification["checks"]),
                "LOCAL_VERIFICATION_REPORT_MISMATCH")
    with prior.offline_guard():
        try:
            artifacts = collect_audit()
        except Exception as exc:
            result = {"status": "failed", "stage_identity": STAGE, "alpha3_21d22_classification": CLASS_INTEGRITY,
                      "primary_classification_count": 1, "failure": type(exc).__name__ + ":" + str(exc), **NO_CALLS,
                      "runtime_recovery_within_same_primary_attempt_allowed": False,
                      "next_stage_recommendation": NEXT_INTEGRITY, "historical_assets_modified": False,
                      "further_same_attempt_authority_audit_allowed": False}
            artifacts = {name: {"audit_state": "NOT_DERIVED_AFTER_INTEGRITY_FAILURE", **result} for name in REQUIRED}
            artifacts["summary"] = artifacts["validation"] = result
        OUT.mkdir()
        for name, value in artifacts.items():
            put_bytes(name + ".json", canonical(value) + b"\n")
        put_bytes("audit_implementation_binding.json", canonical(prior.code_binding(run)) + b"\n")
        put_bytes("focused_test_implementation_binding.json", canonical(ref(
            ROOT / "tests/test_search_plan_v24_alpha321d22_final_retry_authority_offline.py", "offline_proof_evaluator_tests_not_pre_D2_authority")) + b"\n")
        if verification is not None:
            put_bytes("offline_verification_results.json", canonical(verification) + b"\n")
        require(not any((OUT / name).exists() for name in A_ONLY), "A_ONLY_ARTIFACT_WITHOUT_A_AUTHORITY")
        output_root = root_hash(OUT, ROOT_MARKER)
        put_bytes(ROOT_MARKER, (output_root + "\n").encode("ascii"))
        require(root_hash(OUT, ROOT_MARKER) == output_root, "D22_OUTPUT_ROOT_MISMATCH")
        return {**artifacts["summary"], ROOT_MARKER: output_root}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, sort_keys=True), flush=True)
    raise SystemExit(0 if result["status"] == "completed" else 1)
