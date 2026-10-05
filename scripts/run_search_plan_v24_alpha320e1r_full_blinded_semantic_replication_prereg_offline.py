#!/usr/bin/env python3
"""Freeze a new complete blinded semantic replication, without provider calls."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from collections import Counter
from pathlib import Path

from scripts import run_search_plan_v24_alpha320e_semantic_adjudication_prereg_offline as e
from scripts import run_search_plan_v24_alpha320e1_semantic_adjudication_execution as e1
from scripts import run_search_plan_v24_alpha320e11_incomplete_semantic_response_audit_offline as e11


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/20261004_search_plan_v24_dev_alpha3_20e1r_full_blinded_semantic_replication_preregistration_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_20e1r_sha256"
E11_ROOT = "ae2f301c62c6b90b53aefbff2a6170a1761d30904483c23268c4a9cf4c867aa0"
CLASSIFICATION = "FULL_28_GROUP_BLINDED_SEMANTIC_REPLICATION_REQUESTS_FROZEN"
NEXT = "AUTHORIZE_EXACT_28_ALPHA3_20E1R1_FULL_BLINDED_SEMANTIC_REPLICATION_CALLS"
PRIVATE_FILES = ("replication_group_token_mapping_private.jsonl",
                 "replication_candidate_token_mapping_private.jsonl",
                 "replication_blinding_seed_private.json")
EXPLICIT_EXPERIMENTAL_MARKERS = (
    "ABSTRACTION_V1_RELATION_SENTENCE", "ABSTRACTION_V2_RELATION_FRAME",
    "relation sentence", "relation frame", "reference variant",
    "39/42", "37/42", "leakage survivor", "eight-token", "jaccard",
    "previous malformed", "previous adjudication", "previous execution failure",
    "which arm", "which prompt", "replication", "variant-selection",
)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def obj(path: Path) -> dict:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line]


def ref(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}


def put(name: str, value: object, *, private: bool = False) -> str:
    raw = canonical(value) + b"\n"
    path = OUT / name
    if private:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
    else:
        with path.open("xb") as handle:
            handle.write(raw)
    return sha(raw)


def put_rows(name: str, data: list[dict], *, private: bool = False) -> str:
    raw = b"".join(canonical(item) + b"\n" for item in data)
    path = OUT / name
    if private:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
    else:
        with path.open("xb") as handle:
            handle.write(raw)
    return sha(raw)


def marker(name: str, value: str) -> None:
    with (OUT / name).open("xb") as handle:
        handle.write((value + "\n").encode("ascii"))


def scientific_candidate(candidate: dict) -> dict:
    return {"neutral_proposition": candidate["neutral_proposition"],
            "exact_body_evidence_quote": candidate["exact_body_evidence_quote"]}


def science_fingerprint(context: dict, candidates: list[dict]) -> str:
    return sha(canonical({"source_context": context,
        "candidate_science_sha256_multiset": sorted(
            sha(canonical(scientific_candidate(item))) for item in candidates)}))


def no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("REPLICATION_RESPONSE_DUPLICATE_JSON_KEY:" + name)
        result[name] = value
    return result


def validate_replication_response(content: str | None, finish_reason: str,
                                  expected_tokens: list[str], schema: dict) -> tuple:
    """Frozen strict parser: no preprocessing, salvage, or scientific repair."""
    return e1.validate_response(content, finish_reason, expected_tokens, schema)


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA320E1R_OUTPUT_ALREADY_EXISTS")
    roots = ((e11.OUT, e11.ROOT_MARKER, E11_ROOT),
             (e1.OUT, e1.ROOT_MARKER, e11.E1_ROOT),
             (e.OUT, e.ROOT_MARKER, e1.E_ROOT))
    for directory, name, expected in roots:
        require((directory / name).read_text().strip() == expected
                and e.d.c.root_hash(directory, name) == expected,
                "UPSTREAM_FROZEN_ROOT_MISMATCH:" + name)
    frozen = (("development_semantic_fidelity_rubric_v1.json", e1.RUBRIC_SHA),
              ("development_semantic_adjudication_response_envelope_v1.json",
               e1.ENVELOPE_SHA),
              ("semantic_adjudication_prompt_template.txt", e1.PROMPT_SHA),
              ("semantic_adjudication_request_manifest.jsonl", e1.REQUEST_SHA))
    require(all(digest(e.OUT / name) == expected for name, expected in frozen),
            "FROZEN_SCIENTIFIC_OR_INTERFACE_INPUT_MISMATCH")
    e11_validation = obj(e11.OUT / "validation.json")
    e1_validation = obj(e1.OUT / "validation.json")
    require(e11_validation["semantic_response_invalidity_primary_classification"]
            == e11.CLASSIFICATION
            and e11_validation["offline_response_validation_replay_eligible"] is False
            and e11_validation["full_blinded_replication_authority"] == e11.REPLICATION
            and e11_validation["e1_judgments_selection_eligible"] is False
            and e11_validation["unblinding_performed"] is False
            and e1_validation["semantic_scientific_inference_events"] == 28
            and e1_validation["valid_semantic_group_count"] == 27
            and e1_validation["invalid_semantic_group_count"] == 1
            and e1_validation["unblinding_performed"] is False,
            "E1_QUARANTINE_OR_REPLICATION_AUTHORITY_MISMATCH")
    old_requests = rows(e.OUT / "semantic_adjudication_request_manifest.jsonl")
    old_group_tokens = {row["blinded_group_token"] for row in old_requests}
    old_candidate_tokens = {token for row in old_requests for token in
                            row["blinded_candidate_tokens_in_display_order"]}
    require(len(old_requests) == len(old_group_tokens) == 28
            and len(old_candidate_tokens) == 84, "OLD_REQUEST_UNIVERSE_MISMATCH")
    old_by_science = {}
    for row in old_requests:
        payload = json.loads(row["request"]["messages"][1]["content"].split(
            "\n", 1)[1])
        fingerprint = science_fingerprint(payload["source_context"],
                                          payload["candidates"])
        require(fingerprint not in old_by_science, "OLD_GROUP_SCIENCE_NOT_UNIQUE")
        old_by_science[fingerprint] = {"payload": payload,
            "display_science_hashes": [sha(canonical(scientific_candidate(item)))
                                       for item in payload["candidates"]]}
    # Reconstruct controller-only source/arm identity from the frozen Builder
    # candidate universe. E1 judgments and old private mappings are not read.
    d = e.d
    b = e.b
    c = e.c
    d.frozen_root(d.OUT, "search_plan_v24_dev_alpha3_20d_sha256", e.D_ROOT)
    identity_rows = rows(d.OUT / "alpha3_20d_candidate_identity_manifest.jsonl")
    candidate_rows = rows(c.OUT / "alpha3_20c_raw_candidate_manifest.jsonl")
    source_requests = rows(b.OUT / "alpha3_20c_combined_request_manifest.jsonl")
    documents = {row["source_token"]: row for row in rows(d.DOC_MANIFEST)}
    identity_by_cell = {(row["execution_ordinal"], row["raw_array_position"]): row
                        for row in identity_rows}
    require(len(identity_rows) == len(candidate_rows) == 126
            and len(identity_by_cell) == 126 and len(source_requests) == 42,
            "BUILDER_CANDIDATE_AUTHORITY_MISMATCH")
    raw_by_ordinal = {}
    for raw in candidate_rows:
        identity = identity_by_cell[(raw["execution_ordinal"],
                                     raw["raw_array_position"])]
        require(identity["candidate_payload_sha256"] == sha(canonical(raw[
            "candidate"])) and identity["variant_id"] == raw[
                "variant_id_controller_only"],
                "BUILDER_CANDIDATE_PAYLOAD_MISMATCH")
        raw_by_ordinal.setdefault(raw["execution_ordinal"], []).append(
            {"raw": raw, "identity": identity})
    source_groups = {}
    matched_old_fingerprints = set()
    for source_ordinal in range(1, 15):
        triple = source_requests[(source_ordinal - 1) * 3: source_ordinal * 3]
        source_token = triple[0]["private_source_token"]
        require([row["variant_index"] for row in triple] == [1, 2, 3]
                and all(row["source_ordinal"] == source_ordinal and
                        row["private_source_token"] == source_token for row in triple)
                and source_token in documents, "SOURCE_TRIPLE_MISMATCH")
        doc = documents[source_token]
        doc_path = d.E / doc["document_path"]
        require(digest(doc_path) == doc["document_sha256"],
                "SOURCE_DOCUMENT_CHANGED")
        content = obj(doc_path)
        context = {"abstract": content["abstract_text"],
                   "canonical_body": content["body_text"]}
        arms = {}
        for variant_index, variant in enumerate(d.VARIANT_IDS[:2], 1):
            original_ordinal = triple[variant_index - 1]["execution_ordinal"]
            members = sorted(raw_by_ordinal[original_ordinal],
                             key=lambda item: item["raw"]["raw_array_position"])
            require(len(members) == 3 and [item["raw"]["raw_array_position"]
                    for item in members] == [0, 1, 2]
                    and all(item["raw"]["variant_id_controller_only"] == variant
                            and item["raw"]["source_record_token"] == source_token
                            for item in members), "SOURCE_ARM_MEMBERS_MISMATCH")
            visible = [{"neutral_proposition": item["raw"]["candidate"][
                "neutral_proposition"],
                "exact_body_evidence_quote": item["raw"]["candidate"][
                    "construction_evidence_span"]["exact_text"]}
                for item in members]
            fingerprint = science_fingerprint(context, visible)
            require(fingerprint in old_by_science
                    and fingerprint not in matched_old_fingerprints,
                    "E_AND_UPSTREAM_SCIENTIFIC_GROUP_MISMATCH")
            matched_old_fingerprints.add(fingerprint)
            old = old_by_science[fingerprint]
            require(canonical(context) == canonical(old["payload"]["source_context"])
                    and sorted(sha(canonical(x)) for x in visible) == sorted(
                        old["display_science_hashes"]),
                    "E_SCIENTIFIC_CONTEXT_OR_CANDIDATES_CHANGED")
            arms[variant] = {"members": members, "visible_science": visible,
                             "old_display_science_hashes": old[
                                 "display_science_hashes"],
                             "fingerprint": fingerprint,
                             "original_builder_execution_ordinal": original_ordinal}
        source_groups[source_ordinal] = {"source_record_token": source_token,
            "context": context, "context_sha256": sha(canonical(context)),
            "arms": arms}
    require(len(source_groups) == 14 and len(matched_old_fingerprints) == 28,
            "SCIENTIFIC_UNIVERSE_NOT_EXACTLY_MATCHED")
    return {"source_groups": source_groups, "old_group_tokens": old_group_tokens,
            "old_candidate_tokens": old_candidate_tokens,
            "old_science_fingerprints": matched_old_fingerprints}


def envelope_v2() -> dict:
    historical = obj(e.OUT /
        "development_semantic_adjudication_response_envelope_v1.json")
    return {**historical,
        "schema_version": "DevelopmentSemanticAdjudicationResponseEnvelopeV2",
        "serialization_contract": {
            "one_top_level_json_object": True,
            "strict_json": True,
            "double_quoted_keys_and_string_values": True,
            "trailing_commas_allowed": False,
            "comments_allowed": False,
            "markdown_or_code_fences_allowed": False,
            "leading_or_trailing_prose_allowed": False,
            "all_brackets_and_braces_closed": True,
            "response_repair_allowed": False,
            "json_substring_extraction_allowed": False},
        "provider_response_format": {"type": "json_object"},
        "provider_native_json_schema_mode_activated": False}


def prompt_template() -> tuple[str, str, str]:
    historical = (e.OUT / "semantic_adjudication_prompt_template.txt").read_text(
        encoding="utf-8")
    science_prefix, old_format = historical.split("Return one JSON object", 1)
    require(old_format and science_prefix.startswith("SYSTEM:\n")
            and "Do not compare candidates" in science_prefix,
            "HISTORICAL_SCIENTIFIC_PROMPT_BOUNDARY_UNRESOLVED")
    # Only the serialization tail changes. No scientific definition changes.
    format_tail = (
        "Return exactly one strict JSON object. Use double-quoted JSON keys and "
        "double-quoted string values. Do not use trailing commas, comments, "
        "Markdown, code fences, leading prose, or trailing prose. Close every "
        "bracket and brace. Do not emit protocol metadata.\n"
        "The sole top-level key is candidate_reviews, an array of exactly three "
        "objects. Each review object has exactly candidate_token and criteria. "
        "The criteria object has exactly these six keys: " +
        ", ".join(e.CRITERIA) + ". Each criterion value is an object with "
        "exactly state and rationale; state is exactly PASS, FAIL, or "
        "UNRESOLVED and rationale is a nonempty string. Echo each supplied "
        "candidate token exactly once; add no other keys.\n"
        "USER:\n" + e.USER_PREFIX + "<BLINDED_PAYLOAD_JSON>\n")
    template = science_prefix + format_tail
    system, user = template.removeprefix("SYSTEM:\n").split("\nUSER:\n", 1)
    require(system.startswith(e.SYSTEM_PROMPT.split("Return one JSON object", 1)[0])
            and user == e.USER_PREFIX + "<BLINDED_PAYLOAD_JSON>\n",
            "SCIENTIFIC_PROMPT_PREFIX_DRIFT")
    return template, system, e.USER_PREFIX


def group_order(seed: bytes) -> list[tuple[int, str]]:
    # One source-major schedule, random source order, exactly seven first arms
    # of each type. This uses ordinals and a secret seed, never scientific text.
    source_order = sorted(range(1, 15), key=lambda ordinal:
        sha(seed + b"|replication-source-order|" + str(ordinal).encode()))
    first_arm_v1 = set(sorted(range(1, 15), key=lambda ordinal:
        sha(seed + b"|replication-first-arm|" + str(ordinal).encode()))[:7])
    result = []
    for ordinal in source_order:
        first = e.d.VARIANT_IDS[0] if ordinal in first_arm_v1 else e.d.VARIANT_IDS[1]
        second = e.d.VARIANT_IDS[1] if ordinal in first_arm_v1 else e.d.VARIANT_IDS[0]
        result.extend(((ordinal, first), (ordinal, second)))
    require(len(result) == 28
            and sum(result[2 * i][1] == e.d.VARIANT_IDS[0]
                    for i in range(14)) == 7,
            "REPLICATION_EXECUTION_ORDER_BALANCE_FAILED")
    return result


def candidate_permutation(seed: bytes, group_token: str,
                          old_display_hashes: list[str],
                          raw_science_hashes: list[str]) -> list[int]:
    order = sorted(range(3), key=lambda index: sha(
        seed + b"|replication-candidate-order|" + group_token.encode()
        + b"|" + str(index).encode()))
    if [raw_science_hashes[index] for index in order] == old_display_hashes:
        order = order[1:] + order[:1]
    require(sorted(order) == [0, 1, 2]
            and [raw_science_hashes[index] for index in order]
                != old_display_hashes, "CANDIDATE_PERMUTATION_NOT_FRESH")
    return order


def build(state: dict, seed: bytes) -> dict:
    template, system, user_prefix = prompt_template()
    old_groups = state["old_group_tokens"]
    old_candidates = state["old_candidate_tokens"]
    group_mapping, candidate_mapping, permutations = [], [], []
    request_rows, order_rows, context_rows, equivalence_rows = [], [], [], []
    new_groups, new_candidates = set(), set()
    for ordinal, (source_ordinal, variant) in enumerate(group_order(seed), 1):
        source = state["source_groups"][source_ordinal]
        arm = source["arms"][variant]
        group_token = "rsg_" + secrets.token_hex(16)
        require(group_token not in old_groups and group_token not in new_groups,
                "REPLICATION_GROUP_TOKEN_COLLISION")
        new_groups.add(group_token)
        raw_hashes = [sha(canonical(item)) for item in arm["visible_science"]]
        order = candidate_permutation(seed, group_token,
            arm["old_display_science_hashes"], raw_hashes)
        tokened = []
        for raw_position, item in enumerate(arm["members"]):
            token = "rsc_" + secrets.token_hex(16)
            require(token not in old_candidates and token not in new_candidates,
                    "REPLICATION_CANDIDATE_TOKEN_COLLISION")
            new_candidates.add(token)
            tokened.append({"token": token, "item": item,
                            "science": arm["visible_science"][raw_position]})
        visible = [{"candidate_token": tokened[index]["token"],
                    **tokened[index]["science"]} for index in order]
        payload = {"blinded_group_token": group_token,
                   "source_context": source["context"], "candidates": visible}
        request = {"model": "deepseek-flash",
            "thinking": {"type": "enabled"}, "reasoning_effort": "high",
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user_prefix +
                          canonical(payload).decode("utf-8")}]}
        request_sha = sha(canonical(request))
        request_rows.append({"future_execution_ordinal": ordinal,
            "blinded_group_token": group_token,
            "blinded_candidate_tokens_in_display_order": [
                item["candidate_token"] for item in visible],
            "request": request, "request_sha256": request_sha,
            "historical_role": "SEEN_DEVELOPMENT_HISTORY"})
        order_rows.append({"future_execution_ordinal": ordinal,
            "blinded_group_token": group_token,
            "request_sha256": request_sha})
        group_mapping.append({"future_execution_ordinal": ordinal,
            "blinded_group_token": group_token,
            "source_ordinal_private": source_ordinal,
            "source_record_token_private": source["source_record_token"],
            "private_variant_id": variant,
            "alpha3_20c_execution_ordinal": arm[
                "original_builder_execution_ordinal"],
            "source_context_sha256": source["context_sha256"],
            "request_sha256": request_sha})
        permutations.append({"blinded_group_token": group_token,
            "display_order_original_positions": order,
            "differs_from_e1_candidate_order": True,
            "candidate_meaning_or_e1_judgment_used": False,
            "seed_sha256": sha(seed)})
        for position, entry in enumerate(tokened):
            identity = entry["item"]["identity"]
            candidate_mapping.append({"blinded_group_token": group_token,
                "blinded_candidate_token": entry["token"],
                "development_candidate_id": identity["development_candidate_id"],
                "candidate_payload_sha256": identity["candidate_payload_sha256"],
                "source_record_token_private": source["source_record_token"],
                "private_variant_id": variant,
                "raw_array_position": position,
                "blinded_display_position": order.index(position)})
        equivalence_rows.append({"blinded_group_token": group_token,
            "scientific_group_fingerprint_sha256": arm["fingerprint"],
            "exactly_matches_one_e_group": True,
            "source_context_sha256": source["context_sha256"],
            "candidate_science_sha256_multiset": sorted(raw_hashes),
            "scientific_content_changed": False})
    for source_ordinal, source in state["source_groups"].items():
        pair = [row for row in group_mapping if row["source_ordinal_private"]
                == source_ordinal]
        require(len(pair) == 2
                and pair[0]["source_context_sha256"] ==
                    pair[1]["source_context_sha256"] ==
                    source["context_sha256"], "SOURCE_CONTEXT_PAIR_MISMATCH")
        context_rows.append({"source_context_sha256": source["context_sha256"],
            "blinded_group_tokens": [row["blinded_group_token"] for row in pair],
            "scientific_context_byte_equivalent": True,
            "e_scientific_context_equivalent": True})
    require(len(request_rows) == len(order_rows) == len(group_mapping) ==
            len(permutations) == len(equivalence_rows) == 28
            and len(candidate_mapping) == len(new_candidates) == 84
            and len(context_rows) == 14
            and len({row["scientific_group_fingerprint_sha256"] for row in
                     equivalence_rows}) == 28,
            "REPLICATION_GROUP_OR_CANDIDATE_COUNT_MISMATCH")
    wrapper = system + user_prefix
    require(not any(mark.lower() in wrapper.lower() for mark in
                    EXPLICIT_EXPERIMENTAL_MARKERS),
            "MODEL_VISIBLE_EXPERIMENTAL_WRAPPER_LEAK")
    return locals()


def freeze(state: dict, built: dict, seed: bytes) -> dict:
    OUT.mkdir()
    put("alpha3_20e11_root_verification.json", {"verified": True,
        "root_sha256": E11_ROOT})
    put("alpha3_20e1_root_verification.json", {"verified": True,
        "root_sha256": e11.E1_ROOT})
    put("alpha3_20e_root_verification.json", {"verified": True,
        "root_sha256": e1.E_ROOT})
    put("e1_quarantine_binding.json", {"e1_judgments_selection_eligible": False,
        "state": "SEEN_DEVELOPMENT_INCOMPLETE_EXPERIMENT_NOT_SELECTION_ELIGIBLE",
        "e1_root_sha256": e11.E1_ROOT,
        "e1_judgments_used_in_replication_requests": False,
        "e1_judgments_may_substitute_for_replication_responses": False,
        "e1_inference_events_preserved": 28})
    put("replication_development_identity.json", {
        "classification": "POST_ALPHA3_19_SEEN_DATA_DEVELOPMENT_FULL_BLINDED_SEMANTIC_REPLICATION_PREREGISTRATION",
        "development_only": True, "fresh_heldout": False,
        "continuation_or_repair_of_e1": False,
        "new_standalone_experiment": True})
    put("replication_semantic_universe_verification.json", {
        "v1_candidate_count_controller_private": 42,
        "v2_candidate_count_controller_private": 42,
        "v3_candidate_count": 0, "total_candidate_count": 84,
        "source_count": 14, "group_count": 28,
        "exact_scientific_group_fingerprint_set_equal_to_e": True,
        "frozen_e_request_manifest_sha256": e1.REQUEST_SHA,
        "candidate_additions_or_removals": 0})
    put("replication_scientific_policy_equivalence.json", {
        "scientific_rubric_changed": False,
        "scientific_candidate_content_changed": False,
        "scientific_source_context_changed": False,
        "candidate_overall_state_derivation_changed": False,
        "semantic_dominance_rule_changed": False,
        "selection_policy_changed": False,
        "leakage_result_changed": False,
        "scientific_fidelity_precedence_changed": False,
        "permitted_deltas_only": ["new opaque identifiers",
            "non-scientific permutations", "new execution order",
            "strict JSON serialization instructions", "ResponseEnvelopeV2 interface"]})
    put_rows("replication_scientific_context_equivalence.jsonl",
             built["equivalence_rows"])
    put("development_semantic_fidelity_rubric_v1_binding.json", {
        "rubric": ref(e.OUT / "development_semantic_fidelity_rubric_v1.json"),
        "unchanged": True, "criterion_count": 6,
        "states": list(e.STATES)})
    for output, source in (
        ("semantic_candidate_overall_state_derivation_binding.json",
         "semantic_candidate_overall_state_derivation.json"),
        ("semantic_dominance_rule_binding.json",
         "semantic_variant_dominance_rule.json"),
        ("semantic_variant_selection_rule_binding.json",
         "semantic_variant_selection_rule.json")):
        put(output, {"frozen_authority": ref(e.OUT / source),
                     "rule_changed": False,
                     "application_deferred_until_complete_valid_replication": True})
    envelope = envelope_v2()
    envelope_sha = put("development_semantic_adjudication_response_envelope_v2.json",
                       envelope)
    marker("development_semantic_adjudication_response_envelope_v2_sha256",
           envelope_sha)
    put("replication_serialization_hardening_delta.json", {
        "historical_envelope_v1_sha256": e1.ENVELOPE_SHA,
        "model_owned_scientific_schema_identical_to_v1":
            envelope["model_owned_payload_schema"] == obj(e.OUT /
                "development_semantic_adjudication_response_envelope_v1.json")[
                    "model_owned_payload_schema"],
        "scientific_prompt_prefix_identical_to_v1": True,
        "added_explicit_strict_json_rules": ["double quotes", "no trailing comma",
            "no comments", "no markdown or fences", "no prose",
            "close braces and brackets"],
        "provider_native_json_schema_mode_activated": False,
        "provider_capability_network_test_performed": False,
        "scientific_rule_change": False})
    put("replication_strict_json_contract.json", envelope[
        "serialization_contract"])
    put("replication_parser_contract.json", {
        "implementation_entrypoint": "scripts.run_search_plan_v24_alpha320e1r_full_blinded_semantic_replication_prereg_offline.validate_replication_response",
        "underlying_production_validator": "scripts.run_search_plan_v24_alpha320e1_semantic_adjudication_execution.validate_response",
        "underlying_validator_source_sha256": digest(ROOT /
            "scripts/run_search_plan_v24_alpha320e1_semantic_adjudication_execution.py"),
        "strict_json_parse": True, "duplicate_keys_rejected": True,
        "whole_content_only": True, "substring_extraction": False,
        "fence_or_prose_stripping": False, "trailing_comma_or_brace_repair": False,
        "non_enum_normalization": False, "candidate_token_exact_set": True,
        "schema": ref(OUT /
            "development_semantic_adjudication_response_envelope_v2.json"),
        "invalid_completed_response_action": "COUNT_INFERENCE_RECORD_INVALID_NO_RETRY"})
    put("replication_blinding_seed_private.json", {"seed_hex": seed.hex(),
        "seed_sha256": sha(seed),
        "group_order_algorithm": "SHA256(seed|replication-source-order|ordinal), balanced SHA256(seed|replication-first-arm|ordinal)",
        "candidate_order_algorithm": "SHA256(seed|replication-candidate-order|new_group_token|raw_position); rotate if equal to E order"},
        private=True)
    group_map_sha = put_rows("replication_group_token_mapping_private.jsonl",
                             built["group_mapping"], private=True)
    candidate_map_sha = put_rows("replication_candidate_token_mapping_private.jsonl",
                                 built["candidate_mapping"], private=True)
    put_rows("replication_candidate_order_permutation.jsonl",
             built["permutations"])
    put("replication_group_execution_order.json", {
        "group_count": 28, "balanced_first_arm_counts_private": [7, 7],
        "scientific_content_used_for_order": False,
        "blinded_execution_ordinals": built["order_rows"],
        "seed_private_artifact_sha256": digest(OUT /
            "replication_blinding_seed_private.json")})
    put("replication_blinding_contract.json", {
        "fresh_group_tokens": 28, "fresh_candidate_tokens": 84,
        "old_group_tokens_reused": False, "old_candidate_tokens_reused": False,
        "variant_identity_exposed_to_model": False,
        "leakage_result_exposed_to_model": False,
        "e1_judgment_exposed_to_model": False,
        "private_group_mapping_sha256": group_map_sha,
        "private_candidate_mapping_sha256": candidate_map_sha,
        "old_private_mappings_read": False,
        "model_receives_one_group_per_independent_request": True})
    put_rows("replication_source_context_equivalence_audit.jsonl",
             built["context_rows"])
    prompt_sha = sha(built["template"].encode("utf-8"))
    with (OUT / "replication_semantic_adjudication_prompt_template.txt").open(
            "xb") as handle:
        handle.write(built["template"].encode("utf-8"))
    marker("replication_semantic_adjudication_prompt_template_sha256", prompt_sha)
    manifest_sha = put_rows("replication_semantic_adjudication_request_manifest.jsonl",
                            built["request_rows"])
    marker("replication_semantic_adjudication_request_manifest_sha256",
           manifest_sha)
    old_policy = obj(e.OUT / "semantic_adjudication_runtime_policy.json")
    require(old_policy["provider"] == "DeepSeek"
            and old_policy["model"] == "deepseek-flash"
            and old_policy["thinking"] == {"type": "enabled"}
            and old_policy["reasoning_effort"] == "high"
            and old_policy["response_format"] == {"type": "json_object"},
            "PROVIDER_POLICY_DRIFT")
    put("replication_runtime_policy.json", {**old_policy,
        "calls_authorized_in_alpha3_20e": 0,
        "calls_authorized_in_alpha3_20e1r": 0,
        "one_fresh_independent_context_per_group": True,
        "scientific_inference_attempts_per_group_maximum": 1,
        "completed_schema_invalid_action": "COUNT_INFERENCE_RECORD_INVALID_NO_SCIENTIFIC_RETRY",
        "automatic_retry": False,
        "zero_result_dependent_prompt_adaptation": True,
        "parser_contract": ref(OUT / "replication_parser_contract.json")})
    put("replication_call_budget.json", {
        "planned_replication_semantic_groups": 28,
        "planned_replication_semantic_candidates": 84,
        "planned_replication_semantic_scientific_calls": 28,
        "calls_authorized_now": 0,
        "separate_execution_authorization_required": True,
        "one_scientific_inference_per_group": True,
        "completed_invalid_response_scientific_retry_allowed": False})
    put("replication_completeness_contract.json", {
        "valid_group_requirement": 28,
        "valid_candidate_judgment_set_requirement": 84,
        "provider_execution_ambiguity_requirement": 0,
        "partial_selection_allowed": False,
        "completed_invalid_group_replacement_allowed": False})
    put("replication_dataset_independence_contract.json", {
        "replication_dataset_may_mix_with_e1": False,
        "new_valid_response_required_for_each_of_28_groups": True,
        "e1_valid_response_reuse_for_selection": False,
        "best_of_two_selection": False})
    put("e1_judgment_nonuse_audit.json", {
        "e1_raw_judgment_manifest_read": False,
        "e1_response_scientific_content_read": False,
        "e1_valid_27_group_judgments_used": False,
        "e1_invalid_group_used_to_select_scientific_content": False,
        "e1_historical_protocol_metadata_used_only_for_serialization": True})
    put("replication_scientific_nonadaptation_audit.json", {
        "pass_fail_unresolved_judgments_used": False,
        "rationales_used": False, "per_source_e1_semantic_outcomes_used": False,
        "source_scientific_context_exactly_matches_e": True,
        "candidate_scientific_content_exactly_matches_e": True,
        "only_serialization_interface_hardened": True})
    put("replication_future_unblinding_handoff_contract.json", {
        "execution_stops_after_raw_blinded_response_freeze": True,
        "unblind_only_after_28_valid_groups_and_84_valid_candidate_sets": True,
        "candidate_overall_state_derived_only_in_later_offline_stage": True,
        "e1_judgments_excluded": True,
        "variant_selection_deferred": True})
    put("development_contamination_binding.json", {
        "historical_role": "SEEN_DEVELOPMENT_HISTORY",
        "fresh_heldout_claim": False,
        "new_scientific_sources": 0,
        "future_outputs_join_seen_development_history": True,
        "e1_incomplete_judgments_remain_provenance_only": True})
    put("active_deepseek_model_audit.json", {
        "provider": "DeepSeek", "model": "deepseek-flash",
        "thinking": {"type": "enabled"}, "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        "provider_native_schema_mode": False,
        "fallback_model_or_provider": False, "provider_calls": 0})
    put("historical_inference_accounting.json", {
        "alpha3_18_builder": 56, "alpha3_18_quality": 1,
        "alpha3_19_builder": 14, "alpha3_19_quality": 0,
        "alpha3_20c_builder_v4_development": 42,
        "alpha3_20e1_semantic_adjudication": 28,
        "alpha3_20e1r_new_scientific_inference_events": 0,
        "provider_calls": 0, "deepseek_calls": 0, "llm_calls": 0,
        "network_calls": 0, "builder_calls": 0, "quality_calls": 0})
    upstream_roots = ((e11.OUT, e11.ROOT_MARKER, E11_ROOT),
                      (e1.OUT, e1.ROOT_MARKER, e11.E1_ROOT),
                      (e.OUT, e.ROOT_MARKER, e1.E_ROOT))
    require(all(e.d.c.root_hash(directory, name) == value for
                directory, name, value in upstream_roots),
            "HISTORICAL_ROOT_CHANGED_DURING_FREEZE")
    put("historical_preservation_audit.json", {
        "upstream_root_hashes_verified_before_and_after": True,
        "upstream_roots": {name: value for _, name, value in upstream_roots},
        "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {
        "unblinding_performed": False,
        "candidate_overall_state_derived": False,
        "arm_aggregation_performed": False,
        "semantic_dominance_evaluated": False,
        "variant_selection_performed": False,
        "e1_group_12_retry_performed": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0})
    require(all(stat.S_IMODE((OUT / name).stat().st_mode) & 0o077 == 0
                for name in PRIVATE_FILES), "PRIVATE_MAPPING_PERMISSIONS_INVALID")
    validation = {"status": "completed",
        "alpha3_20e1r_classification": CLASSIFICATION,
        "alpha3_20e11_root_verified": True,
        "alpha3_20e1_root_verified": True,
        "e1_judgments_selection_eligible": False,
        "replication_dataset_may_mix_with_e1": False,
        "replication_v1_candidate_count": 42,
        "replication_v2_candidate_count": 42,
        "replication_candidate_count": 84,
        "replication_group_count": 28,
        "replication_candidates_per_group": 3,
        "scientific_rubric_changed": False,
        "scientific_candidate_content_changed": False,
        "scientific_source_context_changed": False,
        "semantic_dominance_rule_changed": False,
        "selection_policy_changed": False,
        "response_envelope_v2_frozen": True,
        "development_semantic_adjudication_response_envelope_v2_sha256":
            envelope_sha,
        "strict_json_required": True,
        "trailing_commas_allowed": False,
        "markdown_allowed": False,
        "leading_or_trailing_prose_allowed": False,
        "response_repair_allowed": False,
        "e1_group_tokens_reused": False,
        "e1_candidate_tokens_reused": False,
        "variant_identity_exposed_to_model": False,
        "leakage_result_exposed_to_model": False,
        "e1_judgment_exposed_to_model": False,
        "replication_semantic_adjudication_prompt_template_sha256": prompt_sha,
        "replication_semantic_adjudication_request_manifest_sha256": manifest_sha,
        "planned_replication_semantic_calls": 28,
        "provider": "DeepSeek", "model": "deepseek-flash",
        "provider_calls": 0, "deepseek_calls": 0,
        "llm_calls": 0, "network_calls": 0,
        "builder_calls": 0, "quality_calls": 0,
        "next_stage_recommendation": NEXT,
        "historical_assets_modified": False}
    put("validation.json", validation)
    put("summary.json", {"status": "completed",
        "classification": CLASSIFICATION,
        "replication_group_count": 28,
        "replication_candidate_count": 84,
        "provider_calls": 0,
        "next_stage_recommendation": NEXT})
    root = e.d.c.root_hash(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    return {**validation, "search_plan_v24_dev_alpha3_20e1r_sha256": root}


def run() -> dict:
    state = preflight()
    seed = secrets.token_bytes(32)
    built = build(state, seed)
    return freeze(state, built, seed)


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
