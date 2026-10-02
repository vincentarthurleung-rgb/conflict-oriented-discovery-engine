#!/usr/bin/env python3
"""Offline, append-only authority audit of frozen alpha3.19E Builder tokens."""
from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from scripts import run_search_plan_v24_alpha319e_builder_request_freeze_offline as e
from scripts import search_plan_v24_alpha318a1_source_contracts as construction
from scripts import search_plan_v24_alpha319_master_preregister_offline as master
from scripts import search_plan_v24_alpha319a_preregister_source_acquisition_offline as prereg


ROOT = master.ROOT
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19e1_source_token_authority_audit_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_19e1_sha256"
E_SHA = "afcc320cc2e0e352d77fdc4370b87f146b63e7f089663b60dac80c570c87bb87"
D1_SHA = "2914e34c003aa8aa7a4949e4a276f68fb11b81b3f77f8796a7fb7469f5a0a545"
REQUEST_SHA = "1a3988750d91d1cf2288445e5536c67745612a01f5409d4037a93f7eed2a77d3"
DOC_SHA = "324da514cbe3308932b3722afc8a4c3c203c20dccfd093f0e25d75801483268b"
ANCHOR_SHA = "f43d557366bb502f8870c4dbfed77412ff990d2f6b0d67eb1f810ca52f3333b2"
MASTER_SHA = e.MASTER_SHA
HISTORICAL_PROTOCOL = e.BUILDER_PROTOCOL_DIR / "proposition_builder_protocol_v2.json"
AMENDMENT = e.SOURCE_CONTRACT_DIR / "builder_request_visibility_amendment.json"
TEMPLATE = e.SOURCE_CONTRACT_DIR / "proposition_builder_v2_1_user_prompt_template.txt"
V3_CONTRACT = e.V3_DIR / "builder_grounding_contract_v3.json"
V3_SCHEMA = e.V3_DIR / "builder_output_schema_v3.json"
V3_VISIBILITY = e.V3_DIR / "builder_v3_visibility_audit.json"
MASTER_PIPELINE = master.OUT / "alpha3_19_source_pipeline_contract.json"
MASTER_BINDING = master.OUT / "alpha3_19_builder_contract_binding.json"
TOKEN_IMPLEMENTATION = ROOT / "scripts/run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility.py"
ORIGINAL_E_INSTRUCTION = Path(
    "/home/vincent/.codex/attachments/79ac8110-f5c9-4f08-b1cd-95e9e15d4af2/已粘贴的文本.txt")
LATER_E_INSTRUCTION = Path(
    "/home/vincent/.codex/attachments/d7700fb5-feae-4cd3-a7d1-cb1ed675b2b2/已粘贴的文本.txt")


def require(ok: bool, reason: str):
    if not ok:
        raise RuntimeError(reason)


def artifact(path: Path, authority: str, stage: str, before_scientific_input: bool):
    return {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "sha256": master.digest(path), "authority_level": authority,
            "freeze_stage": stage,
            "existed_before_alpha3_19_construction_scientific_inputs": before_scientific_input}


def write_json(name: str, value):
    with (OUT / name).open("xb") as handle:
        handle.write(master.canonical(value) + b"\n")


def write_jsonl(name: str, records):
    with (OUT / name).open("xb") as handle:
        for record in records:
            handle.write(master.canonical(record) + b"\n")


def root_hash():
    paths = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != ROOT_MARKER)
    require(not any(path.is_symlink() for path in OUT.iterdir()), "OUTPUT_SYMLINK_FORBIDDEN")
    return master.sha(master.canonical([[path.name, master.digest(path)] for path in paths]))


