#!/usr/bin/env python3
"""Freeze 28 blinded development semantic-fidelity requests; offline only."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from collections import Counter
from pathlib import Path

from scripts import run_search_plan_v24_alpha320b_prompt_freeze_offline as b
from scripts import run_search_plan_v24_alpha320c_builder_v4_execution as c
from scripts import run_search_plan_v24_alpha320d_deterministic_variant_evaluation_offline as d


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/20261003_search_plan_v24_dev_alpha3_20e_semantic_adjudication_preregistration_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_20e_sha256"
D_ROOT = "d6d9b66627fe193d7925333c0c7dd32553465611c11b095075fb84cc75c95e84"
NEXT = "AUTHORIZE_EXACT_28_ALPHA3_20E1_DEVELOPMENT_SEMANTIC_ADJUDICATION_CALLS"
CRITERIA = (
    "actor_or_intervention_fidelity",
    "response_fidelity",
    "direction_or_polarity_fidelity",
    "relation_strength_and_scope_fidelity",
    "essential_context_fidelity",
    "unsupported_mechanism_or_detail",
)
STATES = ("PASS", "FAIL", "UNRESOLVED")

SYSTEM_PROMPT = (
    "You are a proposition_quality_adjudicator performing a development semantic-fidelity review. "
    "Judge each candidate proposition independently against only the supplied Abstract, canonical Body, "
    "and its exact Body evidence quote. The quote is verbatim evidence; the proposition is a separate "
    "scientific abstraction. Use the full supplied context when necessary, but do not use outside knowledge.\n"
    "For each candidate, judge six dimensions with exactly PASS, FAIL, or UNRESOLVED and a concise "
    "scientific rationale grounded only in supplied context. "
    "actor_or_intervention_fidelity: preserve the scientifically relevant actor, perturbation, or "
    "combination intervention; fail substitutions, omissions, or material scope changes. "
    "response_fidelity: preserve the measured or biological response and endpoint. "
    "direction_or_polarity_fidelity: preserve direction or polarity; unresolved only when supplied "
    "material cannot establish it. "
    "relation_strength_and_scope_fidelity: do not turn association into demonstrated causation, "
    "conditional effects into unconditional claims, or measured endpoints into broader mechanisms. "
    "essential_context_fidelity: retain species, cell or tissue type, disease or genotype, treatment, "
    "measurement, time, or combination context only when necessary to preserve scientific meaning. "
    "unsupported_mechanism_or_detail: PASS means no material unsupported mechanism or detail was "
    "added; FAIL means a material unsupported claim was added.\n"
    "Do not judge fluency, elegance, brevity, novelty, lexical difference, or writing style. "
    "Do not compare candidates, rank them, or recommend a prompt. "
    "Return one JSON object with exactly the supplied candidate tokens, each with all six dimension "
    "judgments. Do not emit protocol metadata. Do not add Markdown."
) + (
    " JSON structure: the sole top-level key is candidate_reviews, an array of exactly three "
    "objects. Each review object has exactly candidate_token and criteria. The criteria object "
    "has exactly these six keys: " + ", ".join(CRITERIA) + ". Each criterion value is an object "
    "with exactly state and rationale; state is exactly PASS, FAIL, or UNRESOLVED and rationale "
    "is a nonempty string. Echo each supplied candidate token exactly once and add no other keys."
)
USER_PREFIX = "Assess these three candidate propositions against the shared source context.\n"
TEMPLATE = "SYSTEM:\n" + SYSTEM_PROMPT + "\nUSER:\n" + USER_PREFIX + "<BLINDED_PAYLOAD_JSON>\n"


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
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


def ref(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}


def put(name: str, value: object, private: bool = False) -> str:
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


def put_rows(name: str, values: list[dict], private: bool = False) -> str:
    raw = b"".join(canonical(value) + b"\n" for value in values)
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


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA320E_OUTPUT_ALREADY_EXISTS_NO_REWRITE")
    d.frozen_root(d.OUT, "search_plan_v24_dev_alpha3_20d_sha256", D_ROOT)
    d.frozen_root(c.OUT, "search_plan_v24_dev_alpha3_20c_sha256", d.C_ROOT)
    d.frozen_root(b.OUT, "search_plan_v24_dev_alpha3_20b_sha256", c.B_ROOT)
    for name, expected in (("builder_grounding_contract_v4", c.GROUNDING_SHA),
                           ("builder_output_schema_v4", c.SCHEMA_SHA)):
        require(digest(b.OUT / (name + ".json")) == expected
                and (b.OUT / (name + "_sha256")).read_text().strip() == expected,
                "FROZEN_V4_CONTRACT_MISMATCH:" + name)
    eligibility = obj(d.OUT / "variant_nonleakage_eligibility.json")
    trigger = obj(d.OUT / "semantic_adjudication_trigger_evaluation.json")
    validation = obj(d.OUT / "validation.json")
    require([eligibility[v]["nonleakage_eligible"] for v in d.VARIANT_IDS]
            == [True, True, False]
            and trigger["semantic_adjudication_required"] is True
            and validation["alpha3_20d_classification"] ==
                "DETERMINISTIC_EVALUATION_COMPLETE_SEMANTIC_ADJUDICATION_REQUIRED"
            and validation["deterministic_selection_recommendation"] == "DEFERRED"
            and validation["per_variant"]["V1"]["leakage_survivor_count"] == 39
            and validation["per_variant"]["V2"]["leakage_survivor_count"] == 37,
            "ALPHA320D_SELECTION_BOUNDARY_MISMATCH")
    # The master expressly requires fidelity of these scientific components.
    abstraction_path = b.MASTER / "proposition_abstraction_contract_v1.json"
    abstraction = obj(abstraction_path)
    require(digest(abstraction_path) == b.ABSTRACTION_SHA
            and abstraction["future_semantic_comparison_requires_separate_independent_development_adjudication_if_unresolved"]
            and set(abstraction["must_preserve"]) == {
                "actor or intervention", "observed response", "direction",
                "essential biological context", "source-supported qualifiers"}
            and "invent mechanism" in abstraction["must_not"]
            and "generalize beyond evidence" in abstraction["must_not"],
            "SEMANTIC_ADJUDICATION_AUTHORITY_UNRESOLVED")
    identity_rows = rows(d.OUT / "alpha3_20d_candidate_identity_manifest.jsonl")
    universe_rows = rows(d.OUT / "alpha3_20d_candidate_universe_manifest.jsonl")
    candidate_rows = rows(c.OUT / "alpha3_20c_raw_candidate_manifest.jsonl")
    request_rows = rows(b.OUT / "alpha3_20c_combined_request_manifest.jsonl")
    require(len(identity_rows) == len(universe_rows) == len(candidate_rows) == 126
            and len(request_rows) == 42,
            "FROZEN_SEMANTIC_CANDIDATE_UNIVERSE_MISMATCH")
    identity_by_cell = {(r["execution_ordinal"], r["raw_array_position"]): r
                        for r in identity_rows}
    require(len(identity_by_cell) == 126, "DEVELOPMENT_CANDIDATE_IDENTITY_DUPLICATE")
    retained = []
    for raw in candidate_rows:
        identity = identity_by_cell[(raw["execution_ordinal"],
                                     raw["raw_array_position"])]
        require(identity["candidate_payload_sha256"] == sha(canonical(raw["candidate"]))
                and identity["source_record_token"] == raw["source_record_token"]
                and identity["variant_id"] == raw["variant_id_controller_only"],
                "CANDIDATE_IDENTITY_OR_PAYLOAD_MISMATCH")
        if raw["variant_id_controller_only"] in d.VARIANT_IDS[:2]:
            retained.append({"raw": raw, "identity": identity})
    require(len(retained) == 84
            and Counter(x["raw"]["variant_id_controller_only"] for x in retained)
                == {d.VARIANT_IDS[0]: 42, d.VARIANT_IDS[1]: 42},
            "RETAINED_ARM_UNIVERSE_MISMATCH")
    source_groups = {}
    documents = {r["source_token"]: r for r in rows(d.DOC_MANIFEST)}
    for source_ordinal in range(1, 15):
        source_requests = request_rows[(source_ordinal - 1) * 3:source_ordinal * 3]
        token = source_requests[0]["private_source_token"]
        require(len(source_requests) == 3
                and all(r["source_ordinal"] == source_ordinal
                        and r["private_source_token"] == token
                        for r in source_requests)
                and [r["variant_index"] for r in source_requests] == [1, 2, 3]
                and token in documents,
                "FROZEN_SOURCE_GROUP_IDENTITY_MISMATCH")
        doc_row = documents[token]
        document_path = d.E / doc_row["document_path"]
        require(digest(document_path) == doc_row["document_sha256"]
                and source_requests[0]["construction_document_sha256"] ==
                    doc_row["document_sha256"],
                "FROZEN_SCIENTIFIC_SOURCE_CONTEXT_MISMATCH")
        document = obj(document_path)
        context = {"abstract": document["abstract_text"],
                   "canonical_body": document["body_text"]}
        arm_groups = {}
        for variant_index, variant in enumerate(d.VARIANT_IDS[:2], 1):
            ordinal = source_requests[variant_index - 1]["execution_ordinal"]
            members = sorted((x for x in retained if x["raw"]["execution_ordinal"]
                              == ordinal), key=lambda x: x["raw"]["raw_array_position"])
            require(len(members) == 3
                    and [x["raw"]["raw_array_position"] for x in members]
                        == [0, 1, 2]
                    and all(x["raw"]["source_record_token"] == token
                            and x["raw"]["variant_id_controller_only"] == variant
                            for x in members),
                    "SOURCE_ARM_CANDIDATE_GROUP_MISMATCH")
            arm_groups[variant] = {"execution_ordinal": ordinal,
                                   "members": members}
        source_groups[source_ordinal] = {"source_record_token": token,
            "context": context, "context_sha256": sha(canonical(context)),
            "construction_document_ref": ref(document_path),
            "arms": arm_groups}
    require(len(source_groups) == 14,
            "FROZEN_SOURCE_CONTEXT_GROUP_COUNT_MISMATCH")
    return locals()


def rubric() -> dict:
    return {"schema_version": "DevelopmentSemanticFidelityRubricV1",
        "status": "FROZEN_SEEN_DATA_DEVELOPMENT_ONLY",
        "source_authority": ref(b.MASTER / "proposition_abstraction_contract_v1.json"),
        "criterion_states": list(STATES),
        "criteria": {
            "actor_or_intervention_fidelity": {
                "pass": "Scientifically relevant actor or intervention is preserved.",
                "fail": "Actor substituted, required intervention or combination dropped, perturbation changed, or actor scope materially broadened or narrowed."},
            "response_fidelity": {
                "pass": "Relevant measured or biological response is preserved.",
                "fail": "Endpoint, measurement target, phenotype, or response identity changed or unsupported response substituted."},
            "direction_or_polarity_fidelity": {
                "pass": "Direction or polarity supported by the supplied evidence is preserved.",
                "fail": "Increase/decrease, activation/inhibition, sensitization/resistance, presence/absence, or promotion/suppression flipped.",
                "unresolved": "Direction genuinely cannot be established from supplied source material."},
            "relation_strength_and_scope_fidelity": {
                "pass": "Evidential relation strength, qualifiers, and scope are preserved.",
                "fail": "Association upgraded to demonstrated causation, context-specific or conditional effect generalized, endpoint broadened to mechanism, or necessity/sufficiency overstated."},
            "essential_context_fidelity": {
                "pass": "Context necessary to preserve scientific meaning is retained.",
                "fail": "Scientifically essential species, cell/tissue, disease/genotype, treatment, measurement, time, or combination context omitted or altered."},
            "unsupported_mechanism_or_detail": {
                "pass": "No scientifically material unsupported mechanism or detail was added.",
                "fail": "Material mechanism, intermediate, causal explanation, pathway, cell state, population, or treatment condition was invented."},
        },
        "unresolved_general_rule": "Use UNRESOLVED only when supplied context cannot establish the criterion; do not infer from outside knowledge.",
        "excluded_criteria": ["style", "fluency", "brevity", "novelty",
                              "lexical diversity", "lexical abstraction"],
        "weighted_or_numeric_score": None,
        "candidate_judgments_independent": True}


def response_envelope() -> dict:
    judgment = {"type": "object", "additionalProperties": False,
                "required": ["state", "rationale"],
                "properties": {"state": {"type": "string", "enum": list(STATES)},
                               "rationale": {"type": "string", "minLength": 1}}}
    criteria_schema = {"type": "object", "additionalProperties": False,
                       "required": list(CRITERIA),
                       "properties": {name: judgment for name in CRITERIA}}
    model_schema = {"type": "object", "additionalProperties": False,
        "required": ["candidate_reviews"],
        "properties": {"candidate_reviews": {
            "type": "array", "minItems": 3, "maxItems": 3,
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["candidate_token", "criteria"],
                      "properties": {"candidate_token": {"type": "string", "minLength": 1},
                                     "criteria": criteria_schema}}}}}
    return {"schema_version": "DevelopmentSemanticAdjudicationResponseEnvelopeV1",
        "model_owned_payload_schema": model_schema,
        "controller_owned_metadata": ["schema_version", "blinded_group_token",
            "private_arm_identity", "provider", "model", "request_sha256",
            "execution_ordinal", "transport_and_inference_metadata"],
        "model_required_to_emit_schema_version": False,
        "exact_candidate_token_set_rule": "set(response.candidate_reviews.candidate_token) must equal the three request candidate tokens, with no duplicates",
        "extra_missing_or_duplicate_candidate_action": "COMPLETED_RESPONSE_INVALID_NO_REPAIR",
        "missing_or_non_enum_scientific_judgment_action": "COMPLETED_RESPONSE_INVALID_NO_REPAIR",
        "controller_must_not_fill_scientific_judgments": True,
        "criterion_rationale_role": "supporting text; never overrides categorical state",
        "candidate_overall_state_controller_derived": True,
        "scientific_retry_or_repair": False}


def derive_seeded_order(seed: bytes) -> dict[int, str]:
    ordered_sources = sorted(range(1, 15), key=lambda ordinal:
        sha(seed + b"|source-arm-first|" + str(ordinal).encode("ascii")))
    first_v1 = set(ordered_sources[:7])
    return {ordinal: d.VARIANT_IDS[0] if ordinal in first_v1
            else d.VARIANT_IDS[1] for ordinal in range(1, 15)}


def build(state: dict, seed: bytes) -> dict:
    first_by_source = derive_seeded_order(seed)
    all_group_tokens: set[str] = set()
    all_candidate_tokens: set[str] = set()
    group_map, candidate_map, permutations = [], [], []
    requests, context_audit, universe = [], [], []
    future_ordinal = 0
    for source_ordinal in range(1, 15):
        source = state["source_groups"][source_ordinal]
        first = first_by_source[source_ordinal]
        arm_order = [first, next(v for v in d.VARIANT_IDS[:2] if v != first)]
        context_hashes = []
        for arm_position, variant in enumerate(arm_order, 1):
            future_ordinal += 1
            group_token = "sg_" + secrets.token_hex(16)
            require(group_token not in all_group_tokens, "RANDOM_GROUP_TOKEN_COLLISION")
            all_group_tokens.add(group_token)
            members = source["arms"][variant]["members"]
            tokened = []
            for item in members:
                candidate_token = "sc_" + secrets.token_hex(16)
                require(candidate_token not in all_candidate_tokens,
                        "RANDOM_CANDIDATE_TOKEN_COLLISION")
                all_candidate_tokens.add(candidate_token)
                tokened.append({"candidate_token": candidate_token, "item": item})
            order = sorted(range(3), key=lambda position: sha(
                seed + b"|candidate-permutation|" + group_token.encode("ascii")
                + b"|" + str(position).encode("ascii")))
            candidates_visible = []
            for display_position, original_position in enumerate(order):
                entry = tokened[original_position]
                candidate = entry["item"]["raw"]["candidate"]
                candidates_visible.append({"candidate_token": entry["candidate_token"],
                    "neutral_proposition": candidate["neutral_proposition"],
                    "exact_body_evidence_quote": candidate[
                        "construction_evidence_span"]["exact_text"]})
                candidate_map.append({"blinded_group_token": group_token,
                    "blinded_candidate_token": entry["candidate_token"],
                    "development_candidate_id": entry["item"]["identity"][
                        "development_candidate_id"],
                    "source_record_token": source["source_record_token"],
                    "private_variant_id": variant,
                    "raw_array_position": original_position,
                    "blinded_display_position": display_position,
                    "candidate_payload_sha256": entry["item"]["identity"][
                        "candidate_payload_sha256"]})
            payload = {"blinded_group_token": group_token,
                "source_context": source["context"],
                "candidates": candidates_visible}
            user_message = USER_PREFIX + canonical(payload).decode("utf-8")
            request = {"model": "deepseek-flash",
                "thinking": {"type": "enabled"}, "reasoning_effort": "high",
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                             {"role": "user", "content": user_message}]}
            request_row = {"future_execution_ordinal": future_ordinal,
                "blinded_group_token": group_token,
                "blinded_candidate_tokens_in_display_order": [
                    x["candidate_token"] for x in candidates_visible],
                "request": request,
                "request_sha256": sha(canonical(request)),
                "historical_role": "SEEN_DEVELOPMENT_HISTORY"}
            requests.append(request_row)
            group_map.append({"future_execution_ordinal": future_ordinal,
                "blinded_group_token": group_token,
                "source_ordinal_private": source_ordinal,
                "source_record_token_private": source["source_record_token"],
                "private_variant_id": variant,
                "alpha3_20c_execution_ordinal": source["arms"][variant][
                    "execution_ordinal"],
                "source_context_sha256": source["context_sha256"],
                "request_sha256": request_row["request_sha256"]})
            permutations.append({"blinded_group_token": group_token,
                "source_ordinal_private": source_ordinal,
                "private_variant_id": variant,
                "original_position_to_display_position": {
                    str(original_position): order.index(original_position)
                    for original_position in range(3)},
                "display_order_original_positions": order,
                "seed_sha256": sha(seed),
                "content_not_used_for_order": True})
            context_hashes.append(source["context_sha256"])
            for entry in tokened:
                universe.append({"blinded_group_token": group_token,
                    "blinded_candidate_token": entry["candidate_token"],
                    "candidate_payload_sha256": entry["item"]["identity"][
                        "candidate_payload_sha256"],
                    "historical_role": "SEEN_DEVELOPMENT_HISTORY"})
        context_audit.append({"source_ordinal_private": source_ordinal,
            "source_record_token_private": source["source_record_token"],
            "source_context_sha256_per_blinded_arm": context_hashes,
            "byte_equivalent": context_hashes[0] == context_hashes[1],
            "candidate_specific_fields_only": ["neutral_proposition",
                                               "exact_body_evidence_quote"],
            "source_context_document": source["construction_document_ref"]})
    require(future_ordinal == len(requests) == len(group_map) == 28
            and len(candidate_map) == len(universe) == 84
            and len(context_audit) == 14
            and all(row["byte_equivalent"] for row in context_audit)
            and len(all_group_tokens) == 28
            and len(all_candidate_tokens) == 84
            and sum(v == d.VARIANT_IDS[0] for v in first_by_source.values()) == 7,
            "BLINDED_REQUEST_CONSTRUCTION_FAILURE")
    require(all(len(row["blinded_candidate_tokens_in_display_order"]) == 3
                and len(set(row["blinded_candidate_tokens_in_display_order"])) == 3
                and not any(name in row["request"] for name in ("variant", "arm"))
                for row in requests), "MODEL_VISIBLE_ARM_OR_TOKEN_SET_FAILURE")
    # Audit only the model-facing wrapper. Ordinary scientific source text is
    # deliberately not treated as experimental identity leakage.
    lower_system = SYSTEM_PROMPT.lower()
    require(not any(term in lower_system for term in (
        "v1", "v2", "relation sentence", "relation frame", "reference variant",
        "8-token", "jaccard", "leakage", "survivor", "39", "37",
        "choose a prompt", "which variant")),
        "SEMANTIC_ADJUDICATION_BLINDING_FAILURE")
    require(all(set(row["request"]["messages"][1]["content"].splitlines()[0:1])
                == {USER_PREFIX.rstrip("\n")} for row in requests),
            "ADJUDICATION_USER_WRAPPER_CHANGED")
    return locals()


def freeze(state: dict, built: dict, seed: bytes) -> dict:
    OUT.mkdir()
    put("alpha3_20d_root_verification.json", {"root_sha256": D_ROOT,
        "verified": True})
    put("alpha3_20c_root_verification.json", {"root_sha256": d.C_ROOT,
        "verified": True})
    put_rows("semantic_adjudication_universe_manifest.jsonl", built["universe"])
    put("v1_v2_candidate_count_verification.json", {
        "v1_candidate_count": 42, "v2_candidate_count": 42,
        "semantic_candidate_count": 84,
        "sources_per_retained_arm": 14,
        "candidates_per_source_arm": 3,
        "all_candidates_included_independent_of_leakage": True})
    put("v3_exclusion_binding.json", {
        "source": ref(d.OUT / "variant_nonleakage_eligibility.json"),
        "v1_nonleakage_eligible": True,
        "v2_nonleakage_eligible": True,
        "v3_nonleakage_eligible": False,
        "v3_included_in_semantic_adjudication": False,
        "semantic_adjudication_cannot_rescue_ineligible_v3": True})
    rubric_sha = put("development_semantic_fidelity_rubric_v1.json", rubric())
    marker("development_semantic_fidelity_rubric_v1_sha256", rubric_sha)
    put("semantic_candidate_overall_state_derivation.json", {
        "controller_owned": True,
        "if_any_required_dimension_fail": "SEMANTIC_FIDELITY_FAIL",
        "if_no_fail_and_any_unresolved": "SEMANTIC_FIDELITY_UNRESOLVED",
        "if_all_six_pass": "SEMANTIC_FIDELITY_PASS",
        "rationale_overrides_state": False,
        "weighted_or_numeric_score": None})
    envelope_sha = put("development_semantic_adjudication_response_envelope_v1.json",
                       response_envelope())
    marker("development_semantic_adjudication_response_envelope_v1_sha256",
           envelope_sha)
    put("semantic_adjudicator_role_binding.json", {
        "reviewer_role": "proposition_quality_adjudicator",
        "task_mode": "development_semantic_fidelity_v1",
        "development_only": True,
        "human_gold_or_primary_quality": False,
        "model_chooses_variant": False})
    put("semantic_adjudication_blinding_contract.json", {
        "model_visible": ["random blinded group token", "three random candidate tokens",
            "frozen Abstract", "frozen canonical Body", "candidate neutral proposition",
            "candidate exact Body evidence quote", "uniform six-criterion rubric"],
        "controller_only": ["source token", "V1/V2 arm identity",
            "candidate development identity", "group/candidate token mapping",
            "alpha3.20D leakage outcomes", "selection objective"],
        "direct_variant_comparison_requested": False,
        "one_arm_per_fresh_context": True,
        "ordinary_scientific_body_content_is_not_provenance_leak": True})
    seed_sha = put("semantic_blinding_seed_private.json", {
        "random_seed_hex": seed.hex(), "seed_sha256": sha(seed),
        "source_arm_first_algorithm": "sort source ordinals 1..14 by SHA256(seed|source-arm-first|ordinal); first seven V1 first, rest V2 first",
        "candidate_order_algorithm": "sort positions 0..2 by SHA256(seed|candidate-permutation|random_group_token|position)"},
        private=True)
    group_map_sha = put_rows("semantic_group_token_mapping_private.jsonl",
                             built["group_map"], private=True)
    candidate_map_sha = put_rows("semantic_candidate_token_mapping_private.jsonl",
                                 built["candidate_map"], private=True)
    put_rows("semantic_candidate_order_permutation.jsonl", built["permutations"],
             private=True)
    put("semantic_group_execution_order.json", {
        "order": "source-major; within source hash-balanced blinded arm order",
        "group_count": 28,
        "v1_first_source_count_private": 7,
        "v2_first_source_count_private": 7,
        "blinded_execution_ordinals": [{
            "execution_ordinal": row["future_execution_ordinal"],
            "blinded_group_token": row["blinded_group_token"],
            "request_sha256": row["request_sha256"]}
            for row in built["requests"]],
        "independent_context_per_group": True,
        "scientific_content_used_for_order": False,
        "seed_private_artifact_sha256": seed_sha})
    put_rows("semantic_source_context_equivalence_audit.jsonl",
             built["context_audit"], private=True)
    prompt_sha = sha(TEMPLATE.encode("utf-8"))
    with (OUT / "semantic_adjudication_prompt_template.txt").open("xb") as handle:
        handle.write(TEMPLATE.encode("utf-8"))
    marker("semantic_adjudication_prompt_template_sha256", prompt_sha)
    request_sha = put_rows("semantic_adjudication_request_manifest.jsonl",
                           built["requests"])
    marker("semantic_adjudication_request_manifest_sha256", request_sha)
    put("semantic_adjudication_runtime_policy.json", {
        "provider": "DeepSeek", "api_surface": "Chat Completions",
        "model": "deepseek-flash", "thinking": {"type": "enabled"},
        "reasoning_effort": "high", "response_format": {"type": "json_object"},
        "temperature": "omitted", "top_p": "omitted",
        "max_output_tokens": "omitted as in frozen development baseline",
        "stream": "omitted", "one_fresh_independent_context_per_group": True,
        "scientific_inference_attempts_per_group_maximum": 1,
        "automatic_retry": False,
        "known_no_inference_transport_retry_enabled": False,
        "ambiguous_inference_action": "STOP_NO_RETRY",
        "completed_schema_invalid_action": "RECORD_INVALID_NO_SCIENTIFIC_REPAIR",
        "fallback_model_or_provider": False,
        "calls_authorized_in_alpha3_20e": 0})
    put("semantic_adjudication_call_budget.json", {
        "planned_semantic_adjudication_groups": 28,
        "planned_semantic_adjudication_scientific_calls": 28,
        "calls_authorized_now": 0,
        "separate_alpha3_20e1_execution_authorization_required": True,
        "no_majority_vote_or_second_opinion": True})
    put("semantic_postexecution_summary_contract.json", {
        "complete_experiment_requirement": "all 28 group responses schema-valid and exact candidate-token sets before selection",
        "per_arm_candidate_denominator": 42,
        "per_arm_source_denominator": 14,
        "per_arm_candidate_counts": ["candidate_semantic_pass_count",
            "candidate_semantic_fail_count", "candidate_semantic_unresolved_count"],
        "per_arm_source_counts": ["sources_with_at_least_one_semantic_fail",
            "sources_with_at_least_one_semantic_unresolved",
            "sources_all_three_semantic_pass"],
        "invalid_response_action": "freeze incomplete experiment; do not drop group, impute, repair, or select",
        "rationale_is_supporting_text_only": True})
    put("semantic_variant_dominance_rule.json", {
        "comparison_vector_order": ["candidate_semantic_fail_count",
                                    "candidate_semantic_unresolved_count"],
        "a_dominates_b": "A.fail <= B.fail AND A.unresolved <= B.unresolved AND at least one strict",
        "equal_vectors": "SEMANTIC_TIE",
        "crossed_vectors": "SEMANTIC_INCOMPARABLE",
        "source_level_distribution": "report for interpretation only; not selection optimization",
        "weighted_tradeoff": None})
    put("semantic_variant_selection_rule.json", {
        "precondition": "all 28 valid source-arm adjudications; every three-token set exact",
        "semantic_fidelity_precedes_lexical_yield": True,
        "v1_semantic_dominance": "recommend V1 regardless of leakage count",
        "v2_semantic_dominance": "recommend V2 regardless of leakage count",
        "semantic_tie": "recommend V1 using frozen 20D leakage survivors V1 39/42 versus V2 37/42",
        "semantic_incomparable": "DEFERRED; separately design resolution stage",
        "v3_selection_allowed": False,
        "final_builder_v4_contract_freeze_stage": "alpha3.20F"})
    put("semantic_incomparable_resolution_boundary.json", {
        "incomparable_state": "SEMANTIC_INCOMPARABLE",
        "automatic_tradeoff_or_weighted_score": False,
        "selection_recommendation": "DEFERRED",
        "next_action": "separately preregister resolution; no extra inference implied"})
    put("alpha3_20f_handoff_contract.json", {
        "builder_v4_contract_mutation_in_alpha3_20e_or_e1": False,
        "final_contract_freeze_only_after_complete_valid_semantic_selection": True,
        "final_freeze_stage": "alpha3.20F",
        "v3_cannot_reenter": True})
    # Scan model-visible wrapper and structured fields, not ordinary scientific
    # Body/proposition text, which may naturally contain the same strings.
    require(all(set(row["request"]) == {"model", "thinking", "reasoning_effort",
                                            "response_format", "messages"}
                and set(json.loads(row["request"]["messages"][1]["content"].split(
                    "\n", 1)[1])) == {"blinded_group_token", "source_context", "candidates"}
                for row in built["requests"]),
            "SEMANTIC_ADJUDICATION_MODEL_PAYLOAD_FIREWALL_FAILURE")
    put("leakage_result_nonexposure_audit.json", {
        "model_visible_prompt_mentions_leakage_or_thresholds": False,
        "model_visible_payload_has_leakage_fields": False,
        "model_visible_payload_has_survivor_counts": False,
        "all_84_candidates_included_without_leakage_filter": True,
        "request_count_checked": 28})
    put("variant_identity_nonexposure_audit.json", {
        "model_visible_wrapper_has_v1_v2_or_prompt_variant_identity": False,
        "private_arm_mapping_path": "semantic_group_token_mapping_private.jsonl",
        "private_group_mapping_sha256": group_map_sha,
        "private_candidate_mapping_sha256": candidate_map_sha,
        "direct_variant_comparison_requested": False,
        "separate_arm_contexts": True,
        "random_token_count": 112})
    put("development_contamination_binding.json", {
        "historical_role": "SEEN_DEVELOPMENT_HISTORY",
        "upstream_candidate_manifest": ref(d.OUT /
            "alpha3_20d_candidate_identity_manifest.jsonl"),
        "new_blinded_request_manifest_sha256": request_sha,
        "new_scientific_sources_used": False,
        "future_fresh_heldout_reuse_prohibited": True})
    put("active_deepseek_model_audit.json", {
        "future_provider": "DeepSeek", "future_model": "deepseek-flash",
        "thinking": "enabled", "reasoning_effort": "high",
        "other_model_fallback": False,
        "provider_calls_now": 0})
    for directory, root, marker_name in (
        (d.OUT, D_ROOT, "search_plan_v24_dev_alpha3_20d_sha256"),
        (c.OUT, d.C_ROOT, "search_plan_v24_dev_alpha3_20c_sha256"),
        (b.OUT, c.B_ROOT, "search_plan_v24_dev_alpha3_20b_sha256")):
        d.frozen_root(directory, marker_name, root)
    put("historical_preservation_audit.json", {
        "alpha3_20b_c_d_roots_verified_before_and_after": True,
        "historical_assets_modified": False})
    put("pre_handoff_correction_audit.json", {
        "provisional_snapshot_path":
            "runs/20261003_search_plan_v24_dev_alpha3_20e_semantic_adjudication_preregistration_offline_preflight_superseded",
        "provisional_snapshot_root_sha256":
            "c444ac00f302259d4bd87ba6feb4715ea7935de5dbf9b635ea55c64c458da646",
        "provisional_request_manifest_sha256":
            "27a4e0e7432eab8f13d8506a19003e78fab6c5a92c2659197a9193dddac26b37",
        "correction": "model-facing output JSON key layout made explicit; scientific rubric, source universe, provider binding, blinding, and selection policy unchanged",
        "provisional_provider_calls": 0,
        "provisional_snapshot_never_authorized_for_execution": True})
    put("scientific_state_safety_audit.json", {
        "provider_calls": 0, "deepseek_calls": 0, "llm_calls": 0,
        "network_calls": 0, "quality_calls": 0, "builder_calls": 0,
        "semantic_adjudication_calls": 0,
        "new_scientific_sources_used": False,
        "historical_assets_modified": False})
    validation = {"status": "completed",
        "alpha3_20e_classification":
            "BLINDED_V1_V2_SEMANTIC_ADJUDICATION_REQUESTS_FROZEN",
        "alpha3_20d_root_verified": True,
        "development_only": True,
        "v1_candidate_count": 42, "v2_candidate_count": 42,
        "semantic_candidate_count": 84,
        "v3_included_in_semantic_adjudication": False,
        "semantic_group_count": 28, "candidates_per_group": 3,
        "variant_identity_exposed_to_model": False,
        "leakage_result_exposed_to_model": False,
        "leakage_threshold_exposed_to_model": False,
        "direct_variant_comparison_requested": False,
        "semantic_rubric_frozen": True,
        "semantic_overall_state_controller_derived": True,
        "weighted_semantic_score_used": False,
        "controller_owned_protocol_metadata": True,
        "model_required_to_emit_schema_version": False,
        "development_semantic_fidelity_rubric_v1_sha256": rubric_sha,
        "development_semantic_adjudication_response_envelope_v1_sha256": envelope_sha,
        "semantic_adjudication_prompt_template_sha256": prompt_sha,
        "semantic_adjudication_request_manifest_sha256": request_sha,
        "planned_semantic_adjudication_calls": 28,
        "provider": "DeepSeek", "model": "deepseek-flash",
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "new_scientific_sources_used": False,
        "material_runtime_policy_unresolved_count": 0,
        "next_stage_recommendation": NEXT,
        "historical_assets_modified": False}
    put("validation.json", validation)
    put("summary.json", {"status": "completed",
        "classification": validation["alpha3_20e_classification"],
        "v1_candidate_count": 42, "v2_candidate_count": 42,
        "semantic_group_count": 28,
        "planned_semantic_adjudication_calls": 28,
        "provider_calls": 0,
        "next_stage_recommendation": NEXT})
    root = d.c.root_hash(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    return validation


def main() -> None:
    state = preflight()
    seed = secrets.token_bytes(32)
    built = build(state, seed)
    validation = freeze(state, built, seed)
    print(json.dumps({"status": validation["status"],
        "classification": validation["alpha3_20e_classification"],
        "request_count": 28,
        "root_sha256": (OUT / ROOT_MARKER).read_text().strip()},
        sort_keys=True))


if __name__ == "__main__":
    main()
