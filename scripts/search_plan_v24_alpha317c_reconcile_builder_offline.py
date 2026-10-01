#!/usr/bin/env python3
"""Prospectively reconcile builder cardinality without changing frozen ancestors."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
UP17 = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17_new_blinded_proposition_pool_preregistration_offline"
UP17A = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"
UP17B = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17b_independent_proposition_quality_adjudication_preregistration_offline"
OUT = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17c_builder_cardinality_reconciliation_offline"
ROOT17 = "10bc7cc1f03b0cdf38b4409f624b10697ffef3939053601cfba2dc4ea74cece6"
ROOT17A = "a23e549cf9d83714782d4283c823ee94ce569f5f00f820fc2c4e0b9d3ee7248e"
ROOT17B = "76d0fe4153f9703ab5cf3f076f3fd04fe5f238d48e17154fc369c5e594527035"
POOL_ROOT = "69a63d7ce9f08e8714413247aa4a39478a5eb0acbb39925e3dadeb9b6a45b64b"
SOURCE_ROOT = "755702713972012bc062f7cba43eea95708c9a5e75ca5c93e49ef5396f0c00c0"
OLD_BUILDER_ROOT = "e3e147c5af132e15ab7a9c3612c3d03eaf31a77badea754b86f03a3f9c953fe8"
VERSION = "PropositionBuilderProtocolV2"
SOURCE_NAMES = ["exact_source_queries.jsonl", "source_execution_policy.json", "source_frame_freeze_policy.json",
                "cross_stratum_duplicate_policy.json", "source_sampling_algorithm.json", "mechanical_source_exclusion_order.json",
                "seen_source_local_registry.json", "construction_fulltext_acquisition_policy.json",
                "construction_fulltext_failure_policy.json"]


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


def selected_root(directory: Path, names: list[str]) -> str:
    return sha(canonical([[name, sha((directory / name).read_bytes())] for name in sorted(names)]))


def write(name: str, value: Any) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(canonical(value) + b"\n")


def verify() -> tuple[dict, dict, dict]:
    for directory, name, expected in ((UP17, "search_plan_v24_dev_alpha3_17_sha256", ROOT17),
                                      (UP17A, "search_plan_v24_dev_alpha3_17a_sha256", ROOT17A),
                                      (UP17B, "search_plan_v24_dev_alpha3_17b_sha256", ROOT17B)):
        if aggregate(directory, name) != expected or (directory / name).read_text().strip() != expected:
            raise RuntimeError(f"frozen ancestor root mismatch: {directory.name}")
    if (UP17 / "new_blinded_proposition_pool_protocol_sha256").read_text().strip() != POOL_ROOT:
        raise RuntimeError("original pool protocol mismatch")
    if selected_root(UP17A, SOURCE_NAMES) != SOURCE_ROOT or (UP17A / "new_pool_source_acquisition_manifest_sha256").read_text().strip() != SOURCE_ROOT:
        raise RuntimeError("source acquisition manifest changed")
    if (UP17A / "proposition_builder_protocol_sha256").read_text().strip() != OLD_BUILDER_ROOT:
        raise RuntimeError("historical builder protocol mismatch")
    original = load(UP17 / "proposition_builder_schema.json")
    narrowed = load(UP17A / "proposition_builder_output_schema.json")
    final_choice = load(UP17 / "one_proposition_per_source_policy.json")
    if (original["schema"]["properties"]["propositions"]["minItems"],
        original["schema"]["properties"]["propositions"]["maxItems"]) != (0, 3):
        raise RuntimeError("alpha3.17 does not authorize 0..3")
    if (narrowed["schema"]["properties"]["propositions"]["minItems"],
        narrowed["schema"]["properties"]["propositions"]["maxItems"]) != (0, 1):
        raise RuntimeError("alpha3.17a conflict not reproduced")
    if final_choice["eligible_heldout_propositions_per_source_article_maximum"] != 1 or "After generic grounding, leakage, quality, and duplicate gates" not in final_choice["source_internal_choice_rule"]:
        raise RuntimeError("downstream at-most-one authority missing")
    failed = load(UP17B / "builder_cardinality_authority_audit.json")
    if failed["classification"] != "UPSTREAM_CONTRACT_INCONSISTENT":
        raise RuntimeError("alpha3.17b conflict status changed")
    if load(UP17A / "scientific_state_safety_audit.json")["provider_calls"] != 0:
        raise RuntimeError("unexpected builder inference before amendment")
    return original, narrowed, final_choice


def candidate_id(opaque_source_id: str, candidate: dict) -> str:
    """Opaque, order-independent identity; caller must keep source-ID map private."""
    if not opaque_source_id or any(ch in opaque_source_id for ch in " \t\r\n"):
        raise ValueError("invalid opaque source ID")
    payload_sha = sha(canonical(candidate))
    preimage = canonical([VERSION, opaque_source_id, payload_sha])
    return "pcv2_" + sha(preimage)


def canonicalize_candidates(opaque_source_id: str, candidates: list[dict]) -> list[dict]:
    """Collapse exact duplicate payloads; preserve original positions privately."""
    by_payload: dict[str, dict] = {}
    for position, candidate in enumerate(candidates):
        payload_sha = sha(canonical(candidate))
        if payload_sha not in by_payload:
            by_payload[payload_sha] = {"candidate_id": candidate_id(opaque_source_id, candidate),
                                      "candidate_payload_sha256": payload_sha,
                                      "candidate": candidate, "original_array_positions": []}
        by_payload[payload_sha]["original_array_positions"].append(position)
    return sorted(by_payload.values(), key=lambda item: (item["candidate_payload_sha256"], item["candidate_id"]))


def main() -> None:
    if OUT.exists():
        raise RuntimeError("alpha3.17c exists; never regenerate frozen amendment")
    original, narrowed, final_choice = verify()
    source_schema = original["schema"]
    old_schema = narrowed["schema"]
    if source_schema["properties"]["propositions"]["items"] != old_schema["properties"]["propositions"]["items"]:
        raise RuntimeError("builder scientific item schema differs beyond cardinality")
    v2_schema = deepcopy(source_schema)
    v2_schema["properties"]["candidates"] = v2_schema["properties"].pop("propositions")
    v2_schema["required"] = ["candidates" if item == "propositions" else item for item in v2_schema["required"]]
    assert v2_schema["properties"]["candidates"]["minItems"] == 0
    assert v2_schema["properties"]["candidates"]["maxItems"] == 3
    forbidden = {"quality_score", "retrievability_score", "preferred", "ranking", "best_candidate", "search_plan_compatibility"}
    assert not (forbidden & set(v2_schema["properties"]))
    assert not (forbidden & set(v2_schema["properties"]["candidates"]["items"]["properties"]))
    old_prompt = (UP17A / "proposition_builder_system_prompt.txt").read_text(encoding="utf-8")
    old_user_template = (UP17A / "proposition_builder_user_prompt_template.txt").read_text(encoding="utf-8")
    assert "Propose zero or one neutral, experimentally grounded scientific proposition." in old_prompt
    assert "empty propositions array" in old_prompt
    assert "A nonzero proposition must cite" in old_prompt
    v2_prompt = old_prompt.replace(
        "Propose zero or one neutral, experimentally grounded scientific proposition.",
        "Propose zero to three independent, neutral, experimentally grounded scientific candidate propositions. Do not rank or prefer candidates.")
    v2_prompt = v2_prompt.replace("empty propositions array", "empty candidates array")
    v2_prompt = v2_prompt.replace("A nonzero proposition must cite", "Each candidate must cite")
    assert "zero or one" not in v2_prompt
    provider = load(UP17A / "proposition_builder_provider_config.json")
    visibility = load(UP17A / "proposition_builder_visibility_contract.json")
    request = load(UP17A / "proposition_builder_request_contract.json")
    OUT.mkdir()
    for name, directory, expected in (("alpha3_17_root_verification.json", UP17, ROOT17),
                                      ("alpha3_17a_root_verification.json", UP17A, ROOT17A),
                                      ("alpha3_17b_failure_verification.json", UP17B, ROOT17B)):
        marker = {UP17: "search_plan_v24_dev_alpha3_17_sha256",
                  UP17A: "search_plan_v24_dev_alpha3_17a_sha256",
                  UP17B: "search_plan_v24_dev_alpha3_17b_sha256"}[directory]
        write(name, {"status": "PASS", "expected_sha256": expected,
                     "actual_sha256": aggregate(directory, marker),
                     "historical_artifact_modified": False})
    write("builder_cardinality_conflict_matrix.json", {
        "alpha3_17_builder_output": {"minimum": 0, "maximum": 3,
            "schema_sha256": sha((UP17 / "proposition_builder_schema.json").read_bytes())},
        "alpha3_17a_builder_request_output": {"minimum": 0, "maximum": 1,
            "schema_sha256": sha((UP17A / "proposition_builder_output_schema.json").read_bytes())},
        "alpha3_17b_classification": "UPSTREAM_CONTRACT_INCONSISTENT",
        "new_decision_applies_prospectively_only": True})
    write("contract_responsibility_analysis.json", {
        "alpha3_17_role": "scientific construction architecture; 0..3 builder proposals, followed by quality, duplicate and downstream at-most-one processing",
        "alpha3_17a_role": "execution preflight; its 0..1 request schema narrowed the scientific candidate space and failed closed",
        "alpha3_17b_role": "preserved conflict finding, not an authority to choose a schema",
        "reconciliation_basis": "explicit prospective user authorization in alpha3.17c; no retroactive rewrite",
        "why_not_0_to_1": "It would force implicit model source-internal scientific selection before independent quality adjudication.",
        "stage_order": ["GENERATION", "QUALITY_ADJUDICATION", "DUPLICATE_CONTROL", "DETERMINISTIC_AT_MOST_ONE_PER_SOURCE_SELECTION"]})
    write("builder_cardinality_reconciliation_decision.json", {
        "decision_class": "BUILDER_CARDINALITY_PROTOCOL_AMENDMENT",
        "amendment_class": "PROSPECTIVE_PRE_EXECUTION_AMENDMENT",
        "authoritative_builder_candidate_cardinality": "0_TO_3", "minimum": 0, "maximum": 3,
        "supersedes": "only conflicting alpha3.17a builder request/output cardinality and directly dependent prompt/schema fields",
        "historical_alpha3_17a_0_to_1_retained_as_provenance": True,
        "scientific_builder_outputs_affected_by_amendment": 0})
    write("proposition_builder_output_schema_v2.json", {
        "artifact_schema_version": "PropositionBuilderOutputV2",
        "protocol_version": VERSION, "schema": v2_schema,
        "candidate_item_scientific_fields_unchanged_from_alpha3_17": True,
        "candidate_array_order_semantically_meaningless": True,
        "model_generated_candidate_id_allowed": False})
    schema_sha = sha((OUT / "proposition_builder_output_schema_v2.json").read_bytes())
    # The standalone digest file follows the repository's text-marker convention.
    (OUT / "proposition_builder_output_schema_v2_sha256").write_text(schema_sha + "\n", encoding="utf-8")
    write("proposition_builder_protocol_v2.json", {
        "artifact_schema_version": VERSION,
        "superseded_builder_protocol_sha256": OLD_BUILDER_ROOT,
        "active_output_schema_file": "proposition_builder_output_schema_v2.json",
        "active_output_schema_sha256": schema_sha,
        "source_acquisition_manifest_sha256": SOURCE_ROOT,
        "provider_configuration": provider, "visibility_contract": visibility,
        "request_contract_unchanged_except_prompt_and_schema": request,
        "system_prompt_utf8": v2_prompt, "system_prompt_sha256": sha(v2_prompt.encode("utf-8")),
        "user_prompt_template_utf8": old_user_template,
        "user_prompt_template_sha256": sha(old_user_template.encode("utf-8")),
        "candidate_cardinality": {"minimum": 0, "maximum": 3},
        "one_source_per_builder_call": True, "builder_ranking_allowed": False,
        "builder_preferred_candidate_allowed": False,
        "builder_quality_or_heldout_authority": False,
        "no_scientific_repair_calls": True})
    protocol_sha = sha((OUT / "proposition_builder_protocol_v2.json").read_bytes())
    (OUT / "proposition_builder_protocol_v2_sha256").write_text(protocol_sha + "\n", encoding="utf-8")
    write("candidate_identity_contract.json", {
        "implementation": "scripts/search_plan_v24_alpha317c_reconcile_builder_offline.py:candidate_id",
        "identity_preimage": "canonical JSON UTF-8 of [PropositionBuilderProtocolV2, opaque_source_id, SHA256(canonical candidate JSON UTF-8)]",
        "candidate_id": "pcv2_ + lowercase SHA256(identity_preimage)",
        "opaque_source_id_private": True, "model_generated_id_used": False,
        "raw_PMiD_PMCID_DOI_title_in_id": False, "hash_collision_outcome": "FAIL_CLOSED"})
    write("candidate_order_semantics_contract.json", {
        "candidate_array_order_semantically_meaningless": True,
        "model_order_is_not_rank_or_preference": True,
        "canonical_storage_order": "ascending candidate payload SHA-256, then candidate ID",
        "original_array_positions_private_provenance_only": True})
    write("within_source_exact_dedup_policy.json", {
        "timing": "after whole-response schema validation and before deterministic evidence and quality checks",
        "identity": "exact canonical JSON UTF-8 candidate payload equality; evidence span included",
        "dedup_within_source_only": True, "original_array_positions_preserved_privately": True,
        "semantic_near_duplicate_decision_here": False,
        "implementation": "scripts/search_plan_v24_alpha317c_reconcile_builder_offline.py:canonicalize_candidates"})
    write("candidate_evidence_grounding_contract.json", {
        "each_candidate_requires_own_span": True,
        "span_schema_identical_to_alpha3_17": True,
        "span_existence_validation": "exact source_field and offsets against frozen source-local text before quality adjudication",
        "semantic_support_judgment_deferred_to_independent_quality_adjudication": True,
        "candidate_A_span_does_not_automatically_ground_candidate_B": True})
    write("builder_zero_output_policy.json", {"zero_candidates_valid": True,
        "retry_or_repair_for_zero": False, "source_replacement_for_zero": False,
        "stratum_topup_for_zero": False, "quality_call_for_zero": False})
    write("at_most_one_per_source_boundary.json", {
        "eligible_public_pool_maximum_per_source": 1,
        "applied_after": ["independent quality adjudication", "duplicate processing"],
        "not_applied_by_builder": True,
        "future_selector_must_be_frozen_in_quality_preregistration": True,
        "selection_may_not_use_builder_order_or_confidence_or_retrieval": True,
        "alpha3_17_source_internal_choice_rule_preserved": final_choice["source_internal_choice_rule"]})
    write("future_quality_interface_contract.json", {
        "builder_protocol_version": VERSION,
        "builder_output_schema_v2_sha256": schema_sha,
        "quality_call_unit": "one source article's surviving candidate set (1..3 after deterministic prechecks)",
        "maximum_quality_calls_if_one_source_per_call": 72,
        "candidate_judgments_independent": True,
        "full_quality_protocol_frozen_here": False})
    write("source_acquisition_immutability_audit.json", {
        "source_acquisition_policy_changed": False,
        "source_acquisition_manifest_sha256": SOURCE_ROOT,
        "source_artifact_hashes": [[name, sha((UP17A / name).read_bytes())] for name in SOURCE_NAMES],
        "query_count": len((UP17A / "exact_source_queries.jsonl").read_bytes().splitlines()),
        "source_frame_cap": 200, "sample_cap_per_stratum": 12,
        "sampling_seed": load(UP17 / "sampling_seed_contract.json")["seed_sha256"],
        "source_phase_before_builder_phase": True})
    write("prospective_amendment_disclosure.json", {
        "amendment": "BUILDER_CARDINALITY_PROTOCOL_AMENDMENT",
        "type": "PROSPECTIVE_PRE_EXECUTION_AMENDMENT",
        "builder_inferences_before_amendment": 0,
        "scientific_builder_outputs_affected_by_amendment": 0,
        "old_0_to_1_schema_retained_unchanged": True,
        "new_V2_0_to_3_schema_active_only_for_future_execution": True})
    write("scientific_state_safety_audit.json", {
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0,
        "source_acquisition_calls": 0, "builder_calls": 0, "quality_calls": 0,
        "propositions_generated": 0, "heldout_cases_selected": 0,
        "historical_alpha3_17_modified": False, "historical_alpha3_17a_modified": False,
        "historical_alpha3_17b_modified": False, "search_architecture_changed": False,
        "historical_assets_modified": False})
    write("validation.json", {
        "status": "PASS", "upstream_cardinality_conflict_preserved": True,
        "builder_cardinality_reconciled": True, "authoritative_builder_candidate_cardinality": "0_TO_3",
        "builder_ranking_allowed": False, "builder_preferred_candidate_allowed": False,
        "candidate_array_order_semantically_meaningless": True,
        "at_most_one_per_source_applied_after_quality": True,
        "one_source_per_builder_call": True, "maximum_builder_scientific_calls": 72,
        "source_acquisition_policy_changed": False, "search_architecture_changed": False,
        "builder_calls_before_amendment": 0, "provider_calls": 0, "llm_calls": 0,
        "network_calls": 0, "retrieval_calls": 0})
    write("summary.json", {
        "status": "completed", "authoritative_builder_candidate_cardinality": "0_TO_3",
        "proposition_builder_protocol_v2_sha256": protocol_sha,
        "proposition_builder_output_schema_v2_sha256": schema_sha,
        "source_acquisition_manifest_sha256": SOURCE_ROOT,
        "next_stage_recommendation": "PREREGISTER_INDEPENDENT_PROPOSITION_QUALITY_ADJUDICATION_V2",
        "historical_assets_modified": False})
    root = aggregate(OUT, "search_plan_v24_dev_alpha3_17c_sha256")
    (OUT / "search_plan_v24_dev_alpha3_17c_sha256").write_text(root + "\n", encoding="utf-8")
    assert aggregate(OUT, "search_plan_v24_dev_alpha3_17c_sha256") == root
    print(json.dumps({"status": "completed", "run_root": root,
                      "builder_protocol_v2_sha256": protocol_sha,
                      "builder_schema_v2_sha256": schema_sha,
                      "provider_calls": 0, "network_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
