#!/usr/bin/env python3
"""Freeze independent source-local proposition quality adjudication V2 offline."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17d_independent_quality_adjudication_v2_preregistration_offline"
UP = {
    "alpha3_17": (ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17_new_blinded_proposition_pool_preregistration_offline",
                  "search_plan_v24_dev_alpha3_17_sha256", "10bc7cc1f03b0cdf38b4409f624b10697ffef3939053601cfba2dc4ea74cece6"),
    "alpha3_17a": (ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline",
                   "search_plan_v24_dev_alpha3_17a_sha256", "a23e549cf9d83714782d4283c823ee94ce569f5f00f820fc2c4e0b9d3ee7248e"),
    "alpha3_17b": (ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17b_independent_proposition_quality_adjudication_preregistration_offline",
                   "search_plan_v24_dev_alpha3_17b_sha256", "76d0fe4153f9703ab5cf3f076f3fd04fe5f238d48e17154fc369c5e594527035"),
    "alpha3_17c": (ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17c_builder_cardinality_reconciliation_offline",
                   "search_plan_v24_dev_alpha3_17c_sha256", "01145d324a9bcf6d3d926afe1e4a1135c8b35d8b4404d473f32cb50e9608703d"),
}
BUILDER_ROOT = "8a50314aac4e5f8017109a047905981a91aa91ffb784e1ebde0f92256917ba33"
BUILDER_SCHEMA_ROOT = "5309d3edc9b8a40b64f6fc79e5f7a8e19ac4738808827b33cfe2eb3047db7849"
QUALITY_VERSION = "PropositionQualityAdjudicationV2"
SELECTOR_VERSION = "PropositionQualityOnePerSourceSelectorV1"
STATES = ["PASS", "FAIL", "UNRESOLVED"]
CRITERIA = [
    "EVIDENCE_SUPPORTS_PROPOSITION", "SCIENTIFICALLY_COHERENT", "EXPERIMENTALLY_TESTABLE",
    "DIRECTIONALLY_INTERPRETABLE", "SUFFICIENTLY_SPECIFIC", "NOT_TAUTOLOGICAL",
    "NOT_PURELY_DESCRIPTIVE_IF_FUNCTIONAL_RELATION_REQUIRED", "ACTOR_OR_INTERVENTION_IDENTIFIABLE",
    "RESPONSE_OR_ENDPOINT_IDENTIFIABLE", "BIOLOGICAL_CONTEXT_INTERPRETABLE",
]
DEFINITIONS = {
    "EVIDENCE_SUPPORTS_PROPOSITION": "The candidate's own frozen source evidence, with bounded local context, supports the proposition as written; no background-knowledge substitution.",
    "SCIENTIFICALLY_COHERENT": "Actor or intervention, relation, endpoint and stated context form an interpretable scientific claim, not a judgment that it is generally true.",
    "EXPERIMENTALLY_TESTABLE": "An experimental observation could in principle test the claim.",
    "DIRECTIONALLY_INTERPRETABLE": "The asserted relation or direction is clear enough for later relevance review, including when explicitly direction-unspecified.",
    "SUFFICIENTLY_SPECIFIC": "The stated claim has enough actor, relation, endpoint and context detail for meaningful paper-level relevance review; ignore Search Plan representability.",
    "NOT_TAUTOLOGICAL": "The claim is not merely a restatement of itself or a definitional identity.",
    "NOT_PURELY_DESCRIPTIVE_IF_FUNCTIONAL_RELATION_REQUIRED": "If the candidate claims a functional relation, the evidence is not merely descriptive co-occurrence.",
    "ACTOR_OR_INTERVENTION_IDENTIFIABLE": "The actor or intervention is interpretable from the stated scientific fields and supplied evidence.",
    "RESPONSE_OR_ENDPOINT_IDENTIFIABLE": "The response or endpoint is interpretable from the stated scientific fields and supplied evidence.",
    "BIOLOGICAL_CONTEXT_INTERPRETABLE": "The context stated by the candidate is scientifically interpretable; do not require unstated context fields.",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def aggregate(directory: Path, excluded: str) -> str:
    pairs = [[path.name, sha(path.read_bytes())] for path in sorted(directory.iterdir())
             if path.is_file() and path.name != excluded]
    return sha(canonical(pairs))


def write(name: str, value: Any) -> None:
    path = RUN / name
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.write_bytes(canonical(value) + b"\n")


def write_text(name: str, value: str) -> None:
    path = RUN / name
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.write_bytes(value.encode("utf-8"))


def quality_result(states: dict[str, str]) -> dict[str, Any]:
    if set(states) != set(CRITERIA) or any(value not in STATES for value in states.values()):
        raise ValueError("invalid or missing quality criterion")
    failed = sorted(key for key, value in states.items() if value == "FAIL")
    unresolved = sorted(key for key, value in states.items() if value == "UNRESOLVED")
    return {"overall_quality_state": "QUALITY_ELIGIBLE" if not failed and not unresolved else "QUALITY_INELIGIBLE",
            "failed_criteria": failed, "unresolved_criteria": unresolved}


def validate_response(response: dict[str, Any], expected_group_id: str,
                      expected_candidate_ids: set[str], visible_evidence_by_candidate: dict[str, str],
                      schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Closed-shape and identity validation; canonical output order is candidate ID."""
    if set(response) != set(schema["required"]) or response.get("schema_version") != QUALITY_VERSION:
        raise ValueError("response shape or version mismatch")
    if response.get("source_group_id") != expected_group_id:
        raise ValueError("wrong source group")
    if set(visible_evidence_by_candidate) != expected_candidate_ids:
        raise ValueError("frozen evidence-to-candidate binding mismatch")
    records = response.get("judgments")
    if not isinstance(records, list) or len(records) != len(expected_candidate_ids):
        raise ValueError("wrong record count")
    item_schema = schema["properties"]["judgments"]["items"]
    got: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != set(item_schema["required"]):
            raise ValueError("judgment shape mismatch")
        if record["schema_version"] != QUALITY_VERSION or not isinstance(record["candidate_id"], str):
            raise ValueError("judgment version or identity mismatch")
        candidate = record["candidate_id"]
        if candidate not in expected_candidate_ids or candidate in got:
            raise ValueError("extra or duplicate candidate")
        got.add(candidate)
        states = record["criteria"]
        if not isinstance(states, dict):
            raise ValueError("invalid criterion object")
        quality_result(states)
        reference = record["evidence_support_reference"]
        if reference is not None and (not isinstance(reference, str) or not (1 <= len(reference) <= 240)):
            raise ValueError("invalid bounded evidence reference")
        if states["EVIDENCE_SUPPORTS_PROPOSITION"] in ("PASS", "FAIL") and reference is None:
            raise ValueError("evidence judgment lacks reference")
        if reference is not None and reference not in visible_evidence_by_candidate[candidate]:
            raise ValueError("evidence reference is not in candidate-specific visible source text")
    if got != expected_candidate_ids:
        raise ValueError("missing candidate")
    return sorted(records, key=lambda record: record["candidate_id"])


