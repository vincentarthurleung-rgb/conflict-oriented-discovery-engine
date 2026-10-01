#!/usr/bin/env python3
"""Execute authorized alpha3.18A V3 continuation from the frozen 42-source list.

No source discovery, metadata fetching, model inference, or scientific review.
"""

from __future__ import annotations

import json
import re
import secrets
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts import search_plan_v24_alpha318a5_replay_primary_identity_offline as replay
    from scripts import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as base
    from scripts import search_plan_v24_alpha318a1_source_contracts as policy
    from scripts import search_plan_v24_alpha318a3_correction_reference as correction
except ModuleNotFoundError:
    import search_plan_v24_alpha318a5_replay_primary_identity_offline as replay
    import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as base
    import search_plan_v24_alpha318a1_source_contracts as policy
    import search_plan_v24_alpha318a3_correction_reference as correction


ROOT = replay.ROOT
OUT = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18a_v3_post_metadata_ncbi_continuation"
ROOT_MARKER = "search_plan_v24_dev_alpha3_18a_v3_sha256"
EXPECTED = {
    replay.MARKER: "6f1483beff3daef1bbec9b085c58c36f8420efa4a0c8a025b9470713f67e91d6",
    "pubmed_primary_citation_identity_binding_v1_sha256": "8cc569519a09f9a0f4dcd301c20bb0c006c1ab661454dcf4e9b81b6bede31335",
    "sampled_source_metadata_records_v2_sha256": "ee8498c5667074bb30f0879449376b5100115205bd74feb883236c757ed7d193",
    "post_metadata_pre_oa_source_manifest_v2_sha256": "a1f1a1954c754816fb3d2545848f95dc1af8f39f42aa11d0cfdfae9218e986d8",
    "alpha3_18a5_post_metadata_resume_execution_manifest_v3_sha256": "5756b6d7286974c2dfbf4ea02c337f34ac9f441d57fdde083f3e729e92f6c5ba",
}
CONTRACT_MARKERS = {
    "construction_oa_eligibility_v1_sha256": "c6104c806d46e324b604adaedccd47caf18cfe82f3a48b361bb425e121312c7b",
    "source_type_mechanical_eligibility_v1_sha256": "850ed1883860d3e83c5c071bb376112f157c6c3a0f7d9d9b78807cc26c3c714f",
    "construction_evidence_document_v1_sha256": "be3b6ca63c361a63430fffa3b2c99b6e57ec401eb287408715e9980dde030d70",
    "evidence_span_anchor_v1_sha256": "e29dfcbb6bd0d068d57d57799c29e590cc67d818cdfb1ebb26bebaec29de25f7",
}
BUILDER_MARKERS = {
    "proposition_builder_protocol_v2_sha256": "8a50314aac4e5f8017109a047905981a91aa91ffb784e1ebde0f92256917ba33",
    "proposition_builder_output_schema_v2_sha256": "5309d3edc9b8a40b64f6fc79e5f7a8e19ac4738808827b33cfe2eb3047db7849",
}


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


def _check_marker(directory: Path, name: str, expected: str) -> None:
    if (directory / name).read_text().strip() != expected:
        raise RuntimeError("FROZEN_MARKER_MISMATCH:" + name)


