#!/usr/bin/env python3
"""Preserve and invalidate a frozen source run that accepted NCBI ESearch errors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from scripts import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as execution
except ModuleNotFoundError:
    import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as execution


ROOT = execution.ROOT
SOURCE_RUN = execution.OUT
OUT = ROOT / "runs/20260928_search_plan_v24_dev_alpha3_18a_source_frame_response_error_audit_offline"
EXPECTED_SOURCE_ROOT = "7b6fa0b94ebd415c11e2e70c5299031a4e4aa7183e6d283863a984bf364800b8"
MARKER = "search_plan_v24_dev_alpha3_18a_source_frame_error_audit_sha256"


def write(name: str, value: Any) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(execution.canonical(value) + b"\n")


def main() -> None:
    if OUT.exists():
        raise RuntimeError("source-frame error audit already frozen")
    if execution.root_hash() != EXPECTED_SOURCE_ROOT or (SOURCE_RUN / execution.ROOT_MARKER).read_text().strip() != EXPECTED_SOURCE_ROOT:
        raise RuntimeError("source-run root mismatch")
    source_validation = json.loads((SOURCE_RUN / "validation.json").read_text())
    if source_validation["status"] != "PASS":
        raise RuntimeError("source-run reported status changed")
    rows = [json.loads(line) for line in (SOURCE_RUN / "source_query_execution_results.jsonl").read_text().splitlines()]
    if len(rows) != 6 or any(row["status"] != "COMPLETE" for row in rows):
        raise RuntimeError("unexpected query result structure")
    findings = []
    for row in rows:
        attempt = row["attempts"][-1]
        raw_path = SOURCE_RUN / attempt["raw_path"]
        raw = raw_path.read_bytes()
        if execution.sha(raw) != attempt["raw_sha256"]:
            raise RuntimeError("raw NCBI response hash mismatch")
        response = json.loads(raw)
        result = response["esearchresult"]
        errors = result.get("errorlist") or {}
        findings.append({"stratum_id": row["stratum_id"], "reported_page_status": row["status"],
            "http_status": attempt["status"], "reported_count": row["count"],
            "raw_response_path": str(raw_path.relative_to(ROOT)), "raw_response_sha256": attempt["raw_sha256"],
            "ncbi_errorlist": errors, "unresolved_pmc_phrase": "pmc" in errors.get("phrasesnotfound", []),
            "valid_empty_frame": False if errors.get("phrasesnotfound") or errors.get("fieldsnotfound") else None})
    if not all(item["unresolved_pmc_phrase"] and item["http_status"] == 200 for item in findings):
        raise RuntimeError("six-query NCBI error signature not reproduced")
    OUT.mkdir()
    write("source_run_preservation.json", {"source_run_root_sha256": EXPECTED_SOURCE_ROOT,
        "source_run_reported_status": "PASS", "source_run_modified": False,
        "authoritative_manifest_sha256": execution.MANIFEST_SHA,
        "authority_boundary": "This independent audit supersedes the source run's self-reported completion, without rewriting it."})
    write("ncbi_esearch_error_findings.json", {"query_count": 6, "http_200_error_bodies": 6,
        "error_signature": "esearchresult.errorlist.phrasesnotfound contains pmc",
        "findings": findings, "retrieval_hit_count_interpretation": "INVALID_QUERY_RESPONSE_NOT_ZERO_VALID_HITS"})
    write("invalid_completion_disposition.json", {"status": "FAILED_CLOSED",
        "failure_code": "SOURCE_FRAME_ACQUISITION_FAILED_CLOSED",
        "valid_source_frames_completed": 0, "reported_complete_frames_rejected": 6,
        "six_source_frames_frozen": False, "sampling_barrier_satisfied": False,
        "downstream_zero_sample_and_manifest_artifacts_valid": False,
        "no_query_edit_or_rerun_authorized": True,
        "reason": "The frozen PubMed ESearch queries returned structured NCBI errorlist data; HTTP 200 and count=0 did not constitute a valid empty source frame."})
    write("scientific_state_safety_audit.json", {"network_calls": 0, "provider_calls": 0,
        "llm_calls": 0, "builder_calls": 0, "quality_calls": 0, "source_run_modified": False,
        "new_query_calls": 0, "query_changes": 0})
    write("validation.json", {"status": "FAILED_CLOSED", "failure_code": "SOURCE_FRAME_ACQUISITION_FAILED_CLOSED",
        "source_run_root_verified": True, "source_run_self_reported_success_valid": False,
        "valid_source_frames_completed": 0, "six_source_frames_frozen": False,
        "network_calls_in_this_audit": 0, "provider_calls": 0})
    write("summary.json", {"status": "failed", "source_run_root_sha256": EXPECTED_SOURCE_ROOT,
        "valid_source_frames_completed": 0, "sampled_source_count_authoritative": None,
        "construction_source_count_authoritative": None,
        "actual_builder_scientific_call_count_authoritative": None,
        "next_stage_recommendation": "AUDIT_ALPHA3_18A_RUNTIME_FAILURE_OFFLINE",
        "do_not_use_source_run_self_reported_metrics": True})
    root = execution.sha(execution.canonical([[p.name, execution.sha(p.read_bytes())]
        for p in sorted(OUT.iterdir()) if p.is_file()]))
    (OUT / MARKER).write_text(root + "\n", encoding="utf-8")
    print(json.dumps({"status": "failed_closed", "source_run_root": EXPECTED_SOURCE_ROOT,
                      "audit_root": root, "invalid_frame_responses": len(findings),
                      "new_network_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
