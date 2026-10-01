#!/usr/bin/env python3
"""Independently audit V2 metadata identity extraction without modifying the run."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

try:
    from scripts import search_plan_v24_alpha318a_v2_execute_ncbi_source_acquisition as v2
except ModuleNotFoundError:
    import search_plan_v24_alpha318a_v2_execute_ncbi_source_acquisition as v2


ROOT = v2.ROOT
SOURCE_RUN = v2.OUT
OUT = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18a_v2_metadata_identity_failure_audit_offline"
EXPECTED_RUN_ROOT = "67706ced26bcb1f8b0eb850373c37d81bf4e84f4a17cffd2b537ebee74eef6cc"
MARKER = "search_plan_v24_dev_alpha3_18a_v2_metadata_failure_audit_sha256"


def run_root() -> str:
    files = sorted(p for p in SOURCE_RUN.rglob("*") if p.is_file() and p.name != v2.ROOT_MARKER)
    return v2.base.sha(v2.base.canonical([[str(p.relative_to(SOURCE_RUN)), v2.base.sha(p.read_bytes())]
        for p in files]))


def write(name: str, value: Any) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(v2.base.canonical(value) + b"\n")


def write_jsonl(name: str, rows: list[Any]) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(b"".join(v2.base.canonical(row) + b"\n" for row in rows))


def main() -> None:
    if OUT.exists():
        raise RuntimeError("V2 metadata failure audit already frozen")
    if run_root() != EXPECTED_RUN_ROOT or (SOURCE_RUN / v2.ROOT_MARKER).read_text().strip() != EXPECTED_RUN_ROOT:
        raise RuntimeError("V2 source run root mismatch")
    reported = json.loads((SOURCE_RUN / "validation.json").read_text())
    if reported["status"] != "PASS" or reported["source_frames_completed"] != 6:
        raise RuntimeError("V2 self-reported run state changed")
    records = [json.loads(line) for line in (SOURCE_RUN / "sampled_source_metadata_records.jsonl").read_text().splitlines()]
    exclusions = [json.loads(line) for line in (SOURCE_RUN / "mechanical_source_exclusion_results.jsonl").read_text().splitlines()]
    if len(records) != 72 or len(exclusions) != 72:
        raise RuntimeError("expected 72 frozen sampled-source records")
    findings = []
    for record in records:
        attempt = record["attempts"][-1]
        raw_path = SOURCE_RUN / attempt["raw_path"]
        raw = raw_path.read_bytes()
        if v2.base.sha(raw) != attempt["raw_sha256"]:
            raise RuntimeError("raw metadata response hash mismatch")
        articles = [node for node in ET.fromstring(raw).iter() if node.tag.rsplit("}", 1)[-1] == "PubmedArticle"]
        if len(articles) != 1:
            raise RuntimeError("unexpected PubMed article count in audit")
        pubmed_data = next((node for node in articles[0] if node.tag.rsplit("}", 1)[-1] == "PubmedData"), None)
        if pubmed_data is None:
            raise RuntimeError("PubmedData absent in audit")
        main_list = next((node for node in pubmed_data if node.tag.rsplit("}", 1)[-1] == "ArticleIdList"), None)
        if main_list is None:
            raise RuntimeError("main PubmedData/ArticleIdList absent in audit")
        direct = [node for node in main_list if node.tag.rsplit("}", 1)[-1] == "ArticleId"]
        recursive = [node for node in pubmed_data.iter() if node.tag.rsplit("}", 1)[-1] == "ArticleId"]
        def ids(nodes: list[ET.Element], kind: str) -> list[str]:
            return sorted({(node.text or "").strip() for node in nodes if node.attrib.get("IdType") == kind})
        direct_pmc, recursive_pmc = ids(direct, "pmc"), ids(recursive, "pmc")
        direct_doi, recursive_doi = ids(direct, "doi"), ids(recursive, "doi")
        findings.append({"pmid": record["pmid"], "raw_response_path": str(raw_path.relative_to(ROOT)),
            "raw_response_sha256": attempt["raw_sha256"],
            "reported_metadata_state": record["state"],
            "main_article_pmcid_count": len(direct_pmc),
            "recursive_pubmeddata_pmcid_count": len(recursive_pmc),
            "main_article_doi_count": len(direct_doi),
            "recursive_pubmeddata_doi_count": len(recursive_doi),
            "nested_reference_ids_included_by_executor": (len(recursive_pmc) > len(direct_pmc)
                or len(recursive_doi) > len(direct_doi))})
    ambiguous_pmc = sum(any(reason == "METADATA_UNRESOLVED:PMCID missing or ambiguous" for reason in row["reasons"])
                        for row in exclusions)
    ambiguous_doi = sum(any(reason == "METADATA_UNRESOLVED:DOI ambiguous" for reason in row["reasons"])
                        for row in exclusions)
    if ambiguous_pmc != 70 or ambiguous_doi != 1:
        raise RuntimeError("metadata failure signature changed")
    if not all(row["main_article_pmcid_count"] == 1 for row in findings):
        raise RuntimeError("main-article PMCID count is not uniformly one")
    OUT.mkdir()
    write("source_run_preservation.json", {"source_run_root_sha256": EXPECTED_RUN_ROOT,
        "source_run_reported_status": "PASS", "source_run_modified": False,
        "all_six_source_frames_valid": True, "deduplicated_frame_and_sampling_valid": True,
        "metadata_and_downstream_completion_valid": False})
    write_jsonl("metadata_identity_path_findings.jsonl", findings)
    write("metadata_identity_failure_summary.json", {
        "failure_code": "SAMPLED_METADATA_IDENTITY_PATH_VIOLATION",
        "frozen_required_path": "PubmedArticle/PubmedData/ArticleIdList/ArticleId immediate child",
        "executor_actual_path": "PubmedArticle/PubmedData recursive descendant ArticleId",
        "why_invalid": "The recursive path includes ReferenceList/Reference/ArticleIdList and conflates cited papers with the sampled paper.",
        "sampled_source_count": 72, "executor_PMCID_ambiguity_exclusions": ambiguous_pmc,
        "executor_DOI_ambiguity_exclusions": ambiguous_doi,
        "main_article_single_PMCID_records": sum(row["main_article_pmcid_count"] == 1 for row in findings),
        "nested_reference_id_contamination_records": sum(row["nested_reference_ids_included_by_executor"] for row in findings),
        "source_frames_remain_valid": True, "sampling_remains_valid": True,
        "no_metadata_reinterpretation_or_source_replacement_performed": True})
    write("invalid_downstream_disposition.json", {"status": "FAILED_CLOSED",
        "overall_source_acquisition_complete": False,
        "valid_partial_stages": ["six source frames", "cross-stratum deduplication", "deterministic sampling"],
        "invalid_or_unreliable_stages": ["sampled metadata classification", "seen-source decision",
            "publication and correction states", "OA/license attrition", "JATS selection",
            "construction-source manifest", "builder request manifest", "builder call budget"],
        "reported_zero_builder_budget_authoritative": False,
        "actual_builder_scientific_call_count": "UNKNOWN",
        "in_run_patch_or_rerun_allowed": False})
    write("scientific_state_safety_audit.json", {"new_network_calls": 0, "provider_calls": 0,
        "llm_calls": 0, "builder_calls": 0, "quality_calls": 0,
        "historical_assets_modified": False, "source_run_modified": False})
    write("validation.json", {"status": "FAILED_CLOSED",
        "failure_code": "SAMPLED_METADATA_IDENTITY_PATH_VIOLATION",
        "source_run_root_verified": True, "source_run_self_reported_success_valid": False,
        "six_source_frames_frozen": True, "sampling_after_all_frames": True,
        "construction_source_manifest_frozen_valid": False,
        "builder_request_manifest_frozen_valid": False,
        "network_calls_in_this_audit": 0})
    write("summary.json", {"status": "failed", "source_run_root_sha256": EXPECTED_RUN_ROOT,
        "source_frames_completed": 6, "sampled_source_count_valid": 72,
        "construction_source_count_authoritative": None,
        "actual_builder_scientific_call_count_authoritative": None,
        "next_stage_recommendation": "AUDIT_ALPHA3_18A_V2_RUNTIME_FAILURE_OFFLINE",
        "do_not_use_source_run_self_reported_downstream_metrics": True})
    root = v2.base.sha(v2.base.canonical([[p.name, v2.base.sha(p.read_bytes())]
        for p in sorted(OUT.iterdir()) if p.is_file()]))
    (OUT / MARKER).write_text(root + "\n", encoding="utf-8")
    print(json.dumps({"status": "failed_closed", "run_root": EXPECTED_RUN_ROOT,
        "audit_root": root, "pmcid_false_ambiguity_exclusions": ambiguous_pmc,
        "new_network_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