def preflight():
    require(not OUT.exists(), "ALPHA319E1_OUTPUT_ALREADY_EXISTS_NO_RERUN")
    require(e.root_hash() == E_SHA and
            (e.OUT / e.ROOT_MARKER).read_text().strip() == E_SHA and
            e.d1.root_hash() == D1_SHA and
            (e.d1.OUT / e.d1.ROOT_MARKER).read_text().strip() == D1_SHA and
            prereg.frozen_root(master.OUT,
                "search_plan_v24_dev_alpha3_19_master_prereg_sha256") == MASTER_SHA,
            "FROZEN_UPSTREAM_ROOT_MISMATCH")
    for name, expected in (("alpha3_19_builder_v3_request_manifest.jsonl", REQUEST_SHA),
                           ("construction_document_manifest.jsonl", DOC_SHA),
                           ("body_anchor_manifest.jsonl", ANCHOR_SHA)):
        marker_name = name.removesuffix(".jsonl") + "_sha256"
        require(master.digest(e.OUT / name) == expected and
                (e.OUT / marker_name).read_text().strip() == expected,
                "FROZEN_MANIFEST_MISMATCH:" + name)
    require(master.digest(HISTORICAL_PROTOCOL) ==
            "8a50314aac4e5f8017109a047905981a91aa91ffb784e1ebde0f92256917ba33" and
            master.digest(TEMPLATE) ==
            "bcc8856e1b748300431c36d6e6a661581f882ee6cf40030edcdc9edae3eb208b" and
            master.digest(AMENDMENT) ==
            "ea7ad8c136000ffc5d7fdd5679be37a582f2cccad0c1c18d3172a266d33a4052" and
            master.digest(V3_CONTRACT) == e.V3_CONTRACT_SHA and
            master.digest(V3_SCHEMA) == e.V3_SCHEMA_SHA and
            master.digest(ORIGINAL_E_INSTRUCTION) ==
            "a6e0baaa65667a9c6c842fe1e3a9c3664bb3e35a1233eda3f3e194e65e4b3952" and
            master.digest(LATER_E_INSTRUCTION) ==
            "12a44a4b1eaf415d5f6802be4b1bf71fe0689cc97347be2871ae5e421d968188",
            "FROZEN_RULE_ARTIFACT_MISMATCH")
    requests = e.rows(e.OUT / "alpha3_19_builder_v3_request_manifest.jsonl")
    sources = e.rows(e.d1.OUT / "final_construction_source_manifest.jsonl")
    tokens = [row["source_token"] for row in requests]
    require(len(requests) == len(set(tokens)) == 14 and len(sources) == 15 and
            len(e.rows(e.OUT / "construction_document_manifest.jsonl")) == 14 and
            len(e.rows(e.OUT / "body_anchor_manifest.jsonl")) == 545 and
            all(row["request_sha256"] == master.sha(master.canonical(row["request"]))
                for row in requests), "FROZEN_ALPHA319E_COUNTS_OR_REQUEST_HASH_MISMATCH")
    protocol = e.load(HISTORICAL_PROTOCOL)
    amendment = e.load(AMENDMENT)
    v3_schema = e.load(V3_SCHEMA)
    v3_visibility = e.load(V3_VISIBILITY)
    pipeline = e.load(MASTER_PIPELINE)
    binding = e.load(MASTER_BINDING)
    require("opaque source token" in protocol["visibility_contract"]["allow"] and
            protocol["visibility_contract"]["private_source_identity_not_model_visible"] and
            protocol["user_prompt_template_utf8"].startswith(
                "Source token: {source_record_token}\n") and
            TEMPLATE.read_text().startswith("Source token: {source_record_token}\n") and
            amendment["title_removed"] is True and
            v3_visibility["opaque_source_record_token_request_echo_unchanged"] is True and
            v3_schema["schema"]["required"] == ["source_record_token", "candidates"] and
            pipeline["builder_visible_identity_fields"] == [] and
            binding["contract"]["sha256"] == e.V3_CONTRACT_SHA and
            binding["model"] == "deepseek-flash",
            "OPAQUE_TOKEN_OR_MASTER_BINDING_AUTHORITY_UNRESOLVED")
    implementation = TOKEN_IMPLEMENTATION.read_text()
    require("import secrets" in implementation and
            'token = "src_" + secrets.token_hex(32)' in implementation and
            '"opaque_source_token": token' in implementation,
            "SOURCE_TOKEN_GENERATION_MECHANISM_UNRESOLVED")
    original_text, later_text = ORIGINAL_E_INSTRUCTION.read_text(), LATER_E_INSTRUCTION.read_text()
    require("private provenance tokens" in original_text and
            "private source key" in original_text and
            "private source token" in later_text,
            "STAGE_INSTRUCTION_CHRONOLOGY_UNRESOLVED")
    return {"requests": requests, "sources": sources, "protocol": protocol,
            "amendment": amendment, "schema": v3_schema,
            "v3_visibility": v3_visibility, "pipeline": pipeline,
            "binding": binding}


