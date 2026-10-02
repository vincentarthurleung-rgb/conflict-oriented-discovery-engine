#!/usr/bin/env python3
"""Freeze three seen-data Builder V4 variants and 42 requests, offline only."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
OUT = RUNS / "20261002_search_plan_v24_dev_alpha3_20b_proposition_abstraction_prompt_freeze_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_20b_sha256"
MASTER = RUNS / "20261002_search_plan_v24_dev_alpha3_20_post_alpha3_19_development_master_preregistration_offline"
A20 = RUNS / "20261002_search_plan_v24_dev_alpha3_20a_evidence_reference_v4_offline_validation"
E = RUNS / "20261002_search_plan_v24_dev_alpha3_19e_construction_document_anchor_builder_freeze_offline"
G = RUNS / "20261002_search_plan_v24_dev_alpha3_19g_primary_attempt_closure_offline"
V3_SCHEMA = RUNS / "20261001_search_plan_v24_dev_alpha3_18b1_grounding_contract_consistency_audit_offline/builder_output_schema_v3.json"
USER_TEMPLATE = RUNS / "20260927_search_plan_v24_dev_alpha3_18a1_source_contract_resolution_offline/proposition_builder_v2_1_user_prompt_template.txt"
RETRY_CONTRACT = RUNS / "20261001_search_plan_v24_dev_alpha3_18b_builder_execution_preregistration_offline/builder_transport_retry_contract.json"
ROOTS = [
    (MASTER, "search_plan_v24_dev_alpha3_20_master_prereg_sha256",
     "8a8edb619c2ad2a31e4b0f6398ae43e3d05de74ae31baddeb611b0cd3e0cd3e6"),
    (A20, "search_plan_v24_dev_alpha3_20a_sha256",
     "ecc4549aca4329ac3a910fc933f070333175ec2aa2c0fc728cd1279d9e274364"),
    (E, "search_plan_v24_dev_alpha3_19e_sha256",
     "afcc320cc2e0e352d77fdc4370b87f146b63e7f089663b60dac80c570c87bb87"),
    (G, "search_plan_v24_dev_alpha3_19g_sha256",
     "de6567e7dba0b4f42f936f9e8a5a15f01a09346526bb64f8359b394e769e5da5"),
]
EVIDENCE_SHA = "156424459bd499272f6dba5a466216ffbe72fe96039045ae8bc44dd7b40b5612"
ABSTRACTION_SHA = "5ab84eebd9fb8b6a4d7d7600869c5860aa19fbd815ad6dc4c139a6332550fc99"
FRAGMENT_SHA = "5f93196930af2ff0d436537372a90377ee70acad393c7567b0f25a947e7d28ad"
V3_SCHEMA_SHA = "092961a96fe2985633054b68760cd409780e7e44fbfb2c5cd14c12ed9a51e326"
USER_TEMPLATE_SHA = "bcc8856e1b748300431c36d6e6a661581f882ee6cf40030edcdc9edae3eb208b"
RETRY_SHA = "6a6033d52530d8dc4c28a7b9cb6c58d8b748eebee817605325e24774d77b32e4"
NEXT = "AUTHORIZE_EXACT_42_ALPHA3_20C_BUILDER_V4_DEVELOPMENT_CALLS"

COMMON_SYSTEM_PREFIX = (
    "You are proposition_pool_builder. Analyze only the single supplied source article. "
    "Propose zero to three independent, neutral, experimentally grounded scientific candidate "
    "propositions. Do not rank or prefer candidates. Do not use external knowledge, search "
    "behavior, retrieval performance, or other articles. If no sufficiently grounded "
    "proposition is available, return an empty candidates array.\n"
    "For each candidate, select one exact verbatim quote from the supplied canonical Body "
    "as construction_evidence_span.exact_text. The Abstract is context only and cannot be "
    "the sole grounding source. Do not output source_field, character offsets, paragraph IDs, "
    "or anchor IDs; the controller derives them by exact matching in the canonical Body.\n"
    "Keep the verbatim evidence quote separate from neutral_proposition. State a faithful, "
    "testable scientific relation preserving the actor or intervention, observed response, "
    "direction, essential biological context, and source-supported qualifiers. Scientific "
    "fidelity takes priority over wording novelty. Do not change direction, invent mechanism, "
    "drop essential context, broaden the studied population or context, or change actor or "
    "response merely to vary wording.\n"
    "Proposition-abstraction instruction: "
)
COMMON_SYSTEM_SUFFIX = (
    "\nReturn one JSON object matching the supplied schema; no Markdown or commentary. "
    "The opaque source_record_token is only a response-binding handle.\n"
)
FORBIDDEN_SYSTEM_PHRASES = (
    "8-token", "eight consecutive shared tokens", "jaccard", "0.80",
    "leakage threshold", "detector", "passing leakage", "avoiding leakage",
    "beating lexical checks", "leakage", "pmid", "pmcid", "doi",
)


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def obj(path: Path) -> dict:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line]


def ref(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes())}


def root_hash(directory: Path, marker: str) -> str:
    require(not any(path.is_symlink() for path in directory.rglob("*")),
            "FROZEN_SYMLINK:" + directory.name)
    files = sorted(path for path in directory.rglob("*") if path.is_file()
                   and path.name != marker)
    return sha(canonical([[str(path.relative_to(directory)), sha(path.read_bytes())]
                          for path in files]))


def verify_roots() -> list[dict]:
    verified = []
    for directory, marker, expected in ROOTS:
        require((directory / marker).read_text().strip() == expected
                and root_hash(directory, marker) == expected,
                "UPSTREAM_ROOT_MISMATCH:" + directory.name)
        verified.append({"path": str(directory.relative_to(ROOT)),
                         "sha256": expected, "root_marker": marker, "verified": True})
    return verified


def put(name: str, value: object) -> str:
    raw = canonical(value) + b"\n"
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
    return sha(raw)


def put_text(name: str, value: str) -> str:
    raw = value.encode("utf-8")
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
    require(not OUT.exists(), "ALPHA320B_OUTPUT_ALREADY_EXISTS_NO_REWRITE")
    historical_roots = verify_roots()
    contract_paths = [
        (MASTER / "evidence_reference_contract_v4.json", EVIDENCE_SHA,
         MASTER / "evidence_reference_contract_v4_sha256"),
        (MASTER / "proposition_abstraction_contract_v1.json", ABSTRACTION_SHA,
         MASTER / "proposition_abstraction_contract_v1_sha256"),
        (A20 / "builder_output_schema_v4_evidence_fragment.json", FRAGMENT_SHA,
         A20 / "builder_output_schema_v4_evidence_fragment_sha256"),
    ]
    require(all(sha(path.read_bytes()) == expected
                and marker_path.read_text().strip() == expected
                for path, expected, marker_path in contract_paths),
            "UPSTREAM_CONTRACT_HASH_MISMATCH")
    require(sha(V3_SCHEMA.read_bytes()) == V3_SCHEMA_SHA
            and sha(USER_TEMPLATE.read_bytes()) == USER_TEMPLATE_SHA
            and sha(RETRY_CONTRACT.read_bytes()) == RETRY_SHA,
            "HISTORICAL_SCHEMA_TEMPLATE_OR_RETRY_HASH_MISMATCH")
    master_variants = obj(MASTER / "bounded_prompt_variant_policy.json")
    variants = master_variants["variants"]
    require(len(variants) == 3
            and master_variants["maximum_prospective_scientific_prompt_variants"] == 3
            and len({row["variant_id"] for row in variants}) == 3
            and all(sha(row["abstraction_instruction"].encode()) ==
                    row["instruction_sha256"] for row in variants)
            and [row["variant_id"] for row in variants] ==
                obj(MASTER / "prompt_variant_selection_rule.json")["tie_break_order"],
            "PROMPT_VARIANT_AUTHORITY_UNRESOLVED")
    require(obj(MASTER / "prompt_variant_selection_rule.json")["baseline_variant_id"]
            == variants[0]["variant_id"], "REFERENCE_VARIANT_AUTHORITY_MISMATCH")
    corpus_contract = obj(MASTER / "development_corpus_selection_contract.json")
    corpus = corpus_contract["selected_request_identities"]
    require(corpus_contract["request_count"] == len(corpus) == 14
            and sha(canonical(corpus)) == corpus_contract["selected_request_identity_set_sha256"]
            and corpus_contract["historical_request_manifest"]["sha256"] ==
                sha((E / "alpha3_19_builder_v3_request_manifest.jsonl").read_bytes()),
            "DEVELOPMENT_CORPUS_IDENTITY_HASH_MISMATCH")
    prior_requests = rows(E / "alpha3_19_builder_v3_request_manifest.jsonl")
    doc_rows = {row["source_token"]: row for row in
                rows(E / "construction_document_manifest.jsonl")}
    require(len(prior_requests) == len(doc_rows) == 14
            and [row["ordinal"] for row in prior_requests] == list(range(1, 15)),
            "DEVELOPMENT_SOURCE_COUNT_OR_ORDER_MISMATCH")
    user_template = USER_TEMPLATE.read_text(encoding="utf-8")
    require(user_template == (
        "Source token: {source_record_token}\nAbstract: {frozen_abstract}\n"
        "Body: {frozen_body}\nOutput schema: {output_schema_json}\n"),
        "FROZEN_USER_INPUT_TEMPLATE_MISMATCH")
    documents = {}
    for frozen, prior in zip(corpus, prior_requests, strict=True):
        token = frozen["source_record_token"]
        require(prior["ordinal"] == frozen["ordinal"]
                and prior["source_token"] == token
                and prior["request_sha256"] == frozen["request_sha256"]
                and prior["document_sha256"] == frozen["construction_document_sha256"]
                and token in doc_rows,
                "DEVELOPMENT_SOURCE_IDENTITY_MISMATCH")
        doc_row = doc_rows[token]
        doc_path = E / doc_row["document_path"]
        require(sha(doc_path.read_bytes()) == doc_row["document_sha256"],
                "DEVELOPMENT_DOCUMENT_HASH_MISMATCH")
        document = obj(doc_path)
        old_user = prior["request"]["messages"][1]["content"]
        require(old_user.count("Body: " + document["body_text"]) == 1
                and old_user.count("Abstract: " + document["abstract_text"]) == 1,
                "FROZEN_BODY_OR_ABSTRACT_INPUT_NOT_VISIBLE")
        documents[token] = document
    a20_validation = obj(A20 / "validation.json")
    require(a20_validation["alpha3_20a_classification"] ==
            "EVIDENCE_REFERENCE_V4_VALIDATED"
            and a20_validation["material_runtime_policy_unresolved_count"] == 0,
            "V4_LOCALIZATION_NOT_READY")
    v3 = obj(V3_SCHEMA)["schema"]
    fragment = obj(A20 / "builder_output_schema_v4_evidence_fragment.json")
    span_fragment = fragment["model_generated_candidate_evidence_schema"][
        "properties"]["construction_evidence_span"]
    require(span_fragment["required"] == ["exact_text"]
            and set(span_fragment["properties"]) == {"exact_text"}
            and fragment["model_generated_offsets_required_or_allowed"] is False,
            "V4_EVIDENCE_FRAGMENT_MISMATCH")
    retry = obj(RETRY_CONTRACT)
    provider_binding = obj(E / "builder_provider_binding_alpha3_19.json")
    require(retry["automatic_retry"] is False
            and retry["known_no_inference_transport_retry_enabled"] is False
            and retry["retry_after_ambiguous_execution"] is False
            and provider_binding["provider"] == "DeepSeek"
            and provider_binding["model"] == "deepseek-flash"
            and provider_binding["thinking"] == {"type": "enabled"}
            and provider_binding["reasoning_effort"] == "high",
            "FROZEN_RUNTIME_BASELINE_MISMATCH")
    return locals()


def build(state: dict) -> dict:
    v4_schema = copy.deepcopy(state["v3"])
    candidates = v4_schema["properties"]["candidates"]
    old_item = candidates["items"]
    old_fields = set(old_item["properties"])
    old_required = set(old_item["required"])
    old_item["properties"]["construction_evidence_span"] = copy.deepcopy(
        state["span_fragment"])
    require(set(old_item["properties"]) == old_fields
            and set(old_item["required"]) == old_required
            and candidates["minItems"] == 0 and candidates["maxItems"] == 3
            and set(old_item["properties"]["construction_evidence_span"]["properties"])
                == {"exact_text"},
            "BUILDER_V4_SCIENTIFIC_SCHEMA_DRIFT")
    schema_json = canonical(v4_schema).decode("utf-8")
    full_templates = []
    systems = []
    for variant in state["variants"]:
        instruction = variant["abstraction_instruction"]
        system = COMMON_SYSTEM_PREFIX + instruction + COMMON_SYSTEM_SUFFIX
        require(all(banned not in system.lower() for banned in FORBIDDEN_SYSTEM_PHRASES),
                "LEAKAGE_POLICY_EXPOSED_TO_MODEL_PROMPT")
        template = "SYSTEM:\n" + system + "USER:\n" + state["user_template"]
        require(template.count(instruction) == 1, "VARIANT_INSTRUCTION_NOT_UNIQUE")
        systems.append(system)
        full_templates.append(template)
    sanitized_templates = [full_templates[i].replace(
        state["variants"][i]["abstraction_instruction"],
        "<FROZEN_PROPOSITION_ABSTRACTION_INSTRUCTION>") for i in range(3)]
    require(len(set(sanitized_templates)) == 1,
            "PROMPT_VARIANT_DIFFERENCE_FIREWALL_FAILED")

    per_variant: list[list[dict]] = [[], [], []]
    combined = []
    equivalence = []
    for source in state["prior_requests"]:
        token, source_ordinal = source["source_token"], source["ordinal"]
        document = state["documents"][token]
        user = state["user_template"].format(
            source_record_token=token,
            frozen_abstract=document["abstract_text"],
            frozen_body=document["body_text"],
            output_schema_json=schema_json)
        scientific_input_sha = sha(canonical({
            "abstract_text": document["abstract_text"],
            "body_text": document["body_text"]}))
        source_rows = []
        normalized_requests = []
        for variant_index, variant in enumerate(state["variants"]):
            request = {
                "model": "deepseek-flash",
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": systems[variant_index]},
                    {"role": "user", "content": user}],
            }
            require(not any(key in request for key in ("temperature", "top_p",
                                                    "max_tokens", "stream")),
                    "FROZEN_RUNTIME_PARAMETER_CONFOUND")
            require(user.count("Body: " + document["body_text"]) == 1
                    and user.count("Abstract: " + document["abstract_text"]) == 1
                    and user.startswith("Source token: " + token + "\n"),
                    "SOURCE_SCIENTIFIC_INPUT_CHANGED")
            row = {
                "execution_ordinal": (source_ordinal - 1) * 3 + variant_index + 1,
                "source_ordinal": source_ordinal,
                "variant_index": variant_index + 1,
                "variant_id_controller_only": variant["variant_id"],
                "private_source_token": token,
                "historical_request_sha256": source["request_sha256"],
                "construction_document_sha256": source["document_sha256"],
                "scientific_source_input_sha256": scientific_input_sha,
                "request": request,
                "request_sha256": sha(canonical(request)),
                "historical_role": "SEEN_DEVELOPMENT_HISTORY",
            }
            per_variant[variant_index].append(row)
            combined.append(row)
            source_rows.append(row)
            normalized = copy.deepcopy(request)
            normalized["messages"][0]["content"] = normalized["messages"][0][
                "content"].replace(variant["abstraction_instruction"],
                                   "<FROZEN_PROPOSITION_ABSTRACTION_INSTRUCTION>")
            normalized_requests.append(canonical(normalized))
        audit = {
            "source_ordinal": source_ordinal,
            "private_source_token": token,
            "scientific_source_input_sha256": scientific_input_sha,
            "per_variant_request_sha256": [row["request_sha256"] for row in source_rows],
            "scientific_input_byte_equivalent":
                len({row["request"]["messages"][1]["content"] for row in source_rows}) == 1,
            "only_authorized_abstraction_instruction_differs":
                len(set(normalized_requests)) == 1,
            "variant_request_confound": len(set(normalized_requests)) != 1,
        }
        equivalence.append(audit)
    require([len(rows) for rows in per_variant] == [14, 14, 14]
            and len(combined) == 42
            and [row["execution_ordinal"] for row in combined] == list(range(1, 43))
            and all(not row["variant_request_confound"] and
                    row["scientific_input_byte_equivalent"] for row in equivalence),
            "VARIANT_REQUEST_CONFOUND_DETECTED")
    return locals()


def freeze(state: dict, built: dict) -> None:
    OUT.mkdir()
    put("alpha3_20_master_root_verification.json", {
        "root_sha256": ROOTS[0][2], "verified": True})
    put("alpha3_20a_root_verification.json", {
        "root_sha256": ROOTS[1][2], "verified": True,
        "classification": "EVIDENCE_REFERENCE_V4_VALIDATED"})
    put("evidence_reference_contract_v4_binding.json", {
        "contract": ref(MASTER / "evidence_reference_contract_v4.json"),
        "sha256_marker_verified": True,
        "model_owns_exact_body_quote": True,
        "controller_owns_coordinates": True})
    put("proposition_abstraction_contract_v1_binding.json", {
        "contract": ref(MASTER / "proposition_abstraction_contract_v1.json"),
        "sha256_marker_verified": True,
        "scientific_fidelity_priority": True,
        "model_candidate_specific_examples": 0})
    put("master_prompt_variant_authority.json", {
        "master_artifact": ref(MASTER / "bounded_prompt_variant_policy.json"),
        "all_variant_definitions_bound_to_master": True,
        "mapping": [{"controller_variant_id": f"ABSTRACTION_VARIANT_{i}",
                     "master_variant_id": variant["variant_id"],
                     "instruction_sha256": variant["instruction_sha256"]}
                    for i, variant in enumerate(state["variants"], 1)],
        "reference_variant": state["variants"][0]["variant_id"],
        "variant_wording_invented_after_master": False})
    template_shas = []
    for i, template in enumerate(built["full_templates"], 1):
        value = put_text(f"prompt_variant_{i}_full_template.txt", template)
        marker(f"prompt_variant_{i}_sha256", value)
        template_shas.append(value)
    put("prompt_variant_difference_audit.json", {
        "common_template_after_removing_exact_authorized_instruction_sha256":
            sha(built["sanitized_templates"][0].encode()),
        "all_three_common_templates_equal":
            len(set(built["sanitized_templates"])) == 1,
        "only_authorized_proposition_abstraction_instruction_differs": True,
        "fourth_variant_allowed": False,
        "source_specific_prompt_tuning_used": False,
        "leakage_thresholds_exposed_to_model": False,
        "historical_failed_candidate_examples_used": False})
    full_schema = {
        "schema_version": "BuilderOutputSchemaV4",
        "status": "PROSPECTIVE_SEEN_DATA_DEVELOPMENT",
        "historical_scientific_schema_source": ref(V3_SCHEMA),
        "frozen_evidence_fragment": ref(A20 /
                                        "builder_output_schema_v4_evidence_fragment.json"),
        "only_model_payload_schema_delta_from_v3":
            "construction_evidence_span has only required exact_text; controller derives source_field and coordinates",
        "schema": built["v4_schema"],
        "source_record_token_role": "OPAQUE_NONSEMANTIC_RESPONSE_BINDING_HANDLE",
        "model_generated_offsets_required_or_allowed": False,
        "candidate_cardinality": {"minimum": 0, "maximum": 3},
        "historical_v3_modified": False,
    }
    schema_sha = put("builder_output_schema_v4.json", full_schema)
    marker("builder_output_schema_v4_sha256", schema_sha)
    grounding = {
        "schema_version": "BuilderGroundingContractV4",
        "status": "PROSPECTIVE_SEEN_DATA_DEVELOPMENT",
        "evidence_reference_contract_v4_sha256": EVIDENCE_SHA,
        "builder_output_schema_v4_sha256": schema_sha,
        "localizer_implementation": ref(ROOT /
                                      "scripts/search_plan_v24_alpha320a_v4_localizer.py"),
        "model_owned_evidence": "exact verbatim canonical BODY quote",
        "controller_owned": ["source_field=body", "exact occurrence count",
                             "paragraph binding", "zero-based start and exclusive end offsets",
                             "anchor identity", "coordinate provenance"],
        "zero_match_state": "GROUNDING_TEXT_NOT_FOUND",
        "multiple_match_state": "GROUNDING_TEXT_NONUNIQUE",
        "unique_match_requirement": "one canonical BODY paragraph contains full quote",
        "cross_paragraph_specific_state": "GROUNDING_TEXT_CROSSES_PARAGRAPH_BOUNDARY",
        "cross_paragraph_master_alias": "GROUNDING_PARAGRAPH_BOUNDARY_INVALID",
        "abstract_only_or_other_document_grounding_allowed": False,
        "fuzzy_or_semantic_rescue_allowed": False,
        "historical_v3_states_modified": False,
    }
    grounding_sha = put("builder_grounding_contract_v4.json", grounding)
    marker("builder_grounding_contract_v4_sha256", grounding_sha)
    put("builder_v4_model_controller_ownership_matrix.json", {
        "model_generated": ["opaque source_record_token response binding echo",
                            "scientific candidate fields", "exact BODY evidence quote",
                            "neutral proposition"],
        "controller_generated": ["fixed source_field body", "paragraph identity",
                                 "start/end coordinates", "anchor identity",
                                 "provenance", "variant identity"],
        "model_generated_offsets_required": False,
        "model_generated_source_field_required": False,
        "candidate_evidence_and_proposition_separate": True})
    put("builder_v4_source_identity_firewall.json", {
        "model_visible_wrapper_fields": ["opaque source_record_token",
                                         "frozen scientific Abstract context",
                                         "frozen canonical Body", "output schema"],
        "clear_pmid_pmcid_doi_title_authors_journal_added_by_controller": False,
        "private_filesystem_path_or_source_mapping_exposed": False,
        "variant_id_controller_only": True,
        "historical_candidate_or_leakage_examples_exposed": False,
        "ordinary_scientific_body_content_not_classified_as_metadata_leak": True,
        "all_42_wrapper_templates_same_except_authorized_variant_instruction": True})
    put("development_corpus_binding.json", {
        "master_corpus_contract": ref(MASTER / "development_corpus_selection_contract.json"),
        "historical_request_manifest": ref(E /
                                          "alpha3_19_builder_v3_request_manifest.jsonl"),
        "source_count": 14,
        "selected_request_identity_set_sha256": state["corpus_contract"][
            "selected_request_identity_set_sha256"],
        "all_14_sources_in_all_three_variants": True,
        "source_selection_based_on_alpha3_19_results": False,
        "new_scientific_sources_used": False})
    put("development_source_input_equivalence_spec.json", {
        "scientific_input": ["frozen abstract_text", "frozen body_text"],
        "same_user_message_per_source_across_three_variants": True,
        "same_source_token_and_output_schema_per_source": True,
        "authorized_variant_difference_region": "single exact master abstraction instruction in system message",
        "equivalence_test": "replace only that exact instruction with a sentinel, then compare canonical request bytes",
        "abstract_context_policy_unchanged": True,
        "body_grounding_policy_unchanged": True})
    put("variant_reference_rule.json", {
        "master_selection_rule": ref(MASTER / "prompt_variant_selection_rule.json"),
        "reference_variant_id": state["variants"][0]["variant_id"],
        "reference_controller_id": "ABSTRACTION_VARIANT_1",
        "reference_reason": "explicit master baseline and first frozen tie-break variant",
        "selected_before_model_execution": True,
        "outcome_based_reference_choice": False})
    put("variant_evaluation_dimensions.json", {
        "dimensions": ["response validity", "raw candidate count",
                       "exact evidence quote presence", "V4 unique localization success",
                       "structural completeness", "lexical leakage pass/fail"],
        "fixed_planned_source_denominator_per_variant": 14,
        "actual_complete_triplet_denominator_must_be_reported": True,
        "raw_candidate_denominator_must_be_reported_for_candidate_level_metrics": True,
        "model_offset_accuracy_not_scored": True,
        "weighted_composite_score": None,
        "invalid_completed_response_counts_as_inference_and_validity_failure": True,
        "schema_valid_zero_candidate_response_counts_as_valid": True})
    put("structural_completeness_contract.json", {
        "checks_before_model_calls": [
            "schema-valid nonempty actor_or_intervention",
            "schema-valid nonempty action",
            "schema-valid nonempty response_or_endpoint",
            "relation_direction in frozen enum",
            "schema-valid nonempty biological_unit",
            "preserve species and intrinsic conditioning, therapy, disease/genotype context fields as required nullable representation"],
        "essential_context_representation":
            "biological_unit plus existing species and intrinsic context slots when applicable; no new unpreregistered scientific field",
        "mechanical_presence_proves_scientific_truth": False,
        "semantic_fidelity_if_needed": "separate alpha3.20E development adjudication"})
    put("variant_eligibility_rule.json", {
        "reference_variant": state["variants"][0]["variant_id"],
        "comparison_scope": "same fixed source identities; final selection requires 14 complete variant triplets",
        "absolute_minimum_for_final_selection":
            "at least one schema-valid nonzero response and one structurally complete, uniquely BODY-grounded candidate across the fixed 14 requests",
        "non_leakage_gate_precedence": [
            "response validity must not regress against reference",
            "required structural completeness must not regress against reference",
            "V4 exact unique grounding must not regress against reference",
            "semantic scientific fidelity must be resolved if structural checks cannot establish it"],
        "per_request_nonregression":
            "a source covered by reference on each prerequisite must remain covered by candidate variant",
        "aggregate_nonregression":
            "total candidate count satisfying each prerequisite cannot be lower than reference across fixed 14 sources",
        "leakage_compared_only_after_non_leakage_eligibility": True,
        "semantic_fidelity_not_inferred_from_structure": True,
        "weighted_score": None})
    put("variant_selection_decision_tree.json", {
        "no_non_leakage_eligible_variant": "DO_NOT_SELECT_BUILDER_V4_VARIANT",
        "one_eligible_semantics_resolved": "may proceed toward alpha3.20F final freeze",
        "multiple_eligible_leakage_differs_semantics_unresolved":
            "PREREGISTER_ALPHA3_20E_DEVELOPMENT_SEMANTIC_ADJUDICATION",
        "multiple_eligible_tied_semantics_resolved":
            "choose first eligible in frozen V1,V2,V3 reference order",
        "after_semantics_resolved":
            "maximize fixed-request count with at least one candidate passing prerequisite gates and frozen leakage gate",
        "tie_break_order": [v["variant_id"] for v in state["variants"]],
        "subjective_prose_quality_tie_break": False,
        "weighted_score": None})
    put("semantic_adjudication_trigger.json", {
        "trigger":
            "variant selection depends on scientific-fidelity comparison not established by deterministic schema or structural checks",
        "required_action": "separately preregister alpha3.20E independent development semantic adjudication",
        "quality_calls_in_alpha3_20b": 0,
        "fresh_quality_or_alpha3_19_completion": False,
        "all_results_remain_seen_development_history": True})
    put("alpha3_20c_execution_order.json", {
        "ordering": "source-major, then frozen variant order V1,V2,V3",
        "source_count": 14, "variant_count": 3,
        "execution_ordinals": [{"execution_ordinal": row["execution_ordinal"],
                                "source_ordinal": row["source_ordinal"],
                                "variant_index": row["variant_index"],
                                "request_sha256": row["request_sha256"]}
                               for row in built["combined"]],
        "one_fresh_independent_context_per_source_variant": True,
        "cross_request_or_historical_output_context_allowed": False})
    put("alpha3_20c_runtime_policy.json", {
        "provider": "DeepSeek", "api_surface": "Chat Completions",
        "model": "deepseek-flash", "thinking": {"type": "enabled"},
        "reasoning_effort": "high", "response_format": {"type": "json_object"},
        "temperature": "omitted", "top_p": "omitted",
        "max_output_tokens": "omitted as in frozen development baseline",
        "stream": "omitted",
        "historical_provider_binding": ref(E / "builder_provider_binding_alpha3_19.json"),
        "historical_transport_retry_contract": ref(RETRY_CONTRACT),
        "automatic_retry": False,
        "known_no_inference_transport_retry_enabled": False,
        "ambiguous_execution_action": "STOP_NO_SECOND_SCIENTIFIC_INFERENCE",
        "completed_schema_invalid_action": "COUNT_INFERENCE_RECORD_INVALID_NO_SCIENTIFIC_RETRY",
        "schema_valid_zero_candidate_action": "RECORD_VALID_ZERO_NO_RETRY",
        "fallback_provider_or_model": False,
        "fresh_independent_context_per_pair": True,
        "partial_execution_final_variant_selection": "NO_SELECTION_UNTIL_14_COMPLETE_TRIPLETS_OR_SEPARATE_PREREGISTRATION",
        "calls_authorized_by_alpha3_20b": 0})
    put("alpha3_20c_call_budget.json", {
        "planned_development_sources": 14,
        "planned_prompt_variants": 3,
        "planned_development_builder_scientific_inference_events": 42,
        "maximum_one_scientific_inference_per_source_variant": True,
        "scientific_retry_or_repair_calls": 0,
        "builder_calls_authorized_now": 0,
        "quality_calls_authorized_now": 0,
        "separate_alpha3_20c_execution_authorization_required": True})
    variant_manifest_hashes = []
    for i, manifest in enumerate(built["per_variant"], 1):
        variant_manifest_hashes.append(put_rows(
            f"alpha3_20c_variant_{i}_request_manifest.jsonl", manifest))
    combined_sha = put_rows("alpha3_20c_combined_request_manifest.jsonl",
                            built["combined"])
    marker("alpha3_20c_combined_request_manifest_sha256", combined_sha)
    put_rows("per_source_variant_request_equivalence_audit.jsonl",
             built["equivalence"])
    put("all_alpha3_20c_requests_freeze_barrier.json", {
        "all_42_payloads_constructed_and_hashed_before_provider_access": True,
        "request_count": 42,
        "per_variant_manifest_sha256": variant_manifest_hashes,
        "combined_manifest_sha256": combined_sha,
        "prompt_template_sha256": template_shas,
        "builder_output_schema_v4_sha256": schema_sha,
        "builder_grounding_contract_v4_sha256": grounding_sha,
        "variant_request_confound_count": 0,
        "provider_calls_before_freeze": 0})
    put("leakage_policy_preservation.json", {
        "master_policy": ref(MASTER / "leakage_policy_preservation.json"),
        "eight_consecutive_shared_token_failure_threshold": 8,
        "qualifying_token_jaccard_failure_threshold": 0.80,
        "candidate_side": "neutral_proposition only",
        "source_side": "private source title and containing evidence sentence with frozen fallback",
        "evidence_quote_or_anchor_concatenated_candidate_side": False,
        "thresholds_changed": False,
        "comparison_policy_changed": False,
        "thresholds_exposed_to_model": False})
    put("historical_contamination_binding.json", {
        "combined_seen_source_registry": ref(MASTER /
                                             "alpha3_20_combined_seen_source_registry.jsonl"),
        "combined_seen_candidate_registry": ref(MASTER /
                                                "alpha3_20_combined_seen_candidate_registry.jsonl"),
        "source_pmid_count": 2420,
        "seen_candidate_identity_count": 145,
        "all_14_development_sources_seen": True,
        "all_future_alpha3_20c_outputs_role": "SEEN_DEVELOPMENT_HISTORY",
        "future_primary_fresh_heldout_reuse_prohibited": True})
    put("active_deepseek_model_audit.json", {
        "future_provider": "DeepSeek", "future_model": "deepseek-flash",
        "thinking": "enabled", "reasoning_effort": "high",
        "deepseek_v4_pro_future_fallback": False,
        "historical_model_provenance_changed": False,
        "provider_calls_now": 0})
    put("scientific_content_nonadaptation_audit.json", {
        "prompt_variant_instructions_copied_from_master_exactly": True,
        "historical_candidate_content_used_to_write_prompts": False,
        "historical_leakage_results_used_to_write_prompts": False,
        "source_specific_prompt_tuning_used": False,
        "historical_failed_candidate_examples_used": False,
        "new_scientific_sources_used": False,
        "scientific_source_text_unchanged_between_variants": True})
    require(verify_roots() == state["historical_roots"],
            "HISTORICAL_ROOT_CHANGED_DURING_ALPHA320B")
    put("historical_preservation_audit.json", {
        "all_upstream_roots_verified_before_and_after": True,
        "roots": state["historical_roots"],
        "historical_builder_output_schema_v3_modified": False,
        "alpha3_19_historical_results_modified": False,
        "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {
        "builder_calls": 0, "quality_calls": 0,
        "provider_calls": 0, "deepseek_calls": 0,
        "llm_calls": 0, "network_calls": 0,
        "builder_scientific_inference_events": 0,
        "quality_scientific_inference_events": 0,
        "new_scientific_sources_used": False,
        "historical_assets_modified": False})
    validation = {
        "status": "completed",
        "alpha3_20b_classification":
            "THREE_VARIANT_BUILDER_V4_DEVELOPMENT_REQUESTS_FROZEN",
        "alpha3_20_master_root_verified": True,
        "alpha3_20a_root_verified": True,
        "development_only": True,
        "development_source_count": 14,
        "prompt_variant_count": 3,
        "fourth_variant_allowed": False,
        "all_variant_definitions_bound_to_master": True,
        "builder_grounding_contract_v4_frozen": True,
        "builder_grounding_contract_v4_sha256": grounding_sha,
        "builder_output_schema_v4_frozen": True,
        "builder_output_schema_v4_sha256": schema_sha,
        "model_generated_offsets_required": False,
        "controller_owned_coordinates": True,
        "exact_body_quote_required": True,
        "fuzzy_grounding_allowed": False,
        "candidate_cardinality_min": 0,
        "candidate_cardinality_max": 3,
        "leakage_thresholds_changed": False,
        "leakage_comparison_policy_changed": False,
        "leakage_thresholds_exposed_to_model": False,
        "source_specific_prompt_tuning_used": False,
        "historical_failed_candidate_examples_used": False,
        "provider": "DeepSeek", "model": "deepseek-flash",
        "planned_development_sources": 14,
        "planned_prompt_variants": 3,
        "planned_development_builder_calls": 42,
        "variant_request_confound_count": 0,
        "prompt_variant_1_sha256": template_shas[0],
        "prompt_variant_2_sha256": template_shas[1],
        "prompt_variant_3_sha256": template_shas[2],
        "alpha3_20c_combined_request_manifest_sha256": combined_sha,
        "builder_calls": 0, "quality_calls": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "new_scientific_sources_used": False,
        "material_runtime_policy_unresolved_count": 0,
        "next_stage_recommendation": NEXT,
        "historical_assets_modified": False,
    }
    put("validation.json", validation)
    put("summary.json", {
        "status": "completed",
        "classification": validation["alpha3_20b_classification"],
        "development_source_count": 14,
        "prompt_variant_count": 3,
        "request_count": 42,
        "variant_request_confound_count": 0,
        "provider_calls": 0,
        "next_stage_recommendation": NEXT})
    root = root_hash(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    require(root_hash(OUT, ROOT_MARKER) == root,
            "ALPHA320B_ROOT_VERIFY_FAILED")
    print(json.dumps({"status": "completed", "root_sha256": root,
                      "builder_grounding_contract_v4_sha256": grounding_sha,
                      "builder_output_schema_v4_sha256": schema_sha,
                      "prompt_sha256": template_shas,
                      "combined_request_manifest_sha256": combined_sha}, sort_keys=True))


def main() -> None:
    state = preflight()
    built = build(state)
    freeze(state, built)


if __name__ == "__main__":
    main()