def source_group_id(private_source_token: str) -> str:
    if not private_source_token or re.search(r"\s", private_source_token):
        raise ValueError("invalid private source token")
    return "qgv2_" + sha(canonical([QUALITY_VERSION, private_source_token]))


def evidence_packet(source_text: str, start: int, end: int, exact_span: str) -> dict[str, Any]:
    if not isinstance(source_text, str) or not isinstance(start, int) or not isinstance(end, int):
        raise ValueError("invalid frozen source text or offsets")
    if not (0 <= start < end <= len(source_text)) or source_text[start:end] != exact_span:
        raise ValueError("evidence span does not match frozen source")
    return {"exact_evidence_span": exact_span,
            "bounded_local_context": source_text[max(0, start - 240):min(len(source_text), end + 240)]}


def audit_quality_payload(payload: dict[str, Any], private_source_identity: dict[str, str]) -> None:
    """Fail before provider call if a source identity or forbidden field leaks."""
    allowed_top = {"source_group_id", "candidate_packets"}
    allowed_candidate = {"candidate_id", "scientific_fields", "neutral_proposition", "evidence"}
    allowed_science = {"actor_or_intervention", "action", "relation_direction", "response_or_endpoint",
                       "biological_unit", "species", "intrinsic_conditioning", "intrinsic_therapy_context",
                       "intrinsic_disease_or_genotype_context"}
    if set(payload) != allowed_top or not isinstance(payload["candidate_packets"], list):
        raise ValueError("quality payload top-level allowlist violation")
    if not 1 <= len(payload["candidate_packets"]) <= 3:
        raise ValueError("quality payload candidate count")
    if not isinstance(payload["source_group_id"], str) or not payload["source_group_id"].startswith("qgv2_"):
        raise ValueError("invalid opaque group ID")
    for candidate in payload["candidate_packets"]:
        if not isinstance(candidate, dict) or set(candidate) != allowed_candidate:
            raise ValueError("quality candidate field allowlist violation")
        if not isinstance(candidate["scientific_fields"], dict) or set(candidate["scientific_fields"]) != allowed_science:
            raise ValueError("quality scientific field allowlist violation")
        if not isinstance(candidate["evidence"], dict) or set(candidate["evidence"]) != {"exact_evidence_span", "bounded_local_context"}:
            raise ValueError("quality evidence field allowlist violation")
    serialized = canonical(payload).decode("utf-8")
    if re.search(r"\bPMC[0-9]+\b|\b10\.[0-9]{4,9}/\S+|\b[0-9]{6,9}\b", serialized, re.I):
        raise ValueError("source identifier pattern in quality payload")
    for value in private_source_identity.values():
        if isinstance(value, str) and value and re.search(
            r"(?<!\w)" + re.escape(value) + r"(?!\w)", serialized, re.I
        ):
            raise ValueError("private source identity in quality payload")
    if re.search(r"anchor[_-]?vault|Search Plan|\bP[012]\b|retrieval[_ -]?outcome", serialized, re.I):
        raise ValueError("forbidden architecture or anchor reference")


