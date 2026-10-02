#!/usr/bin/env python3
"""Read-only structural replay of the frozen alpha3.19F deterministic gates."""
from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from scripts import run_search_plan_v24_alpha319f_builder_v3_execution as f


ROOT = f.ROOT
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19f1_zero_quality_input_gate_audit_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_19f1_sha256"
F_SHA = "e1aad29348c72d323221e799b0c9d897aeae336df753f2e761aa98ea4a993549"
E1_SHA = f.E1_SHA
REQUEST_SHA = f.REQUEST_SHA
LEAKAGE_AUTHORITY = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline/leakage_audit_implementation_contract.json"
GROUNDING_AUTHORITY = f.e.SOURCE_CONTRACT_DIR / "builder_grounding_reference_contract.json"
ANCHOR_AUTHORITY = f.e.SOURCE_CONTRACT_DIR / "evidence_span_anchor_v1_contract.json"
V3_CONTRACT = f.e.V3_DIR / "builder_grounding_contract_v3.json"
V3_SCHEMA = f.e.V3_DIR / "builder_output_schema_v3.json"
PROMPT_TEMPLATE = f.e.SOURCE_CONTRACT_DIR / "proposition_builder_v2_1_user_prompt_template.txt"
BUILDER_PROTOCOL = f.e.BUILDER_PROTOCOL_DIR / "proposition_builder_protocol_v2.json"
MASTER_BINDING = f.e.master.OUT / "alpha3_19_builder_contract_binding.json"
MASTER_POLICY = f.e.master.OUT / "scientific_policy_nonadaptation_audit.json"
GROUNDING_IMPLEMENTATION = ROOT / "scripts/search_plan_v24_alpha318a1_source_contracts.py"
POSTCHECK_IMPLEMENTATION = ROOT / "scripts/search_plan_v24_alpha318b_post_builder_prechecks.py"
LEAKAGE_IMPLEMENTATION = ROOT / "scripts/search_plan_v24_alpha317a_safety_audits.py"


def require(ok: bool, reason: str):
    if not ok:
        raise RuntimeError(reason)


def canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def sha(raw: bytes):
    return hashlib.sha256(raw).hexdigest()


def ref(path: Path):
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes())}


def put(name: str, raw: bytes):
    with (OUT / name).open("xb") as handle:
        handle.write(raw)


def obj(name: str, value):
    put(name, canon(value) + b"\n")


def lines(name: str, values):
    put(name, b"".join(canon(value) + b"\n" for value in values))


def root_hash():
    paths = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != ROOT_MARKER)
    require(not any(path.is_symlink() for path in OUT.iterdir()), "OUTPUT_SYMLINK_FORBIDDEN")
    return sha(canon([[path.name, sha(path.read_bytes())] for path in paths]))


def validate_schema(value, schema, location="$._"):
    """Independent local JSON-schema subset replay, without production validator."""
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    match = (kind is None or
             ("object" in kinds and isinstance(value, dict)) or
             ("array" in kinds and isinstance(value, list)) or
             ("string" in kinds and isinstance(value, str)) or
             ("integer" in kinds and type(value) is int) or
             ("null" in kinds and value is None))
    require(match, "REFERENCE_SCHEMA_TYPE:" + location)
    if "enum" in schema:
        require(value in schema["enum"], "REFERENCE_SCHEMA_ENUM:" + location)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        require(set(schema.get("required", [])) <= set(value),
                "REFERENCE_SCHEMA_REQUIRED:" + location)
        if schema.get("additionalProperties") is False:
            require(set(value) <= set(props), "REFERENCE_SCHEMA_EXTRA:" + location)
        for key, item in value.items():
            if key in props:
                validate_schema(item, props[key], location + "." + key)
    elif isinstance(value, list):
        require(schema.get("minItems", 0) <= len(value) <=
                schema.get("maxItems", float("inf")), "REFERENCE_SCHEMA_ARRAY:" + location)
        for index, item in enumerate(value):
            validate_schema(item, schema["items"], f"{location}[{index}]")
    elif isinstance(value, str):
        require(len(value) >= schema.get("minLength", 0),
                "REFERENCE_SCHEMA_LENGTH:" + location)
    elif type(value) is int:
        require(value >= schema.get("minimum", float("-inf")),
                "REFERENCE_SCHEMA_MINIMUM:" + location)


def text_tokens(value: str):
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).lower(),
                      flags=re.UNICODE)


def max_common_contiguous(a: list[str], b: list[str]):
    best, previous = 0, {}
    for word in a:
        current = {}
        for index, other in enumerate(b):
            if word == other:
                current[index] = previous.get(index - 1, 0) + 1
                best = max(best, current[index])
        previous = current
    return best


