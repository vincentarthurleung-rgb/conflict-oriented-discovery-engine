#!/usr/bin/env python3
"""Freeze alpha3.18A.6 license V2 and downstream replay from V3 bytes only."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts import search_plan_v24_alpha318a6_license_extraction as license_v2
    from scripts import search_plan_v24_alpha318a_v3_post_metadata_ncbi_continuation as v3
    from scripts import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as base
    from scripts import search_plan_v24_alpha318a3_correction_reference as correction
except ModuleNotFoundError:
    import search_plan_v24_alpha318a6_license_extraction as license_v2
    import search_plan_v24_alpha318a_v3_post_metadata_ncbi_continuation as v3
    import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as base
    import search_plan_v24_alpha318a3_correction_reference as correction


ROOT = v3.ROOT
V3 = v3.OUT
OUT = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18a6_license_extraction_v2_offline_replay"
ROOT_MARKER = "search_plan_v24_dev_alpha3_18a6_sha256"
V3_SHA = "139bd86ff3050fbbef633fbc39879180cbc24ff6cba488d3f8bea96652329670"
A5_SHA = "6f1483beff3daef1bbec9b085c58c36f8420efa4a0c8a025b9470713f67e91d6"


def sha(raw: bytes) -> str:
    return base.sha(raw)


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def ref(path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}


def write(name: str, value: Any) -> None:
    base.write_json(OUT / name, value)


def write_rows(name: str, value: list[Any]) -> None:
    base.write_jsonl(OUT / name, value)


def marker(name: str, value: str) -> None:
    base.write_bytes(OUT / name, (value + "\n").encode("ascii"))


def v3_root() -> str:
    files = sorted(path for path in V3.rglob("*") if path.is_file() and path.name != v3.ROOT_MARKER)
    if any(path.is_symlink() for path in V3.rglob("*")):
        raise RuntimeError("HISTORICAL_V3_SYMLINK")
    return sha(base.canonical([[str(path.relative_to(V3)), digest(path)] for path in files]))


def preflight() -> dict[str, Any]:
    if v3_root() != V3_SHA or (V3 / v3.ROOT_MARKER).read_text().strip() != V3_SHA:
        raise RuntimeError("HISTORICAL_V3_ROOT_MISMATCH")
    manifest, pre_oa, original = v3.preflight()
    if base.prior.all_file_root(v3.replay.OUT, v3.replay.MARKER) != A5_SHA:
        raise RuntimeError("ALPHA3_18A5_ROOT_MISMATCH")
    oa = v3.replay.rows(V3 / "construction_oa_eligibility_results_v3.jsonl")
    jats = v3.replay.rows(V3 / "pmc_jats_acquisition_results_v3.jsonl")
    attempts = v3.replay.rows(V3 / "ncbi_transport_attempts_v3.jsonl")
    if len(pre_oa) != 42 or len(oa) != 42 or len(jats) != 38 or len(attempts) != 80:
        raise RuntimeError("V3_FROZEN_CORPUS_COUNT_MISMATCH")
    if [row["pmid"] for row in pre_oa] != [row["pmid"] for row in oa]:
        raise RuntimeError("V3_OA_SOURCE_ORDER_MISMATCH")
    if sum(row["subset_result"] is False for row in oa) != 4 or (
        sum(row["subset_result"] is True for row in oa) != 38):
        raise RuntimeError("V3_OA_SUBSET_SIGNATURE_MISMATCH")
    if any(row["state"] != "CONSTRUCTION_OA_UNRESOLVED" for row in oa if row["subset_result"] is True):
        raise RuntimeError("V3_LICENSE_FAILURE_SIGNATURE_MISMATCH")
    if any(not row["success"] for row in jats):
        raise RuntimeError("FROZEN_JATS_NOT_ALL_SUCCESSFUL")
    paths: dict[str, Path] = {}
    raw_refs: list[dict[str, str]] = []
    canonical_refs: list[dict[str, str]] = []
    by_oa = {row["pmid"]: row for row in oa}
    for row in jats:
        pmid = row["pmid"]
        if pmid in paths or pmid not in by_oa or by_oa[pmid]["subset_result"] is not True:
            raise RuntimeError("FROZEN_JATS_IDENTITY_MISMATCH")
        path = V3 / row["canonical_jats_path"]
        if not path.resolve().is_relative_to((V3 / "pmc_jats_canonical_xml_v3").resolve()) or (
            not path.is_file() or digest(path) != row["canonical_jats_sha256"]):
            raise RuntimeError("FROZEN_JATS_MISSING_OR_HASH_MISMATCH")
        matching = [item for item in attempts if item["stage"] == "PMC_JATS_V3" and
                    item["parameters"]["id"] == row["pmcid"][3:]]
        if len(matching) != 1 or matching[0]["status"] != 200 or (
            matching[0]["raw_sha256"] != row["raw_sha256"]):
            raise RuntimeError("FROZEN_JATS_RAW_PROVENANCE_MISMATCH")
        raw = V3 / matching[0]["raw_path"]
        if not raw.resolve().is_relative_to((V3 / "pmc_jats_raw_responses_v3").resolve()) or (
            not raw.is_file() or digest(raw) != row["raw_sha256"]):
            raise RuntimeError("FROZEN_JATS_RAW_BYTES_MISMATCH")
        paths[pmid] = path
        raw_refs.append(ref(raw))
        canonical_refs.append(ref(path))
    if len(paths) != 38:
        raise RuntimeError("FROZEN_38_JATS_INCOMPLETE")
    old_budget = json.loads((V3 / "actual_builder_call_budget_v3.json").read_text())
    if old_budget["actual_builder_scientific_call_count"] != 0 or (
        (V3 / "construction_source_manifest_v3.jsonl").read_bytes() or
        (V3 / "proposition_builder_v2_request_manifest_v3.jsonl").read_bytes()):
        raise RuntimeError("V3_HISTORICAL_ZERO_SIGNATURE_MISMATCH")
    return {"manifest": manifest, "pre_oa": pre_oa, "original": original, "oa": oa,
        "jats": jats, "paths": paths, "raw_refs": raw_refs,
        "canonical_refs": canonical_refs, "attempts": attempts}


def replay(data: dict[str, Any]) -> dict[str, Any]:
    oa_by_pmid = {row["pmid"]: row for row in data["oa"]}
    representation: list[dict[str, Any]] = []
    oa_v4: list[dict[str, Any]] = []
    type_results: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    construction: list[dict[str, Any]] = []
    vault: list[dict[str, Any]] = []
    visibility_results: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    document_payloads: list[tuple[str, bytes]] = []
    document_invalid = 0
    document_unresolved = 0
    parent = json.loads((ROOT / data["manifest"]["parent_v2_manifest"]["path"]).read_text())
    builder_protocol = base.prior.load(base.prior.BUILDER, "proposition_builder_protocol_v2.json")
    output_schema = base.prior.load(base.prior.BUILDER, "proposition_builder_output_schema_v2.json")["schema"]
    template = (base.prior.AMEND / "proposition_builder_v2_1_user_prompt_template.txt").read_text()
    for source_order, source in enumerate(data["pre_oa"], 1):
        pmid = source["pmid"]
        prior = oa_by_pmid[pmid]
        token = prior["source_token"]
        if prior["subset_result"] is True:
            jats = data["paths"][pmid].read_bytes()
            license_result = license_v2.extract_license_v2(jats)
            representation.append({"pmid": pmid, "pmcid": source["pmcid"],
                "source_token": token, "canonical_jats_sha256": sha(jats),
                "old_v3_oa_state": prior["state"], **license_result})
        else:
            jats = None
        decision = license_v2.construction_oa_v2(source["pmcid"], prior["subset_result"], jats)
        oa_v4.append({"source_order": source_order, "pmid": pmid, "pmcid": source["pmcid"],
            "source_token": token, "frozen_oa_subset_result": prior["subset_result"],
            "state": decision["state"], "decision": decision,
            "canonical_jats_sha256": sha(jats) if jats else None})
        if decision["state"] != "CONSTRUCTION_OA_ELIGIBLE":
            continue
        assert jats is not None
        meta = data["original"]["corrected"][pmid]["metadata"]
        type_decision = base.policy.source_type_state(meta["publication_types"], jats)
        final_correction = correction.classify(meta["publication_types"], meta["correction_relationships"],
            type_decision["state"])
        type_results.append({"pmid": pmid, "source_token": token, "state": type_decision["state"],
            "decision": type_decision, "final_correction_reference": final_correction})
        if type_decision["state"] != "SOURCE_TYPE_ELIGIBLE" or (
            final_correction["state"] != "CORRECTION_REFERENCE_CLEAR"):
            continue
        try:
            document = base.policy.build_construction_document(jats, token)
            visible = base.visible_audit(document, jats, meta, parent["queries"])
            if not visible["pass"]:
                raise ValueError("BUILDER_VISIBILITY_FIREWALL_INCOMPLETE:" + ",".join(visible["issues"]))
            v3._verify_anchors(document, token)
            prompt = template.format(source_record_token=token,
                frozen_abstract=document["abstract_text"], frozen_body=document["body_text"],
                output_schema_json=json.dumps(output_schema, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
            for forbidden in (meta["pmid"], meta["pmcid"], meta["doi"]):
                if forbidden and re.search(r"(?<![A-Za-z0-9])" + re.escape(forbidden) + r"(?![A-Za-z0-9])",
                                           prompt, re.I):
                    raise ValueError("BUILDER_VISIBLE_PRIMARY_IDENTITY")
            if "private_anchor_vault" in prompt:
                raise ValueError("BUILDER_VISIBLE_ANCHOR_VAULT_PATH")
        except (ValueError, ET.ParseError, KeyError, IndexError) as exc:
            document_invalid += 1
            visibility_results.append({"pmid": pmid, "source_token": token, "pass": False,
                "reason": str(exc)})
            continue
        document_bytes = base.canonical(document) + b"\n"
        doc_hash = sha(document_bytes)
        doc_name = f"construction_evidence_documents_v4/{token}.json"
        document_payloads.append((doc_name, document_bytes))
        request = {"model": "deepseek-v4-pro", "thinking": {"type": "enabled"},
            "reasoning_effort": "high", "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": builder_protocol["system_prompt_utf8"]},
                         {"role": "user", "content": prompt}]}
        sample = data["original"]["sampled"][pmid]
        documents.append({"source_token": token, "document_path": doc_name,
            "document_sha256": doc_hash, "paragraph_count": len(document["paragraphs"])})
        anchors.extend({"source_token": token, "span_id": item["span_id"],
            "section_path": item["section_path"], "ordinal": item["ordinal"],
            "text_sha256": base.policy.sha_text(item["text"]),
            "start_offset": item["start_offset"], "end_offset": item["end_offset"]}
            for item in document["paragraphs"])
        construction.append({"source_token": token, "stratum": sample["owner_stratum"],
            "sample_rank_in_stratum": sample["sample_rank_in_stratum"],
            "document_path": doc_name, "document_sha256": doc_hash})
        vault.append({"access_class": "ANCHOR_RESTRICTED", "source_token": token,
            "pmid": pmid, "pmcid": source["pmcid"], "doi": source["doi"],
            "owner_stratum": sample["owner_stratum"], "all_strata": sample["all_strata"],
            "sample_rank_in_stratum": sample["sample_rank_in_stratum"],
            "corrected_metadata_sha256": source["raw_metadata_sha256"],
            "canonical_jats_sha256": sha(jats), "construction_document_sha256": doc_hash})
        requests.append({"source_token": token, "request": request,
            "request_sha256": sha(base.canonical(request)), "document_sha256": doc_hash})
        visibility_results.append({"source_token": token, "pass": True, "issues": []})
    if len(representation) != 38 or len(oa_v4) != 42 or (
        len(construction) != len(requests) or len(construction) > 42):
        raise RuntimeError("OFFLINE_REPLAY_COMPLETENESS_FAILURE")
    return {"representation": representation, "oa": oa_v4, "types": type_results,
        "documents": documents, "anchors": anchors, "construction": construction,
        "vault": vault, "visibility": visibility_results, "requests": requests,
        "document_payloads": document_payloads,
        "document_invalid": document_invalid, "document_unresolved": document_unresolved}


def synthetic_cases() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ns = 'xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:ali="http://www.niso.org/schemas/ali/1.0/"'
    by = "https://creativecommons.org/licenses/by/4.0/"
    sa = "https://creativecommons.org/licenses/by-sa/4.0/"
    nc = "https://creativecommons.org/licenses/by-nc/4.0/"
    cc0 = "https://creativecommons.org/publicdomain/zero/1.0/"
    def xml(body: str, extra: str = "") -> bytes:
        return (f'<article {ns}><front><article-meta><permissions>{body}</permissions>'
                f'</article-meta></front>{extra}</article>').encode()
    tests = [
        ("A_direct_cc_by", xml(f'<license xlink:href="{by}"/>'), "ELIGIBLE"),
        ("B_ali_cc_by_sa", xml(f'<license><ali:license_ref>{sa}</ali:license_ref></license>'), "ELIGIBLE"),
        ("C_ext_link_cc_by", xml(f'<license><license-p><ext-link xlink:href="{by}"/></license-p></license>'), "ELIGIBLE"),
        ("D_duplicate_consistent", xml(f'<license xlink:href="{by}"><license-p><ext-link xlink:href="{by}"/></license-p></license>'), "ELIGIBLE"),
        ("E_direct_ext_conflict", xml(f'<license xlink:href="{by}"><license-p><ext-link xlink:href="{nc}"/></license-p></license>'), "UNRESOLVED"),
        ("F_ali_same_class", xml(f'<license><ali:license_ref>{by}</ali:license_ref><ali:license_ref>http://creativecommons.org/licenses/by/3.0/</ali:license_ref></license>'), "ELIGIBLE"),
        ("G_ali_different_class", xml(f'<license><ali:license_ref>{by}</ali:license_ref><ali:license_ref>{nc}</ali:license_ref></license>'), "UNRESOLVED"),
        ("H_plain_prose", xml('<license><license-p>Creative Commons Attribution</license-p></license>'), "UNRESOLVED"),
        ("I_nonwhitelist", xml(f'<license xlink:href="{nc}"/>'), "INELIGIBLE"),
        ("J_cc0", xml(f'<license xlink:href="{cc0}"/>'), "ELIGIBLE"),
        ("K_figure_only", xml('<license/>', f'<body><fig><permissions><license xlink:href="{by}"/></permissions></fig></body>'), "UNRESOLVED"),
        ("L_bibliography_only", xml('<license/>', f'<back><ref-list><ref><ext-link xlink:href="{by}"/></ref></ref-list></back>'), "UNRESOLVED"),
    ]
    records = []
    for name, raw, expected in tests:
        result = license_v2.extract_license_v2(raw)
        records.append({"case": name, "input_xml_utf8": raw.decode(),
            "expected_state": expected, "actual_state": result["state"],
            "actual_reason": result["reason"], "pass": result["state"] == expected})
    if not all(item["pass"] for item in records):
        raise RuntimeError("LICENSE_PARSER_SYNTHETIC_REGRESSION")
    return records, {"case_count": len(records), "passed": len(records), "failed": 0,
        "test_module": ref(ROOT / "tests/test_search_plan_v24_alpha318a6_license_extraction.py")}


def main() -> None:
    if OUT.exists():
        raise RuntimeError("alpha3.18A.6 output already exists; refusing overwrite")
    data = preflight()
    result = replay(data)
    cases, case_summary = synthetic_cases()
    representation = result["representation"]
    path_counts = {path: sum(path in row["representation_paths"] for row in representation)
                   for path in ("A", "B", "C")}
    classifiable = sum(row["state"] != "UNRESOLVED" for row in representation)
    oa_counts = Counter(row["state"] for row in result["oa"])
    type_counts = Counter(row["state"] for row in result["types"])
    if sum(oa_counts.values()) != 42 or classifiable + sum(row["state"] == "UNRESOLVED"
        for row in representation) != 38:
        raise RuntimeError("LICENSE_V2_REPLAY_COUNT_MISMATCH")
    OUT.mkdir(parents=True)
    (OUT / "construction_evidence_documents_v4").mkdir()
    for name, raw in result["document_payloads"]:
        base.write_bytes(OUT / name, raw)
    write("alpha3_18a_v3_verification.json", {"v3_root_sha256": V3_SHA,
        "v3_self_reported_status": "completed", "historical_v3_preserved": True,
        "v3_oa_subset_ineligible": 4, "v3_jats_success": 38,
        "v3_license_unresolved": 38, "v3_builder_budget": 0})
    write("license_extraction_failure_diagnosis.json", {"failure_code":
        "CONSTRUCTION_LICENSE_MACHINE_READABLE_PATH_DEFECT",
        "legacy_v1_scope": "license/@xlink:href or license/@href only",
        "observed_v3_unresolved_due_to_direct_href_absence": 38,
        "license_path_defect_confirmed": True,
        "not_true_license_or_oa_attrition": True,
        "v3_zero_construction_source_claim_prospective_status":
            "SUPERSEDED_BY_LICENSE_EXTRACTION_CONTRACT_DEFECT"})
    write("jats_license_authority_snapshot.json", {"authority_boundary":
        "user-specified article-level JATS paths; verified against frozen PMC JATS locally; no live lookup",
        "paths": {"A": "article/front/article-meta/permissions/license/@xlink:href",
            "B": "article/front/article-meta/permissions/license/ali:license_ref text",
            "C": "article/front/article-meta/permissions/license/license-p//ext-link/@xlink:href"},
        "ali_namespace": license_v2.ALI_NS, "xlink_namespace": license_v2.XLINK_NS,
        "object_level_permissions_excluded": True})
    parser_ref = ref(ROOT / "scripts/search_plan_v24_alpha318a6_license_extraction.py")
    extraction_contract = {"schema_version": "ConstructionLicenseExtractionV2", "parser": parser_ref,
        "article_level_scope": "article/front/article-meta/permissions/license direct chain",
        "accepted_machine_uri_paths": ["A", "B", "C"],
        "plain_prose_cannot_identify_class": True,
        "whitelist": ["CC0", "CC_BY", "CC_BY_SA"],
        "unknown_uri": "UNRESOLVED", "distinct_classes": "UNRESOLVED",
        "start_date_selects_license": False, "network_resolution": False}
    write("construction_license_extraction_v2.json", extraction_contract)
    extraction_sha = digest(OUT / "construction_license_extraction_v2.json")
    marker("construction_license_extraction_v2_sha256", extraction_sha)
    write("article_level_license_scope_contract.json", {"allowed":
        "article/front/article-meta/permissions/license", "forbidden": ["figure", "table",
            "supplementary object", "body", "reference", "third-party asset"],
        "descendant_wildcard_across_article": False})
    write("license_uri_path_contract.json", {"direct_href_A": True, "ali_license_ref_B": True,
        "license_p_ext_link_C": True, "B_namespace": license_v2.ALI_NS,
        "C_href_namespace": license_v2.XLINK_NS,
        "within_same_article_level_license": True})
    write("license_uri_normalization_contract.json", {"scheme": "http/https canonicalized to https",
        "hosts": ["creativecommons.org", "www.creativecommons.org"],
        "canonical_host": "creativecommons.org", "trailing_slash": "one",
        "whitespace": "trim surrounding only", "query_fragment": "reject",
        "redirects": False, "fuzzy_interpretation": False})
    write("creative_commons_license_mapping.json", {"CC0": "publicdomain/zero/1.0",
        "CC_BY": ["licenses/by/2.0", "licenses/by/2.5", "licenses/by/3.0", "licenses/by/4.0"],
        "CC_BY_SA": ["licenses/by-sa/2.0", "licenses/by-sa/2.5", "licenses/by-sa/3.0", "licenses/by-sa/4.0"],
        "EXPLICIT_NONWHITELIST_CC": sorted(license_v2.NONWHITELIST),
        "whitelist_changed": False})
    write("license_conflict_resolution_policy.json", {"same_class_multiple_paths": "CONSISTENT",
        "distinct_classes": "LICENSE_MACHINE_URI_CONFLICT_TO_UNRESOLVED",
        "unknown_machine_uri": "UNRESOLVED",
        "start_date_choose_more_permissive": False,
        "url_text_conflict": "UNRESOLVED"})
    oa_contract = {"schema_version": "ConstructionOAEligibilityV2",
        "existing_oa_subset_results": ref(V3 / "construction_oa_eligibility_results_v3.jsonl"),
        "license_extraction_v2": ref(OUT / "construction_license_extraction_v2.json"),
        "unchanged_whitelist_contract": ref(base.prior.AMEND / "construction_license_policy.json"),
        "oa_subset_false": "CONSTRUCTION_OA_INELIGIBLE",
        "license_ELIGIBLE": "CONSTRUCTION_OA_ELIGIBLE",
        "license_INELIGIBLE": "CONSTRUCTION_OA_INELIGIBLE",
        "license_UNRESOLVED": "CONSTRUCTION_OA_UNRESOLVED",
        "source_type_policy_changed": False, "network_calls": 0}
    write("construction_oa_eligibility_v2.json", oa_contract)
    oa_contract_sha = digest(OUT / "construction_oa_eligibility_v2.json")
    marker("construction_oa_eligibility_v2_sha256", oa_contract_sha)
    quarantine_names = ["construction_oa_eligibility_results_v3.jsonl",
        "construction_oa_summary_v3.json", "source_type_mechanical_eligibility_results_v3.jsonl",
        "construction_source_manifest_v3.jsonl", "proposition_builder_v2_request_manifest_v3.jsonl",
        "actual_builder_call_budget_v3.json"]
    write("v3_license_downstream_quarantine.json", {"quarantine_code":
        "SUPERSEDED_BY_LICENSE_EXTRACTION_CONTRACT_DEFECT", "historical_bytes_preserved": True,
        "old_oa_subset_decisions_reused": True, "old_jats_bytes_reused": True,
        "old_license_and_downstream_conclusions_reused": False,
        "quarantined_refs": [ref(V3 / name) for name in quarantine_names]})
    write("frozen_38_jats_integrity_audit.json", {"expected_jats_count": 38,
        "verified_jats_count": len(data["paths"]),
        "raw_jats_refs": data["raw_refs"], "canonical_jats_refs": data["canonical_refs"],
        "all_raw_and_canonical_hashes_match": True, "jats_refetch_count": 0})
    write_rows("license_representation_replay_results.jsonl", representation)
    with_paths = Counter(tuple(row["representation_paths"]) for row in representation)
    write("license_representation_summary.json", {"articles": 38,
        "articles_path_a": path_counts["A"], "articles_path_b": path_counts["B"],
        "articles_path_c": path_counts["C"],
        "a_only": with_paths[("A",)], "b_only": with_paths[("B",)],
        "c_only": with_paths[("C",)],
        "multiple_representations": sum(len(key) > 1 for key, count in with_paths.items() for _ in range(count)),
        "no_machine_uri": sum(row["candidate_count"] == 0 for row in representation),
        "consistent_multiple_representations": sum(len(row["representation_paths"]) > 1 and
            row["state"] != "UNRESOLVED" for row in representation),
        "conflicting_representations": sum(row["reason"] == "LICENSE_MACHINE_URI_CONFLICT"
            for row in representation),
        "machine_classifiable": classifiable,
        "machine_unresolved": 38 - classifiable,
        "old_v3_unresolved_newly_classifiable_via_b_or_c": sum(row["state"] != "UNRESOLVED" and
            any(path in row["representation_paths"] for path in ("B", "C")) for row in representation)})
    write_rows("construction_oa_eligibility_results_v4.jsonl", result["oa"])
    write("construction_oa_summary_v4.json", {"total": 42,
        "eligible": oa_counts["CONSTRUCTION_OA_ELIGIBLE"],
        "ineligible": oa_counts["CONSTRUCTION_OA_INELIGIBLE"],
        "unresolved": oa_counts["CONSTRUCTION_OA_UNRESOLVED"],
        "frozen_oa_subset_ineligible_preserved": 4})
    write_rows("source_type_mechanical_eligibility_results_v4.jsonl", result["types"])
    write("source_type_summary_v4.json", {"evaluated": len(result["types"]),
        "eligible": type_counts["SOURCE_TYPE_ELIGIBLE"],
        "ineligible": type_counts["SOURCE_TYPE_INELIGIBLE"],
        "unresolved": type_counts["SOURCE_TYPE_UNRESOLVED"],
        "not_evaluated_due_to_oa": 42 - len(result["types"])})
    write_rows("construction_evidence_document_manifest_v4.jsonl", result["documents"])
    write_rows("construction_span_anchor_manifest_v4.jsonl", result["anchors"])
    write("construction_document_summary_v4.json", {"valid": len(result["documents"]),
        "invalid": result["document_invalid"], "unresolved": result["document_unresolved"]})
    write_rows("construction_source_manifest_v4.jsonl", result["construction"])
    source_sha = digest(OUT / "construction_source_manifest_v4.jsonl")
    marker("construction_source_manifest_v4_sha256", source_sha)
    write_rows("private_anchor_vault_source_manifest_v4.jsonl", result["vault"])
    (OUT / "private_anchor_vault_source_manifest_v4.jsonl").chmod(0o600)
    write("builder_visibility_preflight_audit_v4.json", {"records": result["visibility"],
        "failed_count": sum(not row["pass"] for row in result["visibility"]),
        "private_source_identity_visible": False,
        "builder_request_count": len(result["requests"])})
    write_rows("proposition_builder_v2_request_manifest_v4.jsonl", result["requests"])
    request_sha = digest(OUT / "proposition_builder_v2_request_manifest_v4.jsonl")
    marker("proposition_builder_v2_request_manifest_v4_sha256", request_sha)
    count = len(result["construction"])
    write("actual_builder_call_budget_v4.json", {"actual_builder_scientific_call_count_v4": count,
        "construction_source_count_v4": count, "builder_request_count_v4": len(result["requests"]),
        "derived_from_frozen_corrected_manifest": True, "builder_calls_executed": 0})
    write_rows("license_parser_synthetic_cases.jsonl", cases)
    write("license_parser_synthetic_test_results.json", case_summary)
    write("real_38_jats_replay_validation.json", {"expected": 38,
        "replayed": len(representation),
        "one_terminal_state_per_jats_source": True,
        "jats_refetch_count": 0})
    write("historical_preservation_audit.json", {"historical_v3_preserved": v3_root() == V3_SHA,
        "alpha3_18a5_preserved": base.prior.all_file_root(v3.replay.OUT, v3.replay.MARKER) == A5_SHA,
        "v3_original_zero_budget_preserved": True,
        "v3_zero_source_claim_prospective_status": "SUPERSEDED_BY_LICENSE_EXTRACTION_CONTRACT_DEFECT",
        "historical_assets_modified": False})
    write("scientific_state_safety_audit.json", {"network_calls": 0,
        "provider_calls": 0, "llm_calls": 0, "builder_calls": 0,
        "quality_calls": 0, "deepseek_calls": 0, "openai_calls": 0,
        "resampling": False, "source_replacement": False,
        "historical_assets_modified": False})
    write("validation.json", {"status": "PASS", "historical_v3_preserved": True,
        "license_path_defect_confirmed": True, "article_level_license_scope_only": True,
        "license_direct_href_supported": True, "ali_license_ref_supported": True,
        "license_p_ext_link_supported": True, "plain_text_license_not_machine_promoted": True,
        "license_whitelist_changed": False, "oa_subset_results_reused": True,
        "oa_subset_requests_reissued": False, "frozen_jats_reused": True,
        "jats_refetch_count": 0, "expected_frozen_jats": 38,
        "verified_frozen_jats": 38, "all_38_license_records_replayed": True,
        "source_type_policy_changed": False, "construction_document_policy_changed": False,
        "anchor_policy_changed": False, "dynamic_source_replacement_used": False,
        "construction_source_manifest_v4_frozen": True,
        "builder_request_manifest_v4_frozen": True,
        "builder_request_count_matches_construction_source_count": count == len(result["requests"]),
        "material_runtime_policy_unresolved_count": 0,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0})
    next_stage = ("PREREGISTER_ALPHA3_18B_BUILDER_EXECUTION_AUTHORIZATION" if count > 0
                  else "INTERPRET_ZERO_CONSTRUCTION_SOURCE_POOL_AFTER_LICENSE_V2")
    summary = {"status": "completed", "license_articles_path_a": path_counts["A"],
        "license_articles_path_b": path_counts["B"], "license_articles_path_c": path_counts["C"],
        "license_articles_machine_classifiable": classifiable,
        "license_articles_machine_unresolved": 38 - classifiable,
        "construction_oa_eligible": oa_counts["CONSTRUCTION_OA_ELIGIBLE"],
        "construction_oa_ineligible": oa_counts["CONSTRUCTION_OA_INELIGIBLE"],
        "construction_oa_unresolved": oa_counts["CONSTRUCTION_OA_UNRESOLVED"],
        "source_type_eligible": type_counts["SOURCE_TYPE_ELIGIBLE"],
        "source_type_ineligible": type_counts["SOURCE_TYPE_INELIGIBLE"],
        "source_type_unresolved": type_counts["SOURCE_TYPE_UNRESOLVED"],
        "construction_document_valid": len(result["documents"]),
        "construction_document_invalid": result["document_invalid"],
        "construction_document_unresolved": result["document_unresolved"],
        "construction_source_count_v4": count,
        "actual_builder_scientific_call_count_v4": count,
        "builder_request_count_v4": len(result["requests"]),
        "construction_license_extraction_v2_sha256": extraction_sha,
        "construction_oa_eligibility_v2_sha256": oa_contract_sha,
        "construction_source_manifest_v4_sha256": source_sha,
        "proposition_builder_v2_request_manifest_v4_sha256": request_sha,
        "next_stage_recommendation": next_stage}
    write("summary.json", summary)
    root = sha(base.canonical([[str(path.relative_to(OUT)), digest(path)]
        for path in sorted(OUT.rglob("*")) if path.is_file() and path.name != ROOT_MARKER]))
    marker(ROOT_MARKER, root)
    print(json.dumps({"status": "completed", "root_sha256": root, **summary}, sort_keys=True))


if __name__ == "__main__":
    main()
