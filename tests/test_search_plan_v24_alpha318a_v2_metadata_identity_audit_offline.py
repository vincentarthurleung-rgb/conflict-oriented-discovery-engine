"""Verify V2 source frames survived but metadata identity extraction did not."""

import json

from scripts import search_plan_v24_alpha318a_v2_audit_metadata_identity_offline as audit


def test_source_run_preserved_and_downstream_invalidated():
    assert audit.run_root() == audit.EXPECTED_RUN_ROOT
    original = json.loads((audit.SOURCE_RUN / "validation.json").read_text())
    result = json.loads((audit.OUT / "validation.json").read_text())
    assert original["status"] == "PASS"
    assert result["status"] == "FAILED_CLOSED"
    assert result["six_source_frames_frozen"] is True
    assert result["construction_source_manifest_frozen_valid"] is False


def test_reference_ids_caused_false_main_article_identity_ambiguity():
    summary = json.loads((audit.OUT / "metadata_identity_failure_summary.json").read_text())
    findings = [json.loads(line) for line in (audit.OUT / "metadata_identity_path_findings.jsonl").read_text().splitlines()]
    assert len(findings) == 72
    assert summary["executor_PMCID_ambiguity_exclusions"] == 70
    assert summary["executor_DOI_ambiguity_exclusions"] == 1
    assert summary["main_article_single_PMCID_records"] == 72
    assert all(row["main_article_pmcid_count"] == 1 for row in findings)


def test_audit_root_self_consistent():
    files = sorted(p for p in audit.OUT.iterdir() if p.is_file() and p.name != audit.MARKER)
    actual = audit.v2.base.sha(audit.v2.base.canonical([[p.name, audit.v2.base.sha(p.read_bytes())]
        for p in files]))
    assert actual == (audit.OUT / audit.MARKER).read_text().strip()