def evidence_sentence(body: str, start: int, end: int):
    if any(character in ".!?\n" for character in body[start:end]):
        return body, "ENTIRE_BODY_AMBIGUOUS_SPAN"
    left = max((i + 1 for i in range(start) if body[i] in ".!?\n"), default=0)
    right = next((i for i in range(end, len(body)) if body[i] in ".!?\n"), len(body))
    result = body[left:right].strip() or body
    return result, "BOUNDED_CONTAINING_SENTENCE" if result != body else "ENTIRE_BODY_FALLBACK"


def title_from_jats(raw: bytes):
    root = ET.fromstring(raw)
    title = next((node for node in root.iter()
                  if node.tag.rsplit("}", 1)[-1] == "article-title"), None)
    require(title is not None, "PRIVATE_TITLE_MISSING")
    return " ".join(unicodedata.normalize("NFKC", "".join(title.itertext())).split())


def preflight():
    require(not OUT.exists(), "ALPHA319F1_OUTPUT_ALREADY_EXISTS_NO_RERUN")
    require(f.root_hash() == F_SHA and (f.OUT / f.ROOT_MARKER).read_text().strip() == F_SHA and
            f.e1.root_hash() == E1_SHA and
            (f.e1.OUT / f.e1.ROOT_MARKER).read_text().strip() == E1_SHA and
            sha((f.e.OUT / "alpha3_19_builder_v3_request_manifest.jsonl").read_bytes()) ==
                REQUEST_SHA,
            "FROZEN_UPSTREAM_HASH_MISMATCH")
    require(sha(LEAKAGE_AUTHORITY.read_bytes()) ==
            "790cdf7717fe0f58cb3997a9cbe8684475f389edde9f629825298dfb4d58607c" and
            sha(GROUNDING_AUTHORITY.read_bytes()) ==
            "8d0d4e74724f9859516c4c2d1af384f6953a0ea21800a6e04a86be739e663ea0" and
            sha(ANCHOR_AUTHORITY.read_bytes()) == f.e.ANCHOR_CONTRACT_SHA and
            sha(V3_CONTRACT.read_bytes()) == f.e.V3_CONTRACT_SHA and
            sha(V3_SCHEMA.read_bytes()) == f.e.V3_SCHEMA_SHA and
            sha(GROUNDING_IMPLEMENTATION.read_bytes()) == f.e.IMPLEMENTATION_SHA and
            sha(POSTCHECK_IMPLEMENTATION.read_bytes()) ==
            "cc6623dc75b07dd54d7f4fec2ca71bc1b66ae9ab8741865d8f4b917a7e8fa383" and
            sha(LEAKAGE_IMPLEMENTATION.read_bytes()) ==
            "48808884c1a6a603908abaa962ab1ef15c4f11257b02a4fa3f93c63077052ce8",
            "FROZEN_GROUNDING_OR_LEAKAGE_AUTHORITY_MISMATCH")
    leak_contract = json.loads(LEAKAGE_AUTHORITY.read_bytes())
    post_leak = json.loads((f.POSTCHECK_DIR / "builder_leakage_execution_contract.json").read_bytes())
    require(leak_contract["comparison_inputs"] == ["private source title",
                "private evidence sentence", "public neutral proposition"] and
            leak_contract["normalization"] ==
                "Unicode NFKC, lowercase, maximal Unicode-alphanumeric spans" and
            post_leak["shared_consecutive_tokens_failure_threshold"] == 8 and
            post_leak["qualifying_token_jaccard_failure_threshold"] == 0.8,
            "FROZEN_LEAKAGE_INPUT_OR_THRESHOLD_MISMATCH")
    schema = json.loads(V3_SCHEMA.read_bytes())["schema"]
    requests = f.e.rows(f.e.OUT / "alpha3_19_builder_v3_request_manifest.jsonl")
    protocol = json.loads(BUILDER_PROTOCOL.read_bytes())
    amendment = json.loads((f.e.SOURCE_CONTRACT_DIR /
        "builder_request_visibility_amendment.json").read_bytes())
    system_prompt = (protocol["system_prompt_utf8"] +
        amendment["required_additional_instruction"] + "\n")
    require("exact source-local span with zero-based character offsets" in
            protocol["system_prompt_utf8"] and
            "source_field=body and exact offsets into frozen canonical body_text" in
            amendment["required_additional_instruction"] and
            all(row["request"]["messages"][0]["content"] == system_prompt
                for row in requests),
            "EXACT_COPY_PROMPT_AUTHORITY_MISMATCH")
    raw = f.e.rows(f.OUT / "builder_raw_provider_responses.jsonl")
    terminal = f.e.rows(f.OUT / "builder_source_terminal_states.jsonl")
    candidates = f.e.rows(f.OUT / "raw_builder_candidate_manifest.jsonl")
    require(len(requests) == len(raw) == len(terminal) == 14 and len(candidates) == 35 and
            sum(row["terminal_state"] == "BUILDER_VALID_NONZERO" for row in terminal) == 13 and
            sum(row["terminal_state"] == "BUILDER_V3_RESPONSE_INVALID" for row in terminal) == 1,
            "FROZEN_FUNNEL_COUNT_MISMATCH")
    docs = {row["source_token"]: row for row in
            f.e.rows(f.e.OUT / "construction_document_manifest.jsonl")}
    sources = {row["opaque_source_token"]: row for row in
               f.e.rows(f.e.d1.OUT / "final_construction_source_manifest.jsonl")}
    return {"schema": schema, "requests": requests, "raw": raw,
            "terminal": terminal, "candidates": candidates,
            "docs": docs, "sources": sources, "leak_contract": leak_contract}


