#!/usr/bin/env python3
"""Freeze alpha3.19E construction documents, BODY anchors, and Builder V3 requests."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from scripts import search_plan_v24_alpha319_master_preregister_offline as master
from scripts import search_plan_v24_alpha319a_preregister_source_acquisition_offline as prereg
from scripts import search_plan_v24_alpha318a1_source_contracts as policy
from scripts import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as historical
from scripts import search_plan_v24_alpha318a_v3_post_metadata_ncbi_continuation as anchors
from scripts import run_search_plan_v24_alpha319a2_full_six_frame_restart as a2
from scripts import run_search_plan_v24_alpha319b_dedup_seen_sampling_offline as b
from scripts import run_search_plan_v24_alpha319c_pubmed_metadata_eligibility as c
from scripts import run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility as d
from scripts import run_search_plan_v24_alpha319d1_updateof_resolution_offline as d1


ROOT = master.ROOT
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19e_construction_document_anchor_builder_freeze_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_19e_sha256"
MASTER_SHA = "1cf1d29d67474996a6ee87b518af0f09456e3572a3969b5a5f1b6021009ed73b"
A2_SHA = "64b7db6eb803b6464a11876bec2b868eaade5fdcbc7e6eada69a5e675ad7480c"
B_SHA = "7b409cd2bf35b01f7d511717cafa7f030ca0a0b351ec41a6a7e75cd31f5aa1f8"
C_SHA = "922cc952e03bca7e8605971b9dcb6f4acfe3cfbe02e308ca26c9ab37c3a86689"
D_SHA = "422975cb0706f19a6ee2640bc126fc49892d2e220df34b3f6c25c5a57a5b9a33"
D1_SHA = "2914e34c003aa8aa7a4949e4a276f68fb11b81b3f77f8796a7fb7469f5a0a545"
SOURCE_CONTRACT_DIR = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_18a1_source_contract_resolution_offline"
V3_DIR = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18b1_grounding_contract_consistency_audit_offline"
BUILDER_PROTOCOL_DIR = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17c_builder_cardinality_reconciliation_offline"
DOC_CONTRACT_SHA = "0928aa53cbbd0795c607e5342b383b88972680ef4b788bce9280eb47bf66fe57"
ANCHOR_CONTRACT_SHA = "8da77b28943c7e009c8b818302b4df7f793464e2cba81bc86b8ef7e51fe5d6c0"
V3_CONTRACT_SHA = "25d52f9ef10f3226e6003bcca46aa5d6a664b2b47bf7052db255a19da124e497"
V3_SCHEMA_SHA = "092961a96fe2985633054b68760cd409780e7e44fbfb2c5cd14c12ed9a51e326"
IMPLEMENTATION_SHA = "88c4370ebe45c157f9501ea1c7e6350f0348d67a15463254be68d8c315546c5e"
MODEL = "deepseek-flash"


def require(ok: bool, reason: str):
    if not ok:
        raise RuntimeError(reason)


def load(path: Path):
    return json.loads(path.read_bytes())


def rows(path: Path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def ref(path: Path):
    return {"path": str(path.relative_to(ROOT)), "sha256": master.digest(path)}


def write_json(name: str, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(master.canonical(value) + b"\n")


def write_jsonl(name: str, values):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        for value in values:
            handle.write(master.canonical(value) + b"\n")


def write_bytes(name: str, value: bytes):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(value)


def marker(name: str, value: str):
    write_bytes(name, (value + "\n").encode())


def root_hash():
    paths = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != ROOT_MARKER)
    require(not any(path.is_symlink() for path in OUT.rglob("*")), "OUTPUT_SYMLINK_FORBIDDEN")
    return master.sha(master.canonical([[str(path.relative_to(OUT)), master.digest(path)]
                                      for path in paths]))


def verify_root(directory: Path, marker_name: str, expected: str, calculate):
    require(calculate() == expected and (directory / marker_name).read_text().strip() == expected,
            "UPSTREAM_ROOT_MISMATCH:" + marker_name)


def preflight():
    require(not OUT.exists(), "ALPHA319E_OUTPUT_ALREADY_EXISTS_NO_RERUN")
    require(prereg.frozen_root(master.OUT, "search_plan_v24_dev_alpha3_19_master_prereg_sha256") ==
            MASTER_SHA and
            (master.OUT / "search_plan_v24_dev_alpha3_19_master_prereg_sha256").read_text().strip() ==
            MASTER_SHA, "MASTER_PREREG_ROOT_MISMATCH")
    verify_root(a2.OUT, a2.ROOT_MARKER, A2_SHA, a2.root_hash)
    verify_root(b.OUT, b.ROOT_MARKER, B_SHA, b.root_hash)
    verify_root(c.OUT, c.ROOT_MARKER, C_SHA, c.root_hash)
    verify_root(d.OUT, d.ROOT_MARKER, D_SHA, d.root_hash)
    verify_root(d1.OUT, d1.ROOT_MARKER, D1_SHA, d1.root_hash)
    final_path = d1.OUT / "final_construction_source_manifest.jsonl"
    source_rows = rows(final_path)
    final_states = rows(d1.OUT / "final_construction_eligibility_states.jsonl")
    d_jats = rows(d.OUT / "pmc_jats_terminal_states.jsonl")
    jats_by_pmid = {row["pmid"]: row for row in d_jats}
    metadata = rows(c.OUT / "sampled_metadata_records_v3.jsonl")
    metadata_by_pmid = {row["pmid"]: row for row in metadata}
    summary_d1 = load(d1.OUT / "summary.json")
    require(len(source_rows) == len({row["pmid"] for row in source_rows}) == 15 and
            len({row["opaque_source_token"] for row in source_rows}) == 15 and
            [row["sample_ordinal"] for row in source_rows] ==
                sorted(row["sample_ordinal"] for row in source_rows) and
            summary_d1["final_construction_source_count"] == 15 and
            summary_d1["final_construction_manifest_sha256"] == master.digest(final_path) and
            len(final_states) == 42 and
            sum(row["construction_eligibility_state"] == "CONSTRUCTION_SOURCE_ELIGIBLE"
                for row in final_states) == 15 and
            len(metadata_by_pmid) == 72 and len(jats_by_pmid) == 42,
            "FINAL_FIFTEEN_SOURCE_UNIVERSE_MISMATCH")
    excluded = [row for row in final_states
                if row["construction_eligibility_state"] != "CONSTRUCTION_SOURCE_ELIGIBLE"]
    require(len(excluded) == 27 and
            not {row["pmid"] for row in excluded} & {row["pmid"] for row in source_rows},
            "EXCLUDED_SOURCE_FIREWALL_FAILED")
    require(sum(row["terminal_state"] == "JATS_FAILED_NO_REPLACEMENT" for row in d_jats) == 1 and
            not {row["pmid"] for row in d_jats
                 if row["terminal_state"] == "JATS_FAILED_NO_REPLACEMENT"} &
                {row["pmid"] for row in source_rows},
            "HISTORICAL_JATS_FAILURE_FIREWALL_FAILED")
    doc_path = SOURCE_CONTRACT_DIR / "construction_evidence_document_v1_contract.json"
    anchor_path = SOURCE_CONTRACT_DIR / "evidence_span_anchor_v1_contract.json"
    v3_path = V3_DIR / "builder_grounding_contract_v3.json"
    schema_path = V3_DIR / "builder_output_schema_v3.json"
    doc_contract, anchor_contract = load(doc_path), load(anchor_path)
    v3_contract, schema = load(v3_path), load(schema_path)
    builder_protocol = load(BUILDER_PROTOCOL_DIR / "proposition_builder_protocol_v2.json")
    master_binding = load(master.OUT / "alpha3_19_builder_contract_binding.json")
    amendment = load(SOURCE_CONTRACT_DIR / "builder_request_visibility_amendment.json")
    template_path = SOURCE_CONTRACT_DIR / "proposition_builder_v2_1_user_prompt_template.txt"
    template = template_path.read_text()
    require(master.digest(doc_path) == DOC_CONTRACT_SHA and
            master.digest(anchor_path) == ANCHOR_CONTRACT_SHA and
            master.digest(v3_path) == V3_CONTRACT_SHA and
            master.digest(schema_path) == V3_SCHEMA_SHA and
            master.digest(ROOT / "scripts/search_plan_v24_alpha318a1_source_contracts.py") ==
                doc_contract["implementation_sha256"] == anchor_contract["implementation_sha256"] ==
                IMPLEMENTATION_SHA and
            doc_contract["schema_version"] == "ConstructionEvidenceDocumentV1" and
            doc_contract["body_only_candidate_grounding"] is True and
            doc_contract["article_title_visible"] is False and
            doc_contract["bibliography_visible"] is False and
            anchor_contract["schema_version"] == "EvidenceSpanAnchorV1" and
            anchor_contract["anchor_generation"] ==
                "after canonical body truncation; paragraph-level" and
            v3_contract["schema_version"] == "BuilderGroundingContractV3" and
            v3_contract["abstract_admissible_as_candidate_evidence"] is False and
            v3_contract["body_admissible_as_candidate_evidence"] is True and
            v3_contract["candidate_cardinality"] == {"minimum": 0, "maximum": 3} and
            v3_contract["model_grounding_reference"] ==
                "source_field=body + exact_text + zero-based offsets" and
            schema["artifact_schema_version"] == "PropositionBuilderOutputV3" and
            schema["protocol_version"] == "BuilderGroundingContractV3" and
            schema["schema"]["properties"]["candidates"]["items"]["properties"][
                "construction_evidence_span"]["properties"]["source_field"]["enum"] == ["body"] and
            schema["schema"]["properties"]["candidates"]["minItems"] == 0 and
            schema["schema"]["properties"]["candidates"]["maxItems"] == 3 and
            master_binding["contract"]["sha256"] == V3_CONTRACT_SHA and
            master_binding["model"] == MODEL and master_binding["provider"] == "DeepSeek" and
            master_binding["thinking"] == "enabled" and
            master_binding["reasoning_effort"] == "high" and
            master_binding["source_field"] == "body" and
            master_binding["builder_v2_interface_allowed"] is False and
            master.digest(template_path) == amendment["new_template_sha256"] and
            amendment["required_additional_instruction"] ==
                "Candidate evidence must use source_field=body and exact offsets into frozen "
                "canonical body_text; do not use abstract-only grounding." and
            builder_protocol["system_prompt_sha256"] ==
                master.sha(builder_protocol["system_prompt_utf8"].encode()),
            "FROZEN_BUILDER_CONTRACT_OR_PROMPT_MISMATCH")
    queries = master.rows(prereg.OUT / "alpha3_19_source_query_set.jsonl")
    require(len(queries) == 6 and master.digest(prereg.OUT / "alpha3_19_source_query_set.jsonl") ==
            a2.QUERY_SHA, "SOURCE_QUERY_FIREWALL_BINDING_MISMATCH")
    return {"sources": source_rows, "states": final_states, "excluded": excluded,
            "jats": jats_by_pmid, "metadata": metadata_by_pmid, "queries": queries,
            "doc_contract": doc_contract, "anchor_contract": anchor_contract,
            "v3_contract": v3_contract, "schema": schema,
            "builder_protocol": builder_protocol, "master_binding": master_binding,
            "template": template, "amendment": amendment}


def source_jats_binding(state, source):
    pmid, pmcid, token = source["pmid"], source["pmcid"], source["opaque_source_token"]
    jats = state["jats"][pmid]
    metadata = state["metadata"][pmid]
    path = d.OUT / source["normalized_jats_path"]
    raw_path = d.OUT / source["raw_jats_path"]
    require(re.fullmatch(r"src_[0-9a-f]{64}", token) and
            re.fullmatch(r"PMC[1-9][0-9]*", pmcid) and
            jats["terminal_state"] == "JATS_CANONICALIZED" and
            source["pmcid"] == jats["pmcid"] == metadata["pmcid"] and
            source["opaque_source_token"] == jats["opaque_source_token"] and
            source["normalized_jats_sha256"] == jats["normalized_jats_sha256"] ==
                master.digest(path) and
            source["raw_jats_sha256"] == jats["raw_jats_sha256"] == master.digest(raw_path) and
            source["raw_metadata_sha256"] == metadata["raw_xml_sha256"] and
            source["construction_eligibility_state"] == "CONSTRUCTION_SOURCE_ELIGIBLE" and
            source["builder_ready"] is True and
            source["source_type_state"] == "SOURCE_TYPE_ELIGIBLE" and
            source["license_state"] == "ELIGIBLE" and
            source["oa_subset_state"] == "OA_SUBSET_ELIGIBLE" and
            source["updateof_deferred_unresolved"] is False,
            "SOURCE_JATS_OR_ELIGIBILITY_BINDING_MISMATCH")
    return {"sample_ordinal": source["sample_ordinal"], "pmid": pmid, "pmcid": pmcid,
        "opaque_source_token": token, "raw_jats_path": source["raw_jats_path"],
        "raw_jats_sha256": source["raw_jats_sha256"],
        "canonical_jats_path": source["normalized_jats_path"],
        "canonical_jats_sha256": source["normalized_jats_sha256"],
        "raw_metadata_sha256": source["raw_metadata_sha256"],
        "jats_request_attempts": jats["request_attempts"],
        "construction_eligibility_state": source["construction_eligibility_state"],
        "alpha3_19d_root_sha256": D_SHA, "alpha3_19d1_root_sha256": D1_SHA,
        "binding_verified": True}


def request_payload(token, document, schema, system_prompt, template):
    schema_json = json.dumps(schema["schema"], sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"))
    user = template.format(source_record_token=token,
        frozen_abstract=document["abstract_text"], frozen_body=document["body_text"],
        output_schema_json=schema_json)
    return {"model": MODEL, "thinking": {"type": "enabled"},
        "reasoning_effort": "high", "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user}]}


def request_visibility(request, source, document, queries):
    rendered = master.canonical(request).decode()
    issues = []
    for key in ("pmid", "pmcid", "doi"):
        value = source.get(key)
        if value and re.search(r"(?<![A-Za-z0-9])" + re.escape(value) + r"(?![A-Za-z0-9])",
                               rendered, re.I):
            issues.append(key.upper() + "_IN_REQUEST")
    if re.search(r"/home/vincent/|\bruns/|file://|private_anchor_vault", rendered, re.I):
        issues.append("PRIVATE_PATH_IN_REQUEST")
    if "spanv1_" in request["messages"][1]["content"]:
        issues.append("ANCHOR_ID_IN_MODEL_USER_MESSAGE")
    if any(row["query_utf8"] in rendered for row in queries):
        issues.append("SEARCH_QUERY_IN_REQUEST")
    if re.search(r"\bheldout_v[0-9]+_|SearchConstraintAllocationV1|BoundedLexicalRealizationV2|"
                 r"\bP[012]\s*(?:gate|policy)\b|\b(?:DIRECTLY_RELEVANT|WRONG_ENTITY)\b",
                 rendered, re.I):
        issues.append("SEARCH_OR_DEVELOPMENT_STATE_IN_REQUEST")
    if request["messages"][1]["content"].count("Body: " + document["body_text"]) != 1:
        issues.append("BODY_NOT_EXACTLY_ONCE_VISIBLE")
    if document["abstract_text"] and (
        request["messages"][1]["content"].count("Abstract: " + document["abstract_text"]) != 1):
        issues.append("ABSTRACT_CONTEXT_MISMATCH")
    return {"source_token": source["opaque_source_token"], "pass": not issues,
            "issues": issues, "article_front_identity_fields_rendered": False,
            "body_visible": True, "abstract_context_only": True,
            "private_provenance_path_visible": False}


def prepare(state):
    documents, anchors_manifest, anchor_validation = [], [], []
    doc_results, anchor_results, terminal, binding, request_results, requests, visibility = (
        [], [], [], [], [], [], [])
    protocol = state["builder_protocol"]
    schema = state["schema"]
    system_prompt = (protocol["system_prompt_utf8"] +
        state["amendment"]["required_additional_instruction"] + "\n")
    require(system_prompt.startswith(protocol["system_prompt_utf8"]) and
            system_prompt.count(state["amendment"]["required_additional_instruction"]) == 1,
            "BUILDER_V3_SCIENTIFIC_PROMPT_DRIFT")
    for source in state["sources"]:
        token, pmid = source["opaque_source_token"], source["pmid"]
        binding.append(source_jats_binding(state, source))
        jats_bytes = (d.OUT / source["normalized_jats_path"]).read_bytes()
        metadata = state["metadata"][pmid]
        try:
            document = policy.build_construction_document(jats_bytes, token)
            visible = historical.visible_audit(document, jats_bytes, metadata, state["queries"])
            if not visible["pass"]:
                raise ValueError("FROZEN_DOCUMENT_VISIBILITY_FAILURE:" + ",".join(visible["issues"]))
        except (ValueError, ET.ParseError, KeyError, IndexError) as exc:
            reason = type(exc).__name__ + ":" + str(exc)
            doc_results.append({"source_token": token, "pmid": pmid,
                "state": "CONSTRUCTION_DOCUMENT_INVALID", "reason": reason,
                "document_path": None, "document_sha256": None})
            anchor_results.append({"source_token": token, "pmid": pmid,
                "state": "NOT_GENERATED_CONSTRUCTION_DOCUMENT_INVALID", "anchor_count": 0,
                "reason": reason})
            terminal.append({"source_token": token, "pmid": pmid,
                "sample_ordinal": source["sample_ordinal"],
                "state": "CONSTRUCTION_DOCUMENT_INVALID", "reason": reason})
            request_results.append({"source_token": token, "pmid": pmid,
                "state": "NOT_GENERATED_CONSTRUCTION_DOCUMENT_INVALID", "request_sha256": None})
            continue
        doc_name = f"construction_evidence_documents/{token}.json"
        write_json(doc_name, document)
        doc_hash = master.digest(OUT / doc_name)
        documents.append({"source_token": token, "document_path": doc_name,
            "document_sha256": doc_hash, "paragraph_count": len(document["paragraphs"]),
            "body_length": len(document["body_text"]),
            "abstract_context_only": True, "body_only_grounding": True})
        doc_results.append({"source_token": token, "pmid": pmid,
            "state": "CONSTRUCTION_DOCUMENT_VALID", "reason": None,
            "document_path": doc_name, "document_sha256": doc_hash})
        source_anchors = []
        try:
            anchors._verify_anchors(document, token)
            for paragraph in document["paragraphs"]:
                start, end = paragraph["start_offset"], paragraph["end_offset"]
                text = paragraph["text"]
                require(0 <= start < end <= len(document["body_text"]) and
                        document["body_text"][start:end] == text and
                        policy.resolve_candidate_span(document, "body", start, end, text) ==
                            paragraph["span_id"], "BODY_ANCHOR_EXACT_TEXT_OR_OFFSET_INVALID")
                entry = {"source_token": token, "document_sha256": doc_hash,
                    "span_id": paragraph["span_id"], "source_field": "body",
                    "section_path": paragraph["section_path"],
                    "section_headings": paragraph["section_headings"],
                    "paragraph_kind": paragraph["kind"],
                    "paragraph_ordinal": paragraph["ordinal"],
                    "start_offset": start, "end_offset": end,
                    "text_sha256": policy.sha_text(text)}
                source_anchors.append(entry)
        except (ValueError, KeyError, IndexError, RuntimeError) as exc:
            reason = type(exc).__name__ + ":" + str(exc)
            anchor_results.append({"source_token": token, "pmid": pmid,
                "state": "NO_VALID_BODY_GROUNDING_SURFACE", "anchor_count": 0,
                "reason": reason})
            terminal.append({"source_token": token, "pmid": pmid,
                "sample_ordinal": source["sample_ordinal"],
                "state": "NO_VALID_BODY_GROUNDING_SURFACE", "reason": reason})
            request_results.append({"source_token": token, "pmid": pmid,
                "state": "NOT_GENERATED_NO_VALID_BODY_GROUNDING_SURFACE", "request_sha256": None})
            continue
        if not source_anchors:
            anchor_results.append({"source_token": token, "pmid": pmid,
                "state": "NO_VALID_BODY_GROUNDING_SURFACE", "anchor_count": 0,
                "reason": "FROZEN_BODY_PARAGRAPHS_EMPTY"})
            terminal.append({"source_token": token, "pmid": pmid,
                "sample_ordinal": source["sample_ordinal"],
                "state": "NO_VALID_BODY_GROUNDING_SURFACE", "reason": "FROZEN_BODY_PARAGRAPHS_EMPTY"})
            request_results.append({"source_token": token, "pmid": pmid,
                "state": "NOT_GENERATED_NO_VALID_BODY_GROUNDING_SURFACE", "request_sha256": None})
            continue
        anchors_manifest.extend(source_anchors)
        anchor_validation.extend({"source_token": token, "span_id": item["span_id"],
            "resolves": True, "offsets_in_bounds": True, "exact_text_hash_match": True,
            "allowed_body_paragraph": True, "bibliography_or_back_matter": False}
            for item in source_anchors)
        anchor_set_hash = master.sha(master.canonical(source_anchors))
        anchor_results.append({"source_token": token, "pmid": pmid,
            "state": "BODY_ANCHORS_VALID", "anchor_count": len(source_anchors),
            "body_anchor_set_sha256": anchor_set_hash})
        request = request_payload(token, document, schema, system_prompt, state["template"])
        vis = request_visibility(request, source, document, state["queries"])
        visibility.append(vis)
        if not vis["pass"]:
            reason = "BUILDER_REQUEST_VISIBILITY_FAILURE:" + ",".join(vis["issues"])
            terminal.append({"source_token": token, "pmid": pmid,
                "sample_ordinal": source["sample_ordinal"],
                "state": "OTHER_FROZEN_DETERMINISTIC_EXCLUSION", "reason": reason})
            request_results.append({"source_token": token, "pmid": pmid,
                "state": "NOT_GENERATED_VISIBILITY_FAILURE", "request_sha256": None})
            continue
        request_hash = master.sha(master.canonical(request))
        requests.append({"ordinal": len(requests) + 1,
            "sample_ordinal": source["sample_ordinal"], "source_token": token,
            "document_sha256": doc_hash, "body_anchor_set_sha256": anchor_set_hash,
            "builder_grounding_contract_version": "BuilderGroundingContractV3",
            "builder_output_schema_version": "PropositionBuilderOutputV3",
            "provider": "DeepSeek", "model": MODEL,
            "request": request, "request_sha256": request_hash})
        terminal.append({"source_token": token, "pmid": pmid,
            "sample_ordinal": source["sample_ordinal"],
            "state": "BUILDER_REQUEST_READY", "reason": None})
        request_results.append({"source_token": token, "pmid": pmid,
            "state": "BUILDER_REQUEST_FROZEN", "request_sha256": request_hash})
    require(len(binding) == len(doc_results) == len(anchor_results) == len(terminal) ==
            len(request_results) == 15 and len({row["source_token"] for row in terminal}) == 15,
            "FIFTEEN_SOURCE_TERMINAL_PREPARATION_BARRIER_FAILED")
    return {"binding": binding, "doc_results": doc_results, "documents": documents,
            "anchor_results": anchor_results, "anchors": anchors_manifest,
            "anchor_validation": anchor_validation, "terminal": terminal,
            "request_results": request_results, "requests": requests,
            "visibility": visibility, "system_prompt": system_prompt}


def freeze(state, built):
    write_json("alpha3_19d1_root_verification.json", {
        "alpha3_19d1_root_sha256": D1_SHA, "root_verified": d1.root_hash() == D1_SHA,
        "input_manifest": ref(d1.OUT / "final_construction_source_manifest.jsonl")})
    write_json("final_construction_source_manifest_verification.json", {
        "input_count": 15, "input_manifest": ref(d1.OUT / "final_construction_source_manifest.jsonl"),
        "order_rule": "ascending frozen sample_ordinal", "source_addition": False,
        "source_replacement": False, "source_topup": False, "resampling": False,
        "excluded_27_used": False, "failed_jats_source_repaired": False})
    write_jsonl("source_jats_binding_verification.jsonl", built["binding"])
    write_jsonl("construction_document_generation_results.jsonl", built["doc_results"])
    write_jsonl("construction_document_manifest.jsonl", built["documents"])
    doc_sha = master.digest(OUT / "construction_document_manifest.jsonl")
    marker("construction_document_manifest_sha256", doc_sha)
    write_jsonl("body_anchor_generation_results.jsonl", built["anchor_results"])
    write_jsonl("body_anchor_manifest.jsonl", built["anchors"])
    anchor_sha = master.digest(OUT / "body_anchor_manifest.jsonl")
    marker("body_anchor_manifest_sha256", anchor_sha)
    write_jsonl("body_anchor_validation.jsonl", built["anchor_validation"])
    write_jsonl("source_preparation_terminal_states.jsonl", built["terminal"])
    write_json("source_identity_firewall_audit.json", {
        "source_identity_leak_count": sum(not row["pass"] for row in built["visibility"]),
        "private_source_identity_fields_model_visible": False,
        "model_visible_opaque_source_record_token_only": True,
        "document_title_visible": False, "document_bibliography_visible": False,
        "authors_or_journal_front_metadata_rendered": False,
        "candidate_grounding_source_field": "body",
        "invalid_document_with_identifier_excluded_before_request": any(
            row["state"] == "CONSTRUCTION_DOCUMENT_INVALID" and
            "source identifier in model-visible construction evidence" in row["reason"]
            for row in built["doc_results"])})
    write_json("alpha3_18_contamination_nonuse_audit.json", {
        "alpha3_18_scientific_asset_reuse_count": 0,
        "historical_builder_candidate_or_quality_output_read": False,
        "historical_candidate_wording_used": False,
        "historical_protocols_only_reused_as_frozen_authority": True})
    write_json("search_plan_firewall_audit.json", {"search_plan_state_exposed": False,
        "queries_exposed": False, "retrieval_results_exposed": False,
        "direct_or_nondirect_labels_exposed": False, "p0_p1_p2_labels_exposed": False,
        "development_relevance_labels_exposed": False, "known_paper_ids_exposed": False,
        "query_strings_used_only_for_private_visibility_check": True})
    write_json("builder_grounding_contract_v3_binding.json", {
        "contract": ref(V3_DIR / "builder_grounding_contract_v3.json"),
        "version": "BuilderGroundingContractV3", "body_only_grounding": True,
        "abstract_context_only": True, "abstract_grounding_allowed": False,
        "candidate_cardinality": {"minimum": 0, "maximum": 3},
        "model_generated_span_id": False,
        "evidence_reference": "source_field=body + exact_text + zero-based offsets"})
    write_json("builder_output_schema_v3_binding.json", {
        "schema": ref(V3_DIR / "builder_output_schema_v3.json"),
        "version": "PropositionBuilderOutputV3", "source_field_enum": ["body"],
        "candidate_cardinality": {"minimum": 0, "maximum": 3}})
    write_json("builder_provider_binding_alpha3_19.json", {
        "provider": "DeepSeek", "model": MODEL, "thinking": {"type": "enabled"},
        "reasoning_effort": "high", "response_format": {"type": "json_object"},
        "api_surface": "Chat Completions", "temperature": "omitted", "top_p": "omitted",
        "one_independent_context_per_source": True, "one_request_per_ready_source": True,
        "automatic_retry": False, "repair_call": False, "provider_capability_call": False,
        "frozen_master_binding": ref(master.OUT / "alpha3_19_builder_contract_binding.json")})
    write_jsonl("builder_request_generation_results.jsonl", built["request_results"])
    write_jsonl("alpha3_19_builder_v3_request_manifest.jsonl", built["requests"])
    request_sha = master.digest(OUT / "alpha3_19_builder_v3_request_manifest.jsonl")
    marker("alpha3_19_builder_v3_request_manifest_sha256", request_sha)
    write_json("builder_request_visibility_audit.json", {"request_count": len(built["requests"]),
        "per_request": built["visibility"],
        "source_identity_leak_count": sum(not row["pass"] for row in built["visibility"]),
        "abstract_visible_for_context_only": True, "abstract_grounding_allowed": False,
        "body_visible": True, "body_anchor_ids_not_model_generated_or_sent": True,
        "all_requests_pass": all(row["pass"] for row in built["visibility"])})
    write_json("builder_request_scientific_drift_audit.json", {
        "scientific_task_text_unchanged": True,
        "frozen_system_prompt_sha256": state["builder_protocol"]["system_prompt_sha256"],
        "body_only_instruction_sha256": master.sha(
            state["amendment"]["required_additional_instruction"].encode()),
        "actual_system_prompt_sha256": master.sha(built["system_prompt"].encode()),
        "frozen_user_template": ref(SOURCE_CONTRACT_DIR /
            "proposition_builder_v2_1_user_prompt_template.txt"),
        "v3_output_schema": ref(V3_DIR / "builder_output_schema_v3.json"),
        "only_prospective_model_delta": MODEL,
        "source_content_used_to_modify_prompt": False,
        "candidate_cardinality_changed": False,
        "eligibility_threshold_changed": False})
    ready_count = sum(row["state"] == "BUILDER_REQUEST_READY" for row in built["terminal"])
    excluded_count = 15 - ready_count
    write_json("builder_call_budget.json", {
        "input_construction_sources": 15,
        "actual_future_builder_scientific_call_count": ready_count,
        "builder_request_ready_source_count": ready_count,
        "builder_request_excluded_source_count": excluded_count,
        "formula": "one independent future scientific inference per BUILDER_REQUEST_READY source",
        "candidate_count_not_inferred": True, "quality_group_count_not_inferred": True,
        "builder_scientific_inference_events_now": 0,
        "future_calls_authorized_by_this_freeze": False})
    barrier = {"all_15_source_preparation_states_frozen": True,
        "all_valid_construction_documents_frozen": True,
        "all_valid_body_anchor_sets_frozen": True,
        "all_builder_request_payloads_and_hashes_frozen": True,
        "request_manifest_sha256": request_sha,
        "construction_document_manifest_sha256": doc_sha,
        "body_anchor_manifest_sha256": anchor_sha,
        "builder_request_count": len(built["requests"]),
        "actual_future_builder_scientific_call_count": ready_count,
        "builder_requests_frozen_before_provider_access": True,
        "provider_calls_before_freeze": 0,
        "material_runtime_policy_unresolved_count": 0}
    write_json("all_builder_inputs_freeze_barrier.json", barrier)
    write_json("scientific_content_nonadaptation_audit.json", {
        "article_scientific_content_used_for_prompt_change": False,
        "article_scientific_content_used_for_cardinality_change": False,
        "article_scientific_content_used_for_eligibility_threshold_change": False,
        "article_scientific_content_used_for_source_order_change": False,
        "article_scientific_content_used_for_source_selection": False,
        "paragraphs_selected_by_semantics": False,
        "body_paragraphs_included_by_frozen_deterministic_rule_only": True})
    write_json("active_deepseek_model_audit.json", {"prospective_builder_provider": "DeepSeek",
        "prospective_runtime_model": MODEL,
        "all_builder_request_models": sorted({row["request"]["model"]
                                              for row in built["requests"]}),
        "historical_model_provenance_modified": False,
        "provider_capability_calls": 0})
    upstream = {"master_prereg_sha256": MASTER_SHA, "alpha3_19a2_sha256": A2_SHA,
        "alpha3_19b_sha256": B_SHA, "alpha3_19c_sha256": C_SHA,
        "alpha3_19d_sha256": D_SHA, "alpha3_19d1_sha256": D1_SHA}
    write_json("historical_preservation_audit.json", {
        "upstream_roots_before": upstream, "upstream_roots_verified_unchanged_after":
            prereg.frozen_root(master.OUT,
                "search_plan_v24_dev_alpha3_19_master_prereg_sha256") == MASTER_SHA and
            a2.root_hash() == A2_SHA and b.root_hash() == B_SHA and
            c.root_hash() == C_SHA and d.root_hash() == D_SHA and d1.root_hash() == D1_SHA,
        "historical_assets_modified": False,
        "failed_jats_source_repaired": False,
        "source_addition_or_replacement": False})
    write_json("scientific_state_safety_audit.json", {
        "network_calls": 0, "ncbi_calls": 0, "deepseek_calls": 0,
        "openai_calls": 0, "llm_calls": 0,
        "builder_scientific_inference_events": 0, "quality_calls": 0,
        "heldout_sampling": False, "construction_document_contract_changed": False,
        "source_queries_changed": False, "source_sampling_changed": False,
        "candidate_checks_executed": False,
        "historical_assets_modified": False})
    doc_valid = sum(row["state"] == "CONSTRUCTION_DOCUMENT_VALID" for row in built["doc_results"])
    source_with_body = sum(row["state"] == "BODY_ANCHORS_VALID" for row in built["anchor_results"])
    leak_count = sum(not row["pass"] for row in built["visibility"])
    complete = (len(built["terminal"]) == 15 and len(built["requests"]) == ready_count and
        0 <= ready_count <= 15 and leak_count == 0 and
        all(row["request_sha256"] == master.sha(master.canonical(row["request"])) and
            row["request"]["model"] == MODEL for row in built["requests"]) and
        all(row["source_field"] == "body" for row in built["anchors"]) and
        all(row["resolves"] and row["offsets_in_bounds"] and row["exact_text_hash_match"]
            for row in built["anchor_validation"]))
    next_stage = ("INTERPRET_ZERO_BUILDER_INPUT_AFTER_ALPHA3_19E" if complete and ready_count == 0
                  else "AUTHORIZE_EXACT_ALPHA3_19F_BUILDER_V3_CALLS" if complete
                  else "AUDIT_ALPHA3_19E_RUNTIME_OR_CONTRACT_FAILURE_OFFLINE")
    validation = {"status": "completed" if complete else "failed",
        "alpha3_19d1_root_verified": True,
        "input_construction_source_count": 15,
        "construction_documents_valid": doc_valid,
        "construction_documents_invalid": 15 - doc_valid,
        "sources_with_valid_body_grounding_surface": source_with_body,
        "sources_without_valid_body_grounding_surface": 15 - source_with_body,
        "builder_request_ready_source_count": ready_count,
        "builder_request_excluded_source_count": excluded_count,
        "builder_grounding": "BODY_ONLY", "builder_model": MODEL,
        "source_identity_leak_count": leak_count,
        "alpha3_18_scientific_asset_reuse_count": 0,
        "builder_request_manifest_frozen": True,
        "builder_request_count": len(built["requests"]),
        "actual_future_builder_scientific_call_count": ready_count,
        "builder_scientific_inference_events": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "quality_calls": 0,
        "construction_document_manifest_sha256": doc_sha,
        "body_anchor_manifest_sha256": anchor_sha,
        "alpha3_19_builder_v3_request_manifest_sha256": request_sha,
        "material_runtime_policy_unresolved_count": 0 if complete else 1,
        "next_stage_recommendation": next_stage,
        "historical_assets_modified": False,
        "all_builder_inputs_freeze_barrier_crossed": complete,
        "source_addition_used": False, "source_replacement_used": False,
        "construction_document_contract_changed": False,
        "body_only_grounding": True, "abstract_grounding_allowed": False,
        "builder_grounding_contract_v3_bound": True,
        "builder_output_schema_v3_bound": True,
        "builder_requests_frozen_before_provider_access": True,
        "search_plan_state_exposed": False}
    write_json("validation.json", validation)
    write_json("summary.json", {"status": validation["status"],
        "input_construction_sources": 15, "construction_documents_valid": doc_valid,
        "construction_documents_invalid": 15 - doc_valid,
        "body_anchor_count": len(built["anchors"]),
        "builder_request_count": len(built["requests"]),
        "actual_future_builder_scientific_call_count": ready_count,
        "builder_model": MODEL, "builder_scientific_inference_events": 0,
        "network_calls": 0, "quality_calls": 0,
        "material_runtime_policy_unresolved_count": validation[
            "material_runtime_policy_unresolved_count"],
        "next_stage_recommendation": next_stage,
        "construction_document_manifest_sha256": doc_sha,
        "body_anchor_manifest_sha256": anchor_sha,
        "alpha3_19_builder_v3_request_manifest_sha256": request_sha})
    marker(ROOT_MARKER, root_hash())
    print(json.dumps({"status": validation["status"],
        "source_count": 15, "documents_valid": doc_valid,
        "body_anchor_count": len(built["anchors"]),
        "request_count": len(built["requests"]),
        "future_builder_calls": ready_count,
        "root_sha256": (OUT / ROOT_MARKER).read_text().strip()}, sort_keys=True))


def main():
    state = preflight()
    OUT.mkdir()
    built = prepare(state)
    freeze(state, built)


if __name__ == "__main__":
    main()
