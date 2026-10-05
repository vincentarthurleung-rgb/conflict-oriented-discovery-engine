#!/usr/bin/env python3
"""Offline, seen-data Builder V4 evaluation; no semantic or provider calls."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from scripts import run_search_plan_v24_alpha320c_builder_v4_execution as c
from scripts.search_plan_v24_alpha317a_safety_audits import leakage_failed, tokens
from scripts.search_plan_v24_alpha317c_reconcile_builder_offline import candidate_id
from scripts.search_plan_v24_alpha318b_post_builder_prechecks import (
    evidence_sentence, private_identity_from_jats, validate_builder_response)
from scripts.search_plan_v24_alpha320a_v4_localizer import (
    SUCCESS, localize_exact_body_quote)


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
B = c.B
C = c.OUT
A = RUNS / "20261002_search_plan_v24_dev_alpha3_20a_evidence_reference_v4_offline_validation"
E = RUNS / "20261002_search_plan_v24_dev_alpha3_19e_construction_document_anchor_builder_freeze_offline"
D = RUNS / "20261002_search_plan_v24_dev_alpha3_19d_pmc_oa_jats_construction_eligibility"
D1 = RUNS / "20261002_search_plan_v24_dev_alpha3_19d1_updateof_resolution_offline"
OUT = RUNS / "20261003_search_plan_v24_dev_alpha3_20d_deterministic_variant_evaluation_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_20d_sha256"
C_ROOT = "51a78a802f8fdab234f2e0b962e69067ca0f9db53ee11822a195cffe523713f0"
A_ROOT = "ecc4549aca4329ac3a910fc933f070333175ec2aa2c0fc728cd1279d9e274364"
JATS_SOURCE_MANIFEST = D1 / "final_construction_source_manifest.jsonl"
DOC_MANIFEST = E / "construction_document_manifest.jsonl"
VARIANT_IDS = ("ABSTRACTION_V1_RELATION_SENTENCE",
               "ABSTRACTION_V2_RELATION_FRAME",
               "ABSTRACTION_V3_CONTEXT_FIRST")
VARIANT_SHORT = {value: f"V{index}" for index, value in enumerate(VARIANT_IDS, 1)}
STRUCTURE_KEYS = ("actor_or_intervention", "action", "response_or_endpoint",
                  "biological_unit")
CONTEXT_KEYS = ("species", "intrinsic_conditioning", "intrinsic_therapy_context",
                "intrinsic_disease_or_genotype_context")
NEXT_E = "PREREGISTER_ALPHA3_20E_DEVELOPMENT_SEMANTIC_ADJUDICATION"
NEXT_F = "PREREGISTER_ALPHA3_20F_FINAL_BUILDER_V4_CONTRACT_FREEZE"
NEXT_NONE = "DESIGN_NEW_SEEN_DATA_DEVELOPMENT_PROTOCOL_AFTER_ALPHA3_20D_NO_ELIGIBLE_VARIANT"


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def obj(path: Path) -> dict:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line]


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


def ref(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}


def frozen_root(directory: Path, marker: str, expected: str) -> None:
    require((directory / marker).read_text().strip() == expected
            and c.root_hash(directory, marker) == expected,
            "FROZEN_ROOT_MISMATCH:" + directory.name)


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA320D_OUTPUT_ALREADY_EXISTS_NO_REWRITE")
    frozen_root(C, "search_plan_v24_dev_alpha3_20c_sha256", C_ROOT)
    frozen_root(B, "search_plan_v24_dev_alpha3_20b_sha256", c.B_ROOT)
    frozen_root(A, "search_plan_v24_dev_alpha3_20a_sha256", A_ROOT)
    for name, expected in (("builder_grounding_contract_v4", c.GROUNDING_SHA),
                           ("builder_output_schema_v4", c.SCHEMA_SHA)):
        require(digest(B / (name + ".json")) == expected
                and (B / (name + "_sha256")).read_text().strip() == expected,
                "V4_CONTRACT_HASH_MISMATCH:" + name)
    authority_names = (
        "variant_evaluation_dimensions.json",
        "structural_completeness_contract.json",
        "variant_eligibility_rule.json",
        "variant_selection_decision_tree.json",
        "semantic_adjudication_trigger.json",
        "leakage_policy_preservation.json",
    )
    authorities = {name: obj(B / name) for name in authority_names}
    grounding = obj(B / "builder_grounding_contract_v4.json")
    localizer_ref = grounding["localizer_implementation"]
    require(digest(ROOT / localizer_ref["path"]) == localizer_ref["sha256"],
            "V4_LOCALIZER_IMPLEMENTATION_CHANGED")
    leakage_policy = authorities["leakage_policy_preservation.json"]
    require(leakage_policy["candidate_side"] == "neutral_proposition only"
            and leakage_policy["eight_consecutive_shared_token_failure_threshold"] == 8
            and leakage_policy["qualifying_token_jaccard_failure_threshold"] == 0.8
            and leakage_policy["thresholds_changed"] is False
            and leakage_policy["comparison_policy_changed"] is False,
            "FROZEN_LEAKAGE_POLICY_MISMATCH")
    master_ref = leakage_policy["master_policy"]
    require(digest(ROOT / master_ref["path"]) == master_ref["sha256"],
            "FROZEN_MASTER_LEAKAGE_POLICY_MISMATCH")
    historical_leakage = RUNS / "20261001_search_plan_v24_dev_alpha3_18b_builder_execution_preregistration_offline/builder_leakage_execution_contract.json"
    old_contract = obj(historical_leakage)
    for binding in (old_contract["implementation"], old_contract["sentence_and_stage_helper"]):
        require(digest(ROOT / binding["path"]) == binding["sha256"],
                "FROZEN_LEAKAGE_IMPLEMENTATION_CHANGED")
    require(old_contract["shared_consecutive_tokens_failure_threshold"] == 8
            and old_contract["qualifying_token_jaccard_failure_threshold"] == 0.8,
            "FROZEN_LEAKAGE_CONTRACT_CHANGED")
    structure = authorities["structural_completeness_contract.json"]
    eligibility = authorities["variant_eligibility_rule.json"]
    decision = authorities["variant_selection_decision_tree.json"]
    trigger = authorities["semantic_adjudication_trigger.json"]
    require(structure["mechanical_presence_proves_scientific_truth"] is False
            and eligibility["reference_variant"] == VARIANT_IDS[0]
            and eligibility["per_request_nonregression"].startswith("a source covered")
            and eligibility["aggregate_nonregression"].startswith("total candidate count")
            and eligibility["leakage_compared_only_after_non_leakage_eligibility"] is True
            and eligibility["weighted_score"] is None
            and decision["tie_break_order"] == list(VARIANT_IDS)
            and decision["weighted_score"] is None
            and "scientific-fidelity comparison" in trigger["trigger"],
            "FROZEN_VARIANT_POLICY_AUTHORITY_UNRESOLVED")
    candidate_rows = rows(C / "alpha3_20c_raw_candidate_manifest.jsonl")
    request_rows = rows(B / "alpha3_20c_combined_request_manifest.jsonl")
    raw_rows = rows(C / "alpha3_20c_raw_provider_responses.jsonl")
    terminal_rows = rows(C / "alpha3_20c_cell_terminal_states.jsonl")
    valid_rows = rows(C / "alpha3_20c_response_schema_validation.jsonl")
    complete_rows = rows(C / "alpha3_20c_complete_triplet_manifest.jsonl")
    require(digest(B / "alpha3_20c_combined_request_manifest.jsonl") == c.REQUEST_SHA
            and len(candidate_rows) == 126
            and len(request_rows) == len(raw_rows) == len(terminal_rows) == len(valid_rows) == 42
            and len(complete_rows) == 14
            and all(r["terminal_state"] == "COMPLETED_SCHEMA_VALID_NONZERO"
                    for r in terminal_rows)
            and all(r["status"] == "BUILDER_V4_SCHEMA_VALID" for r in valid_rows)
            and sum(r["candidate_count"] for r in valid_rows) == 126,
            "ALPHA320C_CANDIDATE_UNIVERSE_MISMATCH")
    expected_raw = obj(C / "validation.json")
    require(expected_raw["raw_candidate_count"] == 126
            and expected_raw["complete_variant_triplet_count"] == 14
            and expected_raw["builder_scientific_inference_events"] == 42,
            "ALPHA320C_RUNTIME_ACCOUNTING_MISMATCH")
    request_by_ordinal = {r["execution_ordinal"]: r for r in request_rows}
    raw_by_ordinal = {r["execution_ordinal"]: r for r in raw_rows}
    parsed_by_ordinal = {}
    v4_schema = obj(B / "builder_output_schema_v4.json")["schema"]
    for ordinal in range(1, 43):
        request = request_by_ordinal[ordinal]
        raw = raw_by_ordinal[ordinal]
        require(raw["request_sha256"] == request["request_sha256"]
                and raw["source_record_token"] == request["private_source_token"]
                and raw["variant_id_controller_only"] == request[
                    "variant_id_controller_only"]
                and raw["scientific_inference_confirmed"] is True,
                "RAW_RESPONSE_REQUEST_BINDING_MISMATCH")
        parsed = validate_builder_response(raw["model_content_raw"].encode("utf-8"),
            request["private_source_token"], v4_schema)
        require(len(parsed["candidates"]) == valid_rows[ordinal - 1]["candidate_count"],
                "RAW_RESPONSE_CANDIDATE_COUNT_MISMATCH")
        parsed_by_ordinal[ordinal] = parsed
    counters = Counter()
    for raw_candidate in candidate_rows:
        ordinal = raw_candidate["execution_ordinal"]
        request = request_by_ordinal[ordinal]
        position = raw_candidate["raw_array_position"]
        require(raw_candidate["source_record_token"] == request["private_source_token"]
                and raw_candidate["variant_id_controller_only"] == request[
                    "variant_id_controller_only"]
                and raw_candidate["candidate"] == parsed_by_ordinal[ordinal][
                    "candidates"][position], "RAW_CANDIDATE_RESPONSE_BINDING_MISMATCH")
        counters[raw_candidate["variant_id_controller_only"]] += 1
    require([counters[v] for v in VARIANT_IDS] == [42, 42, 42],
            "PER_VARIANT_CANDIDATE_COUNT_MISMATCH")
    docs = {r["source_token"]: r for r in rows(DOC_MANIFEST)}
    sources = {r["opaque_source_token"]: r for r in rows(JATS_SOURCE_MANIFEST)}
    require(len(docs) == 14 and all(token in sources for token in docs),
            "FROZEN_SOURCE_DOCUMENT_BINDING_MISMATCH")
    inputs = {}
    for token, doc_row in docs.items():
        document_path = E / doc_row["document_path"]
        source = sources[token]
        jats_path = D / source["normalized_jats_path"]
        require(digest(document_path) == doc_row["document_sha256"]
                and digest(jats_path) == source["normalized_jats_sha256"],
                "FROZEN_DOCUMENT_OR_JATS_HASH_MISMATCH")
        document = obj(document_path)
        private = private_identity_from_jats(jats_path.read_bytes(), source["pmid"],
                                             source["pmcid"], source.get("doi"))
        require(document["article_title_visible"] is False
                and document["bibliography_visible"] is False
                and private["title_1"], "PRIVATE_TITLE_OR_INPUT_BOUNDARY_MISMATCH")
        inputs[token] = {"document": document, "private_title": private["title_1"],
                         "document_ref": ref(document_path),
                         "jats_ref": ref(jats_path)}
    return locals()


def structural_result(candidate: dict, schema: dict) -> dict:
    failures = []
    for key in STRUCTURE_KEYS:
        if not isinstance(candidate.get(key), str) or not candidate[key]:
            failures.append("REQUIRED_NONEMPTY_FIELD:" + key)
    direction_enum = schema["properties"]["candidates"]["items"]["properties"][
        "relation_direction"]["enum"]
    if candidate.get("relation_direction") not in direction_enum:
        failures.append("RELATION_DIRECTION_NOT_IN_FROZEN_ENUM")
    for key in CONTEXT_KEYS:
        if key not in candidate or not (candidate[key] is None or
                                        isinstance(candidate[key], str)):
            failures.append("REQUIRED_NULLABLE_CONTEXT_FIELD:" + key)
    return {"structural_state": "STRUCTURALLY_COMPLETE" if not failures else
            "STRUCTURALLY_INCOMPLETE", "failure_reasons": failures,
            "semantic_scientific_fidelity_established": False}


def _longest_common_run(left: list[str], right: list[str]) -> int:
    previous = [0] * (len(right) + 1)
    longest = 0
    for ltoken in left:
        current = [0] * (len(right) + 1)
        for j, rtoken in enumerate(right, 1):
            if ltoken == rtoken:
                current[j] = previous[j - 1] + 1
                longest = max(longest, current[j])
        previous = current
    return longest


def production_leakage_metrics(proposition: str, title: str, sentence: str) -> dict:
    candidate = tokens(proposition)
    maximum = 0
    jaccards = []
    for source in (title, sentence):
        other = tokens(source)
        if len(candidate) >= 8 and len(other) >= 8:
            maximum = max(maximum, _longest_common_run(candidate, other))
            a, b = set(candidate), set(other)
            jaccards.append(len(a & b) / len(a | b))
    jaccard = max(jaccards, default=None)
    eight = maximum >= 8
    jac = jaccard is not None and jaccard >= 0.8
    failed = leakage_failed(proposition, title, sentence)
    require(failed == (eight or jac), "PRODUCTION_LEAKAGE_METRIC_DISAGREEMENT")
    return {"maximum_shared_consecutive_tokens": maximum,
            "eight_token_trigger": eight,
            "qualifying_token_jaccard": jaccard,
            "jaccard_trigger": jac,
            "final_leakage_state": "LEXICAL_LEAKAGE_FAILED" if failed else
                                   "LEXICAL_LEAKAGE_PASSED"}


def independent_reference_leakage(proposition: str, title: str,
                                  sentence: str) -> dict:
    # Independent tokenizer and direct window/set implementation. It does not
    # call the production tokenizer or its leakage decision function.
    tokenize = lambda text: re.findall(r"[^\W_]+", unicodedata.normalize(
        "NFKC", text).lower(), flags=re.UNICODE)
    candidate = tokenize(proposition)
    maximum = 0
    jaccards = []
    for source in (title, sentence):
        other = tokenize(source)
        if len(candidate) < 8 or len(other) < 8:
            continue
        for i in range(len(candidate)):
            for j in range(len(other)):
                count = 0
                while i + count < len(candidate) and j + count < len(other) and (
                    candidate[i + count] == other[j + count]):
                    count += 1
                maximum = max(maximum, count)
        common = set(candidate).intersection(other)
        union = set(candidate).union(other)
        jaccards.append(len(common) / len(union))
    jaccard = max(jaccards, default=None)
    eight = maximum >= 8
    jac = jaccard is not None and jaccard >= 0.8
    return {"maximum_shared_consecutive_tokens": maximum,
            "eight_token_trigger": eight,
            "qualifying_token_jaccard": jaccard,
            "jaccard_trigger": jac,
            "final_leakage_state": "LEXICAL_LEAKAGE_FAILED" if eight or jac else
                                   "LEXICAL_LEAKAGE_PASSED"}


def evaluate(state: dict) -> dict:
    universe, identities, localization, structure = [], [], [], []
    leakage_input, leakage_results, survivors = [], [], []
    independent_results = []
    schema = state["v4_schema"]
    for raw in state["candidate_rows"]:
        ordinal, position = raw["execution_ordinal"], raw["raw_array_position"]
        request = state["request_by_ordinal"][ordinal]
        response = state["raw_by_ordinal"][ordinal]
        token = raw["source_record_token"]
        variant = raw["variant_id_controller_only"]
        candidate = raw["candidate"]
        payload_sha = sha(canonical(candidate))
        historical_controller_id = candidate_id(token, candidate)
        development_id = "dv4_" + sha(canonical([
            "alpha3.20C", token, variant, request["request_sha256"],
            response["transport"]["raw_response_sha256"], position, payload_sha]))
        base = {"development_candidate_id": development_id,
                "historical_controller_payload_id": historical_controller_id,
                "source_record_token": token,
                "variant_id": variant, "execution_ordinal": ordinal,
                "raw_array_position": position,
                "request_sha256": request["request_sha256"],
                "raw_response_sha256": response["transport"]["raw_response_sha256"],
                "candidate_payload_sha256": payload_sha}
        universe.append({**base, "raw_candidate_state":
                         "RAW_ALPHA3_20C_BUILDER_V4_DEVELOPMENT_CANDIDATE"})
        identities.append(base)
        document = state["inputs"][token]["document"]
        quote = candidate["construction_evidence_span"]["exact_text"]
        localized = localize_exact_body_quote(quote, document["body_text"],
                                              document["paragraphs"])
        loc_row = {**base, **localized,
                   "exact_text_sha256": sha(quote.encode("utf-8")),
                   "body_sha256": sha(document["body_text"].encode("utf-8"))}
        localization.append(loc_row)
        if localized["development_v4_localization_state"] == SUCCESS:
            start = localized["body_document_start_offset"]
            end = localized["body_document_end_offset"]
            matches = [paragraph for paragraph in document["paragraphs"]
                       if paragraph["ordinal"] == localized["paragraph_ordinal"]
                       and paragraph["span_id"] == localized["anchor_id"]]
            require(len(matches) == 1, "V4_LOCALIZATION_PARAGRAPH_BINDING_FAILURE")
            paragraph = matches[0]
            local_start = localized["paragraph_local_start_offset"]
            local_end = localized["paragraph_local_end_offset"]
            require(document["body_text"][start:end] == quote
                    and paragraph["text"][local_start:local_end] == quote,
                    "V4_LOCALIZATION_ROUND_TRIP_FAILURE")
            structural = structural_result(candidate, schema)
            structure.append({**base, "structural_denominator_included": True,
                              **structural})
            if structural["structural_state"] == "STRUCTURALLY_COMPLETE":
                sentence = evidence_sentence(document["body_text"], start, end)
                title = state["inputs"][token]["private_title"]
                leakage_input.append({**base, "leakage_denominator_included": True,
                    "candidate_surface": "neutral_proposition only",
                    "source_surface": "private source title and frozen containing evidence sentence fallback",
                    "private_title_sha256": sha(title.encode("utf-8")),
                    "sentence_sha256": sha(sentence.encode("utf-8"))})
                result = production_leakage_metrics(candidate["neutral_proposition"],
                                                    title, sentence)
                replay = independent_reference_leakage(
                    candidate["neutral_proposition"], title, sentence)
                require(result == replay, "LEAKAGE_DETERMINISTIC_REPRODUCTION_FAILURE")
                leakage_results.append({**base, **result})
                independent_results.append({"development_candidate_id": development_id,
                                            **replay})
                if result["final_leakage_state"] == "LEXICAL_LEAKAGE_PASSED":
                    survivors.append({**base, "state":
                        "DETERMINISTIC_DEVELOPMENT_SURVIVOR"})
        else:
            structure.append({**base, "structural_denominator_included": False,
                "structural_state": "NOT_EVALUATED_AFTER_GROUNDING_FAILURE",
                "failure_reasons": [], "semantic_scientific_fidelity_established": False})
    require(len(universe) == len(identities) == len(localization) == len(structure) == 126
            and len({row["development_candidate_id"] for row in identities}) == 126,
            "CANDIDATE_IDENTITY_OR_EVALUATION_COUNT_MISMATCH")
    return locals()


def metric_rows(state: dict, evaluation: dict) -> tuple[dict, list[dict]]:
    result = {}
    paired = []
    by_kind = {}
    for key in ("universe", "localization", "structure", "leakage_input",
                "leakage_results", "survivors"):
        by_kind[key] = defaultdict(list)
        for row in evaluation[key]:
            by_kind[key][(row["source_record_token"], row["variant_id"])].append(row)
    tokens_in_order = [state["request_rows"][i * 3]["private_source_token"]
                       for i in range(14)]
    for source_ordinal, token in enumerate(tokens_in_order, 1):
        record = {"source_ordinal": source_ordinal,
                  "source_record_token": token, "variants": {}}
        for variant in VARIANT_IDS:
            key = (token, variant)
            record["variants"][variant] = {
                "raw_candidate_count": len(by_kind["universe"][key]),
                "grounded_candidate_count": sum(r["development_v4_localization_state"]
                    == SUCCESS for r in by_kind["localization"][key]),
                "structurally_eligible_count": sum(r["structural_state"] ==
                    "STRUCTURALLY_COMPLETE" for r in by_kind["structure"][key]),
                "leakage_evaluated_count": len(by_kind["leakage_input"][key]),
                "deterministic_survivor_count": len(by_kind["survivors"][key]),
                "response_schema_valid": True,
                "response_schema_valid_nonzero": True}
        paired.append(record)
    for variant in VARIANT_IDS:
        raw = [r for r in evaluation["universe"] if r["variant_id"] == variant]
        loc = [r for r in evaluation["localization"] if r["variant_id"] == variant]
        stru = [r for r in evaluation["structure"] if r["variant_id"] == variant]
        leak = [r for r in evaluation["leakage_results"] if r["variant_id"] == variant]
        succ = sum(r["development_v4_localization_state"] == SUCCESS for r in loc)
        spass = sum(r["structural_state"] == "STRUCTURALLY_COMPLETE" for r in stru)
        eight_only = sum(r["eight_token_trigger"] and not r["jaccard_trigger"] for r in leak)
        jac_only = sum(r["jaccard_trigger"] and not r["eight_token_trigger"] for r in leak)
        both = sum(r["jaccard_trigger"] and r["eight_token_trigger"] for r in leak)
        survivor_count = sum(r["final_leakage_state"] == "LEXICAL_LEAKAGE_PASSED"
                             for r in leak)
        source_rows = [r["variants"][variant] for r in paired]
        result[variant] = {
            "raw_candidate_count": len(raw),
            "grounding_denominator": len(loc),
            "grounding_success_count": succ,
            "grounding_failure_count": len(loc) - succ,
            "grounding_failure_states": dict(Counter(
                r["development_v4_localization_state"] for r in loc
                if r["development_v4_localization_state"] != SUCCESS)),
            "sources_with_at_least_one_grounded_candidate": sum(
                r["grounded_candidate_count"] > 0 for r in source_rows),
            "sources_with_zero_grounded_candidates": sum(
                r["grounded_candidate_count"] == 0 for r in source_rows),
            "structural_denominator": sum(r["structural_denominator_included"]
                                          for r in stru),
            "structural_pass_count": spass,
            "structural_failure_count": sum(r["structural_state"] ==
                "STRUCTURALLY_INCOMPLETE" for r in stru),
            "leakage_denominator": len(leak),
            "failed_by_8_token_only": eight_only,
            "failed_by_jaccard_only": jac_only,
            "failed_by_both": both,
            "passed_both": survivor_count,
            "leakage_survivor_count": survivor_count,
            "sources_with_at_least_one_deterministic_survivor": sum(
                r["deterministic_survivor_count"] > 0 for r in source_rows),
            "sources_with_zero_deterministic_survivors": sum(
                r["deterministic_survivor_count"] == 0 for r in source_rows),
            "response_schema_valid_count": 14,
            "response_schema_valid_nonzero_count": 14,
            "source_denominator": 14,
        }
        require(result[variant]["structural_denominator"] == succ
                and spass + result[variant]["structural_failure_count"] == succ
                and eight_only + jac_only + both + survivor_count == len(leak),
                "VARIANT_ACCOUNTING_INVARIANT_FAILED")
    return result, paired


def freeze_evaluation(state: dict, evaluation: dict, metrics: dict,
                      paired: list[dict]) -> dict:
    OUT.mkdir()
    put("alpha3_20c_root_verification.json", {"expected_sha256": C_ROOT,
        "verified": True})
    put("alpha3_20b_root_verification.json", {"expected_sha256": c.B_ROOT,
        "verified": True})
    put("alpha3_20d_authority_binding.json", {
        "alpha3_20a_root_sha256": A_ROOT,
        "builder_grounding_contract_v4": ref(B / "builder_grounding_contract_v4.json"),
        "builder_output_schema_v4": ref(B / "builder_output_schema_v4.json"),
        "evaluation_authorities": [ref(B / name) for name in state["authority_names"]],
        "candidate_source": ref(C / "alpha3_20c_raw_candidate_manifest.jsonl"),
        "localizer_implementation": state["localizer_ref"],
        "leakage_implementation": state["old_contract"]["implementation"],
        "frozen_leakage_sentence_helper": state["old_contract"][
            "sentence_and_stage_helper"]})
    hashes = {}
    for name, key in (
        ("alpha3_20d_candidate_universe_manifest.jsonl", "universe"),
        ("alpha3_20d_candidate_identity_manifest.jsonl", "identities"),
        ("v4_localization_results.jsonl", "localization"),
        ("structural_completeness_results.jsonl", "structure"),
        ("leakage_input_eligibility_manifest.jsonl", "leakage_input"),
        ("lexical_leakage_results.jsonl", "leakage_results"),
        ("deterministic_survivor_manifest.jsonl", "survivors")):
        hashes[name] = put_rows(name, evaluation[key])
    # The same frozen inputs and implementation are replayed independently.
    localization_replay = [localize_exact_body_quote(
        raw["candidate"]["construction_evidence_span"]["exact_text"],
        state["inputs"][raw["source_record_token"]]["document"]["body_text"],
        state["inputs"][raw["source_record_token"]]["document"]["paragraphs"])
        for raw in state["candidate_rows"]]
    loc_outcomes = [{key: value for key, value in row.items()
                     if key in localization_replay[0]} for row in evaluation["localization"]]
    require(canonical(loc_outcomes) == canonical(localization_replay),
            "V4_LOCALIZATION_NONDETERMINISM")
    put("v4_localization_determinism_audit.json", {
        "deterministic": True,
        "candidate_count": 126,
        "first_outcome_sha256": sha(canonical(loc_outcomes)),
        "second_outcome_sha256": sha(canonical(localization_replay))})
    structure_replay = []
    for raw, loc in zip(state["candidate_rows"], localization_replay, strict=True):
        if loc["development_v4_localization_state"] == SUCCESS:
            structure_replay.append(structural_result(raw["candidate"],
                                                     state["v4_schema"]))
        else:
            structure_replay.append({"structural_state":
                "NOT_EVALUATED_AFTER_GROUNDING_FAILURE", "failure_reasons": [],
                "semantic_scientific_fidelity_established": False})
    structure_outcomes = [{key: row[key] for key in structure_replay[0]}
                          for row in evaluation["structure"]]
    require(canonical(structure_outcomes) == canonical(structure_replay),
            "STRUCTURAL_EVALUATION_NONDETERMINISM")
    put("structural_completeness_determinism_audit.json", {
        "deterministic": True, "candidate_count": 126,
        "first_outcome_sha256": sha(canonical(structure_outcomes)),
        "second_outcome_sha256": sha(canonical(structure_replay))})
    put("lexical_leakage_independent_replay.json", {
        "independent_reference_implementation":
            "local Unicode NFKC tokenizer, exhaustive contiguous-run search, set Jaccard",
        "leakage_eligible_candidate_count": len(evaluation["leakage_results"]),
        "production_result_sha256": sha(canonical([{k: r[k] for k in (
            "maximum_shared_consecutive_tokens", "eight_token_trigger",
            "qualifying_token_jaccard", "jaccard_trigger", "final_leakage_state")}
            for r in evaluation["leakage_results"]])),
        "independent_result_sha256": sha(canonical([{k: r[k] for k in (
            "maximum_shared_consecutive_tokens", "eight_token_trigger",
            "qualifying_token_jaccard", "jaccard_trigger", "final_leakage_state")}
            for r in evaluation["independent_results"]])),
        "agreement": True})
    put("v4_localization_per_variant_summary.json", {v: {
        k: metrics[v][k] for k in (
            "raw_candidate_count", "grounding_denominator", "grounding_success_count",
            "grounding_failure_count", "grounding_failure_states",
            "sources_with_at_least_one_grounded_candidate",
            "sources_with_zero_grounded_candidates")}
        for v in VARIANT_IDS})
    put("structural_completeness_per_variant_summary.json", {v: {
        k: metrics[v][k] for k in (
            "structural_denominator", "structural_pass_count",
            "structural_failure_count")}
        for v in VARIANT_IDS})
    put("lexical_leakage_per_variant_summary.json", {v: {
        k: metrics[v][k] for k in (
            "leakage_denominator", "failed_by_8_token_only",
            "failed_by_jaccard_only", "failed_by_both", "passed_both",
            "leakage_survivor_count")}
        for v in VARIANT_IDS})
    put("deterministic_survivor_per_variant_summary.json", {v: {
        k: metrics[v][k] for k in (
            "leakage_survivor_count",
            "sources_with_at_least_one_deterministic_survivor",
            "sources_with_zero_deterministic_survivors", "source_denominator")}
        for v in VARIANT_IDS})
    hashes["paired_source_variant_comparison.jsonl"] = put_rows(
        "paired_source_variant_comparison.jsonl", paired)
    hashes["variant_descriptive_metrics.json"] = put("variant_descriptive_metrics.json",
                                                        metrics)
    put("evaluation_freeze_barrier.json", {
        "all_candidate_level_evaluation_frozen_before_selection": True,
        "all_source_and_variant_metrics_frozen_before_selection": True,
        "candidate_count": 126, "complete_source_triplet_count": 14,
        "evaluation_artifact_sha256": hashes,
        "selection_outputs_created_before_barrier": False,
        "localization_deterministic": True,
        "structural_evaluation_deterministic": True,
        "leakage_independent_replay_agrees": True})
    return hashes


def select_from_frozen_metrics() -> dict:
    metrics = obj(OUT / "variant_descriptive_metrics.json")
    paired = rows(OUT / "paired_source_variant_comparison.jsonl")
    rule = obj(B / "variant_eligibility_rule.json")
    tree = obj(B / "variant_selection_decision_tree.json")
    require(len(paired) == 14 and set(metrics) == set(VARIANT_IDS)
            and rule["reference_variant"] == VARIANT_IDS[0],
            "FROZEN_SELECTION_INPUT_MISMATCH")
    reference = metrics[VARIANT_IDS[0]]
    eligibility = {}
    for variant in VARIANT_IDS:
        m = metrics[variant]
        reasons = []
        if m["response_schema_valid_nonzero_count"] < 1 or (
            m["structural_pass_count"] < 1):
            reasons.append("ABSOLUTE_MINIMUM_NOT_MET")
        for key in ("response_schema_valid_count", "raw_candidate_count",
                    "grounding_success_count", "structural_pass_count"):
            if m[key] < reference[key]:
                reasons.append("AGGREGATE_NONREGRESSION:" + key)
        for row in paired:
            mine = row["variants"][variant]
            base = row["variants"][VARIANT_IDS[0]]
            for key in ("response_schema_valid_nonzero",
                        "grounded_candidate_count", "structurally_eligible_count"):
                if bool(base[key]) and not bool(mine[key]):
                    reasons.append("SOURCE_COVERAGE_NONREGRESSION:source_" +
                                   str(row["source_ordinal"]) + ":" + key)
        eligibility[variant] = {
            "state": "NONLEAKAGE_ELIGIBLE" if not reasons else
                     "NONLEAKAGE_INELIGIBLE",
            "nonleakage_eligible": not reasons,
            "deterministic_reasons": reasons,
            "deterministic_survivor_count": m["leakage_survivor_count"],
            "semantic_scientific_fidelity_resolved": False,
            "reference_variant": VARIANT_IDS[0]}
    put("variant_nonleakage_eligibility.json", eligibility)
    eligible = [v for v in VARIANT_IDS if eligibility[v]["nonleakage_eligible"]]
    semantic_required = False
    recommendation = "NONE"
    if not eligible:
        classification = "DETERMINISTIC_EVALUATION_COMPLETE_NO_VARIANT_ELIGIBLE"
        next_stage = NEXT_NONE
        reason = tree["no_non_leakage_eligible_variant"]
    elif eligible == [VARIANT_IDS[0]]:
        # Reference choice follows only mechanical exclusions. No comparative
        # semantic-fidelity claim is needed to retain the conservative baseline.
        classification = "DETERMINISTIC_EVALUATION_COMPLETE_SINGLE_VARIANT_SELECTABLE"
        next_stage = NEXT_F
        recommendation = "V1"
        reason = "sole eligible frozen reference; no semantic comparison used"
    elif len(eligible) == 1:
        semantic_required = True
        classification = "DETERMINISTIC_EVALUATION_COMPLETE_SEMANTIC_ADJUDICATION_REQUIRED"
        next_stage = NEXT_E
        recommendation = "DEFERRED"
        reason = "non-reference single eligible variant requires scientific-fidelity judgment"
    else:
        deterministic_keys = (
            "response_schema_valid_count", "raw_candidate_count",
            "grounding_success_count", "structural_pass_count",
            "leakage_denominator", "leakage_survivor_count",
            "sources_with_at_least_one_deterministic_survivor")
        tied = all(tuple(metrics[v][key] for key in deterministic_keys) ==
                   tuple(metrics[eligible[0]][key] for key in deterministic_keys)
                   for v in eligible[1:])
        if tied and VARIANT_IDS[0] in eligible:
            classification = "DETERMINISTIC_EVALUATION_COMPLETE_REFERENCE_TIEBREAK_APPLICABLE"
            next_stage = NEXT_F
            recommendation = "V1"
            reason = "all preregistered deterministic dimensions tied; frozen reference tie-break"
        else:
            semantic_required = True
            classification = "DETERMINISTIC_EVALUATION_COMPLETE_SEMANTIC_ADJUDICATION_REQUIRED"
            next_stage = NEXT_E
            recommendation = "DEFERRED"
            reason = tree["multiple_eligible_leakage_differs_semantics_unresolved"]
    put("semantic_adjudication_trigger_evaluation.json", {
        "authority": ref(B / "semantic_adjudication_trigger.json"),
        "semantic_adjudication_required": semantic_required,
        "scientific_fidelity_established_by_structure": False,
        "semantic_adjudication_performed": False,
        "reason": reason})
    put("variant_selection_decision_tree_execution.json", {
        "authority": ref(B / "variant_selection_decision_tree.json"),
        "eligible_variants": eligible, "branch_reason": reason,
        "classification": classification,
        "weighted_score_used": False,
        "input_evaluation_freeze_barrier_sha256": digest(OUT /
            "evaluation_freeze_barrier.json")})
    put("deterministic_variant_selection_recommendation.json", {
        "state": "DETERMINISTIC_SELECTION_RECOMMENDATION" if recommendation in
            ("V1", "V2", "V3") else "NO_SELECTION_YET",
        "recommended_variant": recommendation,
        "final_builder_v4_contract_frozen": False,
        "semantic_adjudication_required": semantic_required,
        "next_stage_recommendation": next_stage})
    return {"classification": classification, "next_stage_recommendation": next_stage,
            "semantic_adjudication_required": semantic_required,
            "deterministic_selection_recommendation": recommendation,
            "eligibility": eligibility}


def finish(state: dict, metrics: dict, selection: dict) -> dict:
    frozen_root(C, "search_plan_v24_dev_alpha3_20c_sha256", C_ROOT)
    frozen_root(B, "search_plan_v24_dev_alpha3_20b_sha256", c.B_ROOT)
    frozen_root(A, "search_plan_v24_dev_alpha3_20a_sha256", A_ROOT)
    put("development_interpretation_boundary.json", {
        "classification": "POST_ALPHA3_19_SEEN_DATA_DEVELOPMENT_DETERMINISTIC_VARIANT_EVALUATION",
        "seen_development_results_only": True,
        "fresh_heldout_or_primary_validation_claimed": False,
        "deterministic_survivors_are_not_quality_or_scientific_truth": True,
        "final_builder_v4_contract_frozen": False})
    put("historical_contamination_nonuse_audit.json", {
        "candidate_universe": "alpha3.20C raw Builder V4 candidates only",
        "alpha3_18_or_alpha3_19_candidates_used_as_fourth_arm": False,
        "historical_candidate_outcomes_used_for_scoring": False,
        "source_identity_access": "private title solely for frozen leakage source surface"})
    put("historical_preservation_audit.json", {
        "alpha3_20a_root_unchanged": True,
        "alpha3_20b_root_unchanged": True,
        "alpha3_20c_root_unchanged": True,
        "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {
        "provider_calls": 0, "deepseek_calls": 0, "llm_calls": 0,
        "network_calls": 0, "quality_calls": 0,
        "candidate_text_modified": False,
        "prompt_modified": False,
        "fourth_variant_created": False,
        "weighted_score_used": False,
        "semantic_adjudication_performed": False,
        "grounding_contract_changed": False,
        "structural_contract_changed": False,
        "leakage_thresholds_changed": False,
        "leakage_comparison_policy_changed": False})
    validation = {
        "status": "completed", "alpha3_20d_classification": selection["classification"],
        "alpha3_20c_root_verified": True, "alpha3_20b_root_verified": True,
        "development_only": True,
        "raw_candidate_count": 126, "complete_variant_triplet_count": 14,
        "per_variant": {VARIANT_SHORT[v]: {**metrics[v],
            "nonleakage_eligible": selection["eligibility"][v]["nonleakage_eligible"]}
            for v in VARIANT_IDS},
        "v4_localization_deterministic": True,
        "structural_evaluation_deterministic": True,
        "leakage_independent_replay_agrees": True,
        "semantic_adjudication_required": selection["semantic_adjudication_required"],
        "deterministic_selection_recommendation": selection[
            "deterministic_selection_recommendation"],
        "grounding_contract_changed": False,
        "structural_contract_changed": False,
        "leakage_thresholds_changed": False,
        "leakage_comparison_policy_changed": False,
        "candidate_text_modified": False,
        "prompt_modified": False,
        "fourth_variant_created": False,
        "weighted_score_used": False,
        "semantic_adjudication_performed": False,
        "provider_calls": 0, "llm_calls": 0,
        "network_calls": 0, "quality_calls": 0,
        "next_stage_recommendation": selection["next_stage_recommendation"],
        "historical_assets_modified": False}
    put("validation.json", validation)
    put("summary.json", {"status": "completed",
        "classification": selection["classification"],
        "raw_candidate_count": 126, "complete_source_triplets": 14,
        "per_variant": {VARIANT_SHORT[v]: {
            "grounding_success_count": metrics[v]["grounding_success_count"],
            "leakage_denominator": metrics[v]["leakage_denominator"],
            "leakage_survivor_count": metrics[v]["leakage_survivor_count"],
            "nonleakage_eligible": selection["eligibility"][v]["nonleakage_eligible"]}
            for v in VARIANT_IDS},
        "semantic_adjudication_required": selection["semantic_adjudication_required"],
        "deterministic_selection_recommendation": selection[
            "deterministic_selection_recommendation"],
        "next_stage_recommendation": selection["next_stage_recommendation"]})
    root = c.root_hash(OUT, ROOT_MARKER)
    with (OUT / ROOT_MARKER).open("xb") as handle:
        handle.write((root + "\n").encode("ascii"))
    return validation


def main() -> None:
    state = preflight()
    evaluated = evaluate(state)
    metrics, paired = metric_rows(state, evaluated)
    freeze_evaluation(state, evaluated, metrics, paired)
    selection = select_from_frozen_metrics()
    validation = finish(state, metrics, selection)
    print(json.dumps({"status": validation["status"],
        "classification": validation["alpha3_20d_classification"],
        "root_sha256": (OUT / ROOT_MARKER).read_text().strip()},
        sort_keys=True))


if __name__ == "__main__":
    main()
