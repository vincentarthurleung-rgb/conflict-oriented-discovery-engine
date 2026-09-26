import hashlib
import json
from pathlib import Path

from scripts.search_plan_v24_alpha312_preregister_offline import (
    A310, A311, COPIED_POLICY_FILES, RUN, canonical, contribution_mapping,
    lexical_authority, verify_upstream,
)


REQUIRED = {
    "upstream_root_verification.json", "canonical_scientific_corpus_binding_verification.json",
    "alpha3_11_query_set_verification.json", "query_pair_mapping.jsonl",
    "lexical_change_summary.json", "lexical_authority_verification.json",
    "lexical_budget_freeze.json", "structural_immutability_audit.json",
    "downstream_policy_compatibility_audit.json", "downstream_policy_reuse_matrix.json",
    "query_execution_policy.json", "technical_retry_policy.json",
    "technical_continuation_policy.json", "runtime_adaptation_prohibition.json",
    "retrieval_viability_metrics.json", "lexical_attribution_metric_policy.json",
    "variant_attribution_metric_policy.json", "case_union_policy.json",
    "tail_policy.json", "metadata_policy.json", "candidate_validation_policy.json",
    "oa_eligibility_policy.json", "selection_fulltext_policy.json",
    "known_paper_blindness_policy.json", "historical_label_blinding_policy.json",
    "five_architecture_comparison_plan.json",
    "bounded_lexical_realization_v2_development_execution_manifest.json",
    "bounded_lexical_realization_v2_development_execution_manifest_sha256",
    "scientific_state_safety_audit.json", "validation.json", "summary.json",
    "search_plan_v24_dev_alpha3_12_sha256",
}


def read(name):
    return json.loads((RUN / name).read_text())


def test_frozen_inputs_and_contribution_mapping():
    assert len(verify_upstream()[0]) == 5
    mapping, summary, contributions, queries = contribution_mapping()
    assert len(mapping) == len(contributions) == 63
    assert len(queries) == 55
    assert summary["alpha39_lexically_changed_only_query_contribution_count"] == 63
    assert summary["structurally_unmappable_query_contributions"] == 0
    assert lexical_authority(contributions)["unattributed_executable_surface_count"] == 0


def test_required_artifacts_and_roots_are_immutable_and_complete():
    assert REQUIRED <= {p.name for p in RUN.iterdir() if p.is_file()}
    assert not any(p.is_symlink() for p in RUN.rglob("*"))
    manifest_path = RUN / "bounded_lexical_realization_v2_development_execution_manifest.json"
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert manifest_sha == (RUN / "bounded_lexical_realization_v2_development_execution_manifest_sha256").read_text().strip()
    assert manifest_sha != (A310 / "search_constraint_allocation_v1_development_execution_manifest_sha256").read_text().strip()
    manifest = read(manifest_path.name)
    assert manifest["execution_status"] == "NOT_EXECUTED_PREREGISTRATION"
    assert manifest["observed_retrieval_values"] is None
    assert len(manifest["exact_queries"]) == 55
    assert len(manifest["per_contribution_provenance"]) == 63
    assert manifest["target_sha256_by_case"] == json.loads((A310 / "search_constraint_allocation_v1_development_execution_manifest.json").read_text())["target_sha256_by_case"]
    assert manifest["query_present_set_source"] == "LexicalCoverageCertificateV2.role_alternatives"
    core = [row for row in manifest["per_contribution_provenance"] if row["variant_class"] == "CORE_RELATION"]
    assert core and all("BIOLOGICAL_UNIT_CONTEXT" not in row["lexical_alternative_set_ids"] for row in core)
    root_pairs = [[p.name, hashlib.sha256(p.read_bytes()).hexdigest()] for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "search_plan_v24_dev_alpha3_12_sha256"]
    root = hashlib.sha256(canonical(root_pairs)).hexdigest()
    assert root == (RUN / "search_plan_v24_dev_alpha3_12_sha256").read_text().strip()


def test_downstream_reuse_and_blinding():
    for name in COPIED_POLICY_FILES:
        assert (RUN / name).read_bytes() == (A310 / name).read_bytes()
    audit = read("downstream_policy_compatibility_audit.json")
    assert audit["downstream_policy_compatible"]
    assert audit["material_downstream_policy_changes"] == 0
    query_policy = read("query_execution_policy.json")
    assert query_policy["execution_order"] == "frozen alpha3.11 query-set row order"
    assert query_policy["input_identity_change_only"]
    assert query_policy["material_execution_semantics_changed"] is False
    safety = read("scientific_state_safety_audit.json")
    assert all(safety[k] == 0 for k in (
        "network_calls", "retrieval_calls", "provider_calls", "llm_calls",
        "hit_counts_seen", "candidate_records_seen", "known_pmid_checks",
        "historical_label_reads", "scientific_relevance_adjudications",
    ))
    assert read("canonical_scientific_corpus_binding_verification.json")["source_binding_sha256"] == hashlib.sha256((A311 / "canonical_scientific_corpus_binding.json").read_bytes()).hexdigest()