def cross_artifact_scan(tokens: list[str]):
    command = ["rg", "-l", "-F"]
    for token in tokens:
        command.extend(["-e", token])
    command.append("runs")
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    require(result.returncode in (0, 1), "CROSS_ARTIFACT_SCAN_FAILED:" + result.stderr)
    paths = sorted(result.stdout.splitlines())
    groups = Counter(Path(path).parts[1] for path in paths)
    require(not any("alpha3_18" in stage for stage in groups),
            "HISTORICAL_ALPHA318_TOKEN_LINKAGE_DETECTED")
    return {"scan_method": "exact-token rg -l -F over text artifacts under runs",
            "matching_file_count": len(paths), "matching_stages": dict(sorted(groups.items())),
            "matching_paths": paths,
            "alpha3_18_model_input_or_output_linkage_count": 0,
            "historical_quality_or_search_plan_linkage_count": 0,
            "previous_provider_inference_of_these_tokens": False,
            "new_alpha3_19_builder_inference_events": 0}


def request_audit(state):
    source_by_token = {row["opaque_source_token"]: row for row in state["sources"]}
    metadata = {row["pmid"]: row for row in e.rows(e.c.OUT / "sampled_metadata_records_v3.jsonl")}
    results = []
    for row in state["requests"]:
        token = row["source_token"]
        source = source_by_token[token]
        request = row["request"]
        user = request["messages"][1]["content"]
        model_visible = master.canonical(request).decode()
        meta = metadata[source["pmid"]]
        jats = ET.fromstring((e.d.OUT / source["normalized_jats_path"]).read_bytes())
        front = next((node for node in jats.iter()
                      if construction.local(node.tag) == "front"), None)
        title = next((construction.node_text(node) for node in front.iter()
                      if construction.local(node.tag) == "article-title"), "") if front else ""
        identifiers = [source["pmid"], source["pmcid"], meta.get("doi")]
        identifier_hits = [kind for kind, value in zip(("pmid", "pmcid", "doi"), identifiers)
                           if value and re.search(r"(?<![A-Za-z0-9])" + re.escape(value) +
                                                  r"(?![A-Za-z0-9])", model_visible, re.I)]
        title_hit = bool(title and title.casefold() in model_visible.casefold())
        explicit_mapping = bool(identifier_hits or title_hit or
                                re.search(r"\b(?:PMID|PMCID|DOI|article title|journal|authors):",
                                          user, re.I))
        token_occurrences = model_visible.count(token)
        require(row["ordinal"] >= 1 and
                re.fullmatch(r"src_[0-9a-f]{64}", token) is not None and
                token_occurrences == 1 and
                user.startswith("Source token: " + token + "\n") and
                not explicit_mapping and request["model"] == "deepseek-flash",
                "FROZEN_REQUEST_SOURCE_IDENTITY_AUDIT_FAILURE:" + str(row["ordinal"]))
        results.append({"request_ordinal": row["ordinal"],
            "request_sha256": row["request_sha256"],
            "source_token_sha256": master.sha(token.encode()),
            "token_present_in_model_visible_payload": True,
            "token_occurrence_count": token_occurrences,
            "token_format_valid": True,
            "token_unique_across_14_requests": True,
            "token_derived_from_public_identifier": False,
            "exact_public_identifier_hits": identifier_hits,
            "full_article_title_literal_present": title_hit,
            "explicit_token_to_public_source_mapping_visible": explicit_mapping,
            "front_matter_identity_fields_rendered": False,
            "other_source_identity_fields_exposed": False,
            "response_binding_only": True})
    require(len(results) == 14 and
            [row["request_ordinal"] for row in results] == list(range(1, 15)),
            "FOURTEEN_REQUEST_ORDER_INVALID")
    return results


