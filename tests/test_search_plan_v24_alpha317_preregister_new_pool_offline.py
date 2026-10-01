"""Verify alpha3.17 preregistration roots and isolation boundaries offline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17_new_blinded_proposition_pool_preregistration_offline"
UPSTREAM = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_16_architecture_freeze_fresh_heldout_v3_preregistration_offline"


def load(name: str) -> dict:
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def test_upstream_architecture_and_run_roots() -> None:
    previous = load("alpha3_16_root_verification.json")
    assert previous["status"] == "PASS"
    assert previous["actual_sha256"] == (UPSTREAM / "search_plan_v24_dev_alpha3_16_sha256").read_text().strip()
    architecture = load("architecture_freeze_verification.json")
    assert architecture["status"] == "PASS"
    assert architecture["actual_sha256"] == (UPSTREAM / "architecture_freeze_sha256").read_text().strip()
    assert architecture["all_component_hashes_match"] is True
    files = [path for path in sorted(RUN.iterdir())
             if path.is_file() and path.name != "search_plan_v24_dev_alpha3_17_sha256"]
    pairs = [[path.name, sha(path)] for path in files]
    assert digest(pairs) == (RUN / "search_plan_v24_dev_alpha3_17_sha256").read_text().strip()


def test_protocol_root_and_private_public_firewall() -> None:
    protocol_files = [
        "new_pool_construction_contract.json", "source_universe_contract.json", "source_date_policy.json",
        "generic_source_strata.json", "source_query_restriction_policy.json", "source_sampling_policy.json",
        "sampling_seed_contract.json", "source_exclusion_policy.json", "proposition_builder_isolation_contract.json",
        "proposition_builder_schema.json", "construction_grounding_contract.json",
        "source_evidence_span_contract.json", "paraphrase_leakage_policy.json",
        "lexical_overlap_audit_contract.json", "proposition_quality_gate.json",
        "architecture_compatibility_nonuse_policy.json", "pool_size_policy.json",
        "one_proposition_per_source_policy.json", "duplicate_control_policy.json",
        "pool_eligibility_state_contract.json", "anchor_vault_contract.json", "public_pool_contract.json",
        "anchor_firewall_policy.json", "heldout_sampling_policy.json",
        "development_label_nonuse_policy.json", "future_stage_boundary.json",
    ]
    assert digest([[name, sha(RUN / name)] for name in sorted(protocol_files)]) == (
        RUN / "new_blinded_proposition_pool_protocol_sha256").read_text().strip()
    vault = load("anchor_vault_contract.json")
    public = load("public_pool_contract.json")
    assert vault["vault_defined_not_created_now"] is True
    assert vault["vault_available_to_compiler_retrieval_selector_or_scientific_reviewer"] is False
    assert "PMID" in public["forbidden_public_fields"]
    assert "source_evidence_span" in public["forbidden_public_fields"]
    assert load("construction_grounding_contract.json")["construction_evidence_span_present_required"] is True
    assert load("architecture_compatibility_nonuse_policy.json")["quality_gate_may_ask_pubmed_will_retrieve"] is False


def test_preexecution_firewall_and_stage_boundaries() -> None:
    validation = load("validation.json")
    assert validation["status"] == "PASS"
    assert validation["old_unresolved_propositions_promoted_to_eligible"] == 0
    assert validation["pool_freeze_before_heldout_selection"] is True
    assert validation["query_compilation_before_target_freeze"] is False
    safety = load("scientific_state_safety_audit.json")
    for key in ("new_propositions_generated", "heldout_cases_selected", "query_compilation_calls",
                "provider_calls", "llm_calls", "network_calls", "retrieval_calls"):
        assert safety[key] == 0
    assert load("future_stage_boundary.json")["next_authorization_required"] == (
        "AUTHORIZE_NEW_SOURCE_POOL_ACQUISITION_AND_BLINDED_PROPOSITION_CONSTRUCTION")

