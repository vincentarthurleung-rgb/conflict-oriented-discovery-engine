"""Confirm the six HTTP-200 ESearch error bodies invalidate frame completion."""

import json

from scripts import search_plan_v24_alpha318a_audit_source_frame_response_offline as audit


def test_original_run_preserved_and_invalidated_by_separate_audit():
    assert audit.execution.root_hash() == audit.EXPECTED_SOURCE_ROOT
    result = json.loads((audit.OUT / "validation.json").read_text())
    assert result["status"] == "FAILED_CLOSED"
    assert result["valid_source_frames_completed"] == 0
    assert result["six_source_frames_frozen"] is False
    assert json.loads((audit.SOURCE_RUN / "validation.json").read_text())["status"] == "PASS"


def test_all_six_raw_ncbi_responses_include_unresolved_pmc_phrase():
    report = json.loads((audit.OUT / "ncbi_esearch_error_findings.json").read_text())
    assert report["http_200_error_bodies"] == 6
    assert len(report["findings"]) == 6
    assert all(row["unresolved_pmc_phrase"] for row in report["findings"])
    assert all(row["valid_empty_frame"] is False for row in report["findings"])