def replay(state):
    raw_by_ordinal = {row["ordinal"]: row for row in state["raw"]}
    terminal_by_ordinal = {row["ordinal"]: row for row in state["terminal"]}
    logged_raw = state["candidates"]
    independent_raw = []
    invalid_length = 0
    for request in state["requests"]:
        ordinal, token = request["ordinal"], request["source_token"]
        raw = raw_by_ordinal[ordinal]
        terminal = terminal_by_ordinal[ordinal]["terminal_state"]
        require(raw["source_token"] == token and raw["scientific_inference_confirmed"] is True,
                "FROZEN_RAW_RESPONSE_BINDING_MISMATCH")
        if raw["finish_reason"] != "stop":
            require(raw["finish_reason"] == "length" and
                    terminal == "BUILDER_V3_RESPONSE_INVALID",
                    "INVALID_RESPONSE_STATE_CHANGED")
            invalid_length += 1
            continue
        parsed = json.loads(raw["model_content_raw"])
        validate_schema(parsed, state["schema"])
        require(parsed["source_record_token"] == token and
                terminal == ("BUILDER_VALID_NONZERO" if parsed["candidates"] else
                             "BUILDER_VALID_ZERO"),
                "INDEPENDENT_SCHEMA_OR_TOKEN_REPLAY_MISMATCH")
        independent_raw.extend({"ordinal": ordinal, "source_token": token,
            "raw_array_position": index, "candidate": candidate,
            "state": "RAW_BUILDER_V3_CANDIDATE"}
            for index, candidate in enumerate(parsed["candidates"]))
    require(invalid_length == 1 and independent_raw == logged_raw and
            len(independent_raw) == 35, "RAW_CANDIDATE_REPLAY_MISMATCH")
    identity_log = f.e.rows(f.OUT / "candidate_identity_manifest.jsonl")
    grounding_log = {row["candidate_id"]: row for row in
                     f.e.rows(f.OUT / "body_grounding_audit.jsonl")}
    leakage_log = {row["candidate_id"]: row for row in
                   f.e.rows(f.OUT / "lexical_leakage_audit.jsonl")}
    unique_rows = []
    duplicate_count = 0
    for request in state["requests"]:
        ordinal, token = request["ordinal"], request["source_token"]
        by_digest = {}
        for record in independent_raw:
            if record["ordinal"] != ordinal:
                continue
            candidate = record["candidate"]
            payload_sha = sha(canon(candidate))
            by_digest.setdefault(payload_sha, {"candidate": candidate,
                "positions": []})["positions"].append(record["raw_array_position"])
        duplicate_count += sum(len(x["positions"]) - 1 for x in by_digest.values())
        for payload_sha, group in sorted(by_digest.items()):
            candidate_id = "pcv2_" + sha(canon([
                "PropositionBuilderProtocolV2", token, payload_sha]))
            unique_rows.append({"source_ordinal": ordinal, "source_token": token,
                "candidate_id": candidate_id, "candidate_payload_sha256": payload_sha,
                "original_array_positions_private": group["positions"],
                "candidate": group["candidate"]})
    require(len(unique_rows) == len(identity_log) == 35 and duplicate_count == 0 and
            [row["candidate_id"] for row in unique_rows] ==
                [row["candidate_id"] for row in identity_log] and
            [row["candidate_payload_sha256"] for row in unique_rows] ==
                [row["candidate_payload_sha256"] for row in identity_log],
            "CANDIDATE_ID_OR_EXACT_DEDUP_REPLAY_MISMATCH")
    grounding_rows, leakage_results, diagnostics = [], [], []
    for record in unique_rows:
        token, candidate_id = record["source_token"], record["candidate_id"]
        candidate = record["candidate"]
        span = candidate["construction_evidence_span"]
        doc_row = state["docs"][token]
        doc_path = f.e.OUT / doc_row["document_path"]
        require(sha(doc_path.read_bytes()) == doc_row["document_sha256"],
                "FROZEN_DOCUMENT_HASH_CHANGED")
        document = json.loads(doc_path.read_bytes())
        body = document["body_text"]
        field, text = span["source_field"], span["exact_text"]
        start, end = span["start_offset"], span["end_offset"]
        locations = []
        pos = body.find(text)
        while pos >= 0:
            locations.append(pos)
            pos = body.find(text, pos + 1)
        actual_location = locations[0] if len(locations) == 1 else None
        actual_text_fits_one_paragraph = bool(actual_location is not None and any(
            paragraph["start_offset"] <= actual_location and
            actual_location + len(text) <= paragraph["end_offset"]
            for paragraph in document["paragraphs"]))
        if field != "body":
            taxonomy = "SOURCE_FIELD_INVALID"
        elif not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(body):
            taxonomy = "OFFSET_MISMATCH"
        elif body[start:end] != text:
            taxonomy = "OFFSET_MISMATCH" if locations else "EVIDENCE_TEXT_EXACT_MISMATCH"
        else:
            containing = [paragraph for paragraph in document["paragraphs"]
                          if paragraph["start_offset"] <= start and end <= paragraph["end_offset"]]
            taxonomy = "PASS" if len(containing) == 1 else "REFERENCE_SPANS_MULTIPLE_PARAGRAPHS"
        expected_grounding = ("GROUNDING_REFERENCE_VALID" if taxonomy == "PASS" else
                              "GROUNDING_REFERENCE_FAILED")
        require(grounding_log[candidate_id]["state"] == expected_grounding,
                "GROUNDING_VALIDATOR_REPLAY_MISMATCH:" + candidate_id)
        if taxonomy == "PASS":
            require(grounding_log[candidate_id]["private_anchor_id"] == containing[0]["span_id"],
                    "GROUNDING_ANCHOR_REPLAY_MISMATCH")
        grounding_rows.append({"source_ordinal": record["source_ordinal"],
            "candidate_id": candidate_id, "source_field": field,
            "candidate_start_offset": start, "candidate_end_offset": end,
            "evidence_text_sha256": sha(text.encode()),
            "evidence_text_occurrence_count_in_body": len(locations),
            "unique_actual_body_start_offset": actual_location,
            "actual_text_fits_one_paragraph": actual_text_fits_one_paragraph,
            "failure_stage": "BODY_SLICE_EXACT_TEXT_COMPARISON" if taxonomy == "OFFSET_MISMATCH"
                else "PARAGRAPH_CONTAINMENT" if taxonomy == "REFERENCE_SPANS_MULTIPLE_PARAGRAPHS"
                else "NONE" if taxonomy == "PASS" else "OTHER_STRUCTURAL_STAGE",
            "taxonomy": taxonomy, "reproduced_grounding_state": expected_grounding})
        if taxonomy != "PASS":
            transformations = {
                "NFC": lambda s: unicodedata.normalize("NFC", s),
                "NFKC": lambda s: unicodedata.normalize("NFKC", s),
                "CRLF_TO_LF": lambda s: s.replace("\r\n", "\n"),
                "ASCII_WHITESPACE_COLLAPSE": lambda s: re.sub(r"[ \t\r\n\f\v]+", " ", s),
                "LEADING_TRAILING_WHITESPACE_STRIP": lambda s: s.strip(),
                "XML_ENTITY_UNESCAPE": html.unescape,
            }
            diagnostic = {}
            for name, transform in transformations.items():
                transformed_body, transformed_text = transform(body), transform(text)
                found = transformed_body.find(transformed_text)
                diagnostic[name] = {"text_found": found >= 0,
                    "candidate_offset_matches": found >= 0 and found == start and
                        transformed_body[found:found + len(transformed_text)] == transformed_text}
            diagnostics.append({"candidate_id": candidate_id,
                "historical_state_unchanged": True,
                "raw_exact_text_already_present": bool(locations),
                "diagnostic_transformations": diagnostic})
            require(leakage_log[candidate_id]["state"] == "NOT_RUN_AFTER_GROUNDING_FAILURE",
                    "LEAKAGE_EXECUTED_AFTER_GROUNDING_FAILURE")
            continue
        source = state["sources"][token]
        jats_path = f.e.d.OUT / source["normalized_jats_path"]
        require(sha(jats_path.read_bytes()) == source["normalized_jats_sha256"],
                "FROZEN_JATS_HASH_CHANGED")
        title = title_from_jats(jats_path.read_bytes())
        sentence, sentence_scope = evidence_sentence(body, start, end)
        proposition_tokens = text_tokens(candidate["neutral_proposition"])
        source_metrics = []
        for source_kind, source_text in (("PRIVATE_SOURCE_TITLE", title),
                                         ("CONTAINING_EVIDENCE_SENTENCE", sentence)):
            comparator_tokens = text_tokens(source_text)
            maximum = max_common_contiguous(proposition_tokens, comparator_tokens)
            union = set(proposition_tokens) | set(comparator_tokens)
            jaccard = (len(set(proposition_tokens) & set(comparator_tokens)) / len(union)) if union else 0.0
            eligible = len(proposition_tokens) >= 8 and len(comparator_tokens) >= 8
            source_metrics.append({"source_surface": source_kind,
                "candidate_token_count": len(proposition_tokens),
                "source_token_count": len(comparator_tokens),
                "maximum_shared_consecutive_tokens": maximum,
                "qualifying_token_jaccard": jaccard,
                "minimum_eight_tokens_satisfied": eligible,
                "eight_token_trigger": eligible and maximum >= 8,
                "jaccard_trigger": eligible and jaccard >= 0.80})
        eight = any(item["eight_token_trigger"] for item in source_metrics)
        jaccard = any(item["jaccard_trigger"] for item in source_metrics)
        leakage_state = "LEXICAL_LEAKAGE_FAILED" if eight or jaccard else "LEXICAL_LEAKAGE_PASSED"
        require(leakage_log[candidate_id]["state"] == leakage_state,
                "INDEPENDENT_LEAKAGE_REPLAY_MISMATCH:" + candidate_id)
        leakage_results.append({"source_ordinal": record["source_ordinal"],
            "candidate_id": candidate_id, "candidate_comparator_field": "neutral_proposition",
            "source_sentence_scope": sentence_scope,
            "evidence_exact_text_field_passed_as_candidate_comparator": False,
            "evidence_quote_verbatim_in_model_proposition": text in candidate["neutral_proposition"],
            "comparisons": source_metrics,
            "maximum_shared_consecutive_tokens": max(x["maximum_shared_consecutive_tokens"]
                                                     for x in source_metrics),
            "eight_token_trigger": eight, "jaccard_trigger": jaccard,
            "final_frozen_leakage_state": leakage_state})
    require(len(grounding_rows) == 35 and
            sum(row["taxonomy"] == "PASS" for row in grounding_rows) == 6 and
            len(diagnostics) == 29 and len(leakage_results) == 6 and
            all(row["final_frozen_leakage_state"] == "LEXICAL_LEAKAGE_FAILED"
                for row in leakage_results) and
            len(f.e.rows(f.OUT / "quality_input_candidate_manifest.jsonl")) == 0 and
            len(f.e.rows(f.OUT / "quality_source_group_manifest.jsonl")) == 0,
            "FROZEN_FUNNEL_REPRODUCTION_FAILURE")
    return {"grounding": grounding_rows, "diagnostics": diagnostics,
            "leakage": leakage_results, "raw_count": len(independent_raw),
            "duplicate_count": duplicate_count, "invalid_length": invalid_length}