def _walk_refs(node: Any) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if isinstance(node, dict):
        if "path" in node and "sha256" in node:
            found.append(node)
        for value in node.values():
            found.extend(_walk_refs(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_walk_refs(value))
    return found


def preflight() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    if base.prior.all_file_root(replay.OUT, replay.MARKER) != EXPECTED[replay.MARKER]:
        raise RuntimeError("ALPHA3_18A5_ROOT_MISMATCH")
    for name, expected in EXPECTED.items():
        _check_marker(replay.OUT, name, expected)
    for name, filename in (("pubmed_primary_citation_identity_binding_v1_sha256",
                             "pubmed_primary_citation_identity_binding_v1.json"),
                            ("sampled_source_metadata_records_v2_sha256", "sampled_source_metadata_records_v2.jsonl"),
                            ("post_metadata_pre_oa_source_manifest_v2_sha256", "post_metadata_pre_oa_source_manifest_v2.jsonl"),
                            ("alpha3_18a5_post_metadata_resume_execution_manifest_v3_sha256",
                             "alpha3_18a5_post_metadata_resume_execution_manifest_v3.json")):
        if digest(replay.OUT / filename) != EXPECTED[name]:
            raise RuntimeError("FROZEN_FILE_HASH_MISMATCH:" + filename)
    amend_dir = base.prior.AMEND
    for name, expected in CONTRACT_MARKERS.items():
        _check_marker(amend_dir, name, expected)
    for name, expected in BUILDER_MARKERS.items():
        _check_marker(base.prior.BUILDER, name, expected)
    manifest = json.loads((replay.OUT / "alpha3_18a5_post_metadata_resume_execution_manifest_v3.json").read_text())
    if manifest["material_runtime_policy_unresolved_count"] != 0 or (
        manifest["status"] != "EXECUTABLE_PROSPECTIVE_V3_PREREGISTRATION_FROZEN"):
        raise RuntimeError("V3_RESUME_MANIFEST_NOT_EXECUTABLE")
    references = _walk_refs(manifest)
    for item in references:
        path = ROOT / item["path"]
        if not path.is_file() or path.is_symlink() or digest(path) != item["sha256"]:
            raise RuntimeError("V3_FROZEN_CONTRACT_REFERENCE_MISMATCH:" + item["path"])
    if manifest["next_stage_network_routes"] != ["pmc_oa_subset", "pmc_jats"] or (
        manifest["no_source_discovery_or_sampled_metadata_requests"] is not True):
        raise RuntimeError("V3_NETWORK_SCOPE_MISMATCH")
    # Re-check source-run and checkpoint integrity, without using any old OA/JATS bytes.
    replay.verify_roots()
    sampled, checkpoint = replay.verify_checkpoint()
    _, raw_audit = replay.load_raw_metadata(sampled)
    if raw_audit["complete_verified_raw_responses"] != 72:
        raise RuntimeError("CORRECTED_METADATA_CHECKPOINT_INCOMPLETE")
    corrected = replay.rows(replay.OUT / "sampled_source_metadata_records_v2.jsonl")
    pre_oa = replay.rows(replay.OUT / "post_metadata_pre_oa_source_manifest_v2.jsonl")
    if len(corrected) != 72 or len(pre_oa) != 42 or (
        [row["pmid"] for row in corrected] != [row["pmid"] for row in sampled]):
        raise RuntimeError("V3_STARTING_UNIVERSE_MISMATCH")
    corrected_by_pmid = {row["pmid"]: row for row in corrected}
    sampled_by_pmid = {row["pmid"]: row for row in sampled}
    if len({row["pmid"] for row in pre_oa}) != 42 or len({row["pmcid"] for row in pre_oa}) != 42:
        raise RuntimeError("V3_STARTING_UNIVERSE_DUPLICATE")
    for row in pre_oa:
        pmid = row["pmid"]
        meta_row = corrected_by_pmid.get(pmid)
        if pmid not in sampled_by_pmid or meta_row is None or meta_row["state"] != "RESOLVED":
            raise RuntimeError("V3_STARTING_UNIVERSE_NOT_IN_CORRECTED_SAMPLE")
        meta = meta_row["metadata"]
        if meta["pmcid"] != row["pmcid"] or meta["doi"] != row["doi"] or (
            meta_row["raw_sha256"] != row["raw_metadata_sha256"]):
            raise RuntimeError("V3_STARTING_UNIVERSE_IDENTITY_MISMATCH")
    seen = replay.rows(replay.OUT / "seen_source_replay_results.jsonl")
    types = replay.rows(replay.OUT / "publication_type_replay_results.jsonl")
    corrections = replay.rows(replay.OUT / "correction_reference_replay_results.jsonl")
    if any(len(group) != 72 for group in (seen, types, corrections)):
        raise RuntimeError("V3_METADATA_DEPENDENT_GATE_REPLAY_INCOMPLETE")
    by_seen = {row["pmid"]: row for row in seen}
    by_type = {row["pmid"]: row for row in types}
    by_correction = {row["pmid"]: row for row in corrections}
    for row in pre_oa:
        pmid = row["pmid"]
        if by_seen[pmid]["state"] != row["seen_source_state"] or (
            by_type[pmid]["result"]["state"] != row["preliminary_publication_type_state"] or
            by_correction[pmid]["result"]["state"] != row["correction_reference_preliminary_state"]):
            raise RuntimeError("V3_PRE_OA_GATE_RECORD_MISMATCH")
    return manifest, pre_oa, {"sampled": sampled_by_pmid, "corrected": corrected_by_pmid,
        "checkpoint": checkpoint, "reference_count": len(references)}


def _empty_state() -> dict[str, Any]:
    return {"oa_requests": [], "oa_results": [], "jats_requests": [], "jats_results": [],
        "jats_failures": [], "type_results": [], "documents": [], "anchors": [],
        "construction": [], "vault": [], "visibility": [], "builder_requests": [],
        "document_invalid": 0, "document_unresolved": 0,
        "source_terminal": {}, "source_tokens": {}}


def _verify_anchors(document: dict[str, Any], token: str) -> None:
    if document["schema_version"] != policy.SCHEMA_VERSION or (
        document["article_title_visible"] is not False or document["bibliography_visible"] is not False):
        raise ValueError("CONSTRUCTION_DOCUMENT_SCHEMA_OR_VISIBILITY_INVALID")
    body = document["body_text"]
    if not document["paragraphs"]:
        raise ValueError("EVIDENCE_ANCHORS_MISSING")
    for paragraph in document["paragraphs"]:
        if body[paragraph["start_offset"]:paragraph["end_offset"]] != paragraph["text"]:
            raise ValueError("EVIDENCE_SPAN_OFFSET_MISMATCH")
        expected = "spanv1_" + policy.digest([policy.SPAN_VERSION, token,
            paragraph["section_path"], paragraph["ordinal"], policy.sha_text(paragraph["text"])])
        if paragraph["span_id"] != expected:
            raise ValueError("EVIDENCE_SPAN_HASH_MISMATCH")


def _construct(pre_oa: list[dict[str, Any]], state: dict[str, Any], original: dict[str, Any],
               manifest: dict[str, Any], token_by_pmid: dict[str, str]) -> None:
    builder_protocol = base.prior.load(base.prior.BUILDER, "proposition_builder_protocol_v2.json")
    output_schema = base.prior.load(base.prior.BUILDER, "proposition_builder_output_schema_v2.json")["schema"]
    template = (base.prior.AMEND / "proposition_builder_v2_1_user_prompt_template.txt").read_text()
    system_prompt = builder_protocol["system_prompt_utf8"]
    for row in pre_oa:
        pmid = row["pmid"]
        result = next((x for x in state["oa_results"] if x["pmid"] == pmid), None)
        if result is None or result["state"] != "CONSTRUCTION_OA_ELIGIBLE":
            continue
        jats_path = OUT / result["canonical_jats_path"]
        jats = jats_path.read_bytes()
        meta = original["corrected"][pmid]["metadata"]
        type_decision = policy.source_type_state(meta["publication_types"], jats)
        state["type_results"].append({"pmid": pmid, "source_token": token_by_pmid[pmid],
            "state": type_decision["state"], "decision": type_decision})
        final_correction = correction.classify(meta["publication_types"],
            meta["correction_relationships"], type_decision["state"])
        if type_decision["state"] != "SOURCE_TYPE_ELIGIBLE" or (
            final_correction["state"] != "CORRECTION_REFERENCE_CLEAR"):
            state["source_terminal"][pmid] = {"state": "EXCLUDED_AFTER_SOURCE_TYPE_OR_CORRECTION",
                "source_type": type_decision["state"], "final_correction": final_correction["state"]}
            continue
        token = token_by_pmid[pmid]
        try:
            document = policy.build_construction_document(jats, token)
            parent = json.loads((ROOT / manifest["parent_v2_manifest"]["path"]).read_text())
            visibility = base.visible_audit(document, jats, meta, parent["queries"])
            if not visibility["pass"]:
                raise ValueError("BUILDER_VISIBILITY_FIREWALL_INCOMPLETE:" + ",".join(visibility["issues"]))
            _verify_anchors(document, token)
            visible_prompt = template.format(source_record_token=token,
                frozen_abstract=document["abstract_text"], frozen_body=document["body_text"],
                output_schema_json=json.dumps(output_schema, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
            for forbidden in (meta["pmid"], meta["pmcid"], meta["doi"]):
                if forbidden and re.search(r"(?<![A-Za-z0-9])" + re.escape(forbidden) + r"(?![A-Za-z0-9])",
                                           visible_prompt, re.I):
                    raise ValueError("BUILDER_VISIBLE_PRIMARY_IDENTITY")
            if "private_anchor_vault" in visible_prompt:
                raise ValueError("BUILDER_VISIBLE_ANCHOR_VAULT_PATH")
        except (ValueError, ET.ParseError, KeyError, IndexError) as exc:
            state["document_invalid"] += 1
            state["visibility"].append({"pmid": pmid, "source_token": token, "pass": False,
                "reason": str(exc)})
            state["source_terminal"][pmid] = {"state": "CONSTRUCTION_DOCUMENT_INVALID", "reason": str(exc)}
            continue
        doc_path = OUT / "construction_evidence_documents_v3" / f"{token}.json"
        base.write_json(doc_path, document)
        doc_sha = digest(doc_path)
        request = {"model": "deepseek-v4-pro", "thinking": {"type": "enabled"},
            "reasoning_effort": "high", "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": visible_prompt}]}
        sample = original["sampled"][pmid]
        state["documents"].append({"source_token": token, "document_path": str(doc_path.relative_to(OUT)),
            "document_sha256": doc_sha, "paragraph_count": len(document["paragraphs"])})
        state["anchors"].extend({"source_token": token, "span_id": p["span_id"],
            "section_path": p["section_path"], "ordinal": p["ordinal"],
            "text_sha256": policy.sha_text(p["text"]),
            "start_offset": p["start_offset"], "end_offset": p["end_offset"]}
            for p in document["paragraphs"])
        state["vault"].append({"access_class": "ANCHOR_RESTRICTED", "source_token": token,
            "pmid": pmid, "pmcid": row["pmcid"], "doi": row["doi"],
            "owner_stratum": sample["owner_stratum"], "all_strata": sample["all_strata"],
            "sample_rank_in_stratum": sample["sample_rank_in_stratum"],
            "corrected_metadata_sha256": row["raw_metadata_sha256"],
            "canonical_jats_sha256": sha(jats), "construction_document_sha256": doc_sha})
        state["construction"].append({"source_token": token, "stratum": sample["owner_stratum"],
            "sample_rank_in_stratum": sample["sample_rank_in_stratum"],
            "document_path": str(doc_path.relative_to(OUT)), "document_sha256": doc_sha})
        state["builder_requests"].append({"source_token": token, "request": request,
            "request_sha256": sha(base.canonical(request)), "document_sha256": doc_sha})
        state["visibility"].append({"source_token": token, "pass": True, "issues": []})
        state["source_terminal"][pmid] = {"state": "CONSTRUCTION_SOURCE_ELIGIBLE"}


def run_network(manifest: dict[str, Any], pre_oa: list[dict[str, Any]], original: dict[str, Any],
                transport: base.Transport, state: dict[str, Any]) -> None:
    tokens = {row["pmid"]: "src_" + secrets.token_hex(32) for row in pre_oa}
    if len(set(tokens.values())) != 42:
        raise RuntimeError("OPAQUE_SOURCE_TOKEN_COLLISION")
    state["source_tokens"] = tokens
    oa_requests = []
    for index, row in enumerate(pre_oa, 1):
        params = {"db": "pmc", "retmode": "json", "retmax": "1",
                  "term": policy.oa_subset_esearch_term(row["pmcid"])}
        oa_requests.append({"source_order": index, "source_token": tokens[row["pmid"]],
            "pmid": row["pmid"], "pmcid": row["pmcid"], "endpoint": base.ES, "parameters": params})
    state["oa_requests"] = oa_requests
    write_rows("oa_verification_request_manifest.jsonl", oa_requests)
    subset: dict[str, bool | None] = {}
    subset_attempts: dict[str, list[dict[str, Any]]] = {}
    for index, request in enumerate(oa_requests, 1):
        pmid = request["pmid"]
        key = f"{index:03d}_{pmid}"
        raw, attempts = transport.get("PMC_OA_SUBSET_V3", key, base.ES, request["parameters"],
            "oa_verification_raw_responses")
        subset[pmid] = base.parse_subset(raw, request["pmcid"]) if raw else None
        subset_attempts[pmid] = attempts
        print(json.dumps({"stage": "oa_subset", "processed": index, "total": 42,
            "state": subset[pmid]}), flush=True)
    jats_requests = [{"source_order": index, "source_token": tokens[row["pmid"]],
        "pmid": row["pmid"], "pmcid": row["pmcid"], "endpoint": base.EF,
        "parameters": {"db": "pmc", "retmode": "xml", "id": row["pmcid"][3:]}}
        for index, row in enumerate(pre_oa, 1) if subset[row["pmid"]] is True]
    state["jats_requests"] = jats_requests
    write_rows("pmc_jats_request_manifest_v3.jsonl", jats_requests)
    jats_results_by_pmid: dict[str, dict[str, Any]] = {}
    for index, request in enumerate(jats_requests, 1):
        pmid = request["pmid"]
        source_key = f"{request['source_order']:03d}_{pmid}"
        raw, attempts = transport.get("PMC_JATS_V3", source_key, base.EF, request["parameters"],
            "pmc_jats_raw_responses_v3")
        canonical: bytes | None = None
        failure: str | None = None
        if raw is None:
            failure = "TERMINAL_TRANSPORT_FAILURE"
        else:
            try:
                canonical = base.canonical_article(raw, request["pmcid"])
            except (ET.ParseError, ValueError) as exc:
                failure = str(exc)
        canonical_path = None
        if canonical is not None:
            path = OUT / "pmc_jats_canonical_xml_v3" / f"{source_key}.xml"
            base.write_bytes(path, canonical)
            canonical_path = str(path.relative_to(OUT))
        result = {"pmid": pmid, "pmcid": request["pmcid"],
            "source_token": tokens[pmid], "success": canonical is not None,
            "raw_sha256": sha(raw) if raw is not None else None,
            "canonical_jats_path": canonical_path,
            "canonical_jats_sha256": sha(canonical) if canonical is not None else None,
            "attempts": attempts, "failure": failure}
        state["jats_results"].append(result)
        jats_results_by_pmid[pmid] = result
        if failure:
            state["jats_failures"].append({"pmid": pmid, "pmcid": request["pmcid"],
                "source_token": tokens[pmid], "reason": failure, "attempts": attempts})
        print(json.dumps({"stage": "pmc_jats", "processed": index,
            "total": len(jats_requests), "success": canonical is not None}), flush=True)
    for row in pre_oa:
        pmid, pmcid = row["pmid"], row["pmcid"]
        jats_result = jats_results_by_pmid.get(pmid)
        canonical = (OUT / jats_result["canonical_jats_path"]).read_bytes() if (
            jats_result and jats_result["canonical_jats_path"]) else None
        decision = policy.construction_oa_state(pmcid, subset[pmid], canonical)
        result = {"pmid": pmid, "pmcid": pmcid, "source_token": tokens[pmid],
            "subset_result": subset[pmid], "subset_attempts": subset_attempts[pmid],
            "canonical_jats_path": jats_result["canonical_jats_path"] if jats_result else None,
            "state": decision["state"], "decision": decision}
        state["oa_results"].append(result)
        if decision["state"] != "CONSTRUCTION_OA_ELIGIBLE":
            state["source_terminal"][pmid] = {"state": decision["state"], "reason": decision["reason"]}
    _construct(pre_oa, state, original, manifest, tokens)


def finalize(status: str, failure_code: str | None, manifest: dict[str, Any],
             pre_oa: list[dict[str, Any]], original: dict[str, Any],
             transport: base.Transport, state: dict[str, Any]) -> str:
    for name, key in (("construction_oa_eligibility_results_v3.jsonl", "oa_results"),
                      ("pmc_jats_acquisition_results_v3.jsonl", "jats_results"),
                      ("pmc_jats_failure_records_v3.jsonl", "jats_failures"),
                      ("source_type_mechanical_eligibility_results_v3.jsonl", "type_results"),
                      ("construction_evidence_document_manifest_v3.jsonl", "documents"),
                      ("construction_span_anchor_manifest_v3.jsonl", "anchors"),
                      ("construction_source_manifest_v3.jsonl", "construction"),
                      ("private_anchor_vault_source_manifest_v3.jsonl", "vault"),
                      ("proposition_builder_v2_request_manifest_v3.jsonl", "builder_requests")):
        write_rows(name, state[key])
    (OUT / "private_anchor_vault_source_manifest_v3.jsonl").chmod(0o600)
    for name, value in (("construction_source_manifest_v3_sha256", "construction_source_manifest_v3.jsonl"),
                        ("proposition_builder_v2_request_manifest_v3_sha256",
                         "proposition_builder_v2_request_manifest_v3.jsonl")):
        marker(name, digest(OUT / value))
    write_rows("ncbi_transport_attempts_v3.jsonl", transport.log)
    if not (OUT / "oa_verification_request_manifest.jsonl").exists():
        write_rows("oa_verification_request_manifest.jsonl", state["oa_requests"])
    if not (OUT / "pmc_jats_request_manifest_v3.jsonl").exists():
        write_rows("pmc_jats_request_manifest_v3.jsonl", state["jats_requests"])
    oa_counts = Counter(row["state"] for row in state["oa_results"])
    type_counts = Counter(row["state"] for row in state["type_results"])
    count = len(state["construction"])
    if status == "PASS" and (len(state["oa_results"]) != 42 or len(state["source_terminal"]) != 42 or
        count != len(state["builder_requests"]) or count > 42):
        status, failure_code = "FAILED_CLOSED", "V3_COMPLETION_INVARIANT_FAILED"
    write("construction_oa_summary_v3.json", {"count": len(state["oa_results"]),
        "eligible": oa_counts["CONSTRUCTION_OA_ELIGIBLE"],
        "ineligible": oa_counts["CONSTRUCTION_OA_INELIGIBLE"],
        "unresolved": oa_counts["CONSTRUCTION_OA_UNRESOLVED"]})
    write("source_type_summary_v3.json", {"evaluated_count": len(state["type_results"]),
        "eligible": type_counts["SOURCE_TYPE_ELIGIBLE"],
        "ineligible": type_counts["SOURCE_TYPE_INELIGIBLE"],
        "unresolved": type_counts["SOURCE_TYPE_UNRESOLVED"],
        "not_evaluated_due_to_oa": 42 - len(state["type_results"])})
    write("construction_document_summary_v3.json", {"valid": len(state["documents"]),
        "invalid": state["document_invalid"], "unresolved": state["document_unresolved"]})
    write("builder_visibility_preflight_audit_v3.json", {"records": state["visibility"],
        "failed_count": sum(not x["pass"] for x in state["visibility"]),
        "identity_leakage_allowed": False,
        "builder_request_count": len(state["builder_requests"])})
    write("actual_builder_call_budget_v3.json", {"actual_builder_scientific_call_count": count if status == "PASS" else None,
        "construction_source_count": count, "builder_request_count": len(state["builder_requests"]),
        "maximum": 42, "builder_calls_executed": 0,
        "derived_from_complete_construction_source_manifest": status == "PASS"})
    write("source_phase_completion_barrier_v3.json", {"all_42_sources_terminal": len(state["source_terminal"]) == 42,
        "source_terminal_records": state["source_terminal"],
        "construction_source_manifest_frozen": True,
        "builder_request_manifest_frozen": True, "builder_calls_executed": 0})
    write("provenance_completeness_audit_v3.json", {"status": status,
        "pre_oa_sources": 42, "oa_records": len(state["oa_results"]),
        "jats_requests": len(state["jats_requests"]),
        "jats_results": len(state["jats_results"]),
        "raw_ncbi_attempts": transport.calls, "raw_attempts_preserved": len(transport.log) == transport.calls,
        "construction_sources": count, "private_vault_count": len(state["vault"])})
    write("development_nonuse_audit_v3.json", {"development_labels_used_for_source_selection": False,
        "known_pmid_recovery_checks": 0, "scientific_content_used_for_sampling": False,
        "source_universe_replaced": False})
    write("search_plan_firewall_audit_v3.json", {"search_plan_queries_executed": 0,
        "planner_calls": 0, "heldout_selected": 0, "P0_P1_P2_calls": 0,
        "source_discovery_queries_rerun": 0, "sampled_metadata_refetched": 0})
    write("protocol_compliance_audit_v3.json", {"status": status,
        "v3_resume_manifest_verified": True, "corrected_metadata_v2_verified": True,
        "post_metadata_pre_oa_source_count": 42, "six_source_queries_rerun": False,
        "sampled_metadata_refetched": False, "resampling_performed": False,
        "prior_invalid_oa_jats_reused": False, "oa_policy_modified": False,
        "license_policy_modified": False, "source_type_policy_modified": False,
        "construction_document_policy_modified": False, "anchor_policy_modified": False,
        "dynamic_source_replacement_used": False})
    safety = {"builder_calls": 0, "quality_calls": 0, "deepseek_calls": 0,
        "openai_calls": 0, "llm_calls": 0, "non_ncbi_network_calls": 0,
        "ncbi_network_attempts": transport.calls, "historical_assets_modified": False}
    write("scientific_state_safety_audit.json", safety)
    write("validation.json", {"status": status, "failure_code": failure_code,
        "v3_resume_manifest_verified": True, "corrected_metadata_v2_verified": True,
        "post_metadata_pre_oa_source_count": 42,
        "construction_source_manifest_frozen": True, "builder_request_manifest_frozen": True,
        "builder_request_count_matches_construction_source_count": count == len(state["builder_requests"]),
        "actual_builder_scientific_call_count_derived": status == "PASS",
        **safety})
    summary = {"status": "completed" if status == "PASS" else "failed", "failure_code": failure_code,
        "post_metadata_pre_oa_source_count": 42,
        "construction_oa_eligible": oa_counts["CONSTRUCTION_OA_ELIGIBLE"],
        "construction_oa_ineligible": oa_counts["CONSTRUCTION_OA_INELIGIBLE"],
        "construction_oa_unresolved": oa_counts["CONSTRUCTION_OA_UNRESOLVED"],
        "pmc_jats_requested": len(state["jats_requests"]),
        "pmc_jats_success": sum(x["success"] for x in state["jats_results"]),
        "pmc_jats_failed": sum(not x["success"] for x in state["jats_results"]),
        "source_type_eligible": type_counts["SOURCE_TYPE_ELIGIBLE"],
        "source_type_ineligible": type_counts["SOURCE_TYPE_INELIGIBLE"],
        "source_type_unresolved": type_counts["SOURCE_TYPE_UNRESOLVED"],
        "construction_document_valid": len(state["documents"]),
        "construction_document_invalid": state["document_invalid"],
        "construction_document_unresolved": state["document_unresolved"],
        "construction_source_count": count,
        "actual_builder_scientific_call_count": count if status == "PASS" else None,
        "builder_request_count": len(state["builder_requests"]),
        "ncbi_network_attempts": transport.calls,
        "construction_source_manifest_v3_sha256": digest(OUT / "construction_source_manifest_v3.jsonl"),
        "proposition_builder_v2_request_manifest_v3_sha256": digest(OUT /
            "proposition_builder_v2_request_manifest_v3.jsonl"),
        "next_stage_recommendation": "PREREGISTER_ALPHA3_18B_BUILDER_EXECUTION_AUTHORIZATION" if status == "PASS"
            else "AUDIT_ALPHA3_18A_V3_RUNTIME_FAILURE_OFFLINE"}
    write("summary.json", summary)
    root = sha(base.canonical([[str(path.relative_to(OUT)), digest(path)]
        for path in sorted(OUT.rglob("*")) if path.is_file() and path.name != ROOT_MARKER]))
    marker(ROOT_MARKER, root)
    return root


def main() -> None:
    if OUT.exists():
        raise RuntimeError("V3 continuation directory exists; no automatic rerun")
    manifest, pre_oa, original = preflight()
    OUT.mkdir()
    for dirname in ("oa_verification_raw_responses", "pmc_jats_raw_responses_v3",
                    "pmc_jats_canonical_xml_v3", "construction_evidence_documents_v3"):
        (OUT / dirname).mkdir()
    write("v3_resume_manifest_verification.json", {"v3_resume_manifest_sha256": EXPECTED[
        "alpha3_18a5_post_metadata_resume_execution_manifest_v3_sha256"],
        "alpha3_18a5_root_sha256": EXPECTED[replay.MARKER], "all_nested_contract_refs_verified": True,
        "reference_count": original["reference_count"], "verified_before_first_network_request": True})
    write("corrected_metadata_checkpoint_verification.json", {"corrected_metadata_sha256": EXPECTED[
        "sampled_source_metadata_records_v2_sha256"], "sampled_metadata_count": 72,
        "raw_metadata_reused": True, "metadata_refetches": 0,
        "six_source_frames_sha256": original["checkpoint"]["six_source_frames_sha256"]})
    write("post_metadata_pre_oa_manifest_verification.json", {"manifest_sha256": EXPECTED[
        "post_metadata_pre_oa_source_manifest_v2_sha256"], "source_count": 42,
        "all_sources_in_corrected_sample": True, "replacement": False})
    transport = base.Transport(OUT, base.prior.load(base.prior.SOURCE, "source_execution_policy.json"))
    state = _empty_state()
    try:
        run_network(manifest, pre_oa, original, transport, state)
        status, failure = "PASS", None
    except Exception as exc:
        status, failure = "FAILED_CLOSED", type(exc).__name__ + ":" + str(exc)
    root = finalize(status, failure, manifest, pre_oa, original, transport, state)
    print(json.dumps({"status": status, "failure_code": failure, "root_sha256": root,
        "ncbi_network_attempts": transport.calls, "construction_source_count":
        len(state["construction"])}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