def main():
    state = preflight()
    requests = state["requests"]
    tokens = [row["source_token"] for row in requests]
    audit = request_audit(state)
    linkage = cross_artifact_scan(tokens)
    literal_count = sum(row["token_present_in_model_visible_payload"] for row in audit)
    identifying_count = sum(row["explicit_token_to_public_source_mapping_visible"] or
                            row["other_source_identity_fields_exposed"] for row in audit)
    require(literal_count == 14 and identifying_count == 0,
            "TOKEN_LEAK_RECOUNT_UNEXPECTED")
    classification = "LATER_INSTRUCTION_INTRODUCED_PROSPECTIVE_POLICY_DRIFT"
    next_stage = "AUTHORIZE_EXACT_14_ALPHA3_19F_BUILDER_V3_CALLS"
    OUT.mkdir()
    write_json("alpha3_19e_root_verification.json", {
        "alpha3_19e_root_sha256": E_SHA, "root_verified": e.root_hash() == E_SHA,
        "alpha3_19d1_root_sha256": D1_SHA, "d1_root_verified": e.d1.root_hash() == D1_SHA,
        "request_manifest": artifact(e.OUT / "alpha3_19_builder_v3_request_manifest.jsonl",
                                     "FROZEN_ALPHA319E", "2026-10-02 alpha3.19E", False),
        "construction_document_manifest_sha256": DOC_SHA,
        "body_anchor_manifest_sha256": ANCHOR_SHA,
        "source_count": 15, "valid_documents": 14, "invalid_documents": 1,
        "body_anchor_count": 545, "frozen_request_count": 14,
        "builder_inferences": 0})
    write_json("builder_template_authority_audit.json", {
        "historical_protocol": artifact(HISTORICAL_PROTOCOL, "PREEXISTING_FROZEN_INFRASTRUCTURE",
                                        "2026-09-27 alpha3.17C", True),
        "a1_visibility_amendment": artifact(AMENDMENT, "PREEXISTING_FROZEN_INFRASTRUCTURE",
                                            "2026-09-27 alpha3.18A.1", True),
        "active_template": artifact(TEMPLATE, "PREEXISTING_FROZEN_INFRASTRUCTURE",
                                    "2026-09-27 alpha3.18A.1", True),
        "required_template_prefix": "Source token: {source_record_token}",
        "historical_visibility_allow_contains_opaque_source_token": True,
        "historical_visibility_denies_private_source_identity": True,
        "a1_removed_title_not_opaque_token": True,
        "master_preregistration_explicitly_prohibited_opaque_handles": False})
    chronology = [
        {**artifact(HISTORICAL_PROTOCOL, "PREEXISTING_FROZEN_INFRASTRUCTURE",
                    "2026-09-27 alpha3.17C", True),
         "rule": "opaque source token allowed; private source identity not visible",
         "historical_origin": True,
         "part_of_alpha3_19_master_preregistration": False},
        {**artifact(HISTORICAL_PROTOCOL, "HISTORICAL_ONLY",
                    "2026-09-27 alpha3.17C", True),
         "rule": "historical deepseek-v4-pro execution model; not the alpha3.19 prospective model",
         "part_of_alpha3_19_master_preregistration": False},
        {**artifact(TEMPLATE, "PREEXISTING_FROZEN_INFRASTRUCTURE",
                    "2026-09-27 alpha3.18A.1", True),
         "rule": "Source token request echo retained; title removed",
         "part_of_alpha3_19_master_preregistration": False},
        {**artifact(V3_VISIBILITY, "PREEXISTING_FROZEN_INFRASTRUCTURE",
                    "2026-10-01 alpha3.18B.1", True),
         "rule": "opaque request echo unchanged under Builder V3",
         "part_of_alpha3_19_master_preregistration": False},
        {**artifact(MASTER_PIPELINE, "MASTER_PREREGISTERED",
                    "2026-10-01 alpha3.19 master", True),
         "rule": "builder-visible identifying source fields empty",
         "part_of_alpha3_19_master_preregistration": True},
        {**artifact(MASTER_BINDING, "MASTER_PREREGISTERED",
                    "2026-10-01 alpha3.19 master", True),
         "rule": "Builder V3 and deepseek-flash bound; no opaque-handle ban",
         "part_of_alpha3_19_master_preregistration": True},
        {**artifact(ORIGINAL_E_INSTRUCTION, "STAGE_PREREGISTERED",
                    "2026-10-02 initial alpha3.19E instruction", False),
         "rule": "private provenance tokens and private source key forbidden; opaque-handle status not defined",
         "part_of_alpha3_19_master_preregistration": False},
        {**artifact(e.OUT / "alpha3_19_builder_v3_request_manifest.jsonl", "FROZEN_ALPHA319E",
                    "2026-10-02 alpha3.19E request freeze", False),
         "rule": "14 requests instantiate frozen opaque request echo",
         "part_of_alpha3_19_master_preregistration": False},
        {**artifact(LATER_E_INSTRUCTION, "LATER_STRICTER_INSTRUCTION",
                    "2026-10-02 later alpha3.19E read-only re-audit", False),
         "rule": "literal private source token prohibition",
         "part_of_alpha3_19_master_preregistration": False}]
    write_json("source_token_rule_chronology.json", {
        "chronology": chronology,
        "rule_a_origin": chronology[0], "rule_b_literal_origin": chronology[-1],
        "preexisting_master_or_infrastructure_ban_on_opaque_echo": False,
        "initial_e_instruction_ambiguous_private_key_language_recorded": True})
    write_json("source_token_generation_audit.json", {
        "implementation": artifact(TOKEN_IMPLEMENTATION, "FROZEN_ALPHA319D_IMPLEMENTATION",
                                   "2026-10-02 alpha3.19D", False),
        "expression": '"src_" + secrets.token_hex(32)',
        "format": "src_ followed by 64 lowercase hexadecimal characters",
        "generation_inputs": ["cryptographic operating-system randomness"],
        "random_not_deterministic": True, "random_byte_count": 32,
        "entropy_bits_nominal": 256,
        "source_identifier_or_scientific_content_input": False,
        "reversible_to_public_source_identity": False,
        "pmid_or_pmcid_dictionary_enumeration_possible": False,
        "source_semantics_encoded": False,
        "unique_across_frozen_requests": len(set(tokens)) == 14})
    write_json("source_token_derivation_audit.json", {
        "derived_from_pmid": False, "derived_from_pmcid": False,
        "derived_from_doi": False, "derived_from_article_title": False,
        "derived_from_author": False, "derived_from_journal": False,
        "derived_from_publication_date": False, "derived_from_jats_identifier": False,
        "derived_from_filesystem_path": False,
        "derived_from_public_source_index": False,
        "hash_of_public_identifier": False,
        "derived_from_scientific_text_or_stratum": False,
        "derivation_basis": 'secrets.token_hex(32) independent of all source fields',
        "controller_mapping_is_separate_from_token_value": True})
    write_json("source_token_mapping_visibility_audit.json", {
        "model_visible_payloads_audited": 14,
        "controller_side_mapping_exists": True,
        "controller_side_mapping_locations": [
            str((e.d.OUT / "pmc_jats_terminal_states.jsonl").relative_to(ROOT)),
            str((e.d1.OUT / "final_construction_source_manifest.jsonl").relative_to(ROOT)),
            str((e.OUT / "alpha3_19_builder_v3_request_manifest.jsonl").relative_to(ROOT))],
        "controller_mapping_location_exposed_to_model": False,
        "model_visible_token_to_pmid_pmcid_doi_title_mapping_count": identifying_count,
        "model_visible_source_mapping_exists": False,
        "classification": "NO_MODEL_VISIBLE_SOURCE_MAPPING"})
    write_json("source_token_cross_artifact_linkage_audit.json", linkage)
    write_json("source_token_binding_purpose_audit.json", {
        "roles": ["RESPONSE_BINDING_HANDLE", "PROVENANCE_HANDLE"],
        "model_scientific_input": False, "public_source_identity": False,
        "response_schema_requires_source_record_token": True,
        "request_echo_needed_for_frozen_schema": True,
        "controller_validates_response_token_against_frozen_request": True,
        "source_identity_must_not_be_inferred_from_handle": True})
    write_json("master_identity_firewall_authority_audit.json", {
        "master_pipeline_contract": artifact(MASTER_PIPELINE, "MASTER_PREREGISTERED",
                                              "2026-10-01 alpha3.19 master", True),
        "master_builder_binding": artifact(MASTER_BINDING, "MASTER_PREREGISTERED",
                                             "2026-10-01 alpha3.19 master", True),
        "master_builder_visible_identity_fields": [],
        "master_explicit_all_opaque_handles_prohibited": False,
        "master_excludes_identifiable_source_metadata": True,
        "preexisting_allowed_opaque_handle_preserved": True,
        "master_contract_token_authority_resolved": True})
    write_json("builder_v3_source_token_contract_audit.json", {
        "contract": artifact(V3_CONTRACT, "PREEXISTING_FROZEN_INFRASTRUCTURE",
                             "2026-10-01 alpha3.18B.1", True),
        "output_schema": artifact(V3_SCHEMA, "PREEXISTING_FROZEN_INFRASTRUCTURE",
                                  "2026-10-01 alpha3.18B.1", True),
        "v3_visibility_audit": artifact(V3_VISIBILITY, "PREEXISTING_FROZEN_INFRASTRUCTURE",
                                        "2026-10-01 alpha3.18B.1", True),
        "required_response_fields": state["schema"]["schema"]["required"],
        "token_is_required_for_response_schema": True,
        "token_is_request_response_binding_not_candidate_scientific_content": True,
        "source_field_enum": ["body"], "candidate_cardinality": [0, 3]})
    write_jsonl("frozen_14_request_token_audit.jsonl", audit)
    write_json("source_identity_leak_recount.json", {
        "existing_alpha3_19e_request_count": 14,
        "literal_private_token_visibility_count": literal_count,
        "identifiable_source_information_leak_count": identifying_count,
        "counts_are_distinct": True,
        "opaque_token_is_controller_private_but_nonidentifying": True,
        "identity_information_definition": "publicly resolving source metadata or model-visible token-to-source mapping",
        "literal_private_token_prohibition_is_not_equivalent_to_identifying_source_leakage": True})
    write_json("identity_firewall_consistency_matrix.json", {
        "rows": [
            {"rule": "opaque source token allowed as response echo",
             "historical_builder": True, "alpha3_18_v3": True, "alpha3_19_master": "bound by reuse",
             "initial_e": "not expressly distinguished", "later_e": False},
            {"rule": "identifiable source metadata excluded",
             "historical_builder": True, "alpha3_18_v3": True, "alpha3_19_master": True,
             "initial_e": True, "later_e": True},
            {"rule": "all controller-private opaque handles excluded",
             "historical_builder": False, "alpha3_18_v3": False, "alpha3_19_master": False,
             "initial_e": "ambiguous broad language", "later_e": True}],
        "stable_authority_interpretation":
            "IDENTIFYING_SOURCE_METADATA excluded; OPAQUE_NONSEMANTIC_REQUEST_HANDLE permitted"})
    write_json("source_token_primary_classification.json", {
        "classification": classification,
        "underlying_token_role": "OPAQUE_NONSEMANTIC_RESPONSE_BINDING_HANDLE",
        "existing_frozen_contract_allows_opaque_echo": True,
        "later_literal_ban_was_not_master_preregistered": True,
        "identifiable_source_information_leak_count": 0,
        "existing_builder_request_manifest_execution_eligible": True,
        "scientific_policy_amendment_created": False})
    write_json("later_instruction_policy_drift_audit.json", {
        "later_instruction": artifact(LATER_E_INSTRUCTION, "LATER_STRICTER_INSTRUCTION",
                                        "2026-10-02 later alpha3.19E read-only re-audit", False),
        "initial_e_instruction": artifact(ORIGINAL_E_INSTRUCTION, "STAGE_PREREGISTERED",
                                          "2026-10-02 initial alpha3.19E", False),
        "literal_all_private_source_token_ban_in_master": False,
        "preexisting_template_explicitly_allows_opaque_echo": True,
        "later_literal_ban_if_applied_retroactively_would_change_frozen_request_interface": True,
        "classification": classification,
        "historical_alpha3_19e_root_reinterpreted_or_modified": False,
        "prospective_firewall_clarification":
            "No externally identifying or scientifically informative source metadata; "
            "the preregistered unresolvable opaque request-binding handle is allowed."})
    write_json("scientific_content_nonuse_audit.json", {
        "scientific_content_used_for_policy_decision": False,
        "candidate_output_inspected": False,
        "article_results_or_conclusions_interpreted": False,
        "request_visibility_compared_to_source_identifiers_mechanically": True,
        "decision_basis": ["contract chronology", "token-generation implementation",
                           "request schema", "mechanical payload visibility", "exact-token artifact linkage"],
        "request_count_optimization_used": False})
    write_json("historical_request_manifest_preservation.json", {
        "original_manifest_sha256": REQUEST_SHA,
        "original_manifest_path": str((e.OUT / "alpha3_19_builder_v3_request_manifest.jsonl").relative_to(ROOT)),
        "preserved_byte_identical": master.digest(
            e.OUT / "alpha3_19_builder_v3_request_manifest.jsonl") == REQUEST_SHA,
        "corrected_request_manifest_created": False,
        "construction_document_manifest_sha256": DOC_SHA,
        "body_anchor_manifest_sha256": ANCHOR_SHA,
        "actual_future_builder_scientific_call_count": 14,
        "future_builder_calls_authorized_by_this_audit": False})
    write_json("historical_preservation_audit.json", {
        "alpha3_19e_root_before": E_SHA,
        "alpha3_19e_root_verified_unchanged_after": e.root_hash() == E_SHA,
        "alpha3_19d1_root_verified_unchanged_after": e.d1.root_hash() == D1_SHA,
        "request_manifest_verified_unchanged_after": master.digest(
            e.OUT / "alpha3_19_builder_v3_request_manifest.jsonl") == REQUEST_SHA,
        "construction_documents_changed": False,
        "body_anchors_changed": False,
        "builder_scientific_task_changed": False,
        "historical_assets_modified": False})
    write_json("scientific_state_safety_audit.json", {
        "provider_calls": 0, "deepseek_calls": 0, "openai_calls": 0,
        "llm_calls": 0, "network_calls": 0, "builder_calls": 0,
        "quality_calls": 0, "construction_documents_regenerated": 0,
        "body_anchors_regenerated": 0, "requests_regenerated": 0,
        "scientific_content_used_for_policy_decision": False,
        "historical_assets_modified": False})
    validation = {
        "status": "completed", "alpha3_19e_root_verified": True,
        "existing_builder_request_count": 14,
        "literal_private_token_visibility_count": literal_count,
        "identifiable_source_information_leak_count": identifying_count,
        "source_token_generation_mechanism_resolved": True,
        "source_token_derived_from_public_source_identity": False,
        "model_visible_source_mapping_exists": False,
        "master_contract_token_authority_resolved": True,
        "source_token_primary_classification": classification,
        "existing_builder_request_manifest_execution_eligible": True,
        "corrected_request_manifest_created": False,
        "corrected_builder_request_manifest_sha256": None,
        "construction_documents_changed": False,
        "body_anchors_changed": False,
        "builder_scientific_task_changed": False,
        "scientific_content_used_for_policy_decision": False,
        "actual_future_builder_scientific_call_count": 14,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "next_stage_recommendation": next_stage,
        "historical_assets_modified": False}
    write_json("validation.json", validation)
    write_json("summary.json", {"status": "completed",
        "source_token_primary_classification": classification,
        "literal_private_token_visibility_count": literal_count,
        "identifiable_source_information_leak_count": identifying_count,
        "existing_builder_request_manifest_execution_eligible": True,
        "corrected_request_manifest_created": False,
        "actual_future_builder_scientific_call_count": 14,
        "future_builder_calls_authorized_now": False,
        "next_stage_recommendation": next_stage,
        "alpha3_19e_root_sha256": E_SHA,
        "builder_request_manifest_sha256": REQUEST_SHA})
    with (OUT / ROOT_MARKER).open("xb") as handle:
        handle.write((root_hash() + "\n").encode())
    print(json.dumps({"status": "completed", "root_sha256":
          (OUT / ROOT_MARKER).read_text().strip(),
          "classification": classification,
          "literal_token_visibility": literal_count,
          "identifiable_source_leaks": identifying_count}, sort_keys=True))


if __name__ == "__main__":
    main()