def select_one(source_group: str, eligible_ids: list[str], seed: str) -> str | None:
    if not eligible_ids:
        return None
    if len(set(eligible_ids)) != len(eligible_ids):
        raise ValueError("duplicate candidate IDs")
    if not re.fullmatch(r"[0-9a-f]{64}", seed):
        raise ValueError("invalid selector seed")
    return min(eligible_ids, key=lambda candidate: (
        sha(canonical([SELECTOR_VERSION, seed, source_group, candidate])), candidate))


def verify_upstream() -> tuple[Path, dict[str, Any], dict[str, Any]]:
    for directory, marker, expected in UP.values():
        if aggregate(directory, marker) != expected or (directory / marker).read_text().strip() != expected:
            raise RuntimeError(f"frozen root mismatch: {directory.name}")
    v2 = UP["alpha3_17c"][0]
    if sha((v2 / "proposition_builder_protocol_v2.json").read_bytes()) != BUILDER_ROOT:
        raise RuntimeError("BuilderProtocolV2 mismatch")
    if sha((v2 / "proposition_builder_output_schema_v2.json").read_bytes()) != BUILDER_SCHEMA_ROOT:
        raise RuntimeError("BuilderOutputSchemaV2 mismatch")
    if (v2 / "proposition_builder_protocol_v2_sha256").read_text().strip() != BUILDER_ROOT:
        raise RuntimeError("BuilderProtocolV2 digest marker mismatch")
    if (v2 / "proposition_builder_output_schema_v2_sha256").read_text().strip() != BUILDER_SCHEMA_ROOT:
        raise RuntimeError("BuilderOutputSchemaV2 digest marker mismatch")
    protocol = load(v2 / "proposition_builder_protocol_v2.json")
    schema = load(v2 / "proposition_builder_output_schema_v2.json")
    assert protocol["candidate_cardinality"] == {"minimum": 0, "maximum": 3}
    assert schema["schema"]["properties"]["candidates"]["maxItems"] == 3
    assert protocol["active_output_schema_sha256"] == BUILDER_SCHEMA_ROOT
    assert load(v2 / "validation.json")["status"] == "PASS"
    return UP["alpha3_17"][0], protocol, schema


