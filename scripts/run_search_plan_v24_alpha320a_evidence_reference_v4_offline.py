#!/usr/bin/env python3
"""Offline, seen-data validation of the prospective V4 evidence locator."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path

from scripts import search_plan_v24_alpha320a_v4_localizer as v4


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
OUT = RUNS / "20261002_search_plan_v24_dev_alpha3_20a_evidence_reference_v4_offline_validation"
ROOT_MARKER = "search_plan_v24_dev_alpha3_20a_sha256"
MASTER = RUNS / "20261002_search_plan_v24_dev_alpha3_20_post_alpha3_19_development_master_preregistration_offline"
E = RUNS / "20261002_search_plan_v24_dev_alpha3_19e_construction_document_anchor_builder_freeze_offline"
F = RUNS / "20261002_search_plan_v24_dev_alpha3_19f_builder_v3_execution"
F1 = RUNS / "20261002_search_plan_v24_dev_alpha3_19f1_zero_quality_input_gate_audit_offline"
G = RUNS / "20261002_search_plan_v24_dev_alpha3_19g_primary_attempt_closure_offline"
EXPECTED_ROOTS = [
    (MASTER, "search_plan_v24_dev_alpha3_20_master_prereg_sha256",
     "8a8edb619c2ad2a31e4b0f6398ae43e3d05de74ae31baddeb611b0cd3e0cd3e6"),
    (E, "search_plan_v24_dev_alpha3_19e_sha256",
     "afcc320cc2e0e352d77fdc4370b87f146b63e7f089663b60dac80c570c87bb87"),
    (F, "search_plan_v24_dev_alpha3_19f_sha256",
     "e1aad29348c72d323221e799b0c9d897aeae336df753f2e761aa98ea4a993549"),
    (F1, "search_plan_v24_dev_alpha3_19f1_sha256",
     "090dd53981166a3a64f46af34376a72fe926d6844dfe85f0d8bd52a7263cfeb3"),
    (G, "search_plan_v24_dev_alpha3_19g_sha256",
     "de6567e7dba0b4f42f936f9e8a5a15f01a09346526bb64f8359b394e769e5da5"),
]
EVIDENCE_CONTRACT_SHA = "156424459bd499272f6dba5a466216ffbe72fe96039045ae8bc44dd7b40b5612"
ABSTRACTION_CONTRACT_SHA = "5ab84eebd9fb8b6a4d7d7600869c5860aa19fbd815ad6dc4c139a6332550fc99"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line]


def root_hash(directory: Path, marker: str) -> str:
    require(not any(path.is_symlink() for path in directory.rglob("*")),
            "SYMLINK_IN_FROZEN_ROOT:" + directory.name)
    files = sorted(path for path in directory.rglob("*")
                   if path.is_file() and path.name != marker)
    return sha(canonical([[str(path.relative_to(directory)), sha(path.read_bytes())]
                          for path in files]))


def verify_roots() -> list[dict]:
    verified = []
    for directory, marker, expected in EXPECTED_ROOTS:
        require((directory / marker).read_text().strip() == expected
                and root_hash(directory, marker) == expected,
                "FROZEN_ROOT_MISMATCH:" + directory.name)
        verified.append({"path": str(directory.relative_to(ROOT)),
                         "root_marker": marker, "sha256": expected, "verified": True})
    return verified


def put(name: str, value: object) -> str:
    raw = canonical(value) + b"\n"
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
    return sha(raw)


def put_rows(name: str, values: list[dict]) -> str:
    raw = b"".join(canonical(value) + b"\n" for value in values)
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
    return sha(raw)


def marker(name: str, value: str) -> None:
    with (OUT / name).open("xb") as handle:
        handle.write((value + "\n").encode("ascii"))


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA320A_OUTPUT_ALREADY_EXISTS_NO_REWRITE")
    roots = verify_roots()
    evidence_path = MASTER / "evidence_reference_contract_v4.json"
    abstraction_path = MASTER / "proposition_abstraction_contract_v1.json"
    require(sha(evidence_path.read_bytes()) == EVIDENCE_CONTRACT_SHA
            and (MASTER / "evidence_reference_contract_v4_sha256").read_text().strip()
            == EVIDENCE_CONTRACT_SHA
            and sha(abstraction_path.read_bytes()) == ABSTRACTION_CONTRACT_SHA
            and (MASTER / "proposition_abstraction_contract_v1_sha256").read_text().strip()
            == ABSTRACTION_CONTRACT_SHA,
            "MASTER_CONTRACT_HASH_MISMATCH")
    evidence_contract = read_json(evidence_path)
    require(evidence_contract["model_owned_fields"] == ["exact_text"]
            and "zero-based start_offset" in evidence_contract["controller_owned_reference_fields"]
            and evidence_contract["multiple_match_state"] == v4.NONUNIQUE
            and evidence_contract["zero_match_state"] == v4.NOT_FOUND
            and evidence_contract["semantic_or_fuzzy_localization"] is False,
            "LOCALIZER_MASTER_AUTHORITY_MISMATCH")
    g_validation = read_json(G / "validation.json")
    f1_validation = read_json(F1 / "validation.json")
    require(g_validation["alpha3_19_primary_attempt_closed"] is True
            and g_validation["eligible_proposition_pool_derived"] is False
            and f1_validation["reproduced_grounding_failure_count"] == 29
            and f1_validation["reproduced_grounding_pass_count"] == 6
            and f1_validation["grounding_primary_classification"] ==
            "GROUNDING_CONTRACT_CONSISTENT_MODEL_NONCONFORMANCE",
            "ALPHA319_HISTORY_MISMATCH")
    require(tuple(inspect.signature(v4.localize_exact_body_quote).parameters) ==
            ("exact_text", "canonical_body", "paragraphs"),
            "MODEL_OFFSETS_OR_SOURCE_IDENTITY_IN_LOCALIZER_INTERFACE")
    raw = rows(F / "raw_builder_candidate_manifest.jsonl")
    identity = rows(F / "candidate_identity_manifest.jsonl")
    historical = {row["candidate_id"]: row for row in
                  rows(F / "body_grounding_audit.jsonl")}
    f1_replay = {row["candidate_id"]: row for row in
                 rows(F1 / "body_grounding_validator_replay.jsonl")}
    doc_manifest = {row["source_token"]: row for row in
                    rows(E / "construction_document_manifest.jsonl")}
    require(len(raw) == len(identity) == len(historical) == len(f1_replay) == 35,
            "DEVELOPMENT_CANDIDATE_COUNT_MISMATCH")
    raw_by_hash = {}
    for record in raw:
        candidate = record["candidate"]
        payload_sha = sha(canonical(candidate))
        require(payload_sha not in raw_by_hash, "FROZEN_CANDIDATE_HASH_COLLISION")
        raw_by_hash[payload_sha] = record
    corpus = []
    for item in identity:
        payload_sha = item["candidate_payload_sha256"]
        require(payload_sha in raw_by_hash, "FROZEN_IDENTITY_RAW_MISMATCH")
        record = raw_by_hash[payload_sha]
        token = item["source_token"]
        require(record["source_token"] == token
                and item["candidate_id"] in historical
                and item["candidate_id"] in f1_replay
                and token in doc_manifest,
                "FROZEN_CANDIDATE_SOURCE_BINDING_MISMATCH")
        span = record["candidate"]["construction_evidence_span"]
        require(span["source_field"] == "body"
                and isinstance(span["exact_text"], str) and span["exact_text"],
                "FROZEN_MODEL_BODY_INTENT_OR_QUOTE_INVALID")
        doc_row = doc_manifest[token]
        doc_path = E / doc_row["document_path"]
        require(sha(doc_path.read_bytes()) == doc_row["document_sha256"],
                "FROZEN_CONSTRUCTION_DOCUMENT_HASH_MISMATCH")
        corpus.append({"candidate_id": item["candidate_id"],
                       "candidate_payload_sha256": payload_sha,
                       "source_token": token,
                       "source_ordinal": item["source_ordinal"],
                       "raw_array_positions": item["original_array_positions_private"],
                       "raw_candidate": record["candidate"],
                       "historical_grounding": historical[item["candidate_id"]],
                       "f1_replay": f1_replay[item["candidate_id"]],
                       "document_row": doc_row,
                       "document": read_json(doc_path)})
    require(len(corpus) == 35 and len({x["candidate_id"] for x in corpus}) == 35,
            "CORPUS_NOT_ALL_35_UNIQUE_CANDIDATES")
    return locals()


def localize_corpus(corpus: list[dict]) -> tuple[list[dict], list[dict]]:
    result_rows = []
    for item in corpus:
        # Deliberately extract only the exact model-authored quote. Historical
        # model offsets are not referenced in this localization function.
        exact_text = item["raw_candidate"]["construction_evidence_span"]["exact_text"]
        document = item["document"]
        localized = v4.localize_exact_body_quote(exact_text, document["body_text"],
                                                  document["paragraphs"])
        result_rows.append({"candidate_id": item["candidate_id"],
                            "candidate_payload_sha256": item["candidate_payload_sha256"],
                            "exact_text_sha256": sha(exact_text.encode("utf-8")),
                            "construction_document_sha256":
                                item["document_row"]["document_sha256"],
                            **localized})
    comparison_rows = []
    for item, result in zip(corpus, result_rows, strict=True):
        historical_span = item["raw_candidate"]["construction_evidence_span"]
        old_start = historical_span["start_offset"]
        old_end = historical_span["end_offset"]
        same = (result["development_v4_localization_state"] == v4.SUCCESS
                and old_start == result["body_document_start_offset"]
                and old_end == result["body_document_end_offset"])
        comparison_rows.append({
            "candidate_id": item["candidate_id"],
            "historical_grounding_state": item["historical_grounding"]["state"],
            "historical_model_start_offset": old_start,
            "historical_model_end_offset": old_end,
            "v4_exact_match_count": result["exact_occurrence_count"],
            "development_v4_localization_state":
                result["development_v4_localization_state"],
            "controller_body_start_offset": result["body_document_start_offset"],
            "controller_body_end_offset": result["body_document_end_offset"],
            "historical_model_offsets_equal_controller_offsets": same,
            "historical_grounding_state_modified": False,
        })
    return result_rows, comparison_rows


def synthetic_cases() -> list[dict]:
    def case(case_id: str, paragraph_texts: list[str], quote: str,
             expected: str, **extra) -> dict:
        body = "\n\n".join(paragraph_texts)
        paragraphs = []
        cursor = 0
        for ordinal, text in enumerate(paragraph_texts, 1):
            paragraphs.append({"ordinal": ordinal,
                               "start_offset": cursor,
                               "end_offset": cursor + len(text),
                               "text": text,
                               "span_id": "spanv1_synthetic_" + str(ordinal)})
            cursor += len(text) + 2
        return {"case_id": case_id, "canonical_body": body,
                "paragraphs": paragraphs, "exact_text": quote,
                "expected_state": expected, **extra}

    return [
        case("A_unique_exact_body_quote", ["alpha beta gamma"], "beta", v4.SUCCESS,
             expected_offsets=[6, 10]),
        case("B_zero_exact_occurrence", ["alpha beta gamma"], "delta", v4.NOT_FOUND),
        case("C_two_same_paragraph", ["alpha beta alpha"], "alpha", v4.NONUNIQUE,
             expected_occurrences=2),
        case("D_two_different_paragraphs", ["alpha", "alpha"], "alpha", v4.NONUNIQUE,
             expected_occurrences=2),
        case("E_cross_paragraph", ["alpha", "beta"], "ha\n\nbe", v4.CROSS_PARAGRAPH),
        case("F_abstract_only", ["body text"], "secret evidence", v4.NOT_FOUND,
             abstract_text="secret evidence"),
        case("G_bibliography_only", ["body text"], "secret evidence", v4.NOT_FOUND,
             bibliography_text="secret evidence"),
        case("H_wrong_historical_offsets", ["alpha beta"], "beta", v4.SUCCESS,
             historical_model_offsets=[0, 1], expected_offsets=[6, 10]),
        case("I_model_offsets_not_consulted", ["alpha beta"], "beta", v4.SUCCESS,
             historical_model_offsets=[900, 901], expected_offsets=[6, 10]),
        case("J_unicode_codepoint_roundtrip", ["αβ γδ"], "γδ", v4.SUCCESS,
             expected_offsets=[3, 5]),
        case("K_exclusive_end_offset", ["abc"], "b", v4.SUCCESS,
             expected_offsets=[1, 2]),
        case("L_private_identity_firewall", ["alpha beta"], "beta", v4.SUCCESS,
             private_identity_not_passed="PMID99999999", expected_offsets=[6, 10]),
        case("M_overlapping_exact_occurrences", ["aaa"], "aa", v4.NONUNIQUE,
             expected_occurrences=2),
        case("N_empty_quote_rejected", ["alpha beta"], "", v4.EMPTY_QUOTE),
    ]


def validate_synthetic(cases: list[dict]) -> dict:
    results = []
    for item in cases:
        result = v4.localize_exact_body_quote(item["exact_text"], item["canonical_body"],
                                               item["paragraphs"])
        passes = result["development_v4_localization_state"] == item["expected_state"]
        if "expected_occurrences" in item:
            passes &= result["exact_occurrence_count"] == item["expected_occurrences"]
        if "expected_offsets" in item:
            passes &= [result["body_document_start_offset"],
                       result["body_document_end_offset"]] == item["expected_offsets"]
            start, end = item["expected_offsets"]
            passes &= item["canonical_body"][start:end] == item["exact_text"]
            paragraph = next(p for p in item["paragraphs"]
                             if p["span_id"] == result["anchor_id"])
            passes &= paragraph["text"][result["paragraph_local_start_offset"]:
                                           result["paragraph_local_end_offset"]] == item["exact_text"]
        if item["case_id"] == "L_private_identity_firewall":
            passes &= item["private_identity_not_passed"] not in canonical(result).decode()
        results.append({"case_id": item["case_id"], "expected_state": item["expected_state"],
                        "actual_state": result["development_v4_localization_state"],
                        "passed": bool(passes)})
    require(all(result["passed"] for result in results), "SYNTHETIC_V4_SUITE_FAILED")
    return {"case_count": len(results), "passed_count": len(results),
            "synthetic_suite_pass": True, "cases": results,
            "model_offset_input_in_localizer_signature": False,
            "end_offset_semantics": "exclusive"}


def replay(state: dict) -> dict:
    first, comparison = localize_corpus(state["corpus"])
    second, _ = localize_corpus(state["corpus"])
    first_bytes = b"".join(canonical(row) + b"\n" for row in first)
    second_bytes = b"".join(canonical(row) + b"\n" for row in second)
    require(first_bytes == second_bytes, "V4_NONDETERMINISTIC_REPLAY")
    cases = synthetic_cases()
    synthetic = validate_synthetic(cases)
    by_id = {row["candidate_id"]: row for row in first}
    compare_by_id = {row["candidate_id"]: row for row in comparison}
    historical_failed = [item for item in state["corpus"]
                         if item["historical_grounding"]["state"] ==
                         "GROUNDING_REFERENCE_FAILED"]
    historical_pass = [item for item in state["corpus"]
                       if item["historical_grounding"]["state"] ==
                       "GROUNDING_REFERENCE_VALID"]
    require(len(historical_failed) == 29 and len(historical_pass) == 6,
            "HISTORICAL_GROUNDING_DENOMINATOR_MISMATCH")
    f1_reproduced = all(
        item["f1_replay"]["taxonomy"] == "OFFSET_MISMATCH"
        and item["f1_replay"]["evidence_text_occurrence_count_in_body"] == 1
        and item["f1_replay"]["actual_text_fits_one_paragraph"] is True
        and by_id[item["candidate_id"]]["exact_occurrence_count"] == 1
        and by_id[item["candidate_id"]]["development_v4_localization_state"] == v4.SUCCESS
        and by_id[item["candidate_id"]]["body_document_start_offset"] ==
            item["f1_replay"]["unique_actual_body_start_offset"]
        for item in historical_failed)
    require(f1_reproduced, "ALPHA3_19F1_STRUCTURAL_OBSERVATION_REPRODUCTION_FAILURE")
    same_six = sum(
        compare_by_id[item["candidate_id"]]["historical_model_offsets_equal_controller_offsets"]
        and by_id[item["candidate_id"]]["anchor_id"] ==
            item["historical_grounding"]["private_anchor_id"]
        for item in historical_pass)
    counts = Counter(row["development_v4_localization_state"] for row in first)
    roundtrip = all(
        row["development_v4_localization_state"] != v4.SUCCESS or
        (item["document"]["body_text"][row["body_document_start_offset"]:
                                        row["body_document_end_offset"]] ==
         item["raw_candidate"]["construction_evidence_span"]["exact_text"] and
         next(p for p in item["document"]["paragraphs"]
              if p["span_id"] == row["anchor_id"])["text"][
                  row["paragraph_local_start_offset"]:
                  row["paragraph_local_end_offset"]] ==
         item["raw_candidate"]["construction_evidence_span"]["exact_text"])
        for item, row in zip(state["corpus"], first, strict=True))
    require(roundtrip, "V4_COORDINATE_ROUNDTRIP_FAILURE")
    return locals()


def freeze(state: dict, result: dict) -> None:
    OUT.mkdir()
    corpus_manifest = [{
        "candidate_id": item["candidate_id"],
        "candidate_payload_sha256": item["candidate_payload_sha256"],
        "exact_text_sha256": sha(item["raw_candidate"]["construction_evidence_span"]["exact_text"].encode("utf-8")),
        "historical_model_body_intent": item["raw_candidate"]["construction_evidence_span"]["source_field"],
        "private_source_token": item["source_token"],
        "source_ordinal": item["source_ordinal"],
        "raw_array_positions": item["raw_array_positions"],
        "construction_document_sha256": item["document_row"]["document_sha256"],
        "scientific_candidate_payload_preserved_byte_identically_by_hash": True,
        "historical_role": "SEEN_DEVELOPMENT_HISTORY",
    } for item in state["corpus"]]
    corpus_sha = put_rows("development_candidate_corpus_manifest.jsonl", corpus_manifest)
    marker("development_candidate_corpus_sha256", corpus_sha)
    put("alpha3_20_master_root_verification.json", {
        "root_sha256": EXPECTED_ROOTS[0][2], "verified": True,
        "evidence_reference_contract_v4_sha256": EVIDENCE_CONTRACT_SHA,
        "proposition_abstraction_contract_v1_sha256": ABSTRACTION_CONTRACT_SHA})
    put("alpha3_19f1_root_verification.json", {
        "root_sha256": EXPECTED_ROOTS[3][2], "verified": True,
        "frozen_grounding_observation_used_only_for_development_diagnostic": True})
    put("evidence_reference_v4_implementation_contract.json", {
        "status": "PROSPECTIVE_DEVELOPMENT_INFRASTRUCTURE",
        "authoritative_master_evidence_contract_sha256": EVIDENCE_CONTRACT_SHA,
        "implementation_path": "scripts/search_plan_v24_alpha320a_v4_localizer.py",
        "implementation_sha256": sha((ROOT / "scripts/search_plan_v24_alpha320a_v4_localizer.py").read_bytes()),
        "separate_from_historical_v3_validator": True,
        "localizer_input_parameters": list(inspect.signature(v4.localize_exact_body_quote).parameters),
        "historical_model_offsets_in_localizer_signature": False,
        "canonical_body_only": True,
        "extra_normalization": False,
        "end_offset_semantics": "zero-based, Unicode code-point, exclusive",
        "historical_v3_states_modified": False})
    put("grounding_ownership_runtime_matrix.json", {
        "historical_v3_model_authored_source_field_checked_as_body_intent": True,
        "historical_model_exact_text_preserved": True,
        "prospective_v4_model_owned": ["exact BODY quote", "scientific proposition fields"],
        "prospective_v4_controller_owned": ["source_field constant body",
                                             "exact occurrence count", "paragraph identity",
                                             "zero-based start and exclusive end offsets",
                                             "anchor identity", "coordinate provenance"],
        "historical_model_offsets_consulted_for_localization": False,
        "historical_model_offsets_read_only_after_localization_for_diagnostics": True,
        "controller_scientific_evidence_selection": False,
        "literal_source_field_authority_note":
            "Historical V3 source_field is model-authored BODY intent; prospective V4 final source_field is controller-owned fixed body under the master contract."})
    put("controller_exact_match_localizer_spec.json", {
        "exact_text_input": "unaltered model-authored quote",
        "body_input": "same candidate's frozen canonical ConstructionEvidenceDocument body_text",
        "match_count_method": "all exact Unicode code-point substring occurrences, including overlaps",
        "zero_match": v4.NOT_FOUND, "multiple_matches": v4.NONUNIQUE,
        "unique_match": "require containment in exactly one canonical BODY paragraph",
        "cross_paragraph_diagnostic_state": v4.CROSS_PARAGRAPH,
        "cross_paragraph_master_contract_state": "GROUNDING_PARAGRAPH_BOUNDARY_INVALID",
        "start_offset": "zero-based inclusive Unicode code-point index",
        "end_offset": "zero-based exclusive Unicode code-point index",
        "paragraph_local_offsets": "same inclusive-start, exclusive-end convention",
        "anchor_identity": "existing deterministic EvidenceSpanAnchorV1 paragraph span_id",
        "no_model_offset_hint_or_fuzzy_search": True,
        "no_abstract_title_bibliography_back_matter_or_other_article_search": True})
    put("controller_exact_match_localizer_validation.json", {
        "implementation_sha256": sha((ROOT / "scripts/search_plan_v24_alpha320a_v4_localizer.py").read_bytes()),
        "exact_match_only": True,
        "model_offset_parameter_absent": True,
        "source_identity_parameter_absent": True,
        "synthetic_suite_pass": result["synthetic"]["synthetic_suite_pass"],
        "determinism_replay_pass": True,
        "roundtrip_invariant_pass": result["roundtrip"],
        "material_runtime_policy_unresolved_count": 0})
    put("historical_f1_observation_reproduction.json", {
        "historical_offset_mismatch_candidates": len(result["historical_failed"]),
        "f1_exact_unique_body_quote_and_single_paragraph_claim_reproduced": result["f1_reproduced"],
        "historical_29_v4_localization_success": sum(
            result["by_id"][item["candidate_id"]]["development_v4_localization_state"] == v4.SUCCESS
            for item in result["historical_failed"]),
        "historical_states_rewritten": False,
        "use": "DEVELOPMENT_DIAGNOSTIC_ONLY"})
    put_rows("v4_candidate_localization_results.jsonl", result["first"])
    put_rows("v4_historical_offset_comparison.jsonl", result["comparison"])
    counts = result["counts"]
    summary_counts = {
        "development_candidate_count": 35,
        "v4_unique_exact_localization_success": counts[v4.SUCCESS],
        "v4_text_not_found": counts[v4.NOT_FOUND],
        "v4_text_nonunique": counts[v4.NONUNIQUE],
        "v4_cross_paragraph": counts[v4.CROSS_PARAGRAPH],
        "v4_coordinate_derivation_failure": counts[v4.COORDINATE_FAILURE],
        "other_deterministic_failures": sum(value for key, value in counts.items()
                                            if key not in {v4.SUCCESS, v4.NOT_FOUND,
                                                           v4.NONUNIQUE, v4.CROSS_PARAGRAPH,
                                                           v4.COORDINATE_FAILURE}),
        "historical_29_v4_localization_success": sum(
            result["by_id"][item["candidate_id"]]["development_v4_localization_state"] == v4.SUCCESS
            for item in result["historical_failed"]),
        "historical_6_v4_same_occurrence": result["same_six"],
        "historical_alpha3_19_quality_input_candidates_unchanged": 0,
    }
    require(sum(summary_counts[key] for key in (
        "v4_unique_exact_localization_success", "v4_text_not_found", "v4_text_nonunique",
        "v4_cross_paragraph", "v4_coordinate_derivation_failure",
        "other_deterministic_failures")) == 35, "V4_STATE_TOTAL_MISMATCH")
    put("v4_localization_summary.json", summary_counts)
    put("v4_roundtrip_invariant_audit.json", {
        "localized_candidate_count": counts[v4.SUCCESS],
        "canonical_body_slice_equals_exact_text": result["roundtrip"],
        "paragraph_local_slice_equals_exact_text": result["roundtrip"],
        "end_offset_exclusive": True,
        "coordinate_derivation_failures": counts[v4.COORDINATE_FAILURE],
        "roundtrip_invariant_pass": result["roundtrip"]})
    put("v4_body_boundary_audit.json", {
        "actual_candidates_bound_to_own_frozen_construction_document": 35,
        "canonical_body_only_search": True,
        "abstract_only_synthetic_quote_not_found": True,
        "bibliography_only_synthetic_quote_not_found": True,
        "cross_paragraph_synthetic_quote_failed": True,
        "cross_document_search_used": False,
        "canonicalization_policy_changed": False})
    schema_fragment = {
        "schema_version": "BuilderOutputSchemaV4EvidenceFragment",
        "status": "PROSPECTIVE_EVIDENCE_PORTION_ONLY",
        "model_generated_candidate_evidence_schema": {
            "type": "object",
            "properties": {"construction_evidence_span": {
                "type": "object",
                "properties": {"exact_text": {"type": "string", "minLength": 1}},
                "required": ["exact_text"], "additionalProperties": False}},
            "required": ["construction_evidence_span"],
        },
        "controller_rehydrated_evidence_fields": ["source_field=body", "paragraph_ordinal",
                                                  "start_offset", "end_offset", "anchor_id"],
        "model_generated_offsets_required_or_allowed": False,
        "historical_v3_source_field_body_intent_preserved_only_for_development_replay": True,
        "historical_v3_schema_modified": False,
        "complete_builder_v4_prompt_or_schema_frozen": False,
    }
    schema_sha = put("builder_output_schema_v4_evidence_fragment.json", schema_fragment)
    marker("builder_output_schema_v4_evidence_fragment_sha256", schema_sha)
    put("v4_identity_firewall_audit.json", {
        "future_model_visible_evidence_fragment_contains_pmid_pmcid_doi_title_journal_authors": False,
        "localizer_accepts_private_source_identity": False,
        "historical_private_source_token_only_in_private_development_manifest": True,
        "anchor_identity_controller_derived_from_frozen_opaque_span_id": True,
        "synthetic_private_identity_not_emitted": True,
        "model_generated_clear_source_identifier_added": False})
    put_rows("synthetic_v4_cases.jsonl", result["cases"])
    put("synthetic_v4_test_results.json", result["synthetic"])
    first_sha = sha(b"".join(canonical(row) + b"\n" for row in result["first"]))
    second_sha = sha(b"".join(canonical(row) + b"\n" for row in result["second"]))
    put("v4_determinism_replay_audit.json", {
        "replay_count": 2,
        "first_manifest_sha256": first_sha,
        "second_manifest_sha256": second_sha,
        "byte_identical_state_coordinate_anchor_order_and_hashes": first_sha == second_sha,
        "determinism_replay_pass": first_sha == second_sha})
    require(verify_roots() == state["roots"],
            "HISTORICAL_ROOT_CHANGED_DURING_ALPHA320A")
    put("historical_nonmutation_audit.json", {
        "roots_verified_before_and_after": True,
        "historical_roots": state["roots"],
        "historical_candidate_states_modified": False,
        "historical_leakage_states_modified": False,
        "historical_alpha3_19_funnel": {"raw_candidates": 35,
                                        "grounding_passes": 6,
                                        "quality_input_candidates": 0},
        "builder_invalid_length_response_salvaged": False})
    put("scientific_content_nonuse_audit.json", {
        "scientific_content_used_for_policy_tuning": False,
        "exact_quote_string_used_only_for_structural_match": True,
        "proposition_or_evidence_text_rewritten": False,
        "scientific_candidate_quality_judged": False,
        "leakage_recomputed_or_changed": False})
    put("scientific_state_safety_audit.json", {
        "provider_calls": 0, "deepseek_calls": 0, "openai_calls": 0,
        "llm_calls": 0, "network_calls": 0,
        "builder_calls": 0, "quality_calls": 0,
        "fresh_attempt_started": False,
        "historical_assets_modified": False,
        "proposition_text_changed": False,
        "leakage_policy_changed": False,
        "fuzzy_match_used": False})
    validated = bool(result["roundtrip"] and result["f1_reproduced"]
                     and result["synthetic"]["synthetic_suite_pass"]
                     and first_sha == second_sha and result["same_six"] == 6)
    classification = ("EVIDENCE_REFERENCE_V4_VALIDATED" if validated else
                      "EVIDENCE_REFERENCE_V4_PARTIALLY_VALIDATED_WITH_BLOCKER")
    next_stage = ("PREREGISTER_ALPHA3_20B_PROPOSITION_ABSTRACTION_PROMPT_FREEZE"
                  if validated else "AUDIT_ALPHA3_20A_EVIDENCE_REFERENCE_V4_BLOCKER_OFFLINE")
    validation = {
        "status": "completed", "alpha3_20a_classification": classification,
        "alpha3_20_master_root_verified": True,
        "alpha3_19f1_root_verified": True,
        "development_only": True,
        "development_candidate_count": 35,
        "historical_offset_mismatch_candidate_count": 29,
        "historical_grounding_pass_candidate_count": 6,
        **summary_counts,
        "historical_candidate_states_modified": False,
        "model_offset_used_for_v4_localization": False,
        "exact_quote_model_owned": True,
        "coordinates_controller_owned": True,
        "exact_match_only": True,
        "fuzzy_match_used": False,
        "canonicalization_policy_changed": False,
        "roundtrip_invariant_pass": result["roundtrip"],
        "historical_f1_observation_reproduced": result["f1_reproduced"],
        "synthetic_suite_pass": result["synthetic"]["synthetic_suite_pass"],
        "determinism_replay_pass": first_sha == second_sha,
        "leakage_policy_changed": False,
        "proposition_text_changed": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "builder_output_schema_v4_evidence_fragment_sha256": schema_sha,
        "material_runtime_policy_unresolved_count": 0,
        "next_stage_recommendation": next_stage,
        "historical_assets_modified": False,
    }
    put("validation.json", validation)
    put("summary.json", {"status": "completed", "classification": classification,
                         "development_candidate_count": 35,
                         "v4_localization_counts": summary_counts,
                         "synthetic_suite_pass": True,
                         "determinism_replay_pass": True,
                         "historical_states_unchanged": True,
                         "next_stage_recommendation": next_stage})
    root = root_hash(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    require(root_hash(OUT, ROOT_MARKER) == root,
            "ALPHA320A_ROOT_VERIFY_FAILED")
    print(json.dumps({"status": "completed", "classification": classification,
                      "root_sha256": root, "schema_fragment_sha256": schema_sha,
                      "v4_unique_exact_localization_success": counts[v4.SUCCESS],
                      "historical_29_v4_localization_success":
                          summary_counts["historical_29_v4_localization_success"]},
                     sort_keys=True))


def main() -> None:
    state = preflight()
    result = replay(state)
    freeze(state, result)


if __name__ == "__main__":
    main()
