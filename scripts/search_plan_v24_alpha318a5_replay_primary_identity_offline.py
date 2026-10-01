#!/usr/bin/env python3
"""Freeze alpha3.18A.5 from V2 bytes only; never makes a network request."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts import search_plan_v24_alpha318a5_primary_identity as identity
    from scripts import search_plan_v24_alpha318a_v2_audit_metadata_identity_offline as failure_audit
    from scripts import search_plan_v24_alpha318a3_correction_reference as correction
    from scripts import search_plan_v24_alpha318a_v2_execute_ncbi_source_acquisition as v2
except ModuleNotFoundError:
    import search_plan_v24_alpha318a5_primary_identity as identity
    import search_plan_v24_alpha318a_v2_audit_metadata_identity_offline as failure_audit
    import search_plan_v24_alpha318a3_correction_reference as correction
    import search_plan_v24_alpha318a_v2_execute_ncbi_source_acquisition as v2


ROOT = v2.ROOT
SOURCE = v2.OUT
AUDIT = failure_audit.OUT
OUT = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18a5_primary_citation_identity_binding_offline"
MARKER = "search_plan_v24_dev_alpha3_18a5_sha256"
AUDIT_ROOT = "a06731a5bcf7914d9899ccd139edfeda75b8ce7a77682f835d0f92a747a99e9b"
AMEND_ROOT = "cc222ad4566c4b54ac243f63341c58df98ec68627c8b992814002ac05567d17b"
MANIFEST_SHA = "ddcf9619bf8d5ecec26e0ce71486c2c1617629034cf2d464c3214637c2ad89b3"
BASE = v2.base


def digest(path: Path) -> str:
    return BASE.sha(path.read_bytes())


def ref(path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def write(name: str, value: Any) -> None:
    BASE.write_json(OUT / name, value)


def write_rows(name: str, value: list[Any]) -> None:
    BASE.write_jsonl(OUT / name, value)


def sha_marker(name: str, path: Path) -> str:
    value = digest(path)
    BASE.write_bytes(OUT / name, (value + "\n").encode())
    return value


def verify_roots() -> dict[str, Any]:
    if failure_audit.run_root() != failure_audit.EXPECTED_RUN_ROOT or (
        SOURCE / v2.ROOT_MARKER).read_text().strip() != failure_audit.EXPECTED_RUN_ROOT:
        raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: V2 root")
    if BASE.prior.all_file_root(AUDIT, failure_audit.MARKER) != AUDIT_ROOT or (
        AUDIT / failure_audit.MARKER).read_text().strip() != AUDIT_ROOT:
        raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: failure audit root")
    original = json.loads((SOURCE / "validation.json").read_text())
    if original["status"] != "PASS" or original["source_frames_completed"] != 6:
        raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: preserved self-report")
    if json.loads((AUDIT / "metadata_identity_failure_summary.json").read_text())[
        "failure_code"] != "SAMPLED_METADATA_IDENTITY_PATH_VIOLATION":
        raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: failure classification")
    manifest = v2.verify_before_network()  # static local preflight only; no transport is constructed
    if BASE.prior.all_file_root(v2.freeze.OUT, v2.freeze.ROOT_MARKER) != AMEND_ROOT:
        raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: alpha3.18A.4 root")
    if digest(v2.freeze.OUT / "alpha3_18a4_source_acquisition_execution_manifest_v2.json") != MANIFEST_SHA:
        raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: V2 manifest")
    return manifest


def verify_checkpoint() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    frame_files = sorted((SOURCE / "six_source_frame_manifests").glob("*.json"))
    if len(frame_files) != 6 or any(path.is_symlink() for path in frame_files):
        raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: frame file count")
    frame_aggregate = BASE.sha(BASE.canonical([[path.name, digest(path)] for path in frame_files]))
    if frame_aggregate != (SOURCE / "six_source_frames_sha256").read_text().strip():
        raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: frame aggregate")
    frames = [json.loads(path.read_text()) for path in frame_files]
    if [frame["stratum_id"] for frame in frames] != BASE.STRATA or any(
        frame["status"] != "COMPLETE_VALID_V2" for frame in frames):
        raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: frame order/state")
    membership: dict[str, list[str]] = {}
    for frame in frames:
        for pmid in frame["ordered_unique_pmids"]:
            membership.setdefault(pmid, []).append(frame["stratum_id"])
    expected_frame = [{"pmid": pmid, "owner_stratum": frame["stratum_id"],
        "owner_frame_position": position, "all_strata": membership[pmid]}
        for frame in frames for position, pmid in enumerate(frame["ordered_unique_pmids"])
        if membership[pmid][0] == frame["stratum_id"]]
    stored_frame = rows(SOURCE / "new_pool_source_sampling_frame.jsonl")
    if stored_frame != expected_frame or len(stored_frame) != 1041 or (
        digest(SOURCE / "new_pool_source_sampling_frame.jsonl") !=
        (SOURCE / "new_pool_source_sampling_frame_sha256").read_text().strip()):
        raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: deduplicated sampling frame")
    duplicate_audit = json.loads((SOURCE / "cross_stratum_duplicate_audit.json").read_text())
    if duplicate_audit["canonical_unique_pmids"] != len(stored_frame) or (
        duplicate_audit["cross_stratum_duplicate_pmids"] !=
        sum(len(value) > 1 for value in membership.values())):
        raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: dedup audit")
    sampled = rows(SOURCE / "deterministic_source_sampling_results.jsonl")
    sample_summary = json.loads((SOURCE / "source_sampling_summary.json").read_text())
    seed = BASE.prior.load(BASE.prior.SOURCE, "source_sampling_algorithm.json")["seed_sha256"]
    if len(sampled) != 72 or len({row["pmid"] for row in sampled}) != 72 or (
        sample_summary["sample_count"] != 72 or sample_summary["seed_sha256"] != seed):
        raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: sample count/seed")
    frame_by_pmid = {row["pmid"]: row for row in stored_frame}
    for row in sampled:
        pmid = row["pmid"]
        expected_key = BASE.sha(f"{seed}:{row['owner_stratum']}:{pmid}".encode())
        if pmid not in frame_by_pmid or any(row[key] != frame_by_pmid[pmid][key]
            for key in ("owner_stratum", "owner_frame_position", "all_strata")) or (
            row["sample_key_sha256"] != expected_key):
            raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: sampled identity/key")
    for stratum in BASE.STRATA:
        actual = [row for row in sampled if row["owner_stratum"] == stratum]
        if len(actual) != 12 or [row["sample_rank_in_stratum"] for row in actual] != list(range(1, 13)) or (
            [row["sample_key_sha256"] for row in actual] !=
            sorted(row["sample_key_sha256"] for row in actual)):
            raise RuntimeError("UPSTREAM_CHECKPOINT_REUSE_UNSAFE: sampled stratum order")
    return sampled, {"six_source_frame_files": [ref(path) for path in frame_files],
        "six_source_frames_sha256": frame_aggregate,
        "cross_stratum_duplicate_audit": ref(SOURCE / "cross_stratum_duplicate_audit.json"),
        "deduplicated_source_universe": ref(SOURCE / "new_pool_source_sampling_frame.jsonl"),
        "sampling_frame_sha256": digest(SOURCE / "new_pool_source_sampling_frame.jsonl"),
        "deterministic_sample": ref(SOURCE / "deterministic_source_sampling_results.jsonl"),
        "sampling_summary": ref(SOURCE / "source_sampling_summary.json"),
        "sampled_pmids_in_frozen_order": [row["pmid"] for row in sampled],
        "valid_source_frames_reused": True, "valid_dedup_result_reused": True,
        "valid_72_source_sample_reused": True, "resampling_performed": False,
        "sampling_algorithm_rerun_for_selection": False}


def load_raw_metadata(sampled: list[dict[str, Any]]) -> tuple[list[tuple[dict[str, Any], bytes]], dict[str, Any]]:
    old = rows(SOURCE / "sampled_source_metadata_records.jsonl")
    if len(old) != 72 or [row["pmid"] for row in old] != [row["pmid"] for row in sampled]:
        raise RuntimeError("SAMPLED_METADATA_RAW_RESPONSE_INCOMPLETE: record identities")
    raw_items: list[tuple[dict[str, Any], bytes]] = []
    raw_refs = []
    for selected, record in zip(sampled, old):
        attempts = record["attempts"]
        good = [attempt for attempt in attempts if attempt["status"] == 200 and attempt["error"] is None]
        if len(good) != 1:
            raise RuntimeError("SAMPLED_METADATA_RAW_RESPONSE_INCOMPLETE: successful response count")
        attempt = good[0]
        path = SOURCE / attempt["raw_path"]
        if not path.resolve().is_relative_to((SOURCE / "sampled_metadata_raw_responses").resolve()) or (
            not path.is_file()):
            raise RuntimeError("SAMPLED_METADATA_RAW_RESPONSE_INCOMPLETE: missing/path")
        raw = path.read_bytes()
        if not raw or BASE.sha(raw) != attempt["raw_sha256"] or (
            record["raw_sha256"] != attempt["raw_sha256"]) or (
            attempt["parameters"] != {"db": "pubmed", "retmode": "xml", "id": selected["pmid"]}):
            raise RuntimeError("SAMPLED_METADATA_RAW_RESPONSE_INCOMPLETE: byte hash/request")
        raw_items.append((record, raw))
        raw_refs.append(ref(path))
    if len(raw_items) != 72:
        raise RuntimeError("SAMPLED_METADATA_RAW_RESPONSE_INCOMPLETE: count")
    return raw_items, {"expected_sampled_metadata_responses": 72,
        "complete_verified_raw_responses": 72, "raw_response_refs": raw_refs,
        "all_raw_response_hashes_verified": True, "new_metadata_requests": 0}


def replay(sampled: list[dict[str, Any]], raw_items: list[tuple[dict[str, Any], bytes]]) -> dict[str, Any]:
    registry_path = BASE.prior.SOURCE / "seen_source_local_registry.json"
    registry = json.loads(registry_path.read_text())
    seen_hashes = set(registry["hashed_pmcids"])
    identity_rows, metadata_rows, seen_rows, type_rows, correction_rows, pre_oa = [], [], [], [], [], []
    for selected, (old, raw) in zip(sampled, raw_items):
        pmid = selected["pmid"]
        try:
            bound = identity.bind_primary_citation(raw, pmid)
        except Exception as exc:
            raise RuntimeError(f"PRIMARY_CITATION_BINDING_FAILED:{pmid}:{exc}") from exc
        identity_rows.append({"pmid": pmid, "raw_sha256": BASE.sha(raw), **bound})
        meta = ({"pmid": pmid, "pmcid": bound["pmcid"], "doi": bound["doi"],
            "publication_year": bound["publication_year"],
            "publication_types": bound["publication_types"],
            "correction_relationships": bound["correction_relationships"]}
            if bound["metadata_state"] == "RESOLVED" else None)
        metadata_rows.append({"pmid": pmid, "metadata": meta, "raw_sha256": BASE.sha(raw),
            "state": bound["metadata_state"],
            "unresolved_reasons": bound["metadata_unresolved_reasons"],
            "identity_binding": "PubMedPrimaryCitationIdentityBindingV1"})
        # These structured fields remain independently readable even when the
        # frozen date rule makes the aggregate metadata record unresolved.
        if bound["pmcid"] is None:
            seen_state = "SOURCE_IDENTITY_UNRESOLVED"
            seen = {"pmid": pmid, "state": seen_state}
        else:
            seen_hash = BASE.sha((registry["hash_domain"] + bound["pmcid"]).encode())
            seen_state = "MATCHED_FROZEN_SEEN_SOURCE" if seen_hash in seen_hashes else "NO_FROZEN_LOCAL_MATCH"
            seen = {"pmid": pmid, "pmcid": bound["pmcid"], "state": seen_state,
                "registry_sha256": digest(registry_path)}
        preliminary = BASE.preliminary_type(bound["publication_types"])
        correction_result = correction.classify(bound["publication_types"], bound["correction_relationships"])
        reasons = ["METADATA_UNRESOLVED:" + item for item in bound["metadata_unresolved_reasons"]]
        if seen_state == "MATCHED_FROZEN_SEEN_SOURCE":
            reasons.append(seen_state)
        if preliminary["state"] != "PRELIMINARY_TYPE_ACCEPTED":
            reasons.append("PUBLICATION_TYPE:" + preliminary["reason"])
        conditional_update = (correction_result["state"] == "CORRECTION_REFERENCE_UNRESOLVED" and
            correction_result["unresolved_reasons"] == ["REF_TYPE:UpdateOf:INDEPENDENT_SOURCE_NOT_YET_ELIGIBLE"])
        if correction_result["state"] != "CORRECTION_REFERENCE_CLEAR" and not conditional_update:
            reasons.append(correction_result["state"])
        if not reasons:
            pre_oa.append({"sample_rank_global": len(metadata_rows), "pmid": pmid,
                "pmcid": bound["pmcid"], "doi": bound["doi"],
                "raw_metadata_sha256": BASE.sha(raw),
                "preliminary_publication_type_state": preliminary["state"],
                "seen_source_state": seen_state,
                "correction_reference_preliminary_state": correction_result["state"],
                "conditional_update_of_deferred_until_jats": conditional_update,
                "next_stage": "PMC_OA_SUBSET_VERIFICATION"})
        seen_rows.append(seen)
        type_rows.append({"pmid": pmid, "phase": "PRELIMINARY", "result": preliminary})
        correction_rows.append({"pmid": pmid, "phase": "PRELIMINARY", "snapshot_sha256": BASE.sha(raw),
            "result": correction_result})
        identity_rows[-1]["metadata_only_exclusion_reasons"] = reasons
    return {"identity_rows": identity_rows, "metadata_rows": metadata_rows,
        "seen_rows": seen_rows, "type_rows": type_rows,
        "correction_rows": correction_rows, "pre_oa_rows": pre_oa}


def main() -> None:
    if OUT.exists():
        raise RuntimeError("alpha3.18A.5 output already exists; refusing overwrite")
    frozen_v2_manifest = verify_roots()
    sampled, checkpoint = verify_checkpoint()
    raw_items, raw_audit = load_raw_metadata(sampled)
    result = replay(sampled, raw_items)
    ids = result["identity_rows"]
    if len(ids) != 72 or len(result["metadata_rows"]) != 72:
        raise RuntimeError("PRIMARY_CITATION_BINDING_FAILED: incomplete replay")
    legacy_pmc = sum(len(row["legacy_pmcid_values"]) > 1 for row in ids)
    direct_pmc = sum(len(row["direct_pmcid_values"]) > 1 for row in ids)
    legacy_doi = sum(len(row["legacy_doi_values"]) > 1 for row in ids)
    direct_doi = sum(len(row["direct_doi_values"]) > 1 for row in ids)
    reference_count = sum(len(row["reference_article_ids"]) for row in ids)
    changed = sum((row["legacy_pmcid_values"] != row["direct_pmcid_values"] or
        row["legacy_doi_values"] != row["direct_doi_values"]) for row in ids)
    source_refs = [ref(path) for path in sorted(SOURCE.rglob("*")) if path.is_file()]
    # All preflight reads finished before the first output write.
    OUT.mkdir(parents=True)
    write("alpha3_18a_v2_failure_verification.json", {"failure_code": "PUBMED_PRIMARY_CITATION_IDENTITY_SCOPE_DEFECT",
        "source_run_root_sha256": failure_audit.EXPECTED_RUN_ROOT,
        "original_self_reported_status": "PASS", "original_self_reported_status_authoritative": False,
        "original_ncbi_request_attempts": 100, "original_v2_failed_run_preserved": True,
        "failed_run_artifact_count": len(source_refs)})
    write("metadata_identity_failure_audit_verification.json", {"independent_audit_root_sha256": AUDIT_ROOT,
        "audit_verified": True, "metadata_and_downstream_invalid": True,
        "valid_upstream_checkpoint": "six frames, dedup, sample, raw sampled metadata"})
    write("official_pubmed_xml_identity_structure_snapshot.json", {
        "authority_boundary": "user-specified PubMed XML structural authority; verified against frozen raw responses offline, no live NCBI fetch",
        "primary_pmid_path": "PubmedArticle/MedlineCitation/PMID",
        "primary_external_ids_path": "PubmedArticle/PubmedData/ArticleIdList/ArticleId (direct children)",
        "reference_ids_path": "PubmedArticle/PubmedData/ReferenceList*/Reference/ArticleIdList/ArticleId",
        "reference_ids_are_not_current_article_identity": True})
    parser_ref = ref(ROOT / "scripts/search_plan_v24_alpha318a5_primary_identity.py")
    binding = {"schema_version": "PubMedPrimaryCitationIdentityBindingV1",
        "expected_identity": "frozen sampled PMID", "binding_path": "PubmedArticle/MedlineCitation/PMID",
        "exactly_one_matching_pubmed_article_required": True,
        "missing_code": "PRIMARY_CITATION_RECORD_MISSING", "duplicate_code": "PRIMARY_CITATION_RECORD_DUPLICATE",
        "direct_pubmed_id_mismatch_code": "PRIMARY_CITATION_PMID_IDENTITY_MISMATCH",
        "primary_article_id_path": "PubmedArticle/PubmedData/ArticleIdList/ArticleId",
        "article_id_list_must_be_direct_child_of_pubmed_data": True,
        "reference_list_identity_contribution": False, "batch_record_order_authority": False,
        "parser": parser_ref}
    write("pubmed_primary_citation_identity_binding_v1.json", binding)
    binding_sha = sha_marker("pubmed_primary_citation_identity_binding_v1_sha256",
        OUT / "pubmed_primary_citation_identity_binding_v1.json")
    write("primary_article_id_scope_contract.json", {"allowed_path": binding["primary_article_id_path"],
        "direct_child_only": True, "recursive_identity_extraction_used": False,
        "legacy_recursive_values_for_audit_only": True})
    write("reference_article_id_exclusion_contract.json", {"forbidden_identity_paths": [
        "PubmedData/ReferenceList//ArticleId", "PubmedData/ReferenceList//PMID",
        "Reference/ArticleIdList/ArticleId", "Reference/PMID"],
        "reference_ids_counted_for_contamination_audit_only": True})
    write("primary_pmid_binding_contract.json", {"canonical_pmid_path": binding["binding_path"],
        "direct_pubmed_article_id_if_present_must_match": True,
        "multiple_article_response_bound_by_pmid_not_order": True})
    write("primary_pmcid_extraction_contract.json", {"id_type": "pmc",
        "path": binding["primary_article_id_path"],
        "normalization": "unchanged exact frozen parser semantics: distinct value; PMC[1-9][0-9]*",
        "zero_or_multiple_distinct": "UNRESOLVED",
        "pmcid_alias_not_added": True})
    write("primary_doi_extraction_contract.json", {"id_type": "doi",
        "path": binding["primary_article_id_path"],
        "normalization": "unchanged exact frozen parser semantics: distinct value",
        "multiple_distinct": "UNRESOLVED", "reference_dois_excluded": True})
    write("valid_upstream_checkpoint_audit.json", checkpoint)
    write("sampled_metadata_raw_response_completeness_audit.json", raw_audit)
    write_rows("sampled_metadata_identity_replay_results.jsonl", ids)
    write("sampled_metadata_identity_replay_summary.json", {"expected_records": 72,
        "replayed_records": len(ids), "exact_primary_pmid_bindings": len(ids),
        "direct_single_pmcid_records": sum(len(row["direct_pmcid_values"]) == 1 for row in ids),
        "metadata_state_counts": dict(Counter(row["metadata_state"] for row in ids)),
        "primary_article_ids_direct_child_only": True,
        "reference_article_ids_excluded_from_primary_identity": True})
    write("legacy_vs_v1_identity_parser_comparison.json", {
        "comparison_is_technical_not_scientific": True,
        "legacy_apparent_pmcid_multiplicity_records": legacy_pmc,
        "corrected_direct_list_pmcid_multiplicity_records": direct_pmc,
        "legacy_apparent_doi_multiplicity_records": legacy_doi,
        "corrected_direct_list_doi_multiplicity_records": direct_doi,
        "reference_article_ids_excluded": reference_count,
        "source_records_whose_identifier_state_changes": changed})
    write_rows("sampled_source_metadata_records_v2.jsonl", result["metadata_rows"])
    meta_sha = sha_marker("sampled_source_metadata_records_v2_sha256",
        OUT / "sampled_source_metadata_records_v2.jsonl")
    write_rows("seen_source_replay_results.jsonl", result["seen_rows"])
    write_rows("publication_type_replay_results.jsonl", result["type_rows"])
    write_rows("correction_reference_replay_results.jsonl", result["correction_rows"])
    write_rows("post_metadata_pre_oa_source_manifest_v2.jsonl", result["pre_oa_rows"])
    pre_oa_sha = sha_marker("post_metadata_pre_oa_source_manifest_v2_sha256",
        OUT / "post_metadata_pre_oa_source_manifest_v2.jsonl")
    invalid_names = ["sampled_source_metadata_records.jsonl", "seen_source_overlap_audit.json",
        "correction_reference_eligibility_results.jsonl", "construction_pmc_eligibility_results.jsonl",
        "construction_fulltext_request_manifest.jsonl", "construction_fulltext_acquisition_results.jsonl",
        "construction_fulltext_failure_records.jsonl", "source_type_mechanical_eligibility_results.jsonl",
        "mechanical_source_exclusion_results.jsonl", "construction_evidence_document_manifest.jsonl",
        "construction_span_anchor_manifest.jsonl", "construction_source_manifest.jsonl",
        "construction_source_manifest_sha256", "proposition_builder_v2_request_manifest.jsonl",
        "proposition_builder_v2_request_manifest_sha256", "actual_builder_call_budget.json",
        "private_anchor_vault_source_manifest.jsonl", "builder_visibility_preflight_audit.json"]
    invalid_refs = [ref(SOURCE / name) for name in invalid_names if (SOURCE / name).is_file()]
    write("invalid_downstream_artifact_quarantine_v2.json", {
        "quarantine_code": "INVALID_DOWNSTREAM_DERIVATIVES_OF_METADATA_IDENTITY_DEFECT",
        "original_artifacts_physically_preserved": True, "not_authoritative_for_corrected_path": True,
        "invalid_artifact_refs": invalid_refs,
        "missing_named_artifacts": [name for name in invalid_names if not (SOURCE / name).is_file()]})
    old_oa = [ref(path) for directory in ("pmc_oa_raw_responses", "construction_fulltext_raw_responses",
        "construction_fulltext_canonical_jats") for path in sorted((SOURCE / directory).glob("*")) if path.is_file()]
    write("prior_oa_jats_response_quarantine.json", {"prior_response_refs": old_oa,
        "provenance_only": True, "consume_in_corrected_path": False,
        "future_identical_source_requires_new_frozen_continuation_request": True})
    write("builder_budget_unknown_audit.json", {"actual_builder_scientific_call_count": None,
        "state": "UNKNOWN", "old_reported_zero_authoritative": False,
        "until": ["OA verification", "JATS acquisition", "article-specific license",
            "source-type gate", "construction document", "span anchors", "final request manifest"]})
    write("metadata_resume_boundary.json", {"valid_reused": ["six source frames", "cross-stratum dedup",
        "deterministic 72-source sample", "raw PubMed metadata responses"],
        "offline_replayed": ["primary citation binding", "sampled metadata V2", "seen source",
            "Publication Type", "correction-reference preliminary eligibility"],
        "future_network_start": "PMC_OA_SUBSET_VERIFICATION",
        "future_network_then": "eligible PMC JATS acquisition",
        "six_source_queries_rerun": False, "sampled_metadata_refetched": False})
    future = {"schema_version": "Alpha318A5PostMetadataResumeExecutionManifestV3",
        "status": "EXECUTABLE_PROSPECTIVE_V3_PREREGISTRATION_FROZEN",
        "parent_v2_manifest": ref(v2.freeze.OUT / "alpha3_18a4_source_acquisition_execution_manifest_v2.json"),
        "primary_binding_contract": ref(OUT / "pubmed_primary_citation_identity_binding_v1.json"),
        "corrected_metadata_v2": ref(OUT / "sampled_source_metadata_records_v2.jsonl"),
        "post_metadata_pre_oa_selection": ref(OUT / "post_metadata_pre_oa_source_manifest_v2.jsonl"),
        "valid_upstream_checkpoint": ref(OUT / "valid_upstream_checkpoint_audit.json"),
        "raw_metadata_completeness": ref(OUT / "sampled_metadata_raw_response_completeness_audit.json"),
        "frozen_downstream_contracts": {key: value for key, value in frozen_v2_manifest.items()
            if key in ("frozen_amendment_bindings", "frozen_source_bindings", "builder_protocol",
                "builder_output_schema", "builder_request", "builder_visibility", "correction_gate",
                "correction_gate_code", "network_routes", "failure", "opaque_source_token",
                "source_admission", "builder_request_freeze")},
        "next_stage_network_routes": ["pmc_oa_subset", "pmc_jats"],
        "forbidden_reuse": ["old OA responses", "old JATS responses", "old downstream classifications"],
        "source_order": "frozen post_metadata_pre_oa_source_manifest_v2.jsonl order",
        "no_source_discovery_or_sampled_metadata_requests": True,
        "future_execution_requires_separate_authorization": True,
        "material_runtime_policy_unresolved_count": 0,
        "actual_builder_scientific_call_count": None}
    write("alpha3_18a5_post_metadata_resume_execution_manifest_v3.json", future)
    resume_sha = sha_marker("alpha3_18a5_post_metadata_resume_execution_manifest_v3_sha256",
        OUT / "alpha3_18a5_post_metadata_resume_execution_manifest_v3.json")
    write("final_resume_manifest_completeness_audit.json", {"all_references_hash_verified": all(
        digest(ROOT / item["path"]) == item["sha256"] for item in [future["parent_v2_manifest"],
            future["primary_binding_contract"], future["corrected_metadata_v2"],
            future["post_metadata_pre_oa_selection"], future["valid_upstream_checkpoint"],
            future["raw_metadata_completeness"]]),
        "material_runtime_policy_unresolved_count": 0,
        "resume_execution_manifest_executable": True,
        "network_execution_in_this_run": False})
    write("primary_identity_parser_regression_tests.json", {"test_file": ref(ROOT /
        "tests/test_search_plan_v24_alpha318a5_primary_identity.py"),
        "synthetic_cases": ["direct PMCID/reference PMCID", "direct DOI/reference DOIs",
            "matching direct PMID", "mismatching direct PMID", "many/nested references",
            "true direct PMCID ambiguity", "missing direct PMCID", "multi-article binding",
            "missing expected PMID", "duplicate expected PMID"],
        "repository_recursive_identity_search_audit": {"legacy_executor": "recursive and invalid; preserved historically",
            "failure_auditor": "recursive audit comparison only", "v3_binding_parser": "direct list identity only"}})
    write("real_72_record_replay_validation.json", {"expected": 72, "actual": len(ids),
        "all_expected_pmids_in_frozen_order": [row["pmid"] for row in result["metadata_rows"]] ==
        [row["pmid"] for row in sampled], "raw_response_reuse_only": True,
        "no_scientific_content_used_for_selection": True})
    write("historical_preservation_audit.json", {"historical_assets_modified": False,
        "original_v2_root_still_matches": failure_audit.run_root() == failure_audit.EXPECTED_RUN_ROOT,
        "independent_failure_audit_root_still_matches":
            BASE.prior.all_file_root(AUDIT, failure_audit.MARKER) == AUDIT_ROOT,
        "old_oa_jats_retained_as_provenance": True})
    write("scientific_state_safety_audit.json", {"network_calls": 0, "provider_calls": 0,
        "llm_calls": 0, "builder_calls": 0, "scientific_adjudication": False,
        "source_resampling": False, "source_discovery_rerun": False,
        "search_plan_tuning": False, "historical_assets_modified": False})
    write("validation.json", {"status": "PASS", "failure_code": None,
        "original_v2_failed_run_preserved": True, "valid_source_frames_reused": True,
        "valid_dedup_result_reused": True, "valid_72_source_sample_reused": True,
        "resampling_performed": False, "raw_sampled_metadata_reused": True,
        "primary_record_bound_by_medlinecitation_pmid": True,
        "primary_article_ids_direct_child_only": True,
        "recursive_article_id_identity_extraction_used": False,
        "reference_article_ids_excluded_from_primary_identity": True,
        "all_72_sampled_records_replayed": True, "metadata_identity_replay_complete": True,
        "seen_source_recomputed_from_corrected_identity": True,
        "publication_type_recomputed": True, "correction_reference_recomputed": True,
        "prior_invalid_oa_jats_downstream_quarantined": True,
        "actual_builder_call_count": None, "six_source_queries_rerun": False,
        "material_runtime_policy_unresolved_count": 0,
        "resume_execution_manifest_executable": True,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0})
    summary = {"status": "completed", "sampled_metadata_expected_records": 72,
        "sampled_metadata_replayed_records": len(ids),
        "legacy_pmcid_ambiguity_count": legacy_pmc,
        "corrected_pmcid_ambiguity_count": direct_pmc,
        "legacy_doi_ambiguity_count": legacy_doi,
        "corrected_doi_ambiguity_count": direct_doi,
        "reference_article_ids_excluded": reference_count,
        "source_records_whose_identifier_state_changes": changed,
        "post_metadata_pre_oa_source_count": len(result["pre_oa_rows"]),
        "seen_source_state_counts": dict(Counter(row["state"] for row in result["seen_rows"])),
        "publication_type_state_counts": dict(Counter(row["result"]["state"] for row in result["type_rows"])),
        "correction_reference_state_counts": dict(Counter(row["result"]["state"] for row in result["correction_rows"])),
        "actual_builder_scientific_call_count": None,
        "next_stage_recommendation": "AUTHORIZE_ALPHA3_18A_V3_POST_METADATA_NCBI_ONLY_CONTINUATION",
        "pubmed_primary_citation_identity_binding_v1_sha256": binding_sha,
        "sampled_source_metadata_records_v2_sha256": meta_sha,
        "post_metadata_pre_oa_source_manifest_v2_sha256": pre_oa_sha,
        "alpha3_18a5_post_metadata_resume_execution_manifest_v3_sha256": resume_sha}
    write("summary.json", summary)
    root = BASE.sha(BASE.canonical([[path.name, digest(path)] for path in sorted(OUT.iterdir()) if path.is_file()]))
    BASE.write_bytes(OUT / MARKER, (root + "\n").encode())
    print(json.dumps({"status": "completed", "root_sha256": root, **summary}, sort_keys=True))


if __name__ == "__main__":
    main()