def main() -> None:
    if RUN.exists():
        raise RuntimeError("alpha3.17d run exists; never regenerate frozen protocol")
    old, builder, builder_schema = verify_upstream()
    gate = load(old / "proposition_quality_gate.json")
    grounding = load(old / "construction_grounding_contract.json")
    duplicate = load(old / "duplicate_control_policy.json")
    choice = load(old / "one_proposition_per_source_policy.json")
    upstream_checks = gate["generic_required_checks"]
    expected_checks = ["scientifically_coherent", "experimentally_testable", "directionally_interpretable",
                       "sufficiently_specific", "not_tautological",
                       "not_purely_descriptive_if_functional_relation_required", "actor_and_response_identifiable",
                       "biological_context_interpretable"]
    if upstream_checks != expected_checks or not grounding["construction_evidence_span_present_required"]:
        raise RuntimeError("QUALITY_CRITERION_AUTHORITY_UNRESOLVED")
    if not choice["source_internal_choice_rule"].startswith("After generic grounding, leakage, quality, and duplicate gates"):
        raise RuntimeError("POOL_DUPLICATE_SELECTION_ORDER_UNRESOLVED")
    if not duplicate["semantic_near_duplicate_audit"]:
        raise RuntimeError("POOL_DUPLICATE_SELECTION_ORDER_UNRESOLVED")
    selector_seed = sha(b"PropositionQualityAdjudicationV2|one-per-source-selector-v1")
    RUN.mkdir()
    write("root_verification.json", {name: {"expected_sha256": expected,
          "actual_sha256": aggregate(directory, marker), "status": "PASS"}
          for name, (directory, marker, expected) in UP.items()})
    write("builder_protocol_v2_verification.json", {"status": "PASS", "builder_protocol_v2_sha256": BUILDER_ROOT,
          "builder_output_schema_v2_sha256": BUILDER_SCHEMA_ROOT,
          "authoritative_builder_candidate_cardinality": "0_TO_3",
          "alpha3_17a_0_to_1_active": False, "historical_alpha3_17a_preserved": True})
    authority = [
        ["EVIDENCE_SUPPORTS_PROPOSITION", "construction_grounding_contract.json", "source-grounded claim required; deterministic span existence alone is insufficient"],
        ["SCIENTIFICALLY_COHERENT", "proposition_quality_gate.json", "scientifically_coherent"],
        ["EXPERIMENTALLY_TESTABLE", "proposition_quality_gate.json", "experimentally_testable"],
        ["DIRECTIONALLY_INTERPRETABLE", "proposition_quality_gate.json", "directionally_interpretable"],
        ["SUFFICIENTLY_SPECIFIC", "proposition_quality_gate.json", "sufficiently_specific"],
        ["NOT_TAUTOLOGICAL", "proposition_quality_gate.json", "not_tautological"],
        ["NOT_PURELY_DESCRIPTIVE_IF_FUNCTIONAL_RELATION_REQUIRED", "proposition_quality_gate.json", "not_purely_descriptive_if_functional_relation_required"],
        ["ACTOR_OR_INTERVENTION_IDENTIFIABLE", "proposition_quality_gate.json", "actor_and_response_identifiable, conjunct A"],
        ["RESPONSE_OR_ENDPOINT_IDENTIFIABLE", "proposition_quality_gate.json", "actor_and_response_identifiable, conjunct B"],
        ["BIOLOGICAL_CONTEXT_INTERPRETABLE", "proposition_quality_gate.json", "biological_context_interpretable"],
    ]
    assert [row[0] for row in authority] == CRITERIA
    write("quality_criterion_authority_matrix.json", {"status": "RESOLVED", "criteria": [
        {"criterion": name, "upstream_artifact": source, "authority_mapping": basis,
         "upstream_sha256": sha((old / source).read_bytes())} for name, source, basis in authority],
        "actor_response_split_is_conjunctive_not_new_semantics": True,
        "evidence_support_separate_from_span_existence": True,
        "architecture_compatibility_added": False})
    write("proposition_quality_adjudicator_role.json", {"role": "proposition_quality_adjudicator",
          "distinct_from": ["proposition_pool_builder", "Search Planner", "model_retrieval_adjudicator", "Human Gold"],
          "output_authority": "model criterion judgments only, not expert gold or final pool eligibility",
          "fresh_context_per_source_call": True, "separate_model_invocation_from_builder": True,
          "same_model_is_not_independent_human_expertise": True})
    provider = builder["provider_configuration"]
    assert provider["provider"] == "DeepSeek" and provider["model"] == "deepseek-v4-pro"
    write("quality_provider_config.json", {"provider": "DeepSeek", "api_surface": "Chat Completions",
          "model": "deepseek-v4-pro", "thinking": {"type": "enabled"}, "reasoning_effort": "high",
          "response_format": {"type": "json_object"}, "temperature": "omitted", "top_p": "omitted",
          "service_tier": "omitted", "stream": False, "one_inference_attempt_per_source_group": True,
          "automatic_retry": False, "scientific_repair_calls": False,
          "openai_or_alternate_model_fallback": False,
          "ambiguous_provider_execution": "STOP_WITHOUT_REPLACEMENT_INFERENCE"})
    write("quality_visibility_contract.json", {"visible": ["opaque source-local group ID", "opaque candidate IDs",
          "candidate scientific fields", "neutral proposition", "candidate-specific evidence span", "bounded local evidence context"],
          "forbidden": ["builder reasoning or confidence", "builder prompt transcript", "builder self-evaluation",
          "model array position as preference", "Search Plan architecture or queries", "development cases or labels",
          "P0/P1/P2 outcomes", "retrieval results", "historical review outputs", "PMID", "PMCID", "DOI",
          "source title", "journal", "authors", "source rank or stratum", "private source token", "anchor-vault path"],
          "source_group_id": "qgv2_ + SHA256(canonical JSON [PropositionQualityAdjudicationV2, private source token])",
          "source_group_id_function": "scripts/search_plan_v24_alpha317d_preregister_quality_v2_offline.py:source_group_id",
          "private_source_token_not_in_payload": True})
    write("quality_source_context_contract.json", {"evidence_text": "candidate's exact frozen normalized span",
          "local_context": "up to 240 Unicode code points immediately before and after each span, clamped to the same frozen abstract/body field",
          "context_selection": "character offsets only; no scientific paragraph selection",
          "full_article_visible": False, "title_visible": False,
          "overlapping_candidate_spans": "preserve each candidate's own span and context separately",
          "source_identity_pattern_detected": "STOP_BEFORE_MODEL_CALL; no content repair or replacement"})
    write("semantic_grounding_criterion.json", {"criterion": "EVIDENCE_SUPPORTS_PROPOSITION",
          "question": "Does this candidate's own frozen source evidence and bounded local context support the proposition as written?",
          "states": STATES, "background_knowledge_only_support": "FAIL", "span_existence_alone_sufficient": False,
          "candidate_specific": True})
    write("quality_criteria_contract.json", {"required_criteria": CRITERIA,
          "definitions": DEFINITIONS, "all_required": True,
          "forbidden_criteria": ["PLANNER_COMPATIBLE", "QUERY_COMPILABLE", "PUBMED_RETRIEVABLE",
          "P0_RESOLVABLE", "P1_RESOLVABLE", "P2_RESOLVABLE", "LEXICON_SUPPORTED"],
          "search_architecture_success_prediction": False})
    write("criterion_state_contract.json", {"each_field_allowed_states": {name: STATES for name in CRITERIA},
          "numeric_confidence_allowed": False, "probability_or_score_allowed": False,
          "ranking_allowed": False, "aliases_or_lowercase_allowed": False})
    write("overall_quality_eligibility_rule.json", {"function": "scripts/search_plan_v24_alpha317d_preregister_quality_v2_offline.py:quality_result",
          "QUALITY_ELIGIBLE_iff": "all ten required criteria exactly PASS",
          "otherwise": "QUALITY_INELIGIBLE", "FAIL_or_UNRESOLVED_is_ineligible": True,
          "failure_provenance": ["failed_criteria", "unresolved_criteria"],
          "model_emits_overall_state": False, "model_emits_final_pool_state": False})
    criterion_schema = {"type": "object", "additionalProperties": False,
                        "required": CRITERIA,
                        "properties": {name: {"type": "string", "enum": STATES} for name in CRITERIA}}
    judgment_schema = {"type": "object", "additionalProperties": False,
                       "required": ["schema_version", "candidate_id", "criteria", "evidence_support_reference"],
                       "properties": {"schema_version": {"const": QUALITY_VERSION},
                                      "candidate_id": {"type": "string", "minLength": 1},
                                      "criteria": criterion_schema,
                                      "evidence_support_reference": {"type": ["string", "null"], "minLength": 1, "maxLength": 240}}}
    output_schema = {"type": "object", "additionalProperties": False,
                     "required": ["schema_version", "source_group_id", "judgments"],
                     "properties": {"schema_version": {"const": QUALITY_VERSION},
                                    "source_group_id": {"type": "string", "minLength": 1},
                                    "judgments": {"type": "array", "minItems": 1, "maxItems": 3,
                                                  "items": judgment_schema}}}
    write("proposition_quality_adjudication_v2_schema.json", {"artifact_schema_version": QUALITY_VERSION,
          "schema": output_schema, "overall_quality_state_model_field": False,
          "field_specific_enum_domains": True})
    system_prompt = ("You are proposition_quality_adjudicator, a separate model adjudicator of source-grounded candidate propositions. "
        "Judge each candidate independently against the named scientific criteria and only its own de-identified evidence. "
        "Do not compare, rank, prefer, select, or score candidates. Do not infer from other articles or outside knowledge. "
        "EVIDENCE_SUPPORTS_PROPOSITION asks whether the supplied source evidence supports the proposition as written, not merely whether the span exists. "
        "SCIENTIFICALLY_COHERENT asks whether actor, relation, endpoint, and stated context form an interpretable claim, not whether it is generally true. "
        "EXPERIMENTALLY_TESTABLE asks whether the claim could in principle be tested by experimental observation. "
        "DIRECTIONALLY_INTERPRETABLE asks whether asserted relation semantics are clear. "
        "SUFFICIENTLY_SPECIFIC asks whether paper-level relevance could later be meaningfully adjudicated, not whether any search system can retrieve it. "
        "NOT_TAUTOLOGICAL asks whether the claim is more than a definition or self-restatement. "
        "NOT_PURELY_DESCRIPTIVE_IF_FUNCTIONAL_RELATION_REQUIRED asks whether evidence for a functional claim goes beyond mere descriptive co-occurrence. "
        "ACTOR_OR_INTERVENTION_IDENTIFIABLE and RESPONSE_OR_ENDPOINT_IDENTIFIABLE assess their respective scientific slots. "
        "BIOLOGICAL_CONTEXT_INTERPRETABLE assesses only context actually stated. "
        "Use only PASS, FAIL, or UNRESOLVED per criterion. Treat uncertainty as UNRESOLVED. "
        "You do not decide final quality eligibility, heldout eligibility, Search Plan compatibility, or gold truth.\n")
    user_prompt = ("Source-local group ID: {source_group_id}\n"
                   "Candidate packets JSON (each candidate has its own evidence span and bounded context):\n"
                   "{candidate_packets_json}\n"
                   "Output JSON schema:\n{output_schema_json}\n"
                   "Machine-output appendix:\n{machine_output_appendix}\n")
    write_text("quality_adjudicator_system_prompt.txt", system_prompt)
    write_text("quality_adjudicator_user_prompt_template.txt", user_prompt)
    appendix = ("Return exactly one JSON object matching the output schema. Copy field names, criterion names, and enum strings exactly. "
        "For every expected candidate ID return exactly one judgment; do not add or omit candidates. "
        "For every criterion use only PASS, FAIL, or UNRESOLVED in that criterion's field; do not move values across fields. "
        "Do not invent labels, aliases, scores, rankings, an overall eligibility field, or additional keys. "
        "For PASS or FAIL on EVIDENCE_SUPPORTS_PROPOSITION provide a short exact evidence fragment (maximum 240 characters) from that candidate's visible evidence; use null only for UNRESOLVED. "
        "Candidate array order is not a ranking. Return JSON only, with no Markdown or commentary.")
    write("quality_machine_output_contract.json", {"appendix_utf8": appendix,
          "appendix_sha256": sha(appendix.encode("utf-8")),
          "scientific_prompt_separate_file": "quality_adjudicator_system_prompt.txt",
          "field_specific_enum_domains": {name: STATES for name in CRITERIA},
          "no_alias_or_cross_field_substitution": True})
    write("quality_response_identity_binding_contract.json", {"function": "scripts/search_plan_v24_alpha317d_preregister_quality_v2_offline.py:validate_response",
          "implementation_sha256": sha(Path(__file__).read_bytes()),
          "expected_candidate_id_set_from_frozen_request_manifest": True,
          "record_count_exact": True, "duplicate_missing_extra_or_unknown_id": "FAIL_CLOSED",
          "source_group_id_exact_match": True, "response_array_order_scientifically_meaningless": True,
          "canonical_record_order": "ascending candidate_id after set equality validation"})
    write("quality_invalid_response_policy.json", {"invalid_states": ["missing_candidate", "extra_candidate",
          "duplicate_candidate", "unknown_candidate_id", "wrong_source_group", "missing_criterion",
          "unexpected_criterion", "invalid_enum", "invalid_schema", "invalid_evidence_reference"],
          "behavior": "freeze raw response, mark source-call invalid, stop run; no scientific repair or replacement",
          "model_repair_or_second_opinion": False})
    write("provider_execution_ambiguity_policy.json", {"max_inference_attempts_per_source_group": 1,
          "automatic_retry": False,
          "known_no_inference_transport_retry": "not enabled in this protocol",
          "ambiguous_execution": "STOP_WITHOUT_REPLACEMENT_CALL",
          "provider_or_model_switch": False})
    write("one_source_per_quality_call_contract.json", {"one_source_article_per_call": True,
          "surviving_candidates_per_call_minimum": 1, "surviving_candidates_per_call_maximum": 3,
          "cross_source_candidate_batching": False, "fresh_context_each_call": True,
          "builder_and_quality_calls_separate": True})
    write("candidate_independence_contract.json", {"candidate_specific_evidence": True,
          "one_candidate_evidence_may_ground_another": False,
          "cross_candidate_comparison_or_ranking": False,
          "overlapping_spans_allowed_but_judgments_separate": True})
    write("quality_ranking_prohibition.json", {"rank": False, "best_candidate": False,
          "preferred_candidate": False, "confidence_ordering": False, "numeric_quality_score": False,
          "model_selects_final_candidate": False})
    write("deterministic_one_per_source_selector.json", {"selector_version": SELECTOR_VERSION,
          "implementation_sha256": sha(Path(__file__).read_bytes()),
          "selection_seed_sha256": selector_seed,
          "seed_preimage": "ASCII PropositionQualityAdjudicationV2|one-per-source-selector-v1",
          "architecture_independent_seed": True,
          "key_preimage": "canonical JSON UTF-8 [selector_version, seed_sha256, opaque_source_group_id, opaque_candidate_id]",
          "choice": "minimum unsigned SHA-256 digest; candidate ID lexicographic tie-break",
          "eligible_candidate_set_only": True,
          "runs_after_all_source_local_quality_outputs_and_cross_source_duplicate_control": True,
          "forbidden_inputs": ["builder array order", "scientific content", "confidence", "criterion pattern",
                               "domain", "retrievability", "Search Plan compatibility"],
          "function": "scripts/search_plan_v24_alpha317d_preregister_quality_v2_offline.py:select_one",
          "prospective_implementation_note": "Uses V2 opaque candidate IDs instead of alpha3.17 canonical scientific slot signatures; preserves deterministic, performance-blind selection authority."})
    write("duplicate_selection_order_authority_audit.json", {"status": "RESOLVED",
          "alpha3_17_choice_rule": choice["source_internal_choice_rule"],
          "alpha3_17_duplicate_control_sha256": sha((old / "duplicate_control_policy.json").read_bytes()),
          "order": ["semantic quality gate", "cross-source exact and semantic-near-duplicate control",
                    "deterministic at-most-one-per-source selector", "final pool eligibility"],
          "semantic_near_duplicate_review_not_performed_here": True,
          "unresolved_near_duplicate_blocks_pool_freeze": True})
    write("builder_output_freeze_barrier.json", {"before_any_quality_request": [
          "all builder calls for frozen construction-source manifest complete or fail-closed",
          "all raw builder outputs frozen", "builder V2 schema validation complete",
          "candidate IDs and exact within-source dedup frozen", "source-local evidence-reference existence checked",
          "deterministic lexical leakage checks frozen"],
          "builder_calls_after_quality_start": False})
    write("quality_request_manifest_freeze_barrier.json", {"source_set": "all source groups with at least one surviving candidate after deterministic prechecks",
          "all_quality_payloads_and_hashes_frozen_before_first_call": True,
          "actual_call_count_frozen_before_first_call": True,
          "dynamic_requests_after_first_call": False,
          "raw_responses_frozen_before_output_validation": True})
    write("quality_call_budget_formula.json", {"formula": "count of source groups with >=1 candidate surviving schema validation, exact dedup, evidence-reference existence and leakage checks",
          "maximum_quality_adjudication_calls": 72,
          "actual_quality_call_count_not_yet_known": True,
          "candidate_count_does_not_multiply_calls": True})
    write("anchor_firewall_quality_stage_contract.json", {"visible_identifiers": ["opaque group ID", "opaque candidate IDs"],
          "forbidden_identity_fields": ["PMID", "PMCID", "DOI", "source title", "journal", "authors",
          "private source token", "source rank", "anchor-vault path"],
          "pre_call_leak": "STOP_BEFORE_MODEL_CALL", "deidentified_span_and_context_only": True,
          "private_anchor_vault_unavailable_to_quality_model": True})
    write("quality_payload_blinding_audit_contract.json", {"pre_call_audit": [
          "payload schema allowlist", "PMID numeric pattern", "PMCID pattern", "DOI pattern",
          "exact private source title", "journal and author metadata", "private source token",
          "anchor-vault path", "Search Plan/query/label/retrieval-field keys"],
          "on_match": "STOP_BEFORE_MODEL_CALL", "no_redaction_after_match": True,
          "function": "scripts/search_plan_v24_alpha317d_preregister_quality_v2_offline.py:audit_quality_payload",
          "implementation_sha256": sha(Path(__file__).read_bytes()),
          "evidence_context_function": "scripts/search_plan_v24_alpha317d_preregister_quality_v2_offline.py:evidence_packet",
          "audit_input": "frozen private source-identity registry used only by pre-call controller, not included in payload"})
    write("future_stage_separation.json", {"alpha3_18A": "source acquisition only",
          "alpha3_18B": "builder V2 execution and quality manifest freeze only",
          "alpha3_18C": "independent quality adjudication only",
          "alpha3_19": "eligible public pool freeze and deterministic Fresh Heldout V3 selection",
          "alpha3_20": "frozen-architecture retrieval preregistration",
          "later_stage_outcome_may_modify_earlier_stage_artifact": False,
          "source_topup_after_builder_start": False,
          "builder_replacement_after_quality_start": False})
    write("scientific_state_safety_audit.json", {"provider_calls": 0, "llm_calls": 0,
          "network_calls": 0, "retrieval_calls": 0, "source_acquisition_calls": 0,
          "builder_calls": 0, "quality_calls": 0, "heldout_cases_selected": 0,
          "query_compilation_calls": 0, "historical_assets_modified": False})
    write("validation.json", {"status": "PASS", "builder_protocol_v2_verified": True,
          "authoritative_builder_candidate_cardinality": "0_TO_3",
          "quality_adjudicator_independent_from_builder": True,
          "quality_adjudicator_role": "proposition_quality_adjudicator",
          "quality_provider": "DeepSeek", "quality_model": "deepseek-v4-pro",
          "quality_criteria_authority_resolved": True,
          "semantic_grounding_judged_independently": True,
          "architecture_compatibility_is_quality_criterion": False,
          "criterion_states_exactly_PASS_FAIL_UNRESOLVED": True,
          "quality_numeric_scoring_used": False, "quality_ranking_used": False,
          "overall_quality_eligibility_deterministic": True,
          "one_source_per_quality_call": True,
          "candidate_array_order_semantically_meaningless": True,
          "quality_response_bound_by_candidate_id": True,
          "field_specific_enum_contract_frozen": True,
          "scientific_repair_calls_allowed": False,
          "multi_candidate_final_selection_deterministic": True,
          "duplicate_selection_order_resolved": True,
          "builder_outputs_frozen_before_quality_manifest": True,
          "quality_manifest_frozen_before_first_quality_call": True,
          "dynamic_source_replacement_after_builder_start": False,
          "anchor_identity_exposed_to_quality_adjudicator": False,
          "maximum_quality_adjudication_calls": 72,
          "actual_quality_call_count_not_yet_known": True,
          "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0})
    protocol_names = ["builder_protocol_v2_verification.json", "quality_criterion_authority_matrix.json",
        "proposition_quality_adjudicator_role.json", "quality_provider_config.json", "quality_visibility_contract.json",
        "quality_source_context_contract.json", "semantic_grounding_criterion.json", "quality_criteria_contract.json",
        "criterion_state_contract.json", "overall_quality_eligibility_rule.json",
        "proposition_quality_adjudication_v2_schema.json", "quality_adjudicator_system_prompt.txt",
        "quality_adjudicator_user_prompt_template.txt", "quality_machine_output_contract.json",
        "quality_response_identity_binding_contract.json", "quality_invalid_response_policy.json",
        "provider_execution_ambiguity_policy.json", "one_source_per_quality_call_contract.json",
        "candidate_independence_contract.json", "quality_ranking_prohibition.json",
        "deterministic_one_per_source_selector.json", "duplicate_selection_order_authority_audit.json",
        "builder_output_freeze_barrier.json", "quality_request_manifest_freeze_barrier.json",
        "quality_call_budget_formula.json", "anchor_firewall_quality_stage_contract.json",
        "quality_payload_blinding_audit_contract.json", "future_stage_separation.json"]
    protocol_root = sha(canonical([[name, sha((RUN / name).read_bytes())] for name in sorted(protocol_names)]))
    write_text("proposition_quality_adjudication_v2_protocol_sha256", protocol_root + "\n")
    write("summary.json", {"status": "completed", "builder_protocol_v2_sha256": BUILDER_ROOT,
          "builder_output_schema_v2_sha256": BUILDER_SCHEMA_ROOT,
          "proposition_quality_adjudication_v2_protocol_sha256": protocol_root,
          "next_stage_recommendation": "PREREGISTER_ALPHA3_18A_SOURCE_ACQUISITION_EXECUTION",
          "historical_assets_modified": False})
    run_root = aggregate(RUN, "search_plan_v24_dev_alpha3_17d_sha256")
    write_text("search_plan_v24_dev_alpha3_17d_sha256", run_root + "\n")
    assert aggregate(RUN, "search_plan_v24_dev_alpha3_17d_sha256") == run_root
    print(json.dumps({"status": "completed", "protocol_root": protocol_root,
                      "run_root": run_root, "provider_calls": 0, "network_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