def freeze(state, result):
    OUT.mkdir()
    grounding = result["grounding"]
    leakage = result["leakage"]
    failed = [row for row in grounding if row["taxonomy"] != "PASS"]
    taxonomy = Counter(row["taxonomy"] for row in failed)
    require(taxonomy == {"OFFSET_MISMATCH": 29} and
            all(row["evidence_text_occurrence_count_in_body"] == 1 and
                row["actual_text_fits_one_paragraph"] for row in failed),
            "GROUNDING_FAILURE_STRUCTURE_NOT_AS_CLASSIFIED")
    eight_only = sum(row["eight_token_trigger"] and not row["jaccard_trigger"] for row in leakage)
    jaccard_only = sum(not row["eight_token_trigger"] and row["jaccard_trigger"] for row in leakage)
    both = sum(row["eight_token_trigger"] and row["jaccard_trigger"] for row in leakage)
    passed = sum(not row["eight_token_trigger"] and not row["jaccard_trigger"] for row in leakage)
    require(eight_only + jaccard_only + both + passed == 6 and
            eight_only == 4 and jaccard_only == 0 and both == 2 and passed == 0,
            "LEAKAGE_TRIGGER_ACCOUNTING_MISMATCH")
    grounding_class = "GROUNDING_CONTRACT_CONSISTENT_MODEL_NONCONFORMANCE"
    leakage_class = "LEAKAGE_CONTRACT_CONSISTENT_ZERO_SURVIVORS"
    combined = "ZERO_QUALITY_INPUT_GENUINE_UNDER_CONSISTENT_FROZEN_GATES"
    next_stage = "CLOSE_ALPHA3_19_PRIMARY_ATTEMPT_ZERO_QUALITY_INPUT"
    obj("alpha3_19f_root_verification.json", {"root_sha256": F_SHA,
        "verified": f.root_hash() == F_SHA,
        "frozen_validation": ref(f.OUT / "validation.json"),
        "historical_builder_inference_events": 14})
    obj("builder_execution_preservation_audit.json", {
        "builder_requests_attempted": 14, "builder_scientific_inference_events": 14,
        "builder_valid_nonzero": 13, "builder_response_invalid": 1,
        "invalid_finish_reason": "length", "invalid_partial_candidates_salvaged": 0,
        "builder_reruns": 0, "quality_calls": 0,
        "historical_quality_call_budget": 0,
        "historical_alpha3_19f_root_unchanged": f.root_hash() == F_SHA})
    obj("candidate_funnel_reproduction.json", {"raw_candidates": 35,
        "invalid_completed_responses": 1,
        "candidate_ids_independently_reproduced": 35,
        "exact_duplicates_removed": result["duplicate_count"],
        "reproduced_grounding_pass_count": 6,
        "reproduced_grounding_failure_count": 29,
        "reproduced_leakage_denominator": 6,
        "reproduced_leakage_failure_count": 6,
        "quality_input_candidate_count_historical": 0,
        "quality_source_group_count_historical": 0,
        "deterministic_postcheck_reproduction_pass": True})
    obj("body_grounding_authority_timeline.json", {"layers": [
        {"stage": "alpha3.19 master", "artifact": ref(MASTER_BINDING),
         "representation": "Builder V3 and source_field=body"},
        {"stage": "alpha3.18A.1", "artifact": ref(GROUNDING_AUTHORITY),
         "representation": "BODY-only post-validation authority"},
        {"stage": "alpha3.18A.1", "artifact": ref(ANCHOR_AUTHORITY),
         "representation": "controller-derived paragraph anchor"},
        {"stage": "alpha3.18B.1", "artifact": ref(V3_CONTRACT),
         "representation": "body + exact_text + zero-based offsets"},
        {"stage": "alpha3.18B.1", "artifact": ref(V3_SCHEMA),
         "representation": "source_field body enum, exact_text, start_offset, end_offset"},
        {"stage": "alpha3.19E", "artifact": ref(f.e.OUT /
            "alpha3_19_builder_v3_request_manifest.jsonl"),
         "representation": "frozen exact BODY in 14 user messages"},
        {"stage": "alpha3.19F", "artifact": ref(GROUNDING_IMPLEMENTATION),
         "representation": "exact body substring then exactly one paragraph"}]})
    obj("builder_grounding_contract_consistency_matrix.json", {
        "frozen_system_prompt": ref(BUILDER_PROTOCOL),
        "frozen_user_template": ref(PROMPT_TEMPLATE),
        "v3_contract": ref(V3_CONTRACT), "v3_output_schema": ref(V3_SCHEMA),
        "validator_implementation": ref(GROUNDING_IMPLEMENTATION),
        "model_authored": ["source_field", "exact_text", "start_offset", "end_offset"],
        "controller_owned": ["frozen canonical body_text", "opaque source token",
                             "canonical paragraph boundaries"],
        "deterministically_derived": ["EvidenceSpanAnchorV1 span_id"],
        "model_authored_paragraph_or_anchor_id": False,
        "exact_copy_requirement": "EXACT_COPY_REQUIREMENT_EXPLICIT_AND_ALIGNED",
        "prompt_instruction": "exact source-local span, zero-based character offsets, body canonical text",
        "validator_rule": "body[start_offset:end_offset] == exact_text; one paragraph",
        "paragraph_rule_not_causing_observed_failures": True,
        "all_layers_same_evidence_representation": True})
    body_visibility = []
    for request in state["requests"]:
        token = request["source_token"]
        doc = json.loads((f.e.OUT / state["docs"][token]["document_path"]).read_bytes())
        user = request["request"]["messages"][1]["content"]
        visible = user.count("Body: " + doc["body_text"]) == 1
        body_visibility.append({"request_ordinal": request["ordinal"],
            "request_sha256": request["request_sha256"],
            "canonical_body_visible_exactly_once": visible,
            "document_sha256": state["docs"][token]["document_sha256"],
            "body_sha256": sha(doc["body_text"].encode())})
    require(all(row["canonical_body_visible_exactly_once"] for row in body_visibility),
            "CANONICAL_BODY_NOT_VISIBLE_TO_MODEL")
    obj("builder_request_body_visibility_audit.json", {"requests": body_visibility,
        "requests_with_required_body_surface_available": 14,
        "requests_without_required_body_surface_available": 0,
        "abstract_not_authoritative_grounding": True})
    lines("body_grounding_validator_replay.jsonl", grounding)
    taxonomy_counts = {name: taxonomy.get(name, 0) for name in (
        "SOURCE_FIELD_INVALID", "BODY_REFERENCE_NOT_FOUND", "EVIDENCE_TEXT_EXACT_MISMATCH",
        "OFFSET_MISMATCH", "PARAGRAPH_BOUNDARY_MISMATCH",
        "REFERENCE_SPANS_MULTIPLE_PARAGRAPHS", "REFERENCE_TO_NON_BODY",
        "MISSING_REFERENCE_COMPONENT", "OTHER_FROZEN_STRUCTURAL_FAILURE")}
    obj("body_grounding_failure_taxonomy.json", {"failure_count": 29,
        "taxonomy_counts": taxonomy_counts,
        "quote_exactly_and_uniquely_found_elsewhere_in_body": sum(
            row["taxonomy"] == "OFFSET_MISMATCH" and
            row["evidence_text_occurrence_count_in_body"] == 1 for row in failed),
        "all_quotes_fit_one_paragraph_at_actual_text_location": all(
            row["actual_text_fits_one_paragraph"] for row in failed),
        "historical_failure_states_rewritten": False})
    normalization_counts = {}
    for name in result["diagnostics"][0]["diagnostic_transformations"]:
        normalization_counts[name] = {"text_found_count": sum(
            row["diagnostic_transformations"][name]["text_found"]
            for row in result["diagnostics"]),
            "model_offset_matches_count": sum(
                row["diagnostic_transformations"][name]["candidate_offset_matches"]
                for row in result["diagnostics"])}
    obj("body_grounding_normalization_diagnostic.json", {"failed_candidate_count": 29,
        "diagnostic_only": True, "historical_states_unchanged": True,
        "raw_exact_text_already_found_count": sum(row["raw_exact_text_already_present"]
                                                   for row in result["diagnostics"]),
        "transformations": normalization_counts,
        "normalization_required_by_frozen_contract_but_omitted": False})
    obj("body_grounding_primary_classification.json", {"classification": grounding_class,
        "exact_copy_requirement": "EXACT_COPY_REQUIREMENT_EXPLICIT_AND_ALIGNED",
        "evidence_text_not_present_failures": 0,
        "model_authored_offset_mismatch_failures": 29,
        "validator_implementation_defect_proven": False,
        "contract_or_schema_mismatch_proven": False})
    obj("leakage_authority_timeline.json", {"layers": [
        {"stage": "alpha3.17A", "artifact": ref(LEAKAGE_AUTHORITY),
         "rule": "neutral proposition versus private title and evidence sentence"},
        {"stage": "alpha3.18B", "artifact": ref(f.POSTCHECK_DIR /
            "builder_leakage_execution_contract.json"),
         "rule": "same 8-token / Jaccard 0.80 gates"},
        {"stage": "alpha3.19 master", "artifact": ref(MASTER_POLICY),
         "rule": "thresholds unchanged"},
        {"stage": "alpha3.19F", "artifact": ref(POSTCHECK_IMPLEMENTATION),
         "rule": "neutral_proposition, private title, containing evidence sentence"},
        {"stage": "alpha3.19F", "artifact": ref(LEAKAGE_IMPLEMENTATION),
         "rule": "NFKC tokenization, 8-token or Jaccard >=0.80"}]})
    obj("leakage_comparator_input_surface_audit.json", {
        "candidate_input_fields": ["neutral_proposition"],
        "source_input_fields": ["private source title", "containing evidence sentence"],
        "candidate_evidence_exact_text_field_passed": False,
        "candidate_source_context_passed": False,
        "candidate_anchor_text_passed": False,
        "candidate_rationale_passed": False,
        "controller_metadata_passed": False,
        "frozen_contract_inputs_match_implementation": True})
    obj("leakage_candidate_surface_audit.json", {
        "frozen_intended_surface": "public neutral proposition",
        "actual_candidate_comparator_field": "neutral_proposition",
        "evidence_quote_separately_concatenated": False,
        "comparison_field_changed": False})
    scope_counts = Counter(row["source_sentence_scope"] for row in leakage)
    obj("leakage_source_surface_audit.json", {
        "frozen_source_surfaces": ["private source title", "evidence sentence"],
        "evidence_sentence_rule":
            "nearest . ! ? or LF; if evidence span crosses boundary, use entire canonical body",
        "actual_scope_counts": dict(sorted(scope_counts.items())),
        "full_body_used_only_under_frozen_ambiguous_sentence_fallback": True})
    obj("leakage_evidence_quote_contamination_audit.json", {
        "leakage_comparison_count": 6,
        "mandatory_evidence_exact_text_passed_as_candidate_side_input_count": 0,
        "source_sentence_contains_grounding_quote_count": 6,
        "model_proposition_itself_contains_exact_quote_count": sum(
            row["evidence_quote_verbatim_in_model_proposition"] for row in leakage),
        "mandatory_quote_self_comparison_injected_by_controller": False,
        "source_sentence_use_authorized_by_frozen_contract": True})
    lines("leakage_reference_implementation_results.jsonl", leakage)
    obj("leakage_trigger_accounting.json", {
        "denominator_body_grounding_passes": 6,
        "failed_by_8_token_rule_only": eight_only,
        "failed_by_jaccard_only": jaccard_only,
        "failed_by_both": both, "passed_both": passed,
        "reproduced_leakage_failure_count": eight_only + jaccard_only + both})
    obj("leakage_primary_classification.json", {"classification": leakage_class,
        "independent_reference_implementation_used": True,
        "all_six_production_decisions_reproduced": True,
        "comparator_input_surface_defect_proven": False,
        "tokenization_or_ngram_or_jaccard_defect_proven": False})
    obj("zero_quality_input_primary_classification.json", {"classification": combined,
        "grounding_classification": grounding_class,
        "leakage_classification": leakage_class,
        "historical_quality_input_count": 0,
        "offline_postcheck_replay_eligible": False,
        "future_quality_budget_historical": 0,
        "final_pool_derived": False})
    obj("quality_nonclaim_boundary.json", {"quality_calls": 0,
        "quality_rejected_candidate_count": None,
        "quality_acceptance_rate": None,
        "quality_input_candidate_count": 0,
        "quality_pass_or_fail_states_assigned": False})
    obj("final_pool_nonclaim_boundary.json", {"eligible_proposition_pool": "NOT_DERIVED",
        "final_pool_size": None, "heldout_cases_created": 0,
        "zero_deterministic_precheck_survivors_not_relabelled_as_final_pool": True})
    obj("scientific_content_nonuse_audit.json", {
        "scientific_content_used_for_policy_design": False,
        "candidate_string_structure_only_used": True,
        "scientific_quality_judgments": 0,
        "semantic_paraphrase_or_evidence_selection": False,
        "threshold_changes": 0, "candidate_repairs": 0})
    obj("historical_preservation_audit.json", {"alpha3_19f_root_before": F_SHA,
        "alpha3_19f_root_unchanged_after": f.root_hash() == F_SHA,
        "alpha3_19e1_root_unchanged_after": f.e1.root_hash() == E1_SHA,
        "builder_request_manifest_unchanged_after": sha((f.e.OUT /
            "alpha3_19_builder_v3_request_manifest.jsonl").read_bytes()) == REQUEST_SHA,
        "historical_builder_scientific_inference_events": 14,
        "historical_alpha3_18_builder_inference_events": 56,
        "historical_alpha3_18_quality_inference_events": 1,
        "historical_assets_modified": False})
    obj("scientific_state_safety_audit.json", {"builder_calls": 0,
        "quality_calls": 0, "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "builder_responses_regenerated": 0,
        "candidate_text_repaired": 0, "evidence_reanchored": 0,
        "source_topup": 0, "historical_assets_modified": False})
    obj("validation.json", {"status": "completed", "alpha3_19f_root_verified": True,
        "historical_builder_inference_events_preserved": True,
        "raw_candidate_count": 35,
        "reproduced_grounding_pass_count": 6,
        "reproduced_grounding_failure_count": 29,
        "grounding_authority_resolved": True,
        "exact_copy_requirement": "EXACT_COPY_REQUIREMENT_EXPLICIT_AND_ALIGNED",
        "grounding_primary_classification": grounding_class,
        "reproduced_leakage_denominator": 6,
        "reproduced_leakage_failure_count": 6,
        "failed_by_8_token_rule_only": eight_only,
        "failed_by_jaccard_only": jaccard_only,
        "failed_by_both": both, "passed_both": passed,
        "leakage_authority_resolved": True,
        "leakage_comparator_input_fields_resolved": True,
        "independent_leakage_reference_implementation_used": True,
        "leakage_primary_classification": leakage_class,
        "zero_quality_input_primary_classification": combined,
        "offline_postcheck_replay_eligible": False,
        "quality_input_candidate_count_historical": 0,
        "eligible_proposition_pool": "NOT_DERIVED",
        "builder_calls": 0, "quality_calls": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "scientific_content_used_for_policy_design": False,
        "next_stage_recommendation": next_stage,
        "historical_assets_modified": False})
    obj("summary.json", {"status": "completed", "grounding_primary_classification": grounding_class,
        "leakage_primary_classification": leakage_class,
        "zero_quality_input_primary_classification": combined,
        "raw_candidates": 35, "grounding_passes": 6,
        "grounding_failures": 29, "leakage_denominator": 6,
        "leakage_failures": 6,
        "offline_postcheck_replay_eligible": False,
        "quality_input_candidates_historical": 0,
        "next_stage_recommendation": next_stage})
    put(ROOT_MARKER, (root_hash() + "\n").encode())
    print(json.dumps({"status": "completed", "root_sha256": (OUT / ROOT_MARKER).read_text().strip(),
        "grounding_classification": grounding_class,
        "leakage_classification": leakage_class,
        "next_stage": next_stage}, sort_keys=True))


def main():
    state = preflight()
    result = replay(state)
    freeze(state, result)


if __name__ == "__main__":
    main()
