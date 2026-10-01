"""Focused frozen-quality-protocol checks; no scientific adjudication."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.search_plan_v24_alpha317d_preregister_quality_v2_offline import (
    CRITERIA, audit_quality_payload, evidence_packet, quality_result,
    select_one, source_group_id, validate_response,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17d_independent_quality_adjudication_v2_preregistration_offline"
UP = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17c_builder_cardinality_reconciliation_offline"


def _load(name: str):
    return json.loads((RUN / name).read_text())


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_builder_binding_and_criterion_authority() -> None:
    verification = _load("builder_protocol_v2_verification.json")
    assert verification["status"] == "PASS"
    assert verification["builder_protocol_v2_sha256"] == _sha((UP / "proposition_builder_protocol_v2.json").read_bytes())
    assert verification["builder_output_schema_v2_sha256"] == _sha((UP / "proposition_builder_output_schema_v2.json").read_bytes())
    assert verification["authoritative_builder_candidate_cardinality"] == "0_TO_3"
    matrix = _load("quality_criterion_authority_matrix.json")
    assert matrix["status"] == "RESOLVED"
    assert [entry["criterion"] for entry in matrix["criteria"]] == CRITERIA
    assert matrix["actor_response_split_is_conjunctive_not_new_semantics"]
    assert not matrix["architecture_compatibility_added"]


def test_quality_derivation_is_conservative() -> None:
    passing = {name: "PASS" for name in CRITERIA}
    assert quality_result(passing)["overall_quality_state"] == "QUALITY_ELIGIBLE"
    passing["SCIENTIFICALLY_COHERENT"] = "UNRESOLVED"
    assert quality_result(passing) == {"overall_quality_state": "QUALITY_INELIGIBLE",
                                      "failed_criteria": [], "unresolved_criteria": ["SCIENTIFICALLY_COHERENT"]}
    with pytest.raises(ValueError):
        quality_result({"SCIENTIFICALLY_COHERENT": "PASS"})
    assert "overall_quality_state" not in _load("proposition_quality_adjudication_v2_schema.json")["schema"]["properties"]


def test_response_identity_and_evidence_binding() -> None:
    schema = _load("proposition_quality_adjudication_v2_schema.json")["schema"]
    states = {name: "PASS" for name in CRITERIA}
    records = [{"schema_version": "PropositionQualityAdjudicationV2", "candidate_id": candidate,
                "criteria": states, "evidence_support_reference": "observed increase"}
               for candidate in ("pcv2_b", "pcv2_a")]
    response = {"schema_version": "PropositionQualityAdjudicationV2", "source_group_id": "qgv2_example",
                "judgments": records}
    evidence = {"pcv2_a": "observed increase in response", "pcv2_b": "observed increase in response"}
    assert [row["candidate_id"] for row in validate_response(response, "qgv2_example", set(evidence), evidence, schema)] == ["pcv2_a", "pcv2_b"]
    with pytest.raises(ValueError):
        validate_response(response, "wrong_group", set(evidence), evidence, schema)
    records[1]["candidate_id"] = "pcv2_b"
    with pytest.raises(ValueError):
        validate_response(response, "qgv2_example", set(evidence), evidence, schema)


def test_selector_and_context_do_not_use_array_order() -> None:
    selector = _load("deterministic_one_per_source_selector.json")
    seed = selector["selection_seed_sha256"]
    a = select_one("qgv2_example", ["pcv2_a", "pcv2_b"], seed)
    assert a == select_one("qgv2_example", ["pcv2_b", "pcv2_a"], seed)
    assert select_one("qgv2_example", [], seed) is None
    with pytest.raises(ValueError):
        select_one("qgv2_example", ["pcv2_a", "pcv2_a"], seed)
    assert evidence_packet("abcdefghijklmnopqrstuvwxyz", 5, 8, "fgh")["exact_evidence_span"] == "fgh"
    with pytest.raises(ValueError):
        evidence_packet("abcdefghijklmnopqrstuvwxyz", 5, 8, "xyz")
    assert source_group_id("opaque_private_token").startswith("qgv2_")


def test_payload_blinding_rejects_source_identity() -> None:
    packet = {"candidate_id": "pcv2_example", "scientific_fields": {
        "actor_or_intervention": "A", "action": "changes", "relation_direction": "INCREASES",
        "response_or_endpoint": "B", "biological_unit": "cells", "species": None,
        "intrinsic_conditioning": None, "intrinsic_therapy_context": None,
        "intrinsic_disease_or_genotype_context": None},
        "neutral_proposition": "A increases B in cells",
        "evidence": {"exact_evidence_span": "A increased B", "bounded_local_context": "A increased B"}}
    payload = {"source_group_id": "qgv2_example", "candidate_packets": [packet]}
    audit_quality_payload(payload, {"pmcid": "PMC1234567", "title": "Private study title"})
    packet["evidence"]["bounded_local_context"] = "Recorded in PMC1234567"
    with pytest.raises(ValueError):
        audit_quality_payload(payload, {"pmcid": "PMC1234567"})


def test_protocol_and_run_roots_and_zero_calls() -> None:
    implementation_sha = _sha((ROOT / "scripts/search_plan_v24_alpha317d_preregister_quality_v2_offline.py").read_bytes())
    for name in ("quality_payload_blinding_audit_contract.json", "quality_response_identity_binding_contract.json",
                 "deterministic_one_per_source_selector.json"):
        assert _load(name)["implementation_sha256"] == implementation_sha
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
    def aggregate(names):
        pairs = [[name, _sha((RUN / name).read_bytes())] for name in sorted(names)]
        return _sha(json.dumps(pairs, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())
    assert aggregate(protocol_names) == (RUN / "proposition_quality_adjudication_v2_protocol_sha256").read_text().strip()
    names = [path.name for path in RUN.iterdir() if path.is_file() and path.name != "search_plan_v24_dev_alpha3_17d_sha256"]
    assert aggregate(names) == (RUN / "search_plan_v24_dev_alpha3_17d_sha256").read_text().strip()
    safety = _load("scientific_state_safety_audit.json")
    assert all(safety[key] == 0 for key in ("provider_calls", "llm_calls", "network_calls", "retrieval_calls", "quality_calls"))
